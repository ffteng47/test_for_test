"""文笔层第 1 层「硬伤审计」：只查**事实性硬伤**，不评价好坏（`docs/phase1-merged-plan-final.md` §9.1）。

为什么先做审计而不是先做规则：判分线要 tff 定标才能进尺（P3），而穿帮、章首同构、同一件事反复讲
这三类不需要审美——它们是「读者会立刻看出来不对」的确定缺陷。这一版**只出报告、不进修订环**，
所以不动正在归档的 v3.2 三跑读数；等它抓到东西的量值得改尺时，再连 RuleId 一起接进 `validator.py`。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

# 修真/古风设定里不该出现的现代事物。这份表是**标定旋钮**：往里加词就等于加规则。
_ANACHRONISM = [
    "电话", "邮件", "电邮", "微信", "短信", "电脑", "手机", "摄像", "监控", "显微镜",
    "放大镜", "化学", "分子", "原子", "细菌", "病毒接", "医院", "手术", "麻醉",
    "汽车", "火车", "飞机", "电灯", "灯泡", "保险柜", "西装", "手表", "分钟", "秒表",
    "合同", "签名章", "投票", "开会", "会议室", "办公室", "经理", "公司", "员工",
]
# 章首同构：连续这么多章用同一个句式开头，就是模板痕迹，不是巧合。
_SAME_OPEN_LINE = 3
# 跨章重复的最小 n-gram 长度：短于这个就是「的了他」这类噪声。
_ECHO_GRAM = 12


def _openings(texts: Dict[int, str]) -> List[str]:
    return [texts[k][:12] for k in sorted(texts)]


def audit(texts: Dict[int, str]) -> List[str]:
    """章号→正文 ⇒ 人读得懂的硬伤清单（没有就返回空）。"""
    findings: List[str] = []

    for ch in sorted(texts):
        hits = sorted({w for w in _ANACHRONISM if w in texts[ch]})
        if hits:
            findings.append(f"第 {ch} 章 穿帮词：{'、'.join(hits)}")

    heads = _openings(texts)
    repeated = [h for h in dict.fromkeys(heads) if heads.count(h) >= _SAME_OPEN_LINE]
    for h in repeated:
        chs = [str(ch) for ch in sorted(texts) if texts[ch][:12] == h]
        findings.append(f"章首同构：{len(chs)} 章都以「{h}」起笔（第 {'、'.join(chs)} 章）")

    first_word = [re.match(r"\S{2,3}", texts[ch]).group(0)
                  for ch in sorted(texts) if texts[ch].strip()]
    same_lead = len(first_word) - len(set(first_word))
    if same_lead >= _SAME_OPEN_LINE:
        findings.append(f"章首同主语：{len(first_word)} 章里 {same_lead} 次由同一个名字起笔")

    seen: Dict[str, int] = {}
    for ch in sorted(texts):
        for gram in {m.group(0) for m in re.finditer(
                rf"[\u4e00-\u9fff]{{{_ECHO_GRAM}}}", texts[ch])}:
            seen.setdefault(gram, ch)
    echoed = [g for g, first in seen.items()
              if any(first != ch and g in texts[ch] for ch in texts)]
    if echoed:
        findings.append(f"跨章重复叙述：{len(echoed)} 段 ≥{_ECHO_GRAM} 字的原话被重复使用"
                        f"（例：「{echoed[0]}」）")
    return findings


def chapter_texts_from(run_dir: Path) -> Dict[int, str]:
    from plot_engine.reading import chapter_texts

    # 两种跑目录布局都认：dump/ 子目录（v32/v33 旧约定）或 chNN.md 直接落在跑目录（lv3 起）
    dump = run_dir if (run_dir.name == "dump" or list(run_dir.glob("ch*.md"))) else run_dir / "dump"
    return {k: v["text"] for k, v in chapter_texts(dump).items()}


def main(argv: None | List[str] = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m plot_engine.prose_audit",
                                 description="逐章文笔硬伤审计（不评价好坏，只报读者看得出的不对）")
    ap.add_argument("runs", nargs="+", help="采样目录（含 dump/）")
    ns = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for spec in ns.runs:
        run = Path(spec)
        print(f"== {run}")
        found = audit(chapter_texts_from(run))
        print("\n".join("  " + f for f in found) if found else "  无硬伤（只表示这三类规则没抓到）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
