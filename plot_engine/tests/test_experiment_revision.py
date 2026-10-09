# 06 接入 08 实验：revision_loop 可选注入；不注入时行为逐字不变
import sys
import pathlib

from plot_engine.eventlog import EventLog
from plot_engine.experiment import evaluate_exit_conditions, run_experiment
from plot_engine.models.revision import RevisionPolicy
from plot_engine.revision import RevisionLoop
from plot_engine.store import StateStore

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures"))
import experiment_10ch as fixture  # noqa: E402


def _run(tmp_path, defects, loop=None, chapters=10):
    cfg = fixture.make_config(chapters)
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    return run_experiment(cfg, store=store, log=log,
                          chapter_source=fixture.build_source(defects),
                          scene_writer=fixture.dummy_writer, revision_loop=loop)


def test_without_loop_report_and_e3_are_unchanged(tmp_path):
    r = _run(tmp_path, {})
    assert r.revision_rounds == {} and r.revision_success_rate == 0.0
    assert r.chapters_committed == 10
    assert evaluate_exit_conditions(r)["E3"] is None          # 未跑 Revision → 不可判，不是通过


def test_with_loop_clean_run_records_zero_rounds_and_passes_e3(tmp_path):
    r = _run(tmp_path, {}, loop=RevisionLoop(actions={"rerun_extraction": lambda c: c}))
    assert r.chapters_committed == 10
    assert r.revision_rounds == {ch: 0 for ch in range(1, 11)}
    assert r.revision_success_rate == 1.0
    assert evaluate_exit_conditions(r)["E3"] is True


def test_deterministic_writer_cannot_self_fix_but_rounds_are_recorded(tmp_path):
    """Phase 0 事实：夹具 Writer 是确定性的，重写只会得到同一份 Draft → 振荡升级 → 触顶转人工。"""
    loop = RevisionLoop(actions={"rewrite_scene": lambda c: c, "rewrite_chapter": lambda c: c})
    r = _run(tmp_path, {3: "leak"}, loop=loop, chapters=4)
    assert r.chapters_committed == 3 and r.unresolved_chapters == [3]
    # 同集合 → 振荡 → 沿阶梯升级；阶梯走完仍失败 → 触顶/转人工，但轮数一定被记录（06 R6）
    assert 0 < r.revision_rounds[3] <= RevisionPolicy().max_rounds
    assert r.revision_rounds[1] == 0
    assert r.revision_success_rate == 0.0
    ec = evaluate_exit_conditions(r)
    assert ec["E3"] is False and ec["E2"] is True             # 3/4 = 75% 仍过 E2
