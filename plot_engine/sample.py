"""一批采样跑完，先出一页**人能读的东西**（样章），再谈读数。

只读 dump：取每章**最终**那轮的 Draft（修订过就是修订后的稿子），剥掉机器标注
`<!-- ... -->`，按章号接成一篇。判定不进正文，收在开头的表里——读的人想看故事时
不该被 `H5.1` 挡住，想核账时一眼能找到章号。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from plot_engine.metrics import _section_body, metrics_from_dump

_MARKUP = re.compile(r"<!--.*?-->", re.S)


def _final_draft(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    head = next((ln for ln in lines[:3] if ln.startswith("trace_status=")), lines[0])
    body = "\n".join(_section_body(lines, "Draft")).strip()
    return _MARKUP.sub("", body).strip(), head


def render_sample(dump_dir: Path) -> str:
    m = metrics_from_dump(dump_dir)
    rows = [f"| {r.chapter_no} | {r.trace_status} | {r.rounds} | {'是' if r.bucket != 'disposition' else '否'} |"
            for r in m.reads]
    out = [f"# 样章｜{dump_dir.parent.name}（{m.generated} 章，机器终稿）",
           "",
           f"干净口径 E2 = {m.clean_e2:.1%}｜人工处置率 = {m.disposition_rate:.1%}",
           "",
           "| 章 | 终态 | 修订轮数 | 已提交 |",
           "|---|---|---|---|",
           *rows,
           "",
           "> 正文取自每章最后一轮的稿子；「已提交=否」的章照样能读，只是没过契约判据。",
           ""]
    for path in sorted(dump_dir.glob("ch*.md")):
        draft, head = _final_draft(path)
        out += [f"## {path.stem.upper()} — {head}", "", draft or "（本轮没有产出正文）", ""]
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
