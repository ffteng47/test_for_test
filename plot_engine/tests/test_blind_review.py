"""盲评表的两个致命属性：出处不能漏、格数不够不许出题。"""
import pytest

import plot_engine.blind_review as br


def _items(n_ok, n_bad, run="v32r1"):
    # 正文里刻意不含 run 名：真实 dump 的正文也不会，工作表泄漏只可能来自渲染层。
    return [{"run": run, "chapter": i, "status": "OK" if i < n_ok else "NEEDS_HUMAN",
             "text": f"这是第 {i} 章的正文。"} for i in range(n_ok + n_bad)]


@pytest.fixture
def patched(monkeypatch):
    def go(n_ok, n_bad, run="v32r1"):
        monkeypatch.setattr(br, "pool", lambda dirs: _items(n_ok, n_bad, run))
        return br.build(["ignored"])
    return go


def test_worksheet_leaks_no_provenance(patched):
    items = patched(24, 16)
    text = br.render_worksheet(items)
    assert "v32r1" not in text and "NEEDS_HUMAN" not in text
    assert len(items) == 40 and items[0]["blind_id"] == 1


def test_refuses_when_below_either_floor(patched):
    with pytest.raises(ValueError, match="下限 30"):
        patched(15, 5)                       # 20 章
    with pytest.raises(ValueError, match="下限 15"):
        patched(28, 2)                       # 30 章但失败类只有 2


def test_seed_reproduces_the_same_sheet(patched):
    a = [x["text"] for x in patched(20, 20)]
    b = [x["text"] for x in patched(20, 20)]
    assert a == b
    assert len({x["blind_id"] for x in patched(20, 20)}) == 40


def test_key_maps_blind_id_back(patched):
    items = patched(20, 20)
    key = br.render_key(items)
    assert "v32r1" in key and "NEEDS_HUMAN" in key and "评分收齐前勿开" in key
