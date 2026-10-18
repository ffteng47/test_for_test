"""D 族：章内逐字重复块（宿主直出零 LLM）。

v042 移交件（参照 Oh Story check-degeneration.js 逐行复读指纹）：
去空白标点后整行相等且双序列同步步进的连续块 ≥3 行×20 字。
v1 只逐字，微改写近重复留 v2（shingle）。
"""
from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from plot_engine.l3.models import ConsistencyCandidate

_WS_RE = re.compile(r"[\s　，。、；：？！…—·「」『』“”‘’（）()《》〈〉,.!?;:'\"\-]")


def find_dup_runs(body: Sequence[str], chapter: int,
                  min_run: int = 3, min_len: int = 20) -> List[ConsistencyCandidate]:
    seen, pairs = {}, []
    for i, ln in enumerate(body):
        n = _WS_RE.sub("", ln)
        if len(n) < min_len:
            continue
        if n in seen:
            pairs.append((seen[n], i))
        else:
            seen.setdefault(n, i)
    runs: List[List[int]] = []
    for a, b in pairs:
        if runs and a == runs[-1][0] + runs[-1][2] and b == runs[-1][1] + runs[-1][2]:
            runs[-1][2] += 1
        else:
            runs.append([a, b, 1])
    out: List[ConsistencyCandidate] = []
    for a, b, ln_ in runs:
        if ln_ < min_run:
            continue
        out.append(ConsistencyCandidate(
            family="D", chapter=chapter, rule_id="verbatim_dup_run",
            evidence_refs=[f"{a + 1}-{a + ln_}", f"{b + 1}-{b + ln_}"],
            detail=f"章内逐字重复块 {a + 1}-{a + ln_}行 ↔ {b + 1}-{b + ln_}行（共{ln_}行）"))
    return out
