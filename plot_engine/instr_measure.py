"""W5 残余波动测量 + W6 2x2 对表（instr-fix-01 的真·交付物）。

用法（冻结 v4c 全语料、温度 0 由调用方保证，本模块只测不跑）：
- `double_run_report(run_a, run_b, ...)`：同车道连跑两遍 → 废卷率 / Jaccard 中位 /
  BELIEVES 检出稳定性 + 预登记门槛判定；
- `lane_table(local_rep, cloud_rep, ...)`：2x2 对表 + 预登记车道决策；
- `replay_junk(junk_path)`：W2 验收——_junk.json 历史坏输出离线回放（零采样）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence

from plot_engine.instr import (
    INSTR_VERSION,
    JACCARD_MED_MIN,
    WASTE_RATE_MAX,
    believes_keys,
    chapter_jaccard,
    check_w5_gate,
    decide_lane,
    decide_upgrade_path,
    instr_id_for_lane,
    median_jaccard,
    replay_junk_entries,
    waste_rate,
)


def waste_chapters(malformed: Sequence[dict]) -> set:
    """章级废卷章号：整章无可用条目（单跑 malformed_reply / 分段 chapter_empty）。

    段级 `segment_failed` / `segment_unparsable` 只废该段，不算章废（任务单 W2）。
    """
    return {b.get("chapter") for b in (malformed or [])
            if b.get("reason") in ("malformed_reply", "chapter_empty")
            and b.get("chapter") is not None}


def double_run_report(*, run_a: Dict[int, list], run_b: Dict[int, list],
                      malformed_a: Sequence[dict] = (),
                      malformed_b: Sequence[dict] = (),
                      merged_empty_a: Sequence[int] = (),
                      merged_empty_b: Sequence[int] = (),
                      probe_chapters: Sequence[int] = (),
                      instr: str = INSTR_VERSION) -> Dict[str, object]:
    chapters = sorted(set(run_a) | set(run_b))
    per_chapter = []
    believes_mismatch = []
    for ch in chapters:
        a, b = run_a.get(ch, []), run_b.get(ch, [])
        per_chapter.append({"chapter": ch, "jaccard": chapter_jaccard(a, b),
                            "n_a": len(a), "n_b": len(b)})
        if probe_chapters and ch in set(probe_chapters):
            if believes_keys(a) != believes_keys(b):
                believes_mismatch.append(ch)
    med = median_jaccard([chapter_jaccard(run_a.get(c, []), run_b.get(c, []))
                          for c in chapters])
    waste = waste_chapters([*(malformed_a or []), *(malformed_b or [])])
    waste |= set(merged_empty_a or []) | set(merged_empty_b or [])
    wr = waste_rate(len(waste), len(chapters))
    stable = not believes_mismatch
    gate = check_w5_gate(n_chapters=len(chapters), n_waste=len(waste),
                         pairs=[(run_a.get(c, []), run_b.get(c, [])) for c in chapters],
                         believes_stable=stable)
    return {"instr": instr, "chapters": len(chapters),
            "waste_chapters": sorted(waste), "waste_rate": wr,
            "jaccard_med": med, "per_chapter": per_chapter,
            "believes_stable": stable,
            "believes_mismatch_chapters": believes_mismatch,
            "thresholds": {"waste_lt": WASTE_RATE_MAX, "jaccard_med_ge": JACCARD_MED_MIN},
            "gate": gate,
            "upgrade_path": decide_upgrade_path(
                waste_ok=bool(gate["waste_ok"]), jaccard_ok=bool(gate["jaccard_ok"]),
                believes_ok=stable)}


def lane_cell(report: Dict[str, object], *, probe_recall: float,
              cost_per_chapter: float) -> Dict[str, object]:
    sizes = [c["n_a"] for c in report.get("per_chapter", [])]
    return {"waste_rate": report.get("waste_rate", 0.0),
            "jaccard_med": report.get("jaccard_med", 0.0),
            "mean_items": (sum(sizes) / len(sizes)) if sizes else 0.0,
            "recall": float(probe_recall or 0.0),
            "cost_per_chapter": float(cost_per_chapter or 0.0)}


def lane_table(local_report: Dict[str, object], cloud_report: Dict[str, object], *,
               local_recall: float = 0.0, cloud_recall: float = 0.0,
               local_cost: float = 0.0, cloud_cost: float = 0.0) -> Dict[str, object]:
    local = lane_cell(local_report, probe_recall=local_recall, cost_per_chapter=local_cost)
    local["jaccard_med"] = float(local_report.get("jaccard_med", 0.0))
    cloud = lane_cell(cloud_report, probe_recall=cloud_recall, cost_per_chapter=cloud_cost)
    cloud["jaccard_med"] = float(cloud_report.get("jaccard_med", 0.0))
    decision = decide_lane({"recall": local["recall"], "jaccard_med": local["jaccard_med"]},
                           {"recall": cloud["recall"], "jaccard_med": cloud["jaccard_med"]})
    return {"local": {**local, "instr": instr_id_for_lane("local")},
            "cloud": {**cloud, "instr": instr_id_for_lane("cloud")},
            "decision": decision,
            "note": "判据文本之争在 W5 云端数字落地前一律不再投入"}


def replay_junk(junk_path, parse_fn=None) -> Dict[str, object]:
    from plot_engine.llm_extract import extract_json_array
    path = Path(junk_path)
    try:
        # utf-8-sig 同时容纳带/不带 BOM 的 _junk.json（落档机器与回放机器常不同）
        entries = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (ValueError, OSError) as e:
        return {"junk": str(path), "error": str(e), "pass": False}
    fn = parse_fn or (lambda raw: ([1] if extract_json_array(raw) is not None else [], []))
    result = replay_junk_entries(entries or [], fn)
    return {"junk": str(path), "instr": INSTR_VERSION, **result}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="instr-v2 W5/W6 度量")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_r = sub.add_parser("replay-junk", help="W2：_junk.json 离线回放")
    p_r.add_argument("junk")
    p_r.add_argument("--out", default="")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = replay_junk(args.junk)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
