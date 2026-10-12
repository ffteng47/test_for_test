from pathlib import Path

from plot_engine.fixture_audit import revision_loop_chapters, unreachable_by_construction


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
