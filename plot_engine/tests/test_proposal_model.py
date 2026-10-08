import pytest
from pydantic import ValidationError

from plot_engine.models.proposal import EventProposal, proposal_event_id, to_event


def _p(**over):
    base = dict(proposed_event_type="OBSERVES", actor="char_000001", target="fact_000003",
                chapter=47, scene="scn_0047_01", seq=2, preconditions=["evt_00000047_001"],
                payload={"fact_id": "fact_000003", "method": "sight"},
                confidence=1000, source_ref="para:4",
                extraction_method="llm", extraction_confidence=900)
    return EventProposal(**{**base, **over})


def test_roundtrip_fields():
    p = _p()
    assert p.payload["method"] == "sight" and p.extraction_method == "llm"
    assert _p() == p


def test_event_id_is_deterministic():
    assert proposal_event_id(_p(seq=2)) == "evt_00000047_002"


def test_duplicate_seq_same_id():
    # (chapter, seq) 相同 → event_id 相同：H6.4 的判料（Review Focus #5）
    assert proposal_event_id(_p(seq=1, payload={})) == proposal_event_id(_p(seq=1))


def test_bad_extraction_method_rejected():
    with pytest.raises(ValidationError):
        _p(extraction_method="bogus")


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        _p(extraction_confidence=1001)
    with pytest.raises(ValidationError):
        _p(extraction_confidence=-1)


def test_to_event_carries_all():
    e = to_event(_p(), epoch="epoch_0")
    assert e.event_id == "evt_00000047_002"
    assert e.event_type == "OBSERVES" and e.confidence == 1000
    assert e.schema_version == 2 and e.source_ref == "para:4"
    assert e.causes == [] and e.preconditions == ["evt_00000047_001"]
