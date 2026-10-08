"""不变量检查器 assert_consistent（10 §15 I1~I13 + 03 §10 I1~I8 的 Phase 0 可检子集）。

只读检查，绝不改状态（05 §9 I3）；发现形状 {code, ord, severity, detail}，
按 hard(0) < soft(1) < observation(2) 排序返回；干净状态返回 []。
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

from plot_engine.models.event import Event
from plot_engine.models.state import StoryState

_ORD: Dict[str, int] = {"hard": 0, "soft": 1, "observation": 2}

_KNOWN_PAYLOAD_REFS = ("fact_id", "item_id", "character_id", "conclusion_fact_id",
                       "stated_fact_id", "actual_belief_id", "contradicting_fact_id",
                       "speaker")


def _finding(findings: List[dict], code: str, severity: str, detail: str) -> None:
    findings.append({"code": code, "ord": _ORD[severity], "severity": severity,
                     "detail": detail})


def _resolve(kind: str, ref_id: str, state: StoryState):
    pool = {
        "char": state.characters, "loc": state.locations, "item": state.items,
        "fac": state.factions, "realm": state.realms, "abil": state.abilities,
        "rgn": state.regions, "fact": state.facts,
    }[kind]
    return pool.get(ref_id)


def _check_refs_in_payload(obj, state: StoryState, findings: List[dict], where: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _KNOWN_PAYLOAD_REFS and isinstance(v, str):
                _check_ref(v, state, findings, f"{where}.{k}")
            elif k == "evidence_fact_ids" and isinstance(v, list):
                for i, fid in enumerate(v):
                    if isinstance(fid, str):
                        _check_ref(fid, state, findings, f"{where}.evidence_fact_ids[{i}]")
            elif isinstance(v, (dict, list)):
                _check_refs_in_payload(v, state, findings, where)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_refs_in_payload(v, state, findings, where)


def _check_ref(ref_id: str, state: StoryState, findings: List[dict], where: str) -> None:
    prefix = ref_id.split("_", 1)[0] if "_" in ref_id else ""
    kind = {"char": "char", "loc": "loc", "item": "item", "fac": "fac",
            "realm": "realm", "abil": "abil", "rgn": "rgn", "fact": "fact"}.get(prefix)
    if kind is None:
        return  # 非实体引用（scn_id 等），Phase 0 不检
    if _resolve(kind, ref_id, state) is None:
        _finding(findings, "I2", "hard", f"未解析引用 {ref_id!r}（{where}）")


def _check_id_uniqueness(state: StoryState, findings: List[dict]) -> None:
    ids: List[str] = []
    ids += list(state.characters.keys())
    ids += list(state.locations.keys())
    ids += list(state.items.keys())
    ids += list(state.factions.keys())
    ids += list(state.realms.keys())
    ids += list(state.abilities.keys())
    ids += list(state.regions.keys())
    ids += list(state.facts.keys())
    ids += [r.relationship_id for r in state.relationships]
    ids += [e.inventory_id for e in state.inventory]
    ids += [f.relation_id for f in state.fact_relations]
    for dup, n in Counter(ids).items():
        if n > 1:
            _finding(findings, "I1", "hard", f"ID {dup!r} 重复出现 {n} 次")


def _check_entity_refs(state: StoryState, findings: List[dict]) -> None:
    for c in state.characters.values():
        if c.current_location is not None and c.current_location not in state.locations:
            _finding(findings, "I3", "hard",
                     f"{c.character_id} 位于未定义地点 {c.current_location!r}")
        for ref in filter(None, [c.realm, c.faction_id]):
            _check_ref(ref, state, findings, c.character_id)
        for ab in c.abilities:
            _check_ref(ab, state, findings, f"{c.character_id}.abilities")
    for loc in state.locations.values():
        for ref in filter(None, [loc.parent_location_id, loc.region_id,
                                 loc.realm_cap, loc.faction_control]):
            _check_ref(ref, state, findings, loc.location_id)
        for other in loc.connected_to:
            _check_ref(other, state, findings, f"{loc.location_id}.connected_to")
    for fac in state.factions.values():
        for ref in filter(None, [fac.parent_faction_id]):
            _check_ref(ref, state, findings, fac.faction_id)
        for ch in fac.members:
            if ch not in state.characters:
                _finding(findings, "I2", "hard", f"{fac.faction_id} 成员 {ch!r} 不存在")
        for loc_id in fac.controlled_locations:
            _check_ref(loc_id, state, findings, f"{fac.faction_id}.controlled_locations")
    for r in state.realms.values():
        for ref in filter(None, [r.previous_realm, r.next_realm]):
            _check_ref(ref, state, findings, r.realm_id)


def _check_edges(state: StoryState, findings: List[dict]) -> None:
    for rel in state.relationships:
        for side in (rel.from_character, rel.to_character):
            if side not in state.characters:
                _finding(findings, "I6", "hard",
                         f"关系 {rel.relationship_id} 端点 {side!r} 不存在")
    for e in state.inventory:
        if e.quantity < 0:  # 模型 ge=0 下恒真成立，保留为廉价哨兵（I4）
            _finding(findings, "I4", "hard",
                     f"库存 {e.inventory_id} 数量 {e.quantity} 为负")
        if e.character_id not in state.characters:
            _finding(findings, "I2", "hard", f"库存 {e.inventory_id} 角色不存在")
        if e.item_id not in state.items:
            _finding(findings, "I2", "hard", f"库存 {e.inventory_id} 物品不存在")


def _check_overdraw(events: List[Event], findings: List[dict]) -> None:
    held: Dict[tuple, int] = {}
    for ev in events:
        if ev.event_type == "ITEM_ACQUIRED":
            key = (ev.payload["character_id"], ev.payload["item_id"])
            held[key] = held.get(key, 0) + int(ev.payload["quantity"])
        elif ev.event_type == "ITEM_CONSUMED":
            key = (ev.payload["character_id"], ev.payload["item_id"])
            held[key] = held.get(key, 0) - int(ev.payload["quantity"])
    for (char_id, item_id), balance in held.items():
        if balance < 0:
            _finding(findings, "H4.1", "hard",
                     f"{char_id} 对 {item_id} 超额消耗 {-balance} 件（从事件流重算）")


def _check_actor_status(state: StoryState, events: List[Event], findings: List[dict]) -> None:
    for ev in events:
        c = state.characters.get(ev.actor or "")
        if c is None:
            continue  # 引用缺失由 I2 报
        if c.status in ("dead", "unborn"):
            died = c.death_chapter
            if c.status == "unborn" or died is None or ev.chapter >= died:
                _finding(findings, "I7", "hard",
                         f"{c.status} 角色 {c.character_id} 作为事件 {ev.event_id} 的 actor")
        elif c.status == "missing" and ev.location is not None:
            _finding(findings, "I7", "soft",
                     f"missing 角色 {c.character_id} 的事件 {ev.event_id} 带具体位置（10 §4.2）")


def _check_ledgers(state: StoryState, committed_ids: set, findings: List[dict]) -> None:
    entries = ([(e.source_event_id, e.fact_id, "knowledge") for e in state.knowledge_ledger]
               + [(e.source_event_id, e.fact_id, "belief") for e in state.belief_ledger]
               + [(e.source_event_id, e.fact_id, "reader") for e in state.reader_ledger])
    for src, fact_id, kind in entries:
        if fact_id not in state.facts:
            _finding(findings, "I9", "hard", f"{kind} 记录引用未定义事实 {fact_id!r}")
        if src not in committed_ids:
            _finding(findings, "I9", "hard", f"{kind} 记录 source {src!r} 不在已提交事件集")


def _check_reveal_stage(state: StoryState, findings: List[dict]) -> None:
    for f in state.facts.values():
        if f.narrative_truth != f.objective_truth and f.reveal_stage == "confirmed":
            _finding(findings, "R7", "hard",
                     f"事实 {f.fact_id} 双层真相不一致却标记 confirmed（02 §6 R7）")


def _check_contradicted_unknown(state: StoryState, events: List[Event], findings: List[dict]) -> None:
    for ev in events:
        if ev.event_type != "FACT_CONTRADICTED":
            continue
        fact_id = ev.payload.get("fact_id")
        entry = next((k for k in state.knowledge_ledger
                      if k.character_id == (ev.actor or "") and k.fact_id == fact_id), None)
        if entry is None or entry.knowledge_state == "unknown":
            _finding(findings, "FACT_CONTRADICTED_UNKNOWN", "observation",
                     f"对未知事实 {fact_id!r} 施加 FACT_CONTRADICTED（{ev.event_id}，03 §5.4）")


def assert_consistent(state: StoryState, events: List[Event]) -> List[dict]:
    findings: List[dict] = []
    _check_id_uniqueness(state, findings)
    _check_entity_refs(state, findings)
    _check_edges(state, findings)
    _check_overdraw(events, findings)
    _check_actor_status(state, events, findings)
    _check_ledgers(state, {e.event_id for e in events}, findings)
    _check_reveal_stage(state, findings)
    _check_contradicted_unknown(state, events, findings)
    for ev in events:  # 事件层引用（actor/target/location/payload）
        if ev.actor is not None:
            _check_ref(ev.actor, state, findings, f"{ev.event_id}.actor")
        if ev.location is not None:
            _check_ref(ev.location, state, findings, f"{ev.event_id}.location")
        for ref in (ev.target,):
            if ref is not None:
                _check_ref(ref, state, findings, f"{ev.event_id}.target")
        _check_refs_in_payload(ev.payload, state, findings, ev.event_id)
    findings.sort(key=lambda f: (f["ord"], f["code"]))
    return findings
