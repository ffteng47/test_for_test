# validate_contract H7 族（04 §5.1 V1–V10 + §4.4 兼容矩阵）
from plot_engine.models.contract import ArcContract, ChapterContract
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState
from plot_engine.validator import _run_contract

EPOCH = "epoch_0"


def _arc():
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(40, 60),
        tension_curve=[720] * 21,
        turning_points=[{"chapter": 47, "type": "revelation",
                         "description": "d", "required_event_types": ["OBSERVES", "INFERS"]}],
        knowledge_gates=[{"fact_id": "fact_000002", "allowed_after_chapter": 84,
                          "reveal_stage_target": "confirmed"}],
        created_at="2026-10-08T00:00:00Z")


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", introduced_at_chapter=1, epoch=EPOCH)},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
                defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000002", "fact_000003")},
        state_hash="0" * 64)


def _golden():
    return ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, version=1,
        story_goal="张三发现伪造印章，推断存在叛徒", story_goal_type="revelation",
        must_change=[
            {"character_id": "char_000001", "field": "knowledge", "operation": "add",
             "target": "fact_000003", "expected_value": "known"},
            {"character_id": "char_000001", "field": "knowledge", "operation": "add",
             "target": "fact_000001", "expected_value": "suspected"}],
        must_not_change=[{"character_id": "char_000001", "field": "knowledge",
             "operation": "update", "target": "fact_000002"}],
        required_events=[
            {"event_type": "OBSERVES", "description": "观察", "minimum_count": 1,
             "actors_involved": ["char_000001"], "must_be_visible_to_reader": True},
            {"event_type": "INFERS", "description": "推断", "minimum_count": 1,
             "actors_involved": ["char_000001"], "must_be_visible_to_reader": True}],
        forbidden_events=[{"event_type": "REVEALS", "description": "揭示", "reason": "gate"}],
        knowledge_allowed=["fact_000001", "fact_000003"], knowledge_forbidden=["fact_000002"],
        reader_signals=[{"fact_id": "fact_000003", "target_state": "knows",
                         "established_in_scene": "scn_0047_01"}],
        plot_progress={"main_thread": 80}, tension_target=720,
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        derived_from=["arc_003.knowledge_gates[fact_000002]", "arc_003.turning_points[47]"],
        created_at="2026-10-08T10:00:00Z")


def _codes(f):
    return {x.rule_id for x in f}


def _run(**over):
    dumped = _golden().model_dump()
    dumped.update(over)
    c = ChapterContract(**dumped)
    return _run_contract(c, _arc(), _state())


def test_golden_clean():
    assert _run_contract(_golden(), _arc(), _state()) == []


def test_h7_1_empty_goal():
    assert "H7.1" in _codes(_run(story_goal=""))


def test_h7_1_bad_schema_version():
    assert "H7.1" in _codes(_run(schema_version=1))


def test_h7_2_chapter_out_of_range():
    assert "H7.2" in _codes(_run(chapter_no=70))


def test_h7_2_arc_mismatch():
    assert "H7.2" in _codes(_run(arc_id="arc_009"))


def test_h7_3_tension_deviation_soft():
    arc = _arc().model_copy(update={"tension_curve": [200] * 21})
    f = [x for x in _run_contract(_golden(), arc, _state()) if x.rule_id == "H7.3"]
    assert f and f[0].severity == "soft"


def test_h7_4_allowed_forbidden_overlap():
    assert "H7.4" in _codes(_run(knowledge_allowed=["fact_000002"], knowledge_forbidden=["fact_000002"]))


def test_h7_5_required_forbidden_conflict():
    assert "H7.5" in _codes(_run(forbidden_events=[
        {"event_type": "OBSERVES", "description": "x", "reason": "r"}]))


def test_h7_6_must_conflict_same_target():
    assert "H7.6" in _codes(_run(must_not_change=[
        {"character_id": "char_000001", "field": "knowledge",
         "operation": "update", "target": "fact_000003"}]))


def test_h7_7_incompatible_ending():
    assert "H7.7" in _codes(_run(story_goal_type="setup"))  # setup → question/arrival, not cliffhanger


def test_h7_8_derived_missing():
    assert "H7.8" in _codes(_run(derived_from=["arc_003.knowledge_gates[fact_999999]"]))


def test_h7_10_unknown_reference():
    assert "H7.10" in _codes(_run(knowledge_allowed=["fact_000001", "fact_000003", "fact_888888"]))


def test_h7_11_empty_target():
    assert "H7.11" in _codes(_run(must_change=[
        {"character_id": "char_000001", "field": "knowledge", "operation": "add", "target": ""}]))


def test_contract_idempotent():
    c = _golden()
    r1 = [x.model_dump() for x in _run_contract(c, _arc(), _state())]
    r2 = [x.model_dump() for x in _run_contract(c, _arc(), _state())]
    assert r1 == r2
