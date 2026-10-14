# -*- coding: utf-8 -*-
"""钉密度脱敏重算（零 GPU）：v4d 三跑 45 个钉实例的死因分解 ⇒ 裁定 v3.6 走尺批还是契约批。

口径：对每章取**最后一轮** `## Proposals`（判终局 H5.1 的那一份），与夹具 mandatory 钉型对表：
- 型别缺失：钉型在终局 Proposals 完全不存在 ⇒ 抽取提示面洞；
- 在场未落账：钉型在场但未进账（终局仍 FAIL/ARC）⇒ 归因/方向杀（actor/fact 挂错或 reducer 语义）；
- 全灭：终局 Proposals 为空（`_junk.json` 可证 malformed_reply 吞章）⇒ 仪器解析面。

复现：.venv/Scripts/python.exe sampling/_probe_pinmask.py
局限：在场≠挂对（actor/fact 未校验，「修归因上界」是一阶）；OK 章不采样；rounds>0 章正文已被修稿换过。
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parent.parent

# 夹具 mandatory 钉型（experiment_10ch.py v4，_mandatory 默认=整步事件流）
PINS = {1: ["OBSERVES"], 2: ["READS", "BELIEVES"], 3: ["IS_TOLD", "SUSPECTS"],
        4: ["READS", "DOUBTS"], 5: ["OBSERVES", "SUSPECTS"], 6: ["IS_TOLD"],
        7: ["READS", "BELIEVES"], 8: [], 9: ["INFERS", "BELIEVES"],
        10: ["OBSERVES", "DOUBTS"]}
ARMS = ("v4d1", "v4d2", "v4d3")


def final_props(txt: str) -> set:
    m = re.search(r"## Proposals\n(.*?)(?=\n## |\Z)", txt, re.S)
    return set(re.findall(r"^- ([A-Z_]{3,12}) actor=", m.group(1), re.M)) if m else set()


def main() -> int:
    per = {}
    for d in ARMS:
        for c in range(1, 11):
            txt = (REPO / "sampling" / d / f"ch{c:02d}.md").read_text(encoding="utf-8")
            st = re.search(r"status=(\w+)", txt).group(1)
            if st == "OK" or not PINS[c]:
                continue
            pr = final_props(txt)
            miss = [t for t in PINS[c] if t not in pr]
            attr = [t for t in PINS[c] if t in pr]
            k = ("全灭" if not pr else "混合" if miss and attr else
                 "归因杀" if attr else "型别缺失")
            per[(d, c)] = (k, miss, attr)
    n_miss = sum(len(m) for _, m, _ in per.values())
    n_attr = sum(len(a) for _, _, a in per.values())
    n_dead = sum(len(PINS[c]) for (d, c), (k, _, _) in per.items() if k == "全灭")
    print(f"钉实例总数 {n_miss + n_attr + n_dead}｜型别缺失 {n_miss}"
          f"｜在场未落账 {n_attr}｜全灭章吞钉 {n_dead}")
    cm = Counter(t for _, m, _ in per.values() for t in m)
    ca = Counter(t for _, _, a in per.values() for t in a)
    print("缺席 by 类型:", dict(cm.most_common()))
    print("在场未落账 by 类型:", dict(ca.most_common()))
    for d in ARMS:
        rows = [(c, k, m, a) for (dd, c), (k, m, a) in per.items() if dd == d]
        resc = [c for c, k, m, a in rows if k == "归因杀"]
        print(f"{d}: " + " ".join(f"ch{c:02d}={k}(缺{m}/在{a})" for c, k, m, a in rows))
        print(f"{d} 修归因后E2上界: {(2+len(resc))/10:.0%} 可翻章 {resc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
