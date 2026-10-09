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


def test_fail_message_names_the_actual_reject_reason(tmp_path):
    """线上实测教训：`"not committable (hard violations or empty batch)"` 一句话说两种拒绝，
    8 章 FAIL 之后无从归因，白烧一轮 GPU。原因必须写进 outcome，而不是留给读代码的人猜。"""
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state

    empty = orch.commit(_request(), [], arc)
    assert empty.status == "FAIL"
    assert " or " not in empty.message                      # 不再给「二选一」的含糊话
    assert "HARD=" in empty.message or "empty batch" in empty.message

    dead_arc = arc.model_copy(update={"characters": {
        "char_000001": Character(character_id="char_000001", name="张三", status="dead",
                                 death_chapter=10, current_location="loc_000012",
                                 introduced_at_chapter=1, epoch=EPOCH)}})
    hard = orch.commit(_request(), _proposals(), dead_arc)
    assert hard.status == "FAIL" and "HARD=" in hard.message

def _bare_contract():
    """把契约里所有「本章必须发生点什么」的字段清空：这样空批就是唯一的拒绝原因。"""
    return _contract().model_copy(update={"required_events": [], "must_change": [],
                                          "must_not_change": [], "reader_signals": []})


def test_empty_batch_alone_is_the_reject_reason(tmp_path):
    """backlog #5：`stage0_extract` 会从 markup 通道补 READER_* 事件，线上至今没出现过
    纯空批，所以 `empty batch` 这一支一直只有代码在保护、没有测试钉住。这里绕过抽取直接
    交 0 条 proposal：唯一原因必须是 empty batch，且绝不能顺便推进 version。"""
    store, log, orch = _stack(tmp_path)
    arc = store.load_latest("s1").state
    req = CommitRequest(story_id="s1", chapter_no=47,
                        draft="<!-- hook: cliffhanger strength=800 -->",
                        contract=_bare_contract(), expected_version=0, trace_id="t-empty")
    out = orch.commit(req, [], arc)
    assert out.validation.can_commit() is True            # 不是契约问题：HARD 为空
    assert out.status == "FAIL" and "empty batch" in out.message
    assert "HARD=" not in out.message and " or " not in out.message
    assert store.load_latest("s1").version == 0           # 无副作用（07 §5.3 R1）
    assert log.read_chapter("s1", 47) == []

