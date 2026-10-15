"""Knowledge / Belief / Reader Ledger 记录模型 + epoch_1 剧情层台账（03 §4~§6；WP-A 设计稿 §2）。"""
from __future__ import annotations

from typing import List, Literal, Optional

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


class ForeshadowingEntry(BaseModel):
    """伏笔台账条目（epoch_1，WP-A 设计稿 §2.1）：埋点→提示→到期→回收/逾期 全生命周期。

    迁移单向：planted → hinted → due → paid / due → expired；回退视为新事件而非状态回写。
    `due` 是派生态（validator 视图 chapter ≥ due_by_chapter-1），不落账，保 replay 确定性。
    """

    foreshadow_id: str = Field(..., pattern=r"^fsh_\d{6}$")
    fact_id: str
    lifecycle: Literal["planted", "hinted", "due", "paid", "expired"]
    strength: int = Field(..., ge=0, le=1000)   # 显著度，定点 ×1000

    planted_chapter: int
    due_by_chapter: int                          # 单源=knowledge_gates.must_reveal_by_chapter（04 D11，派生注入）
    paid_chapter: Optional[int] = None

    source_event_id: str
    last_updated_chapter: int

    epoch: str


class CharacterGoalEntry(BaseModel):
    """人物级目标（epoch_1，设计稿 §2.2）：章级 story_goal 的上层归因锚（Phase 1「有原因/有代价/有后果」）。

    本批只冻 schema：无事件型写入方，账常空（同 FactRelation「先留字段」纪律）。
    """

    goal_id: str = Field(..., pattern=r"^goal_\d{6}$")
    character_id: str
    objective: str
    stakes: str = ""
    status: Literal["active", "achieved", "failed", "abandoned"]

    linked_fact_ids: List[str] = []              # 冲突网络挂点（P1，语义 epoch_2）

    source_event_id: str
    acquired_at_chapter: int
    last_updated_chapter: int

    epoch: str


class ArcProgress(BaseModel):
    """弧进度（epoch_1 冻字段，设计稿 §6 P1）：结构化替换 active_arc: Any，路由语义 epoch_2。"""

    arc_id: str = Field(..., pattern=r"^arc_\d{3}$")
    current_chapter: int = 0
    tension_actual: List[int] = []               # 各章实读张力，定点 ×1000（R8 爽点工程承接位）
    turning_points_hit: List[int] = []           # 已命中 turning_point 的章号
