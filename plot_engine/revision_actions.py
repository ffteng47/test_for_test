"""06 §4.2 Contract Error 的回退动作：重议 Chapter Contract。

`renegotiate_contract` = **按 04 §4.3 重新派生**本章契约（version+1，04 I3/I4），
只放宽**作者自己写进 `arc.reader_beats` 的要求**；由 Arc 强制派生的要求
（D3 turning_point、D6 逾期 gate）一条都不许掉——那是「把通过标准改成模型刚好达得到」
的入口，Phase-0 报告第 3 节的两次假通过就是这么来的。
Draft 与 ScenePlan 保持原样：06 §4.2 明写「不重写 Draft」，而计划本身仍是产出这份
Draft 的那份计划（`contract_version` 因此停在原值，不假装重规划过）。
"""
from __future__ import annotations

import dataclasses

from plot_engine.derive import (arc_mandated_event_types, derive_chapter_contract,
                                intents_by_chapter)
from plot_engine.models.contract import ArcContract
from plot_engine.revision import Action, ChapterContext


def renegotiate_contract(arc: ArcContract, *, created_at: str) -> Action:
    """契约层 Root Cause → version+1 的新契约；放宽范围受 `arc_mandated_event_types` 约束。"""
    def action(ctx: ChapterContext) -> ChapterContext:
        if ctx.state is None:
            raise ValueError("重议契约需要本章开工时的 StoryState（ctx.state 为空）")
        ch = ctx.contract.chapter_no
        authored = {e.event_type for e in intents_by_chapter(arc)[ch].required_events}
        relaxable = (set(ctx.unsatisfied_event_types) & authored) - \
            arc_mandated_event_types(arc, ch)               # Arc 强制的永不进入这一侧
        fresh = derive_chapter_contract(arc, ch, ctx.state, created_at=created_at,
                                       version=ctx.contract.version + 1)
        kept = [e for e in fresh.required_events if e.event_type not in relaxable]
        return dataclasses.replace(
            ctx, contract=fresh.model_copy(update={"required_events": kept}))

    return action
