# Alexandria Plot Engine — Core State Layer (Phase 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frozen-spec core state layer for the Alexandria plot engine — Event/StoryState models, canonical hashing, an append-only Event Log, a CAS state store with snapshots, the pure Reducers, an invariant checker, and per-chapter replay parity — so that chapters can be committed as idempotent, replayable, hash-verifiable state transitions.

**Architecture:** Event Sourcing. Every chapter commit appends immutable `Event`s to an append-only SQLite (WAL) log, then CAS-writes a new `StoryState` under `expected_version + 1`, snapshots every N=5 chapters, and auto-replays from the latest snapshot to prove `state_hash` parity (07 §7.1/§7.5). All numeric fields are fixed-point integers (×1000); `state_hash = SHA256(canonical_json(state))` with key-sorted, whitespace-free, UTF-8-unescaped serialization (05 §5.5). Reducers are pure functions `Event × StoryState → StoryState`, applied in `(chapter, seq)` order (07 §6.2).

**Tech Stack:** Python 3.12 (target) / 3.13 (dev box), pydantic 2.12.5 (pinned by venv-app), SQLite (stdlib `sqlite3`, WAL mode), pytest.

**Spec:** `alexandria-spec-v0.2/` — single sources of truth: Fact → `02 §3`; Event/Taxonomy/payload → `01 §3~§4`; Knowledge/Belief/Reader reducers → `03 §4~§8`; canonical & fixed-point → `05 §5.5`; entities + `StoryState` + invariants → `10 §3~§15`; commit/CAS/snapshot/replay/idempotency → `07 §6~§8`; scope rulings → `docs/plot-engine-scope-reduction.md` (C1/C5).

## Global Constraints

- **pydantic==2.12.5** (venv-app pin, `docs/target-architecture.md`); `from pydantic import BaseModel, Field`. Every model uses `from __future__ import annotations` and a one-line Chinese docstring naming its spec section.
- **Fixed-point only (05 §5.5):** every float-semantics field is stored as int ×1000. `strength = (trust_fixed × message_fixed) // 1000` (integer floor). No Python `float` may participate in the replay-critical path (03 §10 I8, 05 §5.5).
- **Canonical JSON (05 §5.5.1):** keys ascending, no whitespace, UTF-8 without escaping ASCII-range chars, numbers as fixed-point integers (no scientific notation). `state_hash = SHA256(canonical_json(state)).hexdigest()`.
- **Event ID:** `^evt_\d{8}_\d{3}$` (e.g. `evt_00000047_003`). **Entity IDs (10 §3~§12):** char/loc/item/rel/inv 6 digits (`^char_\d{6}$` etc.); fac/realm/abil/rgn 5 digits (`^fac_\d{5}$` etc.). **Scene ID:** `^scn_\d{4}_\d{2}$`.
- **Epoch / schema:** `epoch: str` matches `^epoch_\d+$`; `schema_version: int = 2`. Phase 0 runs on `epoch_0`.
- **CAS is mandatory from day 1 (scope-reduction C1):** `persist(..., expected_version)` rejects on version mismatch — single-worker code paths pass trivially; the contract must not change when a second worker is added.
- **Append-only Event Log + snapshot N=5 (scope-reduction C5, 07 §7.3 R2).** Rollback marks events `orphan`, never deletes (07 §7.5 R6).
- **Code location (README 文档层级):** package under `plot_engine/`, tests under `plot_engine/tests/`. No protocol edits during this plan (08 I1).
- **Finding shape (matches `backend/rules.py`):** `{"code": str, "ord": int, "severity": "hard"|"soft"|"observation", "detail": str}`. Checkers only report; they never mutate state.

## Review Focus

These spec-implied failure modes are not covered by a task's happy-path test; each is pinned to the task that owns the code.

1. **CJK canonical byte-stability** — a state containing Chinese `name`/`proposition` must serialize to identical bytes across machines (keys sorted, non-ASCII NOT escaped). → Task 2.
2. **Fixed-point floor-division determinism** — `IS_TOLD` strength (`trust×msg÷1000`) and `FACT_CONTRADICTED` ×0.4 downgrade must use integer floor, never float rounding, and must be byte-identical under replay. → Task 8.
3. **Inventory over-draw & delta clamping** — the entity models clamp stored values (`InventoryEntry.quantity ge=0`; `Relationship.strength/trust 0..1000`), so a `ITEM_CONSUMED` beyond held qty floors at 0 and an out-of-range `RELATIONSHIP_CHANGED` delta floors at the bound; the *illegal consumption* is still surfaced as a HARD finding by recomputing held-vs-consumed **from the events** (H4.1), never silently forgiven. → Task 10 + Task 12.
4. **Replay hash parity across a mid-stream snapshot** — replaying from the most recent snapshot forward must equal the online `state_hash`, not only a from-genesis replay. → Task 13.
5. **Malformed events rejected before append** — unknown `event_type`, bad `event_id` pattern, and a duplicate `(chapter, seq)` for the same story must fail at the model/append boundary, not corrupt the log. → Task 1 + Task 6.

---

## Task 1: Package scaffold, venv, Event model

**Files:**
- Create: `plot_engine/__init__.py` (empty)
- Create: `plot_engine/models/__init__.py` (empty)
- Create: `plot_engine/models/event.py`
- Create: `plot_engine/tests/conftest.py` (puts the repo root on `sys.path` so `import plot_engine...` resolves)
- Test: `plot_engine/tests/test_event_model.py`

**Interfaces:**
- Produces:
  - `EventType` — `Literal[...]` with all 26 values from 01 §4 (Knowledge 5, Belief 3, Statement 4, World 6, Reader 3, Plot 5).
  - `class Event(BaseModel)` with fields: `event_id: str = Field(..., pattern=r"^evt_\d{8}_\d{3}$")`, `epoch: str = Field(..., pattern=r"^epoch_\d+$")`, `schema_version: int = 2`, `event_type: EventType`, `actor: Optional[str] = None`, `target: Optional[str] = None`, `location: Optional[str] = None`, `chapter: int = Field(..., ge=1)`, `scene: Optional[str] = None`, `seq: int = Field(..., ge=0)`, `preconditions: List[str] = []`, `causes: List[str] = []`, `payload: Dict = {}`, `confidence: int = Field(1000, ge=0, le=1000)`, `source_ref: Optional[str] = None`.

- [ ] **Step 1: Create venv and install pinned deps**

Run from repo root:
```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1   # Windows dev box (Git Bash: source .venv/Scripts/activate)
pip install "pydantic==2.12.5" pytest
```
Expected: `pip list` shows `pydantic 2.12.5`, `pytest` present.

- [ ] **Step 2: Write the failing model test**

`plot_engine/tests/test_event_model.py`:
```python
import pytest
from pydantic import ValidationError
from plot_engine.models.event import Event

def _mk(**kw):
    base = dict(event_id="evt_00000047_003", epoch="epoch_0",
                event_type="OBSERVES", chapter=47, seq=2,
                payload={"fact_id": "fact_000003", "method": "sight"})
    base.update(kw); return Event(**base)

def test_valid_event_reads_back_fields():
    e = _mk()
    assert e.schema_version == 2 and e.confidence == 1000

@pytest.mark.parametrize("bad", [
    {"event_id": "evt_47_3"},                 # wrong id pattern
    {"event_type": "NOT_A_TYPE"},             # unknown taxonomy value
    {"chapter": 0},                           # chapter >= 1
    {"confidence": 1001},                     # out of fixed-point range
])
def test_malformed_event_rejected(bad):
    with pytest.raises(ValidationError):
        _mk(**bad)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_event_model.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: plot_engine.models.event`.

- [ ] **Step 4: Implement `models/event.py`**

Add `from __future__ import annotations`; the `EventType` literal with all 26 values (copied verbatim from 01 §4) grouped by comment; the `Event` model with the exact field list above. One-line Chinese docstring citing `01 §4`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_event_model.py -v`
Expected: PASS (both cases).

- [ ] **Step 6: Commit**

```bash
git init -q 2>/dev/null || true   # only if repo not already initialized
git add .gitignore plot_engine/ plot_engine/tests/ .venv/ 2>/dev/null
# ensure .gitignore contains: .venv/ __pycache__/ *.pyc .pytest_cache/
git commit -m "feat(plot-engine): scaffold + Event model (01 §4 taxonomy)"
```

---

## Task 2: Canonical serialization & hashing

**Files:**
- Create: `plot_engine/canonical.py`
- Test: `plot_engine/tests/test_canonical.py`

**Interfaces:**
- Produces:
  - `def canonical_json(obj) -> bytes` — key-sorted, `separators=(",", ":")`, `ensure_ascii=False`; pydantic models are dumped via `obj.model_dump()` (mode="json", warnings="none") before encoding. Numbers must already be ints (fixed-point); floats raise `TypeError`.
  - `def canonical_hash(obj) -> str` — `hashlib.sha256(canonical_json(obj)).hexdigest()`. (`StoryState.state_hash` is defined as `canonical_hash(state)`; 05 §5.5.3.)
  - `def fixed_to_str(v: int) -> str` — `f"{v/1000:.3f}"` (display only, NEVER in replay path).
  - `def to_fixed(x: float | str) -> int` — one-time ingestion helper: `int(Decimal(str(x)) * 1000)`; not used on the replay-critical path.
  - `def proposal_set_hash(proposals: list) -> str` — `canonical_hash(sorted-by-`canonical_json` of each)`. (07 §8 R1.)

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_canonical.py`:
```python
import pytest
from plot_engine.canonical import canonical_json, canonical_hash, fixed_to_str, to_fixed

def test_keys_sorted_and_no_whitespace():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'

def test_cjk_bytes_are_stable_and_unescaped():
    a = canonical_json({"name": "张三", "z": 1, "a": 0})
    b = canonical_json({"a": 0, "name": "张三", "z": 1})
    assert a == b == '{"a":0,"name":"张三","z":1}'.encode("utf-8")

def test_hash_is_deterministic_and_hex64():
    h = canonical_hash({"x": 1})
    assert h == canonical_hash({"x": 1}) and len(h) == 64

def test_float_forbidden_in_canonical_path():
    with pytest.raises(TypeError):
        canonical_json({"strength": 0.4})

def test_fixed_roundtrip_display():
    assert to_fixed(0.4) == 400 and fixed_to_str(400) == "0.400"

def test_proposal_set_hash_order_independent():
    from plot_engine.canonical import proposal_set_hash
    a = proposal_set_hash([{"x": 1}, {"y": 2}])
    b = proposal_set_hash([{"y": 2}, {"x": 1}])   # sorted internally → equal
    assert a == b and len(a) == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_canonical.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `canonical.py`**

Use `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`. Detect pydantic models via `hasattr(obj, "model_dump")` and recurse; reject `float` instances by raising `TypeError` in the default encoder (`default=` hook that dumps models but raises on float). Keep it pure and dependency-light (stdlib + pydantic duck-typing).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_canonical.py -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/canonical.py plot_engine/tests/test_canonical.py
git commit -m "feat(plot-engine): canonical json + hash + fixed-point helpers (05 §5.5)"
```

---

## Task 3: World entity models

**Files:**
- Create: `plot_engine/models/entity.py`
- Test: `plot_engine/tests/test_entity_model.py`

**Interfaces:**
- Produces (fields verbatim from 10 §4~§12; all `epoch: str` matches `^epoch_\d+$`):
  - `Character` (`^char_\d{6}$`, `status: Literal["alive","dead","missing","sealed","unborn"]`, `realm: Optional[str]`, `abilities: List[str]`, `attributes: Dict[str,int]`, `current_location: Optional[str]`, `faction_id: Optional[str]`, `introduced_at_chapter: int`, `death_chapter/seal_chapter/last_seen_at_chapter: Optional[int]`, `gender: Optional[str]`, `aliases: List[str]=[]`).
  - `Location` (`^loc_\d{6}$`, `region_id/parent_location_id/realm_cap/faction_control: Optional[str]`, `connected_to: List[str]=[]`, `distance: Dict[str,int]={}`, `unlocked: bool=True`, `unlock_conditions: List[str]=[]`, `introduced_at_chapter: int`).
  - `Item` (`^item_\d{6}$`, `item_type: Literal["consumable","equipment","material","key","misc","quest"]`, `attributes: Dict[str,Any]={}`, `unique/stackable/consumed_on_use: bool`, `required_realm: Optional[str]`).
  - `Faction` (`^fac_\d{5}$`, `parent_faction_id: Optional[str]`, `relations: Dict[str,str]={}`, `controlled_locations/members: List[str]=[]`).
  - `Realm` (`^realm_\d{5}$`, `tier: int=Field(...,ge=1)`, `system_id: str`, `previous_realm/next_realm: Optional[str]`, `allowed_abilities: List[str]=[]`, `usable_realms: List[int]=[]`, `min_attributes: Dict[str,int]={}`).
  - `Ability` (`^abil_\d{5}$`, `ability_type: Literal["combat","utility","passive","special"]`, `required_realm/consumed_resource: Optional[str]`).
  - `Region` (`^rgn_\d{5}$`, `name: str`, `epoch`).
  - `Relationship` (`^rel_\d{6}$`, `from_character/to_character: str`, `type: Literal[9 values]`, `strength/trust: int=Field(500,ge=0,le=1000)`, `symmetric: bool=True`, `established_at_chapter: int`, `ended_at_chapter: Optional[int]`).
  - `InventoryEntry` (`^inv_\d{6}$`, `character_id/item_id: str`, `quantity: int=Field(...,ge=0)`, `acquired_at_chapter: int`, `consumed_at_chapter: Optional[int]`).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_entity_model.py` — assert valid construction of each entity, and that wrong ID prefixes are rejected:
```python
import pytest
from pydantic import ValidationError
from plot_engine.models.entity import Character, Realm, Relationship, InventoryEntry

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_entity_model.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `models/entity.py`**

One `BaseModel` per entity with the exact `Field(..., pattern=...)` ID constraints and defaults above. Copy enum values verbatim from 10 §4~§12. `Relationship.type` literal: `"family","master_disciple","friend","enemy","ally","rival","lover","colleague","unknown"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_entity_model.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/models/entity.py plot_engine/tests/test_entity_model.py
git commit -m "feat(plot-engine): world entity models (10 §4~§12)"
```

---

## Task 4: Fact, FactRelation & cognitive-ledger models

**Files:**
- Create: `plot_engine/models/fact.py`
- Create: `plot_engine/models/ledger.py`
- Test: `plot_engine/tests/test_fact_ledger_model.py`

**Interfaces:**
- Produces:
  - `Fact` (`02 §3`): `fact_id: str = Field(..., pattern=r"^fact_\d{6}$")`, `fact_type: Literal["existence","identity","relation","event","state"]`, `proposition: str`, `canonical_form: str`, `related_facts: List[str]=[]`, `narrative_truth: Literal["true","false","unknown"]`, `objective_truth: Literal["true","false","unknown"]`, `reveal_stage: Literal["hidden","hinted","partial","confirmed"]="hidden"`, `defined_at_chapter: int`, `epoch: str`.
  - `FactRelation` (`02 §5`): `relation_id: str`, `source_fact_id: str`, `target_fact_id: str`, `relation_type: Literal["evidence_for","confirms","contradicts","implies","derives_from"]`, `strength: int = Field(1000, ge=0, le=1000)`, `epoch: str`.
  - `KnowledgeEntry` (`03 §4.1`): `character_id`, `fact_id`, `knowledge_state: Literal["unknown","suspected","believed","known","confirmed"]`, `strength: int=Field(...,ge=0,le=1000)`, `source_event_id: str`, `acquired_at_chapter: int`, `last_updated_chapter: int`, `epoch`.
  - `BeliefEntry` (`03 §5.1`): `character_id`, `fact_id`, `belief_state: Literal["doubts","suspects","believes"]`, `strength: int`, `source_event_id`, `acquired_at_chapter`, `last_updated_chapter`, `is_true: Optional[bool]=None`, `epoch`.
  - `ReaderKnowledgeEntry` (`03 §6.1`): `fact_id`, `reader_state: Literal["unaware","hinted","knows","deceived"]`, `reader_strength: int`, `established_at_chapter`, `last_updated_chapter`, `source_event_id`, `epoch`.

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_fact_ledger_model.py`:
```python
import pytest
from pydantic import ValidationError
from plot_engine.models.fact import Fact, FactRelation
from plot_engine.models.ledger import KnowledgeEntry, BeliefEntry, ReaderKnowledgeEntry

def test_fact_bad_id():
    with pytest.raises(ValidationError):
        Fact(fact_id="fact_1", fact_type="existence", proposition="p",
             canonical_form="p()", narrative_truth="true",
             objective_truth="true", defined_at_chapter=47, epoch="epoch_0")

def test_factrelation_strength_is_fixed_int():
    fr = FactRelation(relation_id="fr_1", source_fact_id="fact_000001",
                      target_fact_id="fact_000002", relation_type="evidence_for",
                      epoch="epoch_0")
    assert fr.strength == 1000

def test_reader_entry_requires_source_event():
    with pytest.raises(ValidationError):
        ReaderKnowledgeEntry(fact_id="fact_000003", reader_state="knows",
                             reader_strength=900, established_at_chapter=47,
                             last_updated_chapter=47, epoch="epoch_0")  # missing source_event_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_fact_ledger_model.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `models/fact.py` and `models/ledger.py`**

Copy field lists above exactly. `FactRelation.strength` is `int` 0~1000 (fixed-point, 05 §5.5 — the v0.2 hygiene fix, not a float). All ledger `*_id` / `fact_id` fields are `str` (reference-existence is checked by the invariant checker in Task 12, not by the model).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_fact_ledger_model.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/models/fact.py plot_engine/models/ledger.py plot_engine/tests/test_fact_ledger_model.py
git commit -m "feat(plot-engine): fact + fact-relation + ledger models (02 §3/§5, 03 §4~§6)"
```

---

## Task 5: StoryState aggregate + canonical round-trip

**Files:**
- Create: `plot_engine/models/state.py`
- Test: `plot_engine/tests/test_state_model.py`

**Interfaces:**
- Consumes: entity/fact/ledger models (Tasks 3~4); `canonical_hash` (Task 2).
- Produces:
  - `class StoryState(BaseModel)` (`10 §13`): `story_id: str`, `chapter_no: int`, `version: int`, `epoch: str`, `schema_version: int = 2`; collections `characters/locations/items/factions/realms/abilities/regions: Dict[str, <model>] = {}`; `relationships/inventory: List[...] = []`; `facts: Dict[str, Fact] = {}`; `fact_relations: List[FactRelation] = []`; `knowledge_ledger: List[KnowledgeEntry] = []`; `belief_ledger: List[BeliefEntry] = []`; `reader_ledger: List[ReaderKnowledgeEntry] = []`; `active_arc/active_chapter: Optional[Any] = None`; `story_threads/foreshadowing: List[str] = []`; `state_hash: str`.
  - `def with_state_hash(state: StoryState) -> StoryState` — returns a copy whose `state_hash = canonical_hash(state.model_dump(mode="json", exclude={"state_hash"}))`. This is the ONLY sanctioned way to stamp a hash (reducers in Tasks 8~11 call it after applying events).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_state_model.py`:
```python
from plot_engine.models.state import StoryState, with_state_hash
from plot_engine.canonical import canonical_hash

def _empty():
    return StoryState(story_id="s1", chapter_no=1, version=0, epoch="epoch_0", state_hash="")

def test_hash_excludes_itself():
    s = with_state_hash(_empty())
    assert s.state_hash == canonical_hash(
        _empty().model_dump(mode="json", exclude={"state_hash"}))

def test_hash_is_stable_across_rebuild():
    a = with_state_hash(_empty()).state_hash
    b = with_state_hash(_empty()).state_hash
    assert a == b

def test_default_collections_empty():
    s = _empty()
    assert s.characters == {} and s.knowledge_ledger == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_state_model.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `models/state.py`**

Define `StoryState` with the exact field set above. Implement `with_state_hash` as `state.model_copy(update={"state_hash": canonical_hash(state.model_dump(mode="json", exclude={"state_hash"}))})`. Keep it a plain aggregate — no behavior beyond the hash stamper.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_state_model.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/models/state.py plot_engine/tests/test_state_model.py
git commit -m "feat(plot-engine): StoryState aggregate + hash stamper (10 §13)"
```

---

## Task 6: Append-only Event Log (SQLite WAL)

**Files:**
- Create: `plot_engine/eventlog.py`
- Test: `plot_engine/tests/test_eventlog.py`

**Interfaces:**
- Consumes: `Event` (Task 1), `canonical_json` (Task 2).
- Produces:
  - `class EventLog` with `__init__(self, db_path: str)` (opens SQLite, `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, creates table `events(story_id TEXT, chapter INTEGER, seq INTEGER, event_id TEXT UNIQUE, orphan INTEGER DEFAULT 0, payload_json BLOB NOT NULL, PRIMARY KEY(story_id, chapter, seq))`).
  - `def append(self, story_id: str, events: list[Event]) -> None` — inserts each event as `canonical_json(event.model_dump(mode="json"))` bytes; a duplicate `(story_id, chapter, seq)` or duplicate `event_id` raises `sqlite3.IntegrityError` (caller treats as rejection, Review Focus #5). Never UPDATEs or DELETEs payload.
  - `def mark_orphan(self, story_id: str, chapter: int) -> None` — sets `orphan=1` for a chapter's events (07 §7.5 R6; log rows retained).
  - `def read_chapter(self, story_id: str, chapter: int, include_orphan: bool = False) -> list[Event]` — returns non-orphan events in `seq` order (reconstruct via `Event(**json.loads(bytes))`).
  - `def read_range(self, story_id: str, from_chapter: int, to_chapter: int) -> list[Event]` — ordered by `(chapter, seq)`, skipping orphans.

**Design decision:** `Event` has no `story_id` field, so every `EventLog` method takes `story_id` as its first argument. The tests below use that shape.

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_eventlog.py`:
```python
import sqlite3, pytest
from plot_engine.eventlog import EventLog
from plot_engine.models.event import Event

def _ev(ch, seq):
    return Event(event_id=f"evt_{ch:08d}_{seq:03d}", epoch="epoch_0",
                 event_type="OBSERVES", chapter=ch, seq=seq,
                 payload={"fact_id":"fact_000003","method":"sight"})

def test_append_then_read_roundtrips(tmp_path):
    log = EventLog(str(tmp_path / "ev.db"))
    log.append("s1", [_ev(47, 0), _ev(47, 1)])
    got = log.read_chapter("s1", 47)
    assert [e.seq for e in got] == [0, 1]

def test_duplicate_seq_rejected(tmp_path):
    log = EventLog(str(tmp_path / "ev.db"))
    log.append("s1", [_ev(47, 0)])
    with pytest.raises(sqlite3.IntegrityError):
        log.append("s1", [_ev(47, 0)])

def test_orphan_excluded_from_read(tmp_path):
    log = EventLog(str(tmp_path / "ev.db"))
    log.append("s1", [_ev(48, 0)])
    log.mark_orphan("s1", 48)
    assert log.read_chapter("s1", 48) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_eventlog.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `eventlog.py`**

Use stdlib `sqlite3`. `append` is INSERT-only (append-only). Payload stores canonical bytes so replay is byte-identical. Enforce uniqueness via the PRIMARY KEY `(story_id, chapter, seq)` and `event_id UNIQUE`. `mark_orphan` flips the flag only — never deletes. Keep `read_*` ordering in SQL (`ORDER BY chapter, seq`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_eventlog.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/eventlog.py plot_engine/tests/test_eventlog.py
git commit -m "feat(plot-engine): append-only SQLite WAL event log (07 §7.1, C5)"
```

---

## Task 7: CAS State Store + snapshots

**Files:**
- Create: `plot_engine/store.py`
- Test: `plot_engine/tests/test_store.py`

**Interfaces:**
- Consumes: `StoryState` (Task 5), `canonical_hash` (Task 2), `EventLog` (Task 6).
- Produces:
  - `@dataclass StateEnvelope(story_id: str, version: int, chapter_no: int, state: StoryState, state_hash: str)` (07 §7.2).
  - `@dataclass CommitResult(status: str, new_version: int | None = None, current_version: int | None = None, message: str = "")` (`status ∈ {"OK","CONFLICT","DUPLICATE"}`).
  - `class StateStore` with `__init__(self, db_path, *, snapshot_every: int = 5)` (WAL; tables `states(story_id, version, chapter_no, state_hash, envelope BLOB, PRIMARY KEY(story_id, version))`, `snapshots(story_id, chapter_no, version, state_hash, envelope BLOB, PRIMARY KEY(story_id, version))`, `commit_log(story_id, chapter_no, version, state_hash, proposal_set_hash, ts, PRIMARY KEY(story_id, chapter_no, proposal_set_hash))`).
  - `def load_latest(self, story_id: str) -> StateEnvelope` — highest `version`; raises `KeyError` if none.
  - `def init_genesis(self, story_id: str, base_state: StoryState) -> None` — persist the chapter-0 / version-0 base state BOTH as a `states` row and a `snapshots` row, so replay always has a starting point even before the first N-chapter snapshot fires. Idempotent per `(story_id, 0)`.
  - `def persist(self, story_id: str, new_state: StoryState, expected_version: int, *, proposal_set_hash: str, event_log: EventLog, events: list[Event]) -> CommitResult` — the 07 §7.1/§7.2 transaction: idempotency-key check → append events → `load_latest` version compare → CONFLICT on mismatch → write state at `expected_version+1` → snapshot if `(chapter_no % snapshot_every == 0)` → commit-log row → `CommitResult("OK", ...)`. Rolls back on any failure (F1/F2/F3) leaving the log intact.
  - `def load_snapshot_at_or_before(self, story_id: str, chapter_no: int) -> StateEnvelope | None` — for replay (Task 13).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_store.py`:
```python
import pytest
from plot_engine.store import StateStore, CommitResult
from plot_engine.eventlog import EventLog
from plot_engine.models.state import StoryState, with_state_hash

def _st(ch, ver):
    return with_state_hash(StoryState(story_id="s1", chapter_no=ch, version=ver,
                                      epoch="epoch_0", state_hash=""))

@pytest.fixture
def env(tmp_path):
    return StateStore(str(tmp_path/"s.db")), EventLog(str(tmp_path/"e.db"))

def test_first_commit_ok(env):
    store, log = env
    r = store.persist("s1", _st(1, 1), 0, proposal_set_hash="h1", event_log=log, events=[])
    assert r.status == "OK" and r.new_version == 1

def test_cas_conflict(env):
    store, log = env
    store.persist("s1", _st(1, 1), 0, proposal_set_hash="h1", event_log=log, events=[])
    r = store.persist("s1", _st(1, 1), 0, proposal_set_hash="h2", event_log=log, events=[])
    assert r.status == "CONFLICT" and r.current_version == 1

def test_idempotent_duplicate_returns_cached(env):
    store, log = env
    a = store.persist("s1", _st(1, 1), 0, proposal_set_hash="hX", event_log=log, events=[])
    b = store.persist("s1", _st(1, 1), 0, proposal_set_hash="hX", event_log=log, events=[])
    assert a.status == "OK" and b.status == "DUPLICATE"

def test_snapshot_written_at_multiple_of_5(env):
    store, log = env
    ver = 0
    for ch in range(1, 6):
        store.persist("s1", _st(ch, ver+1), ver, proposal_set_hash=f"h{ch}", event_log=log, events=[])
        ver += 1
    assert store.load_snapshot_at_or_before("s1", 5) is not None
    assert store.load_snapshot_at_or_before("s1", 4) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_store.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `store.py`**

Single SQLite connection with explicit `BEGIN IMMEDIATE` transactions for the write path (this is the CAS serialization point; `expected_version` compare is inside the transaction). Persist the `StateEnvelope` by serializing `new_state.model_dump(mode="json")` through `canonical_json` so bytes are stable. Idempotency: a `commit_log` row with the same `(story_id, chapter_no, proposal_set_hash)` short-circuits to `CommitResult("DUPLICATE")` (07 §8 R2). Snapshot rule is 07 §7.3 R2 (default N=5, chapter multiple).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_store.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/store.py plot_engine/tests/test_store.py
git commit -m "feat(plot-engine): CAS state store + snapshots + commit-log idempotency (07 §7, C1/C5)"
```

---

## Task 8: Knowledge reducer

**Files:**
- Create: `plot_engine/reducers/__init__.py` (empty)
- Create: `plot_engine/reducers/knowledge.py`
- Test: `plot_engine/tests/test_reducer_knowledge.py`

**Interfaces:**
- Consumes: `Event`, `StoryState`, `KnowledgeEntry`, `BeliefEntry`, `with_state_hash`.
- Produces: `def reduce_knowledge(event: Event, state: StoryState) -> StoryState` handling `OBSERVES, READS, IS_TOLD, INFERS, FACT_CONTRADICTED` (03 §4.3 R1~R7, §5.4). Upsert by `(character_id, fact_id)`; on equal-stronger keep max and append the new `source_event_id` (R5). All arithmetic integer-only.

Rules to implement exactly:
- `OBSERVES` → state `known` (min), `strength = max(old, 900)`.
- `READS` → `known`, `strength = max(old, 800)`.
- `IS_TOLD` → `believed` (if below `known`), `strength = (trust_level * message_strength) // 1000` from payload (01 §4.1). Never silently exceed `known`.
- `INFERS` → `suspected`, `strength = min over evidence-entry strengths`, then `× event.confidence // 1000` (03 §4.3 R4); 03 §9 worked example: evidence `fact_000003` strength 1000, confidence 700 → result 700 `suspected`.
- `FACT_CONTRADICTED` (03 §5.4) on the entry keyed by `payload["fact_id"]`: `confirmed/known → suspected` at `strength ×4 // 10` ; `believed/suspected → suspected` at `×4 // 10`; `unknown` unchanged (finding deferred to Task 12).
- State ordering `unknown < suspected < believed < known < confirmed`; a rule may raise state only via its own event; only `FACT_CONTRADICTED` lowers (R6/R7).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_reducer_knowledge.py`:
```python
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.models.ledger import KnowledgeEntry
from plot_engine.models.fact import Fact
from plot_engine.reducers.knowledge import reduce_knowledge

def _state_with_facts(fact_ids):
    facts = {fid: Fact(fact_id=fid, fact_type="event", proposition="p",
                       canonical_form=f"p({fid})", narrative_truth="true",
                       objective_truth="true", defined_at_chapter=47, epoch="epoch_0")
             for fid in fact_ids}
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0",
                      facts=facts, state_hash="")

def _ev(typ, payload, seq=0, conf=1000):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor="char_000001", target=payload.get("fact_id") or payload.get("conclusion_fact_id"),
                 chapter=47, seq=seq, payload=payload, confidence=conf)

def test_observes_sets_known_900():
    s = _state_with_facts(["fact_000003"])
    out = reduce_knowledge(_ev("OBSERVES", {"fact_id":"fact_000003","method":"sight"}), s)
    e = out.knowledge_ledger[0]
    assert e.knowledge_state == "known" and e.strength == 900

def test_infers_floor_division_is_integer():
    s = _state_with_facts(["fact_000001","fact_000003"])
    s.knowledge_ledger.append(KnowledgeEntry(character_id="char_000001", fact_id="fact_000003",
        knowledge_state="known", strength=1000, source_event_id="evt_00000047_000",
        acquired_at_chapter=47, last_updated_chapter=47, epoch="epoch_0"))
    out = reduce_knowledge(_ev("INFERS", {"conclusion_fact_id":"fact_000001",
        "evidence_fact_ids":["fact_000003"]}, seq=1, conf=700), s)
    concl = [k for k in out.knowledge_ledger if k.fact_id=="fact_000001"][0]
    assert concl.knowledge_state == "suspected" and concl.strength == 700

def test_fact_contradicted_downgrades_x04():
    s = _state_with_facts(["fact_000001","fact_000002"])
    s.knowledge_ledger.append(KnowledgeEntry(character_id="char_000001", fact_id="fact_000001",
        knowledge_state="known", strength=1000, source_event_id="evt_00000047_000",
        acquired_at_chapter=47, last_updated_chapter=47, epoch="epoch_0"))
    out = reduce_knowledge(_ev("FACT_CONTRADICTED",
        {"fact_id":"fact_000001","contradicting_fact_id":"fact_000002"}, seq=2), s)
    d = [k for k in out.knowledge_ledger if k.fact_id=="fact_000001"][0]
    assert d.knowledge_state == "suspected" and d.strength == 400  # 1000 * 4 // 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_reducer_knowledge.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `reducers/knowledge.py`**

Pure function: copy `state.knowledge_ledger` into a working list, find the `(character_id=actor, fact_id)` entry, apply the rule for `event.event_type`, replace/append, return `with_state_hash(state.model_copy(update={"knowledge_ledger": new_list, ...}))`. Use integer `//` everywhere; `×0.4` downgrade is `strength * 4 // 10`. Do NOT import `BeliefEntry` math helpers here; keep the module one responsibility. `IS_TOLD` reads `payload["trust_level"]` and `payload["message_strength"]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_reducer_knowledge.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/reducers/knowledge.py plot_engine/tests/test_reducer_knowledge.py
git commit -m "feat(plot-engine): knowledge reducer (03 §4.3/§5.4, fixed-point)"
```

---

## Task 9: Belief + Statement reducer

**Files:**
- Create: `plot_engine/reducers/belief.py`
- Test: `plot_engine/tests/test_reducer_belief_statement.py`

**Interfaces:**
- Consumes: `Event`, `StoryState`, `BeliefEntry`, `with_state_hash`.
- Produces: `def reduce_belief(event, state) -> StoryState` handling `BELIEVES, SUSPECTS, DOUBTS` (self-directed) and `STATES, LIES, OMITS, HINTS` (audience-directed → Belief updates per 03 §5.3 R1~R4).

Rules:
- `BELIEVES` → `believes`, `strength = payload["belief_strength"]`.
- `SUSPECTS` → `suspects` (do not downgrade an existing `believes` unless `DOUBTS`).
- `DOUBTS` → `doubts`.
- `STATES` → each audience member gets/updates a `believes` entry for `payload["fact_id"]`, `strength = trust_of_speaker × DEFAULT // 1000` (Phase 0: `trust_of_speaker = event.confidence`; record `source_event_id`).
- `LIES` → audience `believes` `payload["stated_fact_id"]`; speaker's own belief unchanged; log a `lie_event` reference via `source_event_id`.
- `OMITS` → no Belief update (finding/omission tracking deferred; this reducer is a no-op on ledgers).
- `HINTS` → audience entries set to `suspects`.
- Belief ordering `doubts < suspects < believes`; `is_true` left `None` (derived later, not on replay path — 03 §5.1).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_reducer_belief_statement.py`:
```python
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.reducers.belief import reduce_belief

def _st():
    return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0", state_hash="")

def _ev(typ, payload, seq=0, conf=1000):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor="char_000001", chapter=47, seq=seq, payload=payload, confidence=conf)

def test_believes_sets_strength():
    out = reduce_belief(_ev("BELIEVES", {"fact_id":"fact_000002","belief_strength":700}), _st())
    e = out.belief_ledger[0]
    assert e.belief_state == "believes" and e.strength == 700 and e.is_true is None

def test_states_updates_audience_not_speaker():
    out = reduce_belief(_ev("STATES", {"audience":["char_000009"],"fact_id":"fact_000001"}), _st())
    assert {b.character_id for b in out.belief_ledger} == {"char_000009"}

def test_hints_sets_suspects():
    out = reduce_belief(_ev("HINTS", {"audience":["char_000009"],"fact_id":"fact_000001"}), _st())
    assert out.belief_ledger[0].belief_state == "suspects"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_reducer_belief_statement.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `reducers/belief.py`**

Two families in one module: self-directed (`BELIEVES/SUSPECTS/DOUBTS` → actor's own entry) and audience-directed (`STATES/LIES/OMITS/HINTS` → one entry per `payload["audience"]`). Upsert by `(character_id, fact_id)`, respect ordering, return `with_state_hash(...updated belief_ledger...)`. `OMITS` returns the state hash-stamped but with an unchanged ledger (still a pure copy).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_reducer_belief_statement.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/reducers/belief.py plot_engine/tests/test_reducer_belief_statement.py
git commit -m "feat(plot-engine): belief + statement reducers (03 §5.1/§5.3)"
```

---

## Task 10: World reducer (entities)

**Files:**
- Create: `plot_engine/reducers/world.py`
- Test: `plot_engine/tests/test_reducer_world.py`

**Interfaces:**
- Consumes: `Event`, `StoryState`, entity models (Task 3), `Fact` (Task 4), `with_state_hash`.
- Produces: `def reduce_world(event, state) -> StoryState` handling `HAPPENS, REVEALS, CHANGES, ITEM_ACQUIRED, ITEM_CONSUMED, RELATIONSHIP_CHANGED` (10 §4.3, §9.1 R4, §10.1, 01 §4.1).

Rules:
- `REVEALS` (`payload: {fact_id, new_narrative_truth}`) → set `state.facts[fact_id].narrative_truth`; if the fact's `objective_truth` differs, this is legal (Validator flags `reveal_stage=confirmed` mismatch in Task 12, 02 §6 R7).
- `CHANGES` (`payload: {field, old_value, new_value}`, field ∈ status/realm/location/faction/attributes/abilities) → mutate `state.characters[actor]`'s matching attribute; `field=status` must follow 10 §4.2 legal transitions (illegal transitions are caught by Task 12; the reducer still applies the value so the checker can see it). `status=dead` also sets `death_chapter = event.chapter`.
- `ITEM_ACQUIRED` (`{character_id, item_id, quantity>=1}`) → upsert merged `InventoryEntry` when item `stackable` (10 §10.1 R5), new entry when not; `unique` item forces `quantity=1`.
- `ITEM_CONSUMED` (`{character_id, item_id, quantity>=1}`) → subtract from the held total and **clamp the stored `quantity` at 0** (the model forbids negatives: 10 §10 `ge=0` / I4, so a negative can never be persisted). The over-draw itself is NOT silently forgiven — the invariant checker (Task 12) recomputes held-vs-consumed **from the events** and emits finding `H4.1` (Review Focus #3). Stackable merge decrements existing entries.
- `RELATIONSHIP_CHANGED` (`{from, to, relationship_type, strength_delta, trust_delta}`) → upsert `Relationship`; apply deltas then **clamp `strength`/`trust` to [0,1000]** (model `ge/le`); `symmetric=True` stores one row (10 §9.1 R1); `symmetric=False` stores both directions (R2). Out-of-range clamping is recorded so the commit-layer Validator can flag the anomalous raw delta.

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_reducer_world.py`:
```python
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.models.entity import Character, Item
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
    out = reduce_world(_ev("CHANGES", {"field":"status","old_value":"alive","new_value":"dead"}), _st())
    c = out.characters["char_000001"]
    assert c.status == "dead" and c.death_chapter == 47

def test_item_acquired_then_consumed_merges():
    s = _st()
    s = reduce_world(_ev("ITEM_ACQUIRED", {"character_id":"char_000001","item_id":"item_000001","quantity":3}), s)
    s = reduce_world(_ev("ITEM_CONSUMED", {"character_id":"char_000001","item_id":"item_000001","quantity":1}, seq=1), s)
    assert sum(i.quantity for i in s.inventory) == 2

def test_item_consumed_overdraw_clamps_to_zero():
    s = _st()
    s = reduce_world(_ev("ITEM_ACQUIRED", {"character_id":"char_000001","item_id":"item_000001","quantity":1}), s)
    s = reduce_world(_ev("ITEM_CONSUMED", {"character_id":"char_000001","item_id":"item_000001","quantity":5}, seq=1), s)
    # model forbids negatives (ge=0): stored qty floors at 0; Task 12 flags the over-draw from events
    assert all(i.quantity >= 0 for i in s.inventory)
    assert sum(i.quantity for i in s.inventory) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_reducer_world.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `reducers/world.py`**

Mutate the relevant collection on a `model_copy` of state (never the input). `REVEALS` touches `facts`, `CHANGES` touches `characters`, `ITEM_*` touch `inventory`, `RELATIONSHIP_CHANGED` touches `relationships`. For `CHANGES`, map `payload["field"]` to the Character attribute name (`status`/`realm`/`current_location`/`faction_id`/`attributes`/`abilities`) per 10 §4.3. Return `with_state_hash(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_reducer_world.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/reducers/world.py plot_engine/tests/test_reducer_world.py
git commit -m "feat(plot-engine): world entity reducer (10 §4.3/§9/§10, 01 §4.1)"
```

---

## Task 11: Reader + Plot reducer + top-level dispatch

**Files:**
- Create: `plot_engine/reducers/reader.py`
- Create: `plot_engine/reducers/plot.py`
- Create: `plot_engine/reducer.py`
- Test: `plot_engine/tests/test_reducer_dispatch.py`

**Interfaces:**
- Consumes: all category reducers (Tasks 8~10), `ReaderKnowledgeEntry`, `with_state_hash`.
- Produces:
  - `def reduce_reader(event, state) -> StoryState` (`03 §6.3`): `READER_LEARNS → reader_state="knows", reader_strength = max(old, payload.get("strength", event.confidence))`; `READER_DECEIVED → "deceived"`; `READER_HINTED → "hinted"` (unaware→hinted; does NOT downgrade an existing `knows`). Key by `fact_id`.
  - `def reduce_plot(event, state) -> StoryState`: Phase 0 records Plot events (`CASE_SOLVED, FORESHADOWING_SET, FORESHADOWING_PAID, CONTRACT_FULFILLED, CONTRACT_VIOLATED`) by appending identifiers to `story_threads`/`foreshadowing` where meaningful, otherwise a no-op that still re-stamps the hash. Plot semantics are thin until the Contract layer (a later plan); do not invent fields.
  - `class Reducer` with `def apply(self, event: Event, state: StoryState) -> StoryState` — dispatch table mapping each of the 26 `event_type` values to its category function (03 §8 + 07 §6.1). Unmapped type raises `ValueError`.

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_reducer_dispatch.py`:
```python
import pytest
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.reducers.reader import reduce_reader
from plot_engine.reducer import Reducer

def _st(): return StoryState(story_id="s1", chapter_no=47, version=1, epoch="epoch_0", state_hash="")
def _ev(typ, payload, seq=0, conf=1000):
    return Event(event_id=f"evt_00000047_{seq:03d}", epoch="epoch_0", event_type=typ,
                 actor="char_000001", chapter=47, seq=seq, payload=payload, confidence=conf)

def test_reader_hinted_does_not_downgrade_knows():
    s = _st()
    s = reduce_reader(_ev("READER_LEARNS", {"fact_id":"fact_000003","strength":900}), s)
    s = reduce_reader(_ev("READER_HINTED", {"fact_id":"fact_000003"}, seq=1), s)
    r = [x for x in s.reader_ledger if x.fact_id=="fact_000003"][0]
    assert r.reader_state == "knows"

def test_dispatch_routes_observes_to_knowledge_ledger():
    out = Reducer().apply(_ev("OBSERVES", {"fact_id":"fact_000003","method":"sight"}), _st())
    assert len(out.knowledge_ledger) == 1

def test_dispatch_table_covers_all_26_types():
    from typing import get_args
    from plot_engine.models.event import EventType
    from plot_engine.reducer import _DISPATCH
    assert set(_DISPATCH.keys()) == set(get_args(EventType))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_reducer_dispatch.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement the three files**

`reader.py`/`plot.py` as above. `reducer.py`: a module-level `_DISPATCH: dict[str, Callable[[Event, StoryState], StoryState]]` covering all 26 types, and `Reducer.apply` looks up `_DISPATCH[event.event_type]`, raising `ValueError(f"unmapped event_type {event.event_type}")` on miss. Confirm coverage against `typing.get_args(EventType)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_reducer_dispatch.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/reducers/reader.py plot_engine/reducers/plot.py plot_engine/reducer.py plot_engine/tests/test_reducer_dispatch.py
git commit -m "feat(plot-engine): reader + plot reducers + top-level dispatch (03 §6.3/§8, 07 §6.1)"
```

---

## Task 12: Invariant checker (assert_consistent)

**Files:**
- Create: `plot_engine/consistency.py`
- Test: `plot_engine/tests/test_consistency.py`

**Interfaces:**
- Consumes: `StoryState`, `Event`, finding dict shape (Global Constraints).
- Produces: `def assert_consistent(state: StoryState, events: list[Event]) -> list[dict]` implementing the checkable subset of 10 §15 I1~I13 and 03 §10 I1~I8 for Phase 0. Each violation is `{"code": <ID>, "ord": <severity rank>, "severity": "hard"|"soft"|"observation", "detail": <human message>}`. Checkers NEVER mutate state (05 §9 I3). Return `[]` when clean.

Phase-0 checks (HARD unless noted):
- I1 ID global uniqueness across all entity dicts/lists.
- I2 references resolve: every `character_id`/`fact_id`/`item_id`/`loc_id`/`realm`/`faction_id` referenced in entities, ledgers and events exists.
- I3 `Character.current_location` ∈ locations or None.
- H4.1 inventory over-draw: recompute, per `(character_id, item_id)`, cumulative `ITEM_CONSUMED.quantity` vs cumulative `ITEM_ACQUIRED.quantity` from `events`; consumed > acquired → HARD finding `H4.1` (the stored `quantity` is already floored at 0 by the model, so this MUST be judged from events — Review Focus #3). `I4` (`quantity >= 0`) holds trivially via the model `ge=0`; keep it as a cheap assertion.
- I6 `Relationship.from_character/to_character` ∈ characters.
- I7 `dead`/`unborn` characters are not the `actor` of any event in `events` (or `missing` per §4.2 sub-rules → soft).
- I9 (03 §10) every ledger entry's `source_event_id` is a committed event id and its `fact_id` exists.
- 02 §6 R7 / 03 I5: `narrative_truth != objective_truth` → `reveal_stage != confirmed`.
- `FACT_CONTRADICTED` on an `unknown`/absent target → observation (soft, 03 §5.4).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_consistency.py`:
```python
from plot_engine.models.state import StoryState
from plot_engine.models.entity import Character, InventoryEntry
from plot_engine.models.event import Event
from plot_engine.consistency import assert_consistent

def _codes(state, events=()):
    return {f["code"] for f in assert_consistent(state, list(events))}

def test_overdraw_detected_from_events():
    # model floors stored quantity at 0, so over-draw is judged from events (H4.1)
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0", state_hash="")
    acq = Event(event_id="evt_00000001_000", epoch="epoch_0", event_type="ITEM_ACQUIRED",
                actor="char_000001", chapter=1, seq=0,
                payload={"character_id":"char_000001","item_id":"item_000001","quantity":1})
    con = Event(event_id="evt_00000001_001", epoch="epoch_0", event_type="ITEM_CONSUMED",
                actor="char_000001", chapter=1, seq=1,
                payload={"character_id":"char_000001","item_id":"item_000001","quantity":5})
    assert "H4.1" in _codes(s, [acq, con])

def test_dead_actor_is_hard():
    c = Character(character_id="char_000001", name="x", status="dead",
                  death_chapter=10, introduced_at_chapter=1, epoch="epoch_0")
    s = StoryState(story_id="s1", chapter_no=12, version=1, epoch="epoch_0",
                   characters={"char_000001": c}, state_hash="")
    e = Event(event_id="evt_00000012_000", epoch="epoch_0", event_type="OBSERVES",
              actor="char_000001", chapter=12, seq=0, payload={"fact_id":"fact_000001","method":"sight"})
    assert "I7" in _codes(s, [e])

def test_clean_state_no_findings():
    s = StoryState(story_id="s1", chapter_no=1, version=1, epoch="epoch_0", state_hash="")
    assert assert_consistent(s, []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_consistency.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `consistency.py`**

Iterate the check list, each appending a finding dict with a stable `code` (`"I1".."I9"`, `"R7"`, `"FACT_CONTRADICTED_UNKNOWN"`). Order findings by severity rank hard(0) < soft(1) < observation(2). No state mutation. Keep each check a small helper function for readability.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_consistency.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/consistency.py plot_engine/tests/test_consistency.py
git commit -m "feat(plot-engine): invariant checker assert_consistent (10 §15, 03 §10)"
```

---

## Task 13: Per-chapter replay + hash parity

**Files:**
- Create: `plot_engine/replay.py`
- Test: `plot_engine/tests/test_replay.py`

**Interfaces:**
- Consumes: `EventLog`, `StateStore` (snapshot loader), `Reducer`, `assert_consistent`, `with_state_hash`, `canonical_hash`.
- Produces:
  - `def replay_to_chapter(store: StateStore, log: EventLog, reducer: Reducer, story_id: str, chapter_no: int) -> StoryState` — start from `store.load_snapshot_at_or_before(story_id, chapter_no)` (or a genesis empty state if none), then apply every event in `log.read_range(story_id, start_chapter+1, chapter_no)` in `(chapter, seq)` order via `reducer.apply`, re-stamping hash after the last event.
  - `def verify_parity(store: StateStore, log: EventLog, reducer: Reducer, story_id: str, chapter_no: int) -> bool` — `replay_to_chapter(...).state_hash == store.load_latest(story_id).state_hash` for that chapter (07 §7.5 R5/R6). On mismatch the caller marks the chapter orphan and stops the pipeline (rollback is a later/commit-layer concern; here we only prove parity).

- [ ] **Step 1: Write the failing tests**

`plot_engine/tests/test_replay.py`:
```python
from plot_engine.store import StateStore
from plot_engine.eventlog import EventLog
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.models.fact import Fact
from plot_engine.reducer import Reducer
from plot_engine.replay import replay_to_chapter, verify_parity

def _fact(fid): return Fact(fact_id=fid, fact_type="event", proposition="p",
    canonical_form=f"p({fid})", narrative_truth="true", objective_truth="true",
    defined_at_chapter=1, epoch="epoch_0")

def _genesis():
    # chapter_no/version are the PRE-reduce base; the reducer stamps state_hash last.
    return StoryState(story_id="s1", chapter_no=0, version=0, epoch="epoch_0",
                      facts={"fact_000003": _fact("fact_000003")}, state_hash="")

def _ev():
    return Event(event_id="evt_00000001_000", epoch="epoch_0", event_type="OBSERVES",
                 actor="char_000001", chapter=1, seq=0,
                 payload={"fact_id":"fact_000003","method":"sight"})

def test_replay_hash_equals_persisted_hash(tmp_path):
    store, log, red = StateStore(str(tmp_path/"s.db")), EventLog(str(tmp_path/"e.db")), Reducer()
    store.init_genesis("s1", _genesis())            # chapter-0 base snapshot
    reduced = red.apply(_ev(), _genesis())          # hash stamped by the reducer
    store.persist("s1", reduced, 0, proposal_set_hash="h1", event_log=log, events=[_ev()])
    replayed = replay_to_chapter(store, log, red, "s1", 1)
    assert replayed.state_hash == store.load_latest("s1").state_hash

def test_verify_parity_true(tmp_path):
    store, log, red = StateStore(str(tmp_path/"s.db")), EventLog(str(tmp_path/"e.db")), Reducer()
    store.init_genesis("s1", _genesis())
    reduced = red.apply(_ev(), _genesis())
    store.persist("s1", reduced, 0, proposal_set_hash="h1", event_log=log, events=[_ev()])
    assert verify_parity(store, log, red, "s1", 1) is True
```
**Contract note for the implementer:** the persisted state and the replayed state MUST be produced by the SAME reduce path (apply events to the genesis/snapshot state, reducer stamps the final hash). Do not mutate `chapter_no`/`version`/ledger after `with_state_hash`, or the hashes will diverge. If `persist` recomputes `state_hash`, it must exclude the `state_hash` field exactly as `with_state_hash` does (both delegate to `canonical_hash(model_dump(mode="json", exclude={"state_hash"}))`) so the two agree.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_replay.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `replay.py`**

Rebuild purely from persisted bytes (snapshot envelope + canonical event payloads) so it does not depend on in-memory objects. Apply events with `Reducer.apply`; the last applied state IS the replayed state (its `state_hash` was stamped by the reducer's `with_state_hash`). `verify_parity` compares hashes as hex strings, never object identity. Genesis path: if no snapshot exists, reconstruct from the initial state stored at version 0/lowest chapter.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_replay.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add plot_engine/replay.py plot_engine/tests/test_replay.py
git commit -m "feat(plot-engine): per-chapter replay + state_hash parity (07 §7.5)"
```

---

## Task 14: Golden 3-chapter end-to-end fixture

**Files:**
- Create: `plot_engine/tests/fixtures/traitor_arc.json`
- Test: `plot_engine/tests/test_golden_e2e.py`

**Interfaces:**
- Consumes: full stack (store, eventlog, reducer, consistency, replay, canonical).
- Produces: a regression harness committing the 03 §9 worked example (chapter 47) plus two surrounding chapters, asserting the exact expected ledger values and hash parity.

Content of `traitor_arc.json`: the 3 Facts (`fact_000001` traitor exists `narrative_truth=true/objective=true/hinted`, `fact_000002` 李四是叛徒 `narrative=unknown/objective=false/hidden`, `fact_000003` 印章17伪造 `confirmed`) and the 3 Events (`evt_00000047_001` OBSERVES, `evt_00000047_002` INFERS confidence 700, `evt_00000047_003` READER_LEARNS strength 900) copied verbatim from 03 §9, with `char_000001` and `loc_000012` in genesis entities.

- [ ] **Step 1: Write the failing test**

`plot_engine/tests/test_golden_e2e.py`:
```python
import json
from pathlib import Path
from plot_engine.store import StateStore
from plot_engine.eventlog import EventLog
from plot_engine.models.state import StoryState, with_state_hash
from plot_engine.models.event import Event
from plot_engine.reducer import Reducer
from plot_engine.consistency import assert_consistent
from plot_engine.replay import verify_parity

FIX = Path(__file__).parent / "fixtures" / "traitor_arc.json"

def test_golden_traitor_arc(tmp_path):
    data = json.loads(FIX.read_text(encoding="utf-8"))
    store, log, red = StateStore(str(tmp_path/"s.db")), EventLog(str(tmp_path/"e.db")), Reducer()
    genesis = StoryState(**{**data["genesis"], "state_hash": ""})
    store.init_genesis("s1", genesis)
    events = [Event(**e) for e in data["chapter47_events"]]
    state = genesis
    for ev in sorted(events, key=lambda e: (e.chapter, e.seq)):
        state = red.apply(ev, state)                # reducer stamps hash after each event
    hard = [f for f in assert_consistent(state, events) if f["severity"] == "hard"]
    assert hard == []
    # expected ledger values from 03 §9
    kn = {k.fact_id: (k.knowledge_state, k.strength) for k in state.knowledge_ledger}
    assert kn["fact_000003"][0] == "known" and kn["fact_000003"][1] >= 900
    assert kn["fact_000001"] == ("suspected", 700)
    rn = {r.fact_id: (r.reader_state, r.reader_strength) for r in state.reader_ledger}
    assert rn["fact_000003"] == ("knows", 900)
    # fact_000002 must appear in NO ledger
    assert "fact_000002" not in kn and "fact_000002" not in rn
    # commit the final reduced state (reducer already stamped it) + prove replay parity
    store.persist("s1", state, 0, proposal_set_hash="golden47", event_log=log, events=events)
    assert verify_parity(store, log, red, "s1", 47)
```
> `OBSERVES` in 03 §9 yields `known/1000` (event default strength 900 floor vs. 03 §9's stated 1000). Resolve the ONE discrepancy: 03 §4.3 R1 says `strength ≥ 900`; 03 §9 shows `1000`. Pin the reducer to `max(old, 900)` and, for the golden fixture, assert `kn["fact_000003"][0] == "known"` and `strength >= 900` (drop the exact `==1000` claim) so the test reflects the spec's floor, not the illustrative example. Note this in the fixture's `_comment`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest plot_engine/tests/test_golden_e2e.py -v`
Expected: FAIL — fixture/module missing.

- [ ] **Step 3: Author `fixtures/traitor_arc.json`**

Copy 03 §9 JSON verbatim into `{"genesis": {...entities, chapter_no:0, version:0, epoch:"epoch_0"...}, "chapter47_events": [three events]}`. Include `_comment` explaining the `strength >= 900` floor vs the illustrative `1000`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest plot_engine/tests/test_golden_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `pytest plot_engine/tests -v`
Expected: all tests PASS (green Phase 0 core state layer).

- [ ] **Step 6: Commit**

```bash
git add plot_engine/tests/fixtures/traitor_arc.json plot_engine/tests/test_golden_e2e.py
git commit -m "test(plot-engine): golden 3-chapter traitor-arc end-to-end (03 §9)"
```

---

## Out of scope for this plan (subsequent plans)

- **Validators (08 Day 8~11, 05 §4~6):** Level 1/2 rule engines H1~H8, LLM-as-validator Level 3. This plan ships only `assert_consistent` (the deterministic invariants the reducers need locally), not the full Validator stack.
- **Commit protocol wiring (08 Day 12~13, 07 §3~§5):** the Proposal→Validate→Reduce→Persist Stage orchestration, `EventProposal` model, two-phase sandbox, rejection_log. Store/reducer primitives here are the inputs to it.
- **ScenePlan / extraction channels / Writer markup对接 (08 Day 14~19):** `ScenePlan`, `reader_learns` markup parsing (07 §4.4), rule/llm/hybrid/markup Proposal generation and confidence linkage (07 §4.3).
- **10-chapter experiment (08 Day 20~22, 09 epoch, Arc/Contract layer).**
- **`detect_cycle` DAG check (01 §5.3)** — deferred with the Validator layer (Phase 0 only warns).
```
