# §9.1 第 1 层：硬伤必须抓得到，好话不许它说。
from plot_engine.prose_audit import audit

_CLEAN = {1: "张三在藏宝阁凝视那枚印章，印泥是干的。",
          2: "夜色里他翻开花名册，一行小字对不上。"}
_DIRTY = {1: "他举起显微镜看那枚印章。", 2: "一封匿名邮件躺在办公室里。",
          3: "会议室里众人沉默。", 4: "他举着显微镜不肯放。", 5: "他举着显微镜走开了。"}


def test_clean_run_reports_nothing():
    assert audit(_CLEAN) == []


def test_anachronisms_are_named_with_the_chapter():
    hits = [f for f in audit(_DIRTY) if "穿帮词" in f]
    assert len(hits) == 5 and any("第 2 章" in f and "邮件" in f for f in hits)


def test_repeated_chapter_openings_fire_only_past_the_floor():
    same = {n: "张三站在山门前，夜色很深。" + "余" * 20 for n in range(1, 4)}
    assert any("章首同构" in f for f in audit(same))
    assert not any("章首同构" in f for f in audit({1: same[1], 2: same[2]}))
