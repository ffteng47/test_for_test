# 四通道合成 + 置信度联动设值（07 §4.3）
from plot_engine.extract import cross_validate, stage0_extract
from plot_engine.models.proposal import EventProposal


def _p(source_ref, etype="OBSERVES", actor="char_000001", target="fact_000003",
       payload=None, method="rule", conf=1000, seq=0):
    return EventProposal(
        proposed_event_type=etype, actor=actor, target=target, chapter=47, seq=seq,
        payload=payload if payload is not None else {"fact_id": target},
        source_ref=source_ref, extraction_method=method, extraction_confidence=conf)


def _by_key(props):
    return {(p.source_ref, p.extraction_method, p.extraction_confidence) for p in props}


def test_agreement_becomes_hybrid_1000():
    rule = [_p("para:4")]
    llm = [_p("para:4", method="llm")]
    merged, conflicts = cross_validate(rule, llm)
    assert len(merged) == 1
    assert merged[0].extraction_method == "hybrid"
    assert merged[0].extraction_confidence == 1000
    assert conflicts == []


def test_single_channel_rule_700():
    merged, _ = cross_validate([_p("para:4")], [])
    assert len(merged) == 1
    assert merged[0].extraction_method == "rule"
    assert merged[0].extraction_confidence == 700


def test_single_channel_llm_700():
    merged, _ = cross_validate([], [_p("para:6", method="llm", target="fact_000001")])
    assert len(merged) == 1
    assert merged[0].extraction_method == "llm"
    assert merged[0].extraction_confidence == 700


def test_same_span_different_result_conflict_500():
    rule = [_p("para:4", target="fact_000003")]
    llm = [_p("para:4", method="llm", target="fact_000001")]
    merged, conflicts = cross_validate(rule, llm)
    assert len(merged) == 2
    assert all(p.extraction_confidence == 500 for p in merged)
    assert len(conflicts) == 1 and conflicts[0]["span"] == "para:4"


def test_different_spans_do_not_cross_talk():
    rule = [_p("para:4", target="fact_000003")]
    llm = [_p("para:6", method="llm", target="fact_000001")]
    merged, conflicts = cross_validate(rule, llm)
    assert conflicts == []
    assert {p.extraction_confidence for p in merged} == {700}


def test_stage0_reassigns_unique_sequential_seq():
    rule = [_p("para:9"), _p("para:6", target="fact_000001", etype="INFERS")]
    props = stage0_extract("draft", _scene_plan_stub(), _contract_stub(), _state_stub(),
                           chapter=47, rule_channel=lambda *a, **k: list(rule))
    assert sorted(p.seq for p in props) == list(range(len(props)))


def test_stage0_excludes_reader_events():
    rule = [_p("para:4", etype="READER_LEARNS")]
    props = stage0_extract("draft", _scene_plan_stub(), _contract_stub(), _state_stub(),
                           chapter=47, rule_channel=lambda *a, **k: list(rule))
    assert props == []


def test_stage0_default_channels_return_empty():
    props = stage0_extract("draft", _scene_plan_stub(), _contract_stub(), _state_stub(),
                           chapter=47)
    assert props == []


# --- 轻量替身：Stage-0 不读 state/plan/contract 内容，仅需可调用签名 ---
def _scene_plan_stub():
    return None


def _contract_stub():
    return None


def _state_stub():
    return None
