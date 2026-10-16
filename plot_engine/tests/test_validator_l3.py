# Level-3 注入缝：L1/L2 判完即运行（不要求通过；05 §7 闸序 2026-10-17 修订批），且永不产 HARD（§9 I1）
from plot_engine.canonical import canonical_json
from plot_engine.models.contract import ChapterContract, ChapterHook
from plot_engine.models.state import StoryState
from plot_engine.validator import Finding, Validator

EPOCH = "epoch_0"
_CLEAN_DRAFT = "<!-- hook: cliffhanger strength=800 -->"


def _clean_state() -> StoryState:
    return StoryState(story_id="s1", chapter_no=47, version=47, epoch=EPOCH,
                      characters={}, locations={}, items={}, realms={}, abilities={},
                      facts={}, state_hash="0" * 64)


def _clean_contract(**over) -> ChapterContract:
    base = dict(chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="g",
                story_goal_type="revelation",
                ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
                created_at="2026-10-09T00:00:00Z")
    base.update(over)
    return ChapterContract(**base)


def _soft(_draft, _state, _contract):
    return [Finding(rule_id="L3a", severity="soft", message="读起来略平")]


def _hard(_draft, _state, _contract):
    return [Finding(rule_id="L3b", severity="hard", message="假装是 HARD")]


def _mixed(_draft, _state, _contract):
    return [Finding(rule_id="L3c", severity="soft", message="s"),
            Finding(rule_id="L3d", severity="observation", message="o")]


def test_none_level3_preserves_clean_result():
    v = Validator()
    res = v.validate(_CLEAN_DRAFT, [], _clean_contract(), _clean_state())
    assert res.can_commit() and res.hard_violations == []
    assert res.soft_warnings == [] and res.observations == []


def test_level3_soft_lands_in_warnings():
    v = Validator()
    res = v.validate(_CLEAN_DRAFT, [], _clean_contract(), _clean_state(), level3_fn=_soft)
    assert res.can_commit()
    assert [f.rule_id for f in res.soft_warnings] == ["L3a"]


def test_level3_hard_is_downgraded_to_observation():
    v = Validator()
    res = v.validate(_CLEAN_DRAFT, [], _clean_contract(), _clean_state(), level3_fn=_hard)
    assert res.can_commit()
    assert res.hard_violations == []
    assert len(res.observations) == 1
    assert "L3_DOWNGRADED" in res.observations[0].message


def test_level3_runs_even_with_l1_l2_hard():
    calls = {"n": 0}

    def counting(draft, state, contract):
        calls["n"] += 1
        return [Finding(rule_id="x", severity="soft", message="m")]

    v = Validator()
    # required_events 未满足 → L2 产 H5.1 HARD → L3 仍被调用（人审排序读数），
    # 但 L3 的 SOFT 不解除 HARD：Commit 仍被拒（05 §9 I1/I2 不变）
    contract = _clean_contract(required_events=[
        {"event_type": "OBSERVES", "description": "d"}])
    res = v.validate(_CLEAN_DRAFT, [], contract, _clean_state(), level3_fn=counting)
    assert calls["n"] == 1
    assert not res.can_commit()
    assert any(f.rule_id == "H5.1" for f in res.hard_violations)
    assert [f.rule_id for f in res.soft_warnings] == ["x"]


def test_level3_state_untouched():
    v = Validator()
    st = _clean_state()
    before = canonical_json(st.model_dump(mode="json"))
    v.validate(_CLEAN_DRAFT, [], _clean_contract(), st, level3_fn=_mixed)
    assert canonical_json(st.model_dump(mode="json")) == before
