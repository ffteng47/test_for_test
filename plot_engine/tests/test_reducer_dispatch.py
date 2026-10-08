from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.reducers.reader import reduce_reader
from plot_engine.reducer import Reducer


def _st():
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0", state_hash="")


def _ev(typ, payload, seq=0, conf=1000):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor="char_000001", chapter=47, seq=seq, payload=payload, confidence=conf)


def test_reader_hinted_does_not_downgrade_knows():
    s = _st()
    s = reduce_reader(_ev("READER_LEARNS", {"fact_id": "fact_000003", "strength": 900}), s)
    s = reduce_reader(_ev("READER_HINTED", {"fact_id": "fact_000003"}, seq=1), s)
    r = [x for x in s.reader_ledger if x.fact_id == "fact_000003"][0]
    assert r.reader_state == "knows"


def test_reader_learns_takes_max_strength():
    s = reduce_reader(_ev("READER_LEARNS", {"fact_id": "fact_000003", "strength": 600}), _st())
    s = reduce_reader(_ev("READER_LEARNS", {"fact_id": "fact_000003", "strength": 850}, seq=1), s)
    assert s.reader_ledger[0].reader_strength == 850


def test_reader_deceived_sets_deceived():
    out = reduce_reader(_ev("READER_DECEIVED", {"fact_id": "fact_000001"}), _st())
    assert out.reader_ledger[0].reader_state == "deceived"


def test_dispatch_routes_observes_to_knowledge_ledger():
    out = Reducer().apply(_ev("OBSERVES", {"fact_id": "fact_000003", "method": "sight"}), _st())
    assert len(out.knowledge_ledger) == 1


def test_dispatch_routes_foreshadowing_as_noop_restamp():
    s = _st()
    out = Reducer().apply(_ev("FORESHADOWING_SET", {"fact_id": "fact_000003"}), s)
    assert out.model_dump(exclude={"state_hash"}) == s.model_dump(exclude={"state_hash"})


def test_dispatch_table_covers_all_26_types():
    from typing import get_args
    from plot_engine.models.event import EventType
    from plot_engine.reducer import _DISPATCH
    assert set(_DISPATCH.keys()) == set(get_args(EventType))
