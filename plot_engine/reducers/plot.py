"""Plot reducer：CASE_SOLVED / FORESHADOWING_SET / FORESHADOWING_PAID / CONTRACT_FULFILLED / CONTRACT_VIOLATED。

Phase 0：剧情层事件只做哈希重打（no-op），语义留给 Contract 层（后续计划），不发明字段。
"""
from __future__ import annotations

from plot_engine.models.event import Event
from plot_engine.models.state import StoryState, with_state_hash

_PLOT_TYPES = {"CASE_SOLVED", "FORESHADOWING_SET", "FORESHADOWING_PAID",
               "CONTRACT_FULFILLED", "CONTRACT_VIOLATED"}


def reduce_plot(event: Event, state: StoryState) -> StoryState:
    if event.event_type not in _PLOT_TYPES:  # pragma: no cover - 分派表外类型不应进入本 reducer
        raise ValueError(f"reduce_plot 收到非剧情类事件: {event.event_type}")
    return with_state_hash(state)
