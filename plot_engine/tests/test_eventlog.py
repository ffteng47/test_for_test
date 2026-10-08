"""append-only Event Log 测试（07 §7.1 WAL, C5）。"""
from __future__ import annotations

import sqlite3

import pytest

from plot_engine.eventlog import EventLog
from plot_engine.models.event import Event


def _ev(ch, seq):
    return Event(event_id=f"evt_{ch:08d}_{seq:03d}", epoch="epoch_0",
                 event_type="OBSERVES", chapter=ch, seq=seq,
                 payload={"fact_id": "fact_000003", "method": "sight"})


def test_append_then_read_roundtrips(tmp_path):
    log = EventLog(str(tmp_path / "ev.db"))
    log.append("s1", [_ev(47, 0), _ev(47, 1)])
    got = log.read_chapter("s1", 47)
    assert [e.seq for e in got] == [0, 1]
    assert got[0].event_type == "OBSERVES"


def test_duplicate_seq_rejected(tmp_path):
    log = EventLog(str(tmp_path / "ev.db"))
    log.append("s1", [_ev(47, 0)])
    with pytest.raises(sqlite3.IntegrityError):
        log.append("s1", [_ev(47, 0)])


def test_orphan_excluded_from_read(tmp_path):
    log = EventLog(str(tmp_path / "ev.db"))
    log.append("s1", [_ev(48, 0)])
    log.mark_orphan("s1", 48)
    assert log.read_chapter("s1", 48) == []
