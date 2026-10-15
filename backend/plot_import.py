"""plot_engine → noveldb 导入通道（WP-D 一期）。

映射依据：docs/wp-d-noveldb-mapping.md v0.3（开放问题①已关闭，即刻可开工）。
读侧只用既有只读接口，plot_engine 零改动：
  - StateStore.load_latest / load_snapshot_at_or_before（plot_engine/store.py）
  - reading.read_run / chapter_texts（plot_engine/reading.py）
写侧只走 backend/noveldb.py 既有幂等接口（upsert_project/set_bible/upsert_character/upsert_chapter）。

一期范围（映射 §3）：
  - projects(+bible) / characters / chapters（元数据层）
  - 正文不导：等 S2 §2.3 novel_chapters 表（稽核 2026-10-15 裁决，暂存 state.text 弃用）
  - scenes 不导：ScenePlan 无持久化读路径（映射 §3.4 缺口注明），仅保留 tension_to_real 备二期

字段缺失容忍（映射 §6）：epoch_1 后 StoryState 增字段时本模块不硬解版本，一律 getattr 默认。
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.noveldb import Db, open_db
from plot_engine.reading import read_run
from plot_engine.store import StateEnvelope, StateStore

# rewrite_rescued 是 OK 章的 bucket（plot_engine/metrics.py:36），
# 因此 status == "OK" 即完整覆盖「OK + rewrite_rescued」合格面；
# NEEDS_HUMAN / ARC_CONFLICT / FAIL / HALT 等 disposition 一律不入库（残章不进交付管线，映射 §3.3）。
QUALIFIED_STATUS = {"OK"}


def tension_to_real(fixed_point: int) -> float:
    """定点×1000 → REAL÷1000（全表唯一定点转换点，必须显式；映射 §3.4）。

    一期 scenes 不导，本函数为二期 scenes.tension 导入预留，验收测试锁定换算语义。
    """
    return fixed_point / 1000


def _story_id_of(state_db: Path) -> str:
    """从 state.db 发现 story_id（多 story 时报错，要求调用方显式指定；映射 §6 多 run 同源）。"""
    con = sqlite3.connect(f"file:{state_db.as_posix()}?mode=ro", uri=True)
    try:
        ids = [row[0] for row in con.execute("SELECT DISTINCT story_id FROM states")]
    finally:
        con.close()
    if not ids:
        raise ValueError(f"state.db 无 states 行: {state_db}")
    if len(ids) > 1:
        raise ValueError(f"state.db 含多个 story_id {ids}，请用 story_id 参数显式指定")
    return ids[0]


def build_bible(envelope: StateEnvelope) -> Dict[str, Any]:
    """StoryState 聚合 → projects.bible（映射 §3.1；source 块四字段必带，溯源用）。"""
    state = envelope.state

    def _named(rows: Dict[str, Any], id_field: str) -> List[Dict[str, str]]:
        return [
            {"id": getattr(entity, id_field, key), "name": getattr(entity, "name", "")}
            for key, entity in sorted(rows.items())
        ]

    return {
        "facts": {fact_id: getattr(fact, "proposition", "") for fact_id, fact in sorted(state.facts.items())},
        "fact_relations": [rel.model_dump(mode="json") for rel in getattr(state, "fact_relations", [])],
        "world": {
            "locations": _named(getattr(state, "locations", {}), "location_id"),
            "factions": _named(getattr(state, "factions", {}), "faction_id"),
            "realms": _named(getattr(state, "realms", {}), "realm_id"),
        },
        "global_style": "",
        "source": {
            "story_id": envelope.story_id,
            "epoch": getattr(state, "epoch", ""),
            "state_version": envelope.version,
            "state_hash": envelope.state_hash,
        },
    }


def _chapter_memory(
    *,
    no: int,
    chapter_row: Dict[str, Any],
    latest_state: Any,
    exact_snapshot: Optional[StateEnvelope],
    run_label: str,
) -> Dict[str, Any]:
    """章级 chapter memory（映射 §3.3）。

    - findings / guide：来自 chapter_texts（供下游 continuity_checker 消费）
    - knowledge_delta_count：knowledge_ledger 累计台账按 acquired_at_chapter 计数（末态即可算，真实）
    - characters_on_stage / locations：仅当有该章**精确**快照（snapshot.chapter_no == no）时给出；
      快照按 snapshot_every 间隔落盘，非逐章，无精确快照时置 None（宁可标缺，绝不编造）
    """
    memory: Dict[str, Any] = {
        "characters_on_stage": None,
        "locations": None,
        "knowledge_delta_count": sum(
            1
            for entry in getattr(latest_state, "knowledge_ledger", [])
            if getattr(entry, "acquired_at_chapter", None) == no
        ),
        "findings": list(chapter_row.get("findings", [])),
        "guide": list(chapter_row.get("guide", [])),
        "source": {
            "run": run_label,
            "status": chapter_row.get("status"),
            "rounds": chapter_row.get("rounds"),
            "bucket": chapter_row.get("bucket"),
        },
    }
    if exact_snapshot is not None:
        state = exact_snapshot.state
        on_stage = sorted(
            cid
            for cid, char in state.characters.items()
            if getattr(char, "last_seen_at_chapter", None) == no
        )
        memory["characters_on_stage"] = on_stage
        location_ids = {
            getattr(state.characters[cid], "current_location", None) for cid in on_stage
        }
        memory["locations"] = sorted(
            state.locations[loc_id].name
            for loc_id in location_ids
            if loc_id and loc_id in state.locations
        )
    return memory


def import_run(
    db_path: Path | str,
    run_dir: Path | str,
    *,
    title: str,
    author: str = "",
    story_id: Optional[str] = None,
) -> Dict[str, Any]:
    """把一个采样 run（<run>/state/state.db + <run>/dump/）导入 noveldb。

    幂等（映射 §4）：project 按 title 复用，characters/chapters 走表级 UNIQUE upsert，
    重复导入行数不变。返回统计供验收三方对账。
    """
    run_dir = Path(run_dir)
    state_db = run_dir / "state" / "state.db"
    if not state_db.exists():
        raise FileNotFoundError(f"缺 state.db: {state_db}（run 目录须含 state/ 与 dump/）")
    sid = story_id or _story_id_of(state_db)

    store = StateStore(str(state_db))
    envelope = store.load_latest(sid)
    run = read_run(run_dir)

    db = Db(open_db(str(db_path)))
    project_id = db.upsert_project(title, author)
    db.set_bible(project_id, build_bible(envelope))

    characters = sorted(envelope.state.characters.values(), key=lambda c: c.character_id)
    for char in characters:
        db.upsert_character(
            project_id,
            key=char.character_id,
            label=char.name,
            gender=getattr(char, "gender", None),
            aliases=list(getattr(char, "aliases", [])),
            personality=[],  # plot_engine 不建人格维度，不编造（映射 §3.2）
        )

    imported: List[int] = []
    skipped: List[Dict[str, Any]] = []
    for row in run["chapters"]:
        no = row["no"]
        if row.get("status") not in QUALIFIED_STATUS:
            skipped.append({"no": no, "status": row.get("status")})
            continue
        snapshot = store.load_snapshot_at_or_before(sid, no)
        exact = snapshot if (snapshot is not None and snapshot.chapter_no == no) else None
        db.upsert_chapter(
            project_id,
            no,
            title=None,  # plot_engine 无章标题概念（映射 §3.3）
            state=_chapter_memory(
                no=no,
                chapter_row=row,
                latest_state=envelope.state,
                exact_snapshot=exact,
                run_label=run["label"],
            ),
        )
        imported.append(no)

    return {
        "project_id": project_id,
        "title": title,
        "story_id": sid,
        "state_version": envelope.version,
        "characters": len(characters),
        "facts": len(envelope.state.facts),
        "chapters_imported": imported,
        "chapters_skipped": skipped,
    }


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="plot_engine run → noveldb 导入（WP-D）")
    parser.add_argument("--run", required=True, help="采样 run 目录（含 state/state.db 与 dump/）")
    parser.add_argument("--title", required=True, help="作品名（人工给定；story_id 是机读 id，不作 title）")
    parser.add_argument("--author", default="")
    parser.add_argument("--db", default="novelaudio.db", help="noveldb 路径（默认 ./novelaudio.db）")
    parser.add_argument("--story-id", default=None, help="state.db 多 story 时显式指定")
    args = parser.parse_args(argv)
    stats = import_run(args.db, args.run, title=args.title, author=args.author, story_id=args.story_id)
    print(
        "导入完成: project_id={project_id} story={story_id} 人物={characters} 事实={facts} "
        "章 imported={chapters_imported} skipped={chapters_skipped}".format(**stats)
    )


if __name__ == "__main__":
    main()