# WP-F B5 章闭环裁决账：jobs 表复用确认闸状态机，裁决即确认、可查账、非法动作拒入账。
from __future__ import annotations

import json

import pytest

from backend.noveldb import CHAPTER_DECISION_TASK, Db, open_db


@pytest.fixture()
def db(tmp_path):
    return Db(open_db(str(tmp_path / "novelaudio.db")))


def test_decide_chapter_records_confirmed_job(db):
    pid = db.upsert_project("B5 fixture")
    jid = db.decide_chapter(pid, 7, "accept_current")
    row = db.get_job(jid)
    assert row["task"] == CHAPTER_DECISION_TASK and row["status"] == "confirmed"
    assert json.loads(row["payload"]) == {"chapter_no": 7, "action": "accept_current"}


def test_latest_chapter_decision_is_per_chapter_and_newest_wins(db):
    pid = db.upsert_project("B5 fixture")
    db.decide_chapter(pid, 7, "accept_current")
    j2 = db.decide_chapter(pid, 7, "manual_rewrite")
    assert db.latest_chapter_decision(pid, 7)["id"] == j2      # 同章取最新
    assert db.latest_chapter_decision(pid, 8) is None          # 未裁=查无


def test_illegal_action_rejected(db):
    pid = db.upsert_project("B5 fixture")
    with pytest.raises(ValueError):
        db.decide_chapter(pid, 1, "rewrite_everything")
