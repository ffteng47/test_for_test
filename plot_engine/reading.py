"""阅读器里那条「章节 → 正文 → 判定」的取料路径，必须和 sample/viewer 用的是同一份。

三个出口（md / html）共享一份取料，否则样章和阅读器会各自漂走一个「最终稿」的定义：
这里定的都是**最后一轮**的稿子，判定收在旁边、不进正文。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from plot_engine.metrics import _section_body, metrics_from_dump

_MARKUP = re.compile(r"<!--.*?-->", re.S)
STATUS_CN = {"OK": "已提交", "NEEDS_HUMAN": "待人工", "ARC_CONFLICT": "契约冲突",
             "FAIL": "提交失败", "HALT": "停跑", "CONFLICT": "版本冲突",
             "IO_ERROR": "写入失败", "REPLAY_INCONSISTENT": "对账不一致",
             "DUPLICATE": "重复提交"}


def chapter_texts(dump_dir: Path) -> Dict[int, dict]:
    """章号 → {text, findings, guide}：正文剥机器标注，判定与修稿指引原样带着。"""
    out: Dict[int, dict] = {}
    for path in sorted(dump_dir.glob("ch*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        body = "\n".join(_section_body(lines, "Draft")).strip()
        out[int(re.search(r"(\d+)", path.stem).group(1))] = {
            "text": _MARKUP.sub("", body).strip(),
            "findings": [ln.lstrip("- ") for ln in _section_body(lines, "Findings")
                         if ln.strip()],
            "guide": [ln.lstrip("- ") for ln in _section_body(lines, "修稿指引")
                      if ln.strip()]}
    return out


def read_run(run_dir: Path) -> dict:
    """一个采样目录（含 dump/）→ 逐章读数 + 正文，两个出口共用。"""
    dump = run_dir if run_dir.name == "dump" else run_dir / "dump"
    m = metrics_from_dump(dump)
    chapters = chapter_texts(dump)
    for r in m.reads:
        chapters.setdefault(r.chapter_no, {"text": "", "findings": [], "guide": []}).update(
            {"status": r.trace_status, "rounds": r.rounds, "bucket": r.bucket})
    return {"label": dump.parent.name, "e2": f"{m.clean_e2:.0%}",
            "disp": f"{m.disposition_rate:.0%}", "generated": m.generated,
            "chapters": [dict(chapters[k], no=k) for k in sorted(chapters)]}


def paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
