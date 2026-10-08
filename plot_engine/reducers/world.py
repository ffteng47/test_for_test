"""World reducer：HAPPENS / REVEALS / CHANGES / ITEM_ACQUIRED / ITEM_CONSUMED / RELATIONSHIP_CHANGED。

规则出处：10 §4.3（字段映射）、§9.1（关系边）、§10.1（库存）、01 §4.1（payload）。
纯函数；存储值受模型约束（quantity ge=0、strength/trust 0~1000），越界钳到边界，
非法消耗由 Task 12 从事件流重算并落 HARD 发现（Review Focus #3）。
"""
from __future__ import annotations

from typing import Dict, List

from plot_engine.models.entity import InventoryEntry, Relationship
from plot_engine.models.event import Event
from plot_engine.models.state import StoryState, with_state_hash

# 10 §4.3：CharacterChange.field → Character 属性名
_FIELD_MAP: Dict[str, str] = {
    "status": "status",
    "realm": "realm",
    "location": "current_location",
    "faction": "faction_id",
    "attributes": "attributes",
    "abilities": "abilities",
}


def _clamp(v: int) -> int:
    return max(0, min(1000, v))


def _apply_changes(state: StoryState, event: Event) -> StoryState:
    p = event.payload
    char = state.characters.get(event.actor or "")
    if char is None:
        return state  # 引用完整性由 Task 12 检查；reducer 不崩溃
    attr = _FIELD_MAP.get(p["field"])
    if attr is None:
        return state
    update: Dict[str, object] = {attr: p["new_value"]}
    if p["field"] == "status":
        if p["new_value"] == "dead":
            update["death_chapter"] = event.chapter
        elif p["new_value"] == "sealed":
            update["seal_chapter"] = event.chapter
    characters = dict(state.characters)
    characters[char.character_id] = char.model_copy(update=update)
    return state.model_copy(update={"characters": characters})


def _inv_index(entries: List[InventoryEntry], char_id: str, item_id: str) -> List[int]:
    return [i for i, e in enumerate(entries)
            if e.character_id == char_id and e.item_id == item_id]


def _item_acquired(state: StoryState, event: Event) -> StoryState:
    p = event.payload
    entries = list(state.inventory)
    item = state.items.get(p["item_id"])
    qty = 1 if (item is not None and item.unique) else int(p["quantity"])
    stackable = item.stackable if item is not None else True
    if stackable:
        idx = _inv_index(entries, p["character_id"], p["item_id"])
        if idx:
            cur = entries[idx[0]]
            entries[idx[0]] = cur.model_copy(update={"quantity": cur.quantity + qty})
            return state.model_copy(update={"inventory": entries})
    entries.append(InventoryEntry(
        inventory_id=f"inv_{len(entries) + 1:06d}",
        character_id=p["character_id"], item_id=p["item_id"], quantity=qty,
        acquired_at_chapter=event.chapter, epoch=event.epoch))
    return state.model_copy(update={"inventory": entries})


def _item_consumed(state: StoryState, event: Event) -> StoryState:
    p = event.payload
    entries = list(state.inventory)
    remaining = int(p["quantity"])
    for i in _inv_index(entries, p["character_id"], p["item_id"]):
        if remaining <= 0:
            break
        e = entries[i]
        take = min(e.quantity, remaining)
        entries[i] = e.model_copy(update={"quantity": e.quantity - take})
        remaining -= take
    # remaining > 0 → 超额消耗：存储钳在 0（不能为负），Task 12 从事件重算落 H4.1
    return state.model_copy(update={"inventory": entries})


def _relationship_changed(state: StoryState, event: Event) -> StoryState:
    p = event.payload
    rels = list(state.relationships)
    f, t, typ = p["from"], p["to"], p["relationship_type"]
    s_delta, tr_delta = int(p["strength_delta"]), int(p["trust_delta"])
    # Phase 0：关系一律按 symmetric=True 存一行，双向匹配（10 §9.1 R1）
    for i, r in enumerate(rels):
        if r.type == typ and {r.from_character, r.to_character} == {f, t}:
            rels[i] = r.model_copy(update={
                "strength": _clamp(r.strength + s_delta),
                "trust": _clamp(r.trust + tr_delta)})
            return state.model_copy(update={"relationships": rels})
    rels.append(Relationship(
        relationship_id=f"rel_{len(rels) + 1:06d}",
        from_character=f, to_character=t, type=typ,
        strength=_clamp(500 + s_delta), trust=_clamp(500 + tr_delta),
        symmetric=True, established_at_chapter=event.chapter, epoch=event.epoch))
    return state.model_copy(update={"relationships": rels})


def _reveals(state: StoryState, event: Event) -> StoryState:
    fact_id = event.payload["fact_id"]
    fact = state.facts.get(fact_id)
    if fact is None:
        return state
    facts = dict(state.facts)
    facts[fact_id] = fact.model_copy(
        update={"narrative_truth": event.payload["new_narrative_truth"]})
    return state.model_copy(update={"facts": facts})


def reduce_world(event: Event, state: StoryState) -> StoryState:
    et = event.event_type
    if et == "HAPPENS":
        out = state  # Phase 0：HAPPENS 不改写实体表，仅作世界事实标记（引用检查在 Task 12）
    elif et == "REVEALS":
        out = _reveals(state, event)
    elif et == "CHANGES":
        out = _apply_changes(state, event)
    elif et == "ITEM_ACQUIRED":
        out = _item_acquired(state, event)
    elif et == "ITEM_CONSUMED":
        out = _item_consumed(state, event)
    elif et == "RELATIONSHIP_CHANGED":
        out = _relationship_changed(state, event)
    else:  # pragma: no cover - 分派表外类型不应进入本 reducer
        raise ValueError(f"reduce_world 收到非世界类事件: {et}")
    return with_state_hash(out)
