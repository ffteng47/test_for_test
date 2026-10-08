"""Arc / Chapter Contract 与 Scene 前置结构模型（04_contract_protocol.md §3.1/§4.1）。

字段、枚举、默认值逐字对齐协议；派生规则（D1~D9）与自校验（V1~V10）
由 validator 实现（05 H7 族），模型层只做 schema 约束。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class KnowledgeGate(BaseModel):
    """知识闸门：谁在第几章之后可以知道什么（04 §3.1）。"""

    fact_id: str
    allowed_characters: List[str] = []          # 空 = 所有角色
    allowed_after_chapter: int
    must_reveal_by_chapter: Optional[int] = None
    reveal_stage_target: Literal["hidden", "hinted", "partial", "confirmed"]


class TurningPoint(BaseModel):
    chapter: int
    type: Literal["reversal", "revelation", "escalation", "crisis", "climax"]
    description: str
    required_event_types: List[str]             # ∈ 01 §3 Taxonomy


class ArcContract(BaseModel):
    arc_id: str = Field(..., pattern=r"^arc_\d{3}$")
    epoch: str

    chapter_range: Tuple[int, int]              # (start, end)，HARD 结构约束
    tension_curve: List[int] = []               # 每章目标张力 ×1000，长度 = end-start+1（§3.2 R1 HARD）
    turning_points: List[TurningPoint]
    knowledge_gates: List[KnowledgeGate]

    reader_beats: List[dict] = []               # SOFT 元数据，Phase 0 不进 Validator
    theme: Optional[str] = None

    created_at: str
    schema_version: int = 2


class CharacterChange(BaseModel):
    character_id: str
    # v0.2：field 枚举与 10 §4.3 映射表严格对齐
    field: Literal[
        "knowledge", "belief",                  # → Knowledge/Belief Ledger
        "location", "realm", "status",          # → CHANGES(field=...)
        "faction", "attributes", "abilities",   # → CHANGES(field=...)
        "relationship",                         # → RELATIONSHIP_CHANGED
        "inventory",                            # → ITEM_ACQUIRED / ITEM_CONSUMED
    ]
    operation: Literal["add", "remove", "update"]
    target: str                                 # fact_id / loc_id / item_id / char_id / realm_id
    expected_value: Optional[Any] = None


class RequiredEvent(BaseModel):
    event_type: str                             # ∈ 01 §3 Taxonomy
    description: str
    minimum_count: int = 1
    actors_involved: List[str] = []
    must_be_visible_to_reader: bool = True


class ForbiddenEvent(BaseModel):
    event_type: str
    description: str
    reason: str                                 # 为什么禁止（追溯来源）


class ChapterHook(BaseModel):
    type: Literal["cliffhanger", "revelation", "decision", "arrival",
                  "question", "none"]
    strength: int = Field(..., ge=0, le=1000)   # ×1000
    description: str


class ReaderSignal(BaseModel):
    """v0.2 新增，对应 01 §3.5 / 03 §6。"""

    fact_id: str
    target_state: Literal["unaware", "hinted", "knows", "deceived"]
    established_in_scene: Optional[str] = None  # scn_id


class ChapterContract(BaseModel):
    chapter_no: int
    arc_id: str
    epoch: str
    version: int = 1                            # 修订记于此（04 §6 I3/I4）

    story_goal: str
    story_goal_type: Literal[
        "revelation", "escalation", "setup", "resolution",
        "transition", "confrontation", "reflection",
    ]

    # 硬约束
    must_change: List[CharacterChange] = []
    must_not_change: List[CharacterChange] = []
    required_events: List[RequiredEvent] = []
    forbidden_events: List[ForbiddenEvent] = []

    # 知识约束（从 Arc knowledge_gates 派生）
    knowledge_allowed: List[str] = []
    knowledge_forbidden: List[str] = []

    # 读者信号（v0.2 新增）
    reader_signals: List[ReaderSignal] = []

    # 剧情推进
    plot_progress: Dict[str, int] = {}          # 线程进度 ×1000，SOFT
    tension_target: int = Field(500, ge=0, le=1000)  # ×1000，SOFT

    # 章尾
    ending: ChapterHook

    # 元数据
    derived_from: List[str] = []
    created_at: str
    schema_version: int = 2
