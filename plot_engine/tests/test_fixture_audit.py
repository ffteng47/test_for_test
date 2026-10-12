from pathlib import Path

from plot_engine.fixture_audit import revision_loop_chapters, unreachable_by_construction
from plot_engine.models.contract import FIELD_EVENT_TYPES


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
