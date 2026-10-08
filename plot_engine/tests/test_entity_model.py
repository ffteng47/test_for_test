"""世界实体模型测试：合法构造 + 错误 ID 前缀 / 边界拒绝（10 §4~§12）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from plot_engine.models.entity import (
    Character,
    InventoryEntry,
    Realm,
    Relationship,
)


def test_character_valid():
    c = Character(character_id="char_000001", name="张三", status="alive",
                  introduced_at_chapter=1, epoch="epoch_0")
    assert c.attributes == {} and c.aliases == []


def test_character_bad_id():
    with pytest.raises(ValidationError):
        Character(character_id="char_1", name="x", status="alive",
                  introduced_at_chapter=1, epoch="epoch_0")


def test_relationship_defaults_fixed():
    r = Relationship(relationship_id="rel_000001", from_character="char_000001",
                     to_character="char_000002", type="friend",
                     established_at_chapter=1, epoch="epoch_0")
    assert r.strength == 500 and r.trust == 500


def test_realm_tier_floor():
    with pytest.raises(ValidationError):
        Realm(realm_id="realm_00001", name="筑基", tier=0,
              system_id="cultivation_main", epoch="epoch_0")


def test_inventory_quantity_nonneg():
    with pytest.raises(ValidationError):
        InventoryEntry(inventory_id="inv_000001", character_id="char_000001",
                       item_id="item_000001", quantity=-1,
                       acquired_at_chapter=1, epoch="epoch_0")
