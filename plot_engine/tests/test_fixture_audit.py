from pathlib import Path

from plot_engine.fixture_audit import revision_loop_chapters, unreachable_by_construction
from plot_engine.models.contract import FIELD_EVENT_TYPES


def test_fix_guide_h51_covers_every_fixture_event_type():
    """修稿指引 H5.1 必须**逐个**解释夹具用得到的事件类型怎么写得看得见。

    E18（docs/measurement-errata.md）：`FIX_GUIDE["H5.1"]` 漏讲 SUSPECTS，而 ch07 是全库
    唯一必需 SUSPECTS 的章——写手拿到的指引里没有那条的写法，同字典 H5.3 反倒列了它，
    一轮内两条指引对同一类型口径打架。这条静态审计钉住「夹具会用的类型 ⊆ 指引文本」，
    漏一个就红，不必等一次真跑烧掉采样预算才发现指引少了一半信息。
    """
    import re

    from plot_engine.review import FIX_GUIDE
    from plot_engine.tests.fixtures import experiment_10ch as fx

    used = {e["event_type"] for step in fx._STEPS for e in step["events"]}
    guide = FIX_GUIDE["H5.1"]
    missing = [t for t in sorted(used) if not re.search(rf"\b{t}\b", guide)]
    assert not missing, f"H5.1 指引没解释这些夹具事件类型怎么写：{missing}"


def test_ladder_pairs_every_must_change_with_a_same_fact_event():
    """H5.3 的兑现前提：本章必须要求一个**同 field、同对象**的实现事件。

    取事件集必须**按 field 查**，与 `validator._change_implemented` 同源（`:500` 用的就是
    `FIELD_EVENT_TYPES[ch.field]`）：knowledge 要 OBSERVES/READS/IS_TOLD/INFERS，belief 要
    BELIEVES/SUSPECTS/DOUBTS，两族不互通。用并集的话，「`field=knowledge` 却本章只有 BELIEVES」
    这种写串能过审计、但模型怎么写都过不了 H5.3。

    这条抓不到 E14（ch07 当时 `SUSPECTS _F4` 与 `must_change _F4` 是同 field 同对象的自洽对，
    错在对象选得不合戏剧逻辑，只有跨臂同章失败才暴露它），抓的是更坏的下一档：id 或 field 写串。
    """
    from plot_engine.tests.fixtures import experiment_10ch as fx

    for step in fx._STEPS:
        for ch in step["must_change"]:
            implementers = FIELD_EVENT_TYPES.get(ch["field"], set())
            assert any(e["event_type"] in implementers and e.get("fact") == ch["target"]
                       for e in step["events"]), \
                f"{ch['field']}→{ch['target']} 在本步没有同 field 同对象实现事件：{step['events']}"


def test_fixture_has_no_unreachable_chapter_by_construction():
    # 夹具的 A 批改动（逐章知识阶梯）的验收线：期望值全部落在本章事件类型的 reducer 上限内。
    assert unreachable_by_construction() == {}


def test_revision_loop_column_picks_h53_dominated_chapters(tmp_path: Path):
    def dump(no: int, rules: str, status: str = "NEEDS_HUMAN", rounds: int = 3) -> None:
        (tmp_path / f"ch{no:02d}.md").write_text(
            f"# Chapter {no} — status={status}\ntrace_status={status}\nrounds={rounds}\n\n"
            "## Revision\n- round 3 level=contract rules=" + rules + " action=renegotiate_contract\n",
            encoding="utf-8")

    dump(1, "H5.1,H5.3")          # H5.3 与其他同数 ⇒ 算修订环
    dump(2, "H5.1,H5.1,H5.3")     # 被 H5.1 压住 ⇒ 不算
    dump(3, "H5.3", status="OK", rounds=0)   # 已提交 ⇒ 不算
    assert revision_loop_chapters(tmp_path) == [1]
