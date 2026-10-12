"""归因两列（零模型调用，E2 原数不动）：**夹具不可达章** 与 **修订环归属章**。

为什么要住在仓库里：控制臂 5 个未决章里 3 个是 H5.3，v3.2 三跑 likewise——一块不属于模型的固定
缺陷混在 E2 里，×3 只会把它测得更精确。这两列把它单独称出来，读的是输入面与修订环，不是模型。

- 第一列是**确定性**的：`must_change.expected_value` 超出本章事件类型能产生的最高档
  （03 §4.3/§5.1 的 reducer 上限 OBSERVES/READS→known、IS_TOLD→believed、INFERS→suspected；
  BELIEVES→believes、SUSPECTS→suspects、DOUBTS→doubts）。读 `build_arc` 即可，不看正文。
- 第二列读 dump：终轮 Findings 由 H5.3 主导的章（must_change 没有实现事件兑现＝修订环在烧轮，
  与 06 §4.3 的 W1 同源）。

两列都**不进 E1–E6/G1–G4**，只并列呈现（同 `prose_audit`、`diff_audit` 的位置）。
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

from plot_engine.metrics import metrics_from_dump
from plot_engine.tests.fixtures.experiment_10ch import build_arc

# field → 事件类型能达到的最高档（reducer 上限，不是提示词里的说法）
_CAPS = {"knowledge": {"OBSERVES": "known", "READS": "known",
                       "IS_TOLD": "believed", "INFERS": "suspected"},
         "belief": {"BELIEVES": "believes", "SUSPECTS": "suspects", "DOUBTS": "doubts"}}


def unreachable_by_construction(chapters: int = 10) -> Dict[int, List[str]]:
    """章号 → 不可达说明。空字典＝夹具的期望值全部落在本章事件类型的上限之内。"""
    out: Dict[int, List[str]] = {}
    for beat in build_arc(chapters).reader_beats:
        types = {e["event_type"] for e in beat["required_events"]}
        bad = []
        for c in beat["must_change"]:
            table = _CAPS.get(c["field"])
            if table is None:                      # CHANGES/RELATIONSHIP/ITEM 等字段不在这张表里，不判
                continue
            if c["expected_value"] not in {table.get(t) for t in types}:
                reach = sorted({table[t] for t in types if t in table}) or ["无同类事件"]
                bad.append(f"{c['character_id']}.{c['field']}→{c['expected_value']}"
                           f"（本章 {sorted(types)} 最高只到 {'/'.join(reach)}）")
        if bad:
            out[beat["chapter_no"]] = bad
    return out


def revision_loop_chapters(dump_dir) -> List[int]:
    """末轮修订规则由 H5.3 主导的未决章——修订环在原地烧轮的签名（must_change 失去实现事件，06 W1）。"""
    out = []
    for r in metrics_from_dump(dump_dir).reads:
        if r.bucket != "disposition":
            continue
        text = (Path(dump_dir) / f"ch{r.chapter_no:02d}.md")
        if not text.exists():
            continue
        rules = re.findall(r"rules=([\w.,]+)", text.read_text(encoding="utf-8"))
        fired = Counter(x for rnd in rules for x in rnd.split(","))
        if fired.get("H5.3", 0) and fired.get("H5.3", 0) >= max(
                v for k, v in fired.items() if k != "ARC_CONFLICT"):
            out.append(r.chapter_no)
    return out


def main(argv: List[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unreach = unreachable_by_construction()
    print("夹具不可达章（构造即不可达，与模型无关）："
          + ("".join(f"\n  第 {ch} 章 {'、'.join(v)}" for ch, v in sorted(unreach.items()))
             or "无"))
    for d in argv:
        p = Path(d) / "dump" if (Path(d) / "dump").exists() else Path(d)
        m = metrics_from_dump(p)
        n = m.generated or 1
        rev = revision_loop_chapters(p)
        arc = [r.chapter_no for r in m.reads if r.trace_status == "ARC_CONFLICT"]
        other = [r.chapter_no for r in m.reads
                 if r.bucket == "disposition" and r.chapter_no not in rev and r.chapter_no not in arc]
        print(f"{p.parent.name}：生成 {m.generated}｜E2 {m.clean_e2:.0%}（不变）"
              f"｜修订环归属 {len(rev)} 章 {rev}｜Arc 判死 {len(arc)} 章 {arc}"
              f"｜其余未决 {len(other)} 章 {other}"
              f"｜夹具硬伤占比 {len(rev) / n:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
