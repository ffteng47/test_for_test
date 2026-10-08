# reduce_commit：单一 reduce 驱动 + 一致性闸（07 §6，Review Focus #1/#5）
import json
from pathlib import Path

from plot_engine.models.contract import ChapterContract
from plot_engine.models.entity import Character, Location
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal, to_event
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.reduce import reduce_commit
from plot_engine.replay import apply_events

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", current_location="loc_000012",
            introduced_at_chapter=1, epoch=EPOCH)},
        locations={"loc_000012": Location(location_id="loc_000012", name="藏宝阁",
            introduced_at_chapter=1, epoch=EPOCH)},
        items={}, realms={}, abilities={},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
                defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000002", "fact_000003")},
        state_hash="0" * 64)


def _contract():
    return ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="张三发现伪造印章",
        story_goal_type="revelation",
        must_change=[
            {"character_id": "char_000001", "field": "knowledge", "operation": "add",
             "target": "fact_000003", "expected_value": "known"}],
        required_events=[{"event_type": "OBSERVES", "description": "观察"}],
        knowledge_allowed=["fact_000003"], knowledge_forbidden=[],
        plot_progress={"main_thread": 80}, tension_target=720,
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-08T10:00:00Z")


def _proposals():
    method = {"OBSERVES": "rule", "INFERS": "llm", "READER_LEARNS": "markup"}
    out = []
    for ev in _FIX["chapter47_events"]:
        seq = int(ev["event_id"].split("_")[-1])
        out.append(EventProposal(
            proposed_event_type=ev["event_type"], actor=ev.get("actor"),
            target=ev.get("target"), chapter=ev["chapter"], seq=seq,
            preconditions=list(ev.get("preconditions", [])), payload=dict(ev["payload"]),
            confidence=ev["confidence"], source_ref=ev["source_ref"],
            extraction_method=method[ev["event_type"]], extraction_confidence=1000))
    return out


_DRAFT = ("张三凝视那枚印章，纹路对不上。\n\n"
          "<!-- reader_learns: fact_000003 -->\n\n"
          "<!-- hook: cliffhanger strength=800 -->")


def test_clean_batch_committable():
    rb = reduce_commit(_state(), _proposals(), _contract(), _DRAFT, EPOCH,
                       committed_event_ids=frozenset({"evt_00000047_001"}))
    assert rb.new_state is not None
    assert rb.validation.can_commit()
    assert not [f for f in rb.consistency if f["severity"] == "hard"]
    assert rb.committable()


def test_new_state_matches_replay_driver_byte_for_byte():
    # Review Focus #1：new_state 必须 == 用 replay 的 apply_events 驱动 applied 事件的结果
    rb = reduce_commit(_state(), _proposals(), _contract(), _DRAFT, EPOCH,
                       committed_event_ids=frozenset({"evt_00000047_001"}))
    ref = apply_events(_state(), rb.applied, Reducer())
    assert rb.new_state.state_hash == ref.state_hash
    assert rb.new_state.chapter_no == 47


def test_dead_actor_batch_not_committable():
    st = _state()
    st = st.model_copy(update={"characters": {
        "char_000001": Character(character_id="char_000001", name="张三", status="dead",
            death_chapter=10, current_location="loc_000012",
            introduced_at_chapter=1, epoch=EPOCH)}})
    rb = reduce_commit(st, _proposals(), _contract(), _DRAFT, EPOCH,
                       committed_event_ids=frozenset({"evt_00000047_001"}))
    assert rb.committable() is False


def test_h8_quarantine_excluded_from_applied():
    props = _proposals()
    props.append(EventProposal(
        proposed_event_type="OBSERVES", actor="char_000001", target="fact_000001",
        chapter=47, seq=9, preconditions=[], payload={"fact_id": "fact_000001"},
        confidence=1000, source_ref="para:9", extraction_method="rule",
        extraction_confidence=600))
    rb = reduce_commit(_state(), props, _contract(), _DRAFT, EPOCH,
                       committed_event_ids=frozenset({"evt_00000047_001"}))
    assert rb.quarantined == 1
    assert to_event(props[-1], EPOCH).event_id not in {e.event_id for e in rb.applied}


def test_consistency_hard_blocks_committable():
    # 规则通道 OBSERVES 引用不存在事实：Validator 无 HARD，但 assert_consistent 落 I2/I9
    st = _state()
    props = [EventProposal(
        proposed_event_type="OBSERVES", actor="char_000001", target="fact_999999",
        chapter=47, seq=1, preconditions=[], payload={"fact_id": "fact_999999"},
        confidence=1000, source_ref="para:1", extraction_method="rule",
        extraction_confidence=1000)]
    contract = ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="观察",
        story_goal_type="revelation",
        required_events=[{"event_type": "OBSERVES", "description": "观察"}],
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-08T10:00:00Z")
    draft = "段落。\n\n<!-- hook: cliffhanger strength=800 -->"
    rb = reduce_commit(st, props, contract, draft, EPOCH)
    assert rb.validation.can_commit() is True
    assert any(f["severity"] == "hard" for f in rb.consistency)
    assert rb.committable() is False


def test_empty_new_state_when_batch_fails_h81():
    props = _proposals()
    for p in props:
        p.extraction_confidence = 400
    rb = reduce_commit(_state(), props, _contract(), _DRAFT, EPOCH)
    assert rb.new_state is None
    assert rb.applied == []
    assert rb.committable() is False
