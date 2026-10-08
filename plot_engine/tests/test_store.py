"""CAS StateStore + 快照 + 幂等测试（07 §7, 范围裁剪 C1/C5）。"""
from __future__ import annotations

import pytest

from plot_engine.eventlog import EventLog
from plot_engine.models.state import StoryState, with_state_hash
from plot_engine.store import StateStore


def _st(ch, ver):
    return with_state_hash(StoryState(story_id="s1", chapter_no=ch, version=ver,
                                      epoch="epoch_0", state_hash=""))


@pytest.fixture
def env(tmp_path):
    return StateStore(str(tmp_path / "s.db")), EventLog(str(tmp_path / "e.db"))


def test_first_commit_ok(env):
    store, log = env
    r = store.persist("s1", _st(1, 1), 0, proposal_set_hash="h1", event_log=log, events=[])
    assert r.status == "OK" and r.new_version == 1


def test_cas_conflict(env):
    store, log = env
    store.persist("s1", _st(1, 1), 0, proposal_set_hash="h1", event_log=log, events=[])
    r = store.persist("s1", _st(1, 1), 0, proposal_set_hash="h2", event_log=log, events=[])
    assert r.status == "CONFLICT" and r.current_version == 1


def test_idempotent_duplicate_returns_cached(env):
    store, log = env
    a = store.persist("s1", _st(1, 1), 0, proposal_set_hash="hX", event_log=log, events=[])
    b = store.persist("s1", _st(1, 1), 0, proposal_set_hash="hX", event_log=log, events=[])
    assert a.status == "OK" and b.status == "DUPLICATE"


def test_snapshot_written_at_multiple_of_5(env):
    store, log = env
    ver = 0
    for ch in range(1, 6):
        store.persist("s1", _st(ch, ver + 1), ver, proposal_set_hash=f"h{ch}",
                      event_log=log, events=[])
        ver += 1
    assert store.load_snapshot_at_or_before("s1", 5) is not None
    assert store.load_snapshot_at_or_before("s1", 4) is None
