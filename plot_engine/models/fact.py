"""Fact 与 FactRelation 模型（02_fact_protocol.md §3/§5）。"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class Fact(BaseModel):
    """双层真相事实（02 §3）。"""

    fact_id: str = Field(..., pattern=r"^fact_\d{6}$")
    fact_type: Literal["existence", "identity", "relation", "event", "state"]

    proposition: str          # 人类可读："宗门内存在叛徒"
    canonical_form: str       # 机器可比对："traitor_exists(sect_A)"

    related_facts: List[str] = []

    # 双层真相
    narrative_truth: Literal["true", "false", "unknown"]
    objective_truth: Literal["true", "false", "unknown"]

    reveal_stage: Literal["hidden", "hinted", "partial", "confirmed"] = "hidden"

    defined_at_chapter: int
    epoch: str


class FactRelation(BaseModel):
    """Fact 关系边（02 §5）。Phase 0 静态：Arc 初始化定义，运行期不变。"""

    relation_id: str
    source_fact_id: str
    target_fact_id: str
    relation_type: Literal[
        "evidence_for",    # A 是 B 的证据
        "confirms",        # A 确认 B
        "contradicts",     # A 与 B 矛盾
        "implies",         # A 蕴含 B
        "derives_from",    # A 从 B 推断而来
    ]
    strength: int = Field(1000, ge=0, le=1000)  # v0.2：定点 ×1000（05 §5.5），禁止 float
    epoch: str
