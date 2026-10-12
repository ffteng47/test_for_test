# 08 §2 model_router_config 落地：LLM 可配置 + 本地优先（数据不出机器）
import urllib.error

import pytest

from plot_engine.llm import (LlmClient, LlmRouter, LlmUnavailable, ModelEndpoint,
                             _urllib_transport)


def _fake_transport(replies):
    """注入 transport：测试零网络。记录请求，按次序返回 replies。"""
    seen = []
    it = iter(replies)

    def transport(url, payload, headers, timeout_s):
        seen.append((url, payload, headers, timeout_s))
        return next(it)
    return transport, seen


def test_default_router_is_local_ollama_and_needs_no_key():
    r = LlmRouter.default()
    ep = r.endpoints["writer"]
    assert ep.base_url.startswith("http://127.0.0.1:")      # 默认本地，不指向任何公网
    assert ep.api_key is None
    assert r.roles() == ["extract", "plan", "writer"]


def test_each_role_can_point_at_a_different_model():
    r = LlmRouter(endpoints={
        "writer": ModelEndpoint(model="qwen2.5:14b"),
        "extract": ModelEndpoint(model="qwen2.5:7b", max_tokens=600),
        "plan": ModelEndpoint(model="qwen2.5:14b", temperature=300)})
    assert r.endpoints["extract"].model == "qwen2.5:7b"
    assert r.endpoints["plan"].temperature == 300


def test_complete_posts_openai_shape_and_returns_content_and_usage():
    transport, seen = _fake_transport([
        {"choices": [{"message": {"content": "张三凝视印章。"}}],
         "usage": {"prompt_tokens": 120, "completion_tokens": 30}}])
    c = LlmClient(LlmRouter.default(), transport=transport)
    text, usage = c.complete("writer", [{"role": "user", "content": "写第一章"}])
    url, payload, _headers, _timeout = seen[0]
    assert url.endswith("/chat/completions")                 # OpenAI 兼容：Ollama/vLLM 同一套
    assert payload["model"] == "qwen2.5:14b"
    assert payload["messages"][0]["content"] == "写第一章"
    assert text == "张三凝视印章。"
    assert (usage.prompt_tokens, usage.completion_tokens) == (120, 30)


def test_temperature_is_fixed_point_int_over_the_wire():
    """05 §5.5 精神：温度也用 ×1000 定点，避免 float 抖动改变采样。"""
    transport, seen = _fake_transport([{"choices": [{"message": {"content": "x"}}],
                                        "usage": {}}])
    r = LlmRouter(endpoints={"writer": ModelEndpoint(model="m", temperature=700)})
    LlmClient(r, transport=transport).complete("writer", [{"role": "user", "content": "y"}])
    assert seen[0][1]["temperature"] == 0.7                  # 线上仍是模型要的 float，由定点还原


def test_cost_accumulates_only_when_price_configured():
    transport, _ = _fake_transport([
        {"choices": [{"message": {"content": "a"}}],
         "usage": {"prompt_tokens": 1000, "completion_tokens": 1000}},
        {"choices": [{"message": {"content": "b"}}],
         "usage": {"prompt_tokens": 500, "completion_tokens": 500}}])
    local = LlmClient(LlmRouter.default(), transport=transport)
    local.complete("writer", [{"role": "user", "content": "a"}])
    local.complete("writer", [{"role": "user", "content": "b"}])
    assert local.total_tokens == 3000 and local.total_cost_usd == 0.0    # 本地 = 零边际成本

    priced_transport, _ = _fake_transport([
        {"choices": [{"message": {"content": "a"}}],
         "usage": {"prompt_tokens": 1000, "completion_tokens": 1000}}])
    priced = LlmClient(LlmRouter(endpoints={
        "writer": ModelEndpoint(model="gpt-x", usd_per_1k_tokens=0.5)}), transport=priced_transport)
    priced.complete("writer", [{"role": "user", "content": "a"}])
    assert priced.total_cost_usd == pytest.approx(1.0)       # 2000 tokens × $0.5/1k


def test_api_key_goes_in_header_never_in_payload():
    transport, seen = _fake_transport([{"choices": [{"message": {"content": "x"}}], "usage": {}}])
    r = LlmRouter(endpoints={"writer": ModelEndpoint(model="m", api_key="SECRET")})
    LlmClient(r, transport=transport).complete("writer", [{"role": "user", "content": "y"}])
    assert seen[0][2]["Authorization"] == "Bearer SECRET"
    assert "SECRET" not in str(seen[0][1])                   # 绝不进请求体（会被 trace 记录）


def test_unknown_role_is_a_configuration_error():
    transport, _ = _fake_transport([])
    with pytest.raises(KeyError):
        LlmClient(LlmRouter.default(), transport=transport).complete(
            "critic", [{"role": "user", "content": "x"}])


# —— 商业级可配置：一份 JSON 描述所有角色，密钥只从环境变量取
def test_router_round_trips_through_config_dict():
    r = LlmRouter.default()
    r2 = LlmRouter.from_config(r.to_config())
    assert r2.to_config() == r.to_config()
    assert r2.endpoints["extract"].max_tokens == r.endpoints["extract"].max_tokens


def test_from_config_accepts_partial_role_overrides():
    r = LlmRouter.from_config({"writer": {"model": "qwen2.5:32b", "temperature": 500},
                               "extract": {"base_url": "http://127.0.0.1:8000/v1",
                                           "model": "qwen2.5:7b"}})
    assert r.endpoints["writer"].model == "qwen2.5:32b"
    assert r.endpoints["writer"].temperature == 500
    assert r.endpoints["writer"].max_tokens == ModelEndpoint().max_tokens   # 未写的字段用默认
    assert r.endpoints["extract"].base_url.endswith(":8000/v1")             # vLLM 同源兼容
    assert "plan" not in r.endpoints


def test_api_key_is_read_from_env_and_never_stored_in_config(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "sk-from-env")
    r = LlmRouter.from_config({"writer": {"model": "m", "api_key_env": "TEST_LLM_KEY"}})
    assert r.endpoints["writer"].api_key == "sk-from-env"
    dumped = r.to_config()
    assert "sk-from-env" not in str(dumped)          # dump 里只留变量名，绝不落密钥
    assert dumped["writer"]["api_key_env"] == "TEST_LLM_KEY"


def test_missing_env_var_yields_no_key_rather_than_crash(monkeypatch):
    monkeypatch.delenv("ABSENT_LLM_KEY", raising=False)
    r = LlmRouter.from_config({"writer": {"model": "m", "api_key_env": "ABSENT_LLM_KEY"}})
    assert r.endpoints["writer"].api_key is None


# —— 接线故障与内容故障必须可区分（本地模型冷启动 ≈65s，超时常被误读成「模型不行」）
def test_endpoint_timeout_reaches_the_transport():
    transport, seen = _fake_transport([{"choices": [{"message": {"content": "x"}}], "usage": {}}])
    r = LlmRouter(endpoints={"writer": ModelEndpoint(model="m", timeout_s=45)})
    LlmClient(r, transport=transport).complete("writer", [{"role": "user", "content": "y"}])
    assert seen[0][3] == 45


def test_malformed_response_is_unavailable_not_a_keyerror():
    transport, _ = _fake_transport([{"detail": "model not found"}])
    with pytest.raises(LlmUnavailable):
        LlmClient(LlmRouter.default(), transport=transport).complete(
            "writer", [{"role": "user", "content": "x"}])


def test_unreachable_endpoint_raises_llm_unavailable(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr("plot_engine.llm.urllib.request.urlopen", boom)
    with pytest.raises(LlmUnavailable):
        _urllib_transport("http://127.0.0.1:11434/v1/chat/completions", {}, {}, 5)


def test_extra_body_is_merged_into_the_request_payload():
    """qwen3 一类 thinking 模型必须能显式关思考，否则抽取通道只收到推理文本。"""
    transport, seen = _fake_transport([{"choices": [{"message": {"content": "x"}}], "usage": {}}])
    r = LlmRouter(endpoints={"extract": ModelEndpoint(model="qwen3:8b",
                                                     extra_body={"think": False})})
    LlmClient(r, transport=transport).complete("extract", [{"role": "user", "content": "y"}])
    assert seen[0][1]["think"] is False


def test_extra_body_defaults_empty_and_is_reportable():
    r = LlmRouter(endpoints={"writer": ModelEndpoint()})
    assert r.endpoints["writer"].extra_body == {}
    assert r.to_config()["writer"]["extra_body"] == {}


# —— 接线盲区（30b 初筛：十章空正文，run.log 一个字没有）
def test_empty_content_is_recorded_with_reasoning_and_raw_snippet():
    transport, _ = _fake_transport([
        {"choices": [{"message": {"content": "", "reasoning": "我需要先回忆…"},
                      "finish_reason": "length"}], "usage": {"completion_tokens": 1200}}])
    c = LlmClient(LlmRouter.default(), transport=transport)
    c.complete("writer", [{"role": "user", "content": "写第一章"}])
    line = c.render_call_diagnostics()
    assert "可疑 1 次" in line and "finish=length" in line and "思考=7" in line
    assert "我需要先回忆" in c.calls[0].raw          # 空正文时把原始响应留档


def test_clean_calls_are_not_flagged():
    transport, _ = _fake_transport([
        {"choices": [{"message": {"content": "张三凝视印章。"}, "finish_reason": "stop"}],
         "usage": {}}] * 3)
    c = LlmClient(LlmRouter.default(), transport=transport)
    for _ in range(3):
        c.complete("writer", [{"role": "user", "content": "y"}])
    assert c.render_call_diagnostics() == "调用 3 次｜接线正常（无空正文、无截断）"
