# 四方参考项目 vs 我方 — 对比总文档 v1.0

- 建立：2026-10-15；全部结论基于本地代码核实（`refrence_projects/`）
- 定位：对比事实库 + 决策支持；**不含路线裁决**——是否进入工具市场等开放问题由 tff 决策（§6 列决策所需事实）

## 1. 一句话定位对照

| 项目 | 一句话 | 与我方关系 |
|------|--------|-----------|
| AI-Novel-Writing-Assistant（★3.1K） | 全栈桌面/Web 创作产品，Director DAG 驱动 | 形态参照 + 可靠性前车之鉴 |
| InkOS | npm 创作内核 + CLI/Studio，赞助型开源 | **内核同构互证**（最强） |
| Oh Story（★7.5K） | 方法论语料 + Skill 编排，寄生宿主 CLI | 方法论资产参照 + 分发形态参照 |
| SillyTavern | 互动 RP 前端，提示词组装天花板 | 零件图鉴（后端抽象/RAG/召回） |
| **我方 novel-audiobook** | 确定性内核自产内容，双通道变现 | — |

## 2. 能力矩阵（代码核实）

| 能力 | AI-NWA | InkOS | Oh Story | SillyTavern | 我方 |
|------|--------|-------|----------|-------------|------|
| 编排 | 自研 DAG（gateable 节点） | runner 直排 | 宿主+Hook 门禁 | 无链 | 自研状态机 |
| 状态权威 | StateChangeProposal 提案制 | delta 单调入账+入账即校验 | storyctl commit | 无 | **CAS+事件溯源+尺号** |
| 断点恢复 | RuntimeCheckpoint | **按章回放** | 文件冗余 | 无 | **replay** |
| 失败归因 | 质量债归因码 A/D/E | 审后状态对账 | 重生成带约束 | 无 | **revision 八层归因** |
| 量化治理 | QualityReport | **字数规格+遥测** | 字数脚本判据 | token 预算 | 尺号体系 |
| 扫榜 | marketRadar | RadarAgent | story-*-scan | 无 | 缺（R8 #5） |
| 拆书 | bookAnalysis→写法编译 | references/ | story-*-analyze | 无 | 缺（R8 #4） |
| 人工闸 | **gateable DAG 节点** | 修订流程 | 开书停正文前 | 无 | 缺（R8 #2） |
| 去 AI | AntiAiRule 基线+专属 | — | lint 两层级+三遍法 | 无 | lint（R8 #3 升级） |
| 语义记忆 | RAG（Qdrant 可选） | retrieval/ | 无 | 8 源向量适配 | 无（远期） |
| 衍生品 | **Drama/Comic 管线** | 剧本/互动影游 | 封面 | 无 | **有声书通道** |
| 质量证据 | P0 假停止未解 | v2.0 迁移期 | 25+ CI 检查脚本 | 大社区 | **526 tests+尺号回归** |

## 3. 互证清单（我方路线被独立验证的部分）

1. **事件溯源状态**：InkOS delta+reducer+按章回放 ≈ 我方 store CAS+replay——独立收敛同构
2. **提案制状态变更**：AI-NWA StateChangeProposal ≈ 我方 Event Proposal/Validation/Commit
3. **门禁前置**：Oh Story outline-before-prose ≈ 我方 Chapter Contract 先行
4. **字数为交付规格**：InkOS LengthSpec/遥测 + AI-NWA chapterWritingGraph 自动续写补足 ≈ 我方量化治理方向
5. **一源多衍生**：AI-NWA Drama/Comic ≈ 我方有声书通道

## 4. 差距清单（四方有、我方无 → 已全部进入 R8）

| 差距 | 最佳参照 | R8 落点 | 排序 |
|------|----------|---------|------|
| 爽点/情绪量化 | Oh Story 方法论语料颗粒度 | #1 爽点工程 | 1 |
| 人工闸节点化 | AI-NWA gateable | #2 开书确认闸 | 2 |
| 去味量化预算/指纹 | Oh Story check-degeneration 两层级 | #3 量化去味 | 3 |
| 拆书→可生效约束 | AI-NWA 写法编译 | #4 拆文库 | 4 |
| 扫榜→选题简报 | AI-NWA marketRadar | #5 扫榜 | 5 |
| 旧稿导入/正典锚定 | InkOS parent-canon | #6 旧稿导入 | 6 |

**空位确认**：爽点量化、去味量化预算、付费节奏对齐——四方皆无，R8 做完即独占。

## 5. 反方证据（参照系暴露的风险，我方已免疫或需警惕）

| 风险 | 出处 | 我方状态 |
|------|------|----------|
| 端到端可靠性未证明（假停止/异常 token） | AI-NWA roadmap P0 | **已免疫**：526 tests + 尺号回归 + 归因阶梯 |
| 历史项目状态不兼容的迁移成本 | InkOS v1→v2 migrate | **已免疫**：迁移矩阵 + 尺号一因一批 |
| 上下文成本失控 | Oh Story SKILL.md 82KB→54KB 瘦身史 | 需警惕：我方提示词资产也应做体积预算（参照 check-doc-budget） |
| 单轮最优 ≠ 长链一致 | SillyTavern 无状态哲学 | **已免疫**：状态层是主投入方向 |

## 6. 开放决策支持（不下结论）

**决策问题：是否/何时进入工具市场（在双通道内容终点之外）。** 相关事实：

- 赛道拥挤度：开源同品类十余个，多在 500★ 以下；头部形态分化——Skill 包（Oh Story ★7.5K）增速 > 全栈产品（AI-NWA ★3.1K）> 内核库（InkOS，npm 下载量未查）
- 市场规模（研究稿转引，未独立核实）：AI 小说工具 2025 全球约 1.79 亿美元，CAGR 10.7%；广义 AI 创意写作助手 22 亿美元，CAGR 21.4%
- 现有工具共同软肋：可靠性（AI-NWA P0）、量化质量闭环（四家皆无）、长篇一致性（Oh Story 无事务状态层）
- 我方若切入的既有优势：质量基础设施（526 tests/尺号/归因）恰是竞品空白；内核已是 InkOS 同构形态，加 CLI/Studio 壳的路径被 InkOS 证明可行
- 商业化模式谱系（参照系实况）：卖工具（AI-NWA）/ 赞助+托管+数据 API（InkOS）/ 免费流量入口（Oh Story）/ 纯社区（SillyTavern）

## 7. 文档地图

- 本文件：对比总文档
- `README.md`：索引 + 四方矩阵 + 机制参考总表
- `ai-novel-writing-assistant.md` / `inkos.md` / `oh-story.md` / `sillytavern.md`：分项目架构/商业/业务流/代码流
- 上级目录：`r8-commercial-input-requirements-v1.0.md`（需求规格，已确认）、两份主分析报告