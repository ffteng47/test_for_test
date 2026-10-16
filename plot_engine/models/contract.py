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


# 10 §4.3：CharacterChange.field → 能实现该跃迁的事件类型。
# 两个 ledger 的事件族不互通，且 belief 侧要认 DOUBTS。
# H5.3（validator）与派生守卫（derive）共用这张表：契约生成时就排除实现不了的 Δ，
# 别把它交给 Writer 去撞三轮修订。
FIELD_EVENT_TYPES: Dict[str, set] = {
    "knowledge": {"OBSERVES", "READS", "IS_TOLD", "INFERS"},
    "belief": {"BELIEVES", "SUSPECTS", "DOUBTS"},
    "location": {"CHANGES"}, "realm": {"CHANGES"}, "status": {"CHANGES"},
    "faction": {"CHANGES"}, "attributes": {"CHANGES"}, "abilities": {"CHANGES"},
    "relationship": {"RELATIONSHIP_CHANGED"},
    "inventory": {"ITEM_ACQUIRED", "ITEM_CONSUMED"},
}

# Reducer 的档位上限（03 §4.3/§5.1，`reducers/knowledge.py:71-85` 逐条兑现）：
# 每种 knowledge 事件最多把 ledger 推到哪一档。43 章裁定 ③ 族（rank-cap 6 章）
# 就是「类型在表里、档位够不着」的 Δ——D10 光查类型交集放它进契约，
# H5.3（类型判）绿、H2.2（档位判）红，两把尺互斥。三处共用这张表：
# derive D10（生成时排除档位不可达的 Δ）、validator H5.3（实现判=终态达档，与 H2.2
# 同谓词）、夹具（expected_value ≤ 钉事件上限）。
K_RANK: Dict[str, int] = {"unknown": 0, "suspected": 1, "believed": 2,
                          "known": 3, "confirmed": 4}
KNOWLEDGE_RANK_CAP: Dict[str, str] = {"OBSERVES": "known", "READS": "known",
                                      "IS_TOLD": "believed", "INFERS": "suspected"}


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
