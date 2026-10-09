# Commit 请求/追踪/结果模型（07 §4.1 / §11.1）
import pytest
from pydantic import ValidationError

from plot_engine.models.commit import (
    CommitOutcome,
    CommitRequest,
    CommitStatus,
    CommitTrace,
)
from plot_engine.models.contract import ChapterContract
from plot_engine.validator import Finding, ValidationResult


def _contract():
    return ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch="epoch_0",
        story_goal="查明叛徒", story_goal_type="revelation",
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-08T00:00:00Z")


def _trace(result="OK", **over):
    base = dict(trace_id="t1", story_id="s1", chapter_no=47, result=result,
                hard_violations=0, soft_warnings=0, observations=0,
                quarantined_proposals=0, version_before=0, version_after=1,
                epoch="epoch_0")
    return CommitTrace(**{**base, **over})


def test_request_scene_plan_optional_none():
    req = CommitRequest(story_id="s1", chapter_no=47, draft="正文",
                        contract=_contract(), expected_version=0, trace_id="t1")
    assert req.scene_plan is None


def test_request_scene_plan_rejects_non_sceneplan():
    with pytest.raises(ValidationError):
        CommitRequest(story_id="s1", chapter_no=47, draft="正文",
                      contract=_contract(), scene_plan={"scenes": []},
                      expected_version=0, trace_id="t1")


def test_status_accepts_all_six_literals():
    for value in ("OK", "FAIL", "CONFLICT", "DUPLICATE", "IO_ERROR",
                  "REPLAY_INCONSISTENT"):
        _trace(result=value, version_after=None if value != "OK" else 1)


def test_status_rejects_seventh_value():
    with pytest.raises(ValidationError):
        _trace(result="MAYBE")


def test_trace_timing_defaults_zero():
    tr = _trace()
    assert tr.stage_0_ms == 0 == tr.stage_3_ms
    assert tr.replay_check_ms == 0
    assert tr.schema_version == 2
    assert tr.timestamp == ""


def test_trace_result_field_is_commit_status():
    assert _trace(result="CONFLICT").result == "CONFLICT"


def test_outcome_requires_trace_and_defaults():
    out = CommitOutcome(status="OK", trace=_trace())
    assert out.new_version is None
    assert out.current_version is None
    assert out.message == ""
    assert out.validation is None


def test_outcome_carries_validation_result():
    res = ValidationResult(hard_violations=[
        Finding(rule_id="H1.1", severity="hard", message="x")])
    out = CommitOutcome(status="FAIL", trace=_trace(result="FAIL", version_after=None),
                        validation=res)
    assert out.validation.can_commit() is False
