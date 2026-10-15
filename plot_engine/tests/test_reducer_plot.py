"""Plot reducer 测试（WP-A 设计稿 §3：伏笔生命周期 + 联动 + 显式放弃）。"""
from __future__ import annotations

import pytest

from plot_engine.models.event import Event
from plot_engine.models.state import StoryState
from plot_engine.reducers.belief import reduce_belief
from plot_engine.reducers.plot import abandon_foreshadowing, reduce_plot
from plot_engine.reducers.reader import reduce_reader


def _state():
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0",
                      state_hash="")


def _ev(chapter, typ, payload, seq=0, conf=800, actor="char_000001"):
    return Event(event_id=f"evt_{chapter:08d}_{seq:03d}", epoch="epoch_0",
                 event_type=typ, actor=actor,
                 target=payload.get("fact_id"), chapter=chapter, seq=seq,
                 payload=payload, confidence=conf)


def _fsh(state, fid="fsh_000001"):
    return [e for e in state.foreshadowing if e.foreshadow_id == fid][0]


def _set(chapter=10, seq=0):
    return _ev(chapter, "FORESHADOWING_SET",
               {"foreshadow_id": "fsh_000001", "fact_id": "fact_000003",
                "due_by_chapter": 20, "strength": 600}, seq=seq)


def test_set_creates_planted_entry():
    out = reduce_plot(_set(), _state())
    e = _fsh(out)
    assert e.lifecycle == "planted" and e.strength == 600
    assert e.planted_chapter == 10 and e.due_by_chapter == 20
    assert e.paid_chapter is None and e.epoch == "epoch_0"


def test_duplicate_set_rejected():
    s = reduce_plot(_set(), _state())
    with pytest.raises(ValueError, match="重复"):
        reduce_plot(_set(seq=1), s)


def test_paid_from_planted():
    s = reduce_plot(_set(), _state())
    out = reduce_plot(_ev(15, "FORESHADOWING_PAID",
                          {"foreshadow_id": "fsh_000001"}), s)
    e = _fsh(out)
    assert e.lifecycle == "paid" and e.paid_chapter == 15


def test_paid_sourceless_rejected():
    with pytest.raises(ValueError, match="不存在"):
        reduce_plot(_ev(15, "FORESHADOWING_PAID",
                        {"foreshadow_id": "fsh_000009"}), _state())


def test_paid_twice_rejected():
    s = reduce_plot(_set(), _state())
    s = reduce_plot(_ev(15, "FORESHADOWING_PAID", {"foreshadow_id": "fsh_000001"}), s)
    with pytest.raises(ValueError, match="不可回收"):
        reduce_plot(_ev(16, "FORESHADOWING_PAID", {"foreshadow_id": "fsh_000001"}), s)


def test_reader_hinted_links_planted_to_hinted():
    s = reduce_plot(_set(), _state())
    out = reduce_reader(_ev(12, "READER_HINTED",
                            {"fact_id": "fact_000003", "strength": 500}), s)
    assert _fsh(out).lifecycle == "hinted"
    assert _fsh(out).last_updated_chapter == 12
    assert out.reader_ledger[0].reader_state == "hinted"


def test_belief_hints_links_planted_to_hinted():
    s = reduce_plot(_set(), _state())
    out = reduce_belief(_ev(12, "HINTS",
                             {"fact_id": "fact_000003", "audience": ["char_000002"]}), s)
    assert _fsh(out).lifecycle == "hinted"


def test_hint_does_not_touch_other_lifecycles():
    s = reduce_plot(_set(), _state())
    s = reduce_plot(_ev(15, "FORESHADOWING_PAID", {"foreshadow_id": "fsh_000001"}), s)
    out = reduce_reader(_ev(16, "READER_HINTED", {"fact_id": "fact_000003"}), s)
    assert _fsh(out).lifecycle == "paid"  # 已回收不回退


def test_abandon_marks_expired_and_paid_rejected():
    s = reduce_plot(_set(), _state())
    out = abandon_foreshadowing(s, "fsh_000001", 18)
    assert _fsh(out).lifecycle == "expired"
    s2 = reduce_plot(_ev(15, "FORESHADOWING_PAID", {"foreshadow_id": "fsh_000001"}), s)
    with pytest.raises(ValueError, match="不可放弃"):
        abandon_foreshadowing(s2, "fsh_000001", 18)
    with pytest.raises(ValueError, match="不存在"):
        abandon_foreshadowing(_state(), "fsh_000009", 18)


def test_paid_after_expired_rejected():
    s = reduce_plot(_set(), _state())
    s = abandon_foreshadowing(s, "fsh_000001", 18)
    with pytest.raises(ValueError, match="不可回收"):
        reduce_plot(_ev(19, "FORESHADOWING_PAID", {"foreshadow_id": "fsh_000001"}), s)


def test_case_solved_remains_noop():
    s = reduce_plot(_set(), _state())
    out = reduce_plot(_ev(11, "CASE_SOLVED", {"fact_id": "fact_000003"}), s)
    assert out.foreshadowing == s.foreshadowing
