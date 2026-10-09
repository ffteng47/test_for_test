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
                          chapter_source=fixture.build_source(defects, cfg.arc_contract),
                          scene_writer=fixture.dummy_writer)


def test_ten_chapters_all_valid_meets_exit_conditions(tmp_path):
    rep = _run(tmp_path, 10)
    assert rep.chapters_generated == 10 and rep.chapters_committed == 10
    assert rep.replay_consistency is True and rep.replay_mismatch_chapters == []
    assert rep.canon_contradictions == 0 and rep.knowledge_contradictions == 0
    assert rep.timeline_contradictions == 0 and rep.hard_violations == {}
    ec = evaluate_exit_conditions(rep)
    assert ec == {"E1": True, "E2": True, "E3": None, "E4": True, "E5": True, "E6": True}


def test_ten_chapters_do_not_share_one_constraint_set(tmp_path):
    """Review Focus #4：十章派生后若各章 `required_events` 全等，说明 Arc 其实只有一个
    turning point，实验依旧只在测「一条约束重复十遍」而不是跨章推进。"""
    cfg = fixture.make_config(10)
    src = fixture.build_source(arc=cfg.arc_contract)
    arts = [src(ch, cfg.initial_state) for ch in range(1, 11)]
    required = [frozenset(e.event_type for e in a.contract.required_events) for a in arts]
    assert len(set(required)) > 1
    assert required[0] == {"OBSERVES"} and required[4] == {"INFERS"}      # 第 1/5/9 章的拐点
    assert required[-2] == {"OBSERVES", "INFERS"}
    # D2'：张力逐章取曲线值 → 十条互不相同
    assert len({a.contract.tension_target for a in arts}) == 10
    # D5/D9：中段闸门（第 5 章起对读者暗示 fact_000004）→ 前半程 forbidden、后半程有信号
    sigs = [frozenset((s.fact_id, s.target_state) for s in a.contract.reader_signals)
            for a in arts]
    assert sigs[0] != sigs[4] and sigs[4] == sigs[9]
    assert ("fact_000004", "hinted") in sigs[4]
    forbidden = [frozenset(a.contract.knowledge_forbidden) for a in arts]
    assert "fact_000004" in forbidden[0] and "fact_000004" not in forbidden[4]


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
