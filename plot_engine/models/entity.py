"""世界实体模型（10_world_state_protocol.md §4~§12）。"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Character(BaseModel):
    """角色实体（10 §4）。"""

    character_id: str = Field(..., pattern=r"^char_\d{6}$")
    name: str
    aliases: List[str] = []
    gender: Optional[str] = None

    status: Literal["alive", "dead", "missing", "sealed", "unborn"]
    death_chapter: Optional[int] = None
    seal_chapter: Optional[int] = None

    realm: Optional[str] = None              # realm_id
    abilities: List[str] = []                # abil_id 列表
    attributes: Dict[str, int] = {}          # 定点 ×1000（05 §5.5）

    current_location: Optional[str] = None   # loc_id
    faction_id: Optional[str] = None

    introduced_at_chapter: int
    last_seen_at_chapter: Optional[int] = None
    epoch: str


class Location(BaseModel):
    """地点实体（10 §5）。"""

    location_id: str = Field(..., pattern=r"^loc_\d{6}$")
    name: str

    region_id: Optional[str] = None
    parent_location_id: Optional[str] = None

    connected_to: List[str] = []
    distance: Dict[str, int] = {}            # loc_id -> 距离 ×1000

    unlocked: bool = True
    unlock_conditions: List[str] = []

    realm_cap: Optional[str] = None          # realm_id
    faction_control: Optional[str] = None    # fac_id

    introduced_at_chapter: int
    epoch: str


class Item(BaseModel):
    """物品实体（10 §6）。"""

    item_id: str = Field(..., pattern=r"^item_\d{6}$")
    name: str

    item_type: Literal["consumable", "equipment", "material", "key", "misc", "quest"]

    attributes: Dict[str, Any] = {}

    unique: bool = False
    stackable: bool = True

    required_realm: Optional[str] = None
    consumed_on_use: bool = False

    introduced_at_chapter: int
    epoch: str


class Faction(BaseModel):
    """势力实体（10 §7）。"""

    faction_id: str = Field(..., pattern=r"^fac_\d{5}$")
    name: str

    parent_faction_id: Optional[str] = None

    relations: Dict[str, str] = {}           # fac_id -> "ally"|"neutral"|"hostile"

    controlled_locations: List[str] = []
    members: List[str] = []

    introduced_at_chapter: int
    epoch: str


class Realm(BaseModel):
    """境界实体：偏序 + tier 全序编号，禁止字符串比较（10 §8）。"""

    realm_id: str = Field(..., pattern=r"^realm_\d{5}$")
    name: str
    tier: int = Field(..., ge=1)
    system_id: str

    previous_realm: Optional[str] = None
    next_realm: Optional[str] = None

    allowed_abilities: List[str] = []
    usable_realms: List[int] = []            # 可动用 tier 上限；sealed 视为 []
    min_attributes: Dict[str, int] = {}

    epoch: str


class Ability(BaseModel):
    """能力实体（Phase 0 最小版，10 §11）。"""

    ability_id: str = Field(..., pattern=r"^abil_\d{5}$")
    name: str

    ability_type: Literal["combat", "utility", "passive", "special"]

    required_realm: Optional[str] = None
    consumed_resource: Optional[str] = None

    introduced_at_chapter: int
    epoch: str


class Region(BaseModel):
    """区域实体（10 §12）。"""

    region_id: str = Field(..., pattern=r"^rgn_\d{5}$")
    name: str

    epoch: str


class Relationship(BaseModel):
    """角色关系边（10 §9）。"""

    relationship_id: str = Field(..., pattern=r"^rel_\d{6}$")
    from_character: str
    to_character: str

    type: Literal[
        "family", "master_disciple", "friend", "enemy",
        "ally", "rival", "lover", "colleague", "unknown",
    ]

    strength: int = Field(500, ge=0, le=1000)  # ×1000
    trust: int = Field(500, ge=0, le=1000)     # ×1000

    symmetric: bool = True

    established_at_chapter: int
    ended_at_chapter: Optional[int] = None

    epoch: str


class InventoryEntry(BaseModel):
    """库存条目边（10 §10）。"""

    inventory_id: str = Field(..., pattern=r"^inv_\d{6}$")
    character_id: str
    item_id: str
    quantity: int = Field(..., ge=0)

    acquired_at_chapter: int
    consumed_at_chapter: Optional[int] = None

    epoch: str
