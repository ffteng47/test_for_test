"""Knowledge reducer：OBSERVES / READS / IS_TOLD / INFERS / FACT_CONTRADICTED。

规则出处：03 §4.3（R1~R7）+ §5.4（降级）。一切数值走定点整数（05 §5.5），纯函数无副作用。
"""
from __future__ import annotations

from typing import Dict, List

from plot_engine.models.event import Event
from plot_engine.models.ledger import KnowledgeEntry
from plot_engine.models.state import StoryState, with_state_hash

# knowledge_state 序：unknown < suspected < believed < known < confirmed
_STATE_RANK: Dict[str, int] = {
    "unknown": 0, "suspected": 1, "believed": 2, "known": 3, "confirmed": 4,
}


def _index(ledger: List[KnowledgeEntry], char_id: str, fact_id: str):
    for i, e in enumerate(ledger):
        if e.character_id == char_id and e.fact_id == fact_id:
            return i
    return -1


def _merge_upgrade(ledger: List[KnowledgeEntry], char_id: str, fact_id: str,
                   cand_state: str, cand_strength: int, event_id: str, chapter: int,
                   epoch: str) -> None:
    """R5：取更强状态；只升不降（FACT_CONTRADICTED 走独立降级路径）。"""
    idx = _index(ledger, char_id, fact_id)
    if idx < 0:
        ledger.append(KnowledgeEntry(
            character_id=char_id, fact_id=fact_id, knowledge_state=cand_state,
            strength=cand_strength, source_event_id=event_id,
            acquired_at_chapter=chapter, last_updated_chapter=chapter, epoch=epoch))
        return
    cur = ledger[idx]
    new_state = cur.knowledge_state if _STATE_RANK[cur.knowledge_state] >= _STATE_RANK[cand_state] else cand_state
    new_strength = max(cur.strength, cand_strength)
    ledger[idx] = cur.model_copy(update={
        "knowledge_state": new_state, "strength": new_strength,
        "source_event_id": event_id, "last_updated_chapter": chapter})


def _downgrade(ledger: List[KnowledgeEntry], char_id: str, fact_id: str,
               event_id: str, chapter: int) -> None:
    """FACT_CONTRADICTED（03 §5.4）：confirmed/known→suspected、believed/suspected→suspected，强度 ×0.4。"""
    idx = _index(ledger, char_id, fact_id)
    if idx < 0:
        return  # unknown/缺失：不变，降级由 Task 12 落 OBSERVATION
    cur = ledger[idx]
    if cur.knowledge_state == "unknown":
        return
    ledger[idx] = cur.model_copy(update={
        "knowledge_state": "suspected",
        "strength": cur.strength * 4 // 10,   # ×0.4 定点（整数向下取整）
        "source_event_id": event_id, "last_updated_chapter": chapter})


def _evidence_strength(ledger: List[KnowledgeEntry], char_id: str, evidence_ids: List[int]) -> int:
    vals = [e.strength for e in ledger
            if e.character_id == char_id and e.fact_id in evidence_ids]
    return min(vals) if vals else 1000


def reduce_knowledge(event: Event, state: StoryState) -> StoryState:
    ledger = list(state.knowledge_ledger)
    actor = event.actor or ""
    et = event.event_type

    if et == "OBSERVES":
        _merge_upgrade(ledger, actor, event.payload["fact_id"], "known", 900,
                       event.event_id, event.chapter, event.epoch)
    elif et == "READS":
        _merge_upgrade(ledger, actor, event.payload["fact_id"], "known", 800,
                       event.event_id, event.chapter, event.epoch)
    elif et == "IS_TOLD":
        strength = (event.payload["trust_level"] * event.payload["message_strength"]) // 1000
        _merge_upgrade(ledger, actor, event.payload["fact_id"], "believed", strength,
                       event.event_id, event.chapter, event.epoch)
    elif et == "INFERS":
        base = _evidence_strength(ledger, actor, event.payload["evidence_fact_ids"])
        strength = base * event.confidence // 1000
        _merge_upgrade(ledger, actor, event.payload["conclusion_fact_id"],
                       "suspected", strength, event.event_id, event.chapter, event.epoch)
    elif et == "FACT_CONTRADICTED":
        _downgrade(ledger, actor, event.payload["fact_id"], event.event_id, event.chapter)
    else:  # pragma: no cover - 分派表外类型不应进入本 reducer
        raise ValueError(f"reduce_knowledge 收到非知识类事件: {et}")

    return with_state_hash(state.model_copy(update={"knowledge_ledger": ledger}))
