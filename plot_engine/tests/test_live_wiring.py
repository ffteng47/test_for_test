# Task 4：真实模型接入实验管道（08 §3 tokens/cost/时长）+ 网络故障的可读出口
from plot_engine.eventlog import EventLog
from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint
from plot_engine.live import build_client, build_laned_source, build_live_source
from plot_engine.live import check_reachable
from plot_engine.models.experiment import ChapterArtifacts
from plot_engine.store import StateStore
from plot_engine.tests.fixtures import experiment_10ch as fx
from plot_engine.writer import compose_chapter_draft


def _client(n_replies: int = 40):
    """假 transport：writer 回三段正文，extract 回合法 JSON 数组。零网络。"""
    state = {"n": 0}

    def transport(url, payload, headers, timeout_s):
        state["n"] += 1
        sysmsg = payload["messages"][0]["content"]
        if "事件抽取器" in sysmsg:
            content = ('[{"event_type": "OBSERVES", "actor": "char_000001", '
                       '"target": "fact_000003", "payload": {"fact_id": "fact_000003"}}]')
        else:
            content = "张三凝视印章。\n\n印泥是干的。\n\n他听见身后有呼吸声。"
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    router = LlmRouter(endpoints={"writer": ModelEndpoint(model="m"),
                                  "extract": ModelEndpoint(model="m")})
    return LlmClient(router, transport=transport)


def _source(client, cfg):
    """逐章契约/场景 = 对**当前** State 派生（backlog #1：一份 Arc，十章各不相同）。"""
    return build_live_source(client,
                             contracts=lambda ch, cur: fx.contract_for(cfg.arc_contract, ch, cur),
                             plans=fx.plan_for)


def _harness(tmp_path, client, chapters=2):
    cfg = fx.make_config(chapters)
    store = StateStore(str(tmp_path / "state.db"))
    log = EventLog(str(tmp_path / "event.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    from plot_engine.experiment import run_experiment
    src = _source(client, cfg)
    rep = run_experiment(cfg, store=store, log=log, chapter_source=src,
                         scene_writer=_writer(client), llm_client=client)
    return cfg, store, log, rep


def _writer(client):
    from plot_engine.llm_writer import make_scene_writer
    return make_scene_writer(client)


def test_live_source_defers_draft_to_the_real_writer(tmp_path):
    client = _client()
    cfg = fx.make_config(1)
    src = _source(client, cfg)
    art = src(1, cfg.initial_state)
    assert isinstance(art, ChapterArtifacts)
    assert art.draft == "" and art.llm_channel is not None and art.rule_channel is None
    asm = compose_chapter_draft(art.scene_plan, art.contract, cfg.initial_state,
                                 _writer(client))
    assert "张三凝视印章。" in asm.draft
    assert asm.draft.count("<!-- hook:") == 1


def test_report_carries_real_tokens_cost_and_duration(tmp_path):
    cfg, store, log, rep = _harness(tmp_path, _client())
    assert rep.chapters_generated == 2
    assert rep.total_tokens > 0                      # 08 §3：真实模型必须记账
    assert rep.total_cost_usd == 0.0                 # 本地模型零边际成本
    assert rep.total_duration_ms >= 0


def test_offline_path_is_byte_for_byte_unchanged(tmp_path):
    """没有 llm_client → tokens/时长恒 0，与 Day 20–25 的离线夹具行为完全一致。"""
    from plot_engine.experiment import run_experiment
    cfg = fx.make_config(2)
    store = StateStore(str(tmp_path / "s2.db"))
    log = EventLog(str(tmp_path / "e2.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    rep = run_experiment(cfg, store=store, log=log,
                         chapter_source=fx.build_source(arc=cfg.arc_contract),
                         scene_writer=fx.dummy_writer)
    assert (rep.total_tokens, rep.total_duration_ms) == (0, 0)


def test_unreachable_endpoint_reports_a_readable_error_not_a_stack(monkeypatch, capsys):
    monkeypatch.setattr("plot_engine.live._get_json",
                        lambda url, timeout: (_ for _ in ()).throw(OSError("refused")))
    client = build_client({})
    ok, msg = check_reachable(client)
    assert ok is False and "不可达" in msg


def test_reachable_reports_model_names(monkeypatch):
    monkeypatch.setattr("plot_engine.live._get_json",
                        lambda url, timeout: {"data": [{"id": "qwen2.5:14b"}]})
    assert check_reachable(build_client({}))[0] is True


def test_build_client_from_config_dict_selects_router_roles():
    client = build_client({"writer": {"model": "qwen2.5:32b", "timeout_s": 900}})
    assert client.router.endpoints["writer"].model == "qwen2.5:32b"
    assert client.router.endpoints["writer"].timeout_s == 900
    assert client.router.roles() == ["writer"]


def test_live_source_keeps_channels_so_baddies_are_visible():
    """坏料只在通道里，跑完就丢 → 抽取质量无法归因（05 §9 I6）。"""
    client = _client()
    cfg = fx.make_config(1)
    src = _source(client, cfg)
    art = src(1, cfg.initial_state)
    art.llm_channel("正文", None, fx.contract_for(cfg.arc_contract, 1, cfg.initial_state),
                    cfg.initial_state)
    assert src.channels == [art.llm_channel]


def test_extraction_diagnostics_counts_proposals_and_bad_reasons():
    from plot_engine.live import extraction_diagnostics

    client = _client()
    cfg = fx.make_config(2)
    src = _source(client, cfg)
    state = cfg.initial_state
    for ch in (1, 2):
        src(ch, state).llm_channel(
            "正文", None, fx.contract_for(cfg.arc_contract, ch, state), state)
    diag = extraction_diagnostics(src.channels)
    assert diag["proposals"] == 2 and diag["malformed"] == {}


def test_build_live_source_can_hang_the_segmented_channel():
    """接线缺口回归：instr-v2 分段通道必须能从 build_live_source 挂上真跑路径。"""
    cfg = fx.make_config(1)
    src = build_live_source(
        _client(), contracts=lambda ch, cur: fx.contract_for(cfg.arc_contract, ch, cur),
        plans=fx.plan_for, use_segmented=True)
    art = src(1, cfg.initial_state)
    channel = art.llm_channel
    assert channel.instr_version == "instr-v2-local"
    channel("正文", None, fx.contract_for(cfg.arc_contract, 1, cfg.initial_state),
            cfg.initial_state)
    assert channel.segments_run >= 1
    assert src.channels == [channel]


def test_build_laned_source_stamps_the_cloud_lane_and_identity():
    """W6：云端车道挂同一套管道，但仪器戳与身份档案必须换成云的。"""
    cloud = LlmClient(LlmRouter(endpoints={
        "extract": ModelEndpoint(model="cloud-x",
                                 base_url="https://api.example/v1",
                                 usd_per_1k_tokens=0.002)}),
        transport=lambda *a: {"choices": [{"message": {"content": "[]"}}],
                              "usage": {}})
    cfg = fx.make_config(1)
    src = build_laned_source(
        _client(), cloud,
        contracts=lambda ch, cur: fx.contract_for(cfg.arc_contract, ch, cur),
        plans=fx.plan_for, lane="cloud")
    ch1 = src(1, cfg.initial_state).llm_channel
    assert ch1.instr_version == "instr-v2-cloud"
    assert ch1.lane_identity["model"] == "cloud-x"
    assert ch1.lane_identity["usd_per_1k_tokens"] == 0.002
    assert src.instr == "instr-v2-cloud"


def test_cli_lane_cloud_requires_cloud_config(capsys):
    """--lane cloud 却不给 --cloud-config ⇒ 拒绝，不拿默认本地端点顶替。"""
    import pytest
    from plot_engine.review import main
    with pytest.raises(SystemExit):
        main(["--live", "--lane", "cloud"])
    assert "cloud-config" in capsys.readouterr().err


def test_cli_instr_v2_reaches_the_live_run(monkeypatch, capsys):
    """接线缺口回归：--instr v2 必须真的换通道，而不是只能从测试调到。"""
    from plot_engine.review import main
    from plot_engine import review
    seen = {}

    def stub(chapters, model_config, **kw):
        seen.update(kw)
        return None, "端点说明", None
    monkeypatch.setattr(review, "_live_run", stub)
    assert main(["--live", "--instr", "v2"]) == 2
    assert seen["use_segmented"] is True and seen["lane"] == "local"
    assert seen["cloud_client"] is None
    assert "端点说明" in capsys.readouterr().out


def test_live_run_note_carries_the_instrument_stamp_separate_from_the_ruler(
        tmp_path, monkeypatch):
    """仪器戳与尺戳分开记账：run.log 首行同时有两枚戳，且互不覆盖。"""
    from plot_engine.review import _live_run
    monkeypatch.setattr("plot_engine.live.check_reachable",
                        lambda client: (True, "端点可用 models=m"))
    report, msg, diag = _live_run(2, {}, client=_client(), use_segmented=True,
                                  state_dir=str(tmp_path),
                                  dump_dir=str(tmp_path / "dump"))
    assert report is not None
    assert "抽取尺=v3.4-default-700-removed" in msg   # 尺戳已 bump（W4b 裁定后）
    assert "仪器=instr-v2-local" in msg                   # 仪器戳新增
    assert diag["instr"]["instr"] == "instr-v2-local"
    assert diag["instr"]["segments_run"] >= 1


def test_live_run_cloud_lane_without_cloud_client_is_refused():
    """配置错误先于网络报错（E26）：本测试**不打任何桩**——
    本地 11434 通不通都不该影响它，因为 cloud_client 缺失在验活之前就被拦下。"""
    from plot_engine.review import _live_run
    report, msg, _ = _live_run(2, {}, use_segmented=True, lane="cloud",
                               client=_client(), cloud_client=None)
    assert report is None and "cloud-config" in msg
