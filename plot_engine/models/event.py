"""Event 模型与事件分类（01_event_protocol.md §4）。"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

EventType = Literal[
    # Knowledge（5）
    "OBSERVES", "READS", "IS_TOLD", "INFERS", "FACT_CONTRADICTED",
    # Belief（3）
    "BELIEVES", "SUSPECTS", "DOUBTS",
    # Statement（4）
    "STATES", "LIES", "OMITS", "HINTS",
    # World（6）
    "HAPPENS", "REVEALS", "CHANGES",
    "ITEM_ACQUIRED", "ITEM_CONSUMED", "RELATIONSHIP_CHANGED",
    # Reader（3）
    "READER_LEARNS", "READER_DECEIVED", "READER_HINTED",
    # Plot（5）
    "CASE_SOLVED", "FORESHADOWING_SET", "FORESHADOWING_PAID",
    "CONTRACT_FULFILLED", "CONTRACT_VIOLATED",
]


class Event(BaseModel):
    """一次不可变的叙事事件，Event Log 的最小单元（01 §4）。"""

    # 标识
    event_id: str = Field(..., pattern=r"^evt_\d{8}_\d{3}$")  # evt_00000047_003
    epoch: str = Field(..., pattern=r"^epoch_\d+$")           # epoch_0
    schema_version: int = 2

    # 分类
    event_type: EventType

    # 主体
    actor: Optional[str] = None                 # 执行者（char_id）；World 事件可为空
    target: Optional[str] = None                # 受体（char_id / fact_id / item_id / loc_id）
    location: Optional[str] = None              # 发生地点（loc_id）

    # 时序
    chapter: int = Field(..., ge=1)
    scene: Optional[str] = None                 # scn_id（04 附录 B）
    seq: int = Field(..., ge=0)                 # 同一章内的顺序，从 0 起

    # 因果（E3'：Phase 0 允许为空）
    preconditions: List[str] = []               # 前置 event_id（若填写必须已 commit）
    causes: List[str] = []                      # 后果 event_id（可空，允许后续回填）

    # 载荷（按 event_type 严格区分，见 01 §4.1）
    payload: Dict = {}

    # 元数据
    confidence: int = Field(1000, ge=0, le=1000)  # 抽取置信度，定点 ×1000（07 §4.3）
    source_ref: Optional[str] = None             # 正文段落引用，用于 Debug
