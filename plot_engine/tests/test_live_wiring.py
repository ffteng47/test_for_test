# Task 4：真实模型接入实验管道（08 §3 tokens/cost/时长）+ 网络故障的可读出口
from plot_engine.eventlog import EventLog
from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint
from plot_engine.live import build_client, build_live_source, check_reachable
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


def _harness(tmp_path, client, chapters=2):
    cfg = fx.make_config(chapters)
    store = StateStore(str(tmp_path / "state.db"))
    log = EventLog(str(tmp_path / "event.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    from plot_engine.experiment import run_experiment
    src = build_live_source(client, contracts=fx.contract_for, plans=fx.plan_for)
    rep = run_experiment(cfg, store=store, log=log, chapter_source=src,
                         scene_writer=_writer(client), llm_client=client)
    return cfg, store, log, rep


def _writer(client):
    from plot_engine.llm_writer import make_scene_writer
    return make_scene_writer(client)


def test_live_source_defers_draft_to_the_real_writer(tmp_path):
    client = _client()
    src = build_live_source(client, contracts=fx.contract_for, plans=fx.plan_for)
    art = src(1, fx.make_config(1).initial_state)
    assert isinstance(art, ChapterArtifacts)
    assert art.draft == "" and art.llm_channel is not None and art.rule_channel is None
    asm = compose_chapter_draft(art.scene_plan, art.contract,
                                 fx.make_config(1).initial_state, _writer(client))
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
    rep = run_experiment(cfg, store=store, log=log, chapter_source=fx.build_source(),
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
    src = build_live_source(client, contracts=fx.contract_for, plans=fx.plan_for)
    art = src(1, fx.make_config(1).initial_state)
    art.llm_channel("正文", None, fx.contract_for(1), fx.make_config(1).initial_state)
    assert src.channels == [art.llm_channel]


def test_extraction_diagnostics_counts_proposals_and_bad_reasons():
    from plot_engine.live import extraction_diagnostics

    client = _client()
    src = build_live_source(client, contracts=fx.contract_for, plans=fx.plan_for)
    state = fx.make_config(1).initial_state
    src(1, state).llm_channel("正文", None, fx.contract_for(1), state)
    src(2, state).llm_channel("正文", None, fx.contract_for(2), state)
    diag = extraction_diagnostics(src.channels)
    assert diag["proposals"] == 2 and diag["malformed"] == {}
