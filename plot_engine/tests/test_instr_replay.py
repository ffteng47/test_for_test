"""W5 回放 runner 契约钉测（零模型调用）。

1.txt 要求的三件事在此逐条钉死：Draft 段解析、词表同源、run JSON 能被 instr_cli 吃。
"""
import json
from pathlib import Path

from plot_engine.instr_replay import (draft_from_dump, frozen_corpus, replay,
                                      write_run)


def test_draft_section_is_read_not_the_whole_dump():
    """必须只取 `## Draft` 与下一个 `## ` 之间——整篇 dump 会把 Findings/Proposals
    当正文喂给模型，抽取器立刻自证（05 §9/07 §4.3 的独立性就没了）。"""
    d = draft_from_dump("sampling/v4c1/ch02.md")
    assert "夏日的午后" in d
    assert "## Draft" not in d and "## Proposals" not in d
    assert "HARD " not in d and " Findings " not in d


def test_draft_section_keeps_paragraph_structure_for_segmentation():
    """分段靠空行；剥掉空行会让 W1 的分段器只能整章一段。"""
    d = draft_from_dump("sampling/v4c1/ch02.md")
    assert "\n\n" in d and len(d) > 500


def test_frozen_corpus_reports_missing_chapters_loudly():
    """缺章必须显式炸，不静默跳过——静默跳过 = 分母失真，一致率会被悄悄抬高。"""
    import pytest
    with pytest.raises(FileNotFoundError):
        frozen_corpus(["v4c1"], [99])


def test_replay_writes_a_contract_instr_cli_can_consume(tmp_path):
    """1.txt 第三件事：run JSON 能被 instr_cli 吃进去。

    不烧模型调用：直接构造 channel 的返回形状，只验契约与落盘往返。
    """
    from plot_engine.instr_cli import load_run, report
    from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint

    def transport(url, payload, headers, timeout_s):
        return {"choices": [{"message": {"content": "[]"}}], "usage": {
            "prompt_tokens": 10, "completion_tokens": 2}}

    client = LlmClient(LlmRouter(endpoints={
        "extract": ModelEndpoint(model="fake")}), transport=transport)
    data = replay(client, runs=["v4c1"], chapters=[2], lane="local",
                  seg_max_chars=900, seg_overlap=100, log=lambda *a: None)
    # 契约字段齐全（instr_cli 只认这几个）
    for k in ("chapters", "malformed", "tokens", "recall", "instr", "ruler", "lane"):
        assert k in data, k
    assert data["instr"] == "instr-v2-local"
    assert data["ruler"].startswith("v3.5")

    out = write_run(data, tmp_path / "r1.json")
    loaded = load_run(out)
    rep = report([loaded, loaded], n_chapters=1)          # 同语料两遍 ⇒ 一致率应 1.0
    assert rep["jaccard_med"] == 1.0
    assert rep["chapters"] == 1                            # 章号 key 必须是 int（JSON 往返后）
    # 空回被正确计为章级废卷 ⇒ gate 不过。这是**对的行为**：W5 门槛本来就要求 0 废章，
    # 试跑用 fake transport 回 [] 不是模型产出，不该假装通过。
    assert rep["gate"]["pass"] is False
    assert rep["waste_chapters"] == [2]
    assert rep["instr"] == "instr-v2-local"


def test_replay_never_touches_a_dump_directory(tmp_path):
    """硬隔离：runner 只读 dump、只写 --out。写进 dump 会污染 readout 的 E2 读数。"""
    from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint

    before = {p.name for p in Path("sampling/v4c1").glob("*")}
    client = LlmClient(LlmRouter(endpoints={
        "extract": ModelEndpoint(model="fake")}),
        transport=lambda *a: {"choices": [{"message": {"content": "[]"}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    replay(client, runs=["v4c1"], chapters=[2], log=lambda *a: None)
    after = {p.name for p in Path("sampling/v4c1").glob("*")}
    assert before == after, "runner 动了冻结 dump 目录：读数会混账"
