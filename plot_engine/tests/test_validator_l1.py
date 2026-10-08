# Level-1 确定性规则（05 §4 H1/H3/H4/H6）经沙盒模拟验证
from plot_engine.canonical import canonical_json
from plot_engine.models.contract import ChapterContract
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.validator import Simulation, ValidationResult, _run_l1, _simulate

EPOCH = "epoch_0"


def _state():
    from plot_engine.models.entity import (Ability, Character, Item, Location, Realm)
    from plot_engine.models.fact import Fact
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={
            "char_000001": Character(character_id="char_000001", name="张三",
                status="alive", realm="realm_00001",
                abilities=["abil_00001", "abil_00002"],
                current_location="loc_000012", introduced_at_chapter=1, epoch=EPOCH),
            "char_dead": Character(character_id="char_000002", name="死者",
                status="dead", death_chapter=10, current_location="loc_000012",
                introduced_at_chapter=1, epoch=EPOCH),
            "char_missing": Character(character_id="char_000003", name="失踪",
                status="missing", current_location="loc_000012",
                introduced_at_chapter=1, epoch=EPOCH),
        },
        locations={
            "loc_000012": Location(location_id="loc_000012", name="藏宝阁",
                unlocked=True, introduced_at_chapter=1, epoch=EPOCH),
            "loc_000013": Location(location_id="loc_000013", name="禁地",
                unlocked=False, introduced_at_chapter=1, epoch=EPOCH),
        },
        items={"item_000001": Item(item_id="item_000001", name="丹药",
                item_type="consumable", stackable=True, introduced_at_chapter=1, epoch=EPOCH)},
        realms={
            "realm_00001": Realm(realm_id="realm_00001", name="炼气", tier=1,
                system_id="sys", epoch=EPOCH),
            "realm_00002": Realm(realm_id="realm_00002", name="筑基", tier=2,
                system_id="sys", epoch=EPOCH),
        },
        abilities={
            "abil_00001": Ability(ability_id="abil_00001", name="剑法",
                ability_type="combat", introduced_at_chapter=1, epoch=EPOCH),
            "abil_00002": Ability(ability_id="abil_00002", name="禁术",
                ability_type="combat", required_realm="realm_00002",
                introduced_at_chapter=1, epoch=EPOCH),
        },
        facts={"fact_000001": Fact(fact_id="fact_000001", fact_type="existence",
                proposition="p", canonical_form="c", narrative_truth="unknown",
                objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)},
        state_hash="0" * 64,
    )


def _p(**over):
    base = dict(proposed_event_type="OBSERVES", actor="char_000001", target="fact_000001",
                chapter=47, seq=0, payload={"fact_id": "fact_000001"},
                source_ref="x", extraction_method="rule", extraction_confidence=1000)
    return EventProposal(**{**base, **over})


def _l1(proposals, contract=None, committed=frozenset(), state=None):
    st = state or _state()
    sim = _simulate(st, proposals, EPOCH)
    return _run_l1(sim, st, proposals, contract=contract, committed_event_ids=committed)


def _codes(findings):
    return {f.rule_id for f in findings}


def _contract(chapter_no=47):
    return ChapterContract(
        chapter_no=chapter_no, arc_id="arc_003", epoch=EPOCH,
        story_goal="查明叛徒", story_goal_type="revelation",
        required_events=[], forbidden_events=[], must_change=[], must_not_change=[],
        knowledge_allowed=[], knowledge_forbidden=[], reader_signals=[],
        plot_progress={}, tension_target=500,
        ending={"type": "none", "strength": 0, "description": ""},
        derived_from=[], created_at="2026-10-08T00:00:00Z")


def test_clean_batch_no_findings():
    assert _l1([_p()]) == []


def test_simulation_does_not_mutate_input():
    st = _state()
    before = canonical_json(st.model_dump(mode="json"))
    _simulate(st, [_p()], EPOCH)
    assert canonical_json(st.model_dump(mode="json")) == before


def test_simulation_orders_by_chapter_seq():
    sim = _simulate(_state(), [_p(seq=2), _p(seq=0), _p(seq=1)], EPOCH)
    assert [e.seq for e in sim.applied] == [0, 1, 2]


def test_h1_1_dead_actor_acts():
    f = _l1([_p(actor="char_dead")])
    assert "H1.1" in _codes(f)


def test_h1_1_missing_exempt():
    assert "H1.1" not in _codes(_l1([_p(actor="char_missing")]))


def test_h1_2_h4_1_overdraw():
    p_acq = _p(seq=0, proposed_event_type="ITEM_ACQUIRED", actor=None,
               payload={"character_id": "char_000001", "item_id": "item_000001", "quantity": 2})
    p_con = _p(seq=1, proposed_event_type="ITEM_CONSUMED", actor=None,
               payload={"character_id": "char_000001", "item_id": "item_000001", "quantity": 5})
    codes = _codes(_l1([p_acq, p_con]))
    assert "H4.1" in codes and "H1.2" in codes


def test_h1_3_location_mismatch():
    p = _p(seq=0, proposed_event_type="HAPPENS", payload={"location": "loc_000013"})
    # char at loc_000012, event at loc_000013, locked too
    assert "H1.3" in _codes(_l1([p]))


def test_h4_3_locked_location():
    p = _p(seq=0, proposed_event_type="HAPPENS",
           payload={"location": "loc_000013"})
    st = _state()
    # move char to loc_000013 first via nothing; check locked triggers H4.3
    codes = _codes(_l1([p], state=st))
    assert "H4.3" in codes


def test_h1_4_realm_too_low():
    p = _p(seq=0, proposed_event_type="HAPPENS",
           payload={"ability_id": "abil_00002", "location": "loc_000012"})
    assert "H1.4" in _codes(_l1([p]))


def test_h2_4_unknown_ability():
    p = _p(seq=0, proposed_event_type="HAPPENS",
           payload={"ability_id": "abil_99999", "location": "loc_000012"})
    assert "H2.4" in _codes(_l1([p]))


def test_h3_2_future_precondition_beyond_contract():
    p = _p(seq=1, preconditions=["evt_00000099_000"])
    f = _l1([p], contract=_contract(47),
            committed=frozenset({"evt_00000099_000"}))
    assert "H3.2" in _codes(f)


def test_h3_3_time_reversal():
    p = _p(chapter=10, seq=0)
    assert "H3.3" in _codes(_l1([p]))


def test_h3_1_inbatch_order():
    p_first = _p(seq=1, preconditions=["evt_00000047_002"])
    p_second = _p(seq=2)
    f = _l1([p_first, p_second])
    assert "H3.1" in _codes(f)


def test_h6_1_bad_event_type():
    p = _p(proposed_event_type="NOT_A_TYPE")
    assert "H6.1" in _codes(_l1([p]))


def test_h6_2_unknown_precondition():
    p = _p(seq=0, preconditions=["evt_00000001_000"])
    f = _l1([p], contract=_contract(47), committed=frozenset())
    assert "H6.2" in _codes(f)


def test_h6_4_duplicate_event_id():
    f = _l1([_p(seq=3), _p(seq=3)])
    assert "H6.4" in _codes(f)


def test_h6_5_precondition_future_chapter():
    p = _p(seq=0, preconditions=["evt_00000090_000"])
    f = _l1([p], contract=_contract(47))
    assert "H6.5" in _codes(f)


def test_h6_3_cycle_is_soft():
    a = _p(seq=0, preconditions=["evt_00000047_001"])
    b = _p(seq=1, preconditions=["evt_00000047_000"])
    f = _l1([a, b])
    cyc = [x for x in f if x.rule_id == "H6.3"]
    assert cyc and cyc[0].severity == "soft"


def test_malformed_proposal_does_not_crash():
    # CHANGES missing payload keys → reducer KeyError → MALFORMED_PROPOSAL, no raise
    p = _p(seq=0, proposed_event_type="CHANGES", payload={})
    f = _l1([p])
    assert any(x.rule_id == "MALFORMED_PROPOSAL" for x in f)
    assert isinstance(_run_l1(_simulate(_state(), [p], EPOCH), _state(), [p]), list)


def test_idempotence_l1():
    st = _state()
    props = [_p(seq=0, proposed_event_type="HAPPENS", payload={"location": "loc_000013"})]
    r1 = [f.model_dump() for f in _l1(props, state=st)]
    r2 = [f.model_dump() for f in _l1(props, state=st)]
    assert r1 == r2
