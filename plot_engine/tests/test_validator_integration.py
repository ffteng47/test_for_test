# Validator 顶层编排 + 幂等 + 附录 A 金标 e2e（05 §10, 07 §5）
import json
from pathlib import Path

from plot_engine.canonical import canonical_json
from plot_engine.models.contract import ChapterContract
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.validator import Validator

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))


def _state(dead=False):
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="dead" if dead else "alive",
            death_chapter=10 if dead else None,
            current_location="loc_000012", introduced_at_chapter=1, epoch=EPOCH)},
        locations={}, items={}, realms={}, abilities={},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
                defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000002", "fact_000003")},
        state_hash="0" * 64)


def _golden_contract():
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
        required_events=[
            {"event_type": "OBSERVES", "description": "观察"},
            {"event_type": "INFERS", "description": "推断"}],
        forbidden_events=[{"event_type": "REVEALS", "description": "揭示", "reason": "gate"}],
        knowledge_allowed=["fact_000001", "fact_000003"], knowledge_forbidden=["fact_000002"],
        reader_signals=[{"fact_id": "fact_000003", "target_state": "knows"}],
        plot_progress={"main_thread": 80}, tension_target=720,
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        derived_from=["arc_003.knowledge_gates[fact_000002]", "arc_003.turning_points[47]"],
        created_at="2026-10-08T10:00:00Z")


def _event_proposals():
    method = {"OBSERVES": "rule", "INFERS": "llm", "READER_LEARNS": "markup"}
    out = []
    for ev in _FIX["chapter47_events"]:
        # fixture 用 1-based event_id 后缀（..._001）而 seq 字段是 0-based；
        # 抽取路径以 proposal_event_id 为准，故令 seq 对齐 id 后缀，preconditions 才自洽。
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


def test_golden_can_commit():
    v = Validator()
    res = v.validate(_DRAFT, _event_proposals(), _golden_contract(), _state())
    assert res.can_commit()
    assert res.hard_violations == []
    assert res.soft_warnings == []


def test_double_run_equal():
    v = Validator()
    args = (_DRAFT, _event_proposals(), _golden_contract(), _state())
    r1 = v.validate(*args).model_dump(mode="json")
    r2 = v.validate(*args).model_dump(mode="json")
    assert canonical_json(r1) == canonical_json(r2)


def test_state_untouched():
    v = Validator()
    st = _state()
    before = canonical_json(st.model_dump(mode="json"))
    v.validate(_DRAFT, _event_proposals(), _golden_contract(), st)
    assert canonical_json(st.model_dump(mode="json")) == before


def test_dead_actor_blocks_commit():
    v = Validator()
    res = v.validate(_DRAFT, _event_proposals(), _golden_contract(), _state(dead=True))
    assert not res.can_commit()
    assert any(f.rule_id == "H1.1" for f in res.hard_violations)


def test_validat_contract_golden_clean():
    from plot_engine.models.contract import ArcContract
    arc = ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(40, 60), tension_curve=[720] * 21,
        turning_points=[{"chapter": 47, "type": "revelation", "description": "d",
                         "required_event_types": ["OBSERVES", "INFERS"]}],
        knowledge_gates=[{"fact_id": "fact_000002", "allowed_after_chapter": 84,
                          "reveal_stage_target": "confirmed"}],
        created_at="2026-10-08T00:00:00Z")
    v = Validator()
    res = v.validate_contract(_golden_contract(), arc, _state())
    assert res.can_commit() and res.hard_violations == []
