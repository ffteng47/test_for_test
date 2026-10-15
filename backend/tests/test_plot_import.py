"""WP-D 验收测试（docs/wp-d-noveldb-mapping.md v0.3 §5 清单）。

fixture 纪律：真实数据（sampling/bo_ctrl，10 章 run：5 章 OK + 4 章 NEEDS_HUMAN + 1 章 ARC_CONFLICT），
禁 mock 充数；bo_ctrl 已入 git（.gitignore 例外表），属于仓库内固定 fixture。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.noveldb import open_db
from backend.plot_import import import_run, tension_to_real
from plot_engine.reading import read_run
from plot_engine.store import StateStore

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = REPO_ROOT / "sampling" / "bo_ctrl"
TITLE = "WP-D 验收 fixture（bo_ctrl）"


@pytest.fixture()
def stats(tmp_path):
    db_path = tmp_path / "novelaudio.db"
    result = import_run(db_path, RUN_DIR, title=TITLE)
    return {"db_path": db_path, "stats": result}


def _count(db_path: Path, table: str, project_id: int, *, column: str = 'project_id') -> int:
    con = sqlite3.connect(db_path)
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (project_id,)
        ).fetchone()[0]
    finally:
        con.close()


def _ok_chapters() -> list[int]:
    run = read_run(RUN_DIR)
    return [c["no"] for c in run["chapters"] if c.get("status") == "OK"]


def _envelope(story_id: str):
    store = StateStore(str(RUN_DIR / "state" / "state.db"))
    return store.load_latest(story_id)


def test_three_way_reconcile(stats):
    """三方对账（§5-1）：characters 数 = len(state.characters)、
    chapters 数 = dump 中 OK/rescued 章数、bible.facts 数 = len(state.facts)。"""
    db_path, result = stats["db_path"], stats["stats"]
    envelope = _envelope(result["story_id"])
    ok_chapters = _ok_chapters()

    assert _count(db_path, "characters", result["project_id"]) == len(envelope.state.characters)
    assert _count(db_path, "chapters", result["project_id"]) == len(ok_chapters)

    con = sqlite3.connect(db_path)
    try:
        bible = json.loads(
            con.execute("SELECT bible FROM projects WHERE id=?", (result["project_id"],)).fetchone()[0]
        )
    finally:
        con.close()
    assert len(bible["facts"]) == len(envelope.state.facts)

    assert result["characters"] == len(envelope.state.characters)
    assert result["facts"] == len(envelope.state.facts)
    assert result["chapters_imported"] == ok_chapters


def test_idempotent_reimport(tmp_path):
    """幂等（§5-2）：同一 fixture 连导两次，三表行数不变、无报错。"""
    db_path = tmp_path / "novelaudio.db"
    first = import_run(db_path, RUN_DIR, title=TITLE)
    tables = ("projects", "characters", "chapters")
    col = lambda t: "id" if t == "projects" else "project_id"  # projects 主键列名是 id
    before = {t: _count(db_path, t, first["project_id"], column=col(t)) for t in tables}
    second = import_run(db_path, RUN_DIR, title=TITLE)
    after = {t: _count(db_path, t, second["project_id"], column=col(t)) for t in tables}
    assert first["project_id"] == second["project_id"]
    assert before == after


def test_fail_chapters_filtered(stats):
    """过滤（§5-3）：非 OK 章（FAIL/NEEDS_HUMAN/ARC_CONFLICT/HALT 等 disposition）不入库。"""
    db_path, result = stats["db_path"], stats["stats"]
    run = read_run(RUN_DIR)
    non_ok = {c["no"]: c.get("status") for c in run["chapters"] if c.get("status") != "OK"}
    assert non_ok, "bo_ctrl fixture 应含非 OK 章（本用例依赖真实残章）"

    skipped = {s["no"]: s["status"] for s in result["chapters_skipped"]}
    assert skipped == non_ok

    con = sqlite3.connect(db_path)
    try:
        nos = [r[0] for r in con.execute(
            "SELECT no FROM chapters WHERE project_id=? ORDER BY no", (result["project_id"],)
        )]
    finally:
        con.close()
    assert nos == sorted(n for n in {c["no"] for c in run["chapters"]} if n not in non_ok)


def test_tension_fixed_point_conversion():
    """定点转换（§5-4）：scenes.tension = 源值÷1000（700 → 0.7）；一期 scenes 不导，锁换算语义。"""
    assert tension_to_real(700) == pytest.approx(0.7)
    assert tension_to_real(0) == pytest.approx(0.0)
    assert tension_to_real(1000) == pytest.approx(1.0)


def test_bible_json_and_source_block(stats):
    """bible JSON 可 json.loads 且 source 块四字段齐全（§5-5）。"""
    db_path, result = stats["db_path"], stats["stats"]
    con = sqlite3.connect(db_path)
    try:
        raw = con.execute("SELECT bible FROM projects WHERE id=?", (result["project_id"],)).fetchone()[0]
    finally:
        con.close()
    bible = json.loads(raw)
    source = bible.get("source", {})
    for field in ("story_id", "epoch", "state_version", "state_hash"):
        assert field in source and source[field] not in (None, ""), f"source 缺字段: {field}"
    assert source["story_id"] == result["story_id"]


def test_sql_columns_verified(stats):
    """SQL 字段验证（§5-6）：PRAGMA table_info 核对映射表用到的每个列名。"""
    expected = {
        "projects": {"id", "title", "author", "lang", "bible", "created_at"},
        "characters": {"id", "project_id", "key", "label", "gender", "age", "personality", "aliases", "voice_config"},
        "chapters": {"id", "project_id", "no", "title", "state"},
        "scenes": {"id", "project_id", "chapter_id", "ord", "setting", "time", "tension", "summary"},
    }
    con = open_db(str(stats["db_path"]))
    try:
        for table, cols in expected.items():
            actual = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
            assert cols <= actual, f"{table} 缺列: {cols - actual}"
    finally:
        con.close()