# 爽点工程读数（R8 #2 全-A 拍板 2026-10-17）：纯派生观察列的最小钉桩——一正一反
from plot_engine.metrics import r3r6_flags
from plot_engine.models.contract import ArcContract, ChapterContract, ChapterHook, TurningPoint
from plot_engine.validator import _hook_ok

from plot_engine.markup import parse_markup


def _contract(ending_type="cliffhanger") -> ChapterContract:
    return ChapterContract(chapter_no=1, arc_id="arc_003", epoch="epoch_0", story_goal="g",
                           story_goal_type="revelation",
                           ending=ChapterHook(type=ending_type, strength=800, description="d"),
                           created_at="2026-10-17T00:00:00Z")


def test_hook_same_predicate_pass_and_fail():
    draft_ok = "第一段\n\n第二段\n\n第三段收尾\n<!-- hook: cliffhanger strength=600 -->"
    draft_wrong_type = "第一段\n\n第二段\n\n第三段收尾\n<!-- hook: reveal strength=600 -->"
    assert _hook_ok(parse_markup(draft_ok), _contract())
    assert not _hook_ok(parse_markup(draft_wrong_type), _contract())


def test_r3r6_flags_fire_on_crafted_curve_and_stay_quiet_on_clean():
    tps = [TurningPoint(chapter=2, type="crisis", description="d", required_event_types=[]),
           TurningPoint(chapter=8, type="reversal", description="d", required_event_types=[])]
    flat_then_low = [500, 510, 520, 530, 200, 200, 200, 200]
    flags = r3r6_flags(flat_then_low, [t.chapter for t in tps])
    assert any(f.startswith("R3'@ch1") for f in flags)          # 前四章差<50 连续 → 注水窗
    assert any(f.startswith("R6'@ch") for f in flags)           # 转折章 2/8 张力 <700
    assert any(f.startswith("R5'@ch1") for f in flags)          # 10 章窗内无 ≥800 峰
    assert not any(f.startswith("R4'") for f in flags)          # 无 5 连单调升
    clean = [300, 500, 700, 900, 400, 600, 800, 950]
    flags2 = r3r6_flags(clean, [])
    assert flags2 == []                                        # 有峰、无注水窗、无 5 连升
