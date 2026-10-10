"""06 §4.2 Contract Error 的回退动作：重议 Chapter Contract。

`renegotiate_contract` = **按 04 §4.3 重新派生**本章契约（version+1，04 I3/I4），
只放宽**作者自己写进 `arc.reader_beats` 的要求**；由 Arc 强制派生的要求
（D3 turning_point、D6 逾期 gate）一条都不许掉——那是「把通过标准改成模型刚好达得到」
的入口，Phase-0 报告第 3 节的两次假通过就是这么来的。
落空的正好是这类强制项时直接抛 `ArcConflict`：重议帮不了它，继续跑只会把 Arc 层缺陷
伪装成「重议过了」。
Draft 与 ScenePlan 保持原样：06 §4.2 明写「不重写 Draft」，而计划本身仍是产出这份
Draft 的那份计划（`contract_version` 因此停在原值，不假装重规划过）。
"""
from __future__ import annotations

import dataclasses

from plot_engine.derive import (ArcConflict, arc_mandated_event_types,
                                derive_chapter_contract, intents_by_chapter)
from plot_engine.models.contract import ArcContract
from plot_engine.revision import Action, ChapterContext


def renegotiate_contract(arc: ArcContract, *, created_at: str) -> Action:
    """契约层 Root Cause → version+1 的新契约；放宽范围受 `arc_mandated_event_types` 约束。"""
    def action(ctx: ChapterContext) -> ChapterContext:
        if ctx.state is None:
            raise ValueError("重议契约需要本章开工时的 StoryState（ctx.state 为空）")
        ch = ctx.contract.chapter_no
        blocked = sorted(set(ctx.unsatisfied_event_types) & arc_mandated_event_types(arc, ch))
        if blocked:
            # Arc 强制项落空 ⇒ 重议一条也放宽不了，再派生一次只会产出同一份被同一规则
            # 拒掉的契约。静默重议等于把 Arc 层缺陷伪装成「重议通过」，还顺手烧掉剩下的
            # 修订预算（06 §4.3：Arc Error 该回 Arc 层，不该在契约层兜圈）。
            raise ArcConflict(f"{arc.arc_id} 第 {ch} 章落空的事件类型是 Arc 强制项，"
                              f"契约层无权放宽：{blocked}")
        authored = {e.event_type for e in intents_by_chapter(arc)[ch].required_events}
        relaxable = (set(ctx.unsatisfied_event_types) & authored) - \
            arc_mandated_event_types(arc, ch)               # Arc 强制的永不进入这一侧
        fresh = derive_chapter_contract(arc, ch, ctx.state, created_at=created_at,
                                       version=ctx.contract.version + 1)
        kept = [e for e in fresh.required_events if e.event_type not in relaxable]
        return dataclasses.replace(
            ctx, contract=fresh.model_copy(update={"required_events": kept}))

    return action
