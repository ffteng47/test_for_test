"""ladder-v5 静态钉：50 章不回环 + 前 10 章逐字等于 ladder-v4。

WP-E 夹具的验收底线是「40 章新阶梯每步都是合法新 Δ」——即全库
(actor, field, fact) 三元组唯一；回环一步就会让 E2 读数掺夹具伪影。
"""
from plot_engine.tests.fixtures import experiment_10ch as fx10
from plot_engine.tests.fixtures import experiment_50ch as fx50


def test_front_ten_chapters_are_ladder_v4_verbatim():
    for ch in range(1, 11):
        assert fx50._step(ch) is fx10._STEPS[ch - 1]


def test_fifty_chapter_knowledge_triples_never_loop():
    from collections import Counter
    arc = fx50.build_arc(50)
    triples = []
    for beat in arc.reader_beats:
        for c in beat["must_change"]:
            triples.append((c["character_id"], c["field"], c["target"]))
    # 每章 Δ 新跃迁：阶梯对恰出现两次（add suspected → update known），
    # 任何三元组第三次出现 = 回环 = 夹具伪影。
    counts = Counter(triples)
    assert max(counts.values()) == 2, [t for t, n in counts.items() if n > 2]
    assert len(triples) == 18 + 40  # v4 十章 18 钉 + v5 阶梯 40 钉
    assert sum(1 for n in counts.values() if n == 1) == 18


def test_pairs_pool_excludes_ch1_10_and_deception():
    used = {("char_000001", f) for f in
            ("fact_000001", "fact_000002", "fact_000003", "fact_000004", "fact_000005",
             "fact_000006", "fact_000009", "fact_000010", "fact_000011")}
    used |= {("char_000003", "fact_000007"), ("char_000004", "fact_000010")}
    assert not set(fx50._PAIRS) & used
    assert ("char_000002", "fact_000002") not in fx50._PAIRS
    assert len(fx50._PAIRS) == 20


def test_ladder_step_alternates_suspected_then_known():
    assert fx50._step(11)["must_change"][0]["expected_value"] == "suspected"
    assert fx50._step(12)["must_change"][0]["expected_value"] == "known"
    assert fx50._step(50)["must_change"][0]["expected_value"] == "known"


def test_make_config_rejects_short_run():
    try:
        fx50.make_config(10)
        assert False
    except ValueError:
        pass
