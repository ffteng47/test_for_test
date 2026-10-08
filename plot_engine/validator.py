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
