# 06 §4.2 Contract Error → 重议 Chapter Contract：重新派生 + version+1，**不重写 Draft**。
# 这里的红线是：重议只能放宽**作者自订**的要求。由 Arc 派生的要求（D3 turning_point、
# D6 逾期 gate）一旦被「放宽」，就等于把实验的通过标准改成模型刚好能达到的样子——
# 那正是 Phase-0 报告第 3 节两次假通过的失败模式。
import dataclasses
import pytest

from plot_engine.derive import ArcConflict, derive_chapter_contract
from plot_engine.models.contract import ArcContract, ChapterHook
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState
from plot_engine.models.revision import RevisionPolicy
from plot_engine.revision import ChapterContext, RevisionLoop
from plot_engine.revision_actions import renegotiate_contract
from plot_engine.validator import Finding, ValidationResult

EPOCH = "epoch_0"
NOW = "2026-10-09T00:00:00Z"
CAST = "char_000001"


def _arc(authored=("INFERS",), tp_types=("OBSERVES",),
         must_reveal: int | None = 2) -> ArcContract:
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(1, 10), tension_curve=[600] * 10,
        turning_points=([{"chapter": 3, "type": "revelation", "description": "印泥是干的",
                          "required_event_types": list(tp_types)}] if tp_types else []),
        knowledge_gates=[{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                         "must_reveal_by_chapter": must_reveal,
                         "reveal_stage_target": "confirmed"}],
        reader_beats=[{"chapter_no": 3, "story_goal": "张三查印章",
                       "story_goal_type": "revelation",
                       "ending": {"type": "cliffhanger", "strength": 800, "description": "d"},
                       "must_change": [{"character_id": CAST, "field": "knowledge",
                                        "operation": "add", "target": "fact_000003",
                                        "expected_value": "known"}],
                       "required_events": [{"event_type": t, "description": f"{t} 一次"}
                                           for t in authored]}],
        created_at=NOW)


def _state() -> StoryState:
    return StoryState(
        story_id="s1", chapter_no=0, version=0, epoch=EPOCH,
        characters={CAST: Character(character_id=CAST, name="张三", status="alive",
                                    introduced_at_chapter=1, epoch=EPOCH)},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                         canonical_form="c", narrative_truth="unknown",
                         objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000003")},
        state_hash="0" * 64)


def _ctx(arc, unsatisfied=()):
    c = derive_chapter_contract(arc, 3, _state(), created_at=NOW)
    return ChapterContext(contract=c, scene_plan=None, draft="张三凝视印章。",
                          state=_state(), unsatisfied_event_types=list(unsatisfied))


# --- 放宽的边界 -------------------------------------------------------------
def test_renegotiation_drops_only_the_authored_requirement_that_missed():
    arc = _arc()
    ctx = _ctx(arc, unsatisfied=["INFERS"])
    out = renegotiate_contract(arc, created_at=NOW)(ctx)
    types = {e.event_type for e in out.contract.required_events}
    assert "INFERS" not in types
    assert {"OBSERVES", "REVEALS"} <= types          # D3 + D6 派生的仍在外
    assert out.draft == ctx.draft                    # 06 §4.2：不重写 Draft


def test_unsatisfiable_arc_mandated_requirement_fails_fast():
    """批次 4：落空的正好是 Arc 强制项 ⇒ 重议一条也放宽不了，再派生一次只会产出同一份
    被同一规则拒掉的契约。静默重议等于把 Arc 层缺陷伪装成「重议通过」，
    还顺手烧掉剩下的修订预算（06 §4.3：Arc Error → 回 Arc 层）。"""
    arc = _arc()
    ctx = _ctx(arc, unsatisfied=["OBSERVES"])         # D3 拐点要求 OBSERVES，本章给不出
    with pytest.raises(ArcConflict):
        renegotiate_contract(arc, created_at=NOW)(ctx)


def test_version_bumps_and_provenance_survives():
    arc = _arc()
    out = renegotiate_contract(arc, created_at=NOW)(_ctx(arc, ["INFERS"]))
    assert out.contract.version == 2                          # 04 I3/I4
    assert f"arc_003.turning_points[3]" in out.contract.derived_from


def test_renegotiating_a_contract_with_nothing_left_to_drop_is_a_no_op_on_requirements():
    arc = _arc()
    once = renegotiate_contract(arc, created_at=NOW)(_ctx(arc, ["INFERS"]))
    twice = renegotiate_contract(arc, created_at=NOW)(
        dataclasses.replace(once, unsatisfied_event_types=["INFERS"]))
    assert ({e.event_type for e in once.contract.required_events}
            == {e.event_type for e in twice.contract.required_events})
    assert twice.contract.version == 3                        # 仍记版本，不改判据


def test_arc_conflict_is_not_swallowed_by_renegotiation():
    from plot_engine.derive import ArcConflict
    arc = _arc()
    ctx = _ctx(arc, ["INFERS"])                       # 先拿到合法契约
    arc.reader_beats[0]["forbidden_events"] = [        # 再让 Arc 自相矛盾
        {"event_type": "REVEALS", "description": "别说破", "reason": "悬念"}]
    with pytest.raises(ArcConflict):
        renegotiate_contract(arc, created_at=NOW)(ctx)


# --- 下限规则（backlog #9：「靠删掉要求而通过」）------------------------------
def _self_imposed_arc(authored=("INFERS",)) -> ArcContract:
    """本章要求**全部**是作者自订的（没有 D3 拐点、gate 也没逾期）⇒ 一次重议就能把
    required_events 删空，而空契约让 H5.1 永真——「通过」变成删判据的奖品。"""
    return _arc(authored=authored, tp_types=(), must_reveal=None)


def test_renegotiation_refuses_to_empty_the_criteria():
    arc = _self_imposed_arc()
    ctx = _ctx(arc, ["INFERS"])
    out = renegotiate_contract(arc, created_at=NOW)(ctx)
    assert out is ctx                                   # 原样返回：不假装重议过
    assert out.contract.version == 1
    assert {e.event_type for e in out.contract.required_events} == {"INFERS"}


def test_refusing_to_empty_still_allows_partial_relaxation():
    """下限只管「删空」这一种，放宽一条留一条照旧生效——否则这条规则会把 06 §4.2
    授权的动作整个废掉。"""
    arc = _self_imposed_arc(authored=("INFERS", "OBSERVES"))
    out = renegotiate_contract(arc, created_at=NOW)(_ctx(arc, ["INFERS"]))
    assert out.contract.version == 2
    assert {e.event_type for e in out.contract.required_events} == {"OBSERVES"}


def test_refused_renegotiation_ends_as_needs_human_not_an_emptied_commit():
    """被拒绝的重议必须把章交给人，而不是悄悄换出一份没要求的契约再提交一次。"""
    arc = _self_imposed_arc()
    bad = _outcome("FAIL", ValidationResult(hard_violations=[_finding("H5.1", "INFERS")]))
    seen = []

    def recommit(ctx):
        seen.append(ctx.contract.version)
        assert ctx.contract.required_events             # 每一轮进 commit 的判据都非空
        return bad

    loop = RevisionLoop(policy=RevisionPolicy(),
                        actions={"renegotiate_contract": renegotiate_contract(arc, created_at=NOW)})
    trace, out = loop.run_chapter("s1", 3, _ctx(arc, []), recommit)
    assert seen == [1, 1]                               # 第二次重议没产出 version 2 的空契约
    assert out.status == "FAIL" and trace.needs_human is True
    assert trace.final_status == "NEEDS_HUMAN"


# --- 调度：契约层失败现在真的会进第二轮 -------------------------------------
def _finding(rule_id, evidence):
    return Finding(rule_id=rule_id, severity="hard", message=rule_id,
                   location=None, evidence=evidence, suggestion=None)


from plot_engine.models.commit import CommitOutcome, CommitTrace


def _outcome(status, validation=None):
    trace = CommitTrace(trace_id="t", story_id="s1", chapter_no=3, result=status,
                        hard_violations=len(validation.hard_violations) if validation else 0,
                        soft_warnings=0, observations=0, quarantined_proposals=0,
                        version_before=0, version_after=None, epoch=EPOCH)
    return CommitOutcome(status=status, new_version=1 if status == "OK" else None,
                         current_version=0, message=status, trace=trace,
                         validation=validation)


def test_contract_layer_failure_now_reenters_the_loop():
    """回归 08 §8 E3：以前 contract 层缺动作 → 0 轮直接 NEEDS_HUMAN，修订率量不出来。"""
    arc = _arc()
    bad = _outcome("FAIL", ValidationResult(hard_violations=[_finding("H5.1", "INFERS")]))
    ok = _outcome("OK")

    seen = []

    def recommit(ctx):
        seen.append(ctx.contract.version)
        return bad if "INFERS" in {e.event_type for e in ctx.contract.required_events} else ok

    loop = RevisionLoop(policy=RevisionPolicy(),
                        actions={"renegotiate_contract": renegotiate_contract(arc, created_at=NOW)})
    trace, out = loop.run_chapter("s1", 3, _ctx(arc, []), recommit)
    assert out.status == "OK" and trace.final_status == "OK"
    assert trace.rounds == 1 and seen == [1, 2]


def test_unsatisfied_types_reach_the_action_from_h51_evidence():
    """H5.1 的 evidence 是事件类型（结构化），不靠解析中文消息。"""
    arc = _arc()
    captured = []

    def spy(ctx):
        captured.append(ctx.unsatisfied_event_types)
        return renegotiate_contract(arc, created_at=NOW)(ctx)

    bad = _outcome("FAIL", ValidationResult(hard_violations=[
        _finding("H5.1", "INFERS"), _finding("H5.3", "knowledge")]))
    loop = RevisionLoop(policy=RevisionPolicy(), actions={"renegotiate_contract": spy})
    loop.run_chapter("s1", 3, _ctx(arc, []), lambda ctx: bad)
    assert captured[0] == ["INFERS"]
