"""Reader reducer：READER_LEARNS / READER_DECEIVED / READER_HINTED。

规则出处：03 §6.3（作者层控制读者认知）。以 fact_id 为主键；knows 只升不降。
"""
from __future__ import annotations

from typing import Dict, List

from plot_engine.models.event import Event
from plot_engine.models.ledger import ReaderKnowledgeEntry
from plot_engine.models.state import StoryState, with_state_hash
from plot_engine.reducers.plot import hint_foreshadows

# reader_state 序：unaware < hinted/deceived < knows
_STATE_RANK: Dict[str, int] = {"unaware": 0, "hinted": 1, "deceived": 1, "knows": 2}


def _index(ledger: List[ReaderKnowledgeEntry], fact_id: str) -> int:
    for i, e in enumerate(ledger):
        if e.fact_id == fact_id:
            return i
    return -1


def _upsert(ledger: List[ReaderKnowledgeEntry], fact_id: str, cand_state: str,
            cand_strength: int, event_id: str, chapter: int, epoch: str) -> None:
    idx = _index(ledger, fact_id)
    if idx < 0:
        ledger.append(ReaderKnowledgeEntry(
            fact_id=fact_id, reader_state=cand_state, reader_strength=cand_strength,
            established_at_chapter=chapter, last_updated_chapter=chapter,
            source_event_id=event_id, epoch=epoch))
        return
    cur = ledger[idx]
    if _STATE_RANK[cand_state] < _STATE_RANK[cur.reader_state]:
        return  # hinted/deceived 不降级已有 knows（03 §6.3）
    ledger[idx] = cur.model_copy(update={
        "reader_state": cand_state,
        "reader_strength": max(cur.reader_strength, cand_strength),
        "source_event_id": event_id, "last_updated_chapter": chapter})


def reduce_reader(event: Event, state: StoryState) -> StoryState:
    ledger = list(state.reader_ledger)
    et = event.event_type
    fact_id = event.payload["fact_id"]

    if et == "READER_LEARNS":
        _upsert(ledger, fact_id, "knows",
                int(event.payload.get("strength", event.confidence)),
                event.event_id, event.chapter, event.epoch)
    elif et == "READER_DECEIVED":
        _upsert(ledger, fact_id, "deceived",
                int(event.payload.get("strength", event.confidence)),
                event.event_id, event.chapter, event.epoch)
    elif et == "READER_HINTED":
        _upsert(ledger, fact_id, "hinted",
                int(event.payload.get("strength", event.confidence)),
                event.event_id, event.chapter, event.epoch)
    else:  # pragma: no cover - 分派表外类型不应进入本 reducer
        raise ValueError(f"reduce_reader 收到非读者层事件: {et}")

    update: Dict[str, object] = {"reader_ledger": ledger}
    if et == "READER_HINTED" and state.foreshadowing:
        # 伏笔联动：planted→hinted（WP-A 设计稿 §3）
        update["foreshadowing"] = hint_foreshadows(
            state.foreshadowing, fact_id, event.event_id, event.chapter)
    return with_state_hash(state.model_copy(update=update))
