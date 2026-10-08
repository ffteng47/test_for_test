import json

import pytest
from pydantic import ValidationError

from plot_engine.models.contract import (
    ArcContract,
    ChapterContract,
    CharacterChange,
)

GOLDEN = {
    "chapter_no": 47,
    "arc_id": "arc_003",
    "epoch": "epoch_0",
    "version": 1,
    "story_goal": "张三在宗门大殿发现伪造印章，推断宗门内部存在叛徒，但无法确定身份",
    "story_goal_type": "revelation",
    "must_change": [
        {"character_id": "char_000001", "field": "knowledge", "operation": "add",
         "target": "fact_000003", "expected_value": "known"},
        {"character_id": "char_000001", "field": "knowledge", "operation": "add",
         "target": "fact_000001", "expected_value": "suspected"},
    ],
    "must_not_change": [
        {"character_id": "char_000001", "field": "knowledge", "operation": "update",
         "target": "fact_000002"},
    ],
    "required_events": [
        {"event_type": "OBSERVES", "description": "张三观察到伪造印章",
         "minimum_count": 1, "actors_involved": ["char_000001"],
         "must_be_visible_to_reader": True},
        {"event_type": "INFERS", "description": "张三推断宗门存在叛徒",
         "minimum_count": 1, "actors_involved": ["char_000001"],
         "must_be_visible_to_reader": True},
    ],
    "forbidden_events": [
        {"event_type": "REVEALS", "description": "揭示叛徒身份",
         "reason": "arc_003.knowledge_gates[fact_000002].allowed_after_chapter = 84"},
    ],
    "knowledge_allowed": ["fact_000001", "fact_000003"],
    "knowledge_forbidden": ["fact_000002"],
    "reader_signals": [
        {"fact_id": "fact_000003", "target_state": "knows",
         "established_in_scene": "scn_0047_01"},
    ],
    "plot_progress": {"main_thread": 80},
    "tension_target": 720,
    "ending": {"type": "cliffhanger", "strength": 800,
               "description": "张三凝视印章，意识到叛徒可能就在身边"},
    "derived_from": ["arc_003.knowledge_gates[fact_000002]", "arc_003.turning_points[47]"],
    "created_at": "2026-10-08T10:00:00Z",
    "schema_version": 2,
}


def _arc():
    return ArcContract(
        arc_id="arc_003", epoch="epoch_0", chapter_range=(40, 60),
        tension_curve=[500] * 21,
        turning_points=[{"chapter": 47, "type": "revelation",
                         "description": "印章为伪", "required_event_types": ["OBSERVES", "INFERS"]}],
        knowledge_gates=[{"fact_id": "fact_000002", "allowed_characters": [],
                          "allowed_after_chapter": 84, "reveal_stage_target": "confirmed"}],
        created_at="2026-10-08T09:00:00Z")


def test_golden_chapter_contract_roundtrip():
    c = ChapterContract(**GOLDEN)
    assert c.ending.type == "cliffhanger" and c.tension_target == 720
    assert c.model_dump(mode="json")["must_change"][0]["expected_value"] == "known"
    again = ChapterContract(**json.loads(json.dumps(GOLDEN)))
    assert again == c


def test_bad_arc_id_rejected():
    with pytest.raises(ValidationError):
        ArcContract(arc_id="arc_1", epoch="epoch_0", chapter_range=(1, 5),
                    turning_points=[], knowledge_gates=[], created_at="t")


def test_hook_strength_bounds():
    with pytest.raises(ValidationError):
        ChapterContract(**{**GOLDEN, "ending": {**GOLDEN["ending"], "strength": 1001}})


def test_change_field_enum():
    with pytest.raises(ValidationError):
        CharacterChange(character_id="char_000001", field="bogus",
                        operation="add", target="fact_000001")


def test_arc_tension_curve_length():
    a = _arc()
    assert len(a.tension_curve) == a.chapter_range[1] - a.chapter_range[0] + 1


def test_reader_signal_target_enum():
    with pytest.raises(ValidationError):
        ChapterContract(**{**GOLDEN, "reader_signals": [
            {"fact_id": "fact_000003", "target_state": "confused"}]})
