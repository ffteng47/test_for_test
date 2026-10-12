"""E25「事实重锚」检测器：只读 `state/`，零模型调用，离线可跑全库。

重锚 = 本章断言了一个**进本章之前台账里已经有**的事实，而施加后该条目的
(状态, 强度) 一点没动。它对应正文层的「把已经写过的东西再写一遍」：引擎里没有
已渲染台账，Writer 于是可以无限回到同一句话（`docs/measurement-errata.md` E25）。

为什么判 (状态, 强度) 而不是判 `last_updated_chapter`：`_merge_upgrade` / `_upsert`
只要条目存在就会重写 `source_event_id` 与 `last_updated_chapter`，那个字段永远在变，
不是「有没有推进」的证据；只有语义字段（rank、strength）不动才是空转。

两个读数分开，否则夹具的病会算到引擎头上（tff 裁定）：信念弧本来就命令 ch03 相信 /
ch04 动摇 / ch07 起疑重触 F1 ⇒ 命中本章 `must_change` 点名的 (field, fact) 记 **commanded**，
其余记 **uncommanded**。观测列，不卡门。
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from plot_engine.models.event import Event
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer

# 事件 → 它会动哪本台账（world/plot 类没有对应的台账条目，判不了重锚，直接跳过）
_KIND = {"OBSERVES": "knowledge", "READS": "knowledge", "IS_TOLD": "knowledge",
         "INFERS": "knowledge", "FACT_CONTRADICTED": "knowledge",
         "BELIEVES": "belief", "SUSPECTS": "belief", "DOUBTS": "belief",
         "STATES": "belief", "LIES": "belief", "HINTS": "belief",
         "READER_LEARNS": "reader", "READER_DECEIVED": "reader", "READER_HINTED": "reader"}

Claim = Tuple[str, str, str]      # (kind, actor, fact)


def claims(ev: Event) -> List[Claim]:
    et, p = ev.event_type, (ev.payload or {})
    if et == "INFERS":
        return [("knowledge", ev.actor or "", p["conclusion_fact_id"])]
    if et in ("STATES", "LIES"):
        fact = p.get("stated_fact_id") if et == "LIES" else p.get("fact_id")
        return [("belief", a, fact) for a in p.get("audience", []) if fact]
    fact = p.get("fact_id")
    kind = _KIND.get(et)
    if fact is None or kind is None:
        return []
    return [(kind, "" if kind == "reader" else (ev.actor or ""), fact)]


def entry(state: StoryState, kind: str, actor: str, fact: str):
    """条目的语义值；不存在 → None（= 进本章之前这个事实还没渲染给这个人）。"""
    if kind == "knowledge":
        for e in state.knowledge_ledger:
            if e.character_id == actor and e.fact_id == fact:
                return (e.knowledge_state, e.strength)
    elif kind == "belief":
        for e in state.belief_ledger:
            if e.character_id == actor and e.fact_id == fact:
                return (e.belief_state, e.strength)
    else:
        for e in state.reader_ledger:
            if e.fact_id == fact:
                return (e.reader_state, e.reader_strength)
    return None


def _ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def run_states(run_dir: Path) -> Dict[int, StoryState]:
    """章号 → 该章提交后的状态（同章多版取最后一版；章 0 = genesis）。"""
    out: Dict[int, StoryState] = {}
    with _ro(run_dir / "state" / "state.db") as con:
        for ch, blob in con.execute("SELECT chapter_no, envelope FROM states ORDER BY version"):
            out[ch] = StoryState.model_validate(json.loads(blob))
    return out


def run_events(run_dir: Path) -> Dict[int, List[Event]]:
    """章号 → 已提交事件（orphan=0，按 seq）。被回滚章天然不在内。"""
    out: Dict[int, List[Event]] = {}
    with _ro(run_dir / "state" / "event.db") as con:
        for ch, blob in con.execute(
                "SELECT chapter, payload_json FROM events WHERE orphan = 0 ORDER BY chapter, seq"):
            out.setdefault(ch, []).append(Event.model_validate(json.loads(blob)))
    return out


def commanded(ch: int, ladder: str) -> Optional[set]:
    """夹具点名的 (台账, 事实)：本章 must_change 的目标 + 本章阶梯事件自己声明的事实
    （第 8 步「本章不推进」也在此列——那是夹具要求的重触，不能算引擎的病）。
    跑法的夹具戳与当前 `_STEPS` 不同版 → None（无从判定）。"""
    from plot_engine.tests.fixtures import experiment_10ch as fx

    if ladder != fx.LADDER_VERSION:
        return None
    step = fx._STEPS[(ch - 1) % len(fx._STEPS)]
    return ({(m["field"], m["target"]) for m in step["must_change"]}
            | {(_KIND[e["event_type"]], e["fact"]) for e in step["events"]})


def ladder_of(run_dir: Path) -> str:
    """夹具戳在 run.log 或同级 `<run>.log` 第 1 行；没戳的历史跑法一律按 ladder-v1 读。"""
    for log in (run_dir / "run.log", run_dir.with_suffix(".log")):
        if log.exists():
            for line in log.read_text(encoding="utf-8", errors="ignore").splitlines()[:3]:
                found = re.search(r"夹具=([^\s｜]+)", line)
                if found:
                    return found.group(1)
    return "无戳（按 ladder-v1 读）"


def analyze(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    states, events, red = run_states(run_dir), run_events(run_dir), Reducer()
    ladder = ladder_of(run_dir)
    committed = sorted(states)
    per_chapter, totals = [], Counter()
    for ch, evs in sorted(events.items()):
        prior = [c for c in committed if c < ch]
        if not prior:
            continue                       # genesis 章或状态缺档：没有「之前」可对照
        cmd = commanded(ch, ladder)
        base = cur = states[prior[-1]]
        hit = Counter()
        for ev in evs:
            watched = [(kind, actor, fact, entry(cur, kind, actor, fact))
                       for kind, actor, fact in claims(ev)
                       if entry(base, kind, actor, fact) is not None]
            cur = red.apply(ev, cur)
            for kind, actor, fact, before in watched:
                if entry(cur, kind, actor, fact) != before:
                    hit["advancing"] += 1
                    continue
                hit["reanchor"] += 1
                if cmd is None:
                    hit["unclassified"] += 1            # 夹具戳对不上：不猜它是不是命令过的
                elif (kind, fact) in cmd:
                    hit["commanded"] += 1
                else:
                    hit["uncommanded"] += 1
                    hit[f"uncommanded_{kind}"] += 1     # 病在哪本台账上：角色认知 vs 读者认知
        totals.update(hit)
        totals["events"] += len(evs)
        per_chapter.append({"chapter": ch, "events": len(evs), **dict(hit)})
    totals["chapters"] = len(per_chapter)
    totals["ladder_classified"] = commanded(1, ladder) is not None
    return {"run": run_dir.name, "ladder": ladder,
            "chapters_detail": per_chapter, **totals}


def main(argv: None | List[str] = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m plot_engine.reanchor",
                                 description="E25 事实重锚计数（观测列，不卡门）")
    ap.add_argument("runs", nargs="*", help="采样目录（含 state/）；缺省=全库")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    runs = [Path(r) for r in ns.runs] if ns.runs else sorted(
        d.parent.parent for d in Path("sampling").glob("*/state/event.db"))
    rows = [analyze(d) for d in runs if (d / "state" / "event.db").exists()]
    if ns.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(f"{'跑法':<22}{'夹具':<26}{'事件':>5}{'重锚':>6}{'其中命令':>9}{'其中未命令':>10}"
          f"{'推进式重述':>11}{'重锚/章':>9}")
    for r in rows:
        n = r.get("reanchor", 0)
        ch = max(r.get("chapters", 1), 1)
        split = (f"{r.get('commanded', 0):>9}{r.get('uncommanded', 0):>10}"
                 if r["ladder_classified"] else f"{'—':>9}{'—':>10}")
        print(f"{r['run']:<22}{r['ladder']:<26}{r.get('events', 0):>5}{n:>6}{split}"
              f"{r.get('advancing', 0):>11}{(n / ch):>9.2f}")
    print("重锚/章 = 每章平均「说了旧事实而台账没动」的次数；「—」= 该跑法的夹具戳与当前 _STEPS 不同版，"
          "命令/未命令分不了。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
