# WP-F B5 章闭环裁决菜单：committed=ready、处置章=needs_decision+动作候选（派生参考面）
from plot_engine.metrics import adjudication_table


def test_menu_splits_committed_from_needs_decision(tmp_path):
    (tmp_path / "ch01.md").write_text("# Chapter 1 — status=OK\ntrace_status=OK\nrounds=0\n## Draft\n正文\n", encoding="utf-8")
    (tmp_path / "ch02.md").write_text("# Chapter 2 — status=FAIL\ntrace_status=NEEDS_HUMAN\nrounds=3\n## Draft\n正文\n", encoding="utf-8")
    (tmp_path / "ch03.md").write_text("# Chapter 3 — status=ARC_CONFLICT\ntrace_status=FAIL\n"
                                      "message=needs_arc_replan：同条 must_change 仍未实现\nrounds=1\n", encoding="utf-8")

    rows = adjudication_table(tmp_path)
    assert [r["status"] for r in rows] == ["ready", "needs_decision", "needs_decision"]
    assert rows[0]["actions"] == []
    assert rows[2]["trace_status"] == "ARC_CONFLICT"         # 判死族按抬头认（r4/r5 ch10 实证形态）
    assert "arc_replan" in rows[2]["actions"]                # 判死章给大纲重排出口
    assert "contract_edit" in rows[1]["actions"]             # 待人工章给改契约出口
    assert all("accept_current" in r["actions"] for r in rows[1:])  # 接受现状恒在（storyctl 同形）


def test_backend_action_enum_stays_in_sync_with_menu():
    from backend.noveldb import CHAPTER_ACTIONS
    from plot_engine.metrics import ADJ_ALL_ACTIONS

    assert CHAPTER_ACTIONS == ADJ_ALL_ACTIONS          # 两处枚举漂移=入账拒字面，测试先钉死
