# WP-F oh-story 吸收落档（digest）

- 版本：v0.1 ｜ 日期：2026-10-17
- 任务出处：`docs/project-roadmap.md` v0.7→v0.8 裁定④（roadmap:26「oh-story（MIT）吸收通道 = WP-F 入矩阵」）；交付物定义 = roadmap:166（`docs/` 方法论+需求拆解；lint 落地需另批申报；AGPL 件禁代码引入）；承接映射 = roadmap:113（拆文库/扫榜→WP-F）；backlog 挂钩 = roadmap:196（在场静态事实=T1 新事件型，赶 epoch_2/WP-F 双层追踪）。
- 吸收对象：`refrence_projects/oh-story-claudecode/`（GitHub `zenstory-ai/oh-story-claudecode`，本地克隆 HEAD `6d72f70`）。**只读**：该目录为用户未跟踪文件，本次吸收未修改、未 git add 其中任何文件。
- 本文档中 oh-story 路径均相对 `refrence_projects/oh-story-claudecode/`；本项目路径均相对仓库根。
- 既有分析件（本文不重复，只增量）：`docs/commercial/oh-story-architecture-and-commercial-analysis-v1.0.md`（架构+商业）、`docs/commercial/refrence/oh-story.md`（代码流细节，51 行速览）。本文是**方法论吸收+WP-A 映射差+候选落地**三合一，为 WP-F 的正交付件。

---

## 1. 项目画像

**它是什么。** 网文写作 skill 套件：13 个 skill（`skills/<name>/SKILL.md` + `references/` + 自带 `scripts/`），覆盖「扫榜选材 → 拆解爆款 → 搭大纲写正文 → 去AI味 → 封面图」全流程，装进 7 款编程 Agent（Claude Code/Codex/Antigravity/OpenCode/ZCode/OpenClaw/Reasonix）运行（README.md:5-9、37、42、277-301）。产品形态是 **Markdown 写的写作方法与工作流契约 + 确定性 Node/Python 检查脚本**，不是运行时程序（AGENTS.md:8）；写作模型即宿主模型，零 GPU（README.md:38、344-346）。这与 WP-F 前置「零 GPU」（roadmap:166）同型。

**许可证（逐文件核实）。** 纯 MIT，roadmap 裁定④成立：
- 根 `LICENSE:1-3`＝MIT License, Copyright (c) 2025-2026 oh-story-claudecode，为全仓库唯一 LICENSE 文件（`find . -name "LICENSE*"` 排除 `.git/` 仅命中根一处；skills/scripts/demo 无子许可）。
- 工作树全文检索 `AGPL|GPL|GNU General Public`（`grep -rn --exclude-dir=.git`）**零命中**；`git log -S AGPL --all` 与 `git grep AGPL HEAD` 亦零命中——AGPL 字样仅在 `.git/objects/pack/pack-04ffc036….pack` 二进制里有残留串，不属于任何被追踪文件、任何历史版本树，不可执行、不构成交付面。
- 各 skill frontmatter、README.md:25 徽章、docs/*.md 均自述 MIT（例：docs/ai-long-novel-character-consistency.md:3「开源 MIT」、docs/keep-ai-novel-consistent-over-100-chapters.md:3「MIT, 6.8k stars」）。
- 第三方引用件（README.md:415-416 致谢）：FanqieRankTracker（字体反爬解码思路）、Zhuque AIGC Detector CLI（外部复测）——仅思路引用、未 vendor 代码，其自身许可证未核；见 §3.4 排除项。

**活跃度。** 本地克隆 main 线 343 commits，首末提交 2026-04-23 → 2026-10-15（HEAD 提交信息「fix: 复核精修契约并同步中英文 README (#485)」，即吸收当日仍活跃）；远端 refs 696 个（50+ 活跃分支、release/v0.7.9–v0.8.5 标签线）；包内版本 `skills/story/VERSION` = 0.8.5，CHANGELOG.md 持续更新。联网核实快照见 `docs/commercial/oh-story-architecture-and-commercial-analysis-v1.0.md:5`（★7.5k，2026-10-15）。工程纪律密度极高（CI 守卫 25+ 脚本，scripts/README.md:15-30；决策笔记 74 篇，`.agents/notes/`），属于**仍在快速演进、机制已被真实使用验证**（README.md:73-145 全链路实录 demo）的成熟参考件，非玩具仓库。

**与本项目有声书赛道的关系。** 它是**文本生产上游**（面向起点/番茄/晋江/七猫/知乎盐言的网文创作，README.md:43），本项目是**有声书下游交付**（听服生产链）。重叠面恰好是 R8 入队时点名吸收的四块之二：拆榜/爆款方法论、双层追踪记录（roadmap:113）；其去AI味 lint 面与我方 WP-C 同面、列为禁区（roadmap:166）。它的「文件系统当记忆 + 确定性门禁」骨架（README.md:40-41）与我方 plot_engine「EventLog/State/Validator」哲学同源，是方法论可移植性最高的参照项目（四参照项目中唯一 MIT 可吸收件，roadmap:111）。

---

## 2. 可吸收方法论清单

### 2.1 拆榜 / 爆款方法论

**对应实现与机制：**

| 证据（文件:行号） | 机制一句话 |
|---|---|
| skills/story-long-scan/SKILL.md:11 | 核心信念：单本排名只提供线索，近期多榜单、多作品的**重复模式**才支持趋势判断 |
| skills/story-long-scan/SKILL.md:51-66 | 数据源三档路由（脚本采集/用户提供/内置知识），内置知识强制标注「未完成实时校验前只作候选假设」（SKILL.md:71） |
| skills/story-long-scan/SKILL.md:63-66；references/topic-decision.md:41-43 | 稀疏度硬闸：同方向 <15 本（小平台 <10）标「少」，可行性**最高只给"中"**，禁止稀疏样本坐实趋势 |
| skills/story-long-scan/references/topic-decision.md:18-27 | 选题四步缺一不可：能爆的原因（先当假设、标 `待拆文验证`）→ 市场验证（含反例核源）→ 差异化定位（无差异化=同质化）→ 可行性+失败风险+低成本验证动作（「先写黄金三章测追读，不行就换」） |
| docs/scan-charts-and-deconstruct-bestsellers.md:24-47；skills/story-long-analyze/SKILL.md:74-86 | 拆文七阶段单管道：机械章节索引（逐章 hash）→ 黄金三章 → 连续章块提取 → 聚合（节奏/情绪模块）→ 角色设定 → 报告 → 文风；Stage 1 后停靠问作者 |
| skills/story-long-analyze/references/stage3-plot-rhythm.md:9、165 | 情绪模块 EM 卡五门禁字段齐全才算可复现模块：读者想看什么/情绪链/戏剧单元/可替换项/不可照搬；缺任一项不得登记灵感库 |
| skills/story-long-analyze/references/stage3-plot-rhythm.md:168、264、276-277 | 权威/投影分离：`剧情/节奏.md`＋`剧情/情绪模块.md` 是权威，`拆文报告.md`/`故事线.md` 只能摘要引用、不得成为并列权威 |
| docs/scan-charts-and-deconstruct-bestsellers.md:53-57 | 写作消费规则：「用模块组装，不要重新发明」——对标书角色看成功能位（对手/盟友/催化剂）再映射自有角色；复制结构和节奏，不复制句子 |
| docs/scan-charts-and-deconstruct-bestsellers.md:59-61 | 与手工拆书的差量：①爽点/伏笔按章号建索引 ②情绪套路抽成模块卡 ③文风量化成句长/标点分布并附原文锚点——三样都是「可被程序读取的资产」 |

**与 WP-A 契约/Validator/State 的映射差：**
- **能对应**：EM 卡「读者想看什么/情绪链」≈ 爽点工程→WP-A 面（roadmap:113），其读者需求字段与 `reader_ledger`（`plot_engine/models/ledger.py:41-52`，unaware/hinted/knows/deceived）同语义；「铺垫→释放→余波」节奏周期（docs/scan-charts-and-deconstruct-bestsellers.md:46；stage3-plot-rhythm.md:343-345）与伏笔账本 planted→hinted→due→paid 生命周期（ledger.py ForeshadowingEntry 迁移序）结构同型；「按章号建索引+逐章 hash」（scan 文档:30、40）与我方 eventlog/commit 的逐章哈希校验（`plot_engine/commit.py:5`）同一确定性思路。
- **缺的承接位**：本项目**没有**扫榜数据目录、选题决策落盘位、拆文库/{书名}/ 资产面与灵感库（EM 卡跨书聚合）概念——roadmap:113 只写了「拆文库/扫榜→WP-F」，矩阵内无现成承接文件；「跨样本重复模式 vs 个例」的信号判定纪律在我方测量体系（逐章仪器读数）里没有对应物，若落地需新资产层而非 State 扩展。注意：它的拆文逐章提取/披露候选管道（stage2-extraction.md、stage3-plot-rhythm.md:157）是**离线拆解面**，与我方抽取尺面是两套体系——吸收止于方法论，实现不得回流 `llm_extract.py`（见 §3.1）。

### 2.2 双层追踪记录（作者真相 vs 读者已知）

**对应实现与机制：**

| 证据（文件:行号） | 机制一句话 |
|---|---|
| docs/ai-long-novel-character-consistency.md:19-31 | 四层文件骨架：`设定/`、`大纲/`、`正文/`、`追踪/`；追踪内含 `_tracking-state.json`＋派生视图（上下文卡/逐章记录/角色状态/伏笔/时间线） |
| docs/ai-long-novel-character-consistency.md:35-37 | 三设计律：①一个权威其余派生（所有写走 `tracking_commit.py`，手改派生文件被 check 拒绝）②作者真相/读者已知分开记 ③每章写入有字节上限的增量（逐章记录目标 ≤1536、硬上限 3072 字节，状态不随章数线性膨胀） |
| docs/ai-long-novel-character-consistency.md:36；README.md:98 | 双时间线的用途判据：写第 40 章时模型看得见「凶手是谁」（作者真相）但看得见「主角还不知道」，于是不会让角色提前开口；「设定≠角色已知」分开读（:44「徐棠有个哥哥」是设定，「徐棠不知道信是哥哥寄的」是状态） |
| skills/story-long-write/references/tracking-transaction.md:5-13 | 权威层/派生层表格：`上下文.md`、`角色状态/`、`伏笔.md`、`时间线/作者真相.md`、`时间线/读者已知.md` 全部由 state 确定性重生成、逐字比对，「Markdown 只给人读，工具不反向解析 Markdown」（:13）；未来揭示计划留在大纲、不写进时间线既成事实（:13） |
| skills/story-long-write/scripts/tracking_commit.py:1-7 | 提交协议：语言模型只交紧凑语义 JSON，工具内存合并→渲染全部派生视图→`_tracking-state.json` 最后原子写＝唯一提交点；项目锁串行并发写 |
| skills/story-long-write/scripts/tracking_commit.py:617-645 | `render_timeline_views()`：同一 events 表分别渲染「# 作者真相时间线」（:619，含客观事实/读者当前认知/揭示状态/实际揭示章七列）与「# 读者已知时间线」（:627，只含读者当前认知/认知截至章三列） |
| demo/长篇/让你管账号，你高燃混剪炸全网/追踪/_tracking-state.json（timeline 事件 E001–E015；:155、:162） | 事件字段 = objective_fact/reader_knowledge/reveal_status/reveal_chapter/first_recorded_chapter/story_time；**真相候选**语义：E015「作者真相为候选，作者可在第22章细纲前改；揭示前不当读者已知」（:155）、钟嘉嘉军方背景「正文揭示前不能当成读者已知」（:162） |
| demo/…/追踪/时间线/作者真相.md:5-7、读者已知.md:5-7 | 两张派生阅读卡的实表形态（7 列对照表 vs 3 列投影） |
| docs/ai-long-novel-character-consistency.md:51-53 | 旧稿反向初始化：`/story-import` 把已发布正文反解析成追踪结构初版，**推断设定单列"待确认"不写成事实**（接我方 R6/WP-D 旧稿导入相邻面，roadmap:113） |

**与 WP-A 契约/Validator/State 的映射差：**
- **能对应**（这条是三块中映射最强的，我方地基已有）：双层事实在契约层已存在——`Fact.narrative_truth/objective_truth`（`plot_engine/models/fact.py:10、21-22`，「双层真相事实 02 §3」）+ `reveal_stage`（fact.py:24 hidden/hinted/partial/confirmed）+ `ReaderKnowledgeEntry`（ledger.py:41-52）+ knowledge/belief 三账（`plot_engine/models/state.py:54-59`）；「gate 未到期不产读者信号」已由 D9 把守（`plot_engine/derive.py:55-58、225-226`），与「不让角色提前知道」同律；提交乐观锁同型——`expected_version → CONFLICT/DUPLICATE`（`plot_engine/commit.py:37、91-96`）vs 他们的 `expected_state_revision` 拒 stale 事务（tracking-transaction.md「.tracking-commit.lock 串行」段）；「派生文件手改即拒」我方以 EventLog replay + state_hash 重算（commit.py:5、`plot_engine/models/state.py:71-75`）达成更强形式（可从事件流无损重建，他们只能从 state 重渲染当前视图）。roadmap:196 已点名「(b) 在场静态事实=T1 新事件型，赶 epoch_2/WP-F 双层追踪」——即 WP-A 冻结范围外的正牌承接位就是 epoch_2。
- **缺的承接位**：①**读者视角投影卡**：他们把 reader_known 渲染成作者可直读的「认知截至章」表（读者已知.md:5），我方 `reader_ledger` 是程序态、无「读者当前认知」的派生阅读面/落盘位；②**揭示前可改的真相候选**：reveal_status=未揭示 + 「作者可在第22章细纲前改」（demo _tracking-state.json:155）——我方 Fact 只有三值 truth + reveal_stage，无「候选事实→定稿」动作槽（毗邻 Revision 动作面，epoch_2 议题）；③**在场静态事实**：T1 新事件型在 epoch_1 型别表（`plot_engine/models/event.py:10、19`）无对应行（roadmap:196 实证三连穿帮机检全漏的缺口）；④**写章最小状态切片的字节预算规格**：固定 7 栏 ≤12KB 上下文卡 + 逐章增量 ≤3072 字节（docs/ai-long-novel-character-consistency.md:26-27、37），我方 writer prompt 组装无对应「本章所需最小状态」卡生成器。

### 2.3 门禁脚本参考

**对应实现与机制：**

| 证据（文件:行号） | 机制一句话 |
|---|---|
| skills/story-setup/references/templates/hooks/guard-outline-before-prose.sh:1-15 | 写前门（PreToolUse）：首建正文缺对应细纲、或长篇追踪检查点不成立（state 缺失/schema 不符/上一章事务未提交）即拦截；设计原则「宁可漏拦不可误伤——任何不确定都 exit 0」（:14） |
| skills/story-setup/references/templates/hooks/check-prose-after-write.sh:1-15 | 写后兜底网（PostToolUse）：正文落盘后只跑「硬信号」轻量确定性网（截断/拒绝语/工程词/整行复读/毒句式），advisory 类留给 workflow 收尾全量跑——**前门+兜底两层分工**（:12-14 明确声明绕过边界） |
| skills/story-long-write/scripts/storyctl.py:236、311-318、320 | 章级闭环状态机：`ready/needs_decision/blocked/invalid/tool_unavailable` 五态分级 exit code（:236），check 输出 `state_revision`、`tracking_committed`、`available_actions`（:317-320）——把「带外但质量合格」的裁决**交还作者**而不是自动补写/压缩 |
| skills/story-long-write/references/tracking-transaction.md（init/draft/check/commit 命令段） | 生命周期闭环：`draft` 预填本章事务（修订号+在场核心角色快照+字段字节上限），`chapter commit` 提交当下重读文件、重计数、重跑 blocking quality 后原子提交；`check` 逐字比对全部派生视图 |
| skills/story-long-write/scripts/check-outline-contract.js:2-14 | 细纲契约检查器：**只判结构不判值好**——字段必须在场，值可写 `[待补充]`（契约粒度由 artifact-protocols.md 自定），exit 0/1/2 三态 |
| skills/story-long-write/scripts/tracking_commit.py:309-341 | 退役纪律：`find_retired_tracking_paths`/`archive_retired_tracking_paths`——被废弃的追踪结构整档归档，「状态不会静默消失」（README.md:139 同述） |
| scripts/README.md:15-30；AGENTS.md:13-20 | 仓库级质量工程：25+ 守卫（frontmatter/锚点/跨 skill 引用禁、工作流编号契约 `skill-numbering.py`、热路径每次调用 35K 加载硬顶 `path_ceiling`、毒句式正则 js↔py 逐项全等 `check-hook-regex-sync.sh`、GBK 区域字节安全、三平台 CI cross-platform.yml） |
| .agents/notes/rejected/feature/2026-09-25-ai-flavor-prompt-interventions.md:9-30 | 预注册可证伪实验协议：三组降 AI 味干预（约束块/检测器闭环改稿/换强写手）四臂对照，主指标门槛在数据产生前冻结（「比对照少 ≥1.0 项且三本至少两本同向」），全部未过门槛 → **判负不合入**，且「Alternatives considered」先写被否方案最强理由 |

**与 WP-A 契约/Validator/State 的映射差：**
- **能对应**：`Validator` 本身就是「Commit 前的确定性闸门，Stage 1 沙盒：整批 Proposal 纯 Reducer 施加到临时拷贝、绝不落盘」（`plot_engine/validator.py:1-6`）——与 check-outline-contract 的「只判结构不判值」同哲学；H 规则库+分级（hard/soft/observation，validator.py:550-577 H9 族）≈ 他们的 blocking/advisory 二级；D11 单源漂移拦截（roadmap v0.13 批 D）≈ 他们的 `check-hook-regex-sync` 双端全等思想在我方键名单源（`due_by_chapter`↔`gate.must_reveal_by_chapter`）上的对应物；「状态修订乐观锁+提交当下重读重验」（storyctl.py:317 + tracking-transaction.md commit 段）≈ 我方 `expected_version`/CONFLICT（commit.py:37、91）。
- **缺的承接位**：①**「写前」门**：我方闸口在 Commit 前，无 LLM writer **动笔前**的细纲/前置物完备性机检（`plot_engine/sceneplan.py` 有场景规划但无机检契约面）——他们 guard-outline-before-prose + check-outline-contract 是此位的完整参考；②**needs_decision/available_actions 交还作者的形态**：我方 CommitOutcome 是 OK/CONFLICT/DUPLICATE 机器态，无「带外但 pass，可 accept-current-length」的作者裁决出口——此位天然毗邻确认闸（R3+R5 审听出口 `review.py`/`viewer.py` 面，roadmap:113）；③**字节/字数带预算语义**（±12%/±15% 双带、author_range 覆盖，tracking-transaction.md `chapter check` 段）：有声书对应物是字数→时长带，我方无此规格；④**加载预算守卫**（35K/次调用硬顶+stacking 登记，AGENTS.md:13）：我方 `prompts/` 面无等量文本纪律与加载量机检；⑤**退役整档**纪律（tracking_commit.py:309-341）：我方 revision/abandon 动作有账（roadmap v0.12 裁定 5A），但无「被废结构物理归档」面。

---

## 3. 不可吸收 / 禁区（逐项排除及理由）

### 3.1 抽取尺面（EXTRACTION_RULER / PAYLOAD_SCHEMA）——绝对禁区
- 我方尺面现状：`EXTRACTION_RULER` 当前 **v3.8-foreshadow-payload**（`plot_engine/llm_extract.py:49`；尺面纪律史注 :40-53），PAYLOAD_SCHEMA/_SCHEMA_HINT 为 v3.8 批次 E 冻结面（roadmap:21「尺面纪律：v3.8 起读数与 v3.6 分表，禁并列」）。**纪律：触碰尺面 ⇒ 读数作废、必须重基线**（llm_extract.py:44、52 两次明文）。
- oh-story 侧对应物：拆文逐章提取提示词与产出规格（skills/story-long-analyze/references/stage2-extraction.md、stage3-plot-rhythm.md:157「批次关键事件与披露候选」）。**排除理由**：那是离线拆解通道，与我的仪器化抽取是两套体系；任何其提示词文本/字段措辞渗入 `llm_extract.py` 的 `_SCHEMA_HINT`/判据行都构成触尺（v3.8 读数报废，等同重演 #70 型别批撤销事故，roadmap:27）。吸收止于「先索引后语义、逐章 hash、披露顺序敏感」等**流程方法**，实现层零文本交换。roadmap:166 备注列亦明示「lint 落地需另批申报」。

### 3.2 ai_flavor 面（WP-C 同面）——禁区
- 我方禁区位：`plot_engine/ai_flavor_lint.py`、`plot_engine/ai_flavor_baseline.py`（roadmap:166 点名禁区；WP-C 暂停中、归属裁定后激活，roadmap:113）。
- 对应排除件（oh-story 侧全部去味检测实现，一律**不引代码、不改写、不登记新写集**）：`skills/story-deslop/scripts/check-ai-patterns.js`（1586 行，AI 句式模板命中）、`check-degeneration.js`（349 行，退化指纹）、`style-whitelist.js`（文风白名单）、`normalize-punctuation.js`（标点规范化）、`skills/story-setup/references/templates/hooks/check-prose-after-write.sh` 的毒句式兜底段（:7-10）。
- **理由**：量化去味是 WP-C 的牌桌，WP-F 文档不得为其预做实现决定；既有事实是 `ai_flavor_lint.py` 早已是 check-ai-patterns.js 的 Python 完整移植（文件头 :4-12 保留 MIT 版权声明），该移植归属 WP-C 历史批次，与 WP-F 无涉。**例外允许**：§2.3 记录的 rejected 实验笔记（.agents/notes/rejected/…ai-flavor-prompt-interventions.md）作为**方法论结论**（提示词面降味干预未过预注册门槛）登记入档，供 WP-C 激活时参考——它是「他们的实验没做成」的证据，不是实现素材。

### 3.3 AGPL 代码件——核实结论：本仓库内**零 AGPL 件**，无需排除
- 逐文件核实（见 §1 许可证小节证据链）：工作树零 AGPL 命中、历史树零命中（`git log -S AGPL --all`、`git grep AGPL HEAD` 均空），唯一 LICENSE 为 MIT。`.git/objects/pack/pack-04ffc036….pack` 里的 AGPL 残留字节非任何被追踪文件内容，无代码可引入、无义务可传染。
- **真正需守的是隔壁三家**（roadmap:111）：AI-Novel-Writing-Assistant（AGPL+CLA 双许可）、SillyTavern、inkos（均 AGPL-3.0）——已裁「只读思路禁代码引入」，WP-F 的任何候选落地（含 §4 B 档）不得引用这三家代码/文本模板。

### 3.4 其余逐项排除
- **榜单采集脚本**（skills/story-long-scan/scripts/fanqie-rank-scraper.js、qidian-rank-scraper.js、jjwxc/qimao/ciweimao-rank-scraper.js、aggregate-rank.js；短篇 story-short-scan/scripts/*；browser-cdp CDP 登录态复用）：触碰平台服务条款与反爬对抗（番茄字体反爬，README.md:415 鸣谢 FanqieRankTracker），属运营/法务风险面——方法可写文档，**代码不引入**（引入还得过 roadmap:166 的另批申报+一道合规拍板）。
- **demo 受版权文本**（demo/拆文库/盘龙/原文/原文.txt、demo/短篇-曾将爱意私藏.txt、demo/长篇/让你管账号…/正文/*）：《盘龙》等为第三方签约网文实体文本，仅作拆解演示——**不得进我方仓库、语料、训练或交付链**；引用其表格形态（README.md:149-176）止于格式描述。
- **story-cover / GPT-Image-2 生图**（README.md:299、346）：唯一 GPU/付费 API 面，与 WP-F「零 GPU」前置冲突且非本赛道。
- **宿主适配层**（skills/story-setup/references/{claude,codex,antigravity,opencode,zcode,openclaw}/*、scripts/generate-codex-*、sync-opencode.py 等 7 端生成物）：绑定其 skill-packaging 产品形态，我方 Agent 运行形态是 backend/pipeline，无承接位——纯排除。
- **朱雀等外部 AI 检测器**（README.md:354、416）：他们自己仅自测参考不作验收，我方同样不引入（避免给 WP-C 未裁定的验收面塞新指标）。

---

## 4. 候选落地清单（全部「不实施」，仅拆解需求）

### A 档｜零 GPU、纯文档可先行（WP-F 本批交付面，roadmap:166 允许）
- A1 扫榜→选题四步 SOP 移植为有声书赛道选题方法文档（改「黄金三章测追读」为「样章测听服完读」）——证据：story-long-scan/SKILL.md:11、63-66；topic-decision.md:18-43。
- A2 EM 情绪模块卡五字段法→爽点工程需求草案（WP-A 相邻面，只写字段需求不动契约）——证据：stage3-plot-rhythm.md:9、165；scan-charts-and-deconstruct-bestsellers.md:44-47。
- A3 「权威/投影分离」拆解资产规格：拆文库/{书名}/ 双权威文件+摘要投影+逐章索引 hash——证据：stage3-plot-rhythm.md:168、276-277；scan-charts…:30-40、61。
- A4 双层追踪对照表落档：他们 时间线/{作者真相,读者已知} vs 我方 narrative/objective_truth+三账（本文 §2.2 为首版素材）——证据：docs/ai-long-novel-character-consistency.md:35-37；tracking_commit.py:617-645；plot_engine/models/{fact,ledger}.py。
- A5 门禁分层设计原则入档：「写前门+写后兜底网」两层、「宁可漏拦不可误伤」、「只判结构不判值好」——证据：guard-outline-before-prose.sh:14；check-prose-after-write.sh:5-14；check-outline-contract.js:9-13。
- A6 决策笔记纪律（proposed/implemented/rejected 三态+被否方案先写最强理由+决定翻转另开互链）候选入我方 docs 流程——证据：oh-story AGENTS.md:26-33。
- A7 预注册可证伪实验协议归档（四臂/门槛先冻结/判负不合入），供 WP-C 激活与后续模型面实验参照——证据：.agents/notes/rejected/feature/2026-09-25-ai-flavor-prompt-interventions.md:9-30。

### B 档｜需码批另申报（有承接位，但触碰 plot_engine/ 写集或新代码，roadmap:166 明示另批）
- B1 epoch_2「在场静态事实」T1 新事件型+抽取/Validator/State 三处扩展——roadmap:196 已挂名的正牌 WP-F 码批。
- B2 「读者已知」派生阅读卡渲染器（state.reader_ledger → 认知截至章投影，对标 tracking_commit.py:627-645 的读者侧视图）。
- B3 真相候选动作槽（reveal 前可改，对标 demo _tracking-state.json:155 E015 语义；毗邻 Revision 动作面）。
- B4 写前门：正文生成前置物完备性机检（对标 guard-outline-before-prose.sh + check-outline-contract.js，落点在 writer/sceneplan 通道）。
- B5 章闭环裁决状态机进确认闸面：`needs_decision/available_actions/accept-current-length`（对标 storyctl.py:236、311-320；接 roadmap:113 确认闸→review.py/viewer.py）。
- B6 写章最小状态切片（7 栏 ≤12KB 上下文卡的有声书等价物：writer prompt 的状态选取规格，对标 docs/ai-long-novel-character-consistency.md:26、39-44）——注意实现若改变抽取器输入构成即触尺，须与 llm_extract 隔离。
- B7 榜单采集/拆文离线管道（含 A3 的实现面）——除另批申报外还叠加 §3.4 反爬/版权风险。

### C 档｜需拍板（tff）
- C1 扫榜/拆文库是否升格为独立交付 WP（WP-F 现定义仅 docs/，roadmap:166），还是并入 R8 商业线。
- C2 热路径加载预算纪律（35K/调用硬顶+等量文本交换，AGENTS.md:13-20）是否移植到我方 `prompts/` 面。
- C3 js↔py 双端正则全等同步守卫（check-hook-regex-sync.sh，scripts/README.md:29）是否为 `ai_flavor_lint.py`↔参照件之间设立——触 WP-C 面，归属未裁定前禁动。
- C4 旧稿导入（story-import 的「反推结果待确认不写成事实」协议，docs/ai-long-novel-character-consistency.md:51-53）在 R6/WP-D bible 通道里的采纳深度。
- C5 字数双带（内部 ±12%/作者 ±15%，tracking-transaction.md `chapter check` 段）换写为「字数→时长带」后是否进入有声书交付验收。
- C6 逐章增量字节帽+退役归档（逐章记录 ≤3072B、`_旧追踪存档/`，tracking_commit.py:309-341、tracking-transaction.md 末段）是否约束我方 EventLog 快照衍生面。

---

---

## 拍板记录（2026-10-17，tff）

**裁定：按推荐选项确认——A 档 7 条 = 纯文档队列（后续批产出，本 digest 不预写实现）；
B 档 7 条 = 维持「码批另申报」不变；C 档 6 条 = 全部搁置保留，逐条登记保留可能性，不否决任何一条。**

- C1 扫榜/拆文库升格独立交付 WP：搁置保留，重提条件=R8 商业线明确要消费拆文资产时；
- C2 热路径加载预算（35K 硬顶）移植 `prompts/` 面：搁置保留，重提条件=prompt 体积出现实测成本问题；
- C3 js↔py 双端 regex 同步守卫：**维持禁区**（WP-C 归属未裁定前禁动，非搁置项）；
- C4 旧稿导入「待确认不写成事实」协议在 R6/WP-D 的采纳深度：搁置保留，重提条件=WP-D 通道启动批；
- C5 字数双带→时长带进交付验收：搁置保留，重提条件=有声侧时长数据有内部读数基线后；
- C6 逐章增量字节帽+退役归档约束 EventLog 快照面：搁置保留，重提条件=快照体积成为实测问题时。

本裁定零码改、零 GPU；A 档产出时按 roadmap 排期单批走。

**第二轮裁定（2026-10-17，tff「②先选一条验证，其余排期，适当时候提醒拍板」）**：
- **首条 = B2 读者已知派生阅读卡渲染器**（`state.reader_ledger` → 认知截至章投影，纯派生只读）。
  选择理由：与已验证落地的全-A 爽点读数批同构——零尺、零契约、零门禁、不回写任何上游模块，
  可直接在既有归档（wpe50ch state.db）上出验证读数；接口稳定性纪律下代价最小、且不碰 ③ 复现的冻结面。
- **其余 6 条排期 + 提醒触发条件**（触发一到，主会话在该批收口时向 tff 列待拍板清单）：
  - B5 章闭环裁决状态机进确认闸面：**第二顺位**，①③ 读数收口后即申报（其交互形态正是试点/复现读数暴露的人工裁决需求）；
  - B1 在场静态事实 T1 新事件型（epoch_2 契约面）：① 试点若证实「章内可判、跨章来源核查判不了」即提醒拍板（凭空进场族的账级闭环只有它能配齐）；
  - B6 写章最小状态切片：③ 五批读数若出现跨章漂移/上下文溢出实证即提醒（触 Writer 提示词面=须单独带尺戳批）；
  - B4 写前门物完备性机检：① 试点确认需要「进场无源/回卷」写前防护时提醒（新判定面，独立拍板）；
  - B3 真相候选动作槽：Revision 面 needs_arc_replan 存量增长（ch10 标本族扩大）时提醒；
  - B7 榜单/拆文离线管道：R8 商业线要求消费拆文资产时提醒（与 C1 联动，另叠加反爬/版权风险再申报）。

**B2 兑现（2026-10-17，码批收口）**：`plot_engine/metrics.py` 落 `render_reader_card`/`reader_card`
（reader_ledger→截至章纯派生投影，账外 fact 一律记「未感知」，卡面自标「不进闸」），
`plot_engine/readout.py` 接 `--reader-card [--ch=N]`（N>0 走 replay，replay 不可得直接抛不兜假账）。
验证读数：`sampling/ep1v39pv2c-r5` 终态卡=已知1/示意9/未感知2（12 fact 全投影）；
`sampling/wpe50ch --ch=25` replay 中点卡同分布（截至 ch23=最后 committed 章，投影随快照走）。
测试 `plot_engine/tests/test_reader_card.py` 抓到实 bug（facts 是 Dict 迭代出键非 Fact）。
链验 **588**（587+1）/backend **10** 全绿。零尺零契约零门禁、不回写上游，与裁定形态一致；
复现：`.venv/Scripts/python.exe -m plot_engine.readout sampling/ep1v39pv2c-r5 --reader-card`。
- A 档兑现指针：`docs/wp-f-a-docs-absorption.md` v0.1（commit 70eb7f6，roadmap v0.28）。

*本文档为 WP-F 唯一交付件；未修改 `refrence_projects/` 任何文件、未动 plot_engine/、未改 roadmap、未做任何 git 操作。*
