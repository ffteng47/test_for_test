# AI-Novel-Writing-Assistant 深度审查：业务逻辑流与代码流（逐函数核实版）

- 代码基线：`refrence_projects/AI-Novel-Writing-Assistant`（3142 文件，桌面版 v0.4.11）
- 审查方式：直接读源码，结论附 `文件:行号` 证据
- 形态：**全栈产品**（React client + Express/TS server + Electron desktop + Prisma/SQLite），四参照系中唯一完整产品形态

## 1. 架构总览

`server/src` 关键分层：

| 层 | 位置 | 内容 |
|----|------|------|
| 业务域 | `modules/`（12 个） | novel（核心）/ **director**（自动导演 DAG）/ bookAnalysis（拆书）/ **marketRadar**（扫榜）/ knowledge / timeline / characterConversation / export / setup / **comic** / **drama**（衍生管线）/ visualAssets |
| 服务层 | `services/`（23 个域） | novel/（含 runtime、state、quality、repair、selection、artifactSync）/ **styleEngine**/ rag/ audit/ payoff/（伏笔回报）planner/ world/ character/ adaptation/ task/ state/ |
| 辅助图 | `graphs/` | 仅 3 张 LangGraph 辅助图（characterDesign / novelOutline / writingFormula）——**主生产链是自研 Director step DAG，LangGraph 不是承重墙** |
| 数据层 | `prisma/` | 双 schema（PostgreSQL/SQLite），3916 行约 150 模型：书与章节、角色（Mind/Influence/Dialogue/Cast/Faction）、世界（ConsistencyIssue）、写法（WritingFormula/StyleProfile/AntiAiRule/StyleBinding）、**状态提案层**、审计、RAG、时间线、衍生、市场、Director 运行时（Run/StepRun/Artifact/Event/Checkpoint/LlmUsageRecord） |
| HTTP 层 | `modules/*/http/*Routes.ts` | 薄：zod 校验 + 转发 service |

## 2. 业务逻辑流

### 2.1 开书（Director DAG，`modules/director/steps/planDefinition.ts:8-17`）

声明式 10 步，每步带 `requires / produces / needs / gateable / overwrites`：

```
novel_seed
 └ story_macro（故事宏观规划）
    └ book_contract（书级创作约定）
       └ world_setup（世界骨架）
          └ character_setup ★gateable（角色阵容）
             └ volume_strategy ★gateable（分卷策略）
                ├ volume_beat_sheet（卷节奏板）
                └ volume_chapter_list（卷拆章列表）
                   └ chapter_detail_bundle ★gateable（章节任务单）
                      └ execution_contract_sync ★gateable（执行合同）
                         └ chapter_batch ★gateable（章节生成批次）
```

**人工审批闸是 DAG 节点的声明属性**（gateable: true），5 个闸点全在"资产定型"处。

### 2.2 闸编排（`modules/director/domain/gateOrchestrator.ts:5`）

`createGateOrchestrator().next({plan, contract, facts})` 每轮返回五种动作之一：

1. `facts.stopSignal` 存在 → 按 kind 分流：replan→pause(replan)、manual_recovery→pause、action==fail_task→fail、其余→pause(safety)
2. 有 gateable 步骤产物为 draft → `open_gate`，**gateId = `gate:{runId}:{produces}@{version},…`**（闸与具体产物版本绑定，版本变了闸自动失效）
3. 有 ready 步骤（`requireConfirmed: true`）→ `run_step`
4. 无剩余步骤 → `complete`
5. 否则 → `pause(manual_recovery, "no_runnable_step")`（**死锁显式化**，不空转）

注释原话："Assisted driving is a separate policy; it shares dependency facts, never the automatic orchestrator."（辅助驾驶复用事实不复用编排器）

### 2.3 章节生产运行时（`services/novel/runtime/chapterRuntimePipeline.ts`，32828 字节）

```
runStep(chapter_execution)
 ├─ 预算预检：hooks.onCheckBudget(DIRECTOR_CHAPTER_PREFLIGHT_RESERVE_TOKENS=16_000)（:29,:298,:428）
 │    生成前/修复前各检一次，超额前停管线
 ├─ ChapterStreamGenerationOrchestrator 流式生成（SSE）
 ├─ 空内容检测重试（chapterEmptyContentError）
 ├─ 验收评估：acceptanceResult.assessment
 │    ├─ continuePolicy==pause 或 acceptanceStatus==needs_manual_review → 暂停交人
 │    ├─ continuePolicy==repair_once 或 repairable → 修复一次
 │    └─ factPreservation（修复前后事实保持核验）+ riskTags（acceptance_gate_unavailable
 │       属 NON_PATCHABLE_REVIEW_ISSUE_CODES，不可补丁修复）
 ├─ 修复：repairMode 六档 detect_only / light_repair / heavy_repair /
 │    continuity_only / character_only / ending_only（chapterPatchRepairService.ts:16-19）
 │    "unchanged prose needs no paid re-acceptance"（:453 注释：正文没变不花二次验收的钱）
 └─ defer_and_continue 收尾时 → buildQualityDebtAttribution 入库
```

### 2.4 质量债归因（chapterRuntimePipeline.ts:764 `buildQualityDebtAttribution`）

结构化根因分类，供 `analyze_quality_debt_attribution` 工具聚合占比：

- **根因 A**（义务未传达给修复器）：`sameObligationRepeated` = 首次与二次失败 issue codes 集合**完全一致**（修了一遍原样失败⇒修复器根本没收到义务）
- **根因 D**（计划不可达）：`planMisaligned` = firstFailureClassificationCode ∈ {`draft_obligation_unmet`, `replan_required`}
- **根因 E**（签名漂移）：`lengthVsContentDrift` = 首次全是 `LENGTH_*` 类 issue、二次冒出 content 类（修字数把内容修漂了）
- 附带 `missingObligationKinds`（obligationCoverage.missing[].kind）、修复次数用量（合同只允许 0 或 1 次）

### 2.5 目标字数自动续写补足（`chapterWritingGraph.ts:168 enforceTargetLength`）

```
buildLengthInstruction(target ?? chapterMission.targetWordCount) → {target,min,max}
countChapterCharacters(content) → buildContinuationBudget(current, goal)   # 无预算缺口直接返回
组装续写上下文：current_draft_excerpt 块（priority=99, required）+ 书台块 + 章节块
 → sanitizeWriterContextBlocks 守卫（被移块 logWarn 留痕）
streamTextPrompt(stage="writer_extend", triggerReason="length_recovery",
                 maxTokens=continuationBudget.maxOutputTokens)             # 续写不重开一章
追加内容 > maxAdditionalCharacters → 拒绝并 logWarn（beforeLength/additionalCharacters 全留痕）
追加为空 → 保留原稿
```

### 2.6 状态回流：提案制（`prisma/schema.prisma:2904 StateChangeProposal`）

字段：`sourceType / sourceStage / proposalType / **riskLevel** / status(默认validated) / evidenceJson / validationNotesJson / committedVersionId→CanonicalStateVersion`。变更先提案、验证、再入账、版本化——与我方 Proposal/Validation/Commit 同构。

**来源质量溯源**（`services/novel/state/stateProposalSourceQuality.ts`）：`ContentProvenance = confirmed | debt`；`sourceQuality:debt` 或 validationNotes 含 `source_quality:debt` 的提案 → `markDebtSourcePendingReview`：强制 `status=pending_review` + 追加 `quality debt source requires manual review`——**质量债章节产出的状态变更自动打入人工复核**，低质量来源不配自动入账。

### 2.7 LLM 输出清洗（`services/state/StateService.ts`）

- `INVALID_CHAPTER_REFERENCE_VALUES`：{"null","undefined","none","n/a","na","unknown","unknown_chapter_id","placeholder_chapter_id",…} 显式黑名单
- `isPlaceholderChapterReference`：`/^chapter_\d+$/` 占位符拒认
- `findChapterIdByReference`：直接 id/标题匹配 → `第N章` 正则 → 纯数字，三级解析把 LLM 的自由文本章节引用钉到真实章节 id

## 3. 其余关键域速览（读码核实）

- **扫榜**：`modules/marketRadar/`（MarketRadarService + marketRadarSources + 测试），模型表 MarketScanRun/MarketRankingSnapshot/MarketTrendReport/MarketCreativeBrief——榜单→趋势报告→选题简报全链路入库
- **去 AI 味**：`services/styleEngine/` AntiAiRuleService + AntiAiPolicyResolver + styleGenerationSanitizer（`sanitizeStyleContextForGeneration` / `detectForbiddenStyleEntities` 违禁实体检测）——基线规则+书本专属规则双层
- **伏笔回报**：`services/payoff/` PayoffLedgerItem 台账 + StateService 入账时 payoffLedgerSyncService 同步
- **衍生管线**：`modules/drama`（DramaEpisode/Storyboard/Shot/VideoPrompt）、`modules/comic`（Panel/ExportJob）——一源多衍生
- **RAG**：`services/rag/`（KnowledgeChunk/RagIndexJob/RagRetrievalTrace，Qdrant 可选）
- **可靠性自陈**：其 roadmap 自认 P0="减少假停止与异常 token 消耗"——全栈工具路线的端到端可靠性仍在攻坚

## 4. 针对我方当前问题/困境的解决方案对照

| 我方困境 | AI-NWA 方案 | 证据位置 | 可移植性 |
|----------|------------|----------|----------|
| **确认闸设计（B5 裁决状态机在途）** | gateable=DAG 节点声明属性；gateId 绑定 runId+产物@版本（版本变闸自动失效）；stopSignal 四态分类；死锁显式 pause("no_runnable_step") | `gateOrchestrator.ts:5` 全文 | 高——我方确认闸是 CAS 状态机，其"闸与产物版本绑定"和"死锁显式化"两点可直接补入 |
| **质量归因（revision 归因阶梯）** | A/D/E 三码机器判定：同 obligation 重复=义务未传达（集合比较）；draft_obligation_unmet=计划不可达；LENGTH→content=签名漂移 | `chapterRuntimePipeline.ts:764` | **极高**——sameObligationRepeated 就是"修了一遍原样失败"的机器判据，我方归因阶梯目前是人工/半自动，这个判定可直接实现 |
| **低质量产出污染状态账** | debt 溯源：质量债章的状态提案强制 pending_review 人工复核 | `stateProposalSourceQuality.ts` | 高——我方 needs_decision 章的派生事实目前无降级标记，这是现成机制 |
| **爽点工程（R8 #1）** | 爽点节奏在卷级设计：volume_beat_sheet（卷节奏板）是 DAG 正式产物 | `planDefinition.ts:13` | 中——与 Oh Story 细纲爽点字段互证"爽点是设计产物"；我方正文抽读数是第三条路（可度量） |
| **字数治理** | 目标字数自动续写补足：预算制 writer_extend + 超额拒收 + 空追加保留原稿 + 不重开一章 | `chapterWritingGraph.ts:168` | 高——我方 Writer 欠长目前靠提示词愿望，续写补足是工程解 |
| **修复成本控制** | 六档 repairMode 按需选（continuity_only/character_only/ending_only 定向修复）；"正文没变不花二次验收的钱" | `chapterPatchRepairService.ts` / pipeline:453 | 高——我方 rescue 目前是整章重来，定向修复模式可分层 |
| **LLM 输出自由文本引用** | 章节引用三级解析+占位符黑名单 | `StateService.ts` INVALID_CHAPTER_REFERENCE_VALUES | 中——细节但实用，我方 settlement 输出清洗可参照 |
| **验收器自身可靠性** | acceptance_gate_unavailable 入 riskTags 且列 NON_PATCHABLE（验收器坏了不许补丁糊过去） | `chapterRuntimePipeline.ts:191` | 高——与我方"核验器降级不退休"同构且更硬：不可修复类显式枚举 |
| **一源多衍生（有声书通道远亲）** | drama/comic 衍生管线模块化 | `modules/drama` / `modules/comic` | 低（形态差异大），互证"一源多用"工程可行 |

## 5. 与我方架构的异同（诚实对照）

| 维度 | AI-NWA | 我方 plot_engine |
|------|--------|------------------|
| 形态 | 全栈产品（GUI 驱动） | 内核+管线（CLI/后端） |
| 编排 | 自研 DAG + gateable 闸（LangGraph 仅辅助） | 线性管线+确认闸 CAS |
| 状态 | Prisma 关系库 + StateChangeProposal 提案制 | SQLite 事件溯源+CAS |
| 质量 | 验收评估+六档修复+A/D/E 归因 | H1–H8 硬门禁+revision 归因阶梯 |
| 可靠性 | 自认 P0 假停止未解 | 链验 590 测试基线 |
| 爽点 | 卷节奏板（设计层） | 正文派生读数（度量层） |

## 6. 一句话结论

AI-NWA 是"全栈工具路线"的完整样本：Director DAG 的 gateable 闸、A/D/E 质量债机器归因、debt 来源状态提案强制人工复核、writer_extend 预算制续写，四件都是我方在途事（确认闸/归因/状态账污染/字数）的可直接移植实现；其自认的 P0 可靠性困境从反面印证我方"内核纵深+链验基线"路线的正确性。