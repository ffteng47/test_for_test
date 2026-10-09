# Alexandria 10-Chapter Experiment Harness (Day 20–22) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase-0 experiment harness (08 §2–§4, §8): a network-free `run_experiment` driver that walks N chapters through the already-built Writer→Stage-0→Validator→Commit pipeline, aggregates the `ExperimentReport` hard metrics, computes replay consistency, and evaluates the §8 exit conditions.

**Architecture:** The real LLM Writer/extraction and the Arc→Contract→ScenePlan *generator* are NOT Phase-0 scope (Auto-Mode #6: no network, injected seams). The harness consumes **injected** per-chapter artifacts (`ChapterArtifacts = (contract, scene_plan, draft, rule_channel, llm_channel)`) from a `chapter_source: Callable[[int, StoryState], ChapterArtifacts]`, runs them through `CommitOrchestrator`, and classifies every failure into the §4 hard-metric buckets via a rule→category map. Revision loop (06) is not yet built, so `revision_*` report fields are recorded as not-run (E3 = N/A), while E1/E2/E4/E5/E6 are computed from first-round outcomes.

**Tech Stack:** Python 3.12+, pydantic v2, pytest; existing `plot_engine` (writer, extract, validator, commit, store, eventlog, replay, consistency, models).

**Spec:** `08_experiment_protocol.md` §2 (config), §3 (report), §4 (hard metrics), §6 (failure classification), §8 (exit conditions); `07_commit_protocol.md` §5–§9; `06_revision_protocol.md` §4.0 (attribution).

## Global Constraints

- 网络无关：`chapter_source`、`rule_channel`、`llm_channel`、`scene_writer` 全为注入 `Callable`；Phase 0 绝不发网络请求或读密钥（Auto-Mode #6）。真实模型/生成器由实验期或后续 Phase 接入。
- 实验期不得改协议/HARD 规则（08 I1/I2）；本计划只读消费已有规则结果，绝不新增 HARD 判定。
- 硬指标计数全部来自既有产物：ValidationResult.hard_violations（rule_id）、consistency findings、replay parity；分类器只做**映射与计数**，不改判据。
- 定点整数×1000；tokens/cost Phase 0 恒为 0（无真实模型）；计时字段填 0（07 §11.1）。
- Chinese docstrings 引协议节；`from __future__ import annotations`；tests 在 `plot_engine/tests/`，`.venv` 下 `python -m pytest`。
- 偏离记录：E3'（≤3 轮 Revision 后成功率≥90%）需 06 Revision 循环，Phase 0 未落地 → 报告 `revision_rounds={}`、`revision_success_rate=0.0`、`unresolved_chapters=首轮未 commit 章`；harness 明确标注 E3 为 N/A，其余 E1/E2/E4/E5/E6 计算。

## Review Focus

1. **分类器 rule_id→bucket 全覆盖** —— §4 九项硬指标各有对应来源（H2.1/H5.7→knowledge/leak；H3.x→timeline；H1.1→dead；H1.2/H4.1→item；H5.1→required；H1.1/H2.4/H1.4→impossible；replay→replay）。漏映射会让某类 failure 静默不入桶、虚假达成"0"。→ T2。
2. **未 commit 章绝不计入 committed / replay 一致性分母** —— FAIL/CONFLICT/REPLAY_INCONSISTENT 章不推进 store；replay sweep 只对已提交章。错计会虚高 E2/E5。→ T3。
3. **replay 不一致单独归"架构阻断"，不与普通 HARD 混桶** —— REPLAY_INCONSISTENT → E6 阻断 + `replay_mismatch_chapters`，绝不因单样本改判据（08 §7）。→ T3。
4. **注入通道冲突章必须落到 H8.2/H5.1，而非 harness 直接判 FAIL 绕过管道** —— harness 只调 orchestrator.commit，不自行判定有效性。→ T4。
5. **Report 幂等可序列化** —— 同一 `chapter_source` 跑两次 → canonical_json(report) 相等（dict 计数需确定性排序）。→ T1/T3。

---

## File Structure

```
plot_engine/
├── models/experiment.py  # ExperimentConfig + ExperimentReport + 硬指标桶常量 + rule→category 图   [Task 1]
├── classify.py           # classify_outcome：ValidationResult/consistency/replay → §4 桶计数        [Task 2]
├── experiment.py         # run_experiment 驱动 + evaluate_exit_conditions（08 §8 E1/E2/E4/E5/E6）   [Task 3]
└── tests/
    ├── fixtures/experiment_10ch.py   # 确定性 chapter_source（脚本化 OBSERVES/INFERS/…）
    └── test_experiment_e2e.py        # 10 章跑通 + 指标 + 退出条件
```

## Task 1: Experiment 配置/报告模型 + 硬指标映射

**Files:** Create `plot_engine/models/experiment.py`; Test `test_experiment_model.py`

**Interfaces:** Consumes `ArcContract`、`StoryState`、`ChapterContract`、`ScenePlan`. Produces:
```python
@dataclass class ChapterArtifacts: contract; scene_plan; draft; rule_channel; llm_channel
HardMetric = Enum(  CANON, KNOWLEDGE, TIMELINE, IMPOSSIBLE_ACTION, DEAD_REAPPEAR,
                    ITEM_UNAVAILABLE, FORBIDDEN_LEAK, REQUIRED_EVENT_MISSING, REPLAY )
RULE_TO_METRIC: Dict[str, HardMetric]   # H2.1/H5.7→KNOWLEDGE；H3.1/H3.2/H3.3/H3.4→TIMELINE；
    # H1.1→DEAD_REAPPEAR；H1.2/H4.1/H4.2→ITEM_UNAVAILABLE；H2.1 knowledge_forbidden→FORBIDDEN_LEAK；
    # H5.1→REQUIRED_EVENT_MISSING；H1.3/H1.4/H2.4→IMPOSSIBLE_ACTION；REPLAY_INCONSISTENT→REPLAY
class ExperimentConfig(BaseModel): story_id; chapters=10; arc_contract; initial_state; seed; epoch; model_router_config={}
class ExperimentReport(BaseModel):  # 08 §3 verbatim 字段
    experiment_id; config; chapters_generated; chapters_committed
    hard_violations: Dict[str,int]; soft_warnings: Dict[str,int]; observations: Dict[str,int]
    canon_contradictions; knowledge_contradictions; timeline_contradictions: int
    replay_consistency: bool; replay_mismatch_chapters: List[int]
    revision_rounds: Dict[int,int]; revision_success_rate: float; unresolved_chapters: List[int]
    total_tokens; total_cost_usd; total_duration_ms: int = 0; timestamp: str
```
- [ ] Tests: 报告字段默认与类型齐备；`RULE_TO_METRIC` 覆盖 §4 九项、每项至少一 rule_id；`ChapterArtifacts` 是普通 dataclass；Config 默认 chapters=10、model_router_config={}。
- [ ] Commit `feat(plot-engine): experiment config/report models + hard-metric map (08 §2/§3/§4)`

## Task 2: 硬指标分类器

**Files:** Create `plot_engine/classify.py`; Test `test_classify_metrics.py`

**Interfaces:** Consumes `CommitOutcome`（含 validation/trace）、consistency findings（`assert_consistent`）、`RULE_TO_METRIC`。Produces:
```python
@dataclass class MetricCounts: by_metric: Dict[HardMetric,int]; by_rule: Dict[str,int]
def classify_outcome(outcome, *, consistency: List[dict], replay_ok: Optional[bool]=None) -> MetricCounts
    # hard rule_id → by_rule[rule_id]++ 且 by_metric[RULE_TO_METRIC[id]]++（未知 id 归 CANON 兜底并计 by_rule）
    # replay_ok is False → by_metric[REPLAY]++
def to_report_fields(mc: MetricCounts) -> dict   # canon/knowledge/timeline 计数 + hard_violations dict
```
- [ ] Tests: 一条 H2.1+一条 H5.1 → knowledge 1 / required_missing 1；REPLAY_INCONSISTENT+replay_ok False → REPLAY 命中；未知 rule "H9.9" 归 CANON 兜底且 by_rule 仍记；soft/observation 不进硬指标桶。
- [ ] Commit `feat(plot-engine): hard-metric classifier → §4 buckets (08 §4/§6)`

## Task 3: run_experiment 驱动 + 退出条件闸门

**Files:** Create `plot_engine/experiment.py`; Test `test_experiment_run.py`

**Interfaces:** Consumes `ExperimentConfig`、`CommitOrchestrator`、`compose_chapter_draft`、`stage0_extract`、`verify_parity`、`classify_outcome`、`assert_consistent`. Produces:
```python
ChapterSource = Callable[[int, StoryState], ChapterArtifacts]
def run_experiment(config, *, store, log, chapter_source, scene_writer,
                  reducer=None, validator=None) -> ExperimentReport
    # for ch in 1..N：cur=store.load_latest；art=chapter_source(ch,cur)
    #   draft=compose(...) or art.draft；props=stage0_extract(...)
    #   out=orch.commit(CommitRequest(...expected_version=cur version...), props, cur)
    #   计 chapters_generated++；out.status=="OK"→chapters_committed++
    #   consistency=assert_consistent(...)；classify_outcome→累加 MetricCounts
    #   REPLAY_INCONSISTENT→记入 replay_mismatch_chapters（架构阻断）
    # 末尾 replay sweep：对每个已提交章 verify_parity，任一 False→replay_consistency False
    # revision_* 置 0/{}/N/A；unresolved=未 commit 章号；组装 ExperimentReport
def evaluate_exit_conditions(report) -> Dict[str, Optional[bool]]  # E1/E2/E4/E5/E6 计算，E3=None(N/A)
```
- [ ] Tests: 注入恒成功 `chapter_source`（脚本 OBSERVES+INFERS）跑 3 章→ generated=committed=3、replay_consistency True、E1 True；注入第 2 章产 dead-actor→该章 FAIL、committed=2、unresolved=[2]、DEAD_REAPPEAR 命中、E2=2/3；同配置跑两次 report canonical 相等。
- [ ] Commit `feat(plot-engine): run_experiment driver + Phase-0 exit-condition gate (08 §5/§8)`

## Task 4: 脚本化 10 章 e2e + 回归

**Files:** Create `plot_engine/tests/fixtures/experiment_10ch.py`; Test `test_experiment_e2e.py`
- [ ] Tests: `chapter_source` 生成 10 章合法 OBSERVES/INFERS（逐章推进 knowledge），`run_experiment`→ `chapters_generated==10`；纯合法批次 `chapters_committed==10`、`replay_consistency True`、`evaluate_exit_conditions` E1/E2/E5/E6 True、E4 True（无规则占比>40%）、E3 None。再跑一条含 1 章 forbidden-leak + 1 章 replay-break 的场景，断言对应桶>0、`replay_mismatch_chapters` 命中、E6 False。
- [ ] `python -m pytest plot_engine/tests -q` 全绿。
- [ ] Commit `test(plot-engine): 10-chapter experiment e2e + exit-condition regression`

## Out of scope (subsequent plans)

- Arc→Contract→ScenePlan 自动**生成器**与真实 Writer/LLM 模型接入（实验期注入，08 Day 20–22 之后）。
- 06 Revision 循环（E3' 依赖）与 RootCause 自动归因闭环。
- Day 23–25 Architecture Review（人工，基于本报告）。
