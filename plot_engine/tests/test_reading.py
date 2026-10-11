"""阅读器与样章共用一份取料：正文剥机器标注，判定/修稿指引分栏，状态从读数合并进来。"""
from __future__ import annotations

from pathlib import Path

from plot_engine.reading import chapter_texts, paragraphs, read_run

DUMP = """# Chapter 5 — status=FAIL
trace_status=NEEDS_HUMAN
message=not committable: HARD=1
contract_version=1 rounds=3 required_events=['INFERS']

## Findings
- HARD H5.1: 必需事件 INFERS 数量不足（0<1）
- SOFT H5.6: 允许知识未建立

## 修稿指引
- H5.1｜必需事件 INFERS 数量不足（0<1） ⇒ 缺一个必需类型的事件

## Draft
他想起账册<!-- markup: 机器标注不该进正文 -->。

于是得出结论。

## Proposals
- （无）
"""


def _write(tmp_path: Path) -> Path:
    dump = tmp_path / "runx" / "dump"
    dump.mkdir(parents=True)
    (dump / "ch05.md").write_text(DUMP, encoding="utf-8")
    return tmp_path / "runx"


def test_chapter_texts_strips_markup_and_keeps_the_verdict_columns(tmp_path):
    c = chapter_texts(_write(tmp_path) / "dump")[5]
    assert c["text"] == "他想起账册。\n\n于是得出结论。"
    assert c["findings"] == ["HARD H5.1: 必需事件 INFERS 数量不足（0<1）",
                             "SOFT H5.6: 允许知识未建立"]
    assert c["guide"][0].startswith("H5.1｜")
    assert len(paragraphs(c["text"])) == 2          # 分段是阅读器的换行依据


def test_read_run_merges_status_counts_from_the_snapshot(tmp_path):
    run = read_run(_write(tmp_path))
    assert run["label"] == "runx" and run["generated"] == 1
    ch = run["chapters"][0]
    assert ch["status"] == "NEEDS_HUMAN" and ch["rounds"] == 3
    assert ch["text"].startswith("他想起账册")       # 判定与正文来自同一份快照
