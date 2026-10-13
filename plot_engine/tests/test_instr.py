"""P0 instr-fix-01 验收（任务单 info.txt W1-W6）。全离线：注入 fake transport。"""
from plot_engine import instr as I
from plot_engine.instr import InstrFlags
from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint
from plot_engine.llm_extract import make_laned_channel, make_segmented_llm_channel
from plot_engine.llm_extract import parse_proposals
from plot_engine.models.contract import ChapterContract, ChapterHook
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"


def _state(**kw):
    chars = {"char_000001": Character(
        character_id="char_000001", name="张三", aliases=["三哥"],
        status="alive", introduced_at_chapter=1, epoch=EPOCH)}
    if kw.get("ambiguous"):
        chars["char_000002"] = Character(
            character_id="char_000002", name="李四", aliases=["三哥"],
            status="alive", introduced_at_chapter=1, epoch=EPOCH)
    return StoryState(
        story_id="s1", chapter_no=9, version=9, epoch=EPOCH, characters=chars,
        facts={"fact_000001": Fact(
            fact_id="fact_000001", fact_type="existence", proposition="印泥已干",
            canonical_form="c1", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)},
        state_hash="0" * 64)


def _contract():
    return ChapterContract(
        chapter_no=10, arc_id="arc_003", epoch=EPOCH, story_goal="g",
        story_goal_type="revelation", knowledge_allowed=["fact_000001"],
        knowledge_forbidden=[], ending=ChapterHook(
            type="cliffhanger", strength=800, description="d"),
        created_at="2026-10-09T00:00:00Z")


def _client(replies, model="m"):
    it = iter(replies)
    last = []

    def transport(url, payload, headers, timeout_s):
        try:
            out = next(it)
        except StopIteration:
            # 分段 + 修复环的调用次数取决于分段数，超出预置回复时重复最后一条，
            # 测试钉的是「管道行为」而不是「回复序列长度」。
            out = last[-1]
        last.append(out)
        return out
    return LlmClient(LlmRouter(endpoints={"extract": ModelEndpoint(model=model)}),
                     transport=transport)


def _reply(content, finish="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def test_w1_split_windows_and_overlap():
    paras = ["第%d段。" % i + "字" * 400 for i in range(10)]
    segs = I.split_draft_segments("\n\n".join(paras))
    assert len(segs) >= 2
    assert segs[0].para_start == 1
    assert all(s.char_span[1] > s.char_span[0] for s in segs)


def test_w1_empty_draft_zero_segments():
    assert I.split_draft_segments("   ") == []


def test_w1_scene_marker_forces_new_segment():
    draft = "甲段。\n\n<!-- scene 2 -->\n\n乙段。"
    assert len(I.split_draft_segments(draft)) >= 2


def test_w1_merge_dedups_by_event_actor_fact():
    ch = make_segmented_llm_channel(_client([
        _reply('[{"event_type": "OBSERVES", "actor": "char_000001", '
               '"payload": {"fact_id": "fact_000001"}, "paragraph": 1}]'),
        _reply('[{"event_type": "OBSERVES", "actor": "char_000001", '
               '"payload": {"fact_id": "fact_000001"}, "paragraph": 1}]'),
    ]), seg_max_chars=60, seg_overlap=10)
    paras = ["甲%d。" % i + "字" * 30 for i in range(4)]
    props = ch("\n\n".join(paras), None, _contract(), _state())
    assert len(props) == 1        # 4 段各回同一条，跨段确定性合并去重
    assert ch.segments_run == 4
    assert props[0].seq == 0


def test_w2_repair_loop_recovers_one_bad_reply():
    ch = make_segmented_llm_channel(_client([
        _reply("我不确定。"),
        _reply('[{"event_type": "OBSERVES", "actor": "char_000001", '
               '"payload": {"fact_id": "fact_000001"}}]'),
    ]))
    props = ch("张三凝视印章。", None, _contract(), _state())
    assert len(props) == 1 and ch.repaired == 1


def test_w2_segment_failure_degrades_only_that_segment():
    ch = make_segmented_llm_channel(_client([
        _reply("###"),
        _reply("###"),
        _reply('[{"event_type": "OBSERVES", "actor": "char_000001", '
               '"payload": {"fact_id": "fact_000001"}}]'),
        _reply('[{"event_type": "OBSERVES", "actor": "char_000001", '
               '"payload": {"fact_id": "fact_000001"}}]'),
    ]), seg_max_chars=60, seg_overlap=10)
    paras = ["乙%d。" % i + "字" * 30 for i in range(4)]
    props = ch("\n\n".join(paras), None, _contract(), _state())
    assert len(props) == 1
    assert any(b["reason"] == "segment_failed" for b in ch.malformed)
    assert not any(b["reason"] == "malformed_reply" for b in ch.malformed)
    assert len(ch.missing_windows) == 1 and "char_span" in ch.missing_windows[0]


def test_w3_alias_name_maps_to_id():
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "三哥", '
        '"payload": {"fact_id": "fact_000001"}}]', 10, _state(),
        resolve_aliases=True)
    assert len(props) == 1 and props[0].actor == "char_000001"
    assert any(b["reason"] == "alias_resolved" for b in bad)


def test_w3_unknown_name_rejected_with_reason_no_client():
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "王五", '
        '"payload": {"fact_id": "fact_000001"}}]', 10, _state(),
        resolve_aliases=True)
    assert props == []
    assert bad and bad[-1]["reason"] == "alias_unknown" and bad[-1].get("drop")


def test_w3_ambiguous_without_followup_records_polysemy():
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "三哥", '
        '"payload": {"fact_id": "fact_000001"}}]', 10, _state(ambiguous=True),
        resolve_aliases=True)
    assert props == []
    assert bad and bad[-1]["reason"] == "alias_ambiguous"


def test_w3_followup_resolves_unknown_name():
    follow = _client([_reply("char_000001")])
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "王五", '
        '"payload": {"fact_id": "fact_000001"}}]', 10, _state(),
        resolve_aliases=True, alias_client=follow)
    assert len(props) == 1 and props[0].actor == "char_000001"


def test_w3_hallucinated_id_keeps_old_unknown_id_path():
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "char_999999", '
        '"payload": {"fact_id": "fact_000001"}}]', 10, _state(),
        resolve_aliases=True)
    assert props == [] and bad[0]["reason"] == "unknown_id"


def test_w4a_missing_fixed_point_defaulted_in_code():
    props, bad = parse_proposals(
        '[{"event_type": "BELIEVES", "actor": "char_000001", '
        '"payload": {"fact_id": "fact_000001"}}]', 10, _state(),
        code_defaults=True)
    assert len(props) == 1
    assert props[0].payload["belief_strength"] == 700
    assert any(b["reason"] == "defaulted_fixed_point" for b in bad)


def test_w4a_wrong_typed_fixed_point_still_dropped():
    props, bad = parse_proposals(
        '[{"event_type": "BELIEVES", "payload": {"fact_id": "fact_000001", '
        '"belief_strength": "很高"}}]', 10, _state(), code_defaults=True)
    assert props == []


def test_w4b_prompt_has_no_default_sentence():
    from plot_engine.llm_extract import extract_prompt
    system = extract_prompt("正文。", None, _contract(), _state())[0]["content"]
    assert "默认 700" not in system


def test_w5_gate_and_upgrade_path():
    from plot_engine.instr_measure import double_run_report
    from plot_engine.models.proposal import EventProposal

    def mk():
        return EventProposal(
            proposed_event_type="OBSERVES", actor="char_000001", chapter=10,
            seq=0, payload={"fact_id": "fact_000001"}, source_ref="para:1",
            extraction_method="llm", extraction_confidence=1000)
    rep = double_run_report(run_a={10: [mk()]}, run_b={10: [mk()]})
    assert rep["jaccard_med"] == 1.0 and rep["gate"]["pass"]
    assert rep["upgrade_path"] == "pass:open_v4d_baseline"


def test_w5_junk_replay():
    from plot_engine.instr_measure import replay_junk
    import json
    import tempfile
    from pathlib import Path
    junk = [{"reason": "malformed_reply", "raw": "xxx", "chapter": 9}]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "_junk.json"
        p.write_text(json.dumps(junk), encoding="utf-8")
        rep = replay_junk(str(p))
    assert rep["total"] == 1 and rep["pass"]


def test_w6_lanes_share_pipeline_and_stamp_differs():
    good = ('[{"event_type": "OBSERVES", '
            '"payload": {"fact_id": "fact_000001"}}]')
    local = _client([_reply(good)])
    cloud = _client([_reply(good)], model="cloud-x")
    chl = make_laned_channel(local, cloud, lane="local")
    chc = make_laned_channel(local, cloud, lane="cloud")
    assert chl.instr_version == "instr-v2-local"
    assert chc.instr_version == "instr-v2-cloud"
    assert len(chl("正文。", None, _contract(), _state())) == 1
    assert len(chc("正文。", None, _contract(), _state())) == 1
    assert chc.lane_identity["model"] == "cloud-x"
    assert "provider" in chc.lane_identity and "temperature" in chc.lane_identity


def test_w6_lane_decision_rule():
    assert I.decide_lane({"recall": 0.5, "jaccard_med": 0.9},
                         {"recall": 0.7, "jaccard_med": 0.9}) == \
        "cloud_default_local_fallback"
    assert I.decide_lane({"recall": 0.7, "jaccard_med": 0.9},
                         {"recall": 0.7, "jaccard_med": 0.9}) == \
        "local_default_cloud_per_chapter_fallback"


def test_flags_rollback_segmentation_off():
    ch = make_segmented_llm_channel(_client([
        _reply('[{"event_type": "OBSERVES", '
               '"payload": {"fact_id": "fact_000001"}}]'),
    ]), flags=InstrFlags(segmentation=False))
    assert len(ch("甲。\n\n乙。", None, _contract(), _state())) == 1


def test_instr_cli_reports_two_and_four_runs(tmp_path):
    """W6 CLI：2 份 → W5 波动报告；4 份 → 2×2 对表 + 车道决策。"""
    import json
    from pathlib import Path
    from plot_engine.instr_cli import load_run, report

    def dump(name, types, recall, tokens=600):
        (Path(tmp_path) / name).write_text(json.dumps({
            "chapters": {"1": [{"type": t, "actor": "char_000001",
                                "target": "fact_000001",
                                "payload": {"fact_id": "fact_000001"}} for t in types]},
            "malformed": [], "tokens": tokens, "recall": recall}), encoding="utf-8")

    dump("l1.json", ["OBSERVES"], 0.5)
    dump("l2.json", ["OBSERVES"], 0.5)
    dump("c1.json", ["OBSERVES", "SUSPECTS"], 0.9)
    dump("c2.json", ["OBSERVES", "SUSPECTS"], 0.9)
    r2 = report([load_run(tmp_path / "l1.json"), load_run(tmp_path / "l2.json")],
                probe_chapters=[1], n_chapters=1)
    assert r2["jaccard_med"] == 1.0 and r2["gate"]["pass"]
    r4 = report([load_run(tmp_path / "l1.json"), load_run(tmp_path / "l2.json"),
                 load_run(tmp_path / "c1.json"), load_run(tmp_path / "c2.json")],
                n_chapters=1)
    assert r4["decision"] == "cloud_default_local_fallback"
    assert r4["local"]["instr"] == "instr-v2-local"
    assert r4["cloud"]["recall"] == 0.9
    assert r4["local"]["cost_per_chapter"] == 600.0


def test_readout_waste_and_consistency_columns_missing_when_unmeasured(tmp_path):
    """没测 ≠ 0：旧跑法无 _junk/fluctuation 时两列记 "-"，不硬填 0。"""
    from plot_engine.readout import _consistency, _waste_rate
    dump = tmp_path / "old" / "dump"
    dump.mkdir(parents=True)
    (dump / "ch01.md").write_text("# Chapter 1 — status=OK\ntrace_status=OK\n",
                                  encoding="utf-8")
    assert _waste_rate(tmp_path / "old", dump) == "-"
    assert _consistency(tmp_path / "old") == "-"


def test_readout_waste_counts_only_chapter_level_failures(tmp_path):
    """段级 segment_failed/segment_unparsable 不废全章，不进章级废卷率。"""
    import json
    from plot_engine.readout import _waste_rate
    dump = tmp_path / "r" / "dump"
    dump.mkdir(parents=True)
    for i in (1, 2, 3):
        (dump / f"ch{i:02d}.md").write_text("# status=OK\ntrace_status=OK\n",
                                            encoding="utf-8")
    (dump / "_junk.json").write_text(json.dumps([
        {"reason": "segment_failed", "chapter": 1, "seg": 0},
        {"reason": "segment_unparsable", "chapter": 1, "seg": 0},
        {"reason": "chapter_empty", "chapter": 2},
        {"reason": "over_cap", "chapter": 3},
    ]), encoding="utf-8")
    assert _waste_rate(tmp_path / "r", dump) == "33%"   # 只 chapter_empty 计 1/3
