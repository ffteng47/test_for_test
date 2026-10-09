# 10 章实验 e2e + Phase-0 退出条件回归（08 §3/§4/§8）
import sys
from pathlib import Path

from plot_engine.eventlog import EventLog
from plot_engine.experiment import evaluate_exit_conditions, run_experiment
from plot_engine.store import StateStore

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import experiment_10ch as fixture  # noqa: E402


def _run(tmp_path, chapters, defects=None, suffix=""):
    cfg = fixture.make_config(chapters)
    store = StateStore(str(tmp_path / f"s{suffix}.db"))
    log = EventLog(str(tmp_path / f"e{suffix}.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    return run_experiment(cfg, store=store, log=log,
                          chapter_source=fixture.build_source(defects),
                          scene_writer=fixture.dummy_writer)


def test_ten_chapters_all_valid_meets_exit_conditions(tmp_path):
    rep = _run(tmp_path, 10)
    assert rep.chapters_generated == 10 and rep.chapters_committed == 10
    assert rep.replay_consistency is True and rep.replay_mismatch_chapters == []
    assert rep.canon_contradictions == 0 and rep.knowledge_contradictions == 0
    assert rep.timeline_contradictions == 0 and rep.hard_violations == {}
    ec = evaluate_exit_conditions(rep)
    assert ec == {"E1": True, "E2": True, "E3": None, "E4": True, "E5": True, "E6": True}


def test_defects_land_in_correct_hard_metric_buckets(tmp_path):
    rep = _run(tmp_path, 10, defects={3: "leak", 6: "dead"})
    assert rep.chapters_generated == 10 and rep.chapters_committed == 8
    assert rep.unresolved_chapters == [3, 6]
    # leak 章 → H5.7（泄禁知）；dead 章 → H1.1（死人出场）；均计入 hard_violations dict
    assert rep.hard_violations.get("H5.7", 0) >= 1
    assert rep.hard_violations.get("H1.1", 0) >= 1
    # 被拒章不污染 committed 故事的设定/知识/时序矛盾（引擎正确拒了坏输入）
    assert rep.canon_contradictions == 0 and rep.knowledge_contradictions == 0
    assert rep.timeline_contradictions == 0
    ec = evaluate_exit_conditions(rep)
    assert ec["E1"] is True and ec["E2"] is True       # 8/10 ≥ 70%
    # E6：committed 故事无矛盾、Replay 一致 → 无架构阻断。
    # （E4「单一规则占比>40%」随缺陷分布而变，属真实信号，健康性由 all-valid 用例保证。）
    assert ec["E6"] is True


def test_rejected_chapter_never_enters_committed_state(tmp_path):
    # leak 章触发 H5.7；该章未 commit，final committed 故事无矛盾 → 三项命名指标恒 0
    rep = _run(tmp_path, 10, defects={2: "leak"}, suffix="only")
    assert rep.hard_violations.get("H5.7", 0) >= 1
    assert rep.knowledge_contradictions == 0
    assert 2 in rep.unresolved_chapters
    assert rep.chapters_committed == 9
