# 06 §3/§4 Root Cause 归因：rule_id → 层级；§4.0 extraction 优先级最高
from plot_engine.models.revision import RevisionPolicy
from plot_engine.revision import action_for, classify_root_cause
from plot_engine.validator import Finding, ValidationResult


def _res(*rules: str) -> ValidationResult:
    return ValidationResult(hard_violations=[
        Finding(rule_id=r, severity="hard", message=f"{r} 命中") for r in rules])


def test_extraction_is_highest_priority_per_06_4_0():
    rc = classify_root_cause(_res("H1.1", "H8.1"))
    assert rc.level == "extraction" and rc.violated_rule_id == "H8.1"


def test_replay_inconsistency_is_state_layer():
    assert classify_root_cause(_res("REPLAY_INCONSISTENT")).level == "state"


def test_contract_self_check_is_contract_layer():
    assert classify_root_cause(_res("H7.4")).level == "contract"
    assert classify_root_cause(_res("H7.1")).level == "contract"


def test_unsatisfiable_required_event_is_contract_layer():
    # 08 §6：「Contract 无法满足」→ Contract/Arc 问题；R5 禁止用重写正文弥补
    assert classify_root_cause(_res("H5.1")).level == "contract"


def test_text_side_rules_map_to_writer():
    for r in ("H1.1", "H2.1", "H3.1", "H4.1", "H5.2", "H5.7"):
        assert classify_root_cause(_res(r)).level == "writer", r


def test_h53_is_a_contract_failure_not_a_rewrite():
    """06 §4.2：must_change 无实现事件（W1）＝契约要一个本章兑现不了的 Δ。
    归 writer 会让阶梯先烧满重写预算，而重写一百遍也变不出一条不存在的 Δ。"""
    rc = classify_root_cause(_res("H5.3"))
    assert rc.level == "contract" and rc.confidence == 1000


def test_event_taxonomy_rules_map_to_event_layer():
    for r in ("H6.1", "H6.3"):
        assert classify_root_cause(_res(r)).level == "event", r


def test_fact_ontology_rules_map_to_fact_layer():
    for r in ("I1", "R7"):
        assert classify_root_cause(_res(r)).level == "fact", r


def test_unmapped_rule_defaults_to_writer_with_low_confidence():
    rc = classify_root_cause(_res("H9.9"))
    assert rc.level == "writer" and rc.confidence == 500


def test_no_hard_violation_yields_no_root_cause():
    assert classify_root_cause(ValidationResult()) is None


def test_level_selects_action_within_policy_ladder():
    p = RevisionPolicy()
    assert action_for("extraction", p) == "rerun_extraction"
    assert action_for("writer", p) == "rewrite_scene"
    assert action_for("contract", p) == "renegotiate_contract"
    assert action_for("arc", p) == "escalate_to_arc"


def test_non_auto_fixable_layers_have_no_action():
    p = RevisionPolicy()
    # 06 §4.4/§4.5 走 epoch 升级、§4.6 即改协议 → 一律人工，绝不自动重写
    for level in ("fact", "event", "validator"):
        assert action_for(level, p) is None, level
