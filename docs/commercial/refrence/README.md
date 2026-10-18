# 参考项目分析索引（refrence_projects/ 四方对照）

- 建立：2026-10-15，基于本地克隆代码核实（非二手资料）
- 用途：我方 R8 商业化输入路线与内核演进的**零件图鉴 + 互证档案**

## 1. 文档清单

| 文档 | 项目 | 内容 |
|------|------|------|
| `comparison.md` | 四方 + 我方 | **对比总文档**（矩阵、机制参考、修正记录、R8 映射） |
| `ai-novel-writing-assistant.md` | ExplosiveCoderflome/AI-Novel-Writing-Assistant | 全栈产品；含三点前文修正（有扫榜/有衍生管线/LangGraph 仅辅助） |
| `inkos.md` | Narcooo/inkos | **与我方内核最同构**；delta+reducer+回放互证 |
| `oh-story.md` | zenstory-ai/oh-story-claudecode | 业务流/代码流补篇（主分析见上级目录） |
| `sillytavern.md` | SillyTavern/SillyTavern | 互动 RP 前端；提示词组装零件图鉴 |

相关主报告：`../r8-commercial-input-requirements-v1.0.md`、`../oh-story-architecture-and-commercial-analysis-v1.0.md`、`../ai-novel-writing-assistant-comparison-v1.0.md`

## 2. 四方对照矩阵

| 维度 | AI-NWA（★3.1K） | InkOS | Oh Story（★7.5K） | SillyTavern |
|------|-----------------|-------|-------------------|-------------|
| 形态 | 全栈桌面/Web 产品 | npm 内核+CLI+Studio | Skill 包（寄生宿主） | RP 前端（Server+SPA） |
| 编排 | 自研 Director DAG（gateable 节点） | pipeline runner 直排 | 宿主 Agent+Hook | 单轮组装，无链 |
| 状态 | Prisma/SQLite + StateChangeProposal | **delta 单调入账+校验+按章回放** | 文件+storyctl commit | 无状态会话 |
| 语义记忆 | RAG（Qdrant 可选） | retrieval/ | 无 | **8 源向量适配器** |
| 扫榜 | marketRadar 模块 | RadarAgent | story-*-scan | 无 |
| 拆书 | bookAnalysis+写法编译 | references/ | story-*-analyze | 无 |
| 去 AI | AntiAiRule 基线+专属 | — | lint 两层级+三遍法 | 无 |
| 质量 | 质量债归因码（A/D/E） | 字数治理遥测+审后对账 | 退化指纹+CI 脚本锁 | 无 |
| 商业模式 | 工具销售 | **赞助型开源**（Kimi/火山） | 流量入口（免费） | 纯社区 |
| 商业终点 | 卖工具 | 赞助+托管+数据 API | 交付文件 | — |

## 3. 机制参考总表（机制 → 来源 → 我方落点）

| 机制 | 最佳参照 | 我方落点 |
|------|----------|----------|
| 人工闸作为 DAG 节点属性 | AI-NWA `planDefinition.ts` gateable | R8 #2 开书确认闸 |
| 状态提案制（不直写） | AI-NWA StateChangeProposal / 我方 Event Proposal 已有 | 互证，保持 |
| delta 单调入账+入账即校验 | InkOS state-reducer | 互证，保持 |
| 按章回放 | InkOS loadRuntimeStateSnapshotAtChapter / 我方 replay 已有 | 互证，保持 |
| 质量根因分类码 | AI-NWA QualityDebtAttribution（A/D/E） | 对照 revision 归因阶梯，可互换分类经验 |
| 字数治理遥测 | InkOS length-governance | R8 #1 量化体系兄弟机制 |
| 退化指纹（截断/占位/工程词两层级） | Oh Story check-degeneration.js | 补入我方 prose_audit 指纹库 |
| 提示词组装外置为脚本 | Oh Story build_writer_prompt.py | 评估我方提示词构建的确定性 |
| 文档体积预算 CI | Oh Story check-doc-budget | 轻量检查，可即做 |
| 关键词触发+预算注入召回 | SillyTavern world-info.js | 远期语义记忆选型 |
| 多后端一层一文件 | SillyTavern endpoints/ | llm.py 多供应商扩展时参考 |
| 一源多衍生（Drama/Comic 管线） | AI-NWA modules/drama、comic | 双通道终点的远亲互证 |

## 4. 结论（四方夹出的我方定位）

- **AI-NWA** 展示全栈工具路线的形态与可靠性挑战（自认 P0 假停止未解）；**InkOS** 证明内核路线的正确性（与我方独立收敛同构）；**Oh Story** 证明方法论资产与分发的价值（★7.5K）；**SillyTavern** 证明提示词工程与生态
- 我方 = InkOS 式内核纵深 + Oh Story 式方法论语料（R8 待补）+ 双通道内容变现终点
- 四方无一家做**爽点/去味的量化闭环 + 付费节奏对齐**——R8 排序维持，空位仍在
- 是否进入工具市场：**开放决策，由 tff 定夺**；相关事实数据见 `comparison.md` §5
## 5. 深度审查文档（deep-dive/，2026-10-17 逐函数核实版）

每项目一份，含详细业务逻辑流 + 代码流（文件:行号证据）+ 针对我方当前困境的解决方案对照：

| 文档 | 项目 | 核心收获 |
|------|------|----------|
| `deep-dive/inkos.md` | InkOS | 引文核验三件套（行号区间→宿主解析→子串核验）、结算失败保正典、钩子仲裁/时态事实 |
| `deep-dive/oh-story.md` | Oh Story | 细纲爽点必填字段、时间线作者真相/读者已知双视图、chapter check 五态出口码、退化指纹五族 |
| `deep-dive/ai-novel-writing-assistant.md` | AI-NWA | gateable 闸+gateId 绑产物版本、A/D/E 质量债机器归因、debt 源状态提案强制人工复核、writer_extend 续写补足 |
| `deep-dive/sillytavern.md` | SillyTavern | World Info 按需召回五件套（关键词/预算/递归/时态/概率）、21 源向量适配器矩阵、一层一文件后端抽象 |