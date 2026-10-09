# Alexandria ScenePlan + SP1–SP7 (Day 14–16) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Scene/Beat planning layer (04 附录 B) and its deterministic self-check SP1–SP7, then type `scene_plan` on `CommitRequest` — the planning product Writer consumes in Day 17–19.

**Architecture:** A pure data-model module (`models/sceneplan.py`) mirroring 04 §8.2 field-for-field, plus a read-only validator (`sceneplan.py`) that reuses the existing `Finding`/`ValidationResult`/`_bucket` machinery from the Validator (same bucketing discipline as `validate_contract`/H7). SP5 reachability is a BFS over symmetric `Location.connected_to` (10 W-S1/W-S4). ScenePlan is **not** committed and **not** in the Event Log; orchestrator wiring stays minimal (typed field only) because SP is a pre-Writer gate, run by the Plot layer, not by `CommitOrchestrator`.

**Tech Stack:** Python 3.12+, pydantic v2, pytest; existing `plot_engine` (models.state, validator Finding/ValidationResult/_bucket, canonical).

**Spec:** `alexandria-spec-v0.2/04_contract_protocol.md` §8 (附录 B：§8.2 Schema、§8.3 SP1–SP7、§8.4 接口); reachability per `10_*.md` W-S1/W-S4.

## Global Constraints

- Beat/Scene/ScenePlan 字段、正则、`ge/le`、`min_length/max_length` 逐字对齐 04 §8.2。
- `Scene.beats` 3~7、`ScenePlan.scenes` 3~7、`Scene.seq` 0..6；`beat_id ^bt_\d{6}$`、`scene_id ^scn_\d{4}_\d{2}$`、`plan_id ^sop_\d{8}$`。
- SP 规则等级严格照 04 §8.3：SP1~SP6 HARD、SP7 SOFT。validator 只读、幂等、可序列化。
- SP5 可达 = 角色 `current_location` → `beat.location` 在 `connected_to`（对称）图上存在路径；`action_type=="travel"` 的 beat 豁免；角色 `current_location` 为 None 时无法判定，跳过该角色。
- 一切数值定点整数 ×1000；无 float（05 §5.5）。Chinese docstrings 引协议节；`from __future__ import annotations`；tests 在 `plot_engine/tests/`，`.venv` 下 `python -m pytest`。
- 偏离记录：ScenePlan **生成**（LLM/Arc 派生）不在 Day 14–16（属 Writer/Plot 对接，08 Day 17–19）；本计划用手写金标 fixture 充当派生产物，只落地 schema + 自校验 + 类型接入。`CommitOrchestrator` 不强制跑 SP（SP 是 pre-Writer 闸，非 Commit 闸）。

## Review Focus

1. **SP5 对称可达** —— `connected_to` 只写 A→B 时，从 B 出发的角色也应判定可达 A（W-S1 对称）。→ Task 2，测试反向边可达。
2. **SP1 引用存在性覆盖四类 id** —— char/loc/realm/fact 都要检；漏检任一让坏计划通过。realm 来自 `actor_realm`/`target_realm`，fact 来自 `reader_fact_id`。→ Task 2。
3. **SP2/SP3 是并集语义** —— SP2 跨**所有** scene 的 beat 汇总 `expected_event_types` 对 contract.required_events 全覆盖；SP3 任一 beat 命中 forbidden 即违规，不是整批一致才报。→ Task 2。
4. **SOFT vs HARD 分桶不错位** —— SP7（tension 偏差）落 SOFT，绝不进 hard_violations 阻断；与 SP6 唯一性（HARD）区分。→ Task 3。
5. **类型接入不破坏既有 Commit** —— `scene_plan` 从 `Any=None` 收紧为 `Optional[ScenePlan]=None` 后，现有 orchestrator 全部测试（传 None）仍须绿。→ Task 3。

---

## File Structure

```
plot_engine/
├── models/sceneplan.py    # Beat / Scene / ScenePlan（04 §8.2）              [Task 1]
├── sceneplan.py           # 可达性 BFS + validate_scene_plan（SP1~SP7）      [Task 2]
├── models/commit.py       # scene_plan: Any → Optional[ScenePlan]            [Task 3]
└── tests/
    ├── test_sceneplan_model.py
    ├── test_sceneplan_sp.py
    └── test_sceneplan_golden.py      # 金标计划 e2e + SP 逐条命中 + Commit 回归
```

## Task 1: Beat / Scene / ScenePlan models

**Files:** Create `plot_engine/models/sceneplan.py`; Test `test_sceneplan_model.py`

**Interfaces:** Produces `Beat`/`Scene`/`ScenePlan` (pydantic v2) exactly per 04 §8.2:
- `Beat`: `beat_id`(`^bt_\d{6}$`), `seq`(ge=0), `intent:str`, `beat_type`(Literal setup/pressure/turn/release/foreshadow), `action_type`(Optional Literal combat/dialogue/investigation/travel/ritual/reveal/status_change)=None, `actors`List[str]=[], `actor_realm`/`target_realm`/`location`Optional[str]=None, `expected_event_types`List[str]=[], `reader_target`(Optional Literal learns/hinted/deceived)=None, `reader_fact_id`Optional[str]=None.
- `Scene`: `scene_id`(`^scn_\d{4}_\d{2}$`), `chapter_no:int`, `seq`(0..6), `location`Optional[str]=None, `characters`List[str]=[], `purpose`str="", `tension`(0..1000, def 500), `beats`(3..7).
- `ScenePlan`: `plan_id`(`^sop_\d{8}$`), `chapter_no`, `arc_id`, `contract_version:int`, `scenes`(3..7), `derived_from`List[str]=[], `epoch`, `created_at`, `schema_version:int=2`.

- [x] Tests: 合法最小计划构造成功；`beat_id="bt_1"`→ValidationError；`scene_id="scn_47_1"`→ValidationError；`Scene.beats` 长度 2→ValidationError、8→ValidationError；`ScenePlan.scenes` 长度 2/8→ValidationError；`tension=1001`→ValidationError。
- [x] Commit `feat(plot-engine): Scene/Beat/ScenePlan schema models (04 附录 B §8.2)`

## Task 2: SP1–SP7 self-check + reachability

**Files:** Create `plot_engine/sceneplan.py`; Test `test_sceneplan_sp.py`

**Interfaces:** Consumes `plot_engine.validator`（`Finding`、`ValidationResult`、`_bucket`、`_f`）与 `StoryState`/`ChapterContract`/`ScenePlan`。Produces:
```python
def _reachable(state: StoryState, frm: Optional[str], to: str) -> bool
    # 对称 BFS：边集 = connected_to ∪ 反向边；frm==to 视为可达（路径长 0）；frm None → False
def validate_scene_plan(plan: ScenePlan, contract, state: StoryState) -> ValidationResult
    # SP1~SP7；只读、幂等；Finding.rule_id ∈ {"SP1",...,"SP7"}
```
规则实现：
- SP1：遍历每个 beat 的 `actors`(char)、`location`+每个 `Scene.location`(loc)、`actor_realm`/`target_realm`(realm)、`reader_fact_id`(fact)；不在对应 state 池 → HARD，evidence=坏 id。
- SP2：`covered = ∪ beat.expected_event_types`；对 contract.required_events 每个 event_type 不在 covered → HARD（evidence=event_type）。
- SP3：任一 beat.expected_event_types ∩ forbidden_events 非空 → HARD（evidence=冲突 event_type）。
- SP4：contract.reader_signals 每条 (fact_id, target_state→{knows→learns? }) 需被某 beat 的 (reader_fact_id, reader_target) 覆盖。映射：signal.target_state=="knows"→reader_target"learns"；"hinted"→"hinted"；"decovered"?→"deceived"。未覆盖 → HARD。
- SP5：非 travel beat 且声明 `location`：对每个 scene.characters 中 `current_location` 非 None 者，要求 `_reachable(state, cur, beat.location)`；任一不可达 → HARD（evidence=beat_id）。
- SP6：同章内 `scene_id` 全局唯一、`beat_id` 全局唯一（跨 scene）；重复 → HARD。
- SP7：每个 scene.tension 与 contract.tension_target 偏差 > 300 → SOFT（阈值与 H7.3 一致，05 单源）。

- [x] Tests: 干净计划 → can_commit 且无 hard；SP1 坏 char/坏 fact → hard；SP2 缺 required event_type → hard；SP3 声明 forbidden REVEALS → hard；SP4 未覆盖 reader_signal → hard；SP5 travel 豁免 + 反向边可达（W-S1）+ 不可达 hard；SP6 重复 beat_id → hard；SP7 偏差 → soft 不阻断。
- [x] Commit `feat(plot-engine): SP1–SP7 scene-plan self-check + symmetric reachability (04 附录 B §8.3)`

## Task 3: 类型接入 scene_plan + 金标 e2e + Commit 回归

**Files:** Modify `plot_engine/models/commit.py`（`scene_plan: Optional[ScenePlan] = None`）; Test `test_sceneplan_golden.py`

**Interfaces:** Consumes Task 1/2 + 现有 `CommitOrchestrator`（Day 12-13）。金标：手写在 04 附录 A/Day 4-7 语境内构造一个能通过 SP 的 ch47 ScenePlan（3 scene，覆盖 OBSERVES/INFERS，含 fact_000003 reader learns，位置可达）。

- [x] Tests: (a) 金标 ScenePlan 过 `validate_scene_plan`（hard==[]）；(b) 同一计划注入 SP3/SP4 各一处 → 对应 hard 命中；(c) `CommitRequest(scene_plan=<ScenePlan>)` 与 `scene_plan=None` 都能构造；(d) 复用 Day 12-13 `test_commit_orchestrator` 的金标 e2e 仍 OK（回归：scene_plan 字段收紧不破坏 commit）。
- [x] Commit `feat(plot-engine): typed scene_plan on CommitRequest + golden SP e2e (04 附录 B)`

## Task 4: 全绿 + 回归

- [x] `python -m pytest plot_engine/tests -q` 全绿。
- [x] Commit `test(plot-engine): scene-plan layer regression`

## Out of scope (subsequent plans)

- ScenePlan 生成（Arc/Contract 派生、LLM）与 Writer 逐 Scene 生成、双通道 Extraction（Day 17–19）。
- `CommitOrchestrator` 内强制执行 SP 闸（Phase 0 定为 pre-Writer 闸，由 Plot 层调用）。
- Level-3 语义校验、跨章 ScenePlan 一致性。
