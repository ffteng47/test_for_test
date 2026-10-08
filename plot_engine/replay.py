"""逐章 Replay + state_hash 对账（07 §6.3 I5、§7.5 R5/R6）。

在线提交与重放必须走同一条 reduce 路径：`apply_events` 是唯一的驱动函数
（按 (chapter, seq) 排序、进入新章时先推进 chapter_no、由 reducer 打最终哈希）。
Phase 0 约定：被校验的章节至少含一个事件（空章无法从事件流推断章号推进）。
"""
from __future__ import annotations

from typing import Iterable, List

from plot_engine.eventlog import EventLog
from plot_engine.models.event import Event
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore


def apply_events(state: StoryState, events: Iterable[Event], reducer: Reducer) -> StoryState:
    for ev in sorted(events, key=lambda e: (e.chapter, e.seq)):
        if state.chapter_no != ev.chapter:
            state = state.model_copy(update={"chapter_no": ev.chapter})
        state = reducer.apply(ev, state)
    return state


def replay_to_chapter(store: StateStore, log: EventLog, reducer: Reducer,
                      story_id: str, chapter_no: int) -> StoryState:
    base = store.load_snapshot_at_or_before(story_id, chapter_no)
    if base is None:
        raise ValueError(f"story {story_id} 在章 {chapter_no} 之前无快照（需先 init_genesis）")
    events: List[Event] = log.read_range(story_id, base.chapter_no + 1, chapter_no)
    return apply_events(base.state, events, reducer)


def verify_parity(store: StateStore, log: EventLog, reducer: Reducer,
                  story_id: str, chapter_no: int) -> bool:
    replayed = replay_to_chapter(store, log, reducer, story_id, chapter_no)
    return replayed.state_hash == store.load_latest(story_id).state_hash
