"""确定性 50 章实验夹具（WP-E 前置，roadmap #79）。

**为什么不能用 experiment_10ch 直接跑 50 章**：10 章阶梯是环形取步
（`_step(ch) = _STEPS[(ch-1) % 10]`），ch11 起会对已建立的事实在 add 语义
下反复回环——那是夹具压力测试伪影，不是跨章推进，E2 读数会被它污染。

**ladder-v5 的解法**：ch1–10 逐字复用 ladder-v4 的十步；ch11–50 走
20 个从未在 must_change 里出现过的 (人物, 知识 fact) 对的 rank 阶梯——
每对占两章：首章 INFERS 建立 suspected，次章 OBSERVES 推进 known
（rank 推进是合法的新 Δ，04 §4.2 / reducers/knowledge.py 的
unknown<suspected<believed<known<confirmed）。40 章恰好 20 对，全库不回环。

对子池（排除 ch1–10 已用组合与 (LI,F2) 欺骗语义）：
张三 F7/F8/F12，王五 F1/F2/F3/F4/F5/F6/F9/F10/F12，赵六 F1–F8。
世界表/契约派生/正文标注全部复用 experiment_10ch 的原语，本文件只新增阶梯。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from plot_engine.models.contract import ArcContract
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState

from plot_engine.tests.fixtures import experiment_10ch as fx

LADDER_VERSION = "ladder-v5-50ch"

# (actor, fact) 池：按章序展开，i 对 → INFERS 章 11+2i，OBSERVES 章 12+2i
_PAIRS: List[tuple] = [
    (fx._ACTOR, fx._F7), (fx._ACTOR, fx._F8), (fx._ACTOR, fx._F12),
    (fx._WANG, fx._F1), (fx._WANG, fx._F2), (fx._WANG, fx._F3), (fx._WANG, fx._F4),
    (fx._WANG, fx._F5), (fx._WANG, fx._F6), (fx._WANG, fx._F9), (fx._WANG, fx._F10),
    (fx._WANG, fx._F12),
    (fx._ZHAO, fx._F1), (fx._ZHAO, fx._F2), (fx._ZHAO, fx._F3), (fx._ZHAO, fx._F4),
    (fx._ZHAO, fx._F5), (fx._ZHAO, fx._F6), (fx._ZHAO, fx._F7), (fx._ZHAO, fx._F8),
]


def _ladder_step(ch: int) -> Dict[str, Any]:
    a, f = _PAIRS[(ch - 11) // 2]
    if (ch - 11) % 2 == 0:
        return {"events": [fx._infers(f, [fx._F3], actor=a)],
                "must_change": [fx._knows("add", f, "suspected", a)]}
    return {"events": [fx._obs(f, actor=a)],
            "must_change": [fx._knows("update", f, "known", a)]}


def _step(ch: int) -> Dict[str, Any]:
    if ch <= len(fx._STEPS):
        return fx._STEPS[ch - 1]
    if ch > 50:
        raise ValueError(f"ladder-v5 只铺到第 50 章，收到 {ch}")
    return _ladder_step(ch)


def _mandatory(ch: int) -> List[Dict[str, Any]]:
    step = _step(ch)
    return step.get("mandatory", step["events"])


def build_arc(chapters: int = 50) -> ArcContract:
    intents = [{"chapter_no": ch,
                "story_goal": f"{fx._GOALS[(ch - 1) % len(fx._GOALS)]}（第 {ch} 章）",
                "story_goal_type": fx._GOAL_TYPES[ch % len(fx._GOAL_TYPES)],
                "ending": {"type": "cliffhanger", "strength": 500 + 100 * (ch % 5),
                           "description": "章尾悬念"},
                "must_change": _step(ch)["must_change"],
                "must_not_change": _step(ch).get("must_not_change", [
                    {"character_id": fx._ACTOR, "field": "knowledge", "operation": "update",
                     "target": fx._F2}]),
                "required_events": [{"event_type": e["event_type"],
                                     "description": f"{e['event_type']} {e['fact']}",
                                     "actors_involved": fx._actors(e)}
                                    for e in _mandatory(ch)]}
               for ch in range(1, chapters + 1)]
    return ArcContract(
        arc_id="arc_003", epoch=fx.EPOCH, chapter_range=(1, chapters),
        tension_curve=[min(1000, 300 + 60 * ch) for ch in range(1, chapters + 1)],
        turning_points=[{"chapter": c, "type": t, "description": d,
                         "required_event_types": sorted({e["event_type"] for e in _mandatory(c)})}
                        for c, (t, d) in fx._TURNS.items() if c <= chapters],
        knowledge_gates=[{"fact_id": f, "allowed_after_chapter": a, "reveal_stage_target": s}
                         for f, a, s in fx._GATES if a <= chapters],
        reader_beats=intents, created_at=fx.NOW)


def _proposals(ch: int, defect: Optional[str]) -> List[EventProposal]:
    out: List[EventProposal] = []
    events = list(_step(ch)["events"])
    if defect == "leak":
        events = events + [fx._obs(fx._F2)]
    if defect == "no_nail":
        nails = {m["event_type"] for m in _mandatory(ch)}
        events = [e for e in events if e["event_type"] not in nails]
    for i, e in enumerate(events):
        actor = fx._DEAD_ACTOR if defect == "dead" else e.get("actor", fx._ACTOR)
        out.append(EventProposal(
            proposed_event_type=e["event_type"], actor=actor, target=e["fact"], chapter=ch,
            seq=i, preconditions=[f"evt_{ch:08d}_000"] if e["event_type"] == "INFERS" and i else [],
            payload=e["payload"], confidence=e["confidence"], source_ref=f"para:{i + 4}",
            extraction_method="rule", extraction_confidence=1000))
    return out


def _channels(ch: int, defect: Optional[str] = None):
    def rule(*_a):
        return _proposals(ch, defect)

    def llm(*_a):
        return [p.model_copy(update={"extraction_method": "llm"}) for p in rule()]
    return rule, llm


def build_source(defects: Optional[Dict[int, str]] = None,
                 arc: Optional[ArcContract] = None):
    defects = defects or {}

    def src(ch: int, cur: StoryState) -> ChapterArtifacts:
        contract = fx.contract_for(arc or build_arc(), ch, cur)
        rule, llm = _channels(ch, defects.get(ch))
        return ChapterArtifacts(contract=contract, scene_plan=fx.plan_for(contract, cur),
                                draft=fx._draft(contract), rule_channel=rule, llm_channel=llm)
    return src


def make_config(chapters: int = 50) -> ExperimentConfig:
    if chapters < 11:
        raise ValueError(f"ladder-v5 至少 11 章（前 10 章复用 v4，第 11 章起进新阶梯），收到 {chapters}")
    return fx.make_config(chapters).model_copy(update={"arc_contract": build_arc(chapters)})


contract_for = fx.contract_for
plan_for = fx.plan_for
NOW = fx.NOW
dummy_writer = fx.dummy_writer
