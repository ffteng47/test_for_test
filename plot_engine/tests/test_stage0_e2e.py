# Stage-0 贯通 e2e：Writer 组装 → 四通道抽取 → Validate → Commit（07 §4.2–§4.4/§5–§9）
import json
from pathlib import Path

from plot_engine.commit import CommitOrchestrator
from plot_engine.eventlog import EventLog
from plot_engine.extract import stage0_extract
from plot_engine.models.commit import CommitRequest
from plot_engine.models.contract import ChapterContract
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore
from plot_engine.writer import compose_chapter_draft

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))


def _genesis_state():
    return StoryState(**{**_FIX["genesis"], "state_hash": ""})


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


def _plan() -> ScenePlan:
    def beat(i):
        return Beat(beat_id=f"bt_{i:06d}", seq=i % 3, intent="x", beat_type="setup")
    scenes = [Scene(scene_id=f"scn_0047_{n:02d}", chapter_no=47, seq=n - 1,
                   location="loc_000012", characters=["char_000001"], purpose="p",
                   tension=500, beats=[beat(3 * n + k) for k in range(3)]) for n in (1, 2, 3)]
    return ScenePlan(plan_id="sop_00000047", chapter_no=47, arc_id="arc_003",
                     contract_version=1, scenes=scenes, epoch=EPOCH,
                     created_at="2026-10-09T00:00:00Z")


def _scene_writer(scene, contract, state):
    return f"{scene.scene_id}：张三凝视那枚印章，纹路对不上。"


def _obs() -> EventProposal:
    return EventProposal(proposed_event_type="OBSERVES", actor="char_000001",
        target="fact_000003", chapter=47, seq=0, preconditions=[],
        payload={"fact_id": "fact_000003", "method": "sight"},
        confidence=1000, source_ref="para:4", extraction_method="rule",
        extraction_confidence=1000)


def _inf() -> EventProposal:
    return EventProposal(proposed_event_type="INFERS", actor="char_000001",
        target="fact_000001", chapter=47, seq=1, preconditions=["evt_00000047_000"],
        payload={"conclusion_fact_id": "fact_000001", "evidence_fact_ids": ["fact_000003"]},
        confidence=700, source_ref="para:6", extraction_method="rule",
        extraction_confidence=1000)


def _agree_rule(*_a):
    return [_obs(), _inf()]


def _agree_llm(*_a):
    # LLM 通道：同 payload 的镜像（method 改 llm，_key 仍等 → hybrid/1000）
    return [_obs().model_copy(update={"extraction_method": "llm"}),
            _inf().model_copy(update={"extraction_method": "llm"})]


def _conflict_rule(*_a):
    return [_obs()]


def _conflict_llm(*_a):
    # 同 span(para:4) 不同结果 → cross_validate 判冲突，两侧 500
    return [_inf().model_copy(update={"extraction_method": "llm", "source_ref": "para:4"})]


def _stack(tmp_path):
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis("s1", _genesis_state())
    return store, log, CommitOrchestrator(store, log, Reducer())


def test_stage0_golden_commits_and_parity(tmp_path):
    store, log, orch = _stack(tmp_path)
    contract = _contract()
    asm = compose_chapter_draft(_plan(), contract, _genesis_state(), _scene_writer)
    props = stage0_extract(asm.draft, _plan(), contract, _genesis_state(),
                           chapter=47, rule_channel=_agree_rule, llm_channel=_agree_llm)
    # 叙事两条，均 hybrid/1000；不含 READER_*
    assert [p.proposed_event_type for p in props] == ["OBSERVES", "INFERS"]
    assert all(p.extraction_method == "hybrid" and p.extraction_confidence == 1000 for p in props)

    req = CommitRequest(story_id="s1", chapter_no=47, draft=asm.draft, contract=contract,
                        expected_version=0, trace_id="t-47")
    out = orch.commit(req, props, store.load_latest("s1").state)
    assert out.status == "OK"
    assert out.validation is not None and out.validation.can_commit()
    from plot_engine.replay import verify_parity
    assert verify_parity(store, log, Reducer(), "s1", 47) is True


def test_stage0_conflict_quarantines_and_fails(tmp_path):
    store, log, orch = _stack(tmp_path)
    contract = _contract()
    asm = compose_chapter_draft(_plan(), contract, _genesis_state(), _scene_writer)
    props = stage0_extract(asm.draft, _plan(), contract, _genesis_state(),
                           chapter=47, rule_channel=_conflict_rule, llm_channel=_conflict_llm)
    assert all(p.extraction_confidence == 500 for p in props)   # 冲突降为 500

    req = CommitRequest(story_id="s1", chapter_no=47, draft=asm.draft, contract=contract,
                        expected_version=0, trace_id="t-47c")
    out = orch.commit(req, props, store.load_latest("s1").state)
    assert out.status == "FAIL"
    hard_ids = {f.rule_id for f in out.validation.hard_violations}
    assert "H8.2" in hard_ids or "H5.1" in hard_ids            # 隔离 + required 未满足
    assert store.load_latest("s1").version == 0                # 无副作用
    assert log.read_chapter("s1", 47) == []
