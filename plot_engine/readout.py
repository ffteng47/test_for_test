"""一次命令把 N 个跑法收成一张表——替代「跑十次 metrics、抄十份数字进文档」。

为什么要有它：写基线文档的活其实不是判断，是**转录**：每个跑都要 `metrics` 一遍（一次一个目录）、
`fixture_audit` 一遍、`prose_audit` 一遍，再把三份人话输出手抄成 markdown 表格。抄的过程最容易出错
（本轮就抄出过「跨端点均值当同端点」的错），而且每抄一次就把一整段 dump 正文拉进上下文。
这里只输出**判据已经定义过的那几个数**，一跑一行，`--md` 直接出可粘贴的表——文档引用它，不再复述。

不动任何读数：E2/处置率走 `metrics`，归因列走 `fixture_audit`，文笔列走 `prose_audit`，
全是既有口径的并列呈现。「H5.1等价税」是 E22 裁定一的上界报告列——只从 dump 重读，
不改 E2、不进判据（口径与从宽处见 `_flippable` docstring）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

from plot_engine.fixture_audit import revision_loop_chapters, unreachable_by_construction
from plot_engine.metrics import metrics_from_dump, thrill_table
from plot_engine.models.contract import FIELD_EVENT_TYPES
from plot_engine.prose_audit import audit, chapter_texts_from

_SYMBOL = {"first_pass": "首", "rewrite_rescued": "救",
           "renegotiate_only": "继", "disposition": "处"}
_COLUMNS = ["跑法", "生成", "E2", "H5.1等价税", "处置率", "首轮", "救回", "继", "判死",
            "待人工", "修订环章", "穿帮章", "章首同主语", "跨章重复", "废卷率", "一致率",
            "tokens", "用时"]


def _waste_rate(run, d) -> str:
    """instr-v2 常设列：章级废卷率 = 废章 / 生成章（任务单 W5：30 章即 0 章）。

    章级废卷 = 整章无可用条目（`malformed_reply` 单跑路径 / `chapter_empty` 分段路径）。
    段级 `segment_failed` 只废该段、不废全章（任务单 W2 原话），不进章级分母；
    段内细节记 `segment_unparsable`，同样不混入章级。
    无 _junk 或无生成章记 "-"（旧跑法无此账，不硬填 0，避免把"没测"读成"全好"）。
    """
    from pathlib import Path as _P
    import json as _json
    junk = _P(d) / "_junk.json"
    if not junk.exists():
        alt = _P(run) / "_junk.json"
        junk = alt if alt.exists() else junk
    if not junk.exists():
        return "-"
    try:
        # utf-8-sig 同时容纳带/不带 BOM（旧目录常由别的机器/工具落盘）
        entries = _json.loads(junk.read_text(encoding="utf-8-sig", errors="replace"))
    except (ValueError, OSError):
        return "-"
    waste_ch = {e.get("chapter") for e in (entries or [])
                if e.get("reason") in ("malformed_reply", "chapter_empty")
                and e.get("chapter") is not None}
    gen = len(list(_P(d).glob("ch*.md"))) or 1
    return f"{len(waste_ch) / gen:.0%}"


def _consistency(run) -> str:
    """instr-v2 常设列：W5 双跑一致率（Jaccard 中位）。

    读 `<跑法>_fluctuation.json`（任务单"落档"：`instr_cli --out` 写这个文件）；
    无此文件记 "-"（没测 ≠ 0，不硬填 0）。
    """
    from pathlib import Path as _P
    import json as _json
    for cand in (_P(str(run) + "_fluctuation.json"), _P(run) / "fluctuation.json"):
        if cand.exists():
            try:
                data = _json.loads(cand.read_text(encoding="utf-8-sig",
                                                  errors="replace"))
                med = data.get("jaccard_med")
                return f"{float(med):.2f}" if med is not None else "-"
            except (ValueError, OSError, TypeError):
                return "-"
    return "-"


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


_TYPE_OF_FIELD = {t: f for f, ts in FIELD_EVENT_TYPES.items() for t in ts}
_SHORT_RE = re.compile(r"HARD H5\.1: 必需事件 (\w+) 数量不足")
_HARD_RE = re.compile(r"HARD ([\w.]+):")


def _flippable(path: Path) -> bool:
    """这章若把 H5.1 改按 field 等价类判定，会不会整章翻绿——**上界读法**，三条从宽：
    只看「HARD 里除 H5.1 别无他条」（软判据与待复核一概不管）、
    等价类型只要出现过就算补足（不核 minimum_count）、
    读的是当轮 Findings 与 Proposals（首轮过审的章本来就没有 H5.1 可翻）。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    hard = _HARD_RE.findall(text)
    if hard and set(hard) != {"H5.1"}:
        return False
    short = _SHORT_RE.findall(text)
    if not short:
        return False
    got = {ln[2:].split(" actor=")[0] for ln in text.splitlines()
           if ln.startswith("- ") and " actor=" in ln.split(" payload=")[0]}
    return all(any(t in got for t in FIELD_EVENT_TYPES[_TYPE_OF_FIELD[x]]) for x in short)


def _tax(d: Path, m) -> int:
    """不在 E2 分子里的章（继/处）中，H5.1 单类型判定的彩票税能吃掉几章。"""
    return sum(1 for r in m.reads if r.bucket != "first_pass"
               and _flippable(d / f"ch{r.chapter_no:02d}.md"))


def row(run_dir) -> Dict[str, str]:
    run = Path(run_dir)                       # 跑目录是标签/正文/用量的锚；dump 目录只喂 metrics
    d = run / "dump" if (run / "dump").exists() else run
    m = metrics_from_dump(d)
    rev = revision_loop_chapters(d)
    prose = audit(chapter_texts_from(run))
    arc = sum(1 for r in m.reads if r.trace_status == "ARC_CONFLICT")
    n = m.generated or 1
    tax = _tax(d, m)
    return {"跑法": run.name, "生成": str(m.generated), "E2": f"{m.clean_e2:.0%}",
            "H5.1等价税": f"{tax}（上界{(m.clean_e2 + tax / n):.0%}）",
            "处置率": f"{m.disposition_rate:.0%}", "首轮": str(m.count("first_pass")),
            "救回": str(m.count("rewrite_rescued")), "继": str(m.count("renegotiate_only")),
            "判死": str(arc), "待人工": str(m.count("disposition") - arc),
            "修订环章": ",".join(map(str, rev)) or "-",
            "穿帮章": str(sum(1 for x in prose if "穿帮" in x)),
            "章首同主语": _prose(prose, "章首同主语"),
            "跨章重复": _prose(prose, "跨章重复"),
            "废卷率": _waste_rate(run, d), "一致率": _consistency(run),
            "tokens": _cost(run)[0], "用时": _cost(run)[1]}


def matrix(run_dirs: List[str]) -> List[Dict[str, str]]:
    """逐章终态横排：看方差落在哪一章，比看均值有用。"""
    out = []
    for run_dir in run_dirs:
        run = Path(run_dir)
        d = run / "dump" if (run / "dump").exists() else run
        m = metrics_from_dump(d)
        cells = {str(r.chapter_no): _SYMBOL[r.bucket] + ("✗" if r.trace_status == "ARC_CONFLICT" else "")
                 for r in m.reads}
        out.append({"跑法": run.name, **{str(i): cells.get(str(i), "-") for i in range(1, 11)}})
    return out


def md(rows: List[Dict[str, str]], columns: List[str]) -> str:
    return "\n".join(["| " + " | ".join(columns) + " |",
                      "|" + "|".join(["---"] * len(columns)) + "|"]
                     + ["| " + " | ".join(r.get(c, "") for c in columns) + " |" for r in rows])


def main(argv: List[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    runs = [a for a in argv if not a.startswith("--")]
    if "--thrill" in argv:            # 爽点工程读数表（R8 #2 全-A：纯派生离线，不进闸不写账）
        fixture = next((a.split("=", 1)[1] for a in argv if a.startswith("--fixture")),
                       "experiment_10ch")
        for r in runs:
            d = Path(r) / "dump" if (Path(r) / "dump").exists() else Path(r)
            print(thrill_table(d, fixture=fixture), "\n")
        return 0
    matrix_mode = "--matrix" in argv
    if matrix_mode:
        print(md(matrix(runs), ["跑法"] + [str(i) for i in range(1, 11)]))
    else:
        print(md([row(r) for r in runs], _COLUMNS))
    bad = unreachable_by_construction()
    print(f"\n夹具不可达章（构造级，与模型无关）：{bad or '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
