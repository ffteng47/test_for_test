"""一次命令把 N 个跑法收成一张表——替代「跑十次 metrics、抄十份数字进文档」。

为什么要有它：写基线文档的活其实不是判断，是**转录**：每个跑都要 `metrics` 一遍（一次一个目录）、
`fixture_audit` 一遍、`prose_audit` 一遍，再把三份人话输出手抄成 markdown 表格。抄的过程最容易出错
（本轮就抄出过「跨端点均值当同端点」的错），而且每抄一次就把一整段 dump 正文拉进上下文。
这里只输出**判据已经定义过的那几个数**，一跑一行，`--md` 直接出可粘贴的表——文档引用它，不再复述。

不动任何读数：E2/处置率走 `metrics`，归因列走 `fixture_audit`，文笔列走 `prose_audit`，
全是既有口径的并列呈现。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

from plot_engine.fixture_audit import revision_loop_chapters, unreachable_by_construction
from plot_engine.metrics import metrics_from_dump
from plot_engine.prose_audit import audit, chapter_texts_from

_SYMBOL = {"first_pass": "首", "rewrite_rescued": "救",
           "renegotiate_only": "继", "disposition": "处"}
_COLUMNS = ["跑法", "生成", "E2", "处置率", "首轮", "救回", "继", "判死",
            "待人工", "修订环章", "穿帮章", "章首同主语", "跨章重复", "tokens", "用时"]


def _prose(lines: List[str], want: str) -> str:
    """从 prose_audit 的人话里取那一格的数；该格没触发就是 0。"""
    for x in lines:
        if want in x:
            nums = re.findall(r"\d+", x)
            if want == "章首同主语":       # 「10 章里 8 次由同一个名字起笔」
                return f"{nums[1]}/{nums[0]}"
            return nums[0]
    return "0"


def _cost(run_dir: Path) -> tuple:
    """tokens / 用时在当时的 stdout 里，不在 dump 里——按 `<跑法>.log` 或 `<跑法>_log.txt` 找。"""
    for cand in (run_dir.parent / f"{run_dir.name}.log",
                 run_dir.parent / f"{run_dir.name}_log.txt", run_dir / "run.log"):
        if cand.exists():
            text = cand.read_text(encoding="utf-8", errors="replace")
            tok = re.search(r"tokens=(\d+)", text)
            sec = re.search(r"用时=(\d+)s", text)
            return (tok.group(1) if tok else "?", f"{sec.group(1)}s" if sec else "?")
    return ("?", "?")


def row(run_dir) -> Dict[str, str]:
    d = Path(run_dir)
    d = d / "dump" if (d / "dump").exists() else d
    m = metrics_from_dump(d)
    rev = revision_loop_chapters(d)
    prose = audit(chapter_texts_from(d.parent))
    arc = sum(1 for r in m.reads if r.trace_status == "ARC_CONFLICT")
    n = m.generated or 1
    return {"跑法": d.parent.name, "生成": str(m.generated), "E2": f"{m.clean_e2:.0%}",
            "处置率": f"{m.disposition_rate:.0%}", "首轮": str(m.count("first_pass")),
            "救回": str(m.count("rewrite_rescued")), "继": str(m.count("renegotiate_only")),
            "判死": str(arc), "待人工": str(m.count("disposition") - arc),
            "修订环章": ",".join(map(str, rev)) or "-",
            "穿帮章": str(sum(1 for x in prose if "穿帮" in x)),
            "章首同主语": _prose(prose, "章首同主语"),
            "跨章重复": _prose(prose, "跨章重复"),
            "tokens": _cost(d.parent)[0], "用时": _cost(d.parent)[1]}


def matrix(run_dirs: List[str]) -> List[Dict[str, str]]:
    """逐章终态横排：看方差落在哪一章，比看均值有用。"""
    out = []
    for run_dir in run_dirs:
        d = Path(run_dir)
        d = d / "dump" if (d / "dump").exists() else d
        m = metrics_from_dump(d)
        cells = {str(r.chapter_no): _SYMBOL[r.bucket] + ("✗" if r.trace_status == "ARC_CONFLICT" else "")
                 for r in m.reads}
        out.append({"跑法": d.parent.name, **{str(i): cells.get(str(i), "-") for i in range(1, 11)}})
    return out


def md(rows: List[Dict[str, str]], columns: List[str]) -> str:
    return "\n".join(["| " + " | ".join(columns) + " |",
                      "|" + "|".join(["---"] * len(columns)) + "|"]
                     + ["| " + " | ".join(r.get(c, "") for c in columns) + " |" for r in rows])


def main(argv: List[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    flags = [a for a in argv if a.startswith("--")]
    runs = [a for a in argv if not a.startswith("--")]
    cols = ([str(i) for i in range(1, 11)] + ["跑法"] if "--matrix" in flags else _COLUMNS)
    rows = matrix(runs) if "--matrix" in flags else [row(r) for r in runs]
    print(md(rows, ["跑法"] + cols[1:]) if "--matrix" in flags else md(rows, cols))
    bad = unreachable_by_construction()
    print(f"\n夹具不可达章（构造级，与模型无关）：{bad or '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
