"""Knowledge / Belief / Reader Ledger 记录模型（03_knowledge_protocol.md §4~§6）。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """角色"知道"的记录（可信，03 §4.1）。"""

    character_id: str
    fact_id: str
    knowledge_state: Literal["unknown", "suspected", "believed", "known", "confirmed"]
    strength: int = Field(..., ge=0, le=1000)          # 定点 ×1000

    source_event_id: str
    acquired_at_chapter: int
    last_updated_chapter: int

    epoch: str


class BeliefEntry(BaseModel):
    """角色"相信"的记录（可假，03 §5.1）。"""

    character_id: str
    fact_id: str
    belief_state: Literal["doubts", "suspects", "believes"]
    strength: int = Field(..., ge=0, le=1000)          # 定点 ×1000

    source_event_id: str
    acquired_at_chapter: int
    last_updated_chapter: int

    is_true: Optional[bool] = None   # 事后派生值，不参与 Replay 关键路径

    epoch: str


class ReaderKnowledgeEntry(BaseModel):
    """读者认知记录（作者层控制，03 §6.1）。source_event_id 必填（READER_* 事件）。"""

    fact_id: str
    reader_state: Literal["unaware", "hinted", "knows", "deceived"]
    reader_strength: int = Field(..., ge=0, le=1000)   # 定点 ×1000

    established_at_chapter: int
    last_updated_chapter: int
    source_event_id: str

    epoch: str
