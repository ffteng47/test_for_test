from plot_engine.store import StateStore
from plot_engine.eventlog import EventLog
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.models.fact import Fact
from plot_engine.reducer import Reducer
from plot_engine.replay import apply_events, replay_to_chapter, verify_parity


def _fact(fid):
    return Fact(fact_id=fid, fact_type="event", proposition="p",
                canonical_form=f"p({fid})", narrative_truth="true", objective_truth="true",
                defined_at_chapter=1, epoch="epoch_0")


def _genesis():
    return StoryState(story_id="s1", chapter_no=0, version=0, epoch="epoch_0",
                      facts={"fact_000003": _fact("fact_000003")}, state_hash="")


def _ev(chapter=1, seq=0):
    return Event(event_id=f"evt_{chapter:08d}_{seq:03d}", epoch="epoch_0", event_type="OBSERVES",
                 actor="char_000001", chapter=chapter, seq=seq,
                 payload={"fact_id": "fact_000003", "method": "sight"})


def _setup(tmp_path):
    store, log, red = StateStore(str(tmp_path / "s.db")), EventLog(str(tmp_path / "e.db")), Reducer()
    store.init_genesis("s1", _genesis())
    return store, log, red


def _commit_chapter(store, log, red, state, chapter, events, expected_version):
    reduced = apply_events(state, events, red)   # 与 replay 同一条驱动路径
    res = store.persist("s1", reduced, expected_version,
                        proposal_set_hash=f"h{chapter}", event_log=log, events=events)
    assert res.status == "OK"
    return reduced


def test_replay_hash_equals_persisted_hash(tmp_path):
    store, log, red = _setup(tmp_path)
    _commit_chapter(store, log, red, _genesis(), 1, [_ev()], 0)
    replayed = replay_to_chapter(store, log, red, "s1", 1)
    assert replayed.state_hash == store.load_latest("s1").state_hash


def test_verify_parity_true(tmp_path):
    store, log, red = _setup(tmp_path)
    _commit_chapter(store, log, red, _genesis(), 1, [_ev()], 0)
    assert verify_parity(store, log, red, "s1", 1) is True


def test_mid_stream_snapshot_replay_parity(tmp_path):
    # Review Focus #4：从流中间快照（第5章）起重放，哈希仍与在线一致
    store, log, red = _setup(tmp_path)
    state = _genesis()
    for ch in range(1, 7):
        state = _commit_chapter(store, log, red, state, ch, [_ev(chapter=ch)], ch - 1)
    snap = store.load_snapshot_at_or_before("s1", 6)
    assert snap is not None and snap.chapter_no == 5   # 第5章快照确实用作重放基线
    assert verify_parity(store, log, red, "s1", 6) is True


def test_orphan_events_excluded_from_replay(tmp_path):
    store, log, red = _setup(tmp_path)
    _commit_chapter(store, log, red, _genesis(), 1, [_ev()], 0)
    log.mark_orphan("s1", 1)
    replayed = replay_to_chapter(store, log, red, "s1", 1)
    assert replayed.state_hash == store.load_snapshot_at_or_before("s1", 1).state_hash
