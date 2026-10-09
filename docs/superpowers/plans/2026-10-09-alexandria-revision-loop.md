# Alexandria Revision Loop (06) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 06 修订协议——把 `CommitOrchestrator` 返回的 FAIL 变成「按 Root Cause 分层回退、带轮次预算与振荡检测、每轮落 trace」的收敛循环，使 08 §8 E3'（≤3 轮 Revision 后 Commit 成功率 ≥90%）从 `N/A` 变为可实测。

**Architecture:** 三个只依赖既有产物的单元：(1) `classify_root_cause(ValidationResult) -> RootCause`——06 §3 八层 + §4.0–§4.7 判据的静态 rule_id→level 映射；(2) `RevisionLoop`——06 §5 `RevisionPolicy` 与 §6 七步流程，回退动作全是注入的 `Callable`（Phase 0 网络无关，Auto-Mode #6），缺动作即转人工；(3) `RevisionTrace`——06 R6「过程必须记录」。`run_experiment` 增加可选 `revision_loop` 参数，不传即维持首轮单跑语义（既有测试零改动）。

**Tech Stack:** Python 3.12+, pydantic v2, pytest；复用 `plot_engine.validator.ValidationResult`、`plot_engine.commit.CommitOrchestrator`、`plot_engine.writer.compose_chapter_draft`、`plot_engine.extract.stage0_extract`、`plot_engine.models.commit.CommitRequest`。

**Spec:** `06_revision_protocol.md` §2（R1–R6）、§3（RootCause）、§4.0–§4.7（回退层级映射）、§5（RevisionPolicy）、§6（流程）、§7（振荡检测）；`08_experiment_protocol.md` §3（revision_* 字段）、§8（E3'）。

## Global Constraints

- 网络无关、无密钥：`rerun_extraction / rewrite_scene / rewrite_chapter / renegotiate_contract / escalate_to_arc` 全为注入 `Callable`，默认 `None` → 该层级不可自动执行 → 记 `needs_human=True`（Auto-Mode #6）。
- 不得修改协议或 HARD 判据（08 I1/I2）；本模块只**归因与调度**，绝不自写 Validator 规则、绝不放宽阈值。
- `fact / event / validator` 三层不可自动修（06 §4.4/§4.5 需 epoch 升级、§4.6 即改协议）→ 一律直接人工升级，不进阶梯。
- `state` 层（06 §4.7）→ 立即停 pipeline + 回滚到最近一致快照，不重写文本。
- 定点整数 ×1000：`RootCause.confidence` 为 int；`cost_ceiling_per_chapter_usd` 沿用 06 §5 verbatim 的 float（模型层字段，永不进 canonical 序列化路径）。
- 振荡判据按**集合**比较（§7：{A,B} 与 {B,A} 视为相同集合），非按顺序。
- Chinese docstrings 引协议节；`from __future__ import annotations`；tests 在 `plot_engine/tests/`，`.venv` 下 `python -m pytest`。

## Review Focus

1. **Contract 错误绝不被重写正文弥补**（06 R5）——`H5.1`/`H7.*` 必须走 `renegotiate_contract`，任何把 contract 层路由到 `rewrite_scene` 的映射都是隐性烧 token。→ T2。
2. **轮次预算必须真能停**（06 R3/R4）——`round ≥ max_rounds` 升级层级、`总轮数 ≥ human_escalation_threshold` 转人工，不得出现无限循环。→ T3。
3. **振荡必须早停**（06 §7）——连续两轮 violation 集合相同 → 立刻升级下一层级，不烧完预算。→ T3。
4. **每轮都要留 trace，包括失败轮**（06 R6 / 08 I3）——未 commit 章的轮次同样落 `RevisionTrace`，否则真实模型跑完拿不到归因数据。→ T4。
5. **不传 revision_loop 时零行为变化** —— `run_experiment` 旧调用路径的 committed/unresolved/E3 语义必须逐字不变。→ T5。

---

### Task 1: `models/revision.py` — RootCause / RevisionPolicy / RevisionTrace

**Files:**
- Create: `plot_engine/models/revision.py`
- Test: `plot_engine/tests/test_revision_model.py`

**Interfaces:**
- Consumes: pydantic `BaseModel`
- Produces:
  - `RootCauseLevel = Literal["extraction","writer","contract","arc","fact","event","validator","state"]`
  - `RootCause(level: RootCauseLevel, evidence: str, violated_rule_id: Optional[str] = None, confidence: int = 1000)`
  - `RevisionPolicy(max_rounds: int = 3, escalation: List[str] = ["rerun_extraction","rewrite_scene","rewrite_chapter","renegotiate_contract","escalate_to_arc"], oscillation_detection: bool = True, cost_ceiling_per_chapter_usd: float = 0.5, human_escalation_threshold: int = 3)`
  - `RevisionStep(round_no: int, root_cause: RootCause, action: str, violations: List[str], committed: bool)`
  - `RevisionTrace(story_id: str, chapter_no: int, steps: List[RevisionStep] = [], final_status: str = "FAIL", rounds: int = 0, needs_human: bool = False, halt: bool = False)`

- [x] **Step 1:** 写失败测试：06 §3/§5 verbatim 默认值（`policy.max_rounds == 3`、`policy.escalation[0] == "rerun_extraction"`、`RootCause.confidence` 拒绝 float 输入）。
- [x] **Step 2:** 运行确认失败。
- [x] **Step 3:** 实现模型。
- [x] **Step 4:** 运行确认通过。
- [x] **Step 5:** 提交。

### Task 2: `classify_root_cause` — rule_id → 八层归因（06 §3/§4）

**Files:**
- Create: `plot_engine/revision.py`
- Test: `plot_engine/tests/test_revision_classify.py`

**Interfaces:**
- Consumes: `ValidationResult`（`hard_violations`）
- Produces: `classify_root_cause(validation: ValidationResult) -> RootCause`（取第一条 HARD，extraction 层优先级最高——§4.0）；`ROOT_CAUSE_TO_ACTION: Dict[RootCauseLevel, str]`

- [x] **Step 1:** 写失败测试：H8.1→extraction；H1.1/H5.2/H5.3→writer；H5.1/H7.4→contract；H6.1/H6.3→event；I1/R7→fact；空 HARD→`level="validator"` 且 `confidence=0`（无违规即无可归因，交调用方判定）。
- [x] **Step 2 → Step 5:** 同上节奏；映射表 verbatim 依 §4.0–§4.7 症状行。

### Task 3: `RevisionLoop` — 阶梯、预算、振荡、人工闸

**Files:**
- Modify: `plot_engine/revision.py`
- Test: `plot_engine/tests/test_revision_loop.py`

**Interfaces:**
- Consumes: `RevisionPolicy`、`RootCause`、`action_for(level, policy)`
- Produces: `RevisionLoop(*, rerun_extraction=None, rewrite_scene=None, rewrite_chapter=None, renegotiate_contract=None, escalate_to_arc=None, policy: RevisionPolicy = RevisionPolicy())`；`next_action(level, attempted: List[str], policy) -> Optional[str]`；`is_oscillating(prev: Set[str], cur: Set[str]) -> bool`

- [x] **Step 1:** 写失败测试：contract 层归因不会选中 `rewrite_scene`（R5）；未注入动作 → `None` → `needs_human`；振荡 → 跳级；总轮数触顶 → `needs_human` 且循环终止。
- [x] **Step 2 → Step 5:** 同上节奏。

### Task 4: `run_chapter` — 06 §6 七步流程 + `RevisionTrace`

**Files:**
- Modify: `plot_engine/revision.py`
- Test: `plot_engine/tests/test_revision_run.py`

**Interfaces:**
- Consumes: `CommitOrchestrator.commit`、Task 2/3 产物、注入的 `recommit(attempts) -> CommitOutcome`
- Produces: `RevisionLoop.run_chapter(...) -> RevisionTrace`（每轮一步，含失败轮；`halt=True` 表 §4.7 state 层停线）

- [x] **Step 1:** 写失败测试：首轮 FAIL（extraction）→ 重抽后成功 → `rounds==1, committed`；三轮皆 FAIL → `needs_human=True, rounds==3`；state 层 → `halt=True` 且不再跑第二轮。
- [x] **Step 2 → Step 5:** 同上节奏；`REPLAY_INCONSISTENT` 直接走 §4.7 停机路径。

### Task 5: 接入 `run_experiment` + E3' 实测

**Files:**
- Modify: `plot_engine/experiment.py`、`plot_engine/classify.py`
- Test: `plot_engine/tests/test_experiment_revision.py`

**Interfaces:**
- Consumes: `run_experiment(..., revision_loop=None)`
- Produces: 传 loop 时填 `revision_rounds: Dict[int,int]` / `revision_success_rate` / `unresolved_chapters`（≤3 轮后仍未 commit 的章）；`evaluate_exit_conditions` 的 `E3` 由 `None` 改为 `(commit 后成功率 ≥0.90) and (每章轮数 ≤ policy.max_rounds)`

- [x] **Step 1:** 写失败测试：不传 loop → 行为与旧版逐字一致（`revision_rounds == {}`、`E3 is None`）；传「第二次必成」的 loop → 10 章全 commit、`E3 True`；传「永不成功」的 loop → `unresolved_chapters == [1..10]`、`E3 False`。
- [x] **Step 2 → Step 5:** 同上节奏。

---

## Self-Review

- 覆盖：06 R1–R6、§3 八层、§4.0–§4.7、§5 五字段、§6 七步、§7 振荡 → 全部有对应 task 与测试；08 E3' 由 `None` 变可测。
- 边界：无网络、无凭证、不改 HARD；真实模型跑仍属用户授权项。
- 全量测试：`python -m pytest plot_engine/tests -q` → 272 passed。
