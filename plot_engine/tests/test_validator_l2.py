# Level-2 结构化规则（05 §4 H2/H5）+ markup M-rules（07 §4.4 M1–M5）
from plot_engine.markup import parse_markup
from plot_engine.models.contract import ChapterContract
from plot_engine.models.ledger import KnowledgeEntry
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.validator import _run_l2, _simulate

EPOCH = "epoch_0"


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", current_location="loc_000012", introduced_at_chapter=1, epoch=EPOCH)},
        locations={}, items={}, realms={}, abilities={},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                canonical_form="c", narrative_truth="unknown", objective_truth="unknown",
                defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000002", "fact_000003", "fact_000009")},
        knowledge_ledger=[KnowledgeEntry(character_id="char_000001", fact_id="fact_000009",
            knowledge_state="known", strength=900, source_event_id="evt_00000001_000",
            acquired_at_chapter=1, last_updated_chapter=1, epoch=EPOCH)],
        state_hash="0" * 64)


def _contract(**over):
    base = dict(chapter_no=47, arc_id="arc_003", epoch=EPOCH,
                story_goal="查明叛徒", story_goal_type="revelation",
                must_change=[], must_not_change=[], required_events=[], forbidden_events=[],
                knowledge_allowed=[], knowledge_forbidden=[], reader_signals=[],
                plot_progress={}, tension_target=500,
                ending={"type": "cliffhanger", "strength": 800, "description": "d"},
                derived_from=[], created_at="2026-10-08T00:00:00Z")
    return ChapterContract(**{**base, **over})


def _p(**over):
    base = dict(proposed_event_type="OBSERVES", actor="char_000001", target="fact_000001",
                chapter=47, seq=0, payload={"fact_id": "fact_000001"},
                source_ref="x", extraction_method="rule", extraction_confidence=1000)
    return EventProposal(**{**base, **over})


def _l2(proposals, contract, markup=None, state=None):
    st = state or _state()
    mk = markup if markup is not None else parse_markup(
        "<!-- hook: cliffhanger strength=800 -->")
    sim = _simulate(st, proposals, EPOCH)
    return _run_l2(sim, st, proposals, contract=contract, markup=mk)


def _codes(f):
    return {x.rule_id for x in f}


# --- H2 ---
def test_h2_1_forbidden_known_in_pre():
    c = _contract(knowledge_forbidden=["fact_000009"])
    assert "H2.1" in _codes(_l2([], c))


def test_h2_2_must_change_knowledge_missing():
    c = _contract(must_change=[{"character_id": "char_000001", "field": "knowledge",
        "operation": "add", "target": "fact_000001", "expected_value": "known"}])
    assert "H2.2" in _codes(_l2([], c))


def test_h2_2_satisfied():
    c = _contract(must_change=[{"character_id": "char_000001", "field": "knowledge",
        "operation": "add", "target": "fact_000001", "expected_value": "known"}])
    assert "H2.2" not in _codes(_l2([_p()], c))


def test_h5_6_allowed_not_established():
    c = _contract(knowledge_allowed=["fact_000001"],
        must_change=[{"character_id": "char_000001", "field": "knowledge",
            "operation": "add", "target": "fact_000001", "expected_value": "known"}])
    assert "H5.6" in _codes(_l2([], c))


# --- H5 events ---
def test_h5_1_required_missing():
    c = _contract(required_events=[{"event_type": "OBSERVES", "description": "d", "minimum_count": 1}])
    assert "H5.1" in _codes(_l2([], c))


def test_h5_1_satisfied():
    c = _contract(required_events=[{"event_type": "OBSERVES", "description": "d", "minimum_count": 1}])
    assert "H5.1" not in _codes(_l2([_p()], c))


def test_h5_2_forbidden_present():
    c = _contract(forbidden_events=[{"event_type": "REVEALS", "description": "d", "reason": "r"}])
    p = _p(proposed_event_type="REVEALS", payload={"fact_id": "fact_000002", "new_narrative_truth": "true"})
    assert "H5.2" in _codes(_l2([p], c))


def test_h5_3_w1_location_change_missing():
    c = _contract(must_change=[{"character_id": "char_000001", "field": "location",
        "operation": "update", "target": "loc_000013"}])
    assert "H5.3" in _codes(_l2([], c))


def test_h5_3_w1_satisfied():
    c = _contract(must_change=[{"character_id": "char_000001", "field": "location",
        "operation": "update", "target": "loc_000013"}])
    p = _p(proposed_event_type="CHANGES", payload={"field": "location", "new_value": "loc_000013"})
    assert "H5.3" not in _codes(_l2([p], c))


# H5.3 的实现事件集必须按 field 分表（10 §4.3）：knowledge 与 belief 不共用，
# 且 belief 侧要认 DOUBTS。合并集合会让 BELIEVES 冒充 knowledge 跃迁（真实模型第 1 次
# 采样里 ch02/ch08/ch10 就是这么从 FAIL 变成 OK 的）。
_KN = {"character_id": "char_000001", "field": "knowledge",
       "operation": "add", "target": "fact_000001", "expected_value": "known"}
_BL = {"character_id": "char_000001", "field": "belief",
       "operation": "add", "target": "fact_000001", "expected_value": "believes"}


_BELIEF = {"fact_id": "fact_000001", "belief_strength": 700}


def test_h5_3_knowledge_not_implemented_by_belief_event():
    assert "H5.3" in _codes(_l2([_p(proposed_event_type="BELIEVES", payload=_BELIEF)],
                                 _contract(must_change=[_KN])))


def test_h5_3_belief_implemented_by_doubts():
    assert "H5.3" not in _codes(_l2([_p(proposed_event_type="DOUBTS", payload=_BELIEF)],
                                    _contract(must_change=[_BL])))


def test_h5_3_belief_not_implemented_by_knowledge_event():
    assert "H5.3" in _codes(_l2([_p()], _contract(must_change=[_BL])))


def test_h5_3_knowledge_still_implemented_by_observes():
    assert "H5.3" not in _codes(_l2([_p()], _contract(must_change=[_KN])))


# --- 1B：knowledge 的实现判与 H2.2 同谓词（有实现事件且终态达档）---
def test_h5_3_and_h2_2_no_longer_mutually_exclusive():
    """反例：IS_TOLD 在旧类型表里「实现」了 expected known 的 Δ（H5.3 绿），
    终态却只有 believed（H2.2 红）——43 章裁定 ③ 族 rank-cap 章的互斥两尺。
    对齐后同一失败两把尺同判。"""
    told = _p(proposed_event_type="IS_TOLD", payload={
        "fact_id": "fact_000001", "trust_level": 900, "message_strength": 900})
    codes = _codes(_l2([told], _contract(must_change=[_KN])))
    assert "H5.3" in codes and "H2.2" in codes


def test_h5_3_is_told_implements_believed_delta():
    """正例：IS_TOLD 上限 believed，believed 的 Δ 达档 ⇒ H5.3 不再报。"""
    kn = {**_KN, "expected_value": "believed"}
    told = _p(proposed_event_type="IS_TOLD", payload={
        "fact_id": "fact_000001", "trust_level": 900, "message_strength": 900})
    codes = _codes(_l2([told], _contract(must_change=[kn])))
    assert "H5.3" not in codes and "H2.2" not in codes


def test_h5_3_belief_branch_untouched_by_rank_rule():
    """rank 对齐只管 knowledge：belief Δ 仍按类型+actor+fact 判（DOUBTS 兑现 doubts）。"""
    bl = {"character_id": "char_000001", "field": "belief", "operation": "add",
          "target": "fact_000001", "expected_value": "doubts"}
    p = _p(proposed_event_type="DOUBTS", payload={"fact_id": "fact_000001",
                                                  "belief_strength": 400})
    assert "H5.3" not in _codes(_l2([p], _contract(must_change=[bl])))


def test_h5_7_keeps_wide_establish_set():
    """H5.7 用宽集合是对的（BELIEVES 一个 forbidden fact 确实算建立），分表不得动它。"""
    c = _contract(knowledge_forbidden=["fact_000001"])
    assert "H5.7" in _codes(_l2([_p(proposed_event_type="BELIEVES", payload=_BELIEF)], c))


def test_h5_4_must_not_change_violated():
    c = _contract(must_not_change=[{"character_id": "char_000001", "field": "status",
        "operation": "update", "target": "status"}])
    p = _p(proposed_event_type="CHANGES", payload={"field": "status", "new_value": "dead"})
    assert "H5.4" in _codes(_l2([p], c))


def test_h5_7_forbidden_established():
    c = _contract(knowledge_forbidden=["fact_000002"])
    p = _p(payload={"fact_id": "fact_000002"})
    assert "H5.7" in _codes(_l2([p], c))


# --- H5.5 hook markup ---
def test_h5_5_hook_absent():
    c = _contract(ending={"type": "cliffhanger", "strength": 800, "description": "d"})
    assert "H5.5" in _codes(_l2([], c, markup=parse_markup("普通正文")))


def test_h5_5_hook_wrong_type():
    c = _contract(ending={"type": "cliffhanger", "strength": 800, "description": "d"})
    mk = parse_markup("<!-- hook: revelation strength=800 -->")
    assert "H5.5" in _codes(_l2([], c, markup=mk))


def test_h5_5_outside_last3():
    c = _contract(ending={"type": "cliffhanger", "strength": 800, "description": "d"})
    mk = parse_markup("<!-- hook: cliffhanger strength=800 -->\n\na\n\nb\n\nc\n\nd")
    assert "H5.5" in _codes(_l2([], c, markup=mk))


def test_h5_5_strength_range():
    c = _contract(ending={"type": "cliffhanger", "strength": 800, "description": "d"})
    mk = parse_markup("<!-- hook: cliffhanger strength=1001 -->")
    assert "H5.5" in _codes(_l2([], c, markup=mk))


def test_h5_5_none_still_requires_anno():
    c = _contract(ending={"type": "none", "strength": 0, "description": "d"})
    assert "H5.5" in _codes(_l2([], c, markup=parse_markup("正文")))


def test_h5_5_ok():
    c = _contract(ending={"type": "cliffhanger", "strength": 800, "description": "d"})
    mk = parse_markup("正文\n\n<!-- hook: cliffhanger strength=800 -->")
    assert "H5.5" not in _codes(_l2([], c, markup=mk))


# --- H2.3 markup↔proposal ---
def test_h2_3_m2_anno_without_proposal():
    c = _contract()
    mk = parse_markup("正文\n\n<!-- reader_learns: fact_000003 -->\n\n<!-- hook: cliffhanger strength=800 -->")
    assert "H2.3" in _codes(_l2([], c, markup=mk))


def test_h2_3_ok_matched():
    c = _contract()
    mk = parse_markup("正文\n\n<!-- reader_learns: fact_000003 -->\n\n<!-- hook: cliffhanger strength=800 -->")
    rp = _p(seq=5, proposed_event_type="READER_LEARNS", target="fact_000003",
            payload={"fact_id": "fact_000003"}, extraction_method="markup")
    assert "H2.3" not in _codes(_l2([rp], c, markup=mk))


def test_h2_3_m3_proposal_without_anno_is_soft():
    c = _contract()
    mk = parse_markup("正文\n\n<!-- hook: cliffhanger strength=800 -->")
    rp = _p(seq=5, proposed_event_type="READER_LEARNS", target="fact_000003",
            payload={"fact_id": "fact_000003"}, extraction_method="rule")
    f = [x for x in _l2([rp], c, markup=mk) if x.rule_id == "H2.3"]
    assert f and f[0].severity == "soft"


def test_signal_unhit_is_soft():
    c = _contract(reader_signals=[{"fact_id": "fact_000003", "target_state": "knows"}])
    f = [x for x in _l2([], c) if x.rule_id == "SIGNAL_UNHIT"]
    assert f and f[0].severity == "soft"


# --- H9 伏笔生命周期（WP-A 设计稿 §4，一正一反）---
from plot_engine.models.ledger import ForeshadowingEntry  # noqa: E402


def _fs(**over):
    base = dict(foreshadow_id="fsh_000001", fact_id="fact_000003", lifecycle="planted",
                strength=600, planted_chapter=46, due_by_chapter=60,
                source_event_id="evt_00000046_000", last_updated_chapter=46, epoch=EPOCH)
    return ForeshadowingEntry(**{**base, **over})


def _st_fs(*entries):
    return _state().model_copy(update={"foreshadowing": list(entries)})


def test_h9_1_overdue_hard():
    f = _l2([], _contract(), state=_st_fs(_fs(due_by_chapter=46, last_updated_chapter=46)),)
    # due=46 < ch=47 逾期；last_updated 同步设为 46 以免 H9.3（diff=1<5）串扰
    assert "H9.1" in _codes(f)


def test_h9_1_not_overdue_or_expired_no_fire():
    st = _st_fs(_fs(due_by_chapter=47, planted_chapter=46))
    assert "H9.1" not in _codes(_l2([], _contract(), state=st))
    st2 = _st_fs(_fs(due_by_chapter=46, lifecycle="expired"))
    assert "H9.1" not in _codes(_l2([], _contract(), state=st2))


def test_h9_2_sourceless_paid_hard():
    p = _p(proposed_event_type="FORESHADOWING_PAID", target=None,
           payload={"foreshadow_id": "fsh_000009"})
    assert "H9.2" in _codes(_l2([p], _contract(), state=_st_fs(_fs())))


def test_h9_2_set_then_paid_in_batch_no_fire():
    s = _p(proposed_event_type="FORESHADOWING_SET",
           payload={"foreshadow_id": "fsh_000002", "fact_id": "fact_000003",
                    "due_by_chapter": 60, "strength": 500})
    pd = _p(seq=1, proposed_event_type="FORESHADOWING_PAID",
            payload={"foreshadow_id": "fsh_000002"})
    f = _l2([s, pd], _contract(), state=_st_fs())
    assert "H9.2" not in _codes(f)


def test_h9_3_stalled_planted_soft():
    st = _st_fs(_fs(planted_chapter=41, last_updated_chapter=41, due_by_chapter=60))
    f = [x for x in _l2([], _contract(), state=st) if x.rule_id == "H9.3"]
    assert f and f[0].severity == "soft"


def test_h9_3_fresh_or_hinted_no_fire():
    st = _st_fs(_fs(planted_chapter=46, due_by_chapter=60))
    assert "H9.3" not in _codes(_l2([], _contract(), state=st))
    st2 = _st_fs(_fs(planted_chapter=41, due_by_chapter=60,
                     lifecycle="hinted", last_updated_chapter=45))
    assert "H9.3" not in _codes(_l2([], _contract(), state=st2))


def test_h9_4_shallow_paid_observation():
    st = _st_fs(_fs(planted_chapter=44, lifecycle="paid", paid_chapter=46))
    f = [x for x in _l2([], _contract(), state=st) if x.rule_id == "H9.4"]
    assert f and f[0].severity == "observation"


def test_h9_4_deep_paid_no_fire():
    st = _st_fs(_fs(planted_chapter=40, lifecycle="paid", paid_chapter=46))
    assert "H9.4" not in _codes(_l2([], _contract(), state=st))


def test_h53_evidence_is_full_item_key():
    """06 §4.2 分诊靠条目全键认出「同一条 must_change 补写后再失败」（材料四）：
    field 粒度会把同 field 两条 Δ 混成同一笔债。"""
    c = _contract(must_change=[{"character_id": "char_000001", "field": "knowledge",
        "operation": "add", "target": "fact_000001", "expected_value": "known"}])
    f = [x for x in _l2([], c) if x.rule_id == "H5.3"][0]
    assert f.evidence == "char_000001|knowledge|fact_000001|known"
