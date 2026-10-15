"""Belief + Statement reducer：BELIEVES / SUSPECTS / DOUBTS / STATES / LIES / OMITS / HINTS。

规则出处：03 §5.1（belief 三态）+ §5.3 R1~R4（陈述类事件如何改写听众 Belief）。
纯函数，一切数值定点（05 §5.5）。
"""
from __future__ import annotations

from typing import Dict, List

from plot_engine.models.event import Event
from plot_engine.models.ledger import BeliefEntry
from plot_engine.models.state import StoryState, with_state_hash
from plot_engine.reducers.plot import hint_foreshadows

# belief 序：doubts < suspects < believes
_STATE_RANK: Dict[str, int] = {"doubts": 0, "suspects": 1, "believes": 2}


def _index(ledger: List[BeliefEntry], char_id: str, fact_id: str) -> int:
    for i, e in enumerate(ledger):
        if e.character_id == char_id and e.fact_id == fact_id:
            return i
    return -1


def _upsert(ledger: List[BeliefEntry], char_id: str, fact_id: str,
            cand_state: str, cand_strength: int, event_id: str, chapter: int,
            epoch: str, *, allow_downgrade: bool) -> None:
    """默认只升不降；DOUBTS 是唯一的显式降级通道（03 §5.3）。"""
    idx = _index(ledger, char_id, fact_id)
    if idx < 0:
        ledger.append(BeliefEntry(
            character_id=char_id, fact_id=fact_id, belief_state=cand_state,
            strength=cand_strength, source_event_id=event_id,
            acquired_at_chapter=chapter, last_updated_chapter=chapter, epoch=epoch))
        return
    cur = ledger[idx]
    upgrade = _STATE_RANK[cand_state] >= _STATE_RANK[cur.belief_state]
    if not (upgrade or allow_downgrade):
        return
    ledger[idx] = cur.model_copy(update={
        "belief_state": cand_state, "strength": cand_strength,
        "source_event_id": event_id, "last_updated_chapter": chapter})


def reduce_belief(event: Event, state: StoryState) -> StoryState:
    ledger = list(state.belief_ledger)
    actor = event.actor or ""
    et = event.event_type

    if et == "BELIEVES":
        _upsert(ledger, actor, event.payload["fact_id"], "believes",
                event.payload["belief_strength"], event.event_id, event.chapter,
                event.epoch, allow_downgrade=False)
    elif et == "SUSPECTS":
        _upsert(ledger, actor, event.payload["fact_id"], "suspects",
                event.payload.get("belief_strength", event.confidence),
                event.event_id, event.chapter, event.epoch, allow_downgrade=False)
    elif et == "DOUBTS":
        _upsert(ledger, actor, event.payload["fact_id"], "doubts",
                event.payload.get("belief_strength", event.confidence),
                event.event_id, event.chapter, event.epoch, allow_downgrade=True)
    elif et in ("STATES", "LIES"):
        # R2/R3：听众获得 believes；说话者自身信念不变（LIES 的真实信念由其 BELIEVES 通道维护）
        fact_id = event.payload["stated_fact_id"] if et == "LIES" else event.payload["fact_id"]
        for aud in event.payload["audience"]:
            _upsert(ledger, aud, fact_id, "believes", event.confidence,
                    event.event_id, event.chapter, event.epoch, allow_downgrade=False)
    elif et == "HINTS":
        # R4：听众 suspects，不降级已有 believes
        for aud in event.payload["audience"]:
            _upsert(ledger, aud, event.payload["fact_id"], "suspects",
                    event.confidence, event.event_id, event.chapter,
                    event.epoch, allow_downgrade=False)
    elif et == "OMITS":
        pass  # 不改写 Ledger；缺席追踪由 Validator 层负责
    else:  # pragma: no cover - 分派表外类型不应进入本 reducer
        raise ValueError(f"reduce_belief 收到非信念/陈述类事件: {et}")

    update: Dict[str, object] = {"belief_ledger": ledger}
    if et == "HINTS" and state.foreshadowing:
        # 伏笔联动：planted→hinted（WP-A 设计稿 §3）
        update["foreshadowing"] = hint_foreshadows(
            state.foreshadowing, event.payload["fact_id"],
            event.event_id, event.chapter)
    return with_state_hash(state.model_copy(update=update))
