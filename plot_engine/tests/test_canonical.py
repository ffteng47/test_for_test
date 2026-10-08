"""canonical 序列化 / 哈希 / 定点化辅助（05 §5.5）。"""
from __future__ import annotations

import pytest

from plot_engine.canonical import (
    canonical_hash,
    canonical_json,
    fixed_to_str,
    proposal_set_hash,
    to_fixed,
)


def test_keys_sorted_and_no_whitespace():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_cjk_bytes_are_stable_and_unescaped():
    a = canonical_json({"name": "张三", "z": 1, "a": 0})
    b = canonical_json({"a": 0, "name": "张三", "z": 1})
    assert a == b == '{"a":0,"name":"张三","z":1}'.encode("utf-8")


def test_hash_is_deterministic_and_hex64():
    h = canonical_hash({"x": 1})
    assert h == canonical_hash({"x": 1}) and len(h) == 64


def test_float_forbidden_in_canonical_path():
    with pytest.raises(TypeError):
        canonical_json({"strength": 0.4})


def test_fixed_roundtrip_display():
    assert to_fixed(0.4) == 400 and fixed_to_str(400) == "0.400"


def test_proposal_set_hash_order_independent():
    a = proposal_set_hash([{"x": 1}, {"y": 2}])
    b = proposal_set_hash([{"y": 2}, {"x": 1}])   # 内部排序 → 相等
    assert a == b and len(a) == 64
