"""P2 失败即停（`docs/phase1-merged-plan-final.md` §9 裁定）。

测量语义（默认）与产品语义的差别只有一件事：**后面那几章要不要写**。
所以断言的是「停在第几章 + 停后没有再生成」，不是任何判据数字——
分母被这条改了，E2 必须另立基线，这里不该出现任何通过率。
"""
import sys
from pathlib import Path

from plot_engine.eventlog import EventLog
from plot_engine.experiment import run_experiment
from plot_engine.store import StateStore

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import experiment_10ch as fixture  # noqa: E402


def _run(tmp_path, defects, stop, chapters=10):
    cfg = fixture.make_config(chapters)
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    return run_experiment(cfg, store=store, log=log,
                          chapter_source=fixture.build_source(defects, cfg.arc_contract),
                          scene_writer=fixture.dummy_writer, stop_on_unresolved=stop)


def test_default_keeps_running_the_whole_chain(tmp_path):
    rep = _run(tmp_path, {3: "leak"}, stop=False)
    assert rep.chapters_generated == 10
    assert rep.unresolved_chapters == [3]


def test_commit_failure_stops_the_chain_at_that_chapter(tmp_path):
    rep = _run(tmp_path, {3: "leak"}, stop=True)
    assert rep.chapters_generated == 3, "第 3 章之后一章都不许再生成"
    assert rep.unresolved_chapters == [3]
    # 停前已提交的章照常有效，链不是作废而是截断
    assert rep.chapters_committed == 2


def test_commit_failure_at_ch5_stops_there(tmp_path):
    rep = _run(tmp_path, {5: "dead"}, stop=True)
    assert rep.unresolved_chapters == [5]
    assert rep.chapters_generated == 5, "判死章本身算 generated（正文花了），但第 6 章起不许再跑"


def test_arc_error_before_work_starts_also_stops(tmp_path):
    """开工前判死（契约派生就 raise，管道一步没跑）也是「这章交不出去」：产品路径上一样停。"""
    from plot_engine.derive import NoChapterIntent

    cfg = fixture.make_config(10)
    base = fixture.build_source(None, cfg.arc_contract)
    raised = {"n": 0}

    def source(ch, state):
        if ch == 2:
            raised["n"] += 1
            raise NoChapterIntent("夹具：本章没有可执行意图")
        return base(ch, state)

    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)
    rep = run_experiment(cfg, store=store, log=log, chapter_source=source,
                         scene_writer=fixture.dummy_writer, stop_on_unresolved=True)
    assert raised["n"] == 1 and rep.unresolved_chapters == [2]
    assert rep.chapters_generated == 1, "开工前判死不算 generated，也不许往下写第 3 章"


def test_clean_chain_is_unaffected(tmp_path):
    rep = _run(tmp_path, {}, stop=True)
    assert rep.chapters_generated == 10 and rep.unresolved_chapters == []
