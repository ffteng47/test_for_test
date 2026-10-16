# Arc → Chapter Contract 派生（04 §4.3 D1–D9）。协议只规定了「能派生的必须派生」，
# 推不出来的作者意图（story_goal / must_change / ending）显式来自 Arc 的 reader_beats 槽位
# （04 §3.1，SOFT 元数据），生成器绝不编造。
import pytest

from plot_engine.derive import (ArcConflict, NoChapterIntent, derive_chapter_contract)
from plot_engine.models.contract import ArcContract
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState
from plot_engine.validator import Validator

EPOCH = "epoch_0"
NOW = "2026-10-09T00:00:00Z"
CAST = "char_000001"


def _intent(ch: int, **over) -> dict:
    base = {
        "chapter_no": ch, "story_goal": "张三查印章", "story_goal_type": "revelation",
        "ending": {"type": "cliffhanger", "strength": 800, "description": "d"},
        "must_change": [{"character_id": CAST, "field": "knowledge", "operation": "add",
                         "target": "fact_000003", "expected_value": "known"}],
        # 04 §4.2：Δ 必须被对应 Event 实现 ⇒ 意图自带的 must_change 也要自带实现事件
        "required_events": [{"event_type": "OBSERVES", "description": "张三亲眼验出印章",
                             "actors_involved": [CAST]}],
    }
    base.update(over)
    return base


def _arc(gates=(), tps=(), beats=None, curve=None) -> ArcContract:
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(1, 10),
        tension_curve=[600] * 10 if curve is None else curve,
        turning_points=[dict(t) for t in tps],
        knowledge_gates=[dict(g) for g in gates],
        reader_beats=[_intent(c) for c in range(1, 11)] if beats is None else list(beats),
        created_at=NOW)


def _state() -> StoryState:
    return StoryState(
        story_id="s1", chapter_no=0, version=0, epoch=EPOCH,
        characters={CAST: Character(character_id=CAST, name="张三", status="alive",
                                    introduced_at_chapter=1, epoch=EPOCH)},
        locations={"loc_000012": {"location_id": "loc_000012", "name": "藏宝阁",
                                  "introduced_at_chapter": 1, "epoch": EPOCH}},
        facts={fid: Fact(fact_id=fid, fact_type="existence", proposition="p",
                         canonical_form="c", narrative_truth="unknown",
                         objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)
               for fid in ("fact_000001", "fact_000002", "fact_000003")},
        state_hash="0" * 64)


def _types(c) -> set:
    return {r.event_type for r in c.required_events}


# --- D1 / 作者意图缺失 -------------------------------------------------------
def test_d1_chapter_outside_arc_range_is_rejected():
    with pytest.raises(ValueError):
        derive_chapter_contract(_arc(), 11, _state(), created_at=NOW)


def test_no_authored_intent_never_invents_a_story_goal():
    # 编造 story_goal 会让「契约满足」变成模型自证；缺意图必须响亮失败。
    with pytest.raises(NoChapterIntent):
        derive_chapter_contract(_arc(beats=[]), 1, _state(), created_at=NOW)


# --- D3：turning_point 的事件类型必须进 required_events -----------------------
def test_d3_turning_point_chapter_gains_its_event_types():
    arc = _arc(tps=[{"chapter": 3, "type": "revelation", "description": "印泥是干的",
                     "required_event_types": ["OBSERVES", "INFERS"]}],
               beats=[_intent(c, must_change=[], required_events=[]) for c in range(1, 11)])
    hit = derive_chapter_contract(arc, 3, _state(), created_at=NOW)
    miss = derive_chapter_contract(arc, 2, _state(), created_at=NOW)
    assert {"OBSERVES", "INFERS"} <= _types(hit)
    assert _types(miss) == set()
    assert "arc_003.turning_points[3]" in hit.derived_from          # C6 可追溯


# --- D4/D5：gate 到期与否决定允许/禁止 --------------------------------------
def test_d4_d5_same_gate_flips_at_allowed_after_chapter():
    arc = _arc(gates=[{"fact_id": "fact_000002", "allowed_after_chapter": 5,
                       "reveal_stage_target": "confirmed"}])
    before = derive_chapter_contract(arc, 4, _state(), created_at=NOW)
    after = derive_chapter_contract(arc, 5, _state(), created_at=NOW)
    assert "fact_000002" in before.knowledge_forbidden
    assert "fact_000002" not in before.knowledge_allowed
    assert "fact_000002" in after.knowledge_allowed
    assert "fact_000002" not in after.knowledge_forbidden
    assert not (set(after.knowledge_allowed) & set(after.knowledge_forbidden))   # H7.4/I7


def test_d4_gate_restricted_to_offstage_character_neither_allows_forbids():
    # D4 的字面条件：本章角色不含 gate.allowed_characters → 不加入 allowed；
    # 但已到期也不该进 forbidden（那是 D5 的未到期语义）。
    arc = _arc(gates=[{"fact_id": "fact_000002", "allowed_after_chapter": 1,
                       "allowed_characters": ["char_000002"],
                       "reveal_stage_target": "confirmed"}])
    c = derive_chapter_contract(arc, 3, _state(), created_at=NOW)
    assert "fact_000002" not in c.knowledge_allowed
    assert "fact_000002" not in c.knowledge_forbidden


# --- D6：到期未揭示的 gate 必须变成 REVEALS 硬要求 ---------------------------
def test_d6_overdue_gate_adds_reveals_before_and_not_after():
    arc = _arc(gates=[{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                       "must_reveal_by_chapter": 3, "reveal_stage_target": "confirmed"}])
    early = derive_chapter_contract(arc, 2, _state(), created_at=NOW)
    late = derive_chapter_contract(arc, 4, _state(), created_at=NOW)
    assert "REVEALS" not in _types(early)
    assert "REVEALS" in _types(late)
    reveal = next(r for r in late.required_events if r.event_type == "REVEALS")
    assert "fact_000001" in reveal.description
    assert "arc_003.knowledge_gates[fact_000001]" in late.derived_from


def test_overdue_reveal_colliding_with_authored_forbidden_is_arc_error():
    # 06 §4.3：Contract 无法满足且症状源于 Arc → 回 Arc 层重规划，
    # 生成器没有权力自己把 gate 或 forbidden 删掉来「让实验通过」。
    arc = _arc(gates=[{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                       "must_reveal_by_chapter": 3, "reveal_stage_target": "confirmed"}],
               beats=[_intent(c, forbidden_events=[
                   {"event_type": "REVEALS", "description": "别说破", "reason": "悬念"}])
                   for c in range(1, 11)])
    with pytest.raises(ArcConflict):
        derive_chapter_contract(arc, 4, _state(), created_at=NOW)


def test_two_gates_disagreeing_on_the_same_fact_is_arc_error():
    arc = _arc(gates=[{"fact_id": "fact_000002", "allowed_after_chapter": 8,
                       "reveal_stage_target": "confirmed"},
                      {"fact_id": "fact_000002", "allowed_after_chapter": 1,
                       "must_reveal_by_chapter": 2, "reveal_stage_target": "confirmed"}])
    with pytest.raises(ArcConflict):
        derive_chapter_contract(arc, 3, _state(), created_at=NOW)


# --- D9：reader_signal 只能指向已到期的 fact --------------------------------
def test_d9_reader_signal_follows_gate_stage_and_expiry():
    arc = _arc(gates=[{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                       "reveal_stage_target": "hinted"},
                      {"fact_id": "fact_000002", "allowed_after_chapter": 5,
                       "reveal_stage_target": "confirmed"},
                      {"fact_id": "fact_000003", "allowed_after_chapter": 1,
                       "reveal_stage_target": "hidden"}])
    c = derive_chapter_contract(arc, 6, _state(), created_at=NOW)
    signals = {s.fact_id: s.target_state for s in c.reader_signals}
    assert signals == {"fact_000001": "hinted", "fact_000002": "knows"}
    early = derive_chapter_contract(arc, 4, _state(), created_at=NOW)
    assert "fact_000002" not in {s.fact_id for s in early.reader_signals}


# --- D9 补：目标态已到达的 fact 不再要信号（E25 reader 类机械重锚的源头）------
def test_d9_signal_dropped_once_reader_reached_target():
    from plot_engine.models.ledger import ReaderKnowledgeEntry
    arc = _arc(gates=[{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                       "reveal_stage_target": "hinted"},
                      {"fact_id": "fact_000002", "allowed_after_chapter": 1,
                       "reveal_stage_target": "confirmed"}])
    st = _state()
    st.reader_ledger = [
        ReaderKnowledgeEntry(fact_id="fact_000001", reader_state="hinted", reader_strength=300,
                             established_at_chapter=2, last_updated_chapter=2,
                             source_event_id="e1", epoch=EPOCH),
        ReaderKnowledgeEntry(fact_id="fact_000002", reader_state="deceived", reader_strength=300,
                             established_at_chapter=2, last_updated_chapter=2,
                             source_event_id="e2", epoch=EPOCH)]
    signals = {s.fact_id: s.target_state
               for s in derive_chapter_contract(arc, 3, st, created_at=NOW).reader_signals}
    assert signals == {"fact_000002": "knows"}   # hinted 已到达 ⇒ 不再逼重锚；deceived 不算到达


# --- D2'：tension_target 取自曲线本章值 -------------------------------------
def test_d2_tension_target_is_this_chapters_curve_value():
    arc = _arc(curve=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
    assert derive_chapter_contract(arc, 3, _state(), created_at=NOW).tension_target == 300


# --- 成品必须过 H7 自校验（生成器不得产出非法契约）--------------------------
@pytest.mark.parametrize("ch", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
def test_every_derived_contract_passes_h7(ch):
    arc = _arc(
        tps=[{"chapter": 3, "type": "revelation", "description": "印泥是干的",
              "required_event_types": ["OBSERVES", "INFERS"]}],
        gates=[{"fact_id": "fact_000001", "allowed_after_chapter": 1,
                "must_reveal_by_chapter": 4, "reveal_stage_target": "confirmed"},
               {"fact_id": "fact_000002", "allowed_after_chapter": 7,
                "reveal_stage_target": "confirmed"},
               {"fact_id": "fact_000003", "allowed_after_chapter": 1,
                "reveal_stage_target": "hinted"}])
    c = derive_chapter_contract(arc, ch, _state(), created_at=NOW)
    res = Validator().validate_contract(c, arc, _state())
    assert [f.rule_id for f in res.hard_violations] == []
    assert [f.rule_id for f in res.soft_warnings] == []      # 曲线逐章对齐 → 无 H7.3


def test_malformed_intent_fails_loudly_not_silently():
    with pytest.raises(NoChapterIntent):
        derive_chapter_contract(
            _arc(beats=[_intent(1, story_goal_type="melodrama")]), 1, _state(), created_at=NOW)


def test_same_arc_same_chapter_same_contract():
    arc = _arc(gates=[{"fact_id": "fact_000002", "allowed_after_chapter": 5,
                       "reveal_stage_target": "confirmed"}])
    a = derive_chapter_contract(arc, 6, _state(), created_at=NOW)
    b = derive_chapter_contract(arc, 6, _state(), created_at=NOW)
    assert a.model_dump() == b.model_dump()


def test_metadata_and_provenance_are_stamped():
    c = derive_chapter_contract(_arc(), 7, _state(), created_at=NOW)
    assert (c.chapter_no, c.arc_id, c.epoch, c.schema_version, c.created_at) == \
        (7, "arc_003", EPOCH, 2, NOW)
    assert c.version == 1
    assert f"arc_003.reader_beats[{c.chapter_no}]" in c.derived_from   # D7/C2：作者意图也记来源


# --- 实现性守卫：must_change 的 Δ 必须有能兑现它的事件类型（04 §4.2 / 10 §4.3）---
def test_unimplementable_must_change_is_arc_error():
    """Arc 给不出实现事件的 Δ 是输入著作错误（06 §4.3）：在契约生成时就响亮失败，
    别让 Writer 去撞三轮修订——那三轮烧的是 token，换来的还是同一句「无实现事件」。"""
    arc = _arc(beats=[_intent(1, required_events=[
        {"event_type": "RELATIONSHIP_CHANGED", "description": "关系变化"}])])
    with pytest.raises(ArcConflict):
        derive_chapter_contract(arc, 1, _state(), created_at=NOW)


def test_guard_uses_the_per_field_implementer_table():
    """分表方向不能反：knowledge 的 Δ 不能用 belief 事件兑现，反之亦然。"""
    belief_only = _intent(1, must_change=[{"character_id": CAST, "field": "belief",
                                           "operation": "add", "target": "fact_000003",
                                           "expected_value": "believes"}],
                          required_events=[{"event_type": "OBSERVES", "description": "o"}])
    with pytest.raises(ArcConflict):
        derive_chapter_contract(_arc(beats=[belief_only]), 1, _state(), created_at=NOW)


# --- D10 强化（1A）：类型在表还不够，档位必须够得着（KNOWLEDGE_RANK_CAP=reducer 上限）---
def test_rank_unreachable_knowledge_delta_is_arc_error():
    """反例＝43 章裁定 ③ 族 r2ch6 形状：钉只有 IS_TOLD（上限 believed），Δ 却期望 known。
    旧守卫看类型交集放行，契约带着永远兑不了的 Δ 烧三轮修订——现在生成时就响亮失败。"""
    arc = _arc(beats=[_intent(1, required_events=[
        {"event_type": "IS_TOLD", "description": "被人告知"}])])
    with pytest.raises(ArcConflict, match="档位上限"):
        derive_chapter_contract(arc, 1, _state(), created_at=NOW)


def test_rank_reachable_delta_passes_the_guard():
    """正例：INFERS（上限 suspected）对 suspected 的 Δ 够得着；belief Δ 不占 rank 守卫。"""
    arc = _arc(beats=[_intent(
        1,
        must_change=[{"character_id": CAST, "field": "knowledge", "operation": "add",
                      "target": "fact_000003", "expected_value": "suspected"},
                     {"character_id": CAST, "field": "belief", "operation": "add",
                      "target": "fact_000003", "expected_value": "believes"}],
        required_events=[{"event_type": "INFERS", "description": "推出结论"},
                         {"event_type": "BELIEVES", "description": "内心确认"}])])
    assert derive_chapter_contract(arc, 1, _state(), created_at=NOW)


# --- D10 越界钉拦截（3A）：禁知/hidden 档 fact 钉成「看见/读到」是结构不可满足 ---
def test_hidden_fact_nailed_as_observes_is_arc_error():
    """反例＝ch10 旧形态（43 章裁定 ① 族）：hidden 档身份事实要求「亲眼看见」，
    Writer 怎么写都缺读者可见性这一味——契约生成时就拦，别再送进修订环。"""
    arc = _arc(gates=[{"fact_id": "fact_000003", "allowed_after_chapter": 1,
                       "reveal_stage_target": "hidden"}],
               beats=[_intent(1, required_events=[
                   {"event_type": "OBSERVES", "description": "OBSERVES fact_000003"}])])
    with pytest.raises(ArcConflict, match="越界钉"):
        derive_chapter_contract(arc, 1, _state(), created_at=NOW)


def test_hearsay_nail_on_hidden_fact_passes():
    """对照正例：只拦「看见/读到」——IS_TOLD 转述进角色的 believed 账，不依赖读者可见性
    （ch10 新钉形态，ladder-v5b）。"""
    arc = _arc(gates=[{"fact_id": "fact_000003", "allowed_after_chapter": 1,
                       "reveal_stage_target": "hidden"}],
               beats=[_intent(
                   1, must_change=[{"character_id": CAST, "field": "knowledge",
                                    "operation": "add", "target": "fact_000003",
                                    "expected_value": "believed"}],
                   required_events=[{"event_type": "IS_TOLD",
                                     "description": "IS_TOLD fact_000003"}])])
    assert derive_chapter_contract(arc, 1, _state(), created_at=NOW)


def test_turning_point_event_also_implements_the_change():
    """D3 补进来的拐点事件同样是实现事件，守卫看的是最终 required_events。"""
    arc = _arc(tps=[{"chapter": 1, "type": "revelation", "description": "d",
                     "required_event_types": ["OBSERVES"]}],
               beats=[_intent(1, required_events=[])])
    assert derive_chapter_contract(arc, 1, _state(), created_at=NOW).required_events


# --- D11 伏笔限期单源（v0.12 裁定 4A）---
from plot_engine.models.ledger import ForeshadowingEntry  # noqa: E402


def _fsh(due, fid="fact_000003"):
    return ForeshadowingEntry(
        foreshadow_id="fsh_000001", fact_id=fid, lifecycle="planted", strength=600,
        planted_chapter=1, due_by_chapter=due, source_event_id="evt_00000001_000",
        last_updated_chapter=1, epoch=EPOCH)


def _arc_g3():
    return _arc(gates=[{"fact_id": "fact_000003", "allowed_after_chapter": 1,
                        "must_reveal_by_chapter": 6, "reveal_stage_target": "confirmed"}])


def test_d11_due_drift_raises_arcconflict():
    st = _state().model_copy(update={"foreshadowing": [_fsh(due=5)]})
    with pytest.raises(ArcConflict, match="D11"):
        derive_chapter_contract(_arc_g3(), 3, st, created_at=NOW)


def test_d11_aligned_or_ungated_no_drift():
    st_ok = _state().model_copy(update={"foreshadowing": [_fsh(due=6)]})
    assert derive_chapter_contract(_arc_g3(), 3, st_ok, created_at=NOW)
    st_free = _state().model_copy(update={"foreshadowing": [
        _fsh(due=5, fid="fact_000002")]})   # gate 限期只管同名 fact，其余不归 D11 管
    assert derive_chapter_contract(_arc_g3(), 3, st_free, created_at=NOW)
