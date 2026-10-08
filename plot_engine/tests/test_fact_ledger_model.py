"""Fact / FactRelation / Ledger 模型测试（02 §3/§5, 03 §4~§6）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from plot_engine.models.fact import Fact, FactRelation
from plot_engine.models.ledger import BeliefEntry, KnowledgeEntry, ReaderKnowledgeEntry


def test_fact_valid():
    f = Fact(fact_id="fact_000001", fact_type="existence", proposition="宗门内存在叛徒",
             canonical_form="traitor_exists(sect_A)", narrative_truth="true",
             objective_truth="true", defined_at_chapter=47, epoch="epoch_0")
    assert f.reveal_stage == "hidden" and f.related_facts == []


def test_fact_bad_id():
    with pytest.raises(ValidationError):
        Fact(fact_id="fact_1", fact_type="existence", proposition="p",
             canonical_form="p()", narrative_truth="true",
             objective_truth="true", defined_at_chapter=47, epoch="epoch_0")


def test_factrelation_strength_is_fixed_int():
    fr = FactRelation(relation_id="fr_1", source_fact_id="fact_000001",
                      target_fact_id="fact_000002", relation_type="evidence_for",
                      epoch="epoch_0")
    assert fr.strength == 1000 and isinstance(fr.strength, int)


def test_reader_entry_requires_source_event():
    with pytest.raises(ValidationError):
        ReaderKnowledgeEntry(fact_id="fact_000003", reader_state="knows",
                             reader_strength=900, established_at_chapter=47,
                             last_updated_chapter=47, epoch="epoch_0")  # 缺 source_event_id


def test_knowledge_and_belief_states():
    k = KnowledgeEntry(character_id="char_000001", fact_id="fact_000003",
                       knowledge_state="known", strength=900, source_event_id="evt_00000047_001",
                       acquired_at_chapter=47, last_updated_chapter=47, epoch="epoch_0")
    b = BeliefEntry(character_id="char_000001", fact_id="fact_000002",
                    belief_state="believes", strength=700, source_event_id="evt_00000047_002",
                    acquired_at_chapter=47, last_updated_chapter=47, epoch="epoch_0")
    assert k.knowledge_state == "known" and b.is_true is None
