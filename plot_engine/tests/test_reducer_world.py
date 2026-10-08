from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.models.entity import Character, Item
from plot_engine.models.fact import Fact
from plot_engine.reducers.world import reduce_world


def _st():
    c = Character(character_id="char_000001", name="张三", status="alive",
                  introduced_at_chapter=1, epoch="epoch_0")
    it = Item(item_id="item_000001", name="丹药", item_type="consumable",
              stackable=True, unique=False, introduced_at_chapter=1, epoch="epoch_0")
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0",
                      characters={"char_000001": c}, items={"item_000001": it}, state_hash="")


def _ev(typ, payload, actor=None, seq=0):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor=actor or "char_000001", chapter=47, seq=seq, payload=payload)


def test_changes_status_records_death_chapter():
    out = reduce_world(_ev("CHANGES", {"field": "status", "old_value": "alive", "new_value": "dead"}), _st())
    c = out.characters["char_000001"]
    assert c.status == "dead" and c.death_chapter == 47


def test_changes_location_maps_to_current_location():
    out = reduce_world(_ev("CHANGES", {"field": "location", "old_value": None, "new_value": "loc_000012"}), _st())
    assert out.characters["char_000001"].current_location == "loc_000012"


def test_item_acquired_then_consumed_merges():
    s = _st()
    s = reduce_world(_ev("ITEM_ACQUIRED", {"character_id": "char_000001", "item_id": "item_000001", "quantity": 3}), s)
    s = reduce_world(_ev("ITEM_CONSUMED", {"character_id": "char_000001", "item_id": "item_000001", "quantity": 1}, seq=1), s)
    assert sum(i.quantity for i in s.inventory) == 2


def test_item_consumed_overdraw_clamps_to_zero():
    s = _st()
    s = reduce_world(_ev("ITEM_ACQUIRED", {"character_id": "char_000001", "item_id": "item_000001", "quantity": 1}), s)
    s = reduce_world(_ev("ITEM_CONSUMED", {"character_id": "char_000001", "item_id": "item_000001", "quantity": 5}, seq=1), s)
    # model forbids negatives (ge=0): stored qty floors at 0; Task 12 flags the over-draw from events
    assert all(i.quantity >= 0 for i in s.inventory)
    assert sum(i.quantity for i in s.inventory) == 0


def test_relationship_change_clamps_bounds():
    s = _st()
    s = reduce_world(_ev("RELATIONSHIP_CHANGED", {"from": "char_000001", "to": "char_000002",
                                                  "relationship_type": "enemy",
                                                  "strength_delta": 900, "trust_delta": -900}), s)
    s = reduce_world(_ev("RELATIONSHIP_CHANGED", {"from": "char_000001", "to": "char_000002",
                                                  "relationship_type": "enemy",
                                                  "strength_delta": 900, "trust_delta": -900}, seq=1), s)
    r = s.relationships[0]
    assert r.strength == 1000 and r.trust == 0
    assert len(s.relationships) == 1  # 双向匹配，只存一行（10 §9.1 R1）


def test_reveals_sets_narrative_truth():
    s = _st()
    f = Fact(fact_id="fact_000001", fact_type="existence", proposition="存在叛徒",
             canonical_form="traitor_exists(sect_A)",
             narrative_truth="unknown", objective_truth="true",
             defined_at_chapter=1, epoch="epoch_0")
    s = s.model_copy(update={"facts": {"fact_000001": f}})
    out = reduce_world(_ev("REVEALS", {"fact_id": "fact_000001", "new_narrative_truth": "true"}), s)
    assert out.facts["fact_000001"].narrative_truth == "true"


def test_reducer_never_mutates_input():
    s = _st()
    reduce_world(_ev("CHANGES", {"field": "status", "old_value": "alive", "new_value": "dead"}), s)
    assert s.characters["char_000001"].status == "alive"
