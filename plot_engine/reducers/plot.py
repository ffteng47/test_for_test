"""Plot reducer：CASE_SOLVED / FORESHADOWING_SET / FORESHADOWING_PAID / CONTRACT_FULFILLED / CONTRACT_VIOLATED。

epoch_1（WP-A 设计稿 §3）：伏笔生命周期落地——SET 埋点、PAID 回收；
hinted 由 HINTS/READER_HINTED 联动（hint_foreshadows，供 belief/reader reducer 调用）；
due 是派生态不落账、expired 只由显式动作写入（reducer 不自发）。
CASE_SOLVED / CONTRACT_* 仍为 no-op（本轮不动，语义留后续批次）。
"""
from __future__ import annotations

from typing import List

from plot_engine.models.event import Event
from plot_engine.models.ledger import ForeshadowingEntry
from plot_engine.models.state import StoryState, with_state_hash

_PLOT_TYPES = {"CASE_SOLVED", "FORESHADOWING_SET", "FORESHADOWING_PAID",
               "CONTRACT_FULFILLED", "CONTRACT_VIOLATED"}

_PAIDABLE = {"planted", "hinted", "due"}


def hint_foreshadows(foreshadowing: List[ForeshadowingEntry], fact_id: str,
                     event_id: str, chapter: int) -> List[ForeshadowingEntry]:
    """HINTS/READER_HINTED 联动：planted→hinted，其余 lifecycle 不动（设计稿 §3）。"""
    out = []
    for e in foreshadowing:
        if e.fact_id == fact_id and e.lifecycle == "planted":
            e = e.model_copy(update={"lifecycle": "hinted",
                                      "source_event_id": event_id,
                                      "last_updated_chapter": chapter})
        out.append(e)
    return out


def reduce_plot(event: Event, state: StoryState) -> StoryState:
    et = event.event_type
    if et not in _PLOT_TYPES:  # pragma: no cover - 分派表外类型不应进入本 reducer
        raise ValueError(f"reduce_plot 收到非剧情类事件: {et}")

    if et == "FORESHADOWING_SET":
        p = event.payload
        fid = p["foreshadow_id"]
        entries = list(state.foreshadowing)
        if any(e.foreshadow_id == fid for e in entries):
            raise ValueError(f"重复 FORESHADOWING_SET: {fid}")
        entries.append(ForeshadowingEntry(
            foreshadow_id=fid, fact_id=p["fact_id"], lifecycle="planted",
            strength=int(p.get("strength", event.confidence)),
            planted_chapter=event.chapter, due_by_chapter=p["due_by_chapter"],
            source_event_id=event.event_id, last_updated_chapter=event.chapter,
            epoch=event.epoch))
        return with_state_hash(state.model_copy(update={"foreshadowing": entries}))

    if et == "FORESHADOWING_PAID":
        fid = event.payload["foreshadow_id"]
        entries = list(state.foreshadowing)
        for i, e in enumerate(entries):
            if e.foreshadow_id == fid:
                if e.lifecycle not in _PAIDABLE:
                    raise ValueError(
                        f"伏笔 {fid} 不可回收: lifecycle={e.lifecycle}")
                entries[i] = e.model_copy(update={
                    "lifecycle": "paid", "paid_chapter": event.chapter,
                    "last_updated_chapter": event.chapter})
                break
        else:
            raise ValueError(f"FORESHADOWING_PAID 引用不存在的伏笔 {fid}")
        return with_state_hash(state.model_copy(update={"foreshadowing": entries}))

    return with_state_hash(state)  # CASE_SOLVED / CONTRACT_*：no-op


def abandon_foreshadowing(state: StoryState, foreshadow_id: str,
                          chapter: int) -> StoryState:
    """显式人工动作：伏笔→expired（v0.12 裁定 5A；账可溯，不由 reducer/validator 自发）。"""
    entries = list(state.foreshadowing)
    for i, e in enumerate(entries):
        if e.foreshadow_id == foreshadow_id:
            if e.lifecycle == "paid":
                raise ValueError(f"已回收伏笔 {foreshadow_id} 不可放弃")
            entries[i] = e.model_copy(update={
                "lifecycle": "expired", "last_updated_chapter": chapter})
            return with_state_hash(state.model_copy(update={"foreshadowing": entries}))
    raise ValueError(f"abandon 引用不存在的伏笔 {foreshadow_id}")
