# 06 §3/§5 修订层数据契约：默认值 verbatim 于协议 + confidence 定点整数（05 §5.5）
import pytest

from plot_engine.models.revision import (
    RootCause, RevisionPolicy, RevisionStep, RevisionTrace,
)


def test_policy_defaults_are_verbatim_from_06_s5():
    p = RevisionPolicy()
    assert p.max_rounds == 3
    assert p.escalation == ["rerun_extraction", "rewrite_scene", "rewrite_chapter",
                            "renegotiate_contract", "escalate_to_arc"]
    assert p.oscillation_detection is True
    assert p.cost_ceiling_per_chapter_usd == 0.5
    assert p.human_escalation_threshold == 3


def test_root_cause_confidence_is_fixed_point_int():
    rc = RootCause(level="extraction", evidence="H8.1 置信度 400", violated_rule_id="H8.1")
    assert rc.confidence == 1000 and isinstance(rc.confidence, int)
    with pytest.raises(Exception):
        RootCause(level="writer", evidence="x", confidence=750.5)      # 禁止 float


def test_trace_defaults_to_failed_zero_rounds():
    t = RevisionTrace(story_id="s1", chapter_no=3)
    assert t.steps == [] and t.rounds == 0
    assert t.final_status == "FAIL"
    assert t.needs_human is False and t.halt is False


def test_step_records_the_action_that_was_taken():
    step = RevisionStep(round_no=1,
                        root_cause=RootCause(level="contract", evidence="H5.1 无法满足",
                                             violated_rule_id="H5.1"),
                        action="renegotiate_contract", violations=["H5.1"], committed=False)
    assert step.root_cause.level == "contract"
    assert step.action == "renegotiate_contract" and step.committed is False
