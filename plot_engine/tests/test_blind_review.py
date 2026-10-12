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


# ---- 配对出题（E23：语料只有一个局面时，绝对分测的是夹具的单调）----

def _multi(n_run, n_chapter):
    return [{"run": f"run{j}", "chapter": c, "status": "OK" if c % 3 else "NEEDS_HUMAN",
             "text": f"第 {c} 段剧情的第 {j} 个写法。"}
            for j in range(n_run) for c in range(n_chapter)]


@pytest.fixture
def paired_monkey(monkeypatch):
    def go(items):
        monkeypatch.setattr(br, "pool", lambda dirs: items)
        return br.build_paired(["ignored"], seed=7)
    return go


def test_paired_groups_hold_one_beat(paired_monkey):
    items = paired_monkey(_multi(6, 8))
    assert len(items) == 48
    for g in {x["group"] for x in items}:
        grp = [x for x in items if x["group"] == g]
        assert {x["chapter"] for x in grp} == {g}          # 一组 = 一段剧情
        assert len({x["variant"] for x in grp}) == len(grp)  # 变体号不重
        assert {x["run"] for x in grp} == {f"run{j}" for j in range(6)}


def test_paired_refuses_unpairable_beat(paired_monkey):
    only_one = _multi(3, 15) + [{"run": "extra", "chapter": 42, "status": "OK", "text": "独苗"}]
    with pytest.raises(ValueError, match="配不成对"):
        paired_monkey(only_one)


def test_paired_sheet_and_key_no_leak(paired_monkey):
    items = paired_monkey(_multi(6, 8))
    sheet = br.render_worksheet(items)
    assert "run0" not in sheet and "NEEDS_HUMAN" not in sheet
    assert "变体 A" in sheet
    assert "2–4 段" in sheet                      # R5 的常量半边由机器代劳（E24）
    key = br.render_key(items)
    assert "run0" in key and "变体" in key


def test_paired_html_switches_the_instrument(paired_monkey):
    page = br.render_html(paired_monkey(_multi(6, 8)), seed=7)
    assert '"g": 1' in page and "blind-paired-7" in page
    assert "2–4 段" in page                       # 打分页同样带上这条机器常量，省掉人数段落
    flat = [{"blind_id": 1, "status": "OK", "text": "一段正文", "run": "run0", "chapter": 1}]
    census = br.render_html(flat, seed=7)
    assert '"g": null' in census and "blind-census-7" in census
