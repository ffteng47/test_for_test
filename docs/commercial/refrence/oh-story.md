# Oh Story — 业务流 / 代码流补篇（本地代码核实版）

- 代码基线：`refrence_projects/oh-story-claudecode`（816 文件）
- 架构与商业分析见 `docs/commercial/oh-story-architecture-and-commercial-analysis-v1.0.md`；本文档只补**代码流实现细节**
- License：MIT

## 1. 写作脚本草（`skills/story-long-write/scripts/`，13 个）

| 脚本 | 职责 | 可借鉴点 |
|------|------|----------|
| `storyctl.py`（489 行） | 状态权威工具：chapter commit、派生视图渲染 | 状态唯一入口，手改派生被拒 |
| `tracking_commit.py` | 追踪提交（_tracking-state.json） | commit 事务化 |
| `build_writer_prompt.py` | **写作提示词由脚本组装** | 提示词构建外置为确定性代码，不靠宿主即兴 |
| `build_architect_brief.py` | 架构简报组装 | 同上 |
| `check-outline-contract.js` | **细纲契约检查** | 无合规细纲不得写正文（门禁前置） |
| `check-outline-copy.js` | 细纲照搬检测（细纲写成散文句→正文誊抄） | 配「复沓锚句」白名单字段 |
| `check-degeneration.js`（316 行） | 退化指纹检测（详见 §2） | 与我方 prose_audit 互证 |
| `check-ai-patterns.js` | AI 句式模板命中 | deslop lint 核心 |
| `style-whitelist.js` | 文风白名单 | 正向约束（不只禁用） |
| `normalize-punctuation.js` | 标点规范化 | 确定性后处理 |
| `wordcount_core.py` | 字数统计核心 | 子代理可执行判据 |
| `outline_view.py` | 细纲视图 | 人机协同界面 |
| `author_memory_commit.py` | 作者记忆提交 | 记忆三态的写入闸 |

## 2. check-degeneration.js 检测语义（值得逐条对照我方 prose_audit）

- **复读/打转**：长句（可见字符 ≥12）出现 ≥3 次判打转；紧邻整行重复（≥8 字）判即时循环；**短句/弹幕墙/对话刷屏豁免**（网文排比、复读、弹幕是合法修辞）
- **截断**：文件结尾无终止/闭合标点
- **占位/拒绝/元信息泄漏**：「作为AI」（须自指位置、型号后缀可选吃掉、对话行豁免）、「我无法继续生成」、「（此处省略…）」、乱码替换符、英文 AI 腔（Sure/Certainly/As an AI）
- **工程词泄漏**：细纲/情节点/本章/下一章/任务描述 渗入正文，**两层级**——tier1 正文永不合规=blocking；tier2 对话行内工程词=advisory 交 LLM 判
- **哲学**：Report-only，永不改写正文；安全响应 = 带着 finding 作为约束**重新生成受影响单元**（章/摘要），重试封顶，证据浮出水面给用户

## 3. 方法论资产库（`skills/story-long-write/references/`，30+ 份）

commercial-core-methods、deslop-gates、banned-words、emotion-on-page、emotional-arc-design、emotional-methods、long-chapter-hooks、long-chapter-quality、long-format、long-genre-catalog、long-genre-mechanics、long-reversal、genre-prose-cards(+目录)、genre-readers、character-design-methods、character-relations、dialogue-mastery、female-audience-writing、cross-book-recall、benchmark-recall、author-memory(+maintenance)、anti-ai-writing、artifact-protocols、agent-calls……

**这是其真正护城河**：skill 只是壳，方法论语料才是资产。我方 R8 #1（爽点工程）落地时可对标其 long-chapter-hooks / emotional-arc-design 的颗粒度。

## 4. 质量保障工程（`scripts/`，25+ 检查脚本）

check-claude/codex/opencode/zcode/reasonix/antigravity-adapter（六端适配器测试）、check-hook-regex-sync（hook 正则跨端同步）、check-hook-locale-safety、check-current-skill-contracts(+json)、check-doc-budget（文档体积预算！）、check-reference-gates/similarity、check-scan-runtime-policy、check-plugin-packaging、check-python-invocation、check-shared-files、playwright（E2E）。

**启示**：多端一致性和"文档即契约"全部用 CI 脚本锁死——连参考文档的体积都有 budget 检查。我方尺号纪律是同种思维，可补"文档预算"一类轻量检查。

## 5. 与我方 prose_audit 的差异（诚实对照）

| 维度 | Oh Story | 我方 plot_engine |
|------|----------|------------------|
| 复读检测 | 整句/整行重复 + 对话豁免 | 跨章 12 字 n-gram 自相似 |
| 分层 | blocking/advisory 两层 + tier 工程词 | 审计报告（分层在评审侧） |
| 处置 | 只报告，重生成带约束 | revision 归因阶梯 + 回滚 |
| 互补点 | 截断/占位/工程词指纹值得引入 | 跨章重复、CAS 状态是对方没有的 |