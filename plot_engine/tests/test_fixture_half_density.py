"""归因 H 批夹具钉：半密度变体只许动「密度」这一个变量。

turning point 章（1/5/9）与空推进章（8）必须与 ladder-v4 基线逐字同构；
其余章节 must_change / required_events 各砍半；LADDER_VERSION 与规划哈希必须与
基线不同（确认闸据此强制新工单）。离线全绿由 `review --fixture experiment_10ch_half`
的既有路径覆盖，这里只钉「差异面恰好是密度」。
"""
from plot_engine.review import plan_sha256
from plot_engine.tests.fixtures import experiment_10ch as full
from plot_engine.tests.fixtures import experiment_10ch_half as half

_TP_OR_EMPTY = (1, 5, 8, 9)


def test_ladder_identity_and_distinct_plan_hash():
    assert half.LADDER_VERSION != full.LADDER_VERSION
    assert plan_sha256(half.make_config(10), "experiment_10ch_half") != \
        plan_sha256(full.make_config(10), "experiment_10ch")


def test_turning_point_and_empty_chapters_are_byte_identical():
    a_full, a_half = full.build_arc(10), half.build_arc(10)
    for ch in _TP_OR_EMPTY:
        assert a_half.reader_beats[ch - 1] == a_full.reader_beats[ch - 1]


def test_other_chapters_are_thinned_to_one_each():
    a_full, a_half = full.build_arc(10), half.build_arc(10)
    for beat_f, beat_h in zip(a_full.reader_beats, a_half.reader_beats):
        if beat_f["chapter_no"] in _TP_OR_EMPTY:
            continue
        assert len(beat_h["must_change"]) == 1
        assert len(beat_h["required_events"]) == 1
        assert len(beat_f["must_change"]) == 2
    # 全局密度：18→12 / 16→11（非 TP 章减半、TP 章不动）
    assert sum(len(b["must_change"]) for b in a_half.reader_beats) == 12
    assert sum(len(b["required_events"]) for b in a_half.reader_beats) == 11


def test_offline_dry_run_is_green_on_half_density():
    from plot_engine.experiment import evaluate_exit_conditions
    from plot_engine.review import _offline_dry_run
    report = _offline_dry_run(10, {}, fixture="experiment_10ch_half")
    assert all(v is True for v in evaluate_exit_conditions(report).values())
