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
                          chapter_source=fixture.build_source(defects),
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


def test_cli_live_prints_decision_sheet_with_real_token_accounting(monkeypatch, capsys):
    import plot_engine.live as live
    monkeypatch.setattr(live, "check_reachable", lambda c: (True, "可用模型: m"))
    monkeypatch.setattr(live, "build_client", lambda cfg: _fake_live_client())
    assert review_main(["--live", "--chapters", "2"]) == 0
    out = capsys.readouterr().out
    assert "可用模型: m" in out and "§8 退出条件" in out
    assert "生成 2 /" in out
    assert "tokens=" in out and "抽取产出" in out      # 08 §3 记账 + 坏料可见


def test_model_config_accepts_inline_json_and_file(tmp_path):
    from plot_engine.review import _read_model_config

    assert _read_model_config(None) == {}
    assert _read_model_config('{"writer": {"model": "m2"}}') == {"writer": {"model": "m2"}}
    p = tmp_path / "router.json"
    p.write_text('{"writer": {"base_url": "http://192.168.31.213:8000/v1"}}', encoding="utf-8")
    got = _read_model_config(f"@{p}")
    assert got["writer"]["base_url"].endswith(":8000/v1")     # 换 vLLM = 改配置，不改代码

