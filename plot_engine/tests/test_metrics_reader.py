# §7 两条判据线的读数器：只认逐章快照，不改判据定义
from plot_engine.metrics import metrics_from_dump


def _write(tmp_path, name, head, revision="", draft="", round0=""):
    (tmp_path / name).write_text(
        head + "\n" + revision + "\n## Draft\n" + draft + round0, encoding="utf-8")


def test_the_two_frozen_lines_are_recomputable_from_a_dump_dir(tmp_path):
    _write(tmp_path, "ch01.md", "# Chapter 1 — status=OK\ntrace_status=OK\nrounds=0")
    _write(tmp_path, "ch02.md", "# Chapter 2 — status=OK\ntrace_status=OK\nrounds=1",
           "## Revision\n- round 1 level=writer rules=H2.2 action=rewrite_scene committed=True\n",
           draft="正文 A\n")
    _write(tmp_path, "ch03.md", "# Chapter 3 — status=OK\ntrace_status=OK\nrounds=1",
           "## Revision\n- round 1 level=contract rules=H5.1 action=renegotiate_contract committed=True\n",
           draft="正文 B\n", round0="\n## Round 0（contract_version=1）\n正文 B\n")
    _write(tmp_path, "ch04.md", "# Chapter 4 — status=ARC_CONFLICT\ntrace_status=ARC_CONFLICT\nrounds=0")

    m = metrics_from_dump(tmp_path)
    assert [r.bucket for r in m.reads] == ["first_pass", "rewrite_rescued",
                                           "renegotiate_only", "disposition"]
    assert m.clean_e2 == 0.5                 # (首轮 1 + 救回 1) / 生成 4，renegotiate-only 不进分子
    assert m.disposition_rate == 0.25        # 判死 1 / 生成 4 = 1 − 名义提交率
    assert m.dispositions == {"ARC_CONFLICT": 1}
    text = m.render()
    assert "干净口径 E2 = 50.0%" in text and "人工处置率 = 25.0%" in text


def test_needs_human_and_fail_are_both_disposition_and_are_listed_separately(tmp_path):
    _write(tmp_path, "ch01.md", "# Chapter 1 — status=FAIL\ntrace_status=NEEDS_HUMAN\nrounds=3")
    _write(tmp_path, "ch02.md", "# Chapter 2 — status=FAIL\ntrace_status=FAIL\nrounds=3")

    m = metrics_from_dump(tmp_path)
    assert m.dispositions == {"FAIL": 1, "NEEDS_HUMAN": 1}
    assert m.disposition_rate == 1.0 and m.clean_e2 == 0.0
    assert "提交章 0" in m.render()
