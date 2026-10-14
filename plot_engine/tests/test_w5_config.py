"""W5 配置与车道可用性自检（零生成、零采样，只回答「能不能开第 4 步」）。

钉三条：
1. W5 配置的三个差异点必须就是那三个（base_url / temperature / 无其余偏差）——
   少一条就是混账，E9 的「配置差异披露不全」会以另一种形式复现；
2. extract 温度必须为 0（W5 规格），云端模板同样为 0（两车道同温才能归因）；
3. 配置声明的角色集自洽（writer+extract 都在，缺一个 --live 直接抛 KeyError）。
"""
import json
from pathlib import Path

W5 = "router_w5_frozen.json"
CLOUD = "deepseek.router.json"
ONUSE = "router_q25_14b.json"


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def test_w5_config_differs_from_the_in_use_arm_in_exactly_three_ways():
    w5, on = _load(W5), _load(ONUSE)["extract"]
    ex = w5["extract"]
    diffs = [k for k in set(ex) | set(on) if ex.get(k) != on.get(k)]
    assert set(diffs) == {"base_url", "temperature"}, diffs
    assert ex["temperature"] == 0                       # W5 规格：温度 0
    assert "192.168.31.213:11434" in ex["base_url"]      # 用户指定的新端点
    # 未申报的差异才是危险的：max_tokens/timeout/extra_body/model 必须逐字段不动
    for k in ("max_tokens", "timeout_s", "extra_body", "model"):
        assert ex[k] == on[k], k


def test_w5_config_carries_both_roles_and_matches_local_host():
    w5 = _load(W5)
    assert {"writer", "extract"} <= set(w5)
    for role in ("writer", "extract"):
        assert "192.168.31.213:11434" in w5[role]["base_url"], role


def test_two_lanes_share_temperature_zero():
    """2x2 要「只有模型不同」：任一侧温度不为 0，两格就不可比。"""
    assert _load(W5)["extract"]["temperature"] == 0
    assert _load(CLOUD)["extract"]["temperature"] == 0


def test_w5_config_declares_its_purpose_in_a_comment():
    assert "W5" in _load(W5)["_comment"] and "router_q25_14b" in _load(W5)["_comment"]
