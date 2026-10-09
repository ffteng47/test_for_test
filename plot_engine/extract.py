"""Stage-0 四通道 Proposal 合成 + 置信度联动设值（07 §4.3）。

通道：1 markup（`Validator` 内部再派生，本模块不产）、2 规则、3 LLM、4 交叉验证。
本模块只做**机制**：把注入的规则/LLM 通道产物按「同一段落」对齐，设 `extraction_confidence`
（一致→hybrid/1000；单通道→700；冲突→500），联动判定（R1/R2）交给下游 `_h8_gate`。
Phase 0 网络无关：`rule_channel`/`llm_channel` 为注入 `Callable`，默认 `None` → 贡献空。
Stage-0 只产**叙事类** Proposal；READER_* 属 markup 通道，此处过滤以防双计。
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from plot_engine.canonical import canonical_json
from plot_engine.models.proposal import EventProposal

_READER_KINDS = frozenset({"READER_LEARNS", "READER_HINTED", "READER_DECEIVED"})

RuleChannel = Callable[..., List[EventProposal]]
LLMChannel = Callable[..., List[EventProposal]]


def _span(source_ref: str) -> str:
    """同一段落定位：取 `#` 之前的部分（markup 后缀 #seq 不参与对齐）。"""
    return source_ref.split("#", 1)[0]


def _key(p: EventProposal):
    return (p.proposed_event_type, p.actor, p.target,
            canonical_json(p.payload))


def cross_validate(rule: List[EventProposal], llm: List[EventProposal]
                   ) -> Tuple[List[EventProposal], List[dict]]:
    """按 span 对齐规则与 LLM 通道，设置信度。返回 (合成 Proposal, 冲突记录)。"""
    spans: dict = {}
    for p in rule:
        spans.setdefault(_span(p.source_ref), {"rule": [], "llm": []})["rule"].append(p)
    for p in llm:
        spans.setdefault(_span(p.source_ref), {"rule": [], "llm": []})["llm"].append(p)

    merged: List[EventProposal] = []
    conflicts: List[dict] = []
    for span in sorted(spans):
        r, l = spans[span]["rule"], spans[span]["llm"]
        if r and l:
            if {_key(p) for p in r} == {_key(p) for p in l}:      # 一致 → hybrid/1000
                for p in r:
                    merged.append(p.model_copy(update={
                        "extraction_method": "hybrid", "extraction_confidence": 1000}))
            else:                                                  # 冲突 → 两侧各 500（H8.2x）
                for p in r + l:
                    merged.append(p.model_copy(update={"extraction_confidence": 500}))
                conflicts.append({"span": span,
                                  "rule_keys": sorted(map(str, (_key(p) for p in r))),
                                  "llm_keys": sorted(map(str, (_key(p) for p in l)))})
        elif r:
            for p in r:                                            # 单通道 → 700
                merged.append(p.model_copy(update={"extraction_confidence": 700}))
        else:
            for p in l:
                merged.append(p.model_copy(update={"extraction_confidence": 700}))
    return merged, conflicts


def stage0_extract(draft: str, scene_plan, contract, state: "StoryState",
                   *, chapter: int, rule_channel: Optional[RuleChannel] = None,
                   llm_channel: Optional[LLMChannel] = None) -> List[EventProposal]:
    """合成叙事类 Proposal（rule⊕llm 交叉验证后），按 span 稳定序重编 seq。"""
    rule = rule_channel(scene_plan, contract, state) if rule_channel else []
    llm = llm_channel(draft, scene_plan, contract, state) if llm_channel else []
    merged, _conflicts = cross_validate(list(rule), list(llm))
    narrative = [p for p in merged if p.proposed_event_type not in _READER_KINDS]
    return [p.model_copy(update={"seq": i, "chapter": chapter})
            for i, p in enumerate(narrative)]
