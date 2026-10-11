"""影子规则影响面：若「每章必须有非空状态差异」进尺，历史上会有多少章被拒。

为什么先算这个：协议现在**明确允许空差异**——`must_change: List[CharacterChange] = []`
（04 §4.1）、D1~D9 / V1~V10 / W1~W9 三张表里没有任何非空下限，而且 `story_goal_type` 里
`transition`（过场）与 `reflection`（回想）本身就是协议承认的「不推进型」章节。
所以这条规则不是「补个校验函数」，是一次**协议变更**；变更之前先拿已有跑数算清代价，
不花一次模型调用。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from plot_engine.eventlog import EventLog
from plot_engine.reducer import Reducer
from plot_engine.replay import replay_to_chapter
from plot_engine.store import StateStore
from plot_engine.tests.fixtures import experiment_10ch as fx

_DIFF_FIELDS = ("knowledge_ledger", "belief_ledger", "reader_ledger", "facts",
                "characters", "relationships", "inventory", "items")


def _changed(before, after) -> bool:
    return any(getattr(before, f) != getattr(after, f) for f in _DIFF_FIELDS)


def audit_run(run_dir: Path, chapters: int = 10) -> List[dict]:
    cfg = fx.make_config(chapters)
    store = StateStore(str(run_dir / "state" / "state.db"))
    log = EventLog(str(run_dir / "state" / "event.db"))
    rows: List[dict] = []
    for ch in range(1, chapters + 1):
        before = replay_to_chapter(store, log, Reducer(), cfg.story_id, ch - 1)
        contract = fx.contract_for(cfg.arc_contract, ch, before)
        after = replay_to_chapter(store, log, Reducer(), cfg.story_id, ch)
        committed = after.version > before.version or after.chapter_no >= ch
        rows.append({"chapter": ch,
                     "goal_type": contract.story_goal_type,
                     "declared": len(contract.must_change),
                     "committed": committed,
                     "changed": committed and _changed(before, after)})
    return rows


def summarize(rows: List[dict]) -> str:
    gen = [r for r in rows if r["committed"]]
    empty_declared = [r for r in rows if r["declared"] == 0]
    no_change = [r for r in gen if not r["changed"]]
    water = [r for r in empty_declared if r["committed"] and not r["changed"]]
    blocked = sorted({r["chapter"] for r in empty_declared})
    types = sorted({r["goal_type"] for r in empty_declared})
    return (f"规划期会被拒开工 {len(empty_declared)} 章（第 {blocked or '—'} 章，"
            f"goal_type={types or '—'}）｜"
            f"提交后状态毫无变化 {len(no_change)} 章｜"
            f"既没声明也没变化（真·水章）{len(water)} 章｜已提交 {len(gen)} 章")


def main(argv: None | List[str] = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(
        prog="python -m plot_engine.diff_audit",
        description="零模型调用：用盘上那条链算「每章必须有状态差异」这条规则的影响面")
    ap.add_argument("runs", nargs="+", help="采样目录（含 state/）")
    ns = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for spec in ns.runs:
        run = Path(spec)
        print(f"== {run.name}")
        try:
            print("   " + summarize(audit_run(run)))
        except Exception as e:                       # 链不在盘上就是要显式失败，不静默出 0
            print(f"   算不了：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
