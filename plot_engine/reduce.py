"""Stage 2 驱动：`reduce_commit` —— 与 Stage 1 沙盒同一条 reduce 路径（07 §6）。

单一职责：把整批 Proposal 复用 `Validator._review`（H8 闸门 → markup 合并 → 沙盒模拟）
得到 authoritative 判定与 `Simulation`，再以 replay 的 `apply_events` 驱动产出**将持久化**的
`new_state` 与 `applied` 事件（只含成功施加者，天然排除 H8.2 隔离 / MALFORMED，I9），
最后对 `new_state` + `applied` 跑 `assert_consistent`。任一 HARD（判定或一致性）都阻断（Review Focus #5）。
"""
from __future__ import annotations

import dataclasses
from typing import Dict, FrozenSet, List, Optional

from plot_engine.consistency import assert_consistent
from plot_engine.models.event import Event
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.replay import apply_events
from plot_engine.validator import Simulation, Validator, ValidationResult


@dataclasses.dataclass
class ReducedBatch:
    new_state: Optional[StoryState]        # None → 短路/无模拟，不可提交
    applied: List[Event]
    validation: ValidationResult
    quarantined: int                       # H8.2 隔离数
    consistency: List[Dict[str, object]]   # assert_consistent 输出

    def committable(self) -> bool:
        if self.new_state is None:
            return False
        if not self.validation.can_commit():
            return False
        return not any(f["severity"] == "hard" for f in self.consistency)


def reduce_commit(state: StoryState, proposals: List[EventProposal], contract,
                  draft: str, epoch: str,
                  *, committed_event_ids: FrozenSet[str] = frozenset(),
                  validator: Optional[Validator] = None) -> ReducedBatch:
    validator = validator or Validator()
    result, sim = validator._review(draft, proposals, contract, state,
                                    committed_event_ids=committed_event_ids)
    quarantined = sum(1 for f in result.hard_violations if f.rule_id == "H8.2")
    if sim is None:                        # H8.1 整批短路，无事件进入
        return ReducedBatch(None, [], result, quarantined, [])
    applied = sim.applied
    new_state = apply_events(state, applied, Reducer())
    consistency = assert_consistent(new_state, applied) if applied else []
    return ReducedBatch(new_state, applied, result, quarantined, consistency)
