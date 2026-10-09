# 金标 ScenePlan e2e + SP 命中 + Commit 回归（04 附录 B, 07 §4.1）
import json
from pathlib import Path

from plot_engine.commit import CommitOrchestrator
from plot_engine.eventlog import EventLog
from plot_engine.models.commit import CommitRequest
from plot_engine.models.contract import ChapterContract
from plot_engine.models.entity import Character, Location
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.sceneplan import validate_scene_plan
from plot_engine.store import StateStore

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", current_location="loc_000011",
            introduced_at_chapter=1, epoch=EPOCH)},
        locations={"loc_000011": Location(location_id="loc_000011", name="藏宝阁",
            connected_to=[], introduced_at_chapter=1, epoch=EPOCH)},
        items={}, realms={}, abilities={},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
                defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000003")},
        state_hash="0" * 64)


def _contract():
    return ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="张三发现伪造印章",
        story_goal_type="revelation",
        required_events=[{"event_type": "OBSERVES", "description": "观察"},
                         {"event_type": "INFERS", "description": "推断"}],
        forbidden_events=[{"event_type": "REVEALS", "description": "揭示", "reason": "gate"}],
        reader_signals=[{"fact_id": "fact_000003", "target_state": "knows"}],
        tension_target=720,
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-09T00:00:00Z")


def _beat(n, *, events=("OBSERVES", "INFERS"), reader_target="learns",
          reader_fact="fact_000003"):
    return Beat(beat_id=f"bt_{n:06d}", seq=n, intent="i", beat_type="turn",
                actors=["char_000001"], location="loc_000011",
                expected_event_types=list(events),
                reader_target=reader_target, reader_fact_id=reader_fact)


def _scene(n, beats=None):
    beats = beats or [_beat(n * 10 + i) for i in (1, 2, 3)]
    return Scene(scene_id=f"scn_0047_{n:02d}", chapter_no=47, seq=n - 1,
                 location="loc_000011", characters=["char_000001"], tension=720, beats=beats)


def _plan(scenes=None):
    scenes = scenes or [_scene(i) for i in (1, 2, 3)]
    return ScenePlan(plan_id="sop_00000047", chapter_no=47, arc_id="arc_003",
                     contract_version=1, scenes=scenes, epoch=EPOCH,
                     created_at="2026-10-09T00:00:00Z")


def test_golden_scene_plan_passes_sp():
    res = validate_scene_plan(_plan(), _contract(), _state())
    assert res.hard_violations == []
    assert res.can_commit()


def test_inject_sp3_forbidden_event():
    scenes = [_scene(1, beats=[_beat(11, events=("REVEALS",)), _beat(12), _beat(13)]),
              _scene(2), _scene(3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert {f.rule_id for f in res.hard_violations} == {"SP3"}


def test_inject_sp4_uncovered_signal():
    scenes = [_scene(n, beats=[_beat(n * 10 + i, reader_target=None, reader_fact=None)
                               for i in (1, 2, 3)]) for n in (1, 2, 3)]
    res = validate_scene_plan(_plan(scenes), _contract(), _state())
    assert "SP4" in {f.rule_id for f in res.hard_violations}


def test_commit_request_accepts_scene_plan_and_none():
    req = CommitRequest(story_id="s1", chapter_no=47, draft="正文", contract=_contract(),
                        scene_plan=_plan(), expected_version=0, trace_id="t")
    assert req.scene_plan is not None and req.scene_plan.plan_id == "sop_00000047"
    req2 = CommitRequest(story_id="s1", chapter_no=47, draft="正文", contract=_contract(),
                         expected_version=0, trace_id="t")
    assert req2.scene_plan is None


def test_commit_orchestrator_still_ok_with_scene_plan(tmp_path):
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    store.init_genesis("s1", genesis)
    orch = CommitOrchestrator(store, log, Reducer())

    method = {"OBSERVES": "rule", "INFERS": "llm", "READER_LEARNS": "markup"}
    props = []
    for ev in _FIX["chapter47_events"]:
        seq = int(ev["event_id"].split("_")[-1])
        props.append(EventProposal(
            proposed_event_type=ev["event_type"], actor=ev.get("actor"),
            target=ev.get("target"), chapter=ev["chapter"], seq=seq,
            preconditions=list(ev.get("preconditions", [])), payload=dict(ev["payload"]),
            confidence=ev["confidence"], source_ref=ev["source_ref"],
            extraction_method=method[ev["event_type"]], extraction_confidence=1000))
    req = CommitRequest(story_id="s1", chapter_no=47,
                        draft="张三凝视印章。\n\n<!-- reader_learns: fact_000003 -->\n\n"
                              "<!-- hook: cliffhanger strength=800 -->",
                        contract=_contract(), scene_plan=_plan(),
                        expected_version=0, trace_id="t-47")
    arc = store.load_latest("s1").state
    out = orch.commit(req, props, arc, committed_event_ids=frozenset({"evt_00000047_001"}))
    assert out.status == "OK" and out.new_version == 1
