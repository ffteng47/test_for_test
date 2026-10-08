"""StoryState 聚合根（10_world_state_protocol.md §13）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from plot_engine.canonical import canonical_hash
from plot_engine.models.entity import (
    Ability,
    Character,
    Faction,
    InventoryEntry,
    Item,
    Location,
    Realm,
    Region,
    Relationship,
)
from plot_engine.models.fact import Fact, FactRelation
from plot_engine.models.ledger import (
    BeliefEntry,
    KnowledgeEntry,
    ReaderKnowledgeEntry,
)


class StoryState(BaseModel):
    """单一故事在某章提交后的完整状态快照（10 §13）。"""

    # 元数据
    story_id: str
    chapter_no: int
    version: int
    epoch: str
    schema_version: int = 2

    # 实体（10 号协议）
    characters: Dict[str, Character] = {}
    locations: Dict[str, Location] = {}
    items: Dict[str, Item] = {}
    factions: Dict[str, Faction] = {}
    realms: Dict[str, Realm] = {}
    abilities: Dict[str, Ability] = {}
    regions: Dict[str, Region] = {}

    # 边（10 号协议）
    relationships: List[Relationship] = []
    inventory: List[InventoryEntry] = []

    # 认知层（02 / 03）
    facts: Dict[str, Fact] = {}
    fact_relations: List[FactRelation] = []
    knowledge_ledger: List[KnowledgeEntry] = []
    belief_ledger: List[BeliefEntry] = []
    reader_ledger: List[ReaderKnowledgeEntry] = []

    # 剧情层（04）
    active_arc: Optional[Any] = None
    active_chapter: Optional[Any] = None

    # 结构层
    story_threads: List[str] = []
    foreshadowing: List[str] = []

    # 校验（05 §5.5 canonical 序列化）
    state_hash: str


def with_state_hash(state: StoryState) -> StoryState:
    """唯一认可的打哈希方式：对排除 state_hash 的 canonical 内容求 SHA256。"""
    digest = canonical_hash(state.model_dump(mode="json", exclude={"state_hash"}))
    return state.model_copy(update={"state_hash": digest})
