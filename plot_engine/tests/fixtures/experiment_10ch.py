"""确定性 10 章实验 `chapter_source`（08 Day 20–22 测试夹具，网络无关）。

充当真实 Writer/抽取模型：逐章产出合法的 OBSERVES+INFERS（一致 → hybrid/1000），
可选注入 `defects` 把指定章改成 "leak"（建禁止知识 fact_000002）或 "dead"（死人出场），
以便驱动 `run_experiment` 观测 §4 硬指标分桶与 §8 退出条件。
"""
from __future__ import annotations

import json
from pathlib import Path

from plot_engine.models.contract import ArcContract, ChapterContract, ChapterHook, ReaderSignal
from plot_engine.models.entity import Character
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "traitor_arc.json").read_text(encoding="utf-8"))
_DRAFT = ("张三凝视印章。\n\n<!-- reader_learns: fact_000003 -->\n\n"
          "<!-- hook: cliffhanger strength=800 -->")


def plan_for(ch: int) -> ScenePlan:
    def beat(i):
        return Beat(beat_id=f"bt_{i:06d}", seq=i % 3, intent="x", beat_type="setup")
    scenes = [Scene(scene_id=f"scn_{ch:04d}_{n:02d}", chapter_no=ch, seq=n - 1,
                   location="loc_000012", characters=["char_000001"], purpose="p",
                   tension=500, beats=[beat(3 * n + k) for k in range(3)]) for n in (1, 2, 3)]
    return ScenePlan(plan_id=f"sop_{ch:08d}", chapter_no=ch, arc_id="arc_003",
                    contract_version=1, scenes=scenes, epoch=EPOCH,
                    created_at="2026-10-09T00:00:00Z")


def contract_for(ch: int) -> ChapterContract:
    return ChapterContract(
        chapter_no=ch, arc_id="arc_003", epoch=EPOCH, story_goal="g",
        story_goal_type="revelation",
        must_change=[{"character_id": "char_000001", "field": "knowledge", "operation": "add",
                      "target": "fact_000003", "expected_value": "known"},
                     {"character_id": "char_000001", "field": "knowledge", "operation": "add",
                      "target": "fact_000001", "expected_value": "suspected"}],
        must_not_change=[{"character_id": "char_000001", "field": "knowledge",
                          "operation": "update", "target": "fact_000002"}],
        required_events=[{"event_type": "OBSERVES", "description": "o"},
                         {"event_type": "INFERS", "description": "i"}],
        forbidden_events=[{"event_type": "REVEALS", "description": "r", "reason": "gate"}],
        knowledge_allowed=["fact_000001", "fact_000003"], knowledge_forbidden=["fact_000002"],
        reader_signals=[ReaderSignal(fact_id="fact_000003", target_state="knows")],
        tension_target=720,
        ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
        created_at="2026-10-09T00:00:00Z")


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


def build_source(defects: dict[int, str] | None = None):
    defects = defects or {}

    def src(ch: int, cur: StoryState) -> ChapterArtifacts:
        defect = defects.get(ch)
        actor = "char_000009" if defect == "dead" else "char_000001"
        observed = "fact_000002" if defect == "leak" else "fact_000003"
        rule, llm = _channels(ch, actor, observed)
        return ChapterArtifacts(contract=contract_for(ch), scene_plan=plan_for(ch),
                                draft=_DRAFT, rule_channel=rule, llm_channel=llm)
    return src


def make_config(chapters: int = 10) -> ExperimentConfig:
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    chars = dict(genesis.characters)
    chars["char_000009"] = Character(character_id="char_000009", name="旧主", status="dead",
                                     death_chapter=1, introduced_at_chapter=1, epoch=EPOCH)
    genesis = genesis.model_copy(update={"characters": chars})
    arc = ArcContract(arc_id="arc_003", epoch=EPOCH, chapter_range=(1, 30),
                      turning_points=[{"chapter": 1, "type": "revelation", "description": "d",
                                       "required_event_types": ["OBSERVES"]}],
                      knowledge_gates=[], created_at="2026-10-09T00:00:00Z")
    return ExperimentConfig(story_id="s1", chapters=chapters, arc_contract=arc,
                            initial_state=genesis, seed=42, epoch=EPOCH)


def dummy_writer(scene, contract, state) -> str:
    return scene.scene_id
