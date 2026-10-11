"""一批采样跑完，先出一页**人能读的东西**（样章），再谈读数。

只读 dump：取每章**最终**那轮的 Draft（修订过就是修订后的稿子），剥掉机器标注
`<!-- ... -->`，按章号接成一篇。判定不进正文，收在开头的表里——读的人想看故事时
不该被 `H5.1` 挡住，想核账时一眼能找到章号。
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from plot_engine.metrics import metrics_from_dump
from plot_engine.reading import chapter_texts


def render_sample(dump_dir: Path) -> str:
    m = metrics_from_dump(dump_dir)
    texts = chapter_texts(dump_dir)
    rows = [f"| {r.chapter_no} | {r.trace_status} | {r.rounds} | "
            f"{'是' if r.bucket != 'disposition' else '否'} |" for r in m.reads]
    out = [f"# 样章｜{dump_dir.parent.name}（{m.generated} 章，机器终稿）",
           "",
           f"干净口径 E2 = {m.clean_e2:.1%}｜人工处置率 = {m.disposition_rate:.1%}",
           "",
           "| 章 | 终态 | 修订轮数 | 已提交 |",
           "|---|---|---|---|",
           *rows,
           "",
           "> 正文取自每章最后一轮的稿子，机器标注已剥除；「已提交=否」的章照样能读，"
           "只是没过契约判据。",
           ""]
    for r in m.reads:
        body = texts.get(r.chapter_no, {}).get("text", "")
        out += [f"## 第 {r.chapter_no} 章 — {r.trace_status}（修订 {r.rounds} 轮）", "",
                body or "（本轮没有产出正文）", ""]
    return "\n".join(out)


def main(argv: List[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m plot_engine.sample",
                                 description="从逐章快照出一页人读的样章")
    ap.add_argument("dump_dir")
    ap.add_argument("-o", "--out", default=None, help="默认写到 <dump_dir>/../sample.md")
    ns = ap.parse_args(argv)

    dump = Path(ns.dump_dir)
    out_path = Path(ns.out) if ns.out else dump.parent / "sample.md"
    out_path.write_text(render_sample(dump), encoding="utf-8")
    print(f"样章 → {out_path}（{out_path.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
