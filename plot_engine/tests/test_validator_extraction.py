# H8 抽取置信度闸门（07 §4.3 R1–R4）
from plot_engine.markup import parse_markup
from plot_engine.models.contract import ChapterContract
from plot_engine.models.fact import Fact
from plot_engine.models.entity import Character
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.validator import _h8_gate, _run_l2, _simulate

EPOCH = "epoch_0"


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", introduced_at_chapter=1, epoch=EPOCH)},
        facts={"fact_000001": Fact(fact_id="fact_000001", fact_type="existence",
            proposition="p", canonical_form="c", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)},
        state_hash="0" * 64)


def _p(conf=1000, **over):
    base = dict(proposed_event_type="OBSERVES", actor="char_000001", target="fact_000001",
                chapter=47, seq=0, payload={"fact_id": "fact_000001"},
                source_ref="x", extraction_method="rule", extraction_confidence=conf)
    return EventProposal(**{**base, **over})


def _codes(f):
    return {x.rule_id for x in f}


def test_h8_1_low_confidence_fails_batch():
    active, findings = _h8_gate([_p(conf=1000), _p(seq=1, conf=499)], _state())
    assert active == []
    assert "H8.1" in _codes(findings)


def test_h8_2_quarantine_boundaries():
    # 500 与 699 隔离；700 通过
    active, findings = _h8_gate([_p(seq=0, conf=500), _p(seq=1, conf=699), _p(seq=2, conf=700)], _state())
    assert "H8.2" in _codes(findings)
    h82 = [x for x in findings if x.rule_id == "H8.2"]
    assert len(h82) == 2
    assert all("EXTRACTION_UNVERIFIED" in x.message for x in h82)
    assert [p.seq for p in active] == [2]


def test_h8_clean_no_findings():
    active, findings = _h8_gate([_p(conf=700), _p(seq=1, conf=1000)], _state())
    assert findings == [] and len(active) == 2


def test_h8_2_then_h5_1_on_remainder():
    # required OBSERVES 只在被隔离的 proposal 里 → 隔离后 remainder 触发 H5.1
    contract = ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="g",
        story_goal_type="revelation",
        required_events=[{"event_type": "OBSERVES", "description": "d", "minimum_count": 1}],
        ending={"type": "cliffhanger", "strength": 800, "description": "d"},
        created_at="2026-10-08T00:00:00Z")
    st = _state()
    active, qfindings = _h8_gate([_p(conf=600)], st)
    sim = _simulate(st, active, EPOCH)
    mk = parse_markup("<!-- hook: cliffhanger strength=800 -->")
    l2 = _run_l2(sim, st, active, contract=contract, markup=mk)
    assert "H8.2" in _codes(qfindings)
    assert "H5.1" in _codes(l2)


def test_h8_r4_markup_unknown_fact():
    p = _p(extraction_method="markup", proposed_event_type="READER_LEARNS",
           target="fact_999999", payload={"fact_id": "fact_999999"})
    active, findings = _h8_gate([p], _state())
    assert "H6.2" in _codes(findings)
    assert any(x.suggestion and "markup" in x.suggestion for x in findings if x.rule_id == "H6.2")
