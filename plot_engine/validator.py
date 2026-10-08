"""Validator（05_validation_protocol.md）：Commit 前的确定性闸门。

Stage 1 沙盒：整批 Proposal 通过纯 Reducer 施加到 StoryState 的临时拷贝，
规则比对 pre / mid / post 快照与 Draft markup；绝不落盘、绝不改真实状态（05 §2 V4, §9 I3）。
Level 3（LLM-as-validator）只产 SOFT/OBSERVATION，本 Phase 0 不接入。
一切数值为定点整数 ×1000（05 §5.5）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from typing import Literal, get_args

from pydantic import BaseModel, Field, ValidationError

from plot_engine.models.event import Event, EventType
from plot_engine.models.proposal import EventProposal, proposal_event_id, to_event
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer

_VALID_EVENT_TYPES = frozenset(get_args(EventType))


class Finding(BaseModel):
    """单条判定结论（05 §3 verbatim）。"""
    rule_id: str
    severity: Literal["hard", "soft", "observation"]
    message: str
    location: Optional[str] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    """三层判定结果容器（05 §3）。HARD 非空即拒绝 Commit（V1）。"""
    hard_violations: List[Finding] = Field(default_factory=list)
    soft_warnings: List[Finding] = Field(default_factory=list)
    observations: List[Finding] = Field(default_factory=list)

    def can_commit(self) -> bool:
        return len(self.hard_violations) == 0


@dataclass
class Simulation:
    """Stage 2 在整批 Proposal 上的沙盒投影（真实 state 永不被改）。"""
    pre: StoryState
    cur: StoryState
    applied: List[Event] = field(default_factory=list)
    failed: List[Tuple[EventProposal, str]] = field(default_factory=list)
    steps: List[Tuple[Event, StoryState]] = field(default_factory=list)  # (event, state_before)


def _simulate(state: StoryState, proposals: List[EventProposal], epoch: str) -> Simulation:
    """按 (chapter, seq) 拓扑序施加；冲突 id 与 reducer 异常隔离到 failed，绝不抛出（05 §9 I6）。"""
    sim = Simulation(pre=state, cur=state)
    reducer = Reducer()
    seen_ids: set = set()
    for p in sorted(proposals, key=lambda x: (x.chapter, x.seq)):
        eid = proposal_event_id(p)
        if eid in seen_ids:
            sim.failed.append((p, f"duplicate_id:{eid}"))
            continue
        seen_ids.add(eid)
        try:
            ev = to_event(p, epoch)
            before = sim.cur
            sim.cur = reducer.apply(ev, before)
        except (KeyError, ValueError, ValidationError) as exc:
            sim.failed.append((p, f"reducer_error:{type(exc).__name__}"))
            continue
        sim.steps.append((ev, before))
        sim.applied.append(ev)
    return sim


# --- event id 解析 ---
_EVT_ID_RE = re.compile(r"^evt_(\d{8})_(\d{3})$")


def _parse_chapter(event_id: str) -> Optional[int]:
    m = _EVT_ID_RE.match(event_id)
    return int(m.group(1)) if m else None


def _parse_seq(event_id: str) -> Optional[int]:
    m = _EVT_ID_RE.match(event_id)
    return int(m.group(2)) if m else None


def _f(rule_id: str, severity: str, message: str, **kw) -> Finding:
    return Finding(rule_id=rule_id, severity=severity, message=message, **kw)


def _event_location(ev: Event) -> Optional[str]:
    return ev.payload.get("location")


# --- H1 系列 ---
def _l1_h1(sim: Simulation, state: StoryState) -> List[Finding]:
    findings: List[Finding] = []
    # H1.1 dead/unborn 作为 actor（含同批 CHANGES→dead 之后仍出场）
    for ev, before in sim.steps:
        c = before.characters.get(ev.actor or "")
        if c is not None and c.status in ("dead", "unborn"):
            findings.append(_f("H1.1", "hard",
                               f"{c.status} 角色 {c.character_id} 作为事件 {ev.event_id} 的 actor",
                               evidence=ev.event_id))
    # H1.2 / H4.1 超额消耗（pre 库存 + 整批重算）
    held: Dict[Tuple[str, str], int] = {}
    for e in state.inventory:
        held[(e.character_id, e.item_id)] = held.get((e.character_id, e.item_id), 0) + e.quantity
    flagged: set = set()
    for ev, _before in sim.steps:
        if ev.event_type == "ITEM_ACQUIRED":
            key = (ev.payload["character_id"], ev.payload["item_id"])
            held[key] = held.get(key, 0) + int(ev.payload["quantity"])
        elif ev.event_type == "ITEM_CONSUMED":
            key = (ev.payload["character_id"], ev.payload["item_id"])
            held[key] = held.get(key, 0) - int(ev.payload["quantity"])
            if held[key] < 0 and key not in flagged:
                flagged.add(key)
                msg = f"{key[0]} 对 {key[1]} 消耗超过持有（{ev.event_id}）"
                findings.append(_f("H1.2", "hard", msg, evidence=ev.event_id))
                findings.append(_f("H4.1", "hard", msg, evidence=ev.event_id))
    # H1.3 地点矛盾（running before 已含同批 location 变更 → 无需再判 CHANGES）
    for ev, before in sim.steps:
        loc = _event_location(ev)
        c = before.characters.get(ev.actor or "")
        if not loc or c is None or c.status == "missing":
            continue
        if c.current_location and c.current_location != loc:
            findings.append(_f("H1.3", "hard",
                               f"{c.character_id} 位于 {c.current_location}，事件 {ev.event_id} 却在 {loc}",
                               evidence=ev.event_id))
    return findings


def _l1_ability(sim: Simulation, state: StoryState) -> List[Finding]:
    """H1.4 境界矛盾 / H2.4 未学技能（payload.ability_id 约定）。"""
    findings: List[Finding] = []
    for ev, before in sim.steps:
        abil_id = ev.payload.get("ability_id")
        if not abil_id:
            continue
        c = before.characters.get(ev.actor or "")
        if c is None:
            continue
        if abil_id not in c.abilities:
            findings.append(_f("H2.4", "hard",
                               f"{c.character_id} 使用从未习得的能力 {abil_id}（{ev.event_id}）",
                               evidence=ev.event_id))
            continue
        ab = state.abilities.get(abil_id)
        if ab is None or ab.required_realm is None:
            continue
        req = state.realms.get(ab.required_realm)
        act = state.realms.get(c.realm) if c.realm else None
        if req is not None and (act is None or req.tier > act.tier):
            findings.append(_f("H1.4", "hard",
                               f"{c.character_id} 境界不足却使用 {abil_id}（需 {ab.required_realm}）",
                               evidence=ev.event_id))
    return findings


def _l1_h3(sim: Simulation, state: StoryState, proposals: List[EventProposal],
           contract, committed_event_ids) -> List[Finding]:
    findings: List[Finding] = []
    batch_ids = {ev.event_id for ev in sim.applied}
    batch_seq: Dict[str, int] = {ev.event_id: ev.seq for ev in sim.applied}
    batch_chapter: Dict[str, int] = {ev.event_id: ev.chapter for ev in sim.applied}

    # H3.3 时间倒流：proposal.chapter < state.chapter_no
    for p in proposals:
        if p.chapter < state.chapter_no:
            findings.append(_f("H3.3", "hard",
                               f"Proposal {proposal_event_id(p)} 章节 {p.chapter} 早于当前 {state.chapter_no}"))

    contract_ch = getattr(contract, "chapter_no", None) if contract else None
    for ev in sim.applied:
        for pre in ev.preconditions:
            pre_ch = _parse_chapter(pre)
            # H3.2 未来章节引用
            if contract_ch is not None and pre_ch is not None and pre_ch > contract_ch:
                findings.append(_f("H3.2", "hard",
                                   f"{ev.event_id} 前置 {pre} 属未来章节（> {contract_ch}）",
                                   evidence=ev.event_id))
            # H3.1 同批内前置顺序矛盾（前置 seq >= 自身 seq，同章）
            if pre in batch_ids and batch_chapter.get(pre) == ev.chapter:
                if batch_seq[pre] >= ev.seq:
                    findings.append(_f("H3.1", "hard",
                                       f"{ev.event_id} 前置 {pre} 在同批中顺序不早于自身",
                                       evidence=ev.event_id))
    return findings


def _l1_h3_4(sim: Simulation, state: StoryState) -> List[Finding]:
    """H3.4 同角色同时出现在两个不同地点（无中间 location 变更）。"""
    findings: List[Finding] = []
    asserted: Dict[str, str] = {}
    for ev, _before in sim.steps:
        actor = ev.actor or ""
        if ev.event_type == "CHANGES" and ev.payload.get("field") == "location":
            new_loc = ev.payload.get("new_value")
            if new_loc:
                asserted[actor] = new_loc
            continue
        loc = _event_location(ev)
        if loc and actor:
            if actor in asserted and asserted[actor] != loc:
                findings.append(_f("H3.4", "hard",
                                   f"{actor} 同时出现在 {asserted[actor]} 与 {loc}（{ev.event_id}）",
                                   evidence=ev.event_id))
            asserted[actor] = loc
    return findings


def _condition_met(cond: str, actor: Optional[str], state_before: StoryState) -> bool:
    kind, _, ref = cond.partition(":")
    if kind == "fact":
        return any(k.character_id == actor and k.fact_id == ref
                   and k.knowledge_state in ("known", "confirmed")
                   for k in state_before.knowledge_ledger)
    if kind == "realm":
        c = state_before.characters.get(actor or "")
        req = state_before.realms.get(ref)
        act = state_before.realms.get(c.realm) if (c and c.realm) else None
        return bool(req and act and act.tier >= req.tier)
    if kind == "item":
        return any(e.character_id == actor and e.item_id == ref and e.quantity > 0
                   for e in state_before.inventory)
    return True  # 未知语法 Phase 0 视为已满足


def _l1_h4(sim: Simulation, state: StoryState) -> List[Finding]:
    findings: List[Finding] = []
    # H4.2 库存数量为负（模型 ge=0，哨兵）
    for e in sim.cur.inventory:
        if e.quantity < 0:
            findings.append(_f("H4.2", "hard",
                               f"库存 {e.inventory_id} 数量为负（{e.quantity}）", evidence=e.inventory_id))
    # H4.3 未解锁区域进入
    for ev, before in sim.steps:
        loc_id = _event_location(ev)
        if not loc_id:
            continue
        loc = before.locations.get(loc_id)
        if loc is None:
            continue
        if not loc.unlocked:
            findings.append(_f("H4.3", "hard",
                               f"进入未解锁地点 {loc_id}（{ev.event_id}）", evidence=ev.event_id))
            continue
        unmet = [c for c in loc.unlock_conditions
                 if not _condition_met(c, ev.actor, before)]
        if unmet:
            findings.append(_f("H4.3", "hard",
                               f"进入 {loc_id} 解锁条件未满足 {unmet}（{ev.event_id}）",
                               evidence=ev.event_id))
    return findings


def _l1_h6(sim: Simulation, state: StoryState, proposals: List[EventProposal],
           committed_event_ids) -> List[Finding]:
    findings: List[Finding] = []
    batch_ids = {ev.event_id for ev in sim.applied}
    known_ids = batch_ids | set(committed_event_ids)

    # H6.1 event_type 不在 Taxonomy
    for p in proposals:
        if p.proposed_event_type not in _VALID_EVENT_TYPES:
            findings.append(_f("H6.1", "hard",
                               f"event_type {p.proposed_event_type!r} 不在 Taxonomy（{proposal_event_id(p)}）",
                               evidence=proposal_event_id(p)))

    for ev in sim.applied:
        for pre in ev.preconditions:
            pre_ch = _parse_chapter(pre)
            if pre in known_ids:
                continue
            # H6.5 前置指向未来事件（章节 > 自身）
            if pre_ch is not None and pre_ch > ev.chapter:
                findings.append(_f("H6.5", "hard",
                                   f"{ev.event_id} 前置 {pre} 指向未来事件",
                                   evidence=ev.event_id))
            else:
                # H6.2 前置指向不存在事件
                findings.append(_f("H6.2", "hard",
                                   f"{ev.event_id} 前置 {pre} 不存在（未提交且非本批）",
                                   evidence=ev.event_id))

    # H6.4 重复 event_id（首个保留，后续隔离到 failed）
    for p, reason in sim.failed:
        if reason.startswith("duplicate_id"):
            eid = reason.split(":", 1)[1]
            findings.append(_f("H6.4", "hard",
                               f"event_id 重复 {eid}（chapter={p.chapter} seq={p.seq}）",
                               evidence=eid))

    # H6.3 环检测（Phase 0 SOFT，01 §5.2 R1'）
    if _has_cycle(sim.applied):
        findings.append(_f("H6.3", "soft", "事件因果图存在环",
                           suggestion="Phase 1 升 HARD"))

    # MALFORMED_PROPOSAL：reducer 异常（05 §9 I6 不静默丢弃）
    for p, reason in sim.failed:
        if reason.startswith("reducer_error"):
            findings.append(_f("MALFORMED_PROPOSAL", "hard",
                               f"Proposal 无法施加：{reason}（{proposal_event_id(p)}）",
                               evidence=proposal_event_id(p)))
    return findings


def _has_cycle(events: List[Event]) -> bool:
    """批内 preconditions 边 prec→event 的环检测。"""
    ids = {ev.event_id for ev in events}
    edges: Dict[str, List[str]] = {ev.event_id: [p for p in ev.preconditions if p in ids]
                                   for ev in events}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {i: WHITE for i in ids}

    def dfs(n: str) -> bool:
        color[n] = GRAY
        for nxt in edges.get(n, []):
            if color[nxt] == GRAY:
                return True
            if color[nxt] == WHITE and dfs(nxt):
                return True
        color[n] = BLACK
        return False

    return any(color[i] == WHITE and dfs(i) for i in ids)


def _run_l1(sim: Simulation, state: StoryState, proposals: List[EventProposal],
            *, contract=None, committed_event_ids=frozenset()) -> List[Finding]:
    """Level 1 全量确定性检查（H1/H3/H4/H6）。只读，不改 state。"""
    findings: List[Finding] = []
    findings += _l1_h1(sim, state)
    findings += _l1_ability(sim, state)
    findings += _l1_h3(sim, state, proposals, contract, committed_event_ids)
    findings += _l1_h3_4(sim, state)
    findings += _l1_h4(sim, state)
    findings += _l1_h6(sim, state, proposals, committed_event_ids)
    return findings


# --- Level 2：结构化检查（H2 / H5 + markup M-rules），05 §7 Level 2 ---
_K_RANK: Dict[str, int] = {"unknown": 0, "suspected": 1, "believed": 2,
                           "known": 3, "confirmed": 4}
_READING_KINDS = {"READER_LEARNS": "learns", "READER_HINTED": "hinted",
                  "READER_DECEIVED": "deceived"}
_SIGNAL_TO_READER = {"knows": "READER_LEARNS", "hinted": "READER_HINTED",
                     "deceived": "READER_DECEIVED"}
_KNOWLEDGE_ESTABLISH = {"OBSERVES", "READS", "IS_TOLD", "INFERS", "BELIEVES", "SUSPECTS"}
_SIMPLE_FIELDS: Dict[str, str] = {"location": "current_location", "realm": "realm",
                                  "status": "status", "faction": "faction_id",
                                  "attributes": "attributes", "abilities": "abilities"}


def _referenced_fact(ev: Event) -> Optional[str]:
    return (ev.payload.get("fact_id") or ev.payload.get("conclusion_fact_id")
            or ev.payload.get("stated_fact_id") or ev.target)


def _kentry(ledger, char_id: str, fact_id: str):
    return next((e for e in ledger
                 if e.character_id == char_id and e.fact_id == fact_id), None)


def _knowledge_meets(cur, char_id: str, fact_id: str, expected) -> bool:
    e = _kentry(cur.knowledge_ledger, char_id, fact_id)
    if e is None:
        return False
    if expected is None:
        return True
    return _K_RANK.get(e.knowledge_state, 0) >= _K_RANK.get(str(expected), 0)


def _reader_key(p: EventProposal) -> Optional[Tuple[str, str]]:
    if p.proposed_event_type in _READING_KINDS:
        fact = p.payload.get("fact_id") or p.target
        return (_READING_KINDS[p.proposed_event_type], fact)
    return None


def _l2_h2(sim: Simulation, state: StoryState, proposals: List[EventProposal],
           contract, markup) -> List[Finding]:
    findings: List[Finding] = []
    forbidden = set(getattr(contract, "knowledge_forbidden", []))

    # H2.1 角色在 pre-state 已知 forbidden fact
    for e in sim.pre.knowledge_ledger:
        if e.fact_id in forbidden and e.knowledge_state in ("known", "confirmed"):
            findings.append(_f("H2.1", "hard",
                               f"{e.character_id} 掌握禁止知识 {e.fact_id}", evidence=e.fact_id))

    # H2.2 must_change(field=knowledge) 未在 post-state 实现
    for ch in getattr(contract, "must_change", []):
        if ch.field == "knowledge" and ch.operation in ("add", "update"):
            if not _knowledge_meets(sim.cur, ch.character_id, ch.target, ch.expected_value):
                findings.append(_f("H2.2", "hard",
                                   f"{ch.character_id} 未取得知识 {ch.target}（期望 {ch.expected_value}）",
                                   evidence=ch.target))

    # H2.3 markup↔proposal 配对（M2 HARD / M3 SOFT）
    anno_keys = {(a.kind, a.fact_id) for a in markup.readers if a.fact_id}
    proposal_keys = {k for k in (_reader_key(p) for p in proposals) if k}
    for key in sorted(anno_keys - proposal_keys):
        findings.append(_f("H2.3", "hard",
                           f"reader 标注 {key[0]}:{key[1]} 无对应 READER_* Proposal（M2）",
                           evidence=f"{key[0]}:{key[1]}"))
    for p in proposals:
        if p.extraction_method == "markup":
            continue
        key = _reader_key(p)
        if key and key[1] is not None and key not in anno_keys:
            findings.append(_f("H2.3", "soft",
                               f"READER_* Proposal {key[0]}:{key[1]} 缺 Draft 标注（M3）",
                               evidence=f"{key[0]}:{key[1]}"))
    return findings


def _l2_h5(sim: Simulation, state: StoryState, proposals: List[EventProposal],
           contract, markup) -> List[Finding]:
    findings: List[Finding] = []
    applied_types = [ev.event_type for ev in sim.applied]
    forbidden = set(getattr(contract, "knowledge_forbidden", []))
    allowed = set(getattr(contract, "knowledge_allowed", []))

    # H5.1 required_event 未达标
    for req in getattr(contract, "required_events", []):
        if applied_types.count(req.event_type) < req.minimum_count:
            findings.append(_f("H5.1", "hard",
                               f"必需事件 {req.event_type} 数量不足（{applied_types.count(req.event_type)}<{req.minimum_count}）",
                               evidence=req.event_type))

    # H5.2 forbidden_event 出现
    for fb in getattr(contract, "forbidden_events", []):
        if fb.event_type in applied_types:
            findings.append(_f("H5.2", "hard",
                               f"禁用事件 {fb.event_type} 出现", evidence=fb.event_type))

    # H5.3 must_change 无对应实现事件（W1）
    for ch in getattr(contract, "must_change", []):
        if not _change_implemented(sim, ch):
            findings.append(_f("H5.3", "hard",
                               f"must_change {ch.character_id}.{ch.field} 无实现事件（W1）",
                               evidence=ch.field))

    # H5.4 must_not_change 被违反（W2）
    for ch in getattr(contract, "must_not_change", []):
        if _must_not_changed(sim, ch):
            findings.append(_f("H5.4", "hard",
                               f"must_not_change {ch.character_id}.{ch.field} 被修改（W2）",
                               evidence=ch.field))

    # H5.5 hook 标注（W7 / M1 / M5）
    if not _hook_ok(markup, contract):
        findings.append(_f("H5.5", "hard",
                           f"章尾 hook 标注不合规（期望 ending.type={contract.ending.type}）",
                           evidence="hook"))

    # H5.6 knowledge_allowed 中 must_change 目标未建立（W6）
    for ch in getattr(contract, "must_change", []):
        if (ch.field == "knowledge" and ch.target in allowed
                and not _knowledge_meets(sim.cur, ch.character_id, ch.target, ch.expected_value)):
            findings.append(_f("H5.6", "hard",
                               f"允许知识 {ch.target} 未建立（W6）", evidence=ch.target))

    # H5.7 整批建立了 forbidden fact（W5）
    for ev in sim.applied:
        if ev.event_type in _KNOWLEDGE_ESTABLISH:
            fact = _referenced_fact(ev)
            if fact in forbidden:
                findings.append(_f("H5.7", "hard",
                                   f"整批建立禁止知识 {fact}（{ev.event_id}，W5）", evidence=fact))

    # W8 reader_signal 未命中 → SOFT SIGNAL_UNHIT
    proposal_keys = {k for k in (_reader_key(p) for p in proposals) if k}
    for sig in getattr(contract, "reader_signals", []):
        want = _SIGNAL_TO_READER.get(sig.target_state)
        if want is None:
            continue
        key = (_READING_KINDS[want], sig.fact_id)
        if key not in proposal_keys:
            findings.append(_f("SIGNAL_UNHIT", "soft",
                               f"reader_signal {sig.fact_id}→{sig.target_state} 未命中（W8）",
                               evidence=sig.fact_id))
    return findings


def _change_implemented(sim: Simulation, ch) -> bool:
    if ch.field in ("knowledge", "belief"):
        return any(ev.event_type in _KNOWLEDGE_ESTABLISH
                   and (_referenced_fact(ev) == ch.target)
                   and (ev.actor == ch.character_id)
                   for ev in sim.applied)
    if ch.field in _SIMPLE_FIELDS:
        return any(ev.event_type == "CHANGES" and ev.payload.get("field") == ch.field
                   and ev.actor == ch.character_id for ev in sim.applied)
    if ch.field == "relationship":
        return any(ev.event_type == "RELATIONSHIP_CHANGED" for ev in sim.applied)
    if ch.field == "inventory":
        return any(ev.event_type in ("ITEM_ACQUIRED", "ITEM_CONSUMED") for ev in sim.applied)
    return True


def _must_not_changed(sim: Simulation, ch) -> bool:
    pre_c = sim.pre.characters.get(ch.character_id)
    cur_c = sim.cur.characters.get(ch.character_id)
    if ch.field in _SIMPLE_FIELDS:
        attr = _SIMPLE_FIELDS[ch.field]
        pv = getattr(pre_c, attr, None) if pre_c else None
        cv = getattr(cur_c, attr, None) if cur_c else None
        return pv != cv
    if ch.field == "knowledge":
        pre_f = {e.fact_id for e in sim.pre.knowledge_ledger if e.character_id == ch.character_id}
        cur_f = {e.fact_id for e in sim.cur.knowledge_ledger if e.character_id == ch.character_id}
        return pre_f != cur_f
    return False


def _hook_ok(markup, contract) -> bool:
    hooks = markup.hooks
    if len(hooks) != 1:
        return False
    hk = hooks[0]
    in_last3 = hk.para_index >= markup.para_count - 3
    strength_ok = hk.strength is not None and 0 <= hk.strength <= 1000
    kind_ok = hk.kind == contract.ending.type
    return in_last3 and strength_ok and kind_ok


def _run_l2(sim: Simulation, state: StoryState, proposals: List[EventProposal],
            *, contract, markup) -> List[Finding]:
    findings: List[Finding] = []
    findings += _l2_h2(sim, state, proposals, contract, markup)
    findings += _l2_h5(sim, state, proposals, contract, markup)
    return findings


# --- Contract 自校验：H7 族（04 §5.1 V1–V10 + §4.4 兼容矩阵）---
_COMPAT_MATRIX: Dict[str, set] = {
    "revelation": {"revelation", "cliffhanger"},
    "escalation": {"cliffhanger", "decision"},
    "setup": {"question", "arrival"},
    "resolution": {"none", "decision"},
    "transition": {"arrival", "decision"},
    "confrontation": {"cliffhanger", "decision"},
    "reflection": {"question", "none"},
}
_DERIVED_RE = re.compile(r"^arc_\d{3}\.(knowledge_gates|turning_points)\[([^\]]+)\]$")


def _ref_pool(ref: str, state: StoryState):
    prefix = ref.split("_", 1)[0] if "_" in ref else ""
    pool = {"fact": state.facts, "char": state.characters, "loc": state.locations,
            "item": state.items, "realm": state.realms, "fac": state.factions,
            "abil": state.abilities}.get(prefix)
    return pool  # None → 非实体引用（scn/evt/arc），不检


def _contract_referenced_ids(contract) -> List[str]:
    ids: List[str] = list(contract.knowledge_allowed) + list(contract.knowledge_forbidden)
    ids += [s.fact_id for s in contract.reader_signals]
    for ch in list(contract.must_change) + list(contract.must_not_change):
        ids += [ch.character_id, ch.target]
    for req in contract.required_events:
        ids += list(req.actors_involved)
    return [i for i in ids if isinstance(i, str) and i]


def _run_contract(contract, arc, state: StoryState) -> List[Finding]:
    """Contract 生成后自校验（04 §5.1）；返回未分桶的 Finding 列表。只读。"""
    findings: List[Finding] = []

    # H7.1 (V1)：schema_version 与 epoch 一致 + 必填非空退化
    if contract.schema_version != 2:
        findings.append(_f("H7.1", "hard", f"schema_version={contract.schema_version} 应为 2"))
    if not contract.story_goal.strip():
        findings.append(_f("H7.1", "hard", "story_goal 为空"))

    # H7.2 (V2)：chapter_no 命中 arc_range 且 arc_id 匹配
    start, end = arc.chapter_range
    if not (start <= contract.chapter_no <= end):
        findings.append(_f("H7.2", "hard",
                           f"chapter_no {contract.chapter_no} 不在 arc 范围 ({start},{end})"))
    if contract.arc_id != arc.arc_id:
        findings.append(_f("H7.2", "hard",
                           f"contract.arc_id {contract.arc_id} != arc.arc_id {arc.arc_id}"))

    # H7.3 (V3)：张力偏差 > 300 落 SOFT（v0.2 降档；05 单源阈值 300，04 D2' 记 200，取 300）
    idx = contract.chapter_no - start
    if 0 <= idx < len(arc.tension_curve):
        if abs(contract.tension_target - arc.tension_curve[idx]) > 300:
            findings.append(_f("H7.3", "soft",
                               f"tension_target {contract.tension_target} 与曲线 {arc.tension_curve[idx]} 偏差 > 300"))

    # H7.4 (V4 / I7)：allowed ∩ forbidden 非空
    overlap = set(contract.knowledge_allowed) & set(contract.knowledge_forbidden)
    for fact in sorted(overlap):
        findings.append(_f("H7.4", "hard", f"fact {fact} 同时在 allowed 与 forbidden"))

    # H7.5 (V5)：required 与 forbidden 同 event_type 冲突
    req_types = {r.event_type for r in contract.required_events}
    for fb in contract.forbidden_events:
        if fb.event_type in req_types:
            findings.append(_f("H7.5", "hard", f"event_type {fb.event_type} 同时 required 与 forbidden"))

    # H7.6 (V6)：must_change 与 must_not_change 同 (character_id, field, target) 冲突
    change_keys = {(c.character_id, c.field, c.target) for c in contract.must_change}
    for c in contract.must_not_change:
        if (c.character_id, c.field, c.target) in change_keys:
            findings.append(_f("H7.6", "hard",
                               f"{c.character_id}.{c.field}[{c.target}] 同时 must_change 与 must_not_change"))

    # H7.7 (V7 / D8)：ending.type 与 story_goal_type 兼容
    compat = _COMPAT_MATRIX.get(contract.story_goal_type, set())
    if contract.ending.type not in compat:
        findings.append(_f("H7.7", "hard",
                           f"ending.type {contract.ending.type} 与 story_goal_type {contract.story_goal_type} 不兼容"))

    # H7.8 (V8)：derived_from 引用的 Arc 项存在
    gate_facts = {g.fact_id for g in arc.knowledge_gates}
    tp_chapters = {tp.chapter for tp in arc.turning_points}
    for entry in contract.derived_from:
        m = _DERIVED_RE.match(entry)
        if not m:
            continue
        kind, val = m.group(1), m.group(2)
        if kind == "knowledge_gates":
            if val not in gate_facts:
                findings.append(_f("H7.8", "hard", f"derived_from 引用不存在的 gate {val}"))
        else:
            if not val.isdigit() or int(val) not in tp_chapters:
                findings.append(_f("H7.8", "hard", f"derived_from 引用不存在的 turning_point {val}"))

    # H7.10 (V9 / I5)：引用实体存在于 Story State（V9 映射为 H7.10，H7.9 保留）
    for ref in _contract_referenced_ids(contract):
        pool = _ref_pool(ref, state)
        if pool is not None and ref not in pool:
            findings.append(_f("H7.10", "hard", f"引用实体不存在：{ref}（V9）", evidence=ref))

    # H7.11 (V10)：field 枚举由 pydantic 保证；残留 target 为空 → HARD
    for c in list(contract.must_change) + list(contract.must_not_change):
        if not c.target.strip():
            findings.append(_f("H7.11", "hard",
                               f"change {c.character_id}.{c.field} target 为空（V10）"))

    return findings


def _h8_gate(proposals: List[EventProposal], state: StoryState
             ) -> Tuple[List[EventProposal], List[Finding]]:
    """H8 抽取置信度闸门（07 §4.3）。返回 (进入模拟的 active, HARD findings)。

    - 任一 conf < 500 → 整批 FAIL：active=[]，只落 H8.1（06 §4.0 归因 extraction）。
    - 500 ≤ conf < 700 → 该 Proposal 隔离（不入批），逐条落 H8.2 EXTRACTION_UNVERIFIED。
    - markup Proposal 引用不存在事实 → H6.2（归因抽取层，R4），一并隔离。
    """
    if any(p.extraction_confidence < 500 for p in proposals):
        low = min(p.extraction_confidence for p in proposals)
        return [], [_f("H8.1", "hard",
                       f"整批抽取置信度不足（最低 {low} < 500）→ FAIL",
                       suggestion="归因 extraction，整批重抽取（06 §4.0）")]

    active: List[EventProposal] = []
    findings: List[Finding] = []
    for p in proposals:
        eid = proposal_event_id(p)
        if p.extraction_method == "markup":
            fact = p.payload.get("fact_id")
            if fact is not None and fact not in state.facts:
                findings.append(_f("H6.2", "hard",
                                   f"markup 标注引用不存在事实 {fact}（{eid}）",
                                   evidence=fact, suggestion="归因 markup/抽取层（07 §4.3 R4）"))
                continue
        if 500 <= p.extraction_confidence < 700:
            findings.append(_f("H8.2", "hard",
                               f"EXTRACTION_UNVERIFIED：{eid} 置信度 {p.extraction_confidence} 隔离",
                               evidence=eid, suggestion="触发重抽取（不触发 Writer 重写 / Contract 重议）"))
        else:
            active.append(p)
    return active, findings
