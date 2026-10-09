"""确定性 10 章实验 `chapter_source`（08 Day 20–22 测试夹具，网络无关）。

**契约与场景不再手写**：这里是 `docs/phase0-live-run-10ch.md` backlog #1 的修复处——
一份**有内容的 ArcContract**（逐章张力、三个 turning point、四个知识闸门（含一个中段开闸）、
十章逐章意图），Chapter Contract 与 ScenePlan 由 `plot_engine.derive` 按 04 §4.3 / 附录 B 派生。
于是每一章的约束真的不一样，10 章实验才开始测试「跨章推进」而不是一条约束重复十遍。

夹具 Writer/抽取仍充当真实模型：逐章产出合法的 OBSERVES+INFERS（一致 → hybrid/1000），
可选注入 `defects` 把指定章改成 "leak"（建禁止知识 fact_000002）或 "dead"（死人出场）。
turning_point 只用 {OBSERVES, INFERS}、闸门不给 reveal 限期：夹具 Writer 是确定性的，
要求它写不出的东西只会让离线演练一路 FAIL，那就变成在测夹具而不是测管道。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

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
_CAST = ["char_000001"]
# H5.5 把章尾 hook 与 contract.ending.type 对齐，而夹具 Draft 写死 cliffhanger
# → 逐章意图只能在兼容 cliffhanger 的目标类型里变（04 §4.4）。
_GOAL_TYPES = ["revelation", "escalation", "confrontation"]
_DRAFT = ("第{ch}章：张三凝视印章。\n\n<!-- reader_learns: fact_000003 -->\n\n"
          "<!-- hook: cliffhanger strength=800 -->")
_FIX = json.loads((Path(__file__).parent / "traitor_arc.json").read_text(encoding="utf-8"))


def build_arc(chapters: int = 10) -> ArcContract:
    """逐章意图 + 张力曲线 + turning_points + knowledge_gates：契约的合法来源（04 C2）。"""
    goals = ["张三在藏宝阁验出印章是伪造的。", "伪造印章把矛头指向宗门内部。",
             "有人不想让张三继续查下去。", "张三第一次怀疑身边人的说法。",
             "线索断在一句对不上的供词上。", "张三被迫在真相与立场之间选边。",
             "印泥的来源指向守阁的人。", "一次回避比一句谎话更像回答。",
             "张三把三件小事串成同一条线。", "结论逼近，但说出来的代价开始显现。"]
    intents = [{"chapter_no": ch,
                "story_goal": goals[(ch - 1) % len(goals)],
                "story_goal_type": _GOAL_TYPES[ch % len(_GOAL_TYPES)],
                "ending": {"type": "cliffhanger",
                           "strength": 500 + 100 * (ch % 5), "description": "章尾悬念"},
                "must_change": [
                    {"character_id": "char_000001", "field": "knowledge", "operation": "add",
                     "target": "fact_000003", "expected_value": "known"},
                    {"character_id": "char_000001", "field": "knowledge", "operation": "add",
                     "target": "fact_000001", "expected_value": "suspected"}],
                "must_not_change": [{"character_id": "char_000001", "field": "knowledge",
                                     "operation": "update", "target": "fact_000002"}]}
               for ch in range(1, chapters + 1)]
    mid, late = max(2, chapters // 2), max(3, chapters - 1)
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(1, chapters),
        tension_curve=[min(1000, 300 + 60 * ch) for ch in range(1, chapters + 1)],
        turning_points=[
            {"chapter": 1, "type": "revelation", "description": "印章是伪造的",
             "required_event_types": ["OBSERVES"]},
            {"chapter": mid, "type": "escalation", "description": "矛头指向内部",
             "required_event_types": ["INFERS"]},
            {"chapter": late, "type": "crisis", "description": "串成一条线",
             "required_event_types": ["OBSERVES", "INFERS"]}],
        # hidden = 本章不给读者建立该事实 → 不产生 reader_signal（04 §4.3 D9）
        knowledge_gates=[
            {"fact_id": "fact_000001", "allowed_after_chapter": 1,
             "reveal_stage_target": "hidden"},
            {"fact_id": "fact_000003", "allowed_after_chapter": 1,
             "reveal_stage_target": "confirmed"},
            # 中段开闸：第 chapters//2 章起才允许向读者暗示，于是前半程 forbidden、
            # 后半程 hinted 信号 —— 契约逐章真的不一样（Review Focus #4）。
            # 夹具 Writer/抽取从不引用它，所以这条闸门只加约束、不改既有判定。
            {"fact_id": "fact_000004", "allowed_after_chapter": max(1, chapters // 2),
             "reveal_stage_target": "hinted"},
            {"fact_id": "fact_000002", "allowed_after_chapter": chapters,
             "reveal_stage_target": "hidden"}],
        reader_beats=intents, created_at=NOW)


def contract_for(arc: ArcContract, ch: int, state: StoryState) -> ChapterContract:
    return derive_chapter_contract(arc, ch, state, created_at=NOW)


def plan_for(contract: ChapterContract, state: StoryState) -> ScenePlan:
    return derive_scene_plan(contract, state, created_at=NOW)


def _channels(ch: int, actor: str = "char_000001", observed_fact: str = "fact_000003"):
    def rule(*_a):
        return [
            EventProposal(proposed_event_type="OBSERVES", actor=actor, target=observed_fact,
                          chapter=ch, seq=0, preconditions=[],
                          payload={"fact_id": observed_fact, "method": "sight"},
                          confidence=1000, source_ref="para:4", extraction_method="rule",
                          extraction_confidence=1000),
            EventProposal(proposed_event_type="INFERS", actor=actor, target="fact_000001",
                          chapter=ch, seq=1, preconditions=[f"evt_{ch:08d}_000"],
                          payload={"conclusion_fact_id": "fact_000001",
                                   "evidence_fact_ids": [observed_fact]},
                          confidence=700, source_ref="para:6", extraction_method="rule",
                          extraction_confidence=1000)]

    def llm(*_a):
        return [p.model_copy(update={"extraction_method": "llm"}) for p in rule()]
    return rule, llm


def build_source(defects: Optional[Dict[int, str]] = None,
                 arc: Optional[ArcContract] = None):
    defects = defects or {}

    def src(ch: int, cur: StoryState) -> ChapterArtifacts:
        defect = defects.get(ch)
        actor = "char_000009" if defect == "dead" else "char_000001"
        observed = "fact_000002" if defect == "leak" else "fact_000003"
        rule, llm = _channels(ch, actor, observed)
        contract = contract_for(arc or build_arc(), ch, cur)
        return ChapterArtifacts(contract=contract, scene_plan=plan_for(contract, cur),
                                draft=_DRAFT.format(ch=ch), rule_channel=rule, llm_channel=llm)
    return src


def make_config(chapters: int = 10) -> ExperimentConfig:
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    chars = dict(genesis.characters)
    chars["char_000009"] = Character(character_id="char_000009", name="旧主", status="dead",
                                     death_chapter=1, introduced_at_chapter=1, epoch=EPOCH)
    facts = dict(genesis.facts)
    # 只在 Arc 的中段闸门之后才允许对读者暗示；夹具的事件流从不引用它，加它只为让闸门到期
    # 这件事真的发生在十章里（04 §4.3 D5/D9）。
    facts["fact_000004"] = Fact(fact_id="fact_000004", fact_type="existence",
                                proposition="守阁的人碰过印泥",
                                canonical_form="存在=守阁的人碰过印泥",
                                narrative_truth="unknown", objective_truth="true",
                                defined_at_chapter=1, epoch=EPOCH)
    genesis = genesis.model_copy(update={"characters": chars, "facts": facts})
    return ExperimentConfig(story_id="s1", chapters=chapters, arc_contract=build_arc(chapters),
                            initial_state=genesis, seed=42, epoch=EPOCH)


def dummy_writer(scene, contract, state) -> str:
    return scene.scene_id
