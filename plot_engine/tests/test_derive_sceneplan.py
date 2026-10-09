# Contract → ScenePlan 派生（04 附录 B）：SP2/SP3/SP4 由构造保证，产物过 validate_scene_plan。
# 场景/事件之外的东西（地点、氛围）不编造：地点只在角色位置唯一时继承 State 的事实。
import pytest

from plot_engine.derive import derive_chapter_contract, derive_scene_plan
from plot_engine.models.contract import ArcContract
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState
from plot_engine.sceneplan import validate_scene_plan

EPOCH = "epoch_0"
NOW = "2026-10-09T00:00:00Z"
CAST = "char_000001"


def _arc(gates=(), tps=(), reqs=()) -> ArcContract:
    intent = {"chapter_no": 3, "story_goal": "张三查印章", "story_goal_type": "revelation",
              "ending": {"type": "cliffhanger", "strength": 800, "description": "d"},
              "must_change": [{"character_id": CAST, "field": "knowledge", "operation": "add",
                               "target": "fact_000003", "expected_value": "known"}],
              "required_events": [dict(r) for r in reqs]}
    return ArcContract(arc_id="arc_003", epoch=EPOCH, chapter_range=(1, 10),
                       tension_curve=[600] * 10,
                       turning_points=[{"chapter": 3, "type": "revelation",
                                        "description": "印泥是干的",
                                        "required_event_types": ["OBSERVES", "INFERS"]}],
                       knowledge_gates=[dict(g) for g in gates],
                       reader_beats=[intent], created_at=NOW)


def _state(with_loc: bool = False) -> StoryState:
    char = {"character_id": CAST, "name": "张三", "status": "alive",
            "introduced_at_chapter": 1, "epoch": EPOCH}
    if with_loc:
        char["current_location"] = "loc_000012"
    return StoryState(
        story_id="s1", chapter_no=0, version=0, epoch=EPOCH,
        characters={CAST: Character(**char)},
        locations={"loc_000012": {"location_id": "loc_000012", "name": "藏宝阁",
                                  "introduced_at_chapter": 1, "epoch": EPOCH}},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                         canonical_form="c", narrative_truth="unknown",
                         objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000002", "fact_000003")},
        state_hash="0" * 64)


_RICH_GATES = [{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                 "must_reveal_by_chapter": 2, "reveal_stage_target": "confirmed"},
                {"fact_id": "fact_000003", "allowed_after_chapter": 1,
                 "reveal_stage_target": "hinted"}]


def _derive(arc=None, state=None):
    arc = arc or _arc(gates=_RICH_GATES)
    state = state or _state()
    contract = derive_chapter_contract(arc, 3, state, created_at=NOW)
    return contract, derive_scene_plan(contract, state, created_at=NOW)


# --- 产物合法：SP1~SP7 无 finding -------------------------------------------
def test_derived_plan_is_sp_clean():
    contract, plan = _derive()
    res = validate_scene_plan(plan, contract, _state())
    assert [f.rule_id for f in res.hard_violations] == []
    assert [f.rule_id for f in res.soft_warnings] == []       # tension 逐场景对齐目标


@pytest.mark.parametrize("extra", [0, 1, 5, 12])
def test_plan_stays_within_structural_limits_for_any_load(extra):
    reqs = [{"event_type": "STATES", "description": f"台词 {i}"} for i in range(extra)]
    contract, plan = _derive(_arc(gates=_RICH_GATES, reqs=reqs))
    assert 3 <= len(plan.scenes) <= 7
    assert all(3 <= len(sc.beats) <= 7 for sc in plan.scenes)
    res = validate_scene_plan(plan, contract, _state())
    assert [f.rule_id for f in res.hard_violations] == []


# --- SP2/SP4 的构造性覆盖 ---------------------------------------------------
def test_sp2_every_required_event_type_lands_on_a_beat():
    contract, plan = _derive()
    covered = {et for sc in plan.scenes for b in sc.beats for et in b.expected_event_types}
    assert {r.event_type for r in contract.required_events} <= covered


def test_sp4_every_established_reader_signal_has_a_beat():
    contract, plan = _derive()
    pairs = {(b.reader_target, b.reader_fact_id)
             for sc in plan.scenes for b in sc.beats if b.reader_fact_id}
    assert {("learns", "fact_000001"), ("hinted", "fact_000003")} <= pairs
    assert {s.fact_id for s in contract.reader_signals} == {f for _t, f in pairs}


def test_sp3_never_declares_a_forbidden_event_type():
    arc = _arc(gates=_RICH_GATES,
               reqs=[{"event_type": "SUSPECTS", "description": "怀疑李四"}])
    arc.reader_beats[0]["forbidden_events"] = [
        {"event_type": "LIES", "description": "本章不许撒谎", "reason": "节奏"}]
    contract, plan = _derive(arc)
    declared = {et for sc in plan.scenes for b in sc.beats for et in b.expected_event_types}
    assert declared.isdisjoint({f.event_type for f in contract.forbidden_events})


# --- 引用与标识 -------------------------------------------------------------
def test_beat_ids_unique_and_patterns_hold():
    _contract, plan = _derive()
    ids = [b.beat_id for sc in plan.scenes for b in sc.beats]
    assert len(ids) == len(set(ids))
    assert all(sc.scene_id.startswith(f"scn_{plan.chapter_no:04d}_") for sc in plan.scenes)


def test_plan_stamps_contract_version_and_epoch():
    contract, plan = _derive()
    assert (plan.plan_id, plan.chapter_no, plan.arc_id) == ("sop_00000003", 3, "arc_003")
    assert plan.contract_version == contract.version
    assert plan.epoch == EPOCH


def test_scene_location_only_when_state_is_unanimous():
    contract, known = _derive(state=_state(with_loc=True))
    assert {sc.location for sc in known.scenes} == {"loc_000012"}
    _c2, unknown = _derive(state=_state())
    assert {sc.location for sc in unknown.scenes} == {None}


def test_scene_characters_cover_their_beats_and_exist_in_state():
    contract, plan = _derive(state=_state(with_loc=True))
    for sc in plan.scenes:
        actors = {a for b in sc.beats for a in b.actors}
        assert actors <= set(sc.characters)
        assert set(sc.characters) <= {"char_000001"}


def test_derivation_is_deterministic():
    arc = _arc(gates=_RICH_GATES, reqs=[{"event_type": "STATES", "description": "台词"}])
    state = _state(with_loc=True)
    c1 = derive_chapter_contract(arc, 3, state, created_at=NOW)
    p1 = derive_scene_plan(c1, state, created_at=NOW)
    p2 = derive_scene_plan(derive_chapter_contract(arc, 3, state, created_at=NOW),
                           state, created_at=NOW)
    assert p1.model_dump() == p2.model_dump()
