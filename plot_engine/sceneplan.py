"""ScenePlan 自校验 SP1~SP7（04 附录 B §8.3）。

只读、幂等、输出可序列化，复用 Validator 的 `Finding`/`ValidationResult`/`_bucket`
分桶纪律（与 `validate_contract`/H7 同族）。ScenePlan 是 pre-Writer 规划闸，
由 Plot 层调用，**不进 Event Log、不改 State**。数值定点 ×1000。
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional

from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.validator import Finding, ValidationResult, _bucket, _f

# ReaderSignal.target_state → Beat.reader_target 覆盖映射（unaware 无对应标注要求）
_SIGNAL_TO_READER: Dict[str, Optional[str]] = {
    "knows": "learns", "hinted": "hinted", "deceived": "deceived", "unaware": None,
}


def _reachable(state: StoryState, frm: Optional[str], to: str) -> bool:
    """对称可达（10 W-S1/W-S4）：边集 = connected_to ∪ 反向边；frm==to 路径长 0。"""
    if frm is None:
        return False
    if frm == to:
        return True
    if frm not in state.locations or to not in state.locations:
        return False
    adj: Dict[str, set] = {lid: set() for lid in state.locations}
    for lid, loc in state.locations.items():
        for other in loc.connected_to:
            if other in adj:
                adj[lid].add(other)
                adj[other].add(lid)          # 对称
    seen = {frm}
    q = deque([frm])
    while q:
        cur = q.popleft()
        if cur == to:
            return True
        for nxt in adj[cur]:
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return to in seen


def _iter_beats(plan: ScenePlan):
    for sc in plan.scenes:
        for b in sc.beats:
            yield sc, b


def validate_scene_plan(plan: ScenePlan, contract, state: StoryState) -> ValidationResult:
    findings: List[Finding] = []
    chars, locs, realms, facts = state.characters, state.locations, state.realms, state.facts

    # SP1：引用实体存在性（char / loc / realm / fact 四类）
    def _need(pool, rid, kind):
        if rid is not None and rid not in pool:
            findings.append(_f("SP1", "hard", f"{kind} 引用不存在：{rid}", evidence=rid))
    for sc in plan.scenes:
        _need(locs, sc.location, "loc")
        for cid in sc.characters:
            _need(chars, cid, "char")
    for _sc, b in _iter_beats(plan):
        for cid in b.actors:
            _need(chars, cid, "char")
        _need(locs, b.location, "loc")
        _need(realms, b.actor_realm, "realm")
        _need(realms, b.target_realm, "realm")
        _need(facts, b.reader_fact_id, "fact")

    # SP2：∪ expected_event_types 覆盖 required_events 每个 event_type
    covered = set()
    for _sc, b in _iter_beats(plan):
        covered |= set(b.expected_event_types)
    for req in getattr(contract, "required_events", []):
        if req.event_type not in covered:
            findings.append(_f("SP2", "hard",
                               f"required {req.event_type} 未被任何 beat 覆盖", evidence=req.event_type))

    # SP3：任何 beat 不得声明 forbidden event_type
    forbidden = {fb.event_type for fb in getattr(contract, "forbidden_events", [])}
    for _sc, b in _iter_beats(plan):
        for et in b.expected_event_types:
            if et in forbidden:
                findings.append(_f("SP3", "hard",
                                   f"beat {b.beat_id} 声明禁用事件 {et}", evidence=et))

    # SP4：每条 reader_signal 被某 beat (reader_target/reader_fact_id) 覆盖
    beat_signals = {(b.reader_target, b.reader_fact_id) for _sc, b in _iter_beats(plan)}
    for sig in getattr(contract, "reader_signals", []):
        want = _SIGNAL_TO_READER.get(sig.target_state)
        if want is None:
            continue
        if (want, sig.fact_id) not in beat_signals:
            findings.append(_f("SP4", "hard",
                               f"reader_signal {sig.fact_id}→{sig.target_state} 无 beat 覆盖",
                               evidence=sig.fact_id))

    # SP5：非 travel beat 声明 location，需在 scene 各角色 current_location 可达范围内
    for sc in plan.scenes:
        for b in sc.beats:
            if b.action_type == "travel" or b.location is None:
                continue
            for cid in sc.characters:
                c = chars.get(cid)
                if c is None or c.current_location is None:
                    continue
                if not _reachable(state, c.current_location, b.location):
                    findings.append(_f("SP5", "hard",
                                       f"beat {b.beat_id} 地点 {b.location} 对 {cid}（在 {c.current_location}）不可达",
                                       evidence=b.beat_id))

    # SP6：同章内 scene_id / beat_id 唯一
    for label, ids in (("scene_id", [sc.scene_id for sc in plan.scenes]),
                       ("beat_id", [b.beat_id for _sc, b in _iter_beats(plan)])):
        seen = set()
        for i in ids:
            if i in seen:
                findings.append(_f("SP6", "hard", f"{label} 重复：{i}", evidence=i))
            seen.add(i)

    # SP7：scene.tension 与 contract.tension_target 偏差 > 300 → SOFT（阈值与 H7.3 一致）
    for sc in plan.scenes:
        if abs(sc.tension - contract.tension_target) > 300:
            findings.append(_f("SP7", "soft",
                               f"scene {sc.scene_id} tension {sc.tension} 与目标 {contract.tension_target} 偏差 > 300"))

    return _bucket(findings)
