# Scene/Beat/ScenePlan schema（04 附录 B §8.2）
import pytest
from pydantic import ValidationError

from plot_engine.models.sceneplan import Beat, Scene, ScenePlan

EPOCH = "epoch_0"


def _beat(n=1, **over):
    d = dict(beat_id=f"bt_{n:06d}", seq=n, intent="意图", beat_type="setup",
             actors=["char_000001"], location="loc_000012",
             expected_event_types=["OBSERVES"], reader_target="learns",
             reader_fact_id="fact_000003")
    return Beat(**{**d, **over})


def _scene(n=1, nbeats=3, **over):
    beats = [_beat(n * 10 + i) for i in range(1, nbeats + 1)]
    d = dict(scene_id=f"scn_0047_{n:02d}", chapter_no=47, seq=n - 1,
             location="loc_000012", characters=["char_000001"], purpose="p",
             tension=700, beats=beats)
    return Scene(**{**d, **over})


def _plan(nscenes=3, **over):
    scenes = [_scene(i) for i in range(1, nscenes + 1)]
    d = dict(plan_id="sop_00000047", chapter_no=47, arc_id="arc_003",
             contract_version=1, scenes=scenes, epoch=EPOCH,
             created_at="2026-10-09T00:00:00Z")
    return ScenePlan(**{**d, **over})


def test_valid_minimal_plan_constructs():
    plan = _plan()
    assert len(plan.scenes) == 3
    assert plan.scenes[0].beats[0].beat_type == "setup"
    assert plan.schema_version == 2


def test_bad_beat_id_pattern():
    with pytest.raises(ValidationError):
        _beat(beat_id="bt_1")


def test_bad_scene_id_pattern():
    with pytest.raises(ValidationError):
        _scene(scene_id="scn_47_1")


def test_bad_plan_id_pattern():
    with pytest.raises(ValidationError):
        _plan(plan_id="sop_47")


def test_scene_beats_length_bounds():
    with pytest.raises(ValidationError):
        _scene(nbeats=2)
    with pytest.raises(ValidationError):
        _scene(nbeats=8)


def test_plan_scenes_length_bounds():
    with pytest.raises(ValidationError):
        _plan(nscenes=2)
    with pytest.raises(ValidationError):
        _plan(nscenes=8)


def test_scene_seq_and_tension_bounds():
    with pytest.raises(ValidationError):
        _scene(seq=7)
    with pytest.raises(ValidationError):
        _scene(tension=1001)


def test_beat_type_and_action_enums():
    with pytest.raises(ValidationError):
        _beat(beat_type="bogus")
    with pytest.raises(ValidationError):
        _beat(action_type="fly")
    assert _beat(action_type="travel").action_type == "travel"
