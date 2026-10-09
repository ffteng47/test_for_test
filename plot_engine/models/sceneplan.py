"""Scene / Beat / ScenePlan 规划层结构模型（04_contract_protocol.md 附录 B §8.2）。

字段、正则、`ge/le`、`min/max_length` 逐字对齐协议。ScenePlan 是规划产物：
**不进 Event Log、不是 Contract**，被 Contract 约束、被 SP 规则自校验（04 §8.3）、供 Writer 消费。
数值一律定点整数 ×1000。
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Beat(BaseModel):
    beat_id: str = Field(..., pattern=r"^bt_\d{6}$")
    seq: int = Field(..., ge=0)                               # 场景内顺序
    intent: str                                               # 一句话意图（SOFT，供 Writer）
    beat_type: Literal["setup", "pressure", "turn", "release", "foreshadow"]

    # 结构化字段（scope-reduction C6：规则只比枚举/数值，不做关键词匹配）
    action_type: Optional[Literal[
        "combat", "dialogue", "investigation",
        "travel", "ritual", "reveal", "status_change"
    ]] = None
    actors: List[str] = []                                    # char_id
    actor_realm: Optional[str] = None                         # realm_id（H1.4 判定输入）
    target_realm: Optional[str] = None
    location: Optional[str] = None                            # loc_id

    expected_event_types: List[str] = []                      # 本 Beat 预期触发的 01 §3 事件类型
    reader_target: Optional[Literal["learns", "hinted", "deceived"]] = None
    reader_fact_id: Optional[str] = None


class Scene(BaseModel):
    scene_id: str = Field(..., pattern=r"^scn_\d{4}_\d{2}$")  # scn_0047_01
    chapter_no: int
    seq: int = Field(..., ge=0, le=6)
    location: Optional[str] = None
    characters: List[str] = []
    purpose: str = ""                                         # SOFT
    tension: int = Field(500, ge=0, le=1000)                  # ×1000，SOFT
    beats: List[Beat] = Field(..., min_length=3, max_length=7)


class ScenePlan(BaseModel):
    plan_id: str = Field(..., pattern=r"^sop_\d{8}$")
    chapter_no: int
    arc_id: str
    contract_version: int                                     # 绑定的 Chapter Contract 版本
    scenes: List[Scene] = Field(..., min_length=3, max_length=7)
    derived_from: List[str] = []                              # 指向 Contract 条目
    epoch: str
    created_at: str
    schema_version: int = 2
