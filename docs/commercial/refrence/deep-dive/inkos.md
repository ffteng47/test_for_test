# InkOS 深度审查：业务逻辑流与代码流（逐函数核实版）

- 代码基线：`refrence_projects/inkos`（packages/core 为内核，v2.0.0 开发分支）
- 审查方式：直接读源码，结论附 `文件:行号` 证据
- 我方对照系：plot_engine（Alexandria）事件溯源 + H1–H8 硬门禁 + 确认闸

## 1. 架构总览

pnpm Monorepo：`packages/core`（内核）/ `packages/cli` / `packages/studio`（GUI）。`core/src` 分层：

| 层 | 目录 | 关键文件 |
|----|------|----------|
| Agent 层 | `agents/` | architect / planner / composer / **writer.ts**(660行) / **continuity.ts**(连续性审计) / reviser / **state-validator.ts** / **radar.ts**(扫榜) / settler-prompts |
| 编排层 | `pipeline/` | **runner.ts**(2063行主编排) / scheduler / **chapter-review.ts** / **chapter-truth-validation.ts** / **chapter-state-recovery.ts** / chapter-persistence / detection-runner / short-fiction-runner / script-storyboard-runner |
| 状态层 | `state/` | **state-reducer.ts**(189行) / **runtime-state-store.ts** / state-projections / state-validator / manager / chapter-workspace / chapter-word-sync |
| 治理层 | `harness/` | builtin-profiles(操作策略Profile) / **parent-canon.ts**(同人正典锚定) / artifact-revisions / work-store / episode-store / execution-evidence / context-compiler / source-sync |
| 模型层 | `models/` | runtime-state(zod) / **observation.ts**(观察+引文核验) / length-governance / input-governance |
| 工具层 | `utils/` | **hook-arbiter.ts** / length-metrics / source-text(行编号) / narrative-control |
| 能力层 | `llm/` `retrieval/` `forecast/` `references/` `materials/` `translation/` `interactive-film/` `play/` `notify/` | 多供应商 LLM 客户端、检索、市场预测、参考语料、素材、翻译、互动影游、webhook 通知 |

## 2. 业务逻辑流（端到端）

### 2.1 写章主链路（`pipeline/runner.ts:1191 writeChapters`）

```
writeChapters(bookId, chapterCount, options)
 ├─ acquireBookLock(bookId)                       # 书级互斥锁
 ├─ startChapterNumber 校验：必须==下一未写章，否则 CHAPTER_WRITE_RANGE_CONFLICT
 │    （错误对象自带 recovery 指引：inspect→只写作者授权的缺失区间）
 └─ for each chapter: _writeNextChapterLocked → _executeNextChapterLocked
      ├─ ensureControlDocuments + loadBookConfig + getNextChapterNumber
      ├─ prepareWriteInput → chapterIntent / chapterMemo / contextPackage（治理后上下文包）
      ├─ buildLengthSpec(wordCount ?? book.chapterWordCount, lang, book)   # 字数=交付规格
      ├─ ① WriterAgent.writeChapter            # 草稿（流式+字数遥测）
      ├─ ② reviewChapterDraft (chapter-review.ts)  # ContinuityAuditor 带引文审计
      │      失败不崩：unavailable=true + observation[review-unavailable]
      ├─ ③ buildPersistenceOutput → settleChapterState（结算：正文→runtimeStateDelta）
      ├─ ④ validateChapterTruthPersistence (chapter-truth-validation.ts)
      │      StateValidator 比对 old/new truth files；不一致→reconcileChapterStateAfterReview
      │      重算仍不一致→preserveCanonicalRuntimeState（保正典、弃 LLM 版、标 runtimeStateApplied:false）
      └─ ⑤ syncWorkSourceArtifacts(accept)      # 按章边界发布工件，后续失败不遮蔽已完成章
```

### 2.2 结算链路（writer → reducer → store）

```
WriterAgent.settleChapterState (writer.ts:214)
 ├─ loadRuntimeStateSnapshot 或 loadRuntimeStateSnapshotAtChapter(baselineChapter)  # 基线快照
 ├─ settle()：buildSettlerSystemPrompt + buildSettlerUserPrompt + governedControlBlock
 │    + validationFeedback（上一轮对账差异，如有）
 │    + "## Settlement baseline" JSON（lastAppliedChapter/currentState/hooks/allowNewHooks）
 ├─ submitStructured(tool="submit_runtime_state_delta",
 │      schema=createSettlementToolSchema(allowNewHooks),
 │      validate=validateSettlementHookIds(knownHookIds))   # 宿主校验钩子ID，模型只能引用已有ID
 ├─ arbitrateRuntimeStateDeltaHooks (hook-arbiter.ts)        # 新钩子走 candidate，宿主造 canonical ID
 ├─ applyRuntimeStateDelta (state-reducer.ts:23)             # 单调入账+入账即校验
 └─ saveRuntimeStateSnapshot → validateLoadedSnapshot → commitAtomicFileSet  # 原子多文件写
```

### 2.3 审计链路（continuity.ts，带引文核验的审稿）

```
ContinuityAuditor.auditChapter (continuity.ts:24)
 ├─ system prompt 硬规：每条观察交 code/assessment/"确切编号原文证据行"；
 │    "不估算字数，字数由宿主计算"；"observations 为空是合法结果"
 ├─ sources = { governed-context, chapter-N }，全部 numberReviewSource 加行号（不改原文）
 ├─ 若工件已落盘：校验草稿==当前 revision 正文（防冒名），
 │    构造 before/after 对比（parent_revision | episode_start，changedSourceRegion 定改动区间）
 ├─ submitSourcedReview → 模型只交 sourceId+startLine/endLine（或 quote）
 ├─ resolveObservationSources：宿主把行号区间解析为精确引文；区间非法→REVIEW_SOURCE_RANGE_INVALID
 │    （报错带 lineCount）；选中全空行→REVIEW_SOURCE_REQUIRED（报错带 nearbyLines 邻近行提示）
 ├─ validateObservationSources：非 unavailable 观察必须有 sourceRefs；
 │    每条 quote 必须是命名来源的精确子串（includes），否则 REVIEW_SOURCE_MISMATCH
 │    （报错指令："用确切摘录，或撤回无证据发现"）
 └─ scope+issue 类观察强制同时引证 before/current 双版本（REVIEW_SCOPE_EVIDENCE_REQUIRED）
```

### 2.4 真相校验与对账（chapter-truth-validation.ts / chapter-state-recovery.ts）

```
validateChapterTruthPersistence
 ├─ validator.validate(content, chapterNumber, oldState, newState, oldHooks, newHooks, authorityContext)
 ├─ 校验器异常 → observation[state-validation-unavailable] + preserveCanonicalRuntimeState
 ├─ observations 全量 logWarn 浮面（不静默）
 └─ !consistent || reconciliationRequired →
      reconcileChapterStateAfterReview：
       ├─ writer.settleChapterState 重算（allowReapply:true + buildStateReconciliationFeedback
       │     把上轮 observations 逐条变成"请对照正文修正以下差异"反馈）
       ├─ 重算结果再过 validator.validate
       ├─ 通过→kind=reconciled；不通过→kind=unresolved + unresolvedStateObservation
       └─ 出口仍 preserveCanonicalRuntimeState（正典永远是 reducer 产物，不是 LLM 自由文本）
```

## 3. 代码流关键实现（逐函数证据）

### 3.1 state-reducer.ts:23 `applyRuntimeStateDelta` —— 单调入账 + 入账即校验

- 入口即 zod parse 快照四件套 + delta（`StateManifestSchema.parse` 等），脏数据进不来
- `delta.chapter <= manifest.lastAppliedChapter` → throw `goes backwards`（`allowReapply` 时仅禁止 `<`，显式重放开关）
- `delta.chapterSummary.chapter !== delta.chapter` → throw；summary 重复行且非 reapply → throw
- 应用完后立刻 `validateRuntimeState(next)`，issue 非空即 throw——**校验在 reducer 内，脏状态落不了盘**

### 3.2 state-reducer.ts 钩子生命周期纪律（applyHookOps / mergeHookRecord）

- `resolve/defer` 未知 hookId → throw；`superseded` 钩子不可 resolve/defer（`HOOK_SUPERSEDED`）
- 已 resolved 的钩子不可被撤回（`HOOK_RESOLVED_HISTORY`）；撤回必须带 notes 理由（`HOOK_WITHDRAWAL_REASON_REQUIRED`）
- `defer` 不更新 `lastAdvancedChapter`，注释原话：**"Postponing a promise is not evidence that its narrative advanced."**（延期不是叙事推进的证据）
- merge 时 `startChapter` 取 min、`lastAdvancedChapter` 取 max、resolved 状态不可逆

### 3.3 state-reducer.ts 事实时态（applyFactOps）

- 每条 fact 带 `validFromChapter / validUntilChapter / sourceChapter`——**事实是有保质期的**
- `expire`：把 `validUntilChapter` 设为 `chapter-1`（不删行，历史可查）
- `upsert`：同 subject+predicate 的旧 fact 自动 expire（新事实顶替旧事实），完全相同的活跃 fact 跳过（幂等）

### 3.4 hook-arbiter.ts `arbitrateRuntimeStateDeltaHooks` —— 钩子仲裁

- upsert 引用未知 hookId → throw 并指明出路：`Submit a newHookCandidate instead`
- `newHookCandidates` 必须 type+expectedPayoff 非空；`allowNewHooks===false` 时提交 candidate 直接 throw
- 新钩子的 canonical hookId 由 `createCanonicalHook` **宿主侧生成**（模型不掌握 ID 命名权）
- `mention` 自动过滤掉已被 upsert/resolve/defer 覆盖的 ID（防双重计数）

### 3.5 runtime-state-store.ts —— 快照即文件 + 原子写

- 状态 = `story/state/` 下 4 个 JSON（manifest/current_state/hooks/chapter_summaries），加载即 zod 校验（`validateLoadedSnapshot`）
- `loadRuntimeStateSnapshotAtChapter`：`story/snapshots/<N>/state/` **每章一份完整快照**（不靠事件重放，直接读目录）——我方 replay 的对应物，实现更简单粗暴但零重放 bug 面
- `saveRuntimeStateSnapshot` → `commitAtomicFileSet`：多文件原子提交，半个状态写不进去

### 3.6 models/observation.ts —— 引文核验三件套（我方 level3 困局的直接答案）

- `numberReviewSource` = `numberSourceLines`：宿主给来源加显示行号，**不修改权威原文**
- `resolveObservationSources`：模型只交 `{sourceId, startLine, endLine}`，宿主切片 `lines.slice(start-1, end).join("\n")` 得到精确引文；区间非法报错带 `lineCount`；选中全空行报错带 `nearbyLines`（邻近非空行内容）引导模型改选
- `validateObservationSources`：`sources.get(sourceId)?.includes(quote)` **精确子串核验**，不过即抛 `REVIEW_SOURCE_MISMATCH`，错误指令原话："Use exact excerpts from the named source for these references, or withdraw unsupported findings. Keep valid references unchanged."
- Observation 分类：`category: execution|quality|scope`、`assessment: issue|resolved|unavailable|observation`——**unavailable 是一等公民**（证据缺失如实记，不硬编）

### 3.7 writer.ts:214 `settleChapterState` —— 结算器

- 基线快照可指定 `baselineChapter`（从 `snapshots/<N>` 重建基线，支持修订旧章）
- 提示词末尾硬编码 "## Settlement baseline" JSON + 指令："Apply the delta to this exact baseline. Existing hook operations may name only its hook IDs. Later projections in retrieved context are references, not the baseline to be mutated."
- 工具描述："只提交正文有证据的增量状态变更；**章节号由宿主持有**"——模型不掌握章节号

### 3.8 chapter-review.ts `reviewChapterDraft` —— 审稿降级哲学

- auditor 抛异常 → 返回 `unavailable: true` + `observation[review-unavailable]`，管线继续——**审稿是观察层不是门禁**，与我方"核验器按风险降级不退休"同构

### 3.9 length-metrics.ts / length-governance.ts —— 字数治理

- `LengthSpec/LengthTelemetry` zod 建模；`DEFAULT_CHAPTER_LENGTH_ZH=3000`
- `assertChapterLength(content, spec)` 宿主侧硬断言；审计提示词明写"不估算字数，字数由宿主计算"
- runner 里 `buildLengthTelemetry({lengthSpec, writerCount, postReviseCount, finalCount, repairApplied})`——字数是**带遥测的交付规格**，每章留 writer/final 双读数

### 3.10 radar.ts —— 扫榜 Agent

- `RadarAgent.scan()`：`Promise.all(sources.map(fetch))` 多源榜单 → `formatRankingsForPrompt` → `submitStructured(tool="submit_market_radar", schema=RadarResultToolSchema, temperature=0.6)`
- 无源证据直接 throw（"Market radar has no source evidence to analyze."）——**无证据不产建议**

## 4. 针对我方当前问题/困境的解决方案对照

| 我方困境 | inkos 方案 | 证据位置 | 可移植性 |
|----------|-----------|----------|----------|
| **level3 引文逐字命中率 34–46%**（画线核验） | 模型只交行号区间，宿主解析为精确引文（构造性锁死=零抄写误差）；宿主 `includes` 精确子串核验，不过即带指令重试；全空行选中给 nearbyLines 引导 | `models/observation.ts` resolveObservationSources / validateObservationSources | **极高**——我方 v0.4 行号区间批已独立收敛到同一形态（tff 风险①兑现），可再移植 REVIEW_SOURCE_MISMATCH 的"撤回无证据发现"指令与 nearbyLines 提示 |
| **committed 章机检盲区**（ch50 掉锚） | before/after 双版本对比审计：parent_revision / episode_start 两种 scope + changedSourceRegion 定改动区间；scope 类观察强制双版本引证 | `agents/continuity.ts` comparison 构造 + REVIEW_SCOPE_EVIDENCE_REQUIRED | 高——我方审计只审"当前章"，inkos 审"改动"；需要工件版本链（我方有 event.db 归档可对应） |
| **审后状态与正文不一致** | truth-validation → recovery（带 observation 反馈重算）→ preserveCanonicalRuntimeState（保正典弃 LLM 版，runtimeStateApplied:false 显式标记） | `pipeline/chapter-truth-validation.ts` / `chapter-state-recovery.ts` | 高——我方 revision 后状态一致性缺这层"结算失败保正典"兜底 |
| **钩子/伏笔管理** | 生命周期纪律：superseded 不可动、撤回要理由、defer 不算推进、resolved 不可逆；新钩子走 candidate 宿主造 ID | `state-reducer.ts` applyHookOps / `utils/hook-arbiter.ts` | 高——我方 hooks 闸可整套对照 |
| **事实过期/知识边界** | fact 时态：validFromChapter/validUntilChapter/sourceChapter，expire 不删行 | `state-reducer.ts` applyFactOps | 高——我方 fact.py 目前是布尔/键值，可加保质期字段 |
| **字数治理**（E24：让模型数段落=常量灾难） | 字数宿主计算写进审计提示词；LengthSpec/Telemetry 每章双读数留痕 | `utils/length-metrics.ts` / continuity.ts system prompt | 高——与我方"机器读数上屏"同一哲学，遥测双读数可补 |
| **审稿器自身可靠性** | 审稿失败降级为 unavailable observation，管线不崩；StateValidator 不可用同样降级 | `chapter-review.ts` / `chapter-truth-validation.ts` | 已有同构（核验器降级不退休），互证 |
| **扫榜/市场感知（R8 #5）** | RadarAgent + RadarSource 多源榜单→结构化建议，无证据不产建议 | `agents/radar.ts` / `radar-source.ts` | 中——形态可搬，数据源要自建 |
| **多文件状态原子写** | commitAtomicFileSet | `state/runtime-state-store.ts` saveRuntimeStateSnapshot | 中——我方 CAS 已互证，原子多文件写可补 |

## 5. 与我方架构的异同（诚实对照）

| 维度 | inkos | 我方 plot_engine |
|------|-------|------------------|
| 状态推进 | delta 单调入账 + zod 入账即校验 | 事件溯源 + CAS + Proposal/Validation/Commit |
| 历史重建 | **每章一份完整快照目录**（snapshots/N/state/） | replay 事件流重建（更省空间，重放逻辑有 bug 面） |
| 审稿定位 | 观察层（不卡门禁），引文宿主核验 | H1–H8 硬门禁 + level3 旁路核验 |
| 钩子 ID | 宿主造 canonical ID，模型只引用 | 模型产出，闸校验 |
| 字数 | 宿主计算+遥测双读数 | Writer 提示词"写 2~4 段"（E24 教训在册） |
| 审计对象 | 当前章 + before/after 改动区间双模式 | 当前章（committed 盲区已实证） |

## 6. 一句话结论

InkOS 与我方独立收敛到同一内核形态（delta+reducer+校验+回放），其**引文核验三件套（行号区间→宿主解析→子串核验）**和**结算失败保正典**是我方 level3 画线与状态对账两个困局的可直接移植方案；其每章快照目录 vs 我方事件 replay 是两种历史重建路线的互证对偶。