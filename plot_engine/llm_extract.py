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
from typing import Any, Dict, List, Optional, Tuple, get_args

from plot_engine import instr as _instr
from plot_engine.llm import LlmClient
from plot_engine.models.event import EventType
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState

_VALID_TYPES = frozenset(get_args(EventType))
_ID_RE = re.compile(r"^(?:char|fact|item|loc|faction|realm|ability|region|rel)_\d+$")
# 尺的刻度号：写进 run.log，读数才能归到某一把尺上。v3.1 = 纯模型抽取；
# v3.2 = 加上 `_promote_infers` 确定性提升（`docs/phase1-merged-plan-final.md` §7.3-1）。
# v3.3 = 抽取提示词加「类型怎么选」判据（E18：belief 三兄弟与 knowledge 四兄弟无可区分口径）
#        ⇒ 抽取读数与 v3.2 不可并列，历史读数靠尺戳分开。
# v3.4 = W4b 裁定执行（tff，2026-10-14）：删掉「数值键一律给 700」那句。
#        位置核查（重要，别再找错）：该句**从未进生产提示词 extract_prompt**，它只存在于
#        探针的 v3.4 草案补丁 `sampling/_probe_believes.py` 的 `v34_patch()`（追加在
#        「payload 必须给全这些键」之后）——已从该补丁删除。生产面本来就是「不给默认」，
#        故 v3.3→v3.4 的提示词文本零变化；这次 bump 记录的是 W4b 裁定 + W4a 代码兜底
#        正式进入冻结面：缺省补 700 由代码做并记 `defaulted_fixed_point` 账。
#        读数与 v3.3 不可并列的原因：v3.3 时代一个 700 分不清是模型真判断还是抄默认，
#        v3.4 起 700 = 模型真判断，缺省 = 代码补 + 台账有账。
# v3.5 = 修 schema 提示的措辞诱发（tff 裁定，2026-10-14）：`type {t} 的 payload 只放 X`
#        里的裸词 "type" 被 qwen2.5:14b 忠实抄成键名 {"type": "fact_000001"}（W5 冒烟实例），
#        是 `TYPE:key` 变体（见 :59 案底）之后的**第二个变体**。改为「事件 {t}：payload
#        应包含 X」，且不用"只放"——它同样可能被抄成键。触碰尺面 ⇒ 与 v3.4 读数不同表。
#        同时 missing_payload_keys 坏料补记 gave（模型实际给的键），把「没写」与「改名」
#        在废卷筐里分开——此前两者同形，只能人肉看 raw 才发现（取证缺陷）。
# v3.6 (a) 归因面（tff 裁定 2026-10-14，§16 ch06 解剖）：IS_TOLD 的 actor=听的人这个约定
#        只活在夹具 docstring（experiment_10ch `_told`），提示词从未告诉模型 ⇒ 抽取器把
#        说者记成 actor，两方 ledger 全记错、H2.2 双杀。补一行判据文。触碰尺面 ⇒ 读数离
#        v3.5 表，重基线（v4e×3）必须在这行生效**之后**跑。
# v3.7 已由 #70 型别批烧掉（不复用）。
# v3.8 = WP-A epoch_1 伏笔事件进抽取面（设计稿 §2.4、v0.12 裁定 4A）：PAYLOAD_SCHEMA 增
#        FORESHADOWING_SET（foreshadow_id/fact_id/due_by_chapter/strength）与
#        FORESHADOWING_PAID（foreshadow_id）⇒ _SCHEMA_HINT 提示词文本变更。键名 due_by_chapter
#        为冻结会定稿，与 gate.must_reveal_by_chapter 的单源关系由 derive D11 把守。
#        strength 不入 _FIXED_POINT_KEYS：缺省走 reducer 的 event.confidence 回退，
#        不伪造显著度。触碰尺面 ⇒ 读数与 v3.6 分表，不并列。
EXTRACTION_RULER = "v3.8-foreshadow-payload"

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
    "FORESHADOWING_SET": ("foreshadow_id", "fact_id", "due_by_chapter", "strength"),
    "FORESHADOWING_PAID": ("foreshadow_id",),
}
# 提示词不能用 `TYPE:key` 形态 —— 实测模型会把它整段抄成 payload 里的 {"TYPE": "key"}。
# 也不能用裸词 `type`——qwen2.5:14b 实测把「type OBSERVES 的 payload 只放 fact_id」
# 忠实执行成 {"type": "fact_000001"}（W5 冒烟，2026-10-14）。同一失败模式的两个变体。
# 现措辞只留事件名与「应包含」，不出现任何可能被误认为键名的裸词（type / 只放 都危险：
# 后者照样可能被抄成键）。历史教训同款修法，改它 = 尺面变更，见 EXTRACTION_RULER。
_SCHEMA_HINT = "；".join(
    f"事件 {t}：payload 应包含 {','.join(k) if k else '空对象'}"
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
# 枚举键同理：reducer 用 `model_copy` 写 State，**不过 pydantic 校验**，坏值会先静默进 blob，
# 到下一次 `load_latest` 才 ValidationError —— 崩的地方离真正的元凶隔了一整章，更难归因。
# 允许值直接取模型的 Literal，别在这儿抄一份会漂移的副本。
_ENUM_VALUE_KEYS = {"new_narrative_truth": set(
    get_args(Fact.model_fields["narrative_truth"].annotation))}


def _unusable_keys(payload: dict, schema: Tuple[str, ...]) -> List[str]:
    """schema 里「没有可用值」的键：缺失、为 null、定点键不是 int、枚举键不在 Literal 里。"""
    def usable(value, key):
        if value is None:
            return False
        if key in _FIXED_POINT_KEYS:
            return isinstance(value, int) and not isinstance(value, bool)
        if key in _ENUM_VALUE_KEYS:
            return value in _ENUM_VALUE_KEYS[key]
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


def _resolve_actor_field(value, state, alias_index, alias_client,
                         alias_role: str, chapter: int):
    """W3 单字段解析：返回 (resolved_value, 坏料记录或None)。

    - 精确编号 / null → 直通，无记录；
    - 命中注册表姓名/昵称 → 映射到编号，记 `alias_resolved`（不 drop）；
    - id 形态但不在词表（`char_999999` 类幻觉 id）→ 原样返回、无记录，
      交给下游既有 `unknown_id` 路径（保持旧口径与旧测试）；
    - 未知自由文本（"张三"类人名废卷）→ 有 client 则定向追问一次，
      命中则映射记 `alias_resolved_followup`，仍解不出记 `alias_unknown`（drop）；
    - 多义 → 同样追问一次，仍解不出记 `alias_ambiguous`（drop）。
    追问调用异常一律视为未解出（不把接线问题混成内容问题）。
    """
    if value is None:
        return None, None
    resolved, status = _instr.resolve_actor_id(value, state, alias_index)
    if status in ("exact", "null", "null_ok"):
        return resolved, None
    if status == "alias":
        return resolved, {"reason": "alias_resolved", "chapter": chapter,
                          "item": f"{value}->{resolved}"}
    if status == "unknown" and isinstance(value, str) and _ID_RE.match(value):
        return value, None  # 幻觉 id：走既有 unknown_id 路径
    if alias_client is None:
        reason = "alias_ambiguous" if status == "ambiguous" else "alias_unknown"
        return value, {"reason": reason, "chapter": chapter,
                       "item": str(value), "drop": True}
    chars = getattr(state, "characters", {}) or {}
    if status == "ambiguous":
        candidates = list(alias_index.get(str(value), []))
    else:
        candidates = sorted(chars.keys())
    try:
        text, _usage = alias_client.complete(
            alias_role, _instr.alias_followup_prompt(str(value), candidates[:12]))
    except Exception as e:  # noqa: BLE001——追问失败 = 未解出，不抛
        reason = "alias_ambiguous" if status == "ambiguous" else "alias_unknown"
        return value, {"reason": reason, "chapter": chapter,
                       "item": f"{value}（追问失败：{e}）", "drop": True}
    hit = re.search(r"char_\d{6}", text or "")
    if hit and hit.group(0) in (candidates or list(chars.keys())):
        return hit.group(0), {"reason": "alias_resolved_followup", "chapter": chapter,
                              "item": f"{value}->{hit.group(0)}"}
    if (text or "").strip() == "UNKNOWN":
        reason = "alias_ambiguous" if status == "ambiguous" else "alias_unknown"
        return value, {"reason": reason, "chapter": chapter,
                       "item": str(value), "drop": True}
    # 追问回了编号以外的内容：仍解不出，拒收并记因（多义率单独入账见 ambiguous）。
    reason = "alias_ambiguous" if status == "ambiguous" else "alias_unknown"
    return value, {"reason": reason, "chapter": chapter,
                   "item": f"{value}（追问未命中：{(text or '')[:60]}）", "drop": True}


def parse_proposals(raw: str, chapter: int,
                    state: Optional[StoryState] = None,
                    *, resolve_aliases: bool = False,
                    alias_client: Optional[Any] = None,
                    alias_role: str = "extract",
                    code_defaults: bool = False,
                    ) -> Tuple[List[EventProposal], List[dict]]:
    """模型文本 → (合法 Proposal, 坏料记录)。坏料记录原因并留 raw 前 200 字取证（A 批），
    不猜、不补、不提交。

    opt-in 仪器开关（默认全关 = instr-v1 存量行为，保证旧测试与旧读数可比）：
    - ``code_defaults=True``（W4a）：数值定点键缺失/null 由代码补
      ``instr.DEFAULT_FIXED_POINT`` 并记 ``defaulted_fixed_point`` 账；
      字符串/bool/float 等错误类型仍丢弃（不把真坏料洗成假正常）。
    - ``resolve_aliases=True``（W3）：actor/target 先精确匹配编号，命中注册表
      姓名/昵称则映射到编号并记 ``alias_resolved`` 账；未知或多义定向追问一次
      （需 ``alias_client``），仍解不出才拒收并记 ``alias_unknown`` /
      ``alias_ambiguous``。W4b（提示词删"默认 700"句）默认不做。
    """
    array = extract_json_array(raw)
    if array is None:
        return [], [{"reason": "malformed_reply", "raw": raw[:200]}]

    known = _known_ids(state)
    alias_index = _instr.build_alias_index(state) if resolve_aliases else {}
    out: List[EventProposal] = []
    bad: List[dict] = []
    for item in array:
        if not isinstance(item, dict):
            bad.append({"reason": "not_an_object", "item": item, "raw_head": raw[:200]})
            continue
        etype = item.get("event_type") or item.get("proposed_event_type")
        if etype not in _VALID_TYPES:
            bad.append({"reason": "unknown_event_type", "item": etype, "raw_head": raw[:200]})
            continue
        if etype not in PAYLOAD_SCHEMA:
            bad.append({"reason": "type_not_supported", "item": etype, "raw_head": raw[:200]})
            continue
        payload = item.get("payload") or {}
        conf = item.get("confidence", 700)
        if code_defaults and isinstance(payload, dict):
            payload, defaulted = _instr.apply_code_defaults(
                payload, PAYLOAD_SCHEMA[etype], _FIXED_POINT_KEYS)
            for k in defaulted:
                bad.append({"reason": "defaulted_fixed_point",
                            "item": f"{etype}.{k}"})
        if not isinstance(payload, dict) or _has_float(payload) or _has_float(conf):
            bad.append({"reason": "float_in_payload", "item": etype, "raw_head": raw[:200]})
            continue
        actor, target = item.get("actor"), item.get("target")
        if resolve_aliases and state is not None:
            actor, _ab = _resolve_actor_field(
                actor, state, alias_index, alias_client, alias_role, chapter)
            if _ab is not None:
                bad.append(_ab)
                if _ab.get("drop"):
                    continue
            target, _tb = _resolve_actor_field(
                target, state, alias_index, alias_client, alias_role, chapter)
            if _tb is not None:
                bad.append(_tb)
                if _tb.get("drop"):
                    continue
        refs = [actor, target, *payload.values()]
        if known is not None and any(_has_unknown_id(r, known) for r in refs):
            bad.append({"reason": "unknown_id", "item": etype})
            continue
        missing = _unusable_keys(payload, PAYLOAD_SCHEMA[etype])
        if missing:
            bad.append({"reason": "missing_payload_keys",
                        "item": f"{etype} 缺 {','.join(missing)}",
                        # 取证补齐（E26 同型）：只写「缺哪个键」时分不清模型是**没写**还是
                        # **改了名**（实测 {"type": "fact_000001"} 就死于后者，两者在废卷筐里
                        # 长得一模一样）。把模型实际给的键一并落 _junk.json，下次这种模式
                        # 从台账直接可见，不必人肉守 raw。
                        "gave": sorted(payload) if isinstance(payload, dict) else None})
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
            actor=actor, target=target,
            chapter=chapter, seq=seq,
            payload=dict(payload),
            confidence=conf if isinstance(conf, int) else 700,
            source_ref=source_ref,
            extraction_method="llm", extraction_confidence=1000))
    return out, bad


def _vocab(state: StoryState) -> str:
    """角色注册表（含别名，W1/W3：每段提示词携带，供别名映射用）。

    W4b 说明：本函数（生产提示词）不含任何"默认 700"指令——那句话只存在于探针的
    v3.4 草案补丁（见 `EXTRACTION_RULER` 注释），已删除，故此处无需改动。
    数值缺省一律由 W4a 代码后处理补（`code_defaults=True`），此处无尺面触碰。
    """
    parts = []
    for c in state.characters.values():
        label = f"{c.character_id}={c.name}"
        if getattr(c, "aliases", None):
            label += f"（又名{','.join(c.aliases)}）"
        parts.append(label)
    chars = ", ".join(parts)
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
        "类型按「该事实如何进入人物内心」选：OBSERVES=在场亲眼注意到；READS=读到写着的文字；"
        "IS_TOLD=被人当面告知（actor 是**听到告知的人**，知识进他的账；说者不是 actor）；"
        "INFERS=由已知证据推出；BELIEVES=内心确认某事为真；"
        "SUSPECTS=起疑并把嫌疑指向某人/某事；DOUBTS=明确怀疑或否定该事。",
        f"各事件 payload 的键如下: {_SCHEMA_HINT}。",
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


_EVIDENCE_TYPES = {"OBSERVES": "fact_id", "READS": "fact_id"}
# 已经「指向结论」的产物：模型认出这些类型时它 payload 里的 fact 就是被推断/被质疑的那条，
# 只是没给 INFERS。提升规则只从模型自己点名的 id 里取结论，绝不读 Contract 的 required_events
# （07 §4.3：通道独立性），也绝不做文本相似度匹配。
_DERIVED_ID_KEYS = {"FACT_CONTRADICTED": "fact_id", "HINTS": "fact_id", "BELIEVES": "fact_id",
                    "SUSPECTS": "fact_id", "DOUBTS": "fact_id", "LIES": "stated_fact_id",
                    "REVEALS": "fact_id"}
# 结论措辞；命中后还要看它前面有没有否定词——「无法确定 / 不能推断」写的是**没有**结论。
# 两份表都是**标定旋钮**：收窄就少提升，放宽就多提升，读数是它们的函数而不是正文的函数——改它等于改尺。
_CONCLUSION_RE = re.compile(r"确定|断定|得出结论|推断|看来|想必|一定是|只有一个解释|意味着")
_NEGATION_RE = re.compile(r"(?:不|没|未|无法|无从|难以|不能)\s*$")
_NEGATION_RE = re.compile(r"(?:不|没|未|无法|无从|难以|不能)\s*$")


def _states_conclusion(draft: str) -> bool:
    """正文里有没有一句**未被否定**的结论措辞。"""
    return any(not _NEGATION_RE.search(draft[max(0, m.start() - 4):m.start()])
               for m in _CONCLUSION_RE.finditer(draft or ""))


def _promote_infers(props: List[EventProposal], draft: str) -> List[EventProposal]:
    """正文有结论措辞、模型抽到了证据事件却没抽到 INFERS ⇒ 补一条确定性 INFERS。

    结论事实取自**模型自己点名的派生事件**（`_DERIVED_ID_KEYS`），证据事实取自 OBSERVES/READS：
    两头都是模型已经给出的 id，规则只做「类型补全」，不凭空造 id、不看契约答案键。
    上限一章一条（ponytail: 多结论章交给模型自己，补多了就是把尺读成正文读）。
    """
    if not props or any(p.proposed_event_type == "INFERS" for p in props) \
            or not _states_conclusion(draft):
        return []
    evidence: List[str] = []
    evidence_actor: Optional[str] = None
    for p in props:
        key = _EVIDENCE_TYPES.get(p.proposed_event_type)
        fid = p.payload.get(key) if key else None
        if isinstance(fid, str) and fid not in evidence:
            evidence.append(fid)
            evidence_actor = evidence_actor or p.actor
    if not evidence:
        return []
    for p in props:
        key = _DERIVED_ID_KEYS.get(p.proposed_event_type)
        fid = p.payload.get(key) if key else None
        actor = p.actor or evidence_actor
        # INFERS 的账落在 actor 名下（03 §4.3 R2）：没有行为者就没有可提升的推断，别造无主条目
        if isinstance(fid, str) and fid not in evidence and actor:
            return [EventProposal(
                proposed_event_type="INFERS", actor=actor, target=p.target,
                chapter=p.chapter, scene=p.scene, seq=len(props),
                payload={"conclusion_fact_id": fid, "evidence_fact_ids": list(evidence)},
                confidence=p.confidence, source_ref=f"promote:{fid}",
                extraction_method="hybrid", extraction_confidence=1000)]
    return []


def make_llm_channel(client: LlmClient, *, max_items: int = 24,                     extract_role: str = "extract"):
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
        promoted = _promote_infers(props, _strip_markup(draft))
        # 坏料记章号：只按 reason 聚总的话，dump 里说不清哪章丢了什么（§3.5 取证缺口）
        ch = getattr(contract, "chapter_no", 0)
        channel.malformed.extend([{**b, "chapter": ch} for b in bad])
        channel.produced += len(props) + len(promoted)
        channel.promoted += len(promoted)
        return props + promoted

    channel.total_tokens = 0
    channel.produced = 0
    channel.promoted = 0
    channel.malformed: List[dict] = []
    return channel


def extract_with_repair(raw: str, chapter: int, state,
                        client: Optional[LlmClient] = None,
                        extract_role: str = "extract",
                        *, enable_repair: bool = True,
                        **parse_kwargs) -> Tuple[List[EventProposal], List[dict], dict]:
    """W2：解析失败 → 回喂重试 1 次 → 仍失败返回坏料（由调用方做段级降级）。

    返回 (props, bad, info)，info 含 repaired: bool 与 error: str。
    不发网络时（client=None 或 enable_repair=False）行为与 `parse_proposals` 一致。
    约束解码（runtime 支持的话）为可选第三步：client 若带 `constrained_decode`
    属性则调用之，否则跳过——此处只留钩子，不硬依赖。
    """
    props, bad = parse_proposals(raw, chapter, state, **parse_kwargs)
    info: Dict[str, object] = {"repaired": False, "error": ""}
    if bad and len(props) == 0 and bad[0].get("reason") == "malformed_reply" \
            and enable_repair and client is not None:
        info["error"] = "malformed_reply"
        try:
            fixed, usage = client.complete(
                extract_role, _instr.repair_prompt(raw, "malformed_reply"))
            client.total_tokens += usage.total
        except Exception as e:  # noqa: BLE001——修不动 = 优雅降级，不抛
            bad.append({"reason": "repair_call_failed", "chapter": chapter,
                        "item": str(e)[:120]})
            return [], bad, info
        # 约束解码钩子：transport 支持时再收一次（当前 urllib transport 不支持，保持跳过）
        decoder = getattr(client, "constrained_decode", None)
        if decoder is not None and extract_json_array(fixed) is None:
            try:
                fixed = decoder(fixed) or fixed
            except Exception:
                pass
        props2, bad2 = parse_proposals(fixed, chapter, state, **parse_kwargs)
        if props2 or not (bad2 and bad2[0].get("reason") == "malformed_reply"):
            info["repaired"] = True
            return props2, bad2, info
        bad = bad2
    return props, bad, info


def make_segmented_llm_channel(client: LlmClient, *,
                               max_items: int = 24,
                               extract_role: str = "extract",
                               flags: Optional["_instr.InstrFlags"] = None,
                               lane: str = "local",
                               seg_max_chars: int = _instr.SEGMENT_MAX_CHARS,
                               seg_overlap: int = _instr.SEGMENT_OVERLAP_CHARS,
                               ):
    """W1+W2+W3+W4a instr-v2 通道：与 `make_llm_channel` 同签名，可直接替换注入。

    - W1：分段抽取 + 确定性合并去重（(event_type, actor, fact_id)），全局重编 seq；
      段内 paragraph 号重映射回全局段号（`para:N#seg:i`），跨段对齐不断；
      在原先能完整跑完的章上合并后条目数不得少于单跑基线 95%（验收见 W5 报告）。
    - W2：段解析失败 → 修复环 1 次 → 仍失败**只废该段**（记 `segment_failed`
      并标注缺失 char_span），章级 `malformed_reply` 恒为 0；
      `finish=length` 按段记录（`truncated_segment`），分段后应回归 0。
    - W3/W4a：透传 `parse_proposals(resolve_aliases, code_defaults)`，开关见 flags。
    - W6：`lane` 只决定仪器戳（`instr-v2-local/cloud`）与台账标注，管道代码同套。
    全部开关经 `flags` 独立回滚：`flags.segmentation=False` 即退回单跑行为。
    """
    flags = flags or _instr.InstrFlags()
    flags.lane = lane
    instr_version = _instr.instr_id_for_lane(lane)

    def channel(draft, scene_plan, contract, state) -> List[EventProposal]:
        ch = getattr(contract, "chapter_no", 0)
        stripped = _strip_markup(draft)
        segments = (_instr.split_draft_segments(stripped, max_chars=seg_max_chars,
                                                overlap_chars=seg_overlap)
                    if flags.segmentation else [])
        parse_kwargs = dict(resolve_aliases=flags.alias_resolution,
                            alias_client=client, alias_role=extract_role,
                            code_defaults=flags.code_defaults)
        if not segments:
            # 空正文（无段）或开关关闭：退回单跑，但保留 W2/W3/W4a 仪器行为。
            text, usage = client.complete(
                extract_role, extract_prompt(stripped, scene_plan, contract, state))
            channel.total_tokens += usage.total
            if client.calls and client.calls[-1].finish == "length":
                channel.malformed.append({"reason": "truncated_segment", "chapter": ch,
                                          "seg": 0, "instr": instr_version})
            props, bad, info = extract_with_repair(
                text, ch, state, client, extract_role,
                enable_repair=flags.repair_loop, **parse_kwargs)
            if info.get("repaired"):
                channel.repaired += 1
            if len(props) > max_items:
                bad.append({"reason": "over_cap", "item": len(props)})
                props = props[:max_items]
            promoted = _promote_infers(props, stripped)
            channel.malformed.extend([{**b, "chapter": ch, "instr": instr_version}
                                      for b in bad])
            channel.produced += len(props) + len(promoted)
            channel.promoted += len(promoted)
            channel.segments_run += 1
            return props + promoted

        per_seg: List[List[EventProposal]] = []
        for seg in segments:
            text, usage = client.complete(
                extract_role, extract_prompt(seg.text, scene_plan, contract, state))
            channel.total_tokens += usage.total
            if client.calls and client.calls[-1].finish == "length":
                channel.malformed.append({"reason": "truncated_segment", "chapter": ch,
                                          "seg": seg.index, "instr": instr_version})
            props, bad, info = extract_with_repair(
                text, ch, state, client, extract_role,
                enable_repair=flags.repair_loop, **parse_kwargs)
            if info.get("repaired"):
                channel.repaired += 1
            # 段内 paragraph 号 → 全局段号重映射（跨段对齐不断）
            remapped = []
            for p in props:
                m = re.fullmatch(r"para:(\d+)", p.source_ref or "")
                if m:
                    g = seg.para_start + int(m.group(1)) - 1
                    remapped.append(p.model_copy(
                        update={"source_ref": f"para:{g}#seg:{seg.index}"}))
                else:
                    remapped.append(p)
            if not remapped and any(b.get("reason") in ("malformed_reply", "repair_call_failed")
                                    for b in bad):
                # W2 段级优雅降级：只废该段，标注缺失窗口。
                # 段内 malformed_reply 是**段级**细节，改记 segment_unparsable：
                # 章级 malformed_reply 在分段路径恒为 0（任务单 W2 验收口径），
                # 否则 readout 会把一次段废读成整章废。
                channel.malformed.append({"reason": "segment_failed", "chapter": ch,
                                          "seg": seg.index, "char_span": list(seg.char_span),
                                          "instr": instr_version})
                channel.missing_windows.append({"chapter": ch, "seg": seg.index,
                                                "char_span": list(seg.char_span)})
                for b in bad:
                    entry = dict(b)
                    if entry.get("reason") == "malformed_reply":
                        entry["reason"] = "segment_unparsable"
                    channel.malformed.append({**entry, "chapter": ch, "seg": seg.index,
                                              "instr": instr_version})
                per_seg.append([])
                continue
            for b in bad:
                entry = dict(b)
                if entry.get("reason") == "malformed_reply":
                    entry["reason"] = "segment_unparsable"
                channel.malformed.append({**entry, "chapter": ch, "seg": seg.index,
                                          "instr": instr_version})
            per_seg.append(remapped)
        merged, stats = _instr.dedup_proposals([p for seg in per_seg for p in seg])
        if not merged:
            # 章级废卷：分段路径也只剩「整章无可用条目」这一种读法
            channel.malformed.append({"reason": "chapter_empty", "chapter": ch,
                                      "n_segments": len(segments),
                                      "instr": instr_version})
        merged = [p.model_copy(update={"seq": i, "chapter": ch})
                  for i, p in enumerate(merged)]
        channel.deduped += stats["before"] - stats["after"]
        if len(merged) > max_items:
            channel.malformed.append({"reason": "over_cap", "chapter": ch,
                                      "item": len(merged), "instr": instr_version})
            merged = merged[:max_items]
            merged = [p.model_copy(update={"seq": i}) for i, p in enumerate(merged)]
        promoted = _promote_infers(merged, stripped)
        channel.produced += len(merged) + len(promoted)
        channel.promoted += len(promoted)
        channel.segments_run += len(segments)
        return merged + promoted

    channel.total_tokens = 0
    channel.produced = 0
    channel.promoted = 0
    channel.malformed: List[dict] = []
    channel.repaired = 0
    channel.deduped = 0
    channel.segments_run = 0
    channel.missing_windows: List[dict] = []
    channel.instr_version = instr_version
    channel.lane = lane
    channel.lane_identity = _instr.lane_identity_report(client, lane)
    return channel


def make_laned_channel(local_client: LlmClient, cloud_client: Optional[LlmClient] = None,
                       *, lane: str = "local", **kwargs):
    """W6 模型路由层：两条车道共用同一套分段/修复/别名/默认值管道（`make_segmented_llm_channel`）。

    - `lane="local"` → 本地 14B 车道（默认，保 COGS）；`lane="cloud"` → 云端车道；
    - 缺 cloud_client 时请求云端车道直接抛 `ValueError`（不静默回落，归因要干净）；
    - `channel.instr_version` / 台账标注随车道升档（护栏 3：换车道 = 仪器版本变更）。
    """
    if lane == "cloud":
        if cloud_client is None:
            raise ValueError("lane=cloud 但未提供 cloud_client（不静默回落）")
        return make_segmented_llm_channel(cloud_client, lane="cloud", **kwargs)
    return make_segmented_llm_channel(local_client, lane="local", **kwargs)
