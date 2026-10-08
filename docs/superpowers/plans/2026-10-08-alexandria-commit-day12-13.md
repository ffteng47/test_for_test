# Alexandria Commit Orchestration (Day 12–13) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the 07 §5–§7 four-stage Commit pipeline on top of the finished Day 4–7 state layer (store / eventlog / replay) and Day 8–11 Validator: Validate → Reduce+consistency → Persist(CAS) → post-Commit Replay parity, with idempotent key, CONFLICT handling, and §7.5 rollback-on-inconsistency.

**Architecture:** A thin `CommitOrchestrator` that composes existing pure pieces. Stage 1 calls `Validator.validate` (read-only). Stage 2 re-runs the deterministic sandbox reduce (`reduce_commit`) to obtain the *persisted* `new_state` + `applied_events`, then runs `assert_consistent` over them. Stage 3 calls `StateStore.persist` (WAL+CAS+commit_log idempotency, already built). After OK, Stage 3 calls `verify_parity`; mismatch → revert (delete the just-written state version + its commit_log row, mark events orphan) and return `REPLAY_INCONSISTENT`. No new storage engine; SQLite primitives already exist.

**Tech Stack:** Python 3.12+, pydantic v2, pytest; existing `plot_engine` packages (store, eventlog, replay, reducer, consistency, canonical, validator, models).

**Spec:** `alexandria-spec-v0.2/07_commit_protocol.md` (§4.1 request, §5 stages, §6 reduce, §7 persist+replay, §8 idempotency, §9 rollback, §11 trace, §12 invariants).

## Global Constraints

- HARD violations non-empty → FAIL, never enter Stage 2 (07 §5.3 R1).
- Reduce按 (chapter, seq) 拓扑序，与 Validator 沙盒同一驱动（replay.apply_events）。
- CAS：信封 version 列比对 expected_version；不匹配 → CONFLICT，上层重试（07 §7.2/§10.1 T2）。
- 幂等键 (story_id, chapter_no, proposal_set_hash)：命中 → DUPLICATE，返回缓存不重写（07 §8 R1/R2）。
- §7.5：每次 Commit 成功后自动增量 Replay；hash 不符 → 回滚本次 version、Event Log 标 orphan 不删除、落 REPLAY_INCONSISTENT、停 pipeline。
- I9：被隔离（H8.2）/ 抽取失败（MALFORMED_PROPOSAL）的 Proposal 永不进 Event Log —— 即只 append `sim.applied`。
- I7：Commit 不改写已提交章节的 Event（本计划只追加新章）。
- 定点整数 ×1000；无 float（05 §5.5）。Chinese docstrings 引协议节；`from __future__ import annotations`；tests 在 `plot_engine/tests/`，`.venv` 下 `python -m pytest`。
- 偏离记录：07 §4.1 CommitRequest 无 proposals 字段（Stage 0 抽取在 Day 17–19 才落）；本计划 `commit()` 接收 `proposals` 形参，`scene_plan` 暂缺省（Day 14–16）。在代码注释标注为 documented deviation。

## Review Focus

1. **Stage 2 与 Stage 1 必须同一条 reduce 路径** —— 若 Stage 2 单独实现 reduce，会与 Validator 沙盒漂移。→ 复用 `_simulate`/`apply_events`，测试断言 `new_state.state_hash == 沙盒 sim.cur.state_hash`。
2. **Replay 不一致必须回滚且不留脏状态** —— version 指针回退、events 标 orphan、commit_log 行删除；回滚后 `load_latest` 仍是旧 version、`read_chapter(非 orphan)` 为空。→ Task 3。
3. **CAS 冲突与幂等重复是两条不同分支** —— CONFLICT（version 不符，可重试）vs DUPLICATE（幂等键命中，返回缓存）。→ Task 4。
4. **空章提交**：Phase 0 约定被校验章节至少 1 事件；0 applied events 的提交 → FAIL（H5.1 会拦，但需 orchestrator 对空批明确拒绝，不写空 version）。→ Task 4。
5. **HARD=0 但 consistency 有 hard finding** —— assert_consistent 的 hard 必须同样阻断 Commit（I6 一切 HARD 为 0）。→ Task 2。

---

## File Structure

```
plot_engine/
├── models/commit.py         # 07 §4.1 CommitRequest + §11.1 CommitTrace + Outcome  [Task 1]
├── reduce.py                # reduce_commit：单条 reduce 驱动（复用 validator 内部件）  [Task 2]
├── store.py                 # + delete_state_version / delete_commit_log（回滚原语）      [Task 3]
├── commit.py                # CommitOrchestrator：四阶段管道 + parity 回滚                 [Task 4]
└── tests/
    ├── test_commit_model.py
    ├── test_reduce_commit.py
    ├── test_store_rollback.py
    └── test_commit_orchestrator.py    # e2e: genesis→commit→parity→DUPLICATE→CONFLICT→FAIL
```

## Task 1: CommitRequest / CommitTrace / CommitOutcome models

**Files:** Create `plot_engine/models/commit.py`; Test `test_commit_model.py`

**Interfaces:** Produces:
```python
class CommitRequest(BaseModel):   # 07 §4.1 verbatim（scene_plan 可选）
    story_id: str; chapter_no: int; draft: str
    contract: "ChapterContract"; scene_plan: Optional[Any] = None
    expected_version: int; trace_id: str

CommitStatus = Literal["OK","FAIL","CONFLICT","DUPLICATE","IO_ERROR","REPLAY_INCONSISTENT"]

class CommitTrace(BaseModel):     # 07 §11.1（Phase 0 计时字段填 0）
    trace_id: str; story_id: str; chapter_no: int
    stage_0_ms: int = 0; stage_1_ms: int = 0; stage_2_ms: int = 0; stage_3_ms: int = 0
    replay_check_ms: int = 0
    result: CommitStatus
    hard_violations: int; soft_warnings: int; observations: int
    quarantined_proposals: int
    version_before: int; version_after: Optional[int]
    epoch: str; schema_version: int = 2; timestamp: str = ""

class CommitOutcome(BaseModel):
    status: CommitStatus
    new_version: Optional[int] = None
    current_version: Optional[int] = None
    message: str = ""
    trace: CommitTrace
    validation: Optional["ValidationResult"] = None
```

- [x] Tests: CommitRequest 允许 scene_plan=None；CommitStatus 六个值都合法、第七值 ValidationError；CommitTrace result="OK" 构造；CommitOutcome.ok helper? 不加，保持薄。
- [x] Commit `feat(plot-engine): commit request/trace/outcome models (07 §4.1/§11.1)`

## Task 2: reduce_commit — 单一 reduce 驱动 + 一致性闸

**Files:** Create `plot_engine/reduce.py`; Test `test_reduce_commit.py`

**Interfaces:** Consumes validator internals (`parse_markup`, `markup_to_proposals`, `_h8_gate`, `_merge_markup`, `_simulate`)、`Reducer`、`apply_events`、`assert_consistent`、`ValidationResult`。Produces:
```python
@dataclass
class ReducedBatch:
    new_state: Optional[StoryState]   # None → 不可提交
    applied: List[Event]
    validation: ValidationResult
    quarantined: int                  # H8.2 隔离数
    consistency: List[dict]           # assert_consistent 输出（新章事件子集）
    def committable(self) -> bool     # validation.can_commit() and no hard consistency
def reduce_commit(state, proposals, contract, draft, epoch,
                  *, committed_event_ids=frozenset(), validator=None) -> ReducedBatch
```
Stage 1 verdict 由 `Validator.validate` 提供（authoritative ValidationResult）；随后同一 merge/simulate 产出 `new_state=sim.cur`、`applied=sim.applied`（只含成功施加者，天然排除 H8.2/MALFORMED，I9）。对 `new_state` + `applied` 跑 `assert_consistent`，任何 severity==hard 也阻断（Review Focus #5）。

- [x] Tests: 干净批 → committable、new_state hash 与直接 `apply_events` 逐字节相等（Review Focus #1）；dead actor 批 → 不可提交；H8.2 隔离批 → quarantined==1 且 applied 不含被隔离者；consistency hard（如 ledger 引不存在 source）→ 不可提交。
- [x] Commit `feat(plot-engine): reduce_commit single reduce driver + consistency gate (07 §6)`

## Task 3: Store rollback primitives

**Files:** Modify `plot_engine/store.py`（+ `eventlog` 已具 mark_orphan）; Test `test_store_rollback.py`

**Interfaces:** Produces on `StateStore`:
```python
def delete_state_version(self, story_id: str, version: int) -> None   # 删本次 states 行
def delete_commit_log(self, story_id: str, chapter_no: int, proposal_set_hash: str) -> None
def revert_commit(self, story_id, version, chapter_no, proposal_set_hash, event_log) -> None
    # 组合：delete_state_version + delete_commit_log + event_log.mark_orphan(chapter)
```
仅用于 §7.5 R6 parity 失败回滚；不改写历史其它 version（I7）。

- [x] Tests: persist→revert→load_latest 回到旧 version；revert 后 read_chapter(非 orphan) 为空而含 orphan 可见；revert 后同幂等键可再次 persist（commit_log 已清）。
- [x] Commit `feat(plot-engine): store revert primitives for replay-parity rollback (07 §7.5 R6, §9)`

## Task 4: CommitOrchestrator 四阶段管道

**Files:** Create `plot_engine/commit.py`; Test `test_commit_orchestrator.py`

**Interfaces:** Consumes `Validator`, `reduce_commit`, `StateStore`, `EventLog`, `Reducer`, `verify_parity`, `proposal_set_hash`。Produces:
```python
class CommitOrchestrator:
    def __init__(self, store, log, reducer, validator=None): ...
    def commit(self, request: CommitRequest, proposals: List[EventProposal], arc_state,
               *, committed_event_ids=frozenset()) -> CommitOutcome
        # Stage1: reduce_commit → validation; 非 committable → FAIL outcome（无写副作用）
        #         空 applied → FAIL（Review Focus #4）
        # psh = proposal_set_hash([canonical bytes of applied events])  # 幂等键内容=实际提交事件
        # Stage3: store.persist(...) → OK/CONFLICT/DUPLICATE
        #       CONFLICT → outcome CONFLICT；DUPLICATE → outcome DUPLICATE（缓存版本）
        # §7.5: verify_parity → 失败则 revert_commit + outcome REPLAY_INCONSISTENT
        # 全程产 CommitTrace
```
`arc_state` 即当前 `StoryState`（从 store.load_latest 取，或调用方传入）。`expected_version` 来自 request。

- [x] Tests (e2e, tmp_path sqlite):
  (a) genesis + 附录A 章47 → OK、load_latest.version==1、verify_parity True；
  (b) 重复同 proposals → DUPLICATE、version 不变；
  (c) expected_version 错 → CONFLICT、未写新 version；
  (d) dead-actor 批 → FAIL、store 无新 version、eventlog 空（无副作用）；
  (e) 幂等键按 applied 事件算：同 draft 不同抽取顺序 → 同 psh。
- [x] Commit `feat(plot-engine): four-stage commit orchestrator + replay rollback (07 §5–§9)`

## Task 5: 全绿 + 回归

- [x] `python -m pytest plot_engine/tests -q` 全绿。
- [x] 金标章47 e2e 跑通：CommitTrace.result=="OK"，`verify_parity` 真。
- [x] Commit `test(plot-engine): commit pipeline regression`

## Out of scope (subsequent plans)

- Stage 0 extraction 双通道与 LLM 置信度真实生成（Day 17–19）。
- ScenePlan 生成与 SP1~SP7（Day 14–16）；`scene_plan` 形参此阶段留空。
- Revision/重试循环（06）与 CONTRACT_INVALID 升级（07 §10.3）。
- Level-3 LLM-as-validator（只产 SOFT/OBSERVATION）。
