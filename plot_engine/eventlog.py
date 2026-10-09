"""append-only Event Log：SQLite WAL，先写日志后写状态（07 §7.1, 范围裁剪 C5）。

事件一经写入只追加、永不改写内容；回滚只把 orphan 标记置 1，保留行供诊断。
"""
from __future__ import annotations

import json
import sqlite3
from typing import List

from plot_engine.canonical import canonical_json
from plot_engine.models.event import Event

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    story_id     TEXT NOT NULL,
    chapter      INTEGER NOT NULL,
    seq          INTEGER NOT NULL,
    event_id     TEXT NOT NULL UNIQUE,
    orphan       INTEGER NOT NULL DEFAULT 0,
    payload_json BLOB NOT NULL,
    PRIMARY KEY (story_id, chapter, seq)
);
"""


class EventLog:
    """单故事追加型事件日志。"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, story_id: str, events: List[Event]) -> None:
        """只追加。同 (story_id, chapter, seq) 或 event_id 冲突 → IntegrityError。"""
        rows = [
            (story_id, e.chapter, e.seq, e.event_id, 0,
             canonical_json(e.model_dump(mode="json")))
            for e in events
        ]
        try:
            self._conn.executemany(
                "INSERT INTO events (story_id, chapter, seq, event_id, orphan, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            self._conn.rollback()
            raise

    def mark_orphan(self, story_id: str, chapter: int) -> None:
        """回滚标记（07 §7.5 R6）：不删除事件行。"""
        self._conn.execute(
            "UPDATE events SET orphan = 1 WHERE story_id = ? AND chapter = ?",
            (story_id, chapter),
        )
        self._conn.commit()

    @staticmethod
    def _hydrate(blob: bytes) -> Event:
        return Event(**json.loads(blob))

    def read_chapter(self, story_id: str, chapter: int,
                     include_orphan: bool = False) -> List[Event]:
        sql = ("SELECT payload_json FROM events WHERE story_id = ? AND chapter = ?"
               + ("" if include_orphan else " AND orphan = 0")
               + " ORDER BY seq")
        cur = self._conn.execute(sql, (story_id, chapter))
        return [self._hydrate(row[0]) for row in cur.fetchall()]

    def read_range(self, story_id: str, from_chapter: int, to_chapter: int) -> List[Event]:
        cur = self._conn.execute(
            "SELECT payload_json FROM events "
            "WHERE story_id = ? AND chapter BETWEEN ? AND ? AND orphan = 0 "
            "ORDER BY chapter, seq",
            (story_id, from_chapter, to_chapter),
        )
        return [self._hydrate(row[0]) for row in cur.fetchall()]

    def read_story(self, story_id: str) -> List[Event]:
        """整条故事的已提交事件（被回滚章已标 orphan，天然不在内）。

        「已提交事件集」的定义就是日志本身，不是 `1..state.chapter_no`：
        实验夹具会跳章（弧范围 47 起），按上界裁会漏掉真实存在的历史事件。
        """
        cur = self._conn.execute(
            "SELECT payload_json FROM events WHERE story_id = ? AND orphan = 0 "
            "ORDER BY chapter, seq",
            (story_id,),
        )
        return [self._hydrate(row[0]) for row in cur.fetchall()]
