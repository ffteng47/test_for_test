# Phase 1 T1b：人工处置章的重入闭环（06 §6 步 7「交人工」之后，07 §5–§9 一次提交）。
# 闸口 #2 认的是这条，不是 T1a 的导出：路由出去的章必须能被人改完后重新走一遍管道，
# 且 Replay 对账仍为 True。
import pathlib
import sys

from plot_engine.eventlog import EventLog
from plot_engine.experiment import run_experiment
from plot_engine.models.revision import RevisionPolicy
from plot_engine.replay import verify_parity
from plot_engine.rescue import rescue_chapter
from plot_engine.revision import RevisionLoop
from plot_engine.revision_actions import renegotiate_contract
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures"))
import experiment_10ch as fixture  # noqa: E402

NOW = fixture.NOW


def _setup(tmp_path, chapters=2, defects=None):
    """跑一个真有 NEEDS_HUMAN 章的实验：抽取里多写一条本章禁止的知识（H5.7），
    Writer 层的 `rewrite_scene` 没注册 ⇒ 循环判「要人接」并把它交出去。"""
    cfg = fixture.make_config(chapters)
    store, log = StateStore(str(tmp_path / "s.db")), EventLog(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    loop = RevisionLoop(policy=RevisionPolicy(), actions={
        "renegotiate_contract": renegotiate_contract(cfg.arc_contract, created_at=NOW)})
    routed = []
    report = run_experiment(
        cfg, store=store, log=log,
        chapter_source=fixture.build_source(defects or {2: "leak"}, cfg.arc_contract),
        scene_writer=fixture.dummy_writer, revision_loop=loop,
        on_chapter=lambda ch, rounds, out, trace: routed.append(
            (ch, getattr(trace, "final_status", None))))
    return cfg, store, log, report, routed


def test_routed_chapter_rescues_to_a_commit_with_parity(tmp_path):
    cfg, store, log, report, routed = _setup(tmp_path)
    ch, status = routed[-1]
    assert (ch, status) == (2, "NEEDS_HUMAN")          # 前置：这一章确实被路由出去了
    assert report.chapters_committed == 1                   # 只进了第 1 章

    cur = store.load_latest(cfg.story_id).state
    art = fixture.build_source({}, cfg.arc_contract)(ch, cur)   # 人工改后的最小稿
    out = rescue_chapter(store, log, cfg.story_id, art.contract, scene_plan=art.scene_plan,
                         draft=art.draft, rule_channel=art.rule_channel,
                         llm_channel=art.llm_channel)
    assert out.status == "OK", out.message
    assert verify_parity(store, log, Reducer(), cfg.story_id, ch)


def test_rescue_takes_frozen_human_edited_proposals(tmp_path):
    """人已经手工编辑过 Proposal 并冻结时，Stage-0 一步不跑（再抽取会把人的修改冲掉）。"""
    cfg, store, log, _, _ = _setup(tmp_path)
    cur = store.load_latest(cfg.story_id).state
    art = fixture.build_source({}, cfg.arc_contract)(2, cur)
    props = art.rule_channel(art.scene_plan, art.contract, cur)
    out = rescue_chapter(store, log, cfg.story_id, art.contract, scene_plan=art.scene_plan,
                         draft=art.draft, proposals=props)
    assert out.status == "OK", out.message


def test_rescue_refuses_a_chapter_that_is_not_the_chain_tip(tmp_path):
    """救援必须按章号顺序：章 2 已入库时再救章 1，是要把链尾整段重写，不是这里的事。"""
    cfg, store, log, _, _ = _setup(tmp_path)
    cur = store.load_latest(cfg.story_id).state
    art = fixture.build_source({}, cfg.arc_contract)(2, cur)
    assert rescue_chapter(store, log, cfg.story_id, art.contract, scene_plan=art.scene_plan,
                          draft=art.draft, rule_channel=art.rule_channel,
                          llm_channel=art.llm_channel).status == "OK"
    earlier = fixture.contract_for(cfg.arc_contract, 1, store.load_latest(cfg.story_id).state)
    try:
        rescue_chapter(store, log, cfg.story_id, earlier, draft="改过的第 1 章")
    except ValueError as e:
        assert "链尾" in str(e)
    else:
        raise AssertionError("非链尾章节应拒绝救援")
