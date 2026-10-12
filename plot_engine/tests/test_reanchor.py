"""E25 重锚检测器的最小可跑校验：三章合成跑法，逐条对上「establish / reanchor / advancing」。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from plot_engine.canonical import canonical_json
from plot_engine.eventlog import EventLog
from plot_engine.models.event import Event
from plot_engine.models.state import StoryState, with_state_hash
from plot_engine.reanchor import analyze
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore

STORY = "s1"


def _ev(ch, seq, etype, payload, event_id=None):
    return Event(event_id=event_id or f"evt_{ch:08d}_{seq:03d}", epoch="epoch_0",
                 event_type=etype, actor="char_000001", chapter=ch, seq=seq,
                 payload=payload, confidence=900)


def _write_state(db: Path, version: int, chapter: int, state: StoryState) -> None:
    stamped = with_state_hash(state.model_copy(update={"chapter_no": chapter, "version": version}))
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO states VALUES (?, ?, ?, ?, ?)",
                    (STORY, version, chapter, stamped.state_hash,
                     canonical_json(stamped.model_dump(mode="json"))))


def _run(tmp_path: Path) -> dict:
    (tmp_path / "state").mkdir()
    state_db, event_db = tmp_path / "state" / "state.db", tmp_path / "state" / "event.db"
    StateStore(str(state_db))                      # 建表（含 genesis 之外的 states 结构）
    log = EventLog(str(event_db))
    red = Reducer()

    ch1 = [_ev(1, 0, "OBSERVES", {"fact_id": "fact_000003", "method": "sight"})]
    ch2 = [_ev(2, 0, "OBSERVES", {"fact_id": "fact_000003", "method": "sight"}),
           _ev(2, 1, "INFERS", {"conclusion_fact_id": "fact_000001",
                                "evidence_fact_ids": ["fact_000003"]})]
    ch3 = [_ev(3, 0, "OBSERVES", {"fact_id": "fact_000001", "method": "sight"})]

    state = with_state_hash(StoryState(story_id=STORY, chapter_no=0, version=0, epoch="epoch_0",
                                       state_hash=""))
    _write_state(state_db, 0, 0, state)
    version = 0
    for ch, evs in ((1, ch1), (2, ch2), (3, ch3)):
        for ev in evs:
            state = red.apply(ev, state)
        log.append(STORY, evs)
        version += 1
        _write_state(state_db, version, ch, state)
    return analyze(tmp_path)


def test_reanchor_counts_only_no_delta_repeats(tmp_path):
    r = _run(Path(tmp_path))
    assert r["reanchor"] == 1               # ch2 重看 F3：台账没动
    assert r["advancing"] == 1              # ch3 把 F1 从 suspected 升到 known
    assert r["unclassified"] == 1           # 合成跑法没有夹具戳 ⇒ 不猜它是不是命令过的
    assert "uncommanded" not in r          # 分不了类就不出现，不拿 0 冒充「没有病」
    assert r["chapters"] == 3


def test_chapter_one_never_counts_as_reanchor(tmp_path):
    r = _run(Path(tmp_path))
    assert "reanchor" not in r["chapters_detail"][0]      # 第 1 章之前没有「已渲染」可言
