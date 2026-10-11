"""§7.2 反事实回放的两条纪律：提示词只在冻结面**后面**加长；回放一步不落盘。"""
from __future__ import annotations

import types

from plot_engine.counterfactual import (dump_draft, dump_hard, improved_extract_prompt,
                                        replay_chapter)
from plot_engine.eventlog import EventLog
from plot_engine.llm_extract import extract_prompt
from plot_engine.store import StateStore
from plot_engine.tests.fixtures import experiment_10ch as fx


def _contract():
    return types.SimpleNamespace(knowledge_forbidden=[], chapter_no=1)


def test_improved_prompt_is_the_frozen_prompt_plus_the_two_face_rules():
    draft = "1. 他把印章凑到灯下。他想起账册上记的是纯红朱砂——这印是伪造的。"
    frozen = extract_prompt(draft, None, _contract(), None)[0]["content"]
    improved = improved_extract_prompt(draft, None, _contract(), None)[0]["content"]
    assert improved.startswith(frozen)                      # 冻结面一字没改
    assert "必须单独给一条 INFERS" in improved              # 脸一：类型漏抽
    assert "conclusion_fact_id = 他新推出的那条结论" in improved
    assert "该角色由此获得或改变的那条事实" in improved      # 脸二：target 挂错


def test_dump_parsers_read_the_snapshot_format(tmp_path):
    path = tmp_path / "ch01.md"
    path.write_text(
        "# Chapter 1 — status=FAIL\ntrace_status=NEEDS_HUMAN\n\n"
        "## Findings\n- HARD H5.1: 必需事件 INFERS 数量不足（0<1）\n\n"
        "## Draft\n他想起账册。\n\n## Proposals\n- （无）\n", encoding="utf-8")
    assert dump_draft(path) == "他想起账册。"
    assert dump_hard(path) == ["H5.1: 必需事件 INFERS 数量不足（0<1）"]


def test_replay_is_side_effect_free_and_only_swaps_the_channel(tmp_path):
    cfg = fx.make_config(1)
    store = StateStore(str(tmp_path / "state.db"))
    log = EventLog(str(tmp_path / "event.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    before = store.load_latest(cfg.story_id).version
    contract = fx.contract_for(cfg.arc_contract, 1, cfg.initial_state)

    after = replay_chapter(store, log, cfg.story_id, 1, contract, "正文。",
                           lambda *a: [])
    assert any("H5.1" in line for line in after)            # 空通道 ⇒ 必需事件判不足
    assert store.load_latest(cfg.story_id).version == before  # 一条 event 也没落盘
