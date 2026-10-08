from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.reducers.belief import reduce_belief


def _st():
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0", state_hash="")


def _ev(typ, payload, seq=0, conf=1000):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor="char_000001", chapter=47, seq=seq, payload=payload, confidence=conf)


def test_believes_sets_strength():
    out = reduce_belief(_ev("BELIEVES", {"fact_id": "fact_000002", "belief_strength": 700}), _st())
    e = out.belief_ledger[0]
    assert e.belief_state == "believes" and e.strength == 700 and e.is_true is None


def test_states_updates_audience_not_speaker():
    out = reduce_belief(_ev("STATES", {"audience": ["char_000009"], "fact_id": "fact_000001"}), _st())
    assert {b.character_id for b in out.belief_ledger} == {"char_000009"}


def test_hints_sets_suspects():
    out = reduce_belief(_ev("HINTS", {"audience": ["char_000009"], "fact_id": "fact_000001"}), _st())
    assert out.belief_ledger[0].belief_state == "suspects"


def test_doubts_downgrades_believes():
    s = reduce_belief(_ev("BELIEVES", {"fact_id": "fact_000002", "belief_strength": 800}), _st())
    out = reduce_belief(_ev("DOUBTS", {"fact_id": "fact_000002"}, seq=1), s)
    assert out.belief_ledger[0].belief_state == "doubts"


def test_suspects_does_not_downgrade_believes():
    s = reduce_belief(_ev("BELIEVES", {"fact_id": "fact_000002", "belief_strength": 800}), _st())
    out = reduce_belief(_ev("SUSPECTS", {"fact_id": "fact_000002"}, seq=1), s)
    assert out.belief_ledger[0].belief_state == "believes"


def test_lies_audience_believes_stated_fact_speaker_unchanged():
    out = reduce_belief(_ev("LIES", {"audience": ["char_000009"],
                                      "stated_fact_id": "fact_000003",
                                      "actual_belief_id": "fact_000002"}), _st())
    assert {b.character_id for b in out.belief_ledger} == {"char_000009"}
    assert out.belief_ledger[0].fact_id == "fact_000003"


def test_omits_is_noop_on_ledger():
    s = reduce_belief(_ev("BELIEVES", {"fact_id": "fact_000002", "belief_strength": 800}), _st())
    out = reduce_belief(_ev("OMITS", {"audience": ["char_000009"], "fact_id": "fact_000002"}, seq=1), s)
    assert out.belief_ledger == s.belief_ledger
