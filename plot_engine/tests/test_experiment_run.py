# run_experiment 驱动 + 退出条件闸门（08 §5/§8）
import json
from pathlib import Path

from plot_engine.eventlog import EventLog
from plot_engine.experiment import evaluate_exit_conditions, run_experiment
from plot_engine.models.contract import ArcContract, ChapterContract, ChapterHook, ReaderSignal
from plot_engine.models.entity import Character
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.models.state import StoryState
from plot_engine.store import StateStore

EPOCH = "epoch_0"
_FIX = json.loads((Path(__file__).parent / "fixtures" / "traitor_arc.json").read_text(encoding="utf-8"))


def _plan(ch: int) -> ScenePlan:
    def beat(i):
        return Beat(beat_id=f"bt_{i:06d}", seq=i % 3, intent="x", beat_type="setup")
    scenes = [Scene(scene_id=f"scn_{ch:04d}_{n:02d}", chapter_no=ch, seq=n - 1,
                   location="loc_000012", characters=["char_000001"], purpose="p",
                   tension=500, beats=[beat(3 * n + k) for k in range(3)]) for n in (1, 2, 3)]
    return ScenePlan(plan_id=f"sop_{ch:08d}", chapter_no=ch, arc_id="arc_003",
                     contract_version=1, scenes=scenes, epoch=EPOCH,
                     created_at="2026-10-09T00:00:00Z")


def _contract(ch: int) -> ChapterContract:
    return ChapterContract(
        chapter_no=ch, arc_id="arc_003", epoch=EPOCH, story_goal="g",
        story_goal_type="revelation",
        must_change=[{"character_id": "char_000001", "field": "knowledge", "operation": "add",
                      "target": "fact_000003", "expected_value": "known"},
                     {"character_id": "char_000001", "field": "knowledge", "operation": "add",
                      "target": "fact_000001", "expected_value": "suspected"}],
        must_not_change=[{"character_id": "char_000001", "field": "knowledge",
                          "operation": "update", "target": "fact_000002"}],
        required_events=[{"event_type": "OBSERVES", "description": "o"},
                         {"event_type": "INFERS", "description": "i"}],
        forbidden_events=[{"event_type": "REVEALS", "description": "r", "reason": "gate"}],
        knowledge_allowed=["fact_000001", "fact_000003"], knowledge_forbidden=["fact_000002"],
        reader_signals=[ReaderSignal(fact_id="fact_000003", target_state="knows")],
        tension_target=720,
        ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
        created_at="2026-10-09T00:00:00Z")


_DRAFT = ("张三凝视印章。\n\n<!-- reader_learns: fact_000003 -->\n\n"
          "<!-- hook: cliffhanger strength=800 -->")


def _channels(ch: int, actor: str = "char_000001"):
    def rule(*_a):
        return [
            EventProposal(proposed_event_type="OBSERVES", actor=actor, target="fact_000003",
                          chapter=ch, seq=0, preconditions=[],
                          payload={"fact_id": "fact_000003", "method": "sight"},
                          confidence=1000, source_ref="para:4", extraction_method="rule",
                          extraction_confidence=1000),
            EventProposal(proposed_event_type="INFERS", actor=actor, target="fact_000001",
                          chapter=ch, seq=1, preconditions=[f"evt_{ch:08d}_000"],
                          payload={"conclusion_fact_id": "fact_000001",
                                   "evidence_fact_ids": ["fact_000003"]},
                          confidence=700, source_ref="para:6", extraction_method="rule",
                          extraction_confidence=1000)]
    def llm(*_a):
        return [p.model_copy(update={"extraction_method": "llm"}) for p in rule()]
    return rule, llm


def _source(bad_chapter=None):
    def src(ch, cur):
        actor = "char_000009" if (bad_chapter is not None and ch == bad_chapter) else "char_000001"
        rule, llm = _channels(ch, actor)
        return ChapterArtifacts(contract=_contract(ch), scene_plan=_plan(ch),
                                draft=_DRAFT, rule_channel=rule, llm_channel=llm)
    return src


def _config(chapters: int) -> ExperimentConfig:
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    chars = dict(genesis.characters)
    chars["char_000009"] = Character(character_id="char_000009", name="旧主", status="dead",
                                     death_chapter=1, introduced_at_chapter=1, epoch=EPOCH)
    genesis = genesis.model_copy(update={"characters": chars})
    arc = ArcContract(arc_id="arc_003", epoch=EPOCH, chapter_range=(1, 30),
                      turning_points=[{"chapter": 1, "type": "revelation", "description": "d",
                                       "required_event_types": ["OBSERVES"]}],
                      knowledge_gates=[], created_at="2026-10-09T00:00:00Z")
    return ExperimentConfig(story_id="s1", chapters=chapters, arc_contract=arc,
                            initial_state=genesis, seed=42, epoch=EPOCH)


def _dummy_writer(scene, contract, state):
    return scene.scene_id


def _run(tmp_path, chapters, bad_chapter=None, suffix=""):
    cfg = _config(chapters)
    store = StateStore(str(tmp_path / f"s{suffix}.db"))
    log = EventLog(str(tmp_path / f"e{suffix}.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    return run_experiment(cfg, store=store, log=log, chapter_source=_source(bad_chapter),
                          scene_writer=_dummy_writer)


def test_all_valid_commits(tmp_path):
    rep = _run(tmp_path, 3)
    assert rep.chapters_generated == 3 and rep.chapters_committed == 3
    assert rep.replay_consistency is True and rep.replay_mismatch_chapters == []
    assert rep.unresolved_chapters == []
    ec = evaluate_exit_conditions(rep)
    assert ec["E1"] is True and ec["E2"] is True and ec["E6"] is True and ec["E3"] is None


def test_bad_chapter_quarantined_from_commit(tmp_path):
    rep = _run(tmp_path, 3, bad_chapter=2)
    assert rep.chapters_generated == 3 and rep.chapters_committed == 2
    assert rep.unresolved_chapters == [2]
    assert rep.hard_violations.get("H1.1", 0) >= 1     # dead actor → DEAD_REAPPEAR
    assert evaluate_exit_conditions(rep)["E2"] is False  # 2/3 < 70%


def test_report_deterministic_across_runs(tmp_path):
    a = _run(tmp_path, 3, suffix="a")
    b = _run(tmp_path, 3, suffix="b")
    # 报告含 §3 float 字段（cost/success_rate），canonical 禁浮点，故用确定性 json.dumps 比对
    dump = lambda r: json.dumps(r.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    assert dump(a) == dump(b)


def test_on_chapter_records_every_chapter_including_failures(tmp_path):
    """08 §10 I3：所有 failure 必须被记录。失败章不进 State，triage 只能靠这份逐章快照。"""
    from plot_engine.eventlog import EventLog as _Log
    from plot_engine.store import StateStore as _Store

    seen = []
    cfg = _config(3)
    store, log = _Store(str(tmp_path / "s.db")), _Log(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    rep = run_experiment(cfg, store=store, log=log, chapter_source=_source(bad_chapter=2),
                         scene_writer=lambda s, c, st: s.scene_id,
                         on_chapter=lambda ch, draft, props, out: seen.append(
                             (ch, draft, len(props), out.status)))
    assert [s[0] for s in seen] == [1, 2, 3]
    assert all(s[1] for s in seen)                      # 失败章的 draft 也一样记录
    assert seen[1][3] != "OK" and rep.unresolved_chapters == [2]
    assert all(s[2] >= 2 for s in seen)                 # 抽取产物同步交给归因层


def test_arc_conflict_chapter_recorded_and_run_continues(tmp_path):
    """前置 0：derive 判死的章（04 §4.3 / 06 §4.3）不该把整场实验换成 traceback。

    本章一步管道都没跑 ⇒ 不算 generated、不花 token；但 08 §10 I3 要求它被记录，
    所以它进 unresolved + §6 的 Contract/Arc 桶，实验接着跑完剩下的章。
    """
    from plot_engine.derive import ArcConflict

    def src(ch, cur):
        if ch == 2:
            raise ArcConflict("arc_003 第 2 章事实同时 allowed/forbidden：fact_000001")
        return _source()(ch, cur)

    cfg = _config(3)
    store, log = StateStore(str(tmp_path / "s.db")), EventLog(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    seen = []
    rep = run_experiment(cfg, store=store, log=log, chapter_source=src,
                         scene_writer=_dummy_writer,
                         on_chapter=lambda ch, ctx, props, out: seen.append((ch, ctx, str(out))))
    assert rep.chapters_generated == 2 and rep.chapters_committed == 2
    assert rep.unresolved_chapters == [2]
    assert rep.hard_violations["ARC_CONFLICT"] == 1
    assert [s[0] for s in seen] == [1, 2, 3]           # 每章都有快照，失败章不缺
    assert seen[1][1] is None and "allowed/forbidden" in seen[1][2]
