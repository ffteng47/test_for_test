# Oh Story（oh-story-claudecode）深度审查：业务逻辑流与代码流（逐函数核实版）

- 代码基线：`refrence_projects/oh-story-claudecode`（816 文件，13 个 skill + scripts + references + tests）
- 审查方式：直接读源码，结论附 `文件:行号` 证据
- 形态：**寄生宿主的 Skill 包**——自身无 Agent 运行时，靠 Claude Code / Codex / OpenCode / ZCode / Antigravity / OpenClaw 六端适配执行；确定性逻辑全部外置为脚本

## 1. 架构总览

| 层 | 位置 | 内容 |
|----|------|------|
| 技能层 | `skills/` | 13 个：story-long-write / story-long-scan(扫榜) / story-long-analyze(拆文) / story-short-write/scan/analyze / story-deslop(去AI味) / story-review / story-cover(封面) / story-import / story-setup / story / browser-cdp |
| 方法论资产 | `skills/story-long-write/references/` | 30+ 份：workflow-setup/volume/outline/chapter/daily/revision、long-format、writing-craft、long-chapter-hooks、long-chapter-quality、emotional-arc-design、deslop-gates、banned-words、anti-ai-writing、style-resolution、tracking-transaction、artifact-protocols、reader-contract-and-progression、author-memory……**真正护城河** |
| 确定性脚本 | `skills/story-long-write/scripts/` | 13 个（见 §3） |
| 质量工程 | `scripts/`（根） | 25+ CI 检查：六端适配器测试、hook 正则跨端同步、文档体积预算 check-doc-budget、参考文档门禁、playwright E2E |
| 多端适配 | `.claude-plugin/` `.zcode-plugin/` `.agents/` 等 | 同一 skill 六端分发 |

## 2. 业务逻辑流

### 2.1 全流水线（开书到成品）

```
story-setup（环境/端检测）
 → story-long-scan（扫榜：榜单采集→题材热度）
 → story-long-analyze（拆文：对标书→拆文库→对标/ 引用视图）
 → story-long-write Phase 1–3（定方向→定设定→卷纲→单元细纲，按确认点分时刻读 workflow-*）
 → Phase 4 正文（workflow-chapter.md 步骤 1–13）
      每章：build_writer_prompt.py 组装提示词 → 宿主/子agent 写正文
           → storyctl.py chapter check（字数+质量门禁）
           → storyctl.py chapter commit（追踪事务入账+派生视图重渲染）
 → story-deslop（去AI味专项）→ story-review（审稿）→ story-cover（封面）
```

### 2.2 写前必读纪律（SKILL.md 首屏，强制）

- 任何创建/修改故事文件前，按场景分块读到 EOF：`rg` 检索或局部摘读**不算完整读取**；旧会话的"读过"不能沿用
- 任一必需路径不存在/未读完 → **立即停止并报告准确路径，不得先写正文再补读**
- references 读完后立即重读用户请求+本章细纲+卷纲，**在上下文里记下本轮约束**（字数范围/必发生/禁止发生/时间锚/停笔点/章尾新债），references 只提供技法不得覆盖项目事实
- 文风裁决：写/改/审前必读 style-resolution.md 形成 `style_resolution`，优先级=当前请求 > 本书文风 > active 作者记忆 > 对标 > 通用参考

### 2.3 新增物三级（排纲/正文/处置共用）

1. **直接写**：微连接、路人、器物、一次性对话——不申报
2. **写了要报**：具名配角、势力、新伏笔、新关系或承诺——逐条进申报表，主会话核对后才算续写事实
3. **先问作者**：新主线事件/反转、金手指规则、真相或伏笔结算、读者契约、改变细纲已定结果——**写正文时不写，排纲时挂起列候选，主会话问作者**（=我方确认闸的交互形态参照）

### 2.4 单章状态机（storyctl.py chapter check）

`CHECK_EXIT_CODES = { ready:0, needs_decision:0, blocked:1, invalid:1, tool_unavailable:3 }`——**工具坏了（3）与正文要改（1）是不同出口**，检测工具缺失/崩溃 = unavailable，不是正文问题。

## 3. 代码流关键实现（逐函数证据）

### 3.1 storyctl.py（26112 字节）——状态权威 CLI

- `check_blocking_quality(outline, body)`（:147）：依次 subprocess 调 node 跑 `check-ai-patterns.js`、`check-degeneration.js`（`--check --json --fail-on=blocking`）、`normalize-punctuation.js --check`（失败=blocking PUNCTUATION_NOT_NORMALIZED）、`check-outline-copy.js`（细纲照搬，advisory+review=semantic）；工具缺失/崩溃进 `tool_errors`；status = unavailable（有 tool_errors）/ fail（有 blocking）/ pass
- `deslop_skipped(body)`（:141）：标题行下首 6 行窗口内 `<!-- 去味:跳过 -->` 豁免**仅 AI 句式**；退化类（复读/截断/拒绝语/工程词）**照常必须修**——豁免范围收窄是刻意的
- `_require_acceptable_length`（:341）：接受带外长度的两道底线——欠长 < 目标×`ACCEPT_FLOOR_RATIO`(0.5) 拒（BELOW_ACCEPT_FLOOR）；超长必须先 compress-once **真删**（删幅≥差额一半，用 baseline `body_sha256` 变化+ceiling 计算验证，删一两个字不算），否则 COMPRESSION_REQUIRED；作者拍板 `--force` 越过
- `chapter_commit`（:383）：quality 非 pass → QUALITY_BLOCKED；长度带外且未 accept → LENGTH_OUT_OF_BAND；追踪事务**禁止自带 wordcount**（`require("wordcount" not in document)`，宿主用 build_project_wordcount_record 注入）；事务入账后工作目录清理失败只报告、**绝不清仓失败反咬提交**（"The commit is already durable"）

### 3.2 tracking_commit.py（85476 字节）——追踪事务内核

- `追踪/_tracking-state.json` 唯一权威；`上下文.md`、`伏笔.md`、`时间线/`、`角色状态/*.md` 全部**派生视图，禁止手改**
- `merge_transaction`（:1095）双模式：append（推进 last_committed_chapter）/ revision（修订旧章）
  - `retired_characters` 只能 append 提交——注释原话："修订记录属于被改写的旧章，落在那里会**谎报退役发生的章节**"
  - 退役角色同事务不得更新、不得仍在 active_character_names
  - **context 条目整份提交**：掉落必须在 `delta.retired_context_items` 显式声明，未声明即拒（"漏写会静默丢历史裁定"）；revision 必须重交全部现存条目
  - foreshadow/timeline 走 `checkpoint_record`（时间线 keep_first_chapter 保留首登章）
- `render_timeline_views`（:617）**双视图**：作者真相时间线（客观事实/读者当前认知/揭示状态/实际揭示章 七列）+ 读者已知时间线（只呈现读者截至当前章已知，**不泄露作者侧客观真相**）——读者认知是每条事件的 `reader_knowledge` 字段
- `write_views`（:1197）：先写带 next revision 的 `上下文.md`——任何后续崩溃都会让 hook/check 发现视图 revision 与 state 不一致（**崩溃可检测性设计**）
- `warn_sizes`（:1213）：`DELTA_TARGET_BYTES` / `CONTEXT_TARGET_BYTES` / 角色卡体积预算，超限一次报全
- `project_write_lock`（:277）文件锁 + `atomic_write_text`（:243）原子写 + `find_retired_tracking_paths` 退役文件检测/归档

### 3.3 check-outline-contract.js（24521 字节）——细纲契约检查（门禁前置）

- 结构校验不判好坏："It never judges whether a value is good"；字段必须在场值可未知（`[待补充]`）
- 必填 FIELDS：`核心事件、字数目标、字数口径、单元ID/位置、目标情绪、主角目标/关键选择、章首钩子、爽点、本章禁止提前释放`——**爽点/目标情绪/章首钩子是细纲级必填设计字段，不是事后从正文抽的**
- `INTENT_FIELDS=['目标情绪','主角目标/关键选择']` 必须有实际内容；注释存证 #383 隔离实验："只补目标情绪与主角目标就复现了补满全部字段的收益"
- 字数语法与 `wordcount_core.py` **逐字同构**，`test-storyctl.py` 双跑同一批写法——"细纲验收通过的写法，storyctl chapter check 不能再拒"（跨工具契约一致性）
- `契约风险` 三档：契约安全/需补强/契约破坏

### 3.4 check-degeneration.js（15453 字节）——退化指纹检测

- **逐行复读**（:188）：紧邻整行重复且引号外叙述 ≥`ADJACENT_MIN_LEN`(8) 字 → blocking；纯台词/弹幕复沓豁免
- **长句复读**：可见 ≥12 字的句子全文件出现 ≥3 次 → blocking；`stripQuoted` 只豁免引号内台词，「叙述+引号内物件」混合行的引号外叙述仍计数（注释："引号外叙述的复读仍是退化，不能整行豁免"）
- **截断**（:249）：最后一个内容行未以句末/收尾标点结束 → blocking
- **占位/拒绝语**（:265）：hard 模式扫整行；soft 自指/拒绝语只扫 `maskQuotedSpans` 后的引号外文本（**遮罩等长以保留列号**，「对不起，我无法答应你」这类正常对话不误判）
- **工程词泄漏**（:290）：tier1 纯流水线术语 blocking，但命中间位于成对引号内且写手/编剧题材角色真讨论创作时降 advisory；tier2 章节结构/歧义词 advisory（report-only 交人/LLM 判）；注释存证动机："DeepSeek-v4 这类会在对话里冒「该到下一章了」。**漏词的模型自己发现不了，靠脚本兜**"
- 哲学：Report-only 永不改写正文；处置=带 finding 重新生成受影响单元

### 3.5 build_writer_prompt.py（37847 字节）——提示词确定性组装

`build(project, chapter, report)`（:378）逐槽组装，**每槽决策都往 report 留痕**：

- 固定首行：强制写手对「参考文件体系」逐行独立判定命中并读取，"命中即必读，未命中不预加载；交付摘要里报出读了哪几个"
- **细纲只给路径不注入全文**（"动笔前完整读到 EOF"）——防上下文稀释
- 续写状态卡：校验固定 7 栏结构，缺栏即报错（"先用 tracking_commit.py 修派生视图"）
- 文风槽：custom_style true/false **都留槽位标题**（"未跳过，留标题"）——false 时显式写明"文风召回归主会话"，杜绝静默跳过
- **上一章结尾注入正文但不给路径**（"全章不需要，故不给路径"）——防写手回头读整章；按整行回退取末 N 字
- 必读设定槽：`SLOT_MARK` 委托主会话填，指令原话"**直接写出那几句**，不要只给路径让写手去查（Grep 遇超长行会被截断，最关键那句往往正好被吞）"
- 标题行：`learn_heading_form` 从已有章学标题形态，"逐字照抄，勿按通用规则推导"
- 章名含路径分隔符即拒（路径安全）

## 4. 针对我方当前问题/困境的解决方案对照

| 我方困境 | Oh Story 方案 | 证据位置 | 可移植性 |
|----------|--------------|----------|----------|
| **爽点工程（R8 #1/WP-F）** | 爽点/目标情绪/章首钩子/本章禁止提前释放=细纲必填设计字段，正文从细纲消费；#383 实验证明目标情绪+主角目标是最小有效对 | `check-outline-contract.js` FIELDS/INTENT_FIELDS | **路线对照**：我方爽点读数是"从正文抽标记"，Oh Story 是"细纲设计→正文兑现"——前者可度量，后者可前置约束，两者可拼（细纲设计字段+正文兑现核验） |
| **B2 读者已知阅读卡（刚落地）** | 时间线双视图：作者真相（客观事实 vs 读者认知对照表）+ 读者已知（不泄露作者真相）；读者认知是事件级 `reader_knowledge` 字段 | `tracking_commit.py:617` render_timeline_views | **直接同构互证**——我方 reader_ledger 派生投影与其读者视图同一设计；可借鉴"认知截至章"列 |
| **确认闸交互形态（needs_decision）** | chapter check 五态出口码（ready/needs_decision/blocked/invalid/tool_unavailable）；新增物三级"先问作者"清单；accept-current-length 双底线+`--force` 作者拍板 | `storyctl.py` CHECK_EXIT_CODES / SKILL.md 新增物三级 | 高——"工具坏了≠正文要改"的退出码分离、压缩证明（body_sha256）都是确认闸可借的硬形态 |
| **AI 味/退化指纹（prose_audit）** | 退化指纹五族（逐行复读/长句复读/截断/占位拒绝语/工程词两层级）+ 台词豁免精细化（stripQuoted/maskQuotedSpans 保列号）+ 去味:跳过豁免仅 AI 句式不及退化 | `check-degeneration.js` 全文 | 高——指纹库逐条可补入我方 prose_audit；台词豁免比我方 n-gram 精细 |
| **状态管理** | 单文件权威+事务双模式（append/revision 纪律）+派生视图禁手改+掉落显式申报+崩溃可检测（revision 先行写）+体积预算 | `tracking_commit.py` merge_transaction/write_views/warn_sizes | 中——文件式无并发，但 revision 纪律与"掉落显式申报"思想可入我方账 |
| **committed 章修订谎报** | retired 只能 append："修订落在旧章会谎报退役发生的章节" | `merge_transaction` 注释 | 高——我方 revision 章的事件时间归属同一问题，这是现成答案 |
| **提示词工程确定性** | 组装外置为脚本+每槽留 report 行+槽位永不静默跳过+路径/正文注入策略分明（细纲给路径、章尾给正文） | `build_writer_prompt.py` build() | 高——我方提示词构建可对照做"槽位决策留痕" |
| **方法论资产（R8 语料）** | references/ 30+ 份（hooks/emotional-arc/deslop-gates/reader-contract 等） | `skills/story-long-write/references/` | 高——R8 #1 落地时对标其颗粒度；注意其拆文提示词渗尺=读数作废（我方禁区纪律在册） |

## 5. 与我方架构的异同（诚实对照）

| 维度 | Oh Story | 我方 plot_engine |
|------|----------|------------------|
| 运行时 | 寄生宿主 Agent，无自有运行时 | 自有管线+后端 |
| 确定性逻辑 | 全部外置脚本（Python/JS），宿主只编排 | 内核 Python 模块 |
| 状态 | 单 JSON 权威+派生 md 视图（禁手改） | SQLite 事件溯源+CAS |
| 门禁 | 脚本门禁（字数+质量）+作者拍板出口 | H1–H8 硬门禁+确认闸 CAS |
| 爽点 | 细纲设计字段（前置） | 正文派生读数（后置）——互补 |
| 修订纪律 | append/revision 双模式+谎报防护 | revision 归因阶梯 |

## 6. 一句话结论

Oh Story 的证明题是"**方法论资产 + 确定性脚本兜底 + 寄生分发**"：脚本兜住模型自己发现不了的退化（"漏词的模型自己发现不了，靠脚本兜"），references 构成护城河；其细纲爽点字段、时间线读者双视图、chapter check 五态出口码，分别对应我方爽点工程、B2 阅读卡、确认闸三件在途事的可对照实现。