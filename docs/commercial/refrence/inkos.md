# InkOS（Narcooo/inkos）— 架构 / 商业 / 业务流 / 代码流

- 代码基线：`refrence_projects/inkos`（792 文件，v2.0.0 开发分支）
- License：AGPL-3.0
- npm：`@actalk/inkos`；赞助方：Moonshot Kimi、字节火山引擎；网页版托管于 huohuaapi.com

## 0. 一句话定位

**与我方内核最同构的参照系**：多 Agent 分工 + 事件溯源式状态（delta + reducer + 快照回放）+ 字数量化治理，覆盖长篇/短篇/剧本/互动影游/翻译的创作智能体系统。

## 1. 架构

pnpm Monorepo：`packages/core`（内核）/ `packages/cli` / `packages/studio`（GUI）。`core/src` 分层：

| 层 | 目录 | 职责 |
|----|------|------|
| Agent 层 | `agents/` | Architect / Planner / Composer / Writer / ContinuityAuditor / Reviser / StateValidator / **Radar（扫榜）** |
| 编排层 | `pipeline/` | runner（主编排）、scheduler、detection-runner、chapter-review、chapter-persistence、**chapter-truth-validation**、**chapter-state-recovery**、short-fiction-runner、script-storyboard-runner |
| 状态层 | `state/` | runtime-state-store、**state-reducer**、state-projections、state-validator、manager、chapter-workspace |
| 治理层 | `harness/` | builtin-profiles（操作策略 Profile）、**parent-canon**（同人/仿写继承正典锚定） |
| 能力层 | `llm/`、`retrieval/`、`forecast/`、`references/`、`materials/`、`translation/`、`interactive-film/`、`play/`、`notify/`（webhook 通知） |
| 规格 | `spec/creative-harness-v2.md` | 统一创作底座 v2 设计文档 |

## 2. 业务流

```
作品配置(BookConfig/Profile)
 → Architect（架构：设定/卷纲）
 → Planner（章节规划 PlanChapterOutput）
 → Composer（组章 ComposeChapterOutput）
 → Writer（正文 WriteChapterOutput，流式 + 字数遥测）
 → ContinuityAuditor（连续性审计 AuditResult）
 → Reviser（修訂，DEFAULT_REVISE_MODE）
 → StateValidatorAgent（状态校验 ValidationResult）
 → 状态 delta 入账（StateManager.applyRuntimeStateDelta）
 → 投影重渲染（current_state / hooks / chapter_summaries 三视图）
 → chapter-truth-validation（真相校验）→ chapter-state-recovery（未决观察回收）
```

辅助回路：RadarAgent + RadarSource（扫榜输入）、ContextCompressionCallback（上下文压缩）、Observation（观察模型，未决状态回收）、webhook 通知、archiveChapterVersion（章节版本归档）、readChapterUserBrief（人工简报注入）。

## 3. 代码流（核心证据）

### 3.1 状态 = 不可变快照 + delta 单调入账（`state/state-reducer.ts`）

- RuntimeStateSnapshot = `{ manifest, currentState, hooks, chapterSummaries }`，全部 zod Schema 校验
- `applyRuntimeStateDelta` 硬约束：**delta.chapter 必须严格前进**（`goes backwards` 抛错）、summary 章节号必须匹配、重复行拒绝；`allowReapply` 显式重放开关
- 入账后 `validateRuntimeState` 全量校验，issue 非空即抛——**校验在 reducer 内，脏状态落不了盘**

### 3.2 快照回放（`state/runtime-state-store.ts`）

- `loadRuntimeStateSnapshotAtChapter` —— 按章节号重建任意历史状态 = 我方 replay 的对应物
- `state-projections.ts` 三投影渲染：`renderCurrentStateProjection / renderHooksProjection / renderChapterSummariesProjection`

### 3.3 字数治理（`utils/length-metrics.ts` + `models/length-governance.ts`）

- LengthSpec / LengthTelemetry / `buildLengthSpec` / `countChapterLength` / `resolveLengthCountingMode`——**字数是带遥测的交付规格**，不是提示词愿望

### 3.4 主编排（`pipeline/runner.ts`）

- 依赖注入式组装全部 Agent + StateManager + LLMClient（`createLLMClient`，支持 AgentLLMOverride 按代理换模型）
- 读写分离：`readStoryFrame / readVolumeMap / readCharacterContext`（outline-paths）喂上下文，章版本先归档再覆写
- `reconcileChapterStateAfterReview` + `unresolvedStateObservation`（chapter-state-recovery.ts）：审后状态对账，未决观察显式回收

## 4. 商业

- **模式**：开源内核 + npm 分发 + **厂商赞助**（Kimi/火山，README 挂 aff 链接导流 API 售卖）+ 网页托管版（huohuaapi）+ 数据 API 联动（"火花数据"按调用计费的小说素材 API，推荐搭配）
- 本质：**赞助型开源**——模型厂商出钱买入口，项目方出分发位；与我方"自产内容变现"不同赛道
- **架构互证**：其 reducer/投影/回放与我方 store CAS + replay 独立收敛到同一设计，强互证

## 5. 对我方的价值排序

1. **强互证**：delta 单调入账 + 入账即校验 + 按章回放 + 三投影——我方事件溯源路线被独立复现，方向正确性加码
2. **可借鉴**：① 字数治理遥测（LengthSpec/Telemetry）→ R8 #1 爽点/量化体系的兄弟机制；② parent-canon（正典锚定）→ 旧稿导入（R8 #6）与仿写场景的参照；③ Radar 扫榜 Agent 化 → R8 #5；④ 审后状态对账回收（state-recovery）→ 我方 revision 后状态一致性
3. **注意**：v2.0 仍在迁移期（`inkos work migrate` 导入 1.x 项目），其自身也在为"状态不兼容的历史项目"付迁移成本——我方 schema 演进纪律（尺号/迁移矩阵）同样是刚需