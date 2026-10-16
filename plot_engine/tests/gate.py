"""测试侧确认闸工具：造一个已确认 project，返回 review --live 的闸参数。"""
from __future__ import annotations


def confirmed_gate(tmp_path, chapters: int, fixture: str = "experiment_10ch") -> list:
    from backend.noveldb import CONFIRM_TASK, Db, open_db
    from plot_engine.review import _load_fx, plan_sha256

    cfg = _load_fx(fixture).make_config(chapters)
    db_path = tmp_path / "gate.db"
    db = Db(open_db(str(db_path)))
    pid = db.upsert_project("确认闸测试 fixture")
    jid = db.add_confirm_job(pid, CONFIRM_TASK, "开书规划",
                             {"plan_sha256": plan_sha256(cfg, fixture)})
    assert db.set_job_status(jid, "confirmed", "queued")
    return ["--gate-project", str(pid), "--gate-db", str(db_path)]
