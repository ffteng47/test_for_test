"""CAS StateStore：版本乐观锁 + 快照 + commit_log 幂等（07 §7, 范围裁剪 C1/C5）。

单 SQLite 连接，写路径用 BEGIN IMMEDIATE 串行化（这就是接多 Worker 的地基）。
CAS 比较的是信封 version 列（与 state.version 解耦）。
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from typing import List, Optional

from plot_engine.canonical import canonical_json
from plot_engine.eventlog import EventLog
from plot_engine.models.event import Event
from plot_engine.models.state import StoryState, with_state_hash

_SCHEMA = """
CREATE TABLE IF NOT EXISTS states (
    story_id   TEXT NOT NULL,
    version    INTEGER NOT NULL,
    chapter_no INTEGER NOT NULL,
    state_hash TEXT NOT NULL,
    envelope   BLOB NOT NULL,
    PRIMARY KEY (story_id, version)
);
CREATE TABLE IF NOT EXISTS snapshots (
    story_id   TEXT NOT NULL,
    chapter_no INTEGER NOT NULL,
    version    INTEGER NOT NULL,
    state_hash TEXT NOT NULL,
    envelope   BLOB NOT NULL,
    PRIMARY KEY (story_id, chapter_no)
);
CREATE TABLE IF NOT EXISTS commit_log (
    story_id          TEXT NOT NULL,
    chapter_no        INTEGER NOT NULL,
    version           INTEGER NOT NULL,
    state_hash        TEXT NOT NULL,
    proposal_set_hash TEXT NOT NULL,
    ts                TEXT NOT NULL,
    PRIMARY KEY (story_id, chapter_no, proposal_set_hash)
);
"""


@dataclasses.dataclass
class StateEnvelope:
    story_id: str
    version: int
    chapter_no: int
    state: StoryState
    state_hash: str


@dataclasses.dataclass
class CommitResult:
    status: str                         # "OK" | "CONFLICT" | "DUPLICATE"
    new_version: Optional[int] = None
    current_version: Optional[int] = None
    message: str = ""


class StateStore:
    """状态存储：CAS 写入 + 每 N 章快照 + 幂等键。"""

    def __init__(self, db_path: str, *, snapshot_every: int = 5) -> None:
        # isolation_level=None → 手动事务控制（BEGIN IMMEDIATE），CAS 的真正串行化点
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._snapshot_every = snapshot_every

    # ---- 读 ----
    def _current_version(self, story_id: str) -> int:
        cur = self._conn.execute(
            "SELECT MAX(version) FROM states WHERE story_id = ?", (story_id,)
        )
        row = cur.fetchone()[0]
        return 0 if row is None else row

    def load_latest(self, story_id: str) -> StateEnvelope:
        cur = self._conn.execute(
            "SELECT version, chapter_no, state_hash, envelope FROM states "
            "WHERE story_id = ? ORDER BY version DESC LIMIT 1",
            (story_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"no state for story_id={story_id}")
        return self._to_envelope(story_id, row)

    def load_snapshot_at_or_before(
        self, story_id: str, chapter_no: int
    ) -> Optional[StateEnvelope]:
        cur = self._conn.execute(
            "SELECT version, chapter_no, state_hash, envelope FROM snapshots "
            "WHERE story_id = ? AND chapter_no <= ? ORDER BY chapter_no DESC LIMIT 1",
            (story_id, chapter_no),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._to_envelope(story_id, row)

    @staticmethod
    def _to_envelope(story_id: str, row) -> StateEnvelope:
        version, chapter_no, state_hash, blob = row
        state = StoryState.model_validate(json.loads(blob))
        return StateEnvelope(story_id, version, chapter_no, state, state_hash)

    # ---- 写 ----
    def init_genesis(self, story_id: str, base_state: StoryState) -> None:
        """持久化 chapter-0/version-0 基线：同时写 states 与 snapshots，供 replay 起步。"""
        stamped = with_state_hash(base_state.model_copy(update={"version": 0, "chapter_no": 0}))
        blob = canonical_json(stamped.model_dump(mode="json"))
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO states (story_id, version, chapter_no, state_hash, envelope) "
                "VALUES (?, 0, 0, ?, ?)",
                (story_id, stamped.state_hash, blob),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO snapshots (story_id, chapter_no, version, state_hash, envelope) "
                "VALUES (?, 0, 0, ?, ?)",
                (story_id, stamped.state_hash, blob),
            )
            self._conn.execute("COMMIT")
        except sqlite3.Error:
            self._conn.execute("ROLLBACK")
            raise

    def _is_duplicate(self, story_id: str, chapter_no: int, proposal_set_hash: str):
        cur = self._conn.execute(
            "SELECT version, state_hash FROM commit_log "
            "WHERE story_id = ? AND chapter_no = ? AND proposal_set_hash = ?",
            (story_id, chapter_no, proposal_set_hash),
        )
        return cur.fetchone()

    def persist(
        self,
        story_id: str,
        new_state: StoryState,
        expected_version: int,
        *,
        proposal_set_hash: str,
        event_log: EventLog,
        events: List[Event],
    ) -> CommitResult:
        # 1. 幂等键先行（07 §8 R2）：同键已成功 → 返回缓存，不重复写
        chapter_no = new_state.chapter_no
        cached = self._is_duplicate(story_id, chapter_no, proposal_set_hash)
        if cached is not None:
            return CommitResult(status="DUPLICATE", new_version=cached[0],
                                message="already committed (idempotent)")

        # 2. CAS 事务（07 §7.1/§7.2）
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            current = self._current_version(story_id)
            if current != expected_version:
                self._conn.execute("ROLLBACK")
                return CommitResult(status="CONFLICT", current_version=current,
                                    message="Another writer committed first")

            # WAL：先写事件日志（append-only，独立连接，保留供诊断）
            if events:
                event_log.append(story_id, events)

            new_version = expected_version + 1
            # 存给定 state 原样（只补哈希）；CAS 版本只记在信封 version 列，
            # 不改写 state.version —— 否则与 replay 重建的 state 内容哈希对不上。
            stamped = with_state_hash(new_state)
            blob = canonical_json(stamped.model_dump(mode="json"))
            self._conn.execute(
                "INSERT INTO states (story_id, version, chapter_no, state_hash, envelope) "
                "VALUES (?, ?, ?, ?, ?)",
                (story_id, new_version, chapter_no, stamped.state_hash, blob),
            )
            if chapter_no > 0 and chapter_no % self._snapshot_every == 0:
                self._conn.execute(
                    "INSERT OR REPLACE INTO snapshots "
                    "(story_id, chapter_no, version, state_hash, envelope) VALUES (?, ?, ?, ?, ?)",
                    (story_id, chapter_no, new_version, stamped.state_hash, blob),
                )
            self._conn.execute(
                "INSERT INTO commit_log (story_id, chapter_no, version, state_hash, "
                "proposal_set_hash, ts) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (story_id, chapter_no, new_version, stamped.state_hash, proposal_set_hash),
            )
            self._conn.execute("COMMIT")
        except sqlite3.Error:
            self._conn.execute("ROLLBACK")
            raise
        return CommitResult(status="OK", new_version=new_version)

    # ---- 回滚原语（07 §7.5 R6 / §9：仅撤销本次 Commit，不动其它历史 version，I7）----
    def delete_state_version(self, story_id: str, version: int) -> None:
        self._conn.execute(
            "DELETE FROM states WHERE story_id = ? AND version = ?",
            (story_id, version),
        )

    def delete_commit_log(self, story_id: str, chapter_no: int, proposal_set_hash: str) -> None:
        self._conn.execute(
            "DELETE FROM commit_log WHERE story_id = ? AND chapter_no = ? AND proposal_set_hash = ?",
            (story_id, chapter_no, proposal_set_hash),
        )

    def revert_commit(self, story_id: str, version: int, chapter_no: int,
                      proposal_set_hash: str, event_log: EventLog) -> None:
        """§7.5 R6：回滚 version 指针 + 清幂等键 + 本章事件标 orphan（不删除，供诊断）。"""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "DELETE FROM states WHERE story_id = ? AND version = ?",
                (story_id, version),
            )
            self._conn.execute(
                "DELETE FROM snapshots WHERE story_id = ? AND version = ?",
                (story_id, version),
            )
            self._conn.execute(
                "DELETE FROM commit_log WHERE story_id = ? AND chapter_no = ? AND proposal_set_hash = ?",
                (story_id, chapter_no, proposal_set_hash),
            )
            self._conn.execute("COMMIT")
        except sqlite3.Error:
            self._conn.execute("ROLLBACK")
            raise
        event_log.mark_orphan(story_id, chapter_no)

