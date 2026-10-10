# 硬指标分类器：CommitOutcome/consistency/replay → §4 桶（08 §4/§6）
from plot_engine.classify import classify_outcome, consistency_counts, to_report_fields
from plot_engine.models.commit import CommitOutcome, CommitTrace
from plot_engine.models.experiment import HardMetric
from plot_engine.validator import Finding, ValidationResult

EPOCH = "epoch_0"


def _trace(status="OK") -> CommitTrace:
    return CommitTrace(trace_id="t", story_id="s1", chapter_no=1, result=status,
                       hard_violations=0, soft_warnings=0, observations=0,
                       quarantined_proposals=0, version_before=0, version_after=1,
                       epoch=EPOCH)


def _outcome(status="OK", *, hard=(), soft=(), obs=()) -> CommitOutcome:
    val = ValidationResult(
        hard_violations=[Finding(rule_id=r, severity="hard", message="m") for r in hard],
        soft_warnings=[Finding(rule_id=r, severity="soft", message="m") for r in soft],
        observations=[Finding(rule_id=r, severity="observation", message="m") for r in obs])
    return CommitOutcome(status=status, trace=_trace(status), validation=val)


def test_hard_rules_bucketed():
    mc = classify_outcome(_outcome("FAIL", hard=["H2.1", "H5.1"]))
    assert mc.by_rule["H2.1"] == 1 and mc.by_rule["H5.1"] == 1
    assert mc.by_metric[HardMetric.FORBIDDEN_LEAK] == 1
    assert mc.by_metric[HardMetric.REQUIRED_EVENT_MISSING] == 1
    assert mc.by_metric[HardMetric.DEAD_REAPPEAR] == 0


def test_unknown_rule_falls_back_to_canon_but_still_counted():
    mc = classify_outcome(_outcome("FAIL", hard=["H9.9"]))
    assert mc.by_rule["H9.9"] == 1
    assert mc.by_metric[HardMetric.CANON] == 1


def test_consistency_hard_findings_counted():
    consistency = [{"code": "I9", "ord": 0, "severity": "hard", "detail": "x"},
                   {"code": "R7", "ord": 0, "severity": "hard", "detail": "y"},
                   {"code": "FACT_CONTRADICTED_UNKNOWN", "ord": 2, "severity": "observation",
                    "detail": "z"}]
    mc = classify_outcome(_outcome("OK"), consistency=consistency)
    assert mc.by_metric[HardMetric.KNOWLEDGE] == 1        # I9
    assert mc.by_metric[HardMetric.CANON] == 1            # R7
    assert "FACT_CONTRADICTED_UNKNOWN" not in mc.by_rule  # observation 不进硬桶


def test_replay_failure_hits_replay_bucket():
    mc = classify_outcome(_outcome("REPLAY_INCONSISTENT"), replay_ok=False)
    assert mc.by_metric[HardMetric.REPLAY] >= 1


def test_soft_and_observation_do_not_enter_hard_buckets():
    mc = classify_outcome(_outcome("OK", soft=["H7.3"], obs=["MARKUP_DEDUPE"]))
    assert sum(mc.by_metric.values()) == 0
    assert mc.by_rule == {}


def test_to_report_fields_shape():
    mc = classify_outcome(_outcome("FAIL", hard=["H3.3", "I9"]))
    fields = to_report_fields(mc)
    assert fields["timeline_contradictions"] == 1     # H3.3
    assert fields["knowledge_contradictions"] == 1    # I9
    assert fields["canon_contradictions"] == 0
    assert fields["hard_violations"]["H3.3"] == 1


def test_consistency_counts_does_not_swallow_unmapped_codes():
    """批次 4：classify_outcome 的口径是「未知 code 兜底进 CANON，但绝不静默丢弃」，
    §4 三项命名指标用的是另一条路径（consistency_counts），它以前只认映射表里的三个桶 ⇒
    I2/I6/FACT_CONTRADICTED_UNKNOWN 进了 committed 状态就被看不见，§8 E6 因缺席而判过。"""
    assert consistency_counts([
        {"code": "I2", "severity": "hard"},        # 未映射 → canon
        {"code": "I9", "severity": "hard"},        # knowledge
        {"code": "H3.1", "severity": "hard"},      # timeline
        {"code": "I1", "severity": "soft"},        # 非 hard 不计数
    ]) == {"canon": 1, "knowledge": 1, "timeline": 1}
