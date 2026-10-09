# SP1~SP7 ScenePlan 自校验 + 对称可达（04 附录 B §8.3）
from plot_engine.models.contract import ChapterContract
from plot_engine.models.entity import Character, Location
from plot_engine.models.fact import Fact
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.sceneplan import _reachable, validate_scene_plan

EPOCH = "epoch_0"


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={
            "char_000001": Character(character_id="char_000001", name="张三",
                status="alive", current_location="loc_000011",
                introduced_at_chapter=1, epoch=EPOCH),
            "char_000002": Character(character_id="char_000002", name="李四",
                status="alive", current_location="loc_000012",
                introduced_at_chapter=1, epoch=EPOCH)},
        locations={
            "loc_000011": Location(location_id="loc_000011", name="A",
                connected_to=["loc_000012"], introduced_at_chapter=1, epoch=EPOCH),
            # 12 未显式写 11：W-S1 对称 → 从 12 仍应可达 11
            "loc_000012": Location(location_id="loc_000012", name="B",
                connected_to=[], introduced_at_chapter=1, epoch=EPOCH),
            "loc_000099": Location(location_id="loc_000099", name="孤岛",
                connected_to=[], introduced_at_chapter=1, epoch=EPOCH)},
        items={}, realms={}, abilities={},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
                defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000003")},
        state_hash="0" * 64)


def _contract(**over):
    base = dict(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="查明叛徒",
        story_goal_type="revelation",
        required_events=[{"event_type": "OBSERVES", "description": "观察"},
                         {"event_type": "INFERS", "description": "推断"}],
        forbidden_events=[{"event_type": "REVEALS", "description": "揭示", "reason": "gate"}],
        reader_signals=[{"fact_id": "fact_000003", "target_state": "knows"}],
        tension_target=700,
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-09T00:00:00Z")
    return ChapterContract(**{**base, **over})


def _beat(n, *, loc="loc_000011", action=None, events=("OBSERVES", "INFERS"),
          reader_target="learns", reader_fact="fact_000003", actors=("char_000001",)):
    return Beat(beat_id=f"bt_{n:06d}", seq=n, intent="i", beat_type="turn",
                action_type=action, actors=list(actors), location=loc,
                expected_event_types=list(events),
                reader_target=reader_target, reader_fact_id=reader_fact)


def _scene(n, beats=None):
    beats = beats or [_beat(n * 10 + 1), _beat(n * 10 + 2), _beat(n * 10 + 3)]
    return Scene(scene_id=f"scn_0047_{n:02d}", chapter_no=47, seq=n - 1,
                 location="loc_000011", characters=["char_000001"], tension=700, beats=beats)


def _plan(scenes=None):
    scenes = scenes or [_scene(1), _scene(2), _scene(3)]
    return ScenePlan(plan_id="sop_00000047", chapter_no=47, arc_id="arc_003",
                     contract_version=1, scenes=scenes, epoch=EPOCH,
                     created_at="2026-10-09T00:00:00Z")


def _hard(res):
    return {f.rule_id for f in res.hard_violations}


def test_reachable_symmetric_and_self():
    st = _state()
    assert _reachable(st, "loc_000011", "loc_000011") is True    # 路径长 0
    assert _reachable(st, "loc_000012", "loc_000011") is True    # W-S1 反向边
    assert _reachable(st, "loc_000011", "loc_000099") is False   # 孤岛不可达
    assert _reachable(st, None, "loc_000011") is False


def test_clean_plan_no_hard():
    res = validate_scene_plan(_plan(), _contract(), _state())
    assert res.can_commit() and res.hard_violations == []


def test_sp1_bad_char_and_bad_fact():
    scenes = [_scene(1, beats=[_beat(11, actors=("char_999999",)),
                               _beat(12, reader_fact="fact_888888"), _beat(13)])]
    scenes += [_scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP1" in _hard(res)


def test_sp2_missing_required_event_type():
    scenes = [_scene(n, beats=[_beat(n * 10 + i, events=("OBSERVES",)) for i in (1, 2, 3)])
              for n in (1, 2, 3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP2" in _hard(res)


def test_sp3_forbidden_event_declared():
    scenes = [_scene(1, beats=[_beat(11, events=("REVEALS",)), _beat(12), _beat(13)]),
              _scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP3" in _hard(res)


def test_sp4_uncovered_reader_signal():
    scenes = [_scene(n, beats=[_beat(n * 10 + i, reader_target=None, reader_fact=None)
                               for i in (1, 2, 3)]) for n in (1, 2, 3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP4" in _hard(res)


def test_sp5_unreachable_location():
    scenes = [_scene(1, beats=[_beat(11, loc="loc_000099"), _beat(12), _beat(13)]),
              _scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP5" in _hard(res)


def test_sp5_travel_exempt():
    scenes = [_scene(1, beats=[_beat(11, loc="loc_000099", action="travel"),
                               _beat(12), _beat(13)]), _scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP5" not in _hard(res)


def test_sp5_reverse_edge_reachable():
    # char_000002 在 loc_000012，beat.location loc_000011：仅靠对称边可达
    scenes = [_scene(1, beats=[_beat(11, loc="loc_000011", actors=("char_000002",)),
                               _beat(12), _beat(13)]), _scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP5" not in _hard(res)


def test_sp6_duplicate_beat_id():
    dup = _beat(11)
    scenes = [_scene(1, beats=[dup, _beat(12), _beat(13)]),
              _scene(2, beats=[_beat(21), _beat(22), dup]), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP6" in _hard(res)


def test_sp7_tension_deviation_is_soft():
    scenes = [_scene(1, beats=[_beat(11), _beat(12), _beat(13)])]
    scenes[0] = scenes[0].model_copy(update={"tension": 100})
    scenes += [_scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP7" not in _hard(res)
    assert any(f.rule_id == "SP7" for f in res.soft_warnings)
