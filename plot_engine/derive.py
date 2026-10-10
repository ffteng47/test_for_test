"""Plot 层派生：Arc Contract → Chapter Contract（04 §4.3 D1–D9）。

04 §1 明说本协议「不含 Contract 如何生成」，但 §4.3 的派生规则是确定性的：
张力取自曲线、turning_point 的事件类型进 required_events、gate 到期与否决定
knowledge_allowed/forbidden、到期未揭示的 gate 必须变成 REVEALS 硬要求。
本模块把这些**算出来**，使 10 章实验真正逐章推进——夹具里十份相同契约测不到跨章约束。

推不出来的东西（story_goal / must_change / ending）显式来自 `arc.reader_beats`
（04 §3.1 的 SOFT 元数据槽位）：C2 要求 Chapter Contract 派生自 Arc Contract，
放在 Arc 里就不算自我生成；生成器**绝不编造**剧情意图，缺意图就响亮失败。

冲突一律抛 `ArcConflict`（06 §4.3 Arc Error → 回 Arc 层重规划），
不在生成器里悄悄放宽 gate 或删掉 forbidden——那正是「实验结果由我的取舍决定」的老路。
只读、无网络、无时钟：`created_at` 由调用方给定，同输入必同输出。
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Sequence, Set

from pydantic import BaseModel, ValidationError

from plot_engine.models.contract import (
    ArcContract, ChapterContract, ChapterHook, CharacterChange, FIELD_EVENT_TYPES,
    ForbiddenEvent, KnowledgeGate, ReaderSignal, RequiredEvent,
)
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.sceneplan import _SIGNAL_TO_READER

REVEAL_EVENT = "REVEALS"


class ArcConflict(ValueError):
    """Arc 自身给不出合法的本章契约（06 §4.3）。交人工/回 Arc 层，不自动放宽。"""


class NoChapterIntent(ValueError):
    """本章在 `arc.reader_beats` 里没有作者意图 → 拒绝凭空生成 story_goal。"""


class ChapterIntent(BaseModel):
    """作者逐章声明：只放 D1–D9 推不出来的字段，能被协议派生的一律不在此重复。"""
    chapter_no: int
    story_goal: str
    story_goal_type: Literal["revelation", "escalation", "setup", "resolution",
                             "transition", "confrontation", "reflection"]
    ending: ChapterHook
    must_change: List[CharacterChange] = []
    must_not_change: List[CharacterChange] = []
    required_events: List[RequiredEvent] = []
    forbidden_events: List[ForbiddenEvent] = []


# 04 §4.3 D9：gate 的揭示档位 → 读者信号目标状态。hidden 不产生信号
# （「让读者仍然不知道」不是一条要建立的信号），deceived 无 gate 来源，只能由作者显式声明。
_STAGE_TO_READER = {"hinted": "hinted", "partial": "hinted", "confirmed": "knows"}


def intents_by_chapter(arc: ArcContract) -> Dict[int, ChapterIntent]:
    out: Dict[int, ChapterIntent] = {}
    for i, raw in enumerate(arc.reader_beats):
        if not isinstance(raw, dict) or "chapter_no" not in raw:
            continue                        # 非逐章意图的 SOFT 元数据
        try:
            intent = ChapterIntent(**raw)
        except ValidationError as e:
            raise NoChapterIntent(f"arc.reader_beats[{i}] 不是合法的逐章意图：{e}") from e
        out[intent.chapter_no] = intent
    return out


def arc_mandated_event_types(arc: ArcContract, chapter_no: int) -> Set[str]:
    """Arc 强制本章出现的事件类型（D3 turning_point + D6 逾期 gate）。
    作者与 Revision 都无权删——06 §4.2 的「重议」只放宽作者自订的要求。"""
    mandated = {etype for tp in arc.turning_points if tp.chapter == chapter_no
                for etype in tp.required_event_types}
    if any(g.must_reveal_by_chapter is not None and chapter_no > g.must_reveal_by_chapter
           for g in arc.knowledge_gates):
        mandated.add(REVEAL_EVENT)
    return mandated


def _cast(intent: ChapterIntent) -> List[str]:
    ids = [c.character_id for c in list(intent.must_change) + list(intent.must_not_change)]
    for req in intent.required_events:
        ids += list(req.actors_involved)
    return sorted({i for i in ids if i})


def _covers(events: Sequence[RequiredEvent], event_type: str, fact_id: str) -> bool:
    """04 §4.1 的 RequiredEvent 没有 fact 字段，gate↔事件 只能靠描述里的 fact_id 关联（C6）。"""
    return any(e.event_type == event_type and fact_id in e.description for e in events)


def _gates(arc: ArcContract, chapter_no: int, cast: Sequence[str]
           ) -> tuple[Set[str], Set[str], List[KnowledgeGate]]:
    """D4/D5：到期且本章角色匹配 → allowed；未到期 → forbidden；其余不进本章约束。"""
    allowed: Set[str] = set()
    forbidden: Set[str] = set()
    used: List[KnowledgeGate] = []
    for gate in arc.knowledge_gates:
        if chapter_no < gate.allowed_after_chapter:
            forbidden.add(gate.fact_id)
        elif not gate.allowed_characters or set(gate.allowed_characters) & set(cast):
            allowed.add(gate.fact_id)
        else:
            continue
        used.append(gate)
    return allowed, forbidden, used


def derive_chapter_contract(arc: ArcContract, chapter_no: int, state: StoryState, *,
                            created_at: str, version: int = 1) -> ChapterContract:
    """按 04 §4.3 派生本章契约；产物保证过 `Validator.validate_contract`（H7）无 HARD。"""
    start, end = arc.chapter_range
    if not (start <= chapter_no <= end):                      # D1
        raise ValueError(f"chapter_no {chapter_no} 不在 arc 范围 ({start}, {end})")
    intent = intents_by_chapter(arc).get(chapter_no)
    if intent is None:
        raise NoChapterIntent(f"arc {arc.arc_id} 第 {chapter_no} 章没有 reader_beats 意图")

    cast = _cast(intent)
    derived: List[str] = [f"{arc.arc_id}.reader_beats[{chapter_no}]"]   # D7/C2：作者意图也记来源

    # D2'：张力取曲线本章值（曲线缺省则留 schema 默认，H7.3 只比不阻断）
    idx = chapter_no - start
    tension = arc.tension_curve[idx] if 0 <= idx < len(arc.tension_curve) else 500

    # D3：本章命中 turning_point → 其事件类型必须进 required_events（HARD）
    events: List[RequiredEvent] = list(intent.required_events)
    for tp in arc.turning_points:
        if tp.chapter != chapter_no:
            continue
        derived.append(f"{arc.arc_id}.turning_points[{tp.chapter}]")
        for etype in tp.required_event_types:
            if not any(e.event_type == etype for e in events):
                events.append(RequiredEvent(event_type=etype, description=tp.description))

    allowed, forbidden, used = _gates(arc, chapter_no, cast)
    for gate in used:
        derived.append(f"{arc.arc_id}.knowledge_gates[{gate.fact_id}]")

    # D6：已过 must_reveal_by_chapter 仍未出现在 required_events → 契约非法，故补 REVEALS
    for gate in arc.knowledge_gates:
        if gate.must_reveal_by_chapter is None or chapter_no <= gate.must_reveal_by_chapter:
            continue
        if _covers(events, REVEAL_EVENT, gate.fact_id):
            continue
        actors = (sorted(set(gate.allowed_characters) & set(cast)) or cast)
        events.append(RequiredEvent(
            event_type=REVEAL_EVENT,
            description=f"揭示 {gate.fact_id}（{arc.arc_id} gate 限期 {gate.must_reveal_by_chapter}）",
            actors_involved=actors))

    # 06 §4.3：Arc 给的约束互相排斥 → 不静默取舍，交给 Arc 层
    if allowed & forbidden:
        raise ArcConflict(f"{arc.arc_id} 第 {chapter_no} 章事实同时 allowed/forbidden："
                          f"{sorted(allowed & forbidden)}")
    req_types = {e.event_type for e in events}
    clash = req_types & {f.event_type for f in intent.forbidden_events}
    if clash:
        raise ArcConflict(f"{arc.arc_id} 第 {chapter_no} 章事件类型同时被要求与被禁止："
                          f"{sorted(clash)}（06 §4.3 → 回 Arc 层）")
    overdue_forbidden = [g.fact_id for g in arc.knowledge_gates
                         if g.must_reveal_by_chapter is not None
                         and chapter_no > g.must_reveal_by_chapter and g.fact_id in forbidden]
    if overdue_forbidden:
        raise ArcConflict(f"{arc.arc_id} 第 {chapter_no} 章要求揭示 "
                          f"{sorted(overdue_forbidden)}，但同一 gate 又禁止该事实")

    # 04 §4.2：每条 must_change 必须被对应 Event 实现（映射表 10 §4.3）。Δ 在本章
    # 根本实现不了，是 Arc 给错了输入（06 §4.3）——在这里响亮失败，别让它烧完
    # 三轮修订才现形，那三轮烧的是 token，换来的还是同一句 H5.3「无实现事件」。
    implementable = {e.event_type for e in events}
    unmet = [f"{c.character_id}.{c.field}→{c.target}" for c in intent.must_change
             if not implementable & FIELD_EVENT_TYPES.get(c.field, set())]
    if unmet:
        raise ArcConflict(f"{arc.arc_id} 第 {chapter_no} 章的 must_change 没有可实现它的"
                          f"事件类型（现有 {sorted(implementable)}）：{unmet}")

    # D9：只有到期 gate 才能产生读者信号，未到期的 fact 绝不标 knows
    signals: Dict[str, str] = {}
    for gate in arc.knowledge_gates:
        if gate.fact_id in forbidden or gate.fact_id not in allowed:
            continue
        target = _STAGE_TO_READER.get(gate.reveal_stage_target)
        if target:
            signals.setdefault(gate.fact_id, target)

    return ChapterContract(
        chapter_no=chapter_no, arc_id=arc.arc_id, epoch=arc.epoch, version=version,
        story_goal=intent.story_goal, story_goal_type=intent.story_goal_type,
        must_change=intent.must_change, must_not_change=intent.must_not_change,
        required_events=events, forbidden_events=intent.forbidden_events,
        knowledge_allowed=sorted(allowed), knowledge_forbidden=sorted(forbidden),
        reader_signals=[ReaderSignal(fact_id=f, target_state=s)
                        for f, s in sorted(signals.items())],
        tension_target=tension, ending=intent.ending,
        derived_from=list(dict.fromkeys(derived)), created_at=created_at)


MIN_SCENES, MAX_SCENES = 3, 7
MIN_BEATS, MAX_BEATS = 3, 7


def _contract_cast(contract: ChapterContract) -> List[str]:
    ids = [c.character_id for c in list(contract.must_change) + list(contract.must_not_change)]
    for req in contract.required_events:
        ids += list(req.actors_involved)
    return sorted({i for i in ids if i})


def _scene_location(contract: ChapterContract, state: StoryState) -> Optional[str]:
    """地点不是契约的一部分：只有当本章角色在 State 里位置唯一时，才把那个既成事实带进场景。"""
    locs = {state.characters[c].current_location for c in _contract_cast(contract)
            if c in state.characters}
    locs.discard(None)
    return locs.pop() if len(locs) == 1 else None


def _beat_slot(items: List[dict]) -> dict:
    """同槽合并：SP2 只看并集，SP4 要求读者信号逐条在位 → 信号先分槽，事件才可能并进来。"""
    merged = {"expected_event_types": [], "actors": []}
    for it in items:
        merged["expected_event_types"] += it["expected_event_types"]
        merged["actors"] += it["actors"]
        if it.get("reader_fact_id"):
            merged["reader_target"] = it["reader_target"]
            merged["reader_fact_id"] = it["reader_fact_id"]
    merged["intent"] = "；".join(dict.fromkeys(i["intent"] for i in items))
    merged["actors"] = sorted(set(merged["actors"]))
    return merged


def _pack(items: List[dict], slots: int) -> List[dict]:
    buckets: List[List[dict]] = [[] for _ in range(slots)]
    for i, it in enumerate(items):                     # 信号拍优先：各自占一槽，不被合并吃掉
        buckets[i % slots].append(it)
    return [_beat_slot(b) for b in buckets]


def derive_scene_plan(contract: ChapterContract, state: StoryState, *,
                      created_at: str) -> ScenePlan:
    """Contract → ScenePlan（04 附录 B）：SP2/SP4 由构造覆盖，SP3 依赖 H7.5 已排除的冲突。

    Beat 只承载契约里已有的东西（要求的事件类型、要建立的读者信号）；不足 3×3 时补的是
    纯结构过渡拍（无事件、无事实），因为 Schema 要求每场景 3~7 拍，而契约没说话。
    """
    event_beats = [{"expected_event_types": [req.event_type], "intent": req.description,
                    "actors": list(req.actors_involved)}
                   for req in contract.required_events]
    signal_beats = [{"expected_event_types": [], "intent": f"建立读者对 {sig.fact_id} 的认知",
                     "actors": [], "reader_target": target, "reader_fact_id": sig.fact_id}
                    for sig in contract.reader_signals
                    for target in [_SIGNAL_TO_READER.get(sig.target_state)] if target]

    items = signal_beats + event_beats
    scenes_n = max(MIN_SCENES, min(MAX_SCENES, -(-len(items) // MAX_BEATS) or MIN_SCENES))
    per_scene = max(MIN_BEATS, min(MAX_BEATS, -(-len(items) // scenes_n) or MIN_BEATS))
    slots = scenes_n * per_scene
    rows = _pack(items, slots) if len(items) >= slots else items + [
        {"expected_event_types": [], "intent": "过渡", "actors": []}] * (slots - len(items))

    location = _scene_location(contract, state)
    cast = _contract_cast(contract)
    scenes: List[Scene] = []
    for i in range(-(-len(rows) // per_scene)):
        chunk = rows[i * per_scene:(i + 1) * per_scene]
        actors = sorted({a for r in chunk for a in r["actors"]})
        beats = [Beat(beat_id=f"bt_{i * per_scene + j:06d}", seq=j,
                      beat_type=("setup" if j == 0 else
                                 "turn" if j == len(chunk) - 1 else "pressure"),
                      location=None, **r)
                 for j, r in enumerate(chunk)]
        scenes.append(Scene(scene_id=f"scn_{contract.chapter_no:04d}_{i + 1:02d}",
                            chapter_no=contract.chapter_no, seq=i, location=location,
                            characters=actors or cast, tension=contract.tension_target,
                            beats=beats))

    provenance = ([f"chapter_contract[{contract.chapter_no}].required_events[{e.event_type}]"
                   for e in contract.required_events]
                  + [f"chapter_contract[{contract.chapter_no}].reader_signals[{s.fact_id}]"
                     for s in contract.reader_signals])
    return ScenePlan(plan_id=f"sop_{contract.chapter_no:08d}",
                     chapter_no=contract.chapter_no, arc_id=contract.arc_id,
                     contract_version=contract.version, scenes=scenes,
                     derived_from=list(dict.fromkeys(provenance)),
                     epoch=contract.epoch, created_at=created_at)
