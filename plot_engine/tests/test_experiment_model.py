# Experiment 配置/报告模型 + 硬指标映射（08 §2/§3/§4）
import dataclasses

from plot_engine.models.contract import ArcContract
from plot_engine.models.experiment import (
    ChapterArtifacts, ExperimentConfig, ExperimentReport, HardMetric, RULE_TO_METRIC,
)
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"


def _arc() -> ArcContract:
    return ArcContract(arc_id="arc_003", epoch=EPOCH, chapter_range=(1, 10),
                       turning_points=[{"chapter": 3, "type": "revelation",
                                        "description": "d", "required_event_types": ["OBSERVES"]}],
                       knowledge_gates=[{"fact_id": "fact_000002",
                                         "allowed_after_chapter": 84,
                                         "reveal_stage_target": "confirmed"}],
                       created_at="2026-10-09T00:00:00Z")


def _state() -> StoryState:
    return StoryState(story_id="s1", chapter_no=0, version=0, epoch=EPOCH,
                      characters={}, locations={}, items={}, realms={}, abilities={},
                      facts={}, state_hash="0" * 64)


def test_config_defaults():
    cfg = ExperimentConfig(story_id="s1", arc_contract=_arc(), initial_state=_state(),
                           seed=42, epoch=EPOCH)
    assert cfg.chapters == 10
    assert cfg.model_router_config == {}
    assert cfg.seed == 42


def test_report_fields_present():
    rep = ExperimentReport(experiment_id="exp1",
                           config=ExperimentConfig(story_id="s1", arc_contract=_arc(),
                                                   initial_state=_state(), seed=1, epoch=EPOCH),
                           chapters_generated=0, chapters_committed=0)
    assert rep.hard_violations == {} and rep.soft_warnings == {} and rep.observations == {}
    assert rep.canon_contradictions == 0 and rep.knowledge_contradictions == 0
    assert rep.timeline_contradictions == 0
    assert rep.replay_consistency is True and rep.replay_mismatch_chapters == []
    assert rep.revision_rounds == {} and rep.revision_success_rate == 0.0
    assert rep.unresolved_chapters == []
    assert rep.total_tokens == 0 and rep.total_cost_usd == 0 and rep.total_duration_ms == 0


def test_chapter_artifacts_is_dataclass_with_defaults():
    assert dataclasses.is_dataclass(ChapterArtifacts)
    from plot_engine.models.contract import ChapterContract, ChapterHook
    contract = ChapterContract(chapter_no=1, arc_id="arc_003", epoch=EPOCH, story_goal="g",
                               story_goal_type="setup",
                               ending=ChapterHook(type="question", strength=500, description="d"),
                               created_at="2026-10-09T00:00:00Z")
    art = ChapterArtifacts(contract=contract)
    assert art.scene_plan is None and art.draft == ""
    assert art.rule_channel is None and art.llm_channel is None


def test_every_hard_metric_bucket_has_rule_ids():
    mapped = set(RULE_TO_METRIC.values())
    for metric in HardMetric:
        assert metric in mapped, f"{metric.name} 无 rule_id 映射"
        # REPLAY 例外：由 status 而非 rule_id 命中，但仍需有代表来源
    assert RULE_TO_METRIC["H1.1"] is HardMetric.DEAD_REAPPEAR
    assert RULE_TO_METRIC["H5.1"] is HardMetric.REQUIRED_EVENT_MISSING
    assert RULE_TO_METRIC["H5.7"] is HardMetric.FORBIDDEN_LEAK
    assert RULE_TO_METRIC["H3.3"] is HardMetric.TIMELINE
    assert RULE_TO_METRIC["H4.1"] is HardMetric.ITEM_UNAVAILABLE
    assert RULE_TO_METRIC["H1.4"] is HardMetric.IMPOSSIBLE_ACTION
