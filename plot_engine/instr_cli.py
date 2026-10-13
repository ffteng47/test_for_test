"""W5 双跑/2×2 报告生成器（`instr_measure` 的"跑"侧，供回放脚本调用）。

v4c 冻结语料的双跑由 `tools/instr_double_run.py` 落盘 proposal 到 JSON 后，
本模块读两份 run JSON 出 W5 报告；W6 2×2 由四份 JSON（本地×2、云端×2）出对表。

JSON 约定（avoid 内存对象耦合）：`{"chapters": {ch: [{"type","actor","target","fact","evidence"}, ...]}, "malformed": [{"reason","chapter"}], "tokens": int}`。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from plot_engine.instr import INSTR_VERSION
from plot_engine.instr_measure import double_run_report, lane_table
from plot_engine.models.proposal import EventProposal


def load_run(path) -> Dict[str, object]:
    """run JSON → {章号: [EventProposal], malformed, tokens}。

    只重放 **proposal 骨架**（event_type/actor/target/payload），用它算集合一致率；
    confidence/source_ref 不进一致率口径（W5 判的是"抽到了什么"）。
    """
    data = json.loads(Path(path).read_text(encoding="utf-8-sig", errors="replace"))
    by_ch: Dict[int, List[EventProposal]] = {}
    for ch, items in (data.get("chapters") or {}).items():
        props = []
        for i, it in enumerate(items or []):
            props.append(EventProposal(
                proposed_event_type=str(it.get("type")),
                actor=it.get("actor"), target=it.get("target"),
                chapter=int(ch), seq=i, payload=dict(it.get("payload") or {}),
                source_ref=it.get("source_ref", ""), extraction_method="llm",
                extraction_confidence=1000))
        by_ch[int(ch)] = props
    return {"props": by_ch, "malformed": list(data.get("malformed") or []),
            "tokens": int(data.get("tokens") or 0),
            "recall": float(data.get("recall") or 0.0)}


def report(runs: Sequence[Dict[str, object]], *, probe_chapters: Sequence[int] = (),
           n_chapters: Optional[int] = None) -> Dict[str, object]:
    """len(runs)==2 → W5 单车道报告；==4 → W6 2×2（本地×2、云端×2）。"""
    if len(runs) == 2:
        a, b = runs
        return double_run_report(
            run_a=a["props"], run_b=b["props"],
            malformed_a=a["malformed"], malformed_b=b["malformed"],
            probe_chapters=list(probe_chapters))
    if len(runs) == 4:
        la, lb, ca, cb = runs
        rep_l = double_run_report(run_a=la["props"], run_b=lb["props"],
                                  malformed_a=la["malformed"],
                                  malformed_b=lb["malformed"],
                                  probe_chapters=list(probe_chapters))
        rep_c = double_run_report(run_a=ca["props"], run_b=cb["props"],
                                  malformed_a=ca["malformed"],
                                  malformed_b=cb["malformed"],
                                  probe_chapters=list(probe_chapters))
        return lane_table(
            rep_l, rep_c,
            local_recall=float(la.get("recall") or 0.0),
            cloud_recall=float(ca.get("recall") or 0.0),
            # 单章抽取成本 = 两跑总 token / (章数 × 跑数)（任务单 W6 每格一格成本）
            local_cost=(la["tokens"] + lb["tokens"]) / max((n_chapters or 1) * 2, 1),
            cloud_cost=(ca["tokens"] + cb["tokens"]) / max((n_chapters or 1) * 2, 1))
    raise ValueError(f"需 2 份（W5）或 4 份（W6 2×2）run JSON，收到 {len(runs)} 份")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="W5/W6 报告：读 run JSON，出波动/对表报告")
    ap.add_argument("runs", nargs="+", help="2 份（W5）或 4 份（W6：本地1本地2云端1云端2）")
    ap.add_argument("--probes", default="", help="钉测探针章号，逗号分隔，如 2,3,9")
    ap.add_argument("--chapters", type=int, default=0, help="冻结语料章数（算成本/废卷率分母）")
    ap.add_argument("--out", help="落档路径（默认 stdout）")
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    runs = [load_run(p) for p in args.runs]
    probes = [int(x) for x in args.probes.split(",") if x.strip().isdigit()]
    rep = report(runs, probe_chapters=probes, n_chapters=args.chapters or None)
    text = json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已落档：{args.out}（仪器戳 {INSTR_VERSION}）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
