"""盲评工作表（`docs/style-acceptance-v1.1.md` §3）：把若干跑法的章打散、去掉出处，发给人读。

为什么单独做这一步：判定读数知道「哪章过了线」，人读的是**另一件事**——这章好不好看。
两个读数必须解耦，否则人会被 provenance 带着打分（看到 `bo_q3_14b` 就默认它比 `8b` 好读）。
所以这里刻意产出**两份文件**：工作表只给编号与正文，答案键单独一份、评分收齐前不许打开。

取章用普查不用抽样：手上全部章数就是分母，任何「挑几章来评」都是在替被评者选题。
两条下限（≥30 章、失败类 ≥15）不满足时直接拒绝出题，出一张不够格的表比不出表更坏。
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import List

MIN_CHAPTERS = 30
MIN_FAILURES = 15


def pool(run_dirs: List[Path]) -> List[dict]:
    from plot_engine.reading import read_run

    out: List[dict] = []
    for d in run_dirs:
        r = read_run(Path(d))
        out += [{"run": r["label"], "chapter": c["no"], "status": c["status"],
                 "text": c["text"]}
                for c in r["chapters"] if c.get("text")]
    return out


def build(run_dirs: List[Path], seed: int = 0) -> List[dict]:
    items = pool(run_dirs)
    failures = sum(1 for x in items if x["status"] != "OK")
    if len(items) < MIN_CHAPTERS:
        raise ValueError(f"只有 {len(items)} 章可评，盲评下限 {MIN_CHAPTERS} 章：给的跑法不够")
    if failures < MIN_FAILURES:
        raise ValueError(f"失败类只有 {failures} 章，下限 {MIN_FAILURES}：这张表全是过线的章，"
                         f"量不出「判死的章是不是真难看」那一格")
    random.Random(seed).shuffle(items)
    return [dict(x, blind_id=i + 1) for i, x in enumerate(items)]


def render_worksheet(items: List[dict]) -> str:
    head = ("# 盲评工作表\n\n"
            "读法：每章只读不查，读完立刻打「愿意付费读」这一列（是/否），再补一句为什么。\n"
            "**这里没有出处、没有判定状态**——那是答案键里的事，评分收齐前不要打开它。\n\n")
    return head + "\n".join(f"## {x['blind_id']:02d}\n\n{x['text']}\n" for x in items)


def render_key(items: List[dict]) -> str:
    rows = "\n".join(f"| {x['blind_id']:02d} | {x['run']} | {x['chapter']} | {x['status']} |"
                     for x in items)
    return ("# 答案键（评分收齐前勿开）\n\n| 盲评号 | 跑法 | 原章号 | 判定终态 |\n"
            "|---|---|---|---|\n" + rows + "\n")


def main(argv: None | List[str] = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m plot_engine.blind_review",
                                 description="把若干采样跑的章打散成一份无出处盲评表")
    ap.add_argument("runs", nargs="+", help="采样目录（含 dump/）")
    ap.add_argument("-o", "--out", default="docs/samples/blind-worksheet.md")
    ap.add_argument("--seed", type=int, default=0)
    ns = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    items = build([Path(r) for r in ns.runs], ns.seed)
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    key = out.with_name(out.stem + "-key.md")
    out.write_text(render_worksheet(items), encoding="utf-8")
    key.write_text(render_key(items), encoding="utf-8")
    print(f"盲评表 → {out}（{len(items)} 章，"
          f"失败类 {sum(1 for x in items if x['status'] != 'OK')} 章）｜答案键 → {key}"
          f"｜种子 {ns.seed}（换种子=换一份题，读数不可与旧种子并列）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
