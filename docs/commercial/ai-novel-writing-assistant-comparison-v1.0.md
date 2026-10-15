# AI-Novel-Writing-Assistant 对标评估 — 核实、对比与我方战略含义 v1.1

- 状态：分析稿（2026-10-15 核实；v1.1 按 tff 要求清洗表述）
- 输入：tff 提供的研究分析稿 + 三方注册表/评测站交叉核实
- 关联文档：`docs/commercial/r8-commercial-input-requirements-v1.0.md`、`docs/commercial/oh-story-architecture-and-commercial-analysis-v1.0.md`、`docs/commercial/refrence/`（本地代码核实系列）

---

## 1. 核实结果：研究稿对账

### 1.1 确认属实

- 定位：TypeScript Monorepo（pnpm workspace）全栈产品，非聊天助手而是结构化流水线（灵感→世界观→角色→卷纲→章节→质量修复）。
- 创作输入五段式：IDEA → CONTRACT → WORLD → CHARACTERS → PLAN。
- 章节生产闭环：授权正文范围 → 组装上下文 → 生成 → 检查 → 保存/局部修文 → 复验 → 状态同步。
- 状态回流（fact ledger）：从已生成章节抽取硬事实（角色名、交易金额、日期）注入下一章上下文——第三方评测（finds.dev）认为这是"真正有用"的抗一致性漂移机制。
- 写法引擎：从参考文本提取文风特征、编译为可复用写法资产——比"把文风描述粘进 system prompt"更有原则。
- 记忆增强参照 OpenViking / Recurrent-LLM / Generative Agents / CoLong / Mem0 等研究。
- 曾上 GitHub Trending（2026-04-29 首达 #9）；Star 增长轨迹：1.6K（2026-06）→ 约 3.0–3.1K（2026-10，repo.uno 快照 3,100 / LibHunt 2,970），研究稿"★3,050（2026-09）"处于合理区间。

### 1.2 研究稿遗漏或需修正

| 项 | 研究稿 | 核实结果 |
|----|--------|----------|
| **编排框架** | 未提 | 有 LangGraph，但仅用于 3 张辅助图（characterDesign / novelOutline / writingFormula）；**主生产链是自研 Director step DAG**（详见 refrence/ai-novel-writing-assistant.md） |
| **License 性质** | "服务式商用需单独授权" | **AGPL-3.0 + CLA 双授权**（finds.dev 称"open-core 陷阱"）：CLA 给维护者完全再授权权，贡献者仍受 AGPL 约束 |
| **PostgreSQL 可选** | "默认 SQLite，可选 PostgreSQL" | finds.dev 指出 Prisma 查询层与 SQLite 深度耦合，**迁移路径并不现成**，"可选"有水分 |
| **可靠性** | "功能趋于成熟" | 其 roadmap 自承 **P0 = "减少假停止与异常 token 消耗"**——happy path 频繁失败，整书端到端可靠性未经证明 |
| **社区增长** | "持续增长" | 注册表数据冲突：OpenAgentSkill 2026-09 快照显示 1.6K★/距上次 push 4 个月；LibHunt 活跃度 9.9。trending 峰值在 2026-04，此后靠存量传播。宜保守解读为"峰值后平稳" |

### 1.3 研究稿中未独立核实的数据（如实标注）

市场规模（AI 小说工具 2025 年 1.79 亿美元 → 2032 年 3.61 亿，CAGR 10.7%；创意写作助手 22 亿 → 26.7 亿，CAGR 21.4%）、竞品定价（Sudowrite $10/22/44、NovelAI $4.99 周、Novel Crafter、蛙蛙写作留存 45%）均来自研究稿转引，本报告未独立核实，决策引用前需复核原始出处。

---

## 2. 架构深读（补研究稿未展开处）

### 2.1 编排层：自研 Director DAG 为主，LangGraph 为辅

开书主流程由 `modules/director/steps/planDefinition.ts` 声明式 DAG 驱动（10 步，gateable 节点 = 人工审批闸），LangGraph 只承担角色设计/大纲/写法三张辅助图。checkpoint 恢复、审批留痕、产物依赖追溯都在自研 Director 运行时内（DirectorRun/StepRun/Artifact/Checkpoint/Event 全套模型表）。

**与我方对照**：

| 能力 | 对方（自研 Director） | 我方（自研） |
|------|------------------------|--------------|
| 断点恢复 | DirectorRuntimeCheckpoint | replay（事件溯源，确定性重建） |
| 人工审批 | gateable 节点 + 自动批准留痕 | 缺（R8 #2 开书确认闸待建） |
| 并发写入 | SQLite 写串行化风险（finds.dev 点名） | CAS + WAL 纪律（已有禁区管理） |
| 失败归因 | 质量债归因码 A/D/E（本章级） | revision Root Cause 八层归因阶梯 |
| 质量度量 | QualityReport 入库 | 尺号体系（EXTRACTION_RULER，一因一批） |

结论：对方上线速度快、功能面广；我方在**确定性与可度量纵深**上更厚。

### 2.2 资产与规则层（其真正差异化）

五类资产（拆书结果 / 世界角色样本库 / 写法资产 / 去 AI 规则 / 知识库）都是**可导入、可绑定、可复用**的一等公民。与 Oh Story 的拆文库同构，但更进一步：拆书结果可提取文风**编译**进写法引擎，形成"资产 → 规则 → 生效约束"的闭环。

**对我方 R8 的直接映射**：R8 #4（拆文库）若做，应对标这一层——不是存报告，而是产出可编译进生成约束的资产。

### 2.3 去 AI 化（其体系化但未见量化）

全局基线规则 + 写法专属规则 + 专项检测进章节检查——体系上比我方 lint 完整，但公开资料**未见量化预算/分级/防过矫正**。R8 #3 的量化去味仍是差异化空位。

---

## 3. 三方对比矩阵（Oh Story / AI-NWA / 我方）

| 维度 | Oh Story（★7.5K） | AI-NWA（★3.1K） | 我方 novel-audiobook |
|------|-------------------|------------------|----------------------|
| 形态 | Skill 包（寄生宿主 CLI） | 全栈桌面/Web 产品 | 内核引擎 + 流水线 |
| 编排 | 宿主 Agent + 8 Hook | 自研 Director DAG + LangGraph 辅图 | 自研状态机 + CAS + replay |
| 状态权威 | 文件系统 + commit 制 | SQLite + fact ledger + StateChangeProposal | state.db + 事件溯源 + 尺号 |
| 语义记忆 | 无（纯文件） | **RAG（可选 Qdrant）+ 六大记忆研究** | 无（R8 范围外，待议） |
| 市场输入 | **扫榜 + 拆文（完整）** | marketRadar 扫榜 + bookAnalysis 拆书 | 缺（R8 #4/#5 待建） |
| 去 AI 化 | lint + 三遍法 + 预算档 | 基线 + 专属规则体系 | lint（禁区冻结中）→ R8 #3 |
| 人工协同 | 开书默认停在正文前 | gateable DAG 节点 | 缺（R8 #2 待建） |
| License | MIT | AGPL-3.0 + CLA | 自有 |
| 可靠性证据 | 大规模用户使用 | **P0 自认假停止未解** | 526 tests + 尺号回归纪律 |
| 商业终点 | 交付文件为止 | 卖工具（桌面版/授权） | **双通道：平台连载付费 + 有声书付费** |

（四方含 InkOS / SillyTavern 的完整矩阵见 `refrence/comparison.md`）

---

## 4. 对我方的价值：可借鉴清单（设计层）

1. **fact ledger**：硬事实（人名/金额/日期）结构化抽取 + 注入下一章上下文——与我方台账体系互补，可做 R8 后续项。
2. **写法资产编译**：拆书结果 → 可生效的表达约束（不是存文档）。R8 #4 的验收标准应对齐这一层。
3. **审批节点产品化**：gateable 节点证明"人工审批作为流水线一等节点"是正确抽象——R8 #2 开书确认闸应同样做成门禁节点而非流程外操作。
4. **六大记忆研究清单**（OpenViking / Recurrent-LLM / Generative Agents / CoLong / Mem0）：语义记忆选型时的现成调研起点。
5. **双模式共用内核**：简易/专业共用一套流程只裁剪编排——我方未来若有产品层，同样适用。
6. **质量债归因码**：A（义务未传达）/D（计划不可达）/E（签名漂移）的根因分类经验，可与我方 revision 归因阶梯互换。

---

## 5. 商用评估与战略含义

### 5.1 对方商业模式：卖工具

桌面工具 + 商业授权，客户是作者与机构。研究稿四条路径（授权 SaaS / 私有化部署 / 增值生态 / 内容分成）里，"私有化部署"在其授权体系外，其余路径需与维护者建立授权关系。**工具市场数据**（研究稿转引，未独立核实）：AI 小说工具全球 2025 年约 1.79 亿美元。

### 5.2 我方当前模式：自产内容

自产内容 → 网文连载付费 + 有声书付费，面向**内容市场**。它与我方读者市场不构成直接竞争。

### 5.3 开放决策：是否进入工具市场

**本文档不下结论，由 tff 决策**。决策相关事实：

- 工具赛道拥挤度：同品类开源竞品十余个（EthanYoQ 桌面软件、dsh-novel-writer、novel-smith 等），多在 500★ 以下
- 头部数据：Oh Story（Skill 包形态）★7.5K 增速快于 AI-NWA（全栈产品形态）★3.1K
- 工具方共同软肋：可靠性（AI-NWA 自认 P0）、量化质量闭环缺失
- 我方若走工具路线的既有优势：526 tests + 尺号体系 + revision 归因（质量基础设施是竞品空白）
- 我方双通道内容终点与工具路线不互斥，可先后、可并行，视资源裁决

### 5.4 R8 优先级再确认

对方有拆书与扫榜、有审批节点、有去 AI 规则体系——但**爽点量化、去味量化预算、付费节奏对齐**两方竞品皆无，仍是空位。R8 排序（爽点工程 > 确认闸 > 量化去味 > 拆文库 > 扫榜 > 导入）维持不变。

---

## 6. 结论

AI-Novel-Writing-Assistant 是**全栈产品路线**的样本：架构完整（Director DAG 编排 + 五段输入 + 资产规则层 + fact ledger 回流），同时暴露了该路线的两个典型挑战——可靠性 P0 未解、授权体系抬高商用门槛。

与 Oh Story 并看：Oh Story 证明方法论工程化的需求（★7.5K），AI-NWA 展示全栈工具的形态与代价（★3.1K）。我方当前定位——确定性内核自产内容、双通道变现、R8 补市场输入——与两条路线均有借鉴接口；**是否及何时切入工具市场，留待 tff 裁决**。

---

## 附：证据来源

- finds.dev 评测（fact ledger、SQLite/Prisma 风险、P0 假停止、AGPL+CLA 分析）
- OpenAgentSkill 注册表（2026-09 快照：1.6K★/333 forks/距上次 push 4 个月）
- Trendshift（2026-04-29 Trending #9）；repo.uno（3,100★/586 forks）；LibHunt（2,970★，活跃度 9.9）
- 本地代码核实（`refrence_projects/AI-Novel-Writing-Assistant`）：Director DAG、LangGraph 辅图范围、marketRadar/drama/comic 模块
- tff 研究分析稿（市场数据与竞品定价，§1.3 已标注未独立核实项）