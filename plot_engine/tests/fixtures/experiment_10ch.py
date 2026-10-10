"""确定性 10 章实验 `chapter_source`（08 Day 20–22 测试夹具，网络无关）。

**契约与场景不再手写**：这里是 `docs/phase0-live-run-10ch.md` backlog #1 的修复处——
一份**有内容的 ArcContract**（逐章张力、三个 turning point、四个知识闸门（含一个中段开闸）、
十章逐章意图），Chapter Contract 与 ScenePlan 由 `plot_engine.derive` 按 04 §4.3 / 附录 B 派生。
于是每一章的约束真的不一样，10 章实验才开始测试「跨章推进」而不是一条约束重复十遍。

**逐章知识阶梯（backlog #1 / A）**：`must_change` 的语义是 Δ（04 §4.2「每条必须被对应 Event
实现」+ §5.2 W1 + 10 §4.3 映射表），不是章末谓词。所以每一步只声明**本章真的发生的那一次
跃迁**，并由本章事件流里一条同 field 的实现事件兑现；`add` 仅出现在事实首次建立的那一章，
此后写成 rank 更新（suspected→known）。第 8 步的 `must_change` 故意为空——契约必须允许
「本章不推进」这个合法形态。三个 turning point 落在阶梯的第 1/5/9 步，其
`required_event_types` 直接取那一步真的会发出的事件类型，H5.1 因此不可能自相矛盾。

闸门不给 reveal 限期：夹具 Writer 是确定性的，要求它写不出的东西只会让离线演练一路 FAIL，
那就变成在测夹具而不是测管道。`defects` 把指定章改成 "leak"（追加一条建立禁止知识
fact_000002 的 OBSERVES）或 "dead"（本章事件全换成死人出场）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from plot_engine.derive import derive_chapter_contract, derive_scene_plan
from plot_engine.models.contract import ArcContract, ChapterContract
from plot_engine.models.entity import Character
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"
NOW = "2026-10-09T00:00:00Z"
_ACTOR = "char_000001"
_DEAD_ACTOR = "char_000009"
_F1, _F2, _F3, _F4 = "fact_000001", "fact_000002", "fact_000003", "fact_000004"
# H5.5 把章尾 hook 与 contract.ending.type 对齐 ⇒ 逐章意图只能在兼容 cliffhanger
# 的目标类型里变（04 §4.4）。
_GOAL_TYPES = ["revelation", "escalation", "confrontation"]
_GOALS = ["张三在藏宝阁验出印章是伪造的。", "伪造印章把矛头指向宗门内部。",
          "有人不想让张三继续查下去。", "张三第一次怀疑身边人的说法。",
          "线索断在一句对不上的供词上。", "张三被迫在真相与立场之间选边。",
          "印泥的来源指向守阁的人。", "一次回避比一句谎话更像回答。",
          "张三把三件小事串成同一条线。", "结论逼近，但说出来的代价开始显现。"]
_FIX = json.loads((Path(__file__).parent / "traitor_arc.json").read_text(encoding="utf-8"))


# ---- 阶梯的一步 = 本章真的发生的一次跃迁 + 兑现它的事件 ---------------------------

def _obs(fact: str, method: str = "sight") -> Dict[str, Any]:
    return {"event_type": "OBSERVES", "fact": fact, "confidence": 1000,
            "payload": {"fact_id": fact, "method": method}}


def _reads(fact: str) -> Dict[str, Any]:
    return {"event_type": "READS", "fact": fact, "confidence": 900,
            "payload": {"fact_id": fact, "method": "ledger"}}


def _infers(conclusion: str, evidence: List[str]) -> Dict[str, Any]:
    return {"event_type": "INFERS", "fact": conclusion, "confidence": 700,
            "payload": {"conclusion_fact_id": conclusion, "evidence_fact_ids": evidence}}


def _belief(event_type: str, fact: str, strength: int) -> Dict[str, Any]:
    return {"event_type": event_type, "fact": fact, "confidence": strength,
            "payload": {"fact_id": fact, "belief_strength": strength}}


def _knows(op: str, fact: str, expected: str) -> Dict[str, Any]:
    return {"character_id": _ACTOR, "field": "knowledge", "operation": op,
            "target": fact, "expected_value": expected}


def _holds(op: str, fact: str, expected: str) -> Dict[str, Any]:
    return {"character_id": _ACTOR, "field": "belief", "operation": op,
            "target": fact, "expected_value": expected}


# expected_value 不超过该事件类型的 reducer 上限（03 §4.3/§5.1）：
# OBSERVES/READS→known，INFERS→suspected，BELIEVES→believes，SUSPECTS→suspects，DOUBTS→doubts。
_STEPS: List[Dict[str, Any]] = [
    {"events": [_obs(_F3), _infers(_F1, [_F3])],
     "must_change": [_knows("add", _F3, "known"), _knows("add", _F1, "suspected")]},
    {"events": [_obs(_F1)], "must_change": [_knows("update", _F1, "known")]},
    {"events": [_belief("BELIEVES", _F1, 700)],
     "must_change": [_holds("add", _F1, "believes")]},
    {"events": [_belief("DOUBTS", _F1, 500)], "must_change": [_holds("update", _F1, "doubts")]},
    {"events": [_infers(_F4, [_F1])], "must_change": [_knows("add", _F4, "suspected")]},
    {"events": [_reads(_F4)], "must_change": [_knows("update", _F4, "known")]},
    {"events": [_belief("SUSPECTS", _F4, 500)],
     "must_change": [_holds("add", _F4, "suspects")]},
    {"events": [_obs(_F3)], "must_change": []},          # 本章不推进：合法形态
    {"events": [_obs(_F3), _infers(_F1, [_F3]), _belief("BELIEVES", _F3, 600)],
     "must_change": [_holds("add", _F3, "believes")]},
    {"events": [_obs(_F2)], "must_change": [_knows("add", _F2, "known")],
     "must_not_change": []},                             # 第 10 步解禁 fact_000002
]
# turning point 挂在阶梯上真的有对应事件的第 1/5/9 步（事件类型由那一步自己给出）。
_TURNS = {1: ("revelation", "印章是伪造的"), 5: ("escalation", "矛头指向内部"),
          9: ("crisis", "串成一条线")}
# 闸门绝对章号与阶梯首轮的步号对齐：fact_000004 第 5 步首次被推断、fact_000002 第 10 步解禁。
_GATE_F4, _GATE_F2 = 5, 10


def _step(ch: int) -> Dict[str, Any]:
    return _STEPS[(ch - 1) % len(_STEPS)]


def build_arc(chapters: int = 10) -> ArcContract:
    """逐章意图 + 张力曲线 + turning_points + knowledge_gates：契约的合法来源（04 C2）。"""
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
                                     "actors_involved": [_ACTOR]}
                                    for e in _step(ch)["events"]]}
               for ch in range(1, chapters + 1)]
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(1, chapters),
        tension_curve=[min(1000, 300 + 60 * ch) for ch in range(1, chapters + 1)],
        turning_points=[{"chapter": c, "type": t, "description": d,
                         "required_event_types": sorted({e["event_type"] for e in _step(c)["events"]})}
                        for c, (t, d) in _TURNS.items() if c <= chapters],
        # hidden = 本章不给读者建立该事实 → 不产生 reader_signal（04 §4.3 D9）
        knowledge_gates=[
            {"fact_id": _F1, "allowed_after_chapter": 1, "reveal_stage_target": "hidden"},
            {"fact_id": _F3, "allowed_after_chapter": 1, "reveal_stage_target": "confirmed"},
            {"fact_id": _F4, "allowed_after_chapter": _GATE_F4, "reveal_stage_target": "hinted"},
            {"fact_id": _F2, "allowed_after_chapter": _GATE_F2, "reveal_stage_target": "hidden"}],
        reader_beats=intents, created_at=NOW)


def contract_for(arc: ArcContract, ch: int, state: StoryState) -> ChapterContract:
    return derive_chapter_contract(arc, ch, state, created_at=NOW)


def plan_for(contract: ChapterContract, state: StoryState) -> ScenePlan:
    return derive_scene_plan(contract, state, created_at=NOW)


def _draft(contract: ChapterContract) -> str:
    """正文按契约的 reader_signals 生成标注：W8 要命中什么，本章就标什么（夹具不该自己漏）。"""
    marks = [f"<!-- reader_{_MARK_KIND[s.target_state]}: {s.fact_id} -->"
             for s in contract.reader_signals]
    hook = f"<!-- hook: {contract.ending.type} strength={contract.ending.strength} -->"
    return "第{ch}章：张三凝视印章。\n\n".format(ch=contract.chapter_no) + \
        "\n\n".join(marks + [hook])


_MARK_KIND = {"knows": "learns", "hinted": "hinted", "deceived": "deceived"}


def _proposals(ch: int, defect: Optional[str]) -> List[EventProposal]:
    actor = _DEAD_ACTOR if defect == "dead" else _ACTOR
    events = list(_step(ch)["events"])
    if defect == "leak":
        events = events + [_obs(_F2)]                    # 建立本章仍禁止的知识 → H5.7
    if defect == "no_obs":
        # 必需的观察事件整条没写出来 → H5.1 + 与之配对的 H5.3（must_change 失去实现事件）
        events = [e for e in events if e["event_type"] != "OBSERVES"]
    out: List[EventProposal] = []
    for i, e in enumerate(events):
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
        contract = contract_for(arc or build_arc(), ch, cur)
        rule, llm = _channels(ch, defects.get(ch))
        return ChapterArtifacts(contract=contract, scene_plan=plan_for(contract, cur),
                                draft=_draft(contract), rule_channel=rule, llm_channel=llm)
    return src


def make_config(chapters: int = 10) -> ExperimentConfig:
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    chars = dict(genesis.characters)
    chars[_DEAD_ACTOR] = Character(character_id=_DEAD_ACTOR, name="旧主", status="dead",
                                   death_chapter=1, introduced_at_chapter=1, epoch=EPOCH)
    facts = dict(genesis.facts)
    # 第 5 章起才允许对读者暗示（中段开闸）。夹具的事件流按阶梯走到它，
    # 加它只为让闸门到期这件事真的发生在十章里（04 §4.3 D5/D9）。
    facts[_F4] = Fact(fact_id=_F4, fact_type="existence", proposition="守阁的人碰过印泥",
                      canonical_form="存在=守阁的人碰过印泥",
                      narrative_truth="unknown", objective_truth="true",
                      defined_at_chapter=1, epoch=EPOCH)
    genesis = genesis.model_copy(update={"characters": chars, "facts": facts})
    return ExperimentConfig(story_id="s1", chapters=chapters, arc_contract=build_arc(chapters),
                            initial_state=genesis, seed=42, epoch=EPOCH)


def dummy_writer(scene, contract, state) -> str:
    return scene.scene_id
