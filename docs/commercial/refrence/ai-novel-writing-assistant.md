# AI-Novel-Writing-Assistant — 架构 / 商业 / 业务流 / 代码流（本地代码核实版）

- 代码基线：`refrence_projects/AI-Novel-Writing-Assistant`（depth-1 克隆，3142 文件）
- 关联：`docs/commercial/ai-novel-writing-assistant-comparison-v1.0.md`（对标评估，本文档含三点**修正**）
- License：AGPL-3.0 + CLA

## 0. 修正记录（对本系列前文的更正）

| # | 前文说法 | 代码核实结果 |
|---|----------|--------------|
| 1 | "LangGraph 是编排承重墙" | LangGraph 仅用于 3 张辅助图（`server/src/graphs/`: characterDesignGraph / novelOutlineGraph / writingFormulaGraph）。**主生产链是自研 Director step DAG + ChapterRuntimeCoordinator**，承重墙是自研的 |
| 2 | "拆书（无扫榜）" | **有扫榜**：`modules/marketRadar` + 模型表 MarketScanRun / MarketRankingSnapshot / MarketTrendReport / MarketCreativeBrief（榜单 → 趋势报告 → 选题简报全链路入库） |
| 3 | 未提衍生品 | **有短剧/漫画衍生管线**：`modules/drama`（DramaEpisode/Storyboard/Shot/VideoPrompt）、`modules/comic`（Panel/ExportJob）——一源多用的 IP 衍生，与我方有声书通道同构 |

## 1. 架构

pnpm Monorepo：`client`（React）/ `server`（Express + TS）/ `desktop` / `shared`（类型与工具）/ `infra` / `site`。

`server/src` 分层：

- `modules/`（12 个业务域）：novel（核心）、director（自动导演）、bookAnalysis（拆书）、marketRadar（扫榜）、knowledge（知识库）、timeline、characterConversation、export、setup、comic、drama、visualAssets
- `services/`（19 个服务域）：novel/、state/、styleEngine/、rag/、audit/、payoff/（伏笔回报）、planner/、world/、character/、adaptation/、task/ 等
- `graphs/`（3 张 LangGraph 辅助图）、`chains/`（3 条 LangChain 链）、`llm/`（流式 SSE）、`workers/`、`prompting/`、`runtime/`
- HTTP 层薄：`modules/*/http/*Routes.ts` 只做 zod 校验 + 转发 service

**Prisma 双 schema**（`schema.prisma` / `schema.sqlite.prisma`，3916 行、约 150 模型），分组：书与章节、角色（Mind/Influence/Dialogue/Cast/Faction）、世界（ConsistencyIssue!）、写法（WritingFormula/StyleProfile/AntiAiRule/StyleBinding）、**状态提案层**、审计、知识库+RAG、时间线、衍生（Drama/Comic）、市场（Market*）、Director 运行时（Run/StepRun/Artifact/Event/Checkpoint/LlmUsageRecord）。

## 2. 业务流

### 2.1 开书（自动导演 DAG，代码即流程）

`server/src/modules/director/steps/planDefinition.ts` 声明式定义（`director-next-production-v1`）：

```
novel_seed
 └ story_macro（故事宏观规划）
    └ book_contract（书级创作约定）
       ├ world_setup（世界骨架）
       └ character_setup（角色阵容，gateable=人工闸）
          └ volume_strategy（分卷策略，gateable）
             ├ volume_beat_sheet（卷节奏板）
             └ volume_chapter_list（卷拆章列表）
                └ chapter_detail_bundle（章节任务单，gateable）
                   └ execution_contract_sync（执行合同，gateable）
                      └ chapter_batch（章节生成批次，gateable）
```

每步声明 `requires / produces / needs(structured_output) / gateable / overwrites`——**人工审批闸是 DAG 节点属性**，产物间依赖可追溯（DirectorArtifactDependency）。gateable 步骤可自动批准（AutoDirectorAutoApprovalRecord 留痕）。

### 2.2 章节生产（运行时管线）

HTTP `POST /:id/chapters/:chapterId/runtime/run` → `stepModuleRunner.runStep(chapter_execution)` → `ChapterRuntimeCoordinator`（DI 门面）→ `ChapterStreamGenerationOrchestrator.createChapterStream`（SSE 流式）→ `chapterRuntimePipeline.ts`（767 行核心）：

1. 组装 ChapterRuntimePackage（上下文包）
2. 生成（预算预检：`DIRECTOR_CHAPTER_PREFLIGHT_RESERVE_TOKENS = 16_000`，超额前停管线）
3. 空内容检测与重试（chapterEmptyContentError）
4. 质量门（ChapterQualityGateService + acceptance 验收评估）
5. 修复选择（repairMode 六档：detect_only / light / heavy / continuity_only / character_only / ending_only；ChapterRepairCandidateSelection 选修复候选）
6. **质量债归因**（QualityDebtAttribution）：首次/二次失败 issue codes、failureClassification 根因码（A=义务未传达给修复器、D=计划不可达、E=长度/内容签名漂移）、missingObligationKinds——`defer_and_continue` 时入库供 `analyze_quality_debt_attribution` 聚合
7. 制品同步（ChapterArtifactSyncService，director_v2 策略）

另：`chapterWritingGraph.ts` 负责写作图内部——continuityNode 连续性检查、enforceTargetLength **自动续写补足目标字数**（writer_extend 阶段，按 min/max/target 追加预算续写，禁止重开一章）。

### 2.3 状态回流（提案制，非直写）

模型表证据：CanonicalStateVersion + **StateChangeProposal** + StoryStateSnapshot + CharacterState / RelationState / InformationState / ForeshadowState / OpenConflict / **PayoffLedgerItem**（伏笔回报台账）/ CharacterResourceLedgerItem + ReplanRun。状态变更先提案、再入账、版本化——与我方 Proposal/Validation/Commit 同构。

## 3. 代码流核心文件清单（后续精读入口）

| 关注点 | 文件 |
|--------|------|
| 导演 DAG 定义 | `server/src/modules/director/steps/planDefinition.ts` |
| 导演领域（闸/守卫） | `server/src/modules/director/domain/gateOrchestrator.ts`、`domain/guard.ts` |
| 章节运行时编排 | `server/src/services/novel/runtime/ChapterRuntimeCoordinator.ts`（DI 门面） |
| 流式生成编排 | `runtime/ChapterStreamGenerationOrchestrator.ts` |
| 章节管线主逻辑 | `server/src/services/novel/runtime/chapterRuntimePipeline.ts` |
| 写作图（续写补足） | `server/src/services/novel/chapterWritingGraph.ts` |
| 质量门 | `server/src/services/novel/runtime/ChapterQualityGateService.ts` |
| 修复资格/候选 | `runtime/repair/ChapterRepairEligibility.ts`、`runtime/selection/ChapterRepairCandidateSelection.ts` |
| 制品同步 | `runtime/artifactSync/ChapterArtifactSyncService.ts` |
| 写法引擎 | `server/src/services/styleEngine/`（含 styleGenerationSanitizer 违禁实体检测） |
| RAG | `server/src/services/rag/`（KnowledgeChunk / RagIndexJob / RagRetrievalTrace） |
| 数据模型总表 | `server/src/prisma/schema.prisma`（3916 行） |

## 4. 商业

- **模式**：工具产品（桌面版 v0.4.11）+ AGPL/CLA 商业授权；网页/API 未见公开收费
- **其 License 对其自身商业化的影响**（研究稿既有结论）：服务式商用需维护者单独授权，私有化部署是其授权体系外的主路径
- **可靠性观察**：其 roadmap 自承 P0 = "减少假停止与异常 token 消耗"——端到端可靠性仍在攻坚
- **对我方价值**：① Director DAG 的 gateable 节点抽象 → R8 #2 确认闸设计参考；② 质量债归因码（A/D/E 根因分类）→ 与我方 revision 归因阶梯互证；③ Drama/Comic 衍生管线 → 我方有声书通道的远亲，证明"一源多衍生"工程可行；④ StateChangeProposal 提案制 → 与我方 Event Proposal 同构，方向互证；⑤ chapterWritingGraph 的**目标字数自动续写补足** → 与 InkOS 字数治理互证"字数是交付规格"