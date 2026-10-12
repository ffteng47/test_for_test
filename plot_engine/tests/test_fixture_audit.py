from pathlib import Path

from plot_engine.fixture_audit import revision_loop_chapters, unreachable_by_construction
from plot_engine.models.contract import FIELD_EVENT_TYPES


def test_ladder_pairs_every_must_change_with_a_same_fact_event():
    """H5.3 的兑现前提：本章必须要求一个**指向同一对象**的实现事件。

    这条抓不到 E14（ch07 当时 `SUSPECTS _F4` 与 `must_change _F4` 是自洽的，错在对象选得不合戏剧逻辑，
    只有跨臂同章失败才暴露它），抓的是更坏的下一档：目标 id 写串 ⇒ 模型无论怎么写都过不了。
    """
    from plot_engine.tests.fixtures import experiment_10ch as fx

    for step in fx._STEPS:
        implementers = set(FIELD_EVENT_TYPES.get("knowledge", set())) | \
            set(FIELD_EVENT_TYPES.get("belief", set()))
        for ch in step["must_change"]:
            if ch["field"] not in ("knowledge", "belief"):
                continue
            assert any(e["event_type"] in implementers and e["fact"] == ch["target"]
                       for e in step["events"]), \
                f"{ch['field']}→{ch['target']} 在本步没有同对象实现事件：{step['events']}"


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
