"""EventProposal 模型（07 §4.2）：Stage 0 抽取产物，尚未 commit。

Proposal 与 Event 的区别：Proposal 无 event_id、可丢弃、可重生成；
event_id 由 (chapter, seq) 确定性推出（重复 seq → 同 id，H6.4 判料）。
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .event import Event


class EventProposal(BaseModel):
    """Stage 0 生成，尚未获得 event_id，尚未 commit（07 §4.2）。"""

    proposed_event_type: str         # ∈ 01 §3 Taxonomy（含 READER_* / ITEM_* 等）
    actor: Optional[str] = None
    target: Optional[str] = None
    chapter: int
    scene: Optional[str] = None
    seq: int

    preconditions: List[str] = []
    payload: Dict = {}

    confidence: int = Field(1000, ge=0, le=1000)   # 抽取置信度 ×1000（07 §4.3）
    source_ref: str                  # Draft 中的原文引用或 markup: 定位

    extraction_method: Literal["rule", "llm", "hybrid", "markup"]  # v0.2 增 markup 通道
    extraction_confidence: int = Field(1000, ge=0, le=1000)


def proposal_event_id(proposal: EventProposal) -> str:
    """(chapter, seq) → 确定性 event_id；同章重复 seq 产生同一 id（07 §4.2 / H6.4）。"""
    return f"evt_{proposal.chapter:08d}_{proposal.seq:03d}"


def to_event(proposal: EventProposal, epoch: str) -> Event:
    """Commit Stage 2：Proposal 定稿为不可变 Event。"""
    return Event(
        event_id=proposal_event_id(proposal),
        epoch=epoch,
        schema_version=2,
        event_type=proposal.proposed_event_type,  # 非法类型由 Event 的 Literal 拒绝（H6.1 判料）
        actor=proposal.actor,
        target=proposal.target,
        chapter=proposal.chapter,
        scene=proposal.scene,
        seq=proposal.seq,
        preconditions=list(proposal.preconditions),
        payload=dict(proposal.payload),
        confidence=proposal.confidence,
        source_ref=proposal.source_ref,
    )
