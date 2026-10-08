# CommitOrchestrator 四阶段 e2e（07 §5–§9, 附录 A 金标）
import json
from pathlib import Path

from plot_engine.commit import CommitOrchestrator
from plot_engine.eventlog import EventLog
from plot_engine.models.commit import CommitRequest
from plot_engine.models.contract import ChapterContract
from plot_engine.models.entity import Character
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))

_METHOD = {"OBSERVES": "rule", "INFERS": "llm", "READER_LEARNS": "markup"}
_DRAFT = ("张三凝视那枚印章，纹路对不上。\n\n"
          "<!-- reader_learns: fact_000003 -->\n\n"
          "<!-- hook: cliffhanger strength=800 -->")


def _genesis_state():
    return StoryState(**{**_FIX["genesis"], "state_hash": ""})


def _proposals():
    out = []
    for ev in _FIX["chapter47_events"]:
        seq = int(ev["event_id"].split("_")[-1])
        out.append(EventProposal(
            proposed_event_type=ev["event_type"], actor=ev.get("actor"),
            target=ev.get("target"), chapter=ev["chapter"], seq=seq,
            preconditions=list(ev.get("preconditions", [])), payload=dict(ev["payload"]),
            confidence=ev["confidence"], source_ref=ev["source_ref"],
            extraction_method=_METHOD[ev["event_type"]], extraction_confidence=1000))
    return out


def _contract():
    return ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="张三发现伪造印章",
        story_goal_type="revelation",
        must_change=[
            {"character_id": "char_000001", "field": "knowledge", "operation": "add",
             "target": "fact_000003", "expected_value": "known"},
            {"character_id": "char_000001", "field": "knowledge", "operation": "add",
             "target": "fact_000001", "expected_value": "suspected"}],
        must_not_change=[{"character_id": "char_000001", "field": "knowledge",
             "operation": "update", "target": "fact_000002"}],
        required_events=[{"event_type": "OBSERVES", "description": "观察"},
                         {"event_type": "INFERS", "description": "推断"}],
        forbidden_events=[{"event_type": "REVEALS", "description": "揭示", "reason": "gate"}],
        knowledge_allowed=["fact_000001", "fact_000003"], knowledge_forbidden=["fact_000002"],
        reader_signals=[{"fact_id": "fact_000003", "target_state": "knows"}],
        plot_progress={"main_thread": 80}, tension_target=720,
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-08T10:00:00Z")


def _request(expected_version=0):
    return CommitRequest(story_id="s1", chapter_no=47, draft=_DRAFT, contract=_contract(),
                         expected_version=expected_version, trace_id="t-47")


def _stack(tmp_path):
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis("s1", _genesis_state())
    return store, log, CommitOrchestrator(store, log, Reducer())


def test_happy_path_ok_and_parity(tmp_path):
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state
    out = orch.commit(_request(), _proposals(), arc)
    assert out.status == "OK"
    assert out.new_version == 1
    assert out.trace.result == "OK" and out.trace.version_after == 1
    assert store.load_latest("s1").version == 1
    from plot_engine.replay import verify_parity
    assert verify_parity(store, log, Reducer(), "s1", 47) is True


def test_duplicate_idempotent(tmp_path):
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state
    first = orch.commit(_request(0), _proposals(), arc)
    assert first.status == "OK"
    arc2 = store.load_latest("s1").state
    second = orch.commit(_request(1), _proposals(), arc2)
    assert second.status == "DUPLICATE"
    assert second.new_version == 1
    assert store.load_latest("s1").version == 1


def test_conflict_does_not_write(tmp_path):
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state
    out = orch.commit(_request(expected_version=99), _proposals(), arc)
    assert out.status == "CONFLICT"
    assert out.current_version == 0
    assert store.load_latest("s1").version == 0
    assert log.read_chapter("s1", 47) == []


def test_dead_actor_fail_no_side_effects(tmp_path):
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state
    arc = arc.model_copy(update={"characters": {
        "char_000001": Character(character_id="char_000001", name="张三", status="dead",
            death_chapter=10, current_location="loc_000012",
            introduced_at_chapter=1, epoch=EPOCH)}})
    out = orch.commit(_request(), _proposals(), arc)
    assert out.status == "FAIL"
    assert any(f.rule_id == "H1.1" for f in out.validation.hard_violations)
    assert store.load_latest("s1").version == 0        # 未写新 version
    assert log.read_chapter("s1", 47) == []            # 未写事件（无副作用）


def test_idempotency_key_from_applied_events_order_independent(tmp_path):
    # 同 applied 事件、不同抽取入批顺序 → 同 proposal_set_hash → 第二次 DUPLICATE
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state
    props = _proposals()
    first = orch.commit(_request(0), props, arc)
    assert first.status == "OK"
    arc2 = store.load_latest("s1").state
    reversed_props = list(reversed(props))
    second = orch.commit(_request(1), reversed_props, arc2)
    assert second.status == "DUPLICATE"
