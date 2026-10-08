# Alexandria Validator (Day 8–11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the deterministic Validator stack of 08 Day 8–11: contract/proposal models, Draft markup parsing channel (07 §4.4), markup→Proposal generation, and the three-level rule engine H1~H8 (Level 3 LLM excluded — it only emits SOFT/OBSERVATION and is deferred with the Writer layer).

**Architecture:** Stage 1 of the commit pipeline. A proposal batch is *simulated* through the existing pure `Reducer` against a throwaway copy of `StoryState`; rules assert against pre/mid/post simulation snapshots plus parsed Draft markup. No persistence, no LLM, read-only w.r.t. real state (05 §2 V4, §9 I3). Output is the serializable `ValidationResult` (05 §3) that Stage 3 persists with the commit (05 §8 R3).

**Tech Stack:** Python 3.12+, pydantic v2, pytest; existing `plot_engine` packages (models, reducer, consistency, canonical).

**Spec:** `alexandria-spec-v0.2/05_validation_protocol.md` (rule source), `04_contract_protocol.md` (contract schemas + V/W rules), `07_commit_protocol.md` §4 (Proposal, markup M1~M5, confidence R1~R4).

## Global Constraints

- HARD violations non-empty → cannot commit (05 V1); SOFT/OBSERVATION never block (V2/I2).
- Validator idempotent & read-only & serializable output (05 §8 R1–R4, §9 I1/I3/I4/I6); tests assert state is byte-identical after `validate`.
- No HARD rule may consult an LLM (05 §9 I1). L3 (Level 3) is out of scope for this plan.
- All numeric semantics are fixed-point ints ×1000 (05 §5.5). No floats.
- H6.3 (event cycle) is Phase-0 **SOFT** per 01 §5.2 R1' despite sitting in the HARD table — implement severity=soft, rule_id "H6.3", suggestion "Phase 1 升 HARD".
- `Finding.rule_id` exact strings: "H1.1"…"H8.2", "W3"-style codes NOT used — W-rules surface under their H-codes (W1→H5.3, W2→H5.4, W3→H5.1, W4→H5.2, W5→H5.7, W6→H5.6/H2.2, W7→H5.5). Markup M-codes map: M1→H5.5, M2→H2.3, M3→H2.3(soft), M4→H6.2, M5→H6.1. Anything unattributable → rule_id "MALFORMED_PROPOSAL" (05 §9 I6: never silently drop).
- Committed event ids are NOT reachable from the fixed 05 §10 signature; `Validator.validate` gains ONE keyword-only optional param `committed_event_ids: frozenset[str] = frozenset()` (H6.2/H6.5 need it). Documented deviation, superset-compatible.
- Chinese docstrings citing spec sections; `from __future__ import annotations`; tests live in `plot_engine/tests/`; run via `.venv` python -m pytest from repo root.

## Review Focus

1. **Markup spoofing/typos** — `<!-- hook: cliffhanger strength=1001 -->`, `<!-- reader_knows: ... -->`, hook outside last-3 paragraphs, two hooks: the parser must classify each defect and the validator must emit the right M-mapped code, never silently drop (05 §9 I6). → Task 3 + Task 6.
2. **A crashing proposal must not crash the validator** — missing payload key makes `Reducer` raise; simulation catches `KeyError/ValueError/ValidationError` into a HARD `MALFORMED_PROPOSAL` and excludes that proposal from further simulation. → Task 5.
3. **Quarantine interaction** — an H8.2-isolated proposal is excluded from the batch, then H5.1 (required_event missing) still fires normally on the *remaining* set (07 §4.3 R3). → Task 8.
4. **Cross-batch causal refs** — `preconditions` pointing at committed events (absent `committed_event_ids` → H6.2) vs future events (H6.5 HARD) vs intra-batch ids (resolvable). → Task 5.
5. **Duplicate (chapter, seq)** — deterministic event_id assignment collides; must surface as H6.4 and simulation must apply only the first, marking the rest malformed. → Task 2 + Task 5.

---

## File Structure

```
plot_engine/
├── models/contract.py      # 04 §3.1/§4.1 nine schemas          [Task 1]
├── models/proposal.py      # 07 §4.2 EventProposal + to_event    [Task 2]
├── markup.py               # 07 §4.4 Draft markup parser         [Task 3]
├── markup_channel.py       # markup → EventProposal (§4.3 通道1) [Task 4]
├── validator.py            # Finding/ValidationResult/Levels 1-2 [Tasks 5–8, 9 wiring]
└── tests/                  # test_contract_model / test_proposal_model / test_markup /
                            # test_markup_channel / test_validator_l1 / test_validator_l2 /
                            # test_validator_contract / test_validator_extraction /
                            # test_validator_integration
```

`validator.py` internal layout (one file, four sections — split further only if >400 lines):

```python
class Finding(BaseModel):      # 05 §3 verbatim
    rule_id: str
    severity: Literal["hard", "soft", "observation"]
    message: str
    location: Optional[str] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None

class ValidationResult(BaseModel):
    hard_violations: List[Finding] = []
    soft_warnings: List[Finding] = []
    observations: List[Finding] = []
    def can_commit(self) -> bool: ...

@dataclass class Simulation:   # sandbox of Stage-2 over a batch
    pre: StoryState            # == state as given (never mutated)
    cur: StoryState            # mid-batch projection
    applied: List[Event]       # successfully applied, in topo order
    failed: List[tuple[EventProposal, str]]

def _simulate(state, proposals, epoch) -> Simulation
    # sorted (chapter, seq); id collision → failed[MALFORMED_PROPOSAL duplicate];
    # to_event → Reducer.apply wrapped in try/(KeyError, ValueError, ValidationError)
    # → failed(reason). Returns Simulation; raises nothing.

class Validator:
    def validate(self, draft, proposals, contract, state,
                 *, committed_event_ids: frozenset = frozenset()) -> ValidationResult
        # order: H8 gate → parse markup → markup proposals merge (M2 pairing) →
        #        simulate → L1 (H1/H3/H4/H6) → L2 (H2/H5 + markup M-rules) →
        #        result = sorted findings bucketed by severity. Idempotent.
    def validate_contract(self, contract, arc, state) -> ValidationResult
        # H7 set + 04 §5.1 V1–V10 mapped to H7 codes.
```

## Task 1: Contract models (04 §3.1 / §4.1)

**Files:** Create `plot_engine/models/contract.py`; Test `plot_engine/tests/test_contract_model.py`

**Interfaces:** Produces (verbatim from spec): `KnowledgeGate`, `TurningPoint`, `ArcContract` (`arc_id ^arc_\d{3}$`, `chapter_range: Tuple[int,int]`, `tension_curve: List[int]`), `CharacterChange` (10-field enum, `operation ∈ add|remove|update`), `RequiredEvent`(`minimum_count=1`), `ForbiddenEvent`, `ChapterHook`(6-type enum, `strength ge/le 0..1000`), `ReaderSignal`, `ChapterContract` (all fields incl. `ending: ChapterHook`, `schema_version=2`).

- [ ] Step 1 failing tests: golden ChapterContract from 04 附录 A round-trip; bad `arc_id="arc_1"` rejected; `strength=1001` rejected; `field="bogus"` rejected.
- [ ] Steps 2–5: run-fail → implement → run-pass → commit `feat(plot-engine): contract models (04 §3.1/§4.1)`.

## Task 2: EventProposal + deterministic to_event (07 §4.2)

**Files:** Create `plot_engine/models/proposal.py`; Test `test_proposal_model.py`

**Interfaces:** Consumes `Event`. Produces:
```python
class EventProposal(BaseModel):   # 07 §4.2 verbatim, 12 fields
def proposal_event_id(p, ) -> str  # f"evt_{p.chapter:08d}_{p.seq:03d}"
def to_event(p, epoch: str) -> Event  # proposed_event_type→event_type, confidence→confidence
```

- [ ] Tests: round-trip keeps payload; id format `evt_00000047_002`; `extraction_method="bogus"` rejected; duplicate (chapter,seq) → same event_id (this IS the Review Focus #5 hook).
- [ ] Commit `feat(plot-engine): EventProposal model + deterministic event_id (07 §4.2)`.

## Task 3: Draft markup parser (07 §4.4)

**Files:** Create `plot_engine/markup.py`; Test `test_markup.py`

**Interfaces:** Produces:
```python
@dataclass HookAnno: kind: str | None; strength: int | None; para_index: int; raw: str
@dataclass ReaderAnno: kind: str  # "learns"|"hinted"|"deceived"
                       fact_id: str | None; para_index: int; raw: str
@dataclass DraftMarkup: hooks: list[HookAnno]; readers: list[ReaderAnno];
                        para_count: int; unknown: list[str]
def parse_markup(draft: str) -> DraftMarkup
```
Grammar: HTML comments only. Paragraphs = split on blank lines. Hook regex `<!--\s*hook:\s*(\w+)\s+strength=(\d+)\s*-->`; reader regex `<!--\s*reader_(learns|hinted|deceived):\s*(\S+)\s*-->`. Malformed/near-miss comments (`reader_knows`, strength=1001 parse-fail) land in the right defect bucket — NEVER dropped (I6). Parser does NOT enforce counts/positions (validator rules M1/M5 do).

- [ ] Tests: well-formed chapter (hook in last 3 paras) parses; `strength=1001` → HookAnno(kind set, strength=1001) (validator judges range); `<!-- reader_knows: fact_000001 -->` → `unknown`; three reader kinds each captured; CJK body unaffected; empty draft → para_count 0.
- [ ] Commit `feat(plot-engine): draft markup parser channel (07 §4.4 M-rules input)`.

## Task 4: markup → Proposal generation, channel 1 (07 §4.3)

**Files:** Create `plot_engine/markup_channel.py`; Test `test_markup_channel.py`

**Interfaces:** Consumes `DraftMarkup`, `EventProposal`. Produces:
```python
def markup_to_proposals(markup, chapter, start_seq) -> list[EventProposal]
```
reader annos → `READER_LEARNS/READER_HINTED/READER_DECEIVED`, `payload={"fact_id":...}`, `extraction_method="markup"`, `extraction_confidence=1000` (07 §4.3 通道1), actor None, source_ref=f"markup:reader_{kind}#{seq}". seq increments from `start_seq`. Fact-less/unknown annos are NOT turned into proposals (validator pairs annotations↔proposals instead).

- [ ] Tests: 2 annos → 2 proposals confidence 1000 method markup, seq contiguous; kind mapping exact.
- [ ] Commit `feat(plot-engine): markup proposal channel (07 §4.3 通道1)`.

## Task 5: Validator core — Simulation + Level-1 rules (H1/H3/H4/H6)

**Files:** Create `plot_engine/validator.py` (Finding/ValidationResult/Simulation skeleton + `_l1_*` functions); Test `test_validator_l1.py`

**Interfaces:** Produces the `Finding`/`ValidationResult` classes (Global Constraints) and `_simulate`. L1 checks (each takes `Simulation`, `state`, proposals; returns findings):

- **H1.1** — `actor` of any proposal is `dead`/`unborn` in *pre-simulation-at-that-point* state (respect in-batch `CHANGES status=dead`: acting AFTER death in same batch still HARD). `missing` → skip (soft sub-rule deferred to consistency I7).
- **H1.2 / H4.1** — for each `(character_id,item_id)` recompute acquired-vs-consumed over pre-state inventory + batch: consumed > held → H4.1 (both codes, same evidence: 05 lists H1.2 canon / H4.1 resource).
- **H1.3** — proposal.location set, actor has `current_location`, mismatch, and no same-batch `CHANGES(location)` to the new place before this event (W-S5; `missing` exempt).
- **H1.4 / H2.4** — payload carrying `ability_id` (Phase-0 convention): actor lacks it in `abilities` → H2.4; its `required_realm` tier > actor realm tier (`can_defeat`-style compare, 10 §8.1) → H1.4.
- **H3.1** — (chapter, seq) unsorted/duplicate beyond what to_event already flags → covered by H6.4; H3.1 reserved for preconditions order violation *within* batch (precondition seq ≥ own seq) → HARD.
- **H3.2** — `preconditions` ref id whose chapter number (parsed from `evt_%08d`) > contract.chapter_no → HARD.
- **H3.3** — proposal.chapter < state.chapter_no → HARD time reversal.
- **H3.4** — one actor with two different concrete `location`s among proposals in the batch without an intervening `CHANGES(location)` → HARD.
- **H4.2** — inventory recomputed total negative (model makes impossible; keep sentinel).
- **H4.3** — proposal.location names a `unlocked=False` location or one whose `unlock_conditions` (Phase-0 grammar `fact:<id>` / `realm:<id>` / `item:<id>`, 10 §5.2) unmet against the pre-sim state → HARD.
- **H6.1** — `proposed_event_type ∉ get_args(EventType)` (pydantic keeps it as str field) → HARD.
- **H6.2** — precondition id ∉ (committed_event_ids ∪ batch ids) → HARD.
- **H6.3** — cycle over batch-internal edges → **SOFT** (see Global Constraints).
- **H6.4** — duplicate computed event_id → HARD (first kept, later excluded via Simulation.failed with MALFORMED_PROPOSAL note).
- **H6.5** — precondition event_id with chapter > own chapter → HARD (stays HARD per 01 §5.2 R4).

- [ ] Tests (one per bullet above; ~15 tests). Include Review Focus #2: proposal missing payload key → `MALFORMED_PROPOSAL` HARD, validator returns (doesn't raise), state untouched. Review Focus #4: precondition vs committed_event_ids three-way. Idempotence smoke: same input twice → equal result.
- [ ] Commit `feat(plot-engine): validator level-1 rules via sandbox simulation (05 §4 H1/H3/H4/H6)`.

## Task 6: Level-2 rules — H2 / H5 + markup M-rules

**Files:** Modify `plot_engine/validator.py`; Test `test_validator_l2.py`

**Interfaces:** `_l2_*` functions. Contract:

- **H2.1** — pre-state ledger: any character `known/confirmed` a fact ∈ `contract.knowledge_forbidden` → HARD (per character).
- **H2.2** — `must_change(field=knowledge, operation=add, target=f)` and after simulation that char's entry for f is missing or weaker than `expected_value` rank → HARD.
- **H2.3** — markup↔proposal pairing: reader anno without matching READER_* proposal → HARD (M2); batch READER_* proposal (from state delta this chapter) without anno → SOFT (M3).
- **H5.1** — required_event.type count over batch < minimum_count → HARD.
- **H5.2** — forbidden_event.type present in batch → HARD.
- **H5.3** — W1: every must_change implemented via 10 §4.3 mapped event type in batch → else HARD. (knowledge → OBSERVES/READS/IS_TOLD/INFERS/BELIEVES/SUSPECTS/DOUBTS; location/realm/status/faction/attributes/abilities → CHANGES(field=…); relationship → RELATIONSHIP_CHANGED; inventory → ITEM_ACQUIRED/ITEM_CONSUMED.)
- **H5.4** — must_not_change: simulated post-state value of that field differs from pre-state → HARD.
- **H5.5** — exactly one hook anno, inside last 3 paragraphs, `kind == contract.ending.type`, `strength` int 0..1000 → else HARD (M1/M5). `ending.type == "none"` → hook anno absent expected? NO: "none" still requires the anno `<!-- hook: none strength=N -->` (恰好一条 rule is absolute; note in docstring).
- **H5.6** — must_change(field=knowledge) target ∈ knowledge_allowed not established → HARD (overlaps H2.2 — emit both codes when both trigger).
- **H5.7** — batch establishes any fact ∈ knowledge_forbidden (any Knowledge/Belief-class payload fact_id) → HARD (W5).
- **W8/W9 (record-only)** — reader_signal declared but no matching READER_* proposal this chapter → SOFT `rule_id "SIGNAL_UNHIT"`; `contract.tension_target` vs post-sim scene tension absent in Phase 0 → skip. These two are the ONLY codes outside the H table (both SOFT, non-blocking — 05 §9 I2 holds).

- [ ] Tests: one per code + Review Focus #1 (three markup defect drafts: wrong-type hook, strength=1001, anno outside last-3) + H2.3 both directions.
- [ ] Commit `feat(plot-engine): validator level-2 rules + markup M-rule wiring (05 H2/H5, 07 M1–M5)`.

## Task 7: validate_contract — H7 set (04 §5.1 V1–V10)

**Files:** Modify `plot_engine/validator.py`; Test `test_validator_contract.py`

- **H7.1** — pydantic pre-validation already ran if a contract object exists; check `schema_version == 2` & required-but-empty degenerates (`story_goal` nonempty) → HARD.
- **H7.2** — `contract.chapter_no ∉ arc.chapter_range` or `contract.arc_id != arc.arc_id` → HARD.
- **H7.3** — `abs(tension_target − arc.tension_curve[chapter_no − start]) > 300` → **SOFT** (v0.2 降档, exact threshold 300 per 05 H7.3; 04 D2' says 200 — use 300, 05 is the single source; add comment citing this).
- **H7.4** — set overlap allowed∩forbidden nonempty → HARD (I7).
- **H7.5** — same event_type in both required and forbidden lists → HARD.
- **H7.6** — same (character_id, field) in must_change and must_not_change → HARD.
- **H7.7** — `ending.type ∉ compat_matrix(story_goal_type)` (04 §4.4) → HARD.
- **H7.8** — `derived_from` entries not present in arc (gates/turning points/valid ids) → HARD.
- V9 → reuse I2-style existence: contract-referenced fact/char/loc/item/realm ids ∈ state → HARD, rule_id "H7.9" reserved? NO — V9 maps to H2-consistency family; emit rule_id "H7.8" is wrong. Resolution: V9 gets rule_id "H7.10" documented as 04 V9 mapping.
- V10 — field enum: pydantic guarantees; residual `operation`/`target` existence → HARD "H7.11".

- [ ] Tests: one per code; golden 附录 A contract vs its arc passes clean (`can_commit()` True, no hard).
- [ ] Commit `feat(plot-engine): validate_contract H7 rules + compat matrix (04 §5.1)`.

## Task 8: H8 extraction-confidence gate (07 §4.3 R1–R4)

**Files:** Modify `plot_engine/validator.py`; Test `test_validator_extraction.py`

- **H8.1** — ANY proposal `extraction_confidence < 500` → batch-level HARD "H8.1", and validate() short-circuits: return result with only this family (整批 FAIL).
- **H8.2** — 500 ≤ conf < 700 → proposal quarantined: excluded from simulation & L1/L2 batch; HARD finding `rule_id "H8.2"` message "EXTRACTION_UNVERIFIED" per quarantined proposal.
- **R3 interaction** — after quarantine, remaining proposals still evaluated → required_event shortfall fires H5.1 normally (Review Focus #3).
- **R4** — markup proposal whose fact_id ∉ state.facts → HARD "H6.2" with suggestion "归因 markup/抽取层".

- [ ] Tests: <500 short-circuit; two quarantined + H5.1; boundary 500/700 exact (500 isolates? NO: `< 500` fails, `[500,700)` isolates, `≥700` passes — pin: 499→H8.1, 500→H8.2, 699→H8.2, 700→clean).
- [ ] Commit `feat(plot-engine): H8 extraction gate + quarantine semantics (07 §4.3)`.

## Task 9: Top-level wiring, idempotence & integration

**Files:** Modify `plot_engine/validator.py`; Test `test_validator_integration.py`

**Interfaces:** Complete `Validator.validate()` per File Structure order. Wire `markup_to_proposals` merge: parsed annos generate channel-1 proposals which are APPENDED to caller-provided proposals only if the caller has none from markup (dedupe on (READER_*, fact_id) — markup proposals take priority, duplicates dropped silently is forbidden: dedupe emits observation). Also expose `plot_engine.validator` from nothing new — store/commit layer (Day 12–13) will import `Validator`, `ValidationResult`.

- [ ] Tests: (a) 05 §8 R1–R4: double-run equality; `canonical_json(result.model_dump(mode="json"))` stable; input state `model_dump()` byte-equal after run. (b) Golden: 附录 A chapter-47 contract + the 3 traitor-arc events-as-proposals + markup'd draft (reuse traitor_arc fixture text) → `can_commit()` True, zero hard/soft. (c) Same batch with dead actor → H1.1 hard → False.
- [ ] Full suite green: `python -m pytest plot_engine/tests -q`.
- [ ] Commit `feat(plot-engine): Validator top-level wiring + golden contract e2e (05 §10, 07 §5)`.

## Out of scope (subsequent plans)

- Stage-3 Commit orchestration & rejection_log (Day 12–13; consumes this plan's `Validator` + existing store/reducer/replay).
- ScenePlan models & SP1–SP7 (Day 14–16, 04 附录 B).
- Level-3 LLM-as-validator, rule/llm/hybrid proposal channels, dual-channel cross-validation (Day 17–19).
- Writer-side markup *generation* (this plan only parses and judges it).
