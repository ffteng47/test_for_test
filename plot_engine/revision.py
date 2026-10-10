"""06 修订协议：Root Cause 归因 + 分层回退循环（R1–R6、§4.0–§4.7、§5、§6、§7）。

本模块只**归因与调度**：读 `ValidationResult` / `CommitOutcome`，决定回退到哪一层、
还剩几轮、是否振荡、是否停机，并把每轮写进 `RevisionTrace`。
绝不改 HARD 判据（08 I2）、绝不做网络调用——回退动作是注入的纯函数 `ChapterContext →
ChapterContext`（Phase 0 网络无关，Auto-Mode #6），重跑 Stage 0→3 由调用方经 `recommit` 提供。
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from plot_engine.models.commit import CommitOutcome
from plot_engine.models.contract import ChapterContract
from plot_engine.models.revision import (
    RevisionPolicy, RevisionStep, RevisionTrace, RootCause, RootCauseLevel,
)
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.validator import ValidationResult

# 回退动作只改「本章产物」，不碰 State：Contract 层换 Contract，Writer 层换 Draft。
@dataclasses.dataclass(frozen=True)
class ChapterContext:
    contract: ChapterContract
    scene_plan: Optional[ScenePlan] = None
    draft: str = ""
    # 动作需要的上下文：`state` = 本章开工时的已提交状态（重议契约要对它求解），
    # `unsatisfied_event_types` = 循环在调用动作前填进来的 H5.1 evidence（事件类型，非中文消息）。
    state: Optional[StoryState] = None
    unsatisfied_event_types: List[str] = dataclasses.field(default_factory=list)


Action = Callable[[ChapterContext], ChapterContext]
Recommit = Callable[[ChapterContext], CommitOutcome]

# 06 §4 各层症状 → rule_id。未列出的 rule 保守归 writer（§4.1，最低成本回退层）。
RULE_TO_LEVEL: Dict[str, RootCauseLevel] = {
    # §4.0 Extraction：置信度不足/被隔离/抽取与 Draft 不符/markup 无对应 Proposal
    "H8.1": "extraction", "H8.2": "extraction", "H8.3": "extraction",
    "H6.2": "extraction", "H6.4": "extraction", "H6.5": "extraction",
    "MALFORMED_PROPOSAL": "extraction",
    # §4.5 Event：Taxonomy 表达不了 / 因果图无法构造 → 需 epoch 升级，非自动修
    "H6.1": "event", "H6.3": "event",
    # §4.4 Fact：无法归一化 / canonical 冲突 → 需 epoch 升级
    "I1": "fact", "R7": "fact",
    # §4.2 Contract：Contract 要求的事件在当前 State 下无法发生
    "H5.1": "contract",
    # §4.2 Contract：must_change 的 Δ 在本章没有实现事件可兑现（W1）。归 writer 的话，
    # 阶梯要先烧满重写预算才轮到契约层，而重写永远变不出一条不存在的 Δ（批次 4 实测）。
    "H5.3": "contract",
    # §4.7 State：replay 对不上账
    "REPLAY_INCONSISTENT": "state",
}

# §4.0：Extraction 优先级最高；§4.7 State 停机次先；§4.4/§4.5 需人工先于自动重写
_LEVEL_PRIORITY: Sequence[RootCauseLevel] = (
    "extraction", "state", "fact", "event", "contract", "arc", "validator", "writer")

# §4 层级 → 阶梯动作名（§5 escalation）。fact/event/validator 无自动动作（要嘛改协议要嘛 epoch 升级）。
_LEVEL_TO_ACTION: Dict[str, str] = {
    "extraction": "rerun_extraction",
    "writer": "rewrite_scene",
    "contract": "renegotiate_contract",
    "arc": "escalate_to_arc",
}

_HUMAN_LEVELS: Set[str] = {"fact", "event", "validator"}


def classify_root_cause(result: Optional[ValidationResult]) -> Optional[RootCause]:
    """HARD 集合 → 单一 Root Cause（06 R1）。无 HARD 返回 None（无可归因）。"""
    if result is None or not result.hard_violations:
        return None
    by_level: Dict[str, Tuple[object, int]] = {}
    for f in result.hard_violations:
        mapped = RULE_TO_LEVEL.get(f.rule_id)
        if mapped is None and f.rule_id.startswith("H7."):
            mapped = "contract"                 # §4.2：Contract 自校验不过 = Contract 本身有问题
        level: RootCauseLevel = mapped or "writer"      # type: ignore[assignment]
        confidence = 1000 if mapped else 500            # 未映射规则：低置信归因，留待人工复核
        by_level.setdefault(level, (f, confidence))
    for level in _LEVEL_PRIORITY:
        if level in by_level:
            f, confidence = by_level[level]
            return RootCause(level=level, evidence=f.message,        # type: ignore[attr-defined]
                             violated_rule_id=f.rule_id,             # type: ignore[attr-defined]
                             confidence=confidence)
    return None


def action_for(level: RootCauseLevel, policy: RevisionPolicy) -> Optional[str]:
    """错误层级决定回退层级（06 R2）。不可自动修的层返回 None → 人工。"""
    name = _LEVEL_TO_ACTION.get(level)
    return name if name in policy.escalation else None


def is_oscillating(prev: Sequence[str], cur: Sequence[str]) -> bool:
    """06 §7：连续两轮 violation **集合**相同（顺序无关）→ 振荡 → 立即升级下一层级。"""
    return bool(prev) and set(prev) == set(cur)


def _unsatisfied_types(result: ValidationResult) -> List[str]:
    """H5.1 的 evidence 就是落空的事件类型（05 结构化字段）；动作靠它判断放宽哪一条，
    绝不去解析中文消息。"""
    return sorted({f.evidence for f in result.hard_violations
                   if f.rule_id == "H5.1" and f.evidence})


class RevisionLoop:
    """单章修订循环（06 §6 七步）。`actions` 里没提供的动作一律视为不可执行 → 转人工。"""

    def __init__(self, *, policy: Optional[RevisionPolicy] = None,
                 actions: Mapping[str, Action] = {}) -> None:
        self.policy = policy or RevisionPolicy()
        self.actions = dict(actions)

    def _ladder_next(self, action: str) -> Optional[str]:
        ladder = self.policy.escalation
        if action not in ladder:
            return None
        for nxt in ladder[ladder.index(action) + 1:]:
            if nxt in self.actions:
                return nxt
        return None

    def run_chapter(self, story_id: str, chapter_no: int, ctx: ChapterContext,
                    recommit: Recommit) -> Tuple[RevisionTrace, CommitOutcome]:
        trace = RevisionTrace(story_id=story_id, chapter_no=chapter_no)
        outcome = recommit(ctx)
        if outcome.status == "OK":
            trace.final_status = "OK"
            return trace, outcome

        action: Optional[str] = None
        prev_violations: List[str] = []
        while True:
            if outcome.status == "REPLAY_INCONSISTENT":       # §4.7：停 pipeline，不再重试
                trace.halt = True
                trace.final_status = "HALT"
                return trace, outcome

            rc = classify_root_cause(outcome.validation)
            if rc is None:                                     # CONFLICT/DUPLICATE/IO_ERROR：非文本问题
                trace.needs_human = True
                trace.final_status = "NEEDS_HUMAN"
                return trace, outcome

            violations = sorted({f.rule_id for f in outcome.validation.hard_violations})
            if rc.level in _HUMAN_LEVELS:                      # §4.4/§4.5/§4.6：改协议或走 epoch 升级
                trace.needs_human = True
                trace.final_status = "NEEDS_HUMAN"
                trace.steps.append(RevisionStep(round_no=trace.rounds + 1, root_cause=rc,
                                                action="needs_human", violations=violations,
                                                committed=False))
                return trace, outcome

            if action is None:
                action = action_for(rc.level, self.policy)
            elif self.policy.oscillation_detection and is_oscillating(prev_violations, violations):
                action = self._ladder_next(action)             # §7：立即升级，不烧完预算
            if action is None or action not in self.actions:
                trace.needs_human = True
                trace.final_status = "NEEDS_HUMAN"
                return trace, outcome

            ctx = self.actions[action](dataclasses.replace(
                ctx, unsatisfied_event_types=_unsatisfied_types(outcome.validation)))
            trace.rounds += 1
            outcome = recommit(ctx)
            trace.steps.append(RevisionStep(round_no=trace.rounds, root_cause=rc,
                                            action=action, violations=violations,
                                            committed=outcome.status == "OK"))
            prev_violations = violations

            if outcome.status == "OK":
                trace.final_status = "OK"
                return trace, outcome
            if trace.rounds >= min(self.policy.max_rounds,
                                   self.policy.human_escalation_threshold):
                trace.needs_human = True                       # §6 步 6：总轮数触顶 → 人工介入
                trace.final_status = "FAIL"
                return trace, outcome
