# StateStore 回滚原语（07 §7.5 R6 / §9，Review Focus #2/#3）
import json
from pathlib import Path

from plot_engine.canonical import proposal_set_hash
from plot_engine.eventlog import EventLog
from plot_engine.models.event import Event
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.replay import apply_events
from plot_engine.store import StateStore

_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))


def _setup(tmp_path):
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    store.init_genesis("s1", genesis)
    events = [Event(**e) for e in _FIX["chapter47_events"]]
    state = apply_events(genesis, events, Reducer())
    psh = proposal_set_hash([e.model_dump(mode="json") for e in events])
    return store, log, genesis, events, state, psh


def test_revert_restores_previous_version(tmp_path):
    store, log, _g, events, state, psh = _setup(tmp_path)
    res = store.persist("s1", state, 0, proposal_set_hash=psh, event_log=log, events=events)
    assert res.status == "OK" and res.new_version == 1

    store.revert_commit("s1", 1, 47, psh, log)

    assert store.load_latest("s1").version == 0


def test_revert_orphans_events_but_keeps_history(tmp_path):
    store, log, _g, events, state, psh = _setup(tmp_path)
    store.persist("s1", state, 0, proposal_set_hash=psh, event_log=log, events=events)
    store.revert_commit("s1", 1, 47, psh, log)

    assert log.read_chapter("s1", 47) == []                       # 非 orphan 视图为空
    assert len(log.read_chapter("s1", 47, include_orphan=True)) == 3  # 行保留供诊断（I7）


def test_revert_clears_idempotency_allows_recommit(tmp_path):
    store, log, _g, events, state, psh = _setup(tmp_path)
    store.persist("s1", state, 0, proposal_set_hash=psh, event_log=log, events=events)
    store.revert_commit("s1", 1, 47, psh, log)

    # commit_log 已清，同幂等键可再次成功写入
    res2 = store.persist("s1", state, 0, proposal_set_hash=psh, event_log=log, events=[])
    assert res2.status == "OK" and res2.new_version == 1


def test_delete_helpers_are_idempotent(tmp_path):
    store, log, _g, events, state, psh = _setup(tmp_path)
    store.delete_state_version("s1", 99)      # 不存在 → 静默
    store.delete_commit_log("s1", 47, psh)    # 不存在 → 静默
    assert store.load_latest("s1").version == 0
