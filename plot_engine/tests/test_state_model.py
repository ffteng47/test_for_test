"""StoryState 聚合根测试（10 §13）。"""
from __future__ import annotations

from plot_engine.canonical import canonical_hash
from plot_engine.models.state import StoryState, with_state_hash


def _empty():
    return StoryState(story_id="s1", chapter_no=1, version=0, epoch="epoch_0", state_hash="")


def test_hash_excludes_itself():
    s = with_state_hash(_empty())
    assert s.state_hash == canonical_hash(
        _empty().model_dump(mode="json", exclude={"state_hash"}))


def test_hash_is_stable_across_rebuild():
    a = with_state_hash(_empty()).state_hash
    b = with_state_hash(_empty()).state_hash
    assert a == b


def test_default_collections_empty():
    s = _empty()
    assert s.characters == {} and s.knowledge_ledger == []
