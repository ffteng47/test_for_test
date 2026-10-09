"""07 §4.3 通道 3：真实模型抽取通道。

模型输出按**不可信输入**处理：解析、逐条校验、坏料显式记录（05 §9 I6 不静默丢弃），
绝不因为「模型说了」就提交。三条铁律：
1. `seq` 由本模块重编为连续 0..n-1 —— event_id 由 (chapter, seq) 推出，模型重复编号会炸成 H6.4。
2. 凡 payload/confidence 出现 float 一律丢弃 —— 定点 ×1000 是 05 §5.5 的硬约束，float 会让
   `canonical_json` 在 commit 阶段抛错，归因链就此断掉。
3. 凡 actor/target/payload 里的 id 不在 State 词表里一律丢弃 —— 幻觉 id 会在下游炸成一串无法归因的违例。
`preconditions` 直接丢弃：Phase 0 允许因果为空（01 §5.2 E3'），模型无法知道本章将要生成的 event_id。
"""
from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple, get_args

from plot_engine.llm import LlmClient
from plot_engine.models.event import EventType
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState

_VALID_TYPES = frozenset(get_args(EventType))
_ID_RE = re.compile(r"^(?:char|fact|item|loc|faction|realm|ability|region|rel)_\d+$")


def _known_ids(state: Optional[StoryState]) -> Optional[set]:
    if state is None:
        return None
    ids: set = set()
    for field in ("characters", "facts", "items", "locations", "factions",
                  "realms", "abilities", "regions"):
        ids |= set(getattr(state, field))
    return ids


def _has_float(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_has_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_float(v) for v in value)
    return False


def _has_unknown_id(value, known: set) -> bool:
    if isinstance(value, str):
        return bool(_ID_RE.match(value)) and value not in known
    if isinstance(value, dict):
        return any(_has_unknown_id(v, known) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_unknown_id(v, known) for v in value)
    return False


def extract_json_array(raw: str) -> Optional[list]:
    """从模型回复里取第一个完整 JSON 数组：容忍 ``` 围栏与前后废话。"""
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, list) else None


def parse_proposals(raw: str, chapter: int,
                    state: Optional[StoryState] = None
                    ) -> Tuple[List[EventProposal], List[dict]]:
    """模型文本 → (合法 Proposal, 坏料记录)。坏料只记录原因，不猜、不补、不提交。"""
    array = extract_json_array(raw)
    if array is None:
        return [], [{"reason": "malformed_reply", "raw": raw[:200]}]

    known = _known_ids(state)
    out: List[EventProposal] = []
    bad: List[dict] = []
    for item in array:
        if not isinstance(item, dict):
            bad.append({"reason": "not_an_object", "item": item})
            continue
        etype = item.get("event_type") or item.get("proposed_event_type")
        if etype not in _VALID_TYPES:
            bad.append({"reason": "unknown_event_type", "item": etype})
            continue
        payload = item.get("payload") or {}
        conf = item.get("confidence", 700)
        if not isinstance(payload, dict) or _has_float(payload) or _has_float(conf):
            bad.append({"reason": "float_in_payload", "item": etype})
            continue
        refs = [item.get("actor"), item.get("target"), *payload.values()]
        if known is not None and any(_has_unknown_id(r, known) for r in refs):
            bad.append({"reason": "unknown_id", "item": etype})
            continue
        seq = len(out)
        out.append(EventProposal(
            proposed_event_type=etype,
            actor=item.get("actor"), target=item.get("target"),
            chapter=chapter, seq=seq,
            payload=dict(payload),
            confidence=conf if isinstance(conf, int) else 700,
            source_ref=item.get("source_ref") or f"llm:{chapter}#{seq}",
            extraction_method="llm", extraction_confidence=1000))
    return out, bad


def _vocab(state: StoryState) -> str:
    chars = ", ".join(f"{c.character_id}={c.name}" for c in state.characters.values())
    facts = ", ".join(f"{f.fact_id}: {f.proposition[:40]}" for f in state.facts.values())
    return f"已知角色: {chars or '（无）'}\n已知事实: {facts or '（无）'}"


def extract_prompt(draft, scene_plan, contract, state) -> List[dict]:
    """抽取提示：Taxonomy、State 词表、Contract 要求 + Draft 全文。"""
    taxonomy = " / ".join(sorted(_VALID_TYPES))
    required = " / ".join(e.event_type for e in contract.required_events) or "（无）"
    forbidden = " / ".join(contract.knowledge_forbidden) or "（无）"
    rules = [
        "你是叙事事件抽取器。只输出一个 JSON 数组，不要任何解释文字。",
        f"数组每个元素形如 "
        '{"event_type": str, "actor": str|null, "target": str|null, '
        '"payload": object, "source_ref": str}。',
        f"event_type 只能取: {taxonomy}。",
        "id 只能使用下面词表里出现过的，绝不自造 id。",
        "数值一律整数（不要小数）。不要输出 preconditions。",
        f"本章 Contract 要求的事件类型: {required}。",
        f"禁止把这些事实作为事件内容泄露: {forbidden}。",
    ]
    if state is not None:
        rules.insert(3, _vocab(state))
    return [{"role": "system", "content": "\n".join(rules)},
            {"role": "user", "content": f"正文：\n{draft[:6000]}"}]


def make_llm_channel(client: LlmClient, *, max_items: int = 24,
                     extract_role: str = "extract"):
    """产出 `stage0_extract(..., llm_channel=)` 需要的通道：(draft, scene_plan, contract, state) -> Proposal。"""
    def channel(draft, scene_plan, contract, state) -> List[EventProposal]:
        text, usage = client.complete(extract_role, extract_prompt(draft, scene_plan,
                                                                   contract, state))
        channel.total_tokens += usage.total
        props, bad = parse_proposals(text, getattr(contract, "chapter_no", 0), state)
        if len(props) > max_items:
            bad.append({"reason": "over_cap", "item": len(props)})
            props = props[:max_items]
        channel.malformed.extend(bad)
        channel.produced += len(props)
        return props

    channel.total_tokens = 0
    channel.produced = 0
    channel.malformed: List[dict] = []
    return channel
