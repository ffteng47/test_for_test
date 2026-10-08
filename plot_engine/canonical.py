"""canonical 序列化 / 哈希 / 定点化辅助（05 §5.5）。

唯一序列化依据：key 字典序、无空白、UTF-8 不转义 ASCII、浮点禁用（一律定点 int）。
所有 Replay 关键路径的哈希都出自本模块，跨机器 / 跨语言必须一致。
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def _normalize(obj: Any) -> Any:
    """递归转成 JSON 安全结构；pydantic 模型先 model_dump，float 直接拒绝。"""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    if obj is None or isinstance(obj, bool) or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        raise TypeError("float 禁止进入 canonical 路径：请一律定点 ×1000 存整数（05 §5.5）")
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(x) for x in obj]
    raise TypeError(f"canonical 路径不支持的类型: {type(obj)!r}")


def canonical_json(obj: Any) -> bytes:
    """key 字典序、无空白、UTF-8 不转义 ASCII；数值必须已是定点整数（05 §5.5.1）。"""
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_hash(obj: Any) -> str:
    """state_hash = SHA256(canonical_json(obj))（05 §5.5.3）。"""
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def proposal_set_hash(proposals: list) -> str:
    """SHA256(canonical_json(sorted proposals))——防同键不同内容重放（07 §8 R1）。"""
    ordered = sorted(proposals, key=lambda p: canonical_json(p))
    return canonical_hash(ordered)


def to_fixed(x: float | str) -> int:
    """一次性入库转换：原值 ×1000 取整。禁止用于 Replay 关键路径的反复计算。"""
    return int(Decimal(str(x)) * 1000)


def fixed_to_str(v: int) -> str:
    """定点值 → 显示字符串（仅展示，永不进 Replay 路径）。"""
    return f"{v / 1000:.3f}"
