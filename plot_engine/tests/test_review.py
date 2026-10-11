# Day 23-25 Architecture Review 决策单（08 §6/§7/§8）：只读、不改架构
import json
import pathlib
import sys
import tempfile

import pytest

from plot_engine.eventlog import EventLog
from plot_engine.experiment import run_experiment
from plot_engine.review import (
    FAILURE_EXTRACTION, FAILURE_WRITER_VALIDATOR, FAILURE_ARCH_BLOCKER,
    architecture_review, main as review_main, render_review_text,
)
from plot_engine.store import StateStore

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures"))
import experiment_10ch as fixture  # noqa: E402


def _report(tmp_path, defects, suffix=""):
    cfg = fixture.make_config(10)
    store = StateStore(str(tmp_path / f"s{suffix}.db"))
    log = EventLog(str(tmp_path / f"e{suffix}.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    return run_experiment(cfg, store=store, log=log,
                          chapter_source=fixture.build_source(defects, cfg.arc_contract),
                          scene_writer=fixture.dummy_writer)


def test_healthy_run_is_not_phase0_blocking(tmp_path):
    sheet = architecture_review(_report(tmp_path, {}))
    assert sheet["exit_conditions"]["E1"] is True
    assert sheet["freeze_gate"]["may_change_architecture"] is False
    assert sheet["failure_classes"][FAILURE_ARCH_BLOCKER]["count"] == 0
    # 干净批次不该冒出 extraction/writer 类失败
    assert sheet["failure_classes"][FAILURE_EXTRACTION]["count"] == 0


def test_dead_actor_classified_as_writer_validator(tmp_path):
    sheet = architecture_review(_report(tmp_path, {6: "dead"}))
    cls = sheet["failure_classes"][FAILURE_WRITER_VALIDATOR]
    assert cls["count"] >= 1 and "H1.1" in cls["rule_ids"]


def test_replay_break_is_architecture_blocker_and_g2(tmp_path):
    rep = _report(tmp_path, {})
    rep = rep.model_copy(update={"replay_mismatch_chapters": [5], "replay_consistency": False})
    sheet = architecture_review(rep)
    assert sheet["failure_classes"][FAILURE_ARCH_BLOCKER]["count"] >= 1
    assert sheet["freeze_gate"]["G2_architecture_blocker"] is True
    assert sheet["freeze_gate"]["may_change_architecture"] is True


def test_sheet_is_json_serializable_and_text_renders(tmp_path):
    sheet = architecture_review(_report(tmp_path, {2: "leak", 7: "dead"}))
    assert json.loads(json.dumps(sheet, ensure_ascii=False)) == sheet
    text = render_review_text(sheet)
    assert "§6 失败分类" in text and "§7 架构冻结闸" in text and "§8 退出条件" in text


# —— `python -m plot_engine.review` 入口：必须有输出，且只写临时目录
def test_cli_prints_decision_sheet(capsys):
    assert review_main([]) == 0
    out = capsys.readouterr().out
    assert "生成 10 / 提交 10" in out
    assert "§6 失败分类" in out and "§8 退出条件" in out
    # 06 已接入：离线演练带 Revision 循环 → E3 可判，不再是 N/A
    assert "Revision：需修 0 章 / 最多 0 轮 / 修复率 1.00" in out
    assert "E3: True" in out


def test_cli_defect_flag_shows_failure_class(capsys):
    assert review_main(["--chapters", "3", "--defect", "2:leak"]) == 0
    out = capsys.readouterr().out
    assert "未决 [2]" in out
    assert "Revision：需修 1 章" in out             # 2 章进过修订循环


def test_cli_rejects_unknown_defect_kind(capsys):
    with pytest.raises(SystemExit):
        review_main(["--defect", "2:typo"])
    assert "leak|dead" in capsys.readouterr().err


# —— --live：端点不通必须早退，绝不能烧掉 45 分钟 GPU 预算
def _fake_live_client():
    from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint

    def transport(url, payload, headers, timeout_s):
        sysmsg = payload["messages"][0]["content"]
        content = ('[{"event_type": "OBSERVES", "actor": "char_000001", '
                   '"target": "fact_000003", "payload": {"fact_id": "fact_000003"}}]'
                   if "事件抽取器" in sysmsg else
                   "张三凝视印章。\n\n印泥是干的。\n\n他听见身后有呼吸声。")
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    return LlmClient(LlmRouter(endpoints={"writer": ModelEndpoint(model="m"),
                                          "extract": ModelEndpoint(model="m")}),
                     transport=transport)


def test_cli_live_reports_unreachable_endpoint_and_exits_2(monkeypatch, capsys):
    import plot_engine.live as live
    monkeypatch.setattr(live, "check_reachable", lambda c: (False, "模型端点不可达：boom"))
    monkeypatch.setattr(live, "build_client", lambda cfg: _fake_live_client())
    assert review_main(["--live", "--chapters", "1"]) == 2
    assert "不可达" in capsys.readouterr().out


def test_mid_run_model_failure_is_one_readable_line_not_a_stack(tmp_path, monkeypatch, capsys):
    """`check_reachable` 只保证开工前那一刻通：跑一半 500（服务器 Ollama 坏掉就是这样）
    也必须给人一句话 + 已落盘的快照目录，而不是把 traceback 撒在 30 分钟的输出后面。"""
    import plot_engine.live as live
    from plot_engine.llm import LlmUnavailable

    def boom(url, payload, headers, timeout_s):
        raise LlmUnavailable(f"{url} → HTTP 500: llama-server binary not found")

    client = _fake_live_client()
    client._transport = boom
    monkeypatch.setattr(live, "check_reachable", lambda c: (True, "ok"))
    monkeypatch.setattr(live, "build_client", lambda cfg: client)
    dumps = tmp_path / "d"
    assert review_main(["--live", "--chapters", "2", "--dump-dir", str(dumps)]) == 2
    out = capsys.readouterr().out
    assert "中途" in out and "Traceback" not in out and "HTTP 500" in out


def test_cli_live_prints_decision_sheet_with_real_token_accounting(monkeypatch, capsys):
    import plot_engine.live as live
    monkeypatch.setattr(live, "check_reachable", lambda c: (True, "可用模型: m"))
    monkeypatch.setattr(live, "build_client", lambda cfg: _fake_live_client())
    assert review_main(["--live", "--chapters", "2"]) == 0
    out = capsys.readouterr().out
    assert "可用模型: m" in out and "§8 退出条件" in out
    assert "生成 2 /" in out
    assert "tokens=" in out and "抽取产出" in out      # 08 §3 记账 + 坏料可见


def test_cli_live_dumps_drafts_and_proposals_for_triage(tmp_path, monkeypatch):
    """失败章不进 State：唯一能区分「模型没写」与「抽取漏了」的证据就是这份逐章快照。"""
    import plot_engine.live as live
    monkeypatch.setattr(live, "check_reachable", lambda c: (True, "ok"))
    monkeypatch.setattr(live, "build_client", lambda cfg: _fake_live_client())
    assert review_main(["--live", "--chapters", "2", "--dump-dir", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.glob("ch*.md")) == ["ch01.md", "ch02.md"]
    text = (tmp_path / "ch01.md").read_text(encoding="utf-8")
    assert "status=" in text and "## Draft" in text and "## Proposals" in text
    assert "OBSERVES" in text
    # 06 §4.2 的重议只能从这份快照看出来（08 §3 报告字段是逐字表，不许加字段）
    assert "contract_version=1" in text


def test_model_config_accepts_inline_json_and_file(tmp_path):
    from plot_engine.review import _read_model_config

    assert _read_model_config(None) == {}
    assert _read_model_config('{"writer": {"model": "m2"}}') == {"writer": {"model": "m2"}}
    p = tmp_path / "router.json"
    p.write_text('{"writer": {"base_url": "http://192.168.31.213:8000/v1"}}', encoding="utf-8")
    got = _read_model_config(f"@{p}")
    assert got["writer"]["base_url"].endswith(":8000/v1")     # 换 vLLM = 改配置，不改代码



def test_chapter_dump_records_arc_conflict_without_a_single_round(tmp_path):
    """契约没派生出来的章也要有快照（08 §10 I3）：正文没有，异常消息就是全部证据。"""
    from plot_engine.review import _write_chapter_dump

    _write_chapter_dump(tmp_path, 2, [], "第 2 章事实同时 allowed/forbidden：fact_000001", None)
    text = (tmp_path / "ch02.md").read_text(encoding="utf-8")
    assert "status=ARC_CONFLICT" in text and "allowed/forbidden" in text


def test_dump_header_carries_the_trace_status_separately(tmp_path):
    """T1a：人工终态只存在于 trace 上。`status=` 是 07 §4.1 的 CommitStatus 枚举（没有
    NEEDS_HUMAN），只从它数「要不要人接」会把已路由给人的章读成 0——Phase 0 把 9 章读成
    0 章就是这么来的。所以头部必须两行并列，报告从 trace_status 数处置章。"""
    import types

    from plot_engine.models.revision import RevisionTrace
    from plot_engine.review import _write_chapter_dump

    ctx = types.SimpleNamespace(draft="张三凝视印章。",
                                contract=types.SimpleNamespace(version=1, required_events=[]))
    out = types.SimpleNamespace(status="FAIL", message="FAIL", validation=None, consistency=[])
    _write_chapter_dump(tmp_path, 3, [(ctx, [])], out,
                        RevisionTrace(story_id="s1", chapter_no=3, rounds=3, needs_human=True,
                                      final_status="NEEDS_HUMAN"))
    head = (tmp_path / "ch03.md").read_text(encoding="utf-8").splitlines()
    assert head[0] == "# Chapter 3 — status=FAIL"
    assert head[1] == "trace_status=NEEDS_HUMAN"


def test_render_lists_per_chapter_revision_rounds(tmp_path):
    """聚合值（需修几章 / 最多几轮）盖住了「修订烧在哪一章」，Review 会要的是逐章那一行。"""
    rep = _report(tmp_path, {}).model_copy(
        update={"revision_rounds": {ch: (2 if ch == 3 else 0) for ch in range(1, 11)}})
    text = render_review_text(architecture_review(rep))
    assert "逐章轮数：" in text and "3:2" in text and "1:0" in text


def test_revision_round_rewrites_are_visible_in_the_dump(tmp_path):
    """批次 4 路由 + 批次 5 取证的联合验收：注入 H5.3 类失败（必需事件没写出来）后，
    dump 里 round 1 的动作必须是 renegotiate_contract、最终契约版本已经涨上去，
    而第 0 轮的正文与抽取产物没被最终稿盖掉——「重议真的发生过」只能从这份快照看出来。
    第 2 章不是拐点章，落空的 OBSERVES 属于作者自订 ⇒ 可放宽（拐点的 1/5/9 会直接 fail-fast）。
    """
    from plot_engine.eventlog import EventLog
    from plot_engine.experiment import run_experiment
    from plot_engine.models.revision import RevisionPolicy
    from plot_engine.revision import RevisionLoop
    from plot_engine.revision_actions import renegotiate_contract
    from plot_engine.review import _write_chapter_dump
    from plot_engine.store import StateStore

    cfg = fixture.make_config(5)
    store, log = StateStore(str(tmp_path / "s.db")), EventLog(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    loop = RevisionLoop(policy=RevisionPolicy(), actions={
        "renegotiate_contract": renegotiate_contract(cfg.arc_contract,
                                                    created_at="2026-10-10T00:00:00Z")})
    dumps = tmp_path / "d"
    run_experiment(cfg, store=store, log=log,
                   chapter_source=fixture.build_source({2: "no_obs"}, cfg.arc_contract),
                   scene_writer=fixture.dummy_writer, revision_loop=loop,
                   on_chapter=lambda ch, rounds, out, trace: _write_chapter_dump(
                       dumps, ch, rounds, out, trace))
    text = (dumps / "ch02.md").read_text(encoding="utf-8")
    assert "- round 1 level=contract" in text and "action=renegotiate_contract" in text
    assert "## Revision" in text
    assert "contract_version=1 rounds=0" not in text         # 头部用的是最终一轮的 ctx
    assert "## Round 0（contract_version=1）" in text          # 第 0 轮另起一段留档
    assert "## Revision" not in (dumps / "ch01.md").read_text(encoding="utf-8")
