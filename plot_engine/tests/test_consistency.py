from plot_engine.models.state import StoryState
from plot_engine.models.entity import Character, Relationship
from plot_engine.models.fact import Fact
from plot_engine.models.event import Event
from plot_engine.consistency import assert_consistent


def _codes(state, events=()):
    return {f["code"] for f in assert_consistent(state, list(events))}


def _ev(typ, payload, actor="char_000001", chapter=1, seq=0):
    return Event(event_id=f"evt_{chapter:08d}_{seq:03d}", epoch="epoch_0",
                 event_type=typ, actor=actor, chapter=chapter, seq=seq, payload=payload)


def test_overdraw_detected_from_events():
    # model floors stored quantity at 0, so over-draw is judged from events (H4.1)
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0", state_hash="")
    acq = _ev("ITEM_ACQUIRED", {"character_id": "char_000001", "item_id": "item_000001", "quantity": 1})
    con = _ev("ITEM_CONSUMED", {"character_id": "char_000001", "item_id": "item_000001", "quantity": 5}, seq=1)
    assert "H4.1" in _codes(s, [acq, con])


def test_dead_actor_is_hard():
    c = Character(character_id="char_000001", name="x", status="dead",
                  death_chapter=10, introduced_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=12, version=1, epoch="epoch_0",
                   characters={"char_000001": c}, state_hash="")
    e = _ev("OBSERVES", {"fact_id": "fact_000001", "method": "sight"}, chapter=12)
    assert "I7" in _codes(s, [e])


def test_clean_state_no_findings():
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0", state_hash="")
    assert assert_consistent(s, []) == []


def test_unresolved_location_is_I3():
    c = Character(character_id="char_000001", name="x", status="alive",
                  current_location="loc_000099", introduced_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0",
                   characters={"char_000001": c}, state_hash="")
    assert "I3" in _codes(s)


def test_relationship_dangling_endpoint_is_I6():
    c = Character(character_id="char_000001", name="x", status="alive",
                  introduced_at_chapter=1, epoch="epoch_0")
    rel = Relationship(relationship_id="rel_000001", from_character="char_000001",
                       to_character="char_000002", type="friend",
                       established_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0",
                   characters={"char_000001": c}, relationships=[rel], state_hash="")
    assert "I6" in _codes(s)


def test_reveal_stage_confirmed_with_split_truth_is_R7():
    f = Fact(fact_id="fact_000001", fact_type="identity", proposition="甲是叛徒",
             canonical_form="traitor(a)", narrative_truth="true", objective_truth="false",
             reveal_stage="confirmed", defined_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0",
                   facts={"fact_000001": f}, state_hash="")
    assert "R7" in _codes(s)


def test_contradicted_unknown_is_observation():
    f = Fact(fact_id="fact_000001", fact_type="identity", proposition="p",
             canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
             defined_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0",
                   facts={"fact_000001": f}, state_hash="")
    ev = _ev("FACT_CONTRADICTED", {"fact_id": "fact_000001", "contradicting_fact_id": "fact_000001"})
    findings = assert_consistent(s, [ev])
    assert "FACT_CONTRADICTED_UNKNOWN" in {x["code"] for x in findings}
    assert all(x["severity"] != "hard" for x in findings
               if x["code"] == "FACT_CONTRADICTED_UNKNOWN")


def test_findings_sorted_hard_first():
    c = Character(character_id="char_000001", name="x", status="dead",
                  death_chapter=1, introduced_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0",
                   characters={"char_000001": c}, state_hash="")
    ev = _ev("FACT_CONTRADICTED", {"fact_id": "fact_000001", "contradicting_fact_id": "fact_000001"})
    findings = assert_consistent(s, [ev])
    ords = [x["ord"] for x in findings]
    assert ords == sorted(ords)


def test_checker_does_not_mutate_state():
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0", state_hash="")
    before = s.model_dump()
    assert_consistent(s, [_ev("OBSERVES", {"fact_id": "fact_000009", "method": "sight"})])
    assert s.model_dump() == before
