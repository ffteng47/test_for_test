from pathlib import Path

from plot_engine.readout import _prose, _flippable, matrix, row


def _dump(tmp_path: Path, no: int, status: str, rounds: int, action: str = "") -> None:
    rev = f"- round {rounds} level=writer action={action} committed=True\n" if action else ""
    (tmp_path / f"ch{no:02d}.md").write_text(
        f"# Chapter {no} — status={status}\ntrace_status={status}\nrounds={rounds}\n\n"
        f"## Revision\n{rev}", encoding="utf-8")


def test_tax_flips_only_pure_h51_failure_with_a_field_equivalent(tmp_path: Path):
    def write(no: int, findings: str, proposals: str) -> Path:
        p = tmp_path / f"ch{no:02d}.md"
        p.write_text(f"## Findings\n{findings}\n## Proposals\n{proposals}", encoding="utf-8")
        return p
    a = write(1, "- HARD H5.1: 必需事件 OBSERVES 数量不足（0<1）\n",
              "- READS actor=char_000001 target=None payload={}\n")
    assert _flippable(a)                       # 缺 OBSERVES，但同 knowledge 族的 READS 在场
    b = write(2, "- HARD H5.1: 必需事件 OBSERVES 数量不足（0<1）\n"
                 "- HARD H2.2: char_000001 未取得知识 fact_000001（期望 known）\n",
               "- READS actor=char_000001 target=None payload={}\n")
    assert not _flippable(b)                   # 还压着别的 HARD，放宽 H5.1 也翻不绿
    c = write(3, "- HARD H5.1: 必需事件 BELIEVES 数量不足（0<1）\n",
               "- OBSERVES actor=char_000001 target=None payload={}\n")
    assert not _flippable(c)                   # OBSERVES 是 knowledge 族，补不了 belief 族的 BELIEVES
    d = write(4, "\n", "- OBSERVES actor=char_000001 target=None payload={}\n")
    assert not _flippable(d)                   # 没有 H5.1 欠账可翻



def test_matrix_uses_the_four_bucket_symbols_and_marks_arc(tmp_path: Path):
    dump = tmp_path / "runx" / "dump"
    dump.mkdir(parents=True)
    _dump(dump, 1, "OK", 0)                                  # 首轮
    _dump(dump, 2, "OK", 2, "rewrite_chapter")               # 救回
    _dump(dump, 3, "ARC_CONFLICT", 3, "renegotiate_contract")
    _dump(dump, 4, "NEEDS_HUMAN", 1)                        # 处置
    assert matrix([dump.parent])[0] == {"跑法": "runx", "1": "首", "2": "救",
                                        "3": "处✗", "4": "处",
                                        **{str(i): "-" for i in range(5, 11)}}


def test_row_reads_cost_from_the_sibling_log(tmp_path: Path):
    dump = tmp_path / "runy" / "dump"
    dump.mkdir(parents=True)
    _dump(dump, 1, "OK", 0)
    (tmp_path / "runy.log").write_text("tokens=12345 cost=$0.0000 用时=456s\n", encoding="utf-8")
    r = row(dump.parent)
    assert (r["tokens"], r["用时"], r["E2"]) == ("12345", "456s", "100%")


def test_row_labels_flat_layout_runs_by_their_own_dir(tmp_path: Path):
    """lv3 起 `--dump-dir <run>` 把 chNN.md 直接落在跑目录——标签/用量/正文都锚在跑目录，
    不许再借 dump 的 parent 反推（那会把三行都读成 "sampling"）。"""
    run = tmp_path / "lv3r1"
    run.mkdir()
    _dump(run, 1, "OK", 0)
    (tmp_path / "lv3r1.log").write_text("tokens=999 用时=7s\n", encoding="utf-8")
    r = row(run)
    assert (r["跑法"], r["tokens"], r["用时"]) == ("lv3r1", "999", "7s")
    assert matrix([run])[0]["跑法"] == "lv3r1"


def test_prose_column_extracts_the_two_numbers_in_order():
    assert _prose(["章首同主语：10 章里 8 次由同一个名字起笔"], "章首同主语") == "8/10"
    assert _prose([], "章首同主语") == "0"


def test_matrix_table_has_every_chapter_exactly_once():
    # 曾经把 ch01 整列丢了、跑法名重复两次——表头与每一行的格数必须一致且含 1..10。
    from plot_engine.readout import md
    lines = md(matrix(["sampling/bo_ctrl"]), ["跑法"] + [str(i) for i in range(1, 11)]).splitlines()
    assert lines[0].count("|") == 12 and sorted(int(x) for x in lines[0].split("|")[2:-1]) == list(range(1, 11))
    assert lines[2].split("|")[1].strip() == "bo_ctrl"
