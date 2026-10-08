"""Knowledge reducer 测试（03 §4.3/§5.4，定点整数路径）。"""
from __future__ import annotations

from plot_engine.models.event import Event
from plot_engine.models.fact import Fact
from plot_engine.models.ledger import KnowledgeEntry
from plot_engine.models.state import StoryState
from plot_engine.reducers.knowledge import reduce_knowledge


def _state_with_facts(fact_ids):
    facts = {fid: Fact(fact_id=fid, fact_type="event", proposition="p",
                       canonical_form=f"p({fid})", narrative_truth="true",
                       objective_truth="true", defined_at_chapter=47, epoch="epoch_0")
             for fid in fact_ids}
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0",
                      facts=facts, state_hash="")


def _ev(typ, payload, seq=0, conf=1000):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor="char_000001",
                 target=payload.get("fact_id") or payload.get("conclusion_fact_id"),
                 chapter=47, seq=seq, payload=payload, confidence=conf)


def _kn(state, fid):
    return [k for k in state.knowledge_ledger if k.fact_id == fid][0]


def test_observes_sets_known_900():
    s = _state_with_facts(["fact_000003"])
    out = reduce_knowledge(_ev("OBSERVES", {"fact_id": "fact_000003", "method": "sight"}), s)
    e = _kn(out, "fact_000003")
    assert e.knowledge_state == "known" and e.strength == 900


def test_infers_floor_division_is_integer():
    s = _state_with_facts(["fact_000001", "fact_000003"])
    s.knowledge_ledger.append(KnowledgeEntry(
        character_id="char_000001", fact_id="fact_000003", knowledge_state="known",
        strength=1000, source_event_id="evt_00000047_000",
        acquired_at_chapter=47, last_updated_chapter=47, epoch="epoch_0"))
    out = reduce_knowledge(_ev("INFERS", {
        "conclusion_fact_id": "fact_000001", "evidence_fact_ids": ["fact_000003"]},
        seq=1, conf=700), s)
    concl = _kn(out, "fact_000001")
    assert concl.knowledge_state == "suspected" and concl.strength == 700


def test_fact_contradicted_downgrades_x04():
    s = _state_with_facts(["fact_000001", "fact_000002"])
    s.knowledge_ledger.append(KnowledgeEntry(
        character_id="char_000001", fact_id="fact_000001", knowledge_state="known",
        strength=1000, source_event_id="evt_00000047_000",
        acquired_at_chapter=47, last_updated_chapter=47, epoch="epoch_0"))
    out = reduce_knowledge(_ev("FACT_CONTRADICTED", {
        "fact_id": "fact_000001", "contradicting_fact_id": "fact_000002"}, seq=2), s)
    d = _kn(out, "fact_000001")
    assert d.knowledge_state == "suspected" and d.strength == 400  # 1000 * 4 // 10
