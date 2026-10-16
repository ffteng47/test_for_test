"""归因 H 批夹具：ladder-v4 的**半密度契约**变体（结构面单变量实验）。

与 experiment_10ch 的唯一差异：非 turning point 章（2/3/4/6/7/10）的 `must_change`
与钉成 Arc 强制项的事件各**只保留一条**（原为两条/一条钉）。turning point 章 1/5/9
与空推进章 8 一字不动（D3 的 required_event_types 耦合、ch8 合法空形态都在）。
`events`（离线抽取道提案）保持全量，只削契约负载——离线跑法与 live 的差只在契约。

用途：与 14b 全密度基线（docs/phase0-live-run-10ch.md §9 三批）对比，判 Contract/Arc
类失败（H5.1/H5.3 领衔）是「任务单过重」还是「模型根本做不到」。归因必须单变量：
本批不换模型、不换尺、不换硬件以外的任何东西。

LADDER_VERSION 独立 ⇒ plan_sha256 独立 ⇒ 确认闸必须另开新工单。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from plot_engine.models.contract import ArcContract, ChapterContract
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.tests.fixtures import experiment_10ch as base
from plot_engine.tests.fixtures.experiment_10ch import (
    _belief, _GOALS, _GOAL_TYPES, _holds, _infers, _knows, _obs, _reads, _told,
    _F1, _F2, _F3, _F4, _F5, _F6, _F7, _F8, _F9, _F10, _F11,
    _ACTOR, _LI, _WANG, _ZHAO)

EPOCH = base.EPOCH
NOW = base.NOW
LADDER_VERSION = "ladder-v4-halfdensity"

# 半密度阶梯：非 TP 章 must_change/mandatory 各留 1（注释标保留的是哪条跃迁）。
# 与 base._STEPS 的 (ch, 三元组) 对应关系只删不加，唯一性/不回环性质自动继承。
_STEPS: List[Dict[str, Any]] = [
    base._STEPS[0],                                   # ch1 TP：原样
    {"events": base._STEPS[1]["events"],
     "mandatory": [base._STEPS[1]["events"][0]],      # 留「读阁簿」，削王五 BELIEVES 钉
     "must_change": [base._STEPS[1]["must_change"][0]]},   # 留 张三.knowledge F5
    {"events": base._STEPS[2]["events"],
     "mandatory": [base._STEPS[2]["events"][0]],      # 留「赵六当面告知」，削张三 SUSPECTS 钉
     "must_change": [base._STEPS[2]["must_change"][0]]},   # 留 张三.knowledge F6
    {"events": base._STEPS[3]["events"],
     "mandatory": [base._STEPS[3]["events"][0]],      # 留王五 READS，削李四 DOUBTS 钉
     "must_change": [base._STEPS[3]["must_change"][0]]},   # 留 王五.knowledge F7
    base._STEPS[4],                                   # ch5 TP：原样
    {"events": base._STEPS[5]["events"],
     "mandatory": [base._STEPS[5]["mandatory"][0]],   # 仍钉「下山来报」IS_TOLD
     "must_change": [base._STEPS[5]["must_change"][1]]},   # 留 张三.knowledge F10=believed，削赵六 known
    {"events": base._STEPS[6]["events"],
     "mandatory": [base._STEPS[6]["events"][0]],      # 留张三 READS，削王五 BELIEVES 钉
     "must_change": [base._STEPS[6]["must_change"][0]]},   # 留 张三.knowledge F11
    base._STEPS[7],                                   # ch8 空推进：原样
    base._STEPS[8],                                   # ch9 TP：原样
    {"events": base._STEPS[9]["events"],
     "mandatory": [base._STEPS[9]["events"][0]],      # 留张三 OBSERVES F2，削李四 DOUBTS 钉
     "must_change": [base._STEPS[9]["must_change"][0]],
     "must_not_change": []},                          # 解禁 F2 与基线同
]


def _step(ch: int) -> Dict[str, Any]:
    return _STEPS[(ch - 1) % len(_STEPS)]


def _mandatory(ch: int) -> List[Dict[str, Any]]:
    step = _step(ch)
    return step.get("mandatory", step["events"])


def build_arc(chapters: int = 10) -> ArcContract:
    """与 base.build_arc 同构，但 reader_beats/turning_points 取自本模块的半密度阶梯。"""
    intents = [{"chapter_no": ch,
                "story_goal": f"{_GOALS[(ch - 1) % len(_GOALS)]}（第 {ch} 章）",
                "story_goal_type": _GOAL_TYPES[ch % len(_GOAL_TYPES)],
                "ending": {"type": "cliffhanger", "strength": 500 + 100 * (ch % 5),
                           "description": "章尾悬念"},
                "must_change": _step(ch)["must_change"],
                "must_not_change": _step(ch).get("must_not_change", [
                    {"character_id": _ACTOR, "field": "knowledge", "operation": "update",
                     "target": _F2}]),
                "required_events": [{"event_type": e["event_type"],
                                     "description": f"{e['event_type']} {e['fact']}",
                                     "actors_involved": base._actors(e)}
                                    for e in _mandatory(ch)]}
               for ch in range(1, chapters + 1)]
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(1, chapters),
        tension_curve=[min(1000, 300 + 60 * ch) for ch in range(1, chapters + 1)],
        turning_points=[{"chapter": c, "type": t, "description": d,
                         "required_event_types": sorted({e["event_type"] for e in _mandatory(c)})}
                        for c, (t, d) in base._TURNS.items() if c <= chapters],
        knowledge_gates=[{"fact_id": f, "allowed_after_chapter": a, "reveal_stage_target": s}
                         for f, a, s in base._GATES if a <= chapters],
        reader_beats=intents, created_at=NOW)


def contract_for(arc: ArcContract, ch: int, state: StoryState) -> ChapterContract:
    return base.contract_for(arc, ch, state)


def plan_for(contract: ChapterContract, state: StoryState):
    return base.plan_for(contract, state)


def _proposals(ch: int, defect: Optional[str]) -> List[EventProposal]:
    """与 base._proposals 同构，但「钉」按本模块的半密度 mandatory 取。"""
    out: List[EventProposal] = []
    events = list(_step(ch)["events"])
    if defect == "leak":
        events = events + [_obs(_F2)]
    if defect == "no_nail":
        nails = {m["event_type"] for m in _mandatory(ch)}
        events = [e for e in events if e["event_type"] not in nails]
    for i, e in enumerate(events):
        actor = base._DEAD_ACTOR if defect == "dead" else e.get("actor", _ACTOR)
        out.append(EventProposal(
            proposed_event_type=e["event_type"], actor=actor, target=e["fact"], chapter=ch,
            seq=i, preconditions=[f"evt_{ch:08d}_000"] if e["event_type"] == "INFERS" and i else [],
            payload=e["payload"], confidence=e["confidence"], source_ref=f"para:{i + 4}",
            extraction_method="rule", extraction_confidence=1000))
    return out


def build_source(defects: Optional[Dict[int, str]] = None,
                 arc: Optional[ArcContract] = None):
    defects = defects or {}

    def src(ch: int, cur: StoryState) -> ChapterArtifacts:
        contract = contract_for(arc or build_arc(), ch, cur)

        def rule(*_a):
            return _proposals(ch, defects.get(ch))

        def llm(*_a):
            return [p.model_copy(update={"extraction_method": "llm"}) for p in rule()]
        return ChapterArtifacts(contract=contract, scene_plan=plan_for(contract, cur),
                                draft=base._draft(contract), rule_channel=rule, llm_channel=llm)
    return src


def make_config(chapters: int = 10) -> ExperimentConfig:
    cfg = base.make_config(chapters)
    return cfg.model_copy(update={"arc_contract": build_arc(chapters)})


def dummy_writer(scene, contract, state) -> str:
    return base.dummy_writer(scene, contract, state)
