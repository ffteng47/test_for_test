"""顶层 Reducer：Event → StoryState 的类别分派表（03 §8 + 07 §6.1）。

分派覆盖 EventType 全部 26 个取值；未映射类型直接 ValueError。
Reduce 是纯函数：不落盘、无副作用、按 (chapter, seq) 拓扑序由上层驱动（07 §6.2 R1/R2）。
"""
from __future__ import annotations

from typing import Callable, Dict

from plot_engine.models.event import Event
from plot_engine.models.state import StoryState
from plot_engine.reducers.belief import reduce_belief
from plot_engine.reducers.knowledge import reduce_knowledge
from plot_engine.reducers.plot import reduce_plot
from plot_engine.reducers.reader import reduce_reader
from plot_engine.reducers.world import reduce_world

_DISPATCH: Dict[str, Callable[[Event, StoryState], StoryState]] = {
    # Knowledge（03 §4/§5.4）
    "OBSERVES": reduce_knowledge,
    "READS": reduce_knowledge,
    "IS_TOLD": reduce_knowledge,
    "INFERS": reduce_knowledge,
    "FACT_CONTRADICTED": reduce_knowledge,
    # Belief + Statement（03 §5）
    "BELIEVES": reduce_belief,
    "SUSPECTS": reduce_belief,
    "DOUBTS": reduce_belief,
    "STATES": reduce_belief,
    "LIES": reduce_belief,
    "OMITS": reduce_belief,
    "HINTS": reduce_belief,
    # World（10）
    "HAPPENS": reduce_world,
    "REVEALS": reduce_world,
    "CHANGES": reduce_world,
    "ITEM_ACQUIRED": reduce_world,
    "ITEM_CONSUMED": reduce_world,
    "RELATIONSHIP_CHANGED": reduce_world,
    # Reader（03 §6）
    "READER_LEARNS": reduce_reader,
    "READER_DECEIVED": reduce_reader,
    "READER_HINTED": reduce_reader,
    # Plot（04，Phase 0 thin）
    "CASE_SOLVED": reduce_plot,
    "FORESHADOWING_SET": reduce_plot,
    "FORESHADOWING_PAID": reduce_plot,
    "CONTRACT_FULFILLED": reduce_plot,
    "CONTRACT_VIOLATED": reduce_plot,
}


class Reducer:
    def apply(self, event: Event, state: StoryState) -> StoryState:
        """纯函数：输入 State + Event → 输出新 State（07 §6.1）。"""
        fn = _DISPATCH.get(event.event_type)
        if fn is None:
            raise ValueError(f"unmapped event_type {event.event_type}")
        return fn(event, state)
