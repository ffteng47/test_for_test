"""确认闸 jobs 账面（docs/confirmation-gate-design.md v1.0 §2/§4）。

零迁移：jobs 表 schema 未动，只新增读写函数。验收四件：
payload 哈希往返 / CAS 并发单赢 / 打回重提循环 / 非法迁移报错。
"""
from __future__ import annotations

import json

import pytest

from backend.noveldb import CONFIRM_TASK, Db, open_db

PLAN = {"plan_sha256": "ab" * 32}


@pytest.fixture()
def db(tmp_path):
    return Db(open_db(str(tmp_path / "novelaudio.db")))


@pytest.fixture()
def job(db):
    pid = db.upsert_project("确认闸 fixture")
    jid = db.add_confirm_job(pid, CONFIRM_TASK, "开书规划", PLAN)
    return pid, jid


def test_confirm_job_roundtrip_with_plan_hash(db, job):
    pid, jid = job
    row = db.get_job(jid)
    assert row["project_id"] == pid and row["task"] == CONFIRM_TASK
    assert row["status"] == "queued"
    assert json.loads(row["payload"]) == PLAN
    latest = db.latest_job(pid, CONFIRM_TASK)
    assert latest["id"] == jid


def test_cas_double_confirm_only_one_wins(tmp_path, db, job):
    _, jid = job
    rival = Db(open_db(str(tmp_path / "novelaudio.db")))
    results = [db.set_job_status(jid, "confirmed", "queued"),
               rival.set_job_status(jid, "confirmed", "queued")]
    assert results == [True, False]
    assert db.get_job(jid)["status"] == "confirmed"


def test_reject_then_resubmit_cycle(db, job):
    _, jid = job
    assert db.set_job_status(jid, "rejected", "queued")
    assert db.set_job_status(jid, "queued", "rejected")
    assert db.set_job_status(jid, "confirmed", "queued")
    assert db.get_job(jid)["status"] == "confirmed"


def test_illegal_transition_raises(db, job):
    _, jid = job
    db.set_job_status(jid, "confirmed", "queued")
    with pytest.raises(ValueError, match="非法迁移"):
        db.set_job_status(jid, "rejected", "confirmed")   # 已放行不可回退打回
    with pytest.raises(ValueError, match="非法状态"):
        db.set_job_status(jid, "done", "queued")
