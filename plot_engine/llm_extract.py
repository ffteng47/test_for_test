"""07 §4.3 通道 3：真实模型抽取通道。

模型输出按**不可信输入**处理：解析、逐条校验、坏料显式记录（05 §9 I6 不静默丢弃），
绝不因为「模型说了」就提交。三条铁律：
1. `seq` 由本模块重编为连续 0..n-1 —— event_id 由 (chapter, seq) 推出，模型重复编号会炸成 H6.4。
2. 凡 payload/confidence 出现 float 一律丢弃 —— 定点 ×1000 是 05 §5.5 的硬约束，float 会让
   `canonical_json` 在 commit 阶段抛错，归因链就此断掉。定点键（trust_level 等）给了 null/字符串
   也一样丢：reducer 会拿它做整数算术，炸的是整个进程，一次采样的读数一起没了。
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

# 本通道只承接 reducer 真能消费的 event_type，且键名逐一对齐 01 §4.1 的实际取用（reducer 里
# 的 event.payload[...]）。缺键的产物放下去只会变成 MALFORMED_PROPOSAL 级联，归因反而更难。
PAYLOAD_SCHEMA: Dict[str, Tuple[str, ...]] = {
    "OBSERVES": ("fact_id",),
    "READS": ("fact_id",),
    "IS_TOLD": ("fact_id", "trust_level", "message_strength"),
    "INFERS": ("conclusion_fact_id", "evidence_fact_ids"),
    "FACT_CONTRADICTED": ("fact_id",),
    "BELIEVES": ("fact_id", "belief_strength"),
    "SUSPECTS": ("fact_id",),
    "DOUBTS": ("fact_id",),
    "STATES": ("fact_id", "audience"),
    "LIES": ("stated_fact_id", "audience"),
    "OMITS": (),
    "HINTS": ("fact_id", "audience"),
    "HAPPENS": (),
    "REVEALS": ("fact_id", "new_narrative_truth"),
}
# 提示词不能用 `TYPE:key` 形态 —— 实测模型会把它整段抄成 payload 里的 {"TYPE": "key"}。
_SCHEMA_HINT = "；".join(
    f"type {t} 的 payload 只放 {','.join(k) if k else '空对象'}"
    for t, k in PAYLOAD_SCHEMA.items())


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


# 词表里这些键的值必须是可解析的实体 id（整数/自由文本都不行）；
# 与之相对 trust_level/belief_strength 是定点整数，new_narrative_truth 是枚举。
_ID_VALUE_KEYS = {"fact_id", "conclusion_fact_id", "stated_fact_id", "audience"}
_ID_LIST_KEYS = {"evidence_fact_ids"}
# reducer 拿这些键做整数算术（03 §4.3 R3/R4）：null / 字符串 / bool 放下去就是 TypeError，
# 而 TypeError 会炸掉整个进程——一次采样的读数全丢，比丢一条提案贵得多。
_FIXED_POINT_KEYS = {"trust_level", "message_strength", "belief_strength"}


def _unusable_keys(payload: dict, schema: Tuple[str, ...]) -> List[str]:
    """schema 里「没有可用值」的键：缺失、为 null，或定点键不是 int。"""
    def usable(value, key):
        if value is None:
            return False
        if key in _FIXED_POINT_KEYS:
            return isinstance(value, int) and not isinstance(value, bool)
        return True
    return [k for k in schema if not usable(payload.get(k), k)]


def _bad_id_key(etype: str, payload: dict, known: set) -> Optional[str]:
    """返回第一个「该是 id 却不是已知 id」的 `TYPE.key=value` 描述，None 表示干净。"""
    def check(key, value):
        if key in _ID_LIST_KEYS:
            if (isinstance(value, list) and value
                    and all(isinstance(v, str) and v in known for v in value)):
                return None
        elif isinstance(value, str) and value in known:
            return None
        return f"{etype}.{key}={value!r}"

    for key in _ID_VALUE_KEYS | _ID_LIST_KEYS:
        if key in payload:
            found = check(key, payload[key])
            if found:
                return found
    return None


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
        if etype not in PAYLOAD_SCHEMA:
            bad.append({"reason": "type_not_supported", "item": etype})
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
        missing = _unusable_keys(payload, PAYLOAD_SCHEMA[etype])
        if missing:
            bad.append({"reason": "missing_payload_keys",
                        "item": f"{etype} 缺 {','.join(missing)}"})
            continue
        if known is not None:
            bad_ref = _bad_id_key(etype, payload, known)
            if bad_ref:
                bad.append({"reason": "id_value_not_id", "item": bad_ref})
                continue
        # 模型会把 schema 提示 `OBSERVES:fact_id` 回声成 payload 键。事件本身有效，
        # 剥掉回声键并记账，别让提示词脚手架进 EventLog（08 §10 I3：不可静默）。
        declared = set(PAYLOAD_SCHEMA[etype])
        for extra in [k for k in payload if k not in declared]:
            bad.append({"reason": "stripped_payload_key", "item": f"{etype}.{extra}"})
            payload.pop(extra)
        seq = len(out)
        para = item.get("paragraph")
        source_ref = (item.get("source_ref")
                      or (f"para:{para}" if isinstance(para, int) and not isinstance(para, bool)
                          else f"llm:{chapter}#{seq}"))
        out.append(EventProposal(
            proposed_event_type=etype,
            actor=item.get("actor"), target=item.get("target"),
            chapter=chapter, seq=seq,
            payload=dict(payload),
            confidence=conf if isinstance(conf, int) else 700,
            source_ref=source_ref,
            extraction_method="llm", extraction_confidence=1000))
    return out, bad


def _vocab(state: StoryState) -> str:
    chars = ", ".join(f"{c.character_id}={c.name}" for c in state.characters.values())
    facts = ", ".join(f"{f.fact_id}: {f.proposition[:40]}" for f in state.facts.values())
    return f"已知角色: {chars or '（无）'}\n已知事实: {facts or '（无）'}"


def _strip_markup(draft: str) -> str:
    """composer 的 `<!-- ... -->` 标记是通道 1 的答案；LLM 通道读到它就失去独立性（07 §4.3）。"""
    return re.sub(r"<!--.*?-->", "", draft or "", flags=re.S).strip()


def _numbered(draft: str) -> str:
    """正文按段号给出：模型只需回 `paragraph: N`，抽取产物才是可对齐的 span。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", (draft or "").strip()) if p.strip()]
    return "\n".join(f"{i}. {p[:400]}" for i, p in enumerate(paras, 1))


def extract_prompt(draft, scene_plan, contract, state) -> List[dict]:
    """抽取提示：可承接的事件类型 + payload 键 + State 词表 + 带段号正文。

    **不给 Contract 的 required_events**：实测模型看到答案键后，即使正文一个事件都没有
    也会照单输出 OBSERVES/INFERS，H5.1/H5.3 就变成抽取器自证。通道必须彼此独立（07 §4.3）。
    """
    taxonomy = " / ".join(sorted(PAYLOAD_SCHEMA))
    forbidden = " / ".join(contract.knowledge_forbidden) or "（无）"
    rules = [
        "你是叙事事件抽取器。只输出一个 JSON 数组，不要任何解释文字。",
        '数组每个元素形如 {"event_type": str, "actor": str|null, "target": str|null, '
        '"payload": object, "paragraph": 整数段号}。',
        "event_type 只能取（本阶段只承接这些，其余写了也没用）:",
        f"  {taxonomy}。",
        f"payload 必须给全这些键: {_SCHEMA_HINT}。",
        "payload 的键名只能是上面列出的键名本身，绝不要把事件类型名（如 OBSERVES）写成键。",
        "fact_id / conclusion_fact_id / stated_fact_id / audience 这些键的值必须是下面词表里"
        "出现过的 id 字符串（如 \"fact_000001\"），绝不要写成 3 这样的裸整数，也绝不要用"
        "「印章」这类自由文本代替 id。",
        "只有 trust_level / message_strength / belief_strength 这类数值键才给整数，且一律整数（不要小数）。",
        "actor/target 用词表里的 id，或 null。id 绝不自造。不要输出 preconditions。",
        "只抽取正文里真实发生的事件；正文没有的事件就不要输出，宁缺毋造。",
        f"禁止把这些事实作为事件内容泄露: {forbidden}。",
    ]
    if state is not None:
        rules.insert(5, _vocab(state))
    return [{"role": "system", "content": "\n".join(rules)},
            {"role": "user", "content": f"正文（段落编号）：\n{_numbered(draft)[:6000]}"}]


def make_llm_channel(client: LlmClient, *, max_items: int = 24,
                     extract_role: str = "extract"):
    """产出 `stage0_extract(..., llm_channel=)` 需要的通道：(draft, scene_plan, contract, state) -> Proposal。"""
    def channel(draft, scene_plan, contract, state) -> List[EventProposal]:
        text, usage = client.complete(extract_role, extract_prompt(_strip_markup(draft),
                                                                   scene_plan,
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
