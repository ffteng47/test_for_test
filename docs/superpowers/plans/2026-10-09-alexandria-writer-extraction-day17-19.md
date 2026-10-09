# Alexandria Writer + Four-Channel Extraction (Day 17–19) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Stage-0 proposal composition (07 §4.2/§4.3): the four channels (markup / rule / LLM / cross-validation) with confidence linkage, a deterministic Writer draft assembler that emits the mandatory §4.4 markup, and an injectable Level-3 validator seam — all **network-free** (LLM & rule channels are injectable callables; the shipped defaults contribute nothing and the real model is wired by the caller in the Day 20–22 experiment).

**Architecture:** `extract.py` composes channels into caller `EventProposal`s with `extraction_confidence` set by channel-4 agreement rules; the existing `_h8_gate` in the Validator already turns those confidences into R1/R2 (H8.1/H8.2) outcomes, so extraction does **not** re-implement the linkage — it only sets the number. `writer.py` assembles a chapter draft from Scene fragments (Scene = minimal rewrite unit, 04 §8.4) and injects `<!-- hook -->` + `<!-- reader_* -->` so the markup channel can consume them. `Validator` gains an optional post-L1/L2 `level3_fn` that can only append SOFT/OBSERVATION (05 §9 I1). Stage-0 output feeds the already-built Validate→Reduce→Persist→Replay pipeline unchanged.

**Tech Stack:** Python 3.12+, pydantic v2, pytest; existing `plot_engine` (models.proposal, markup, markup_channel, validator, sceneplan, commit).

**Spec:** `07_commit_protocol.md` §4.2/§4.3/§4.4; `05_validation_protocol.md` §7 Level 3 + §9 I1/I2; `04_contract_protocol.md` §8.4; `06_revision_protocol.md` §4.0.

## Global Constraints

- 网络无关：LLM/规则通道是注入式 `Callable`，默认实现返回 `[]`；Phase 0 绝不发起网络请求或读密钥（Auto-Mode #6）。
- 置信度联动只**设值**，判定交 `_h8_gate`：一致→`hybrid`/1000，单通道→700，冲突→500（H8.2x，由 H8.1/H8.2 接住）。extraction_confidence ∈ 0..1000 定点整数。
- Stage-0 只产**叙事类** Proposal（rule/llm/hybrid）；READER_* 与 hook 属 markup 通道，由 `Validator` 内部再派生，Stage-0 不重复生成（避免双计）。
- `extraction_method` ∈ {rule, llm, hybrid, markup}；cross-validate 命中同段一致 → "hybrid"。
- Writer 输出的整章 Draft 必须携带恰好一条 `<!-- hook: <type> strength=<0..1000> -->`（末尾 3 段内）与每条 reader_signal 的 `<!-- reader_*: fact_id -->`（07 §4.4）。
- Level-3：仅 L1/L2 全通过（无 HARD）后运行；只产 SOFT/OBSERVATION，**永不产 HARD**（05 §9 I1）；`level3_fn=None` 时完全跳过。
- Chinese docstrings 引协议节；`from __future__ import annotations`；tests 在 `plot_engine/tests/`，`.venv` 下 `python -m pytest`。
- 偏离记录：真实 LLM 抽取/写手内容不在 Phase 0（属实验期注入）；本计划交付**四通道机制 + 置信度联动 + Writer 组装/重写缝 + L3 缝**，用注入的确定性 channel 充当非确定模型，验证接线正确。

## Review Focus

1. **Stage-0 与 Validator 不重复生成 markup 事件** —— 若 Stage-0 也产 READER_*，`_merge_markup` 会与内部 markup 通道撞 (type,fact) 触发 MARKUP_DEDUPE 噪声或双计。→ Task 1（测试：stage0 结果不含 READER_*）。
2. **冲突置信度 500 必须被 H8.2 隔离、而非静默提交** —— cross-validate 产 500 → Validator 隔离该条 → applied 不含、quarantined++。→ Task 1 + Task 4。
3. **一致→hybrid/1000、单通道→700 的三态可区分** —— 同一 source_ref 规则=LLM → 1000 hybrid；仅一侧 → 700 原 method。→ Task 1。
4. **Writer Draft 可被现有 markup 解析器回读** —— compose 出的 hook 落在末尾 3 段、reader 标注逐条可解析；否则下游 H5.5/M2 必炸。→ Task 2。
5. **L3 不得引入 HARD、不得改 State** —— 注入的 `level3_fn` 返回带 hard 的 finding 被丢弃/降级为 observation；State 前后逐字节不变。→ Task 3。

---

## File Structure

```
plot_engine/
├── extract.py    # cross_validate + stage0_extract（四通道合成 + 置信度联动设值）   [Task 1]
├── writer.py     # compose_chapter_draft + Scene 级重写缝（04 §8.4, 07 §4.4）        [Task 2]
├── validator.py  # Validator.validate 增加可选 level3_fn（05 §7 L3, §9 I1）           [Task 3]
└── tests/
    ├── test_extract_channels.py
    ├── test_writer_draft.py
    ├── test_validator_l3.py
    └── test_stage0_e2e.py        # Writer→draft→stage0→validate→commit 金标贯通
```

## Task 1: 四通道合成 + 置信度联动设值

**Files:** Create `plot_engine/extract.py`; Test `test_extract_channels.py`

**Interfaces:** Consumes `EventProposal`、`parse_markup`、`markup_to_proposals`（仅作说明，Stage-0 不调）。Produces:
```python
LLMChannel  = Callable[[str, "ScenePlan", "ChapterContract", StoryState], List[EventProposal]]
RuleChannel = Callable[["ScenePlan", "ChapterContract", StoryState], List[EventProposal]]

def _key(p: EventProposal) -> tuple            # (type, actor, target, canonical(payload))
def _span(p: EventProposal) -> str             # source_ref 的段落定位（如 para:6）
def cross_validate(rule: List[EventProposal], llm: List[EventProposal]
                   ) -> Tuple[List[EventProposal], List[dict]]
    # 按 (span, 事件集) 对齐：两侧一致→hybrid/1000；单侧→原method/700；同 span 冲突→双 500
def stage0_extract(draft, scene_plan, contract, state, *, chapter,
                   rule_channel=None, llm_channel=None) -> List[EventProposal]
    # rule()+llm()→cross_validate→重排 seq（按 span、再 method）；返回叙事 Proposal
```
- [ ] Tests: 同段一致→1 条 hybrid/1000；仅规则→rule/700；仅 LLM→llm/700；同 span 不同结果→2 条各 500；输出不含 READER_*（Stage-0 只管叙事）；seq 唯一且从 0 连续；默认通道 None→返回 []。
- [ ] Commit `feat(plot-engine): four-channel extraction + confidence linkage (07 §4.3)`

## Task 2: Writer 整章 Draft 组装 + Scene 重写缝

**Files:** Create `plot_engine/writer.py`; Test `test_writer_draft.py`

**Interfaces:** Consumes `ScenePlan`、`ChapterContract`。Produces:
```python
SceneWriter = Callable[["Scene", "ChapterContract", StoryState], str]   # 注入；Phase 0 可传占位
@dataclass
class DraftAssembly:
    draft: str
    scene_ok: List[str]        # 成功 scene_id
    scene_failed: List[str]    # 抛错的 scene_id（仅这些重写，04 §8.4）
def compose_chapter_draft(scene_plan, contract, state, scene_writer
                          ) -> DraftAssembly
    # 逐 scene 调 scene_writer；异常→记 failed、该 scene 跳过（不整章重写）
    # 末尾追加恰好一条 hook（type/strength 取 contract.ending）与每条 reader_signal 的 reader 标注
```
- [ ] Tests: 两 scene 成功→draft 含两段+hook+reader；某 scene 抛错→仅该 scene 进 scene_failed、其余照常、整章仍含合规 markup；产出能被 `parse_markup` 回读（hook 唯一、reader 命中）；hook 落末 3 段内。
- [ ] Commit `feat(plot-engine): writer chapter assembly + scene rewrite seam (04 §8.4, 07 §4.4)`

## Task 3: Level-3 注入缝（只产 SOFT/OBSERVATION）

**Files:** Modify `plot_engine/validator.py`（`Validator.validate`/`_review` 增可选 `level3_fn`）; Test `test_validator_l3.py`

**Interfaces:** Produces：`Validator.validate(..., *, committed_event_ids=..., level3_fn=None)`；`level3_fn: Callable[[draft, sim_cur_state, contract], List[Finding]]`，仅当 L1/L2 无 HARD 时调用；返回的 finding 中 `severity=="hard"` 一律降级为 `observation` 并记 message 前缀 `L3_DOWNGRADED`（05 §9 I1）。`_review` 透传，`reduce_commit` 不受影响（默认 None）。
- [ ] Tests: `level3_fn=None` 行为与旧一致（金标仍绿）；注入产 SOFT→落入 soft_warnings 且 can_commit True；注入产 HARD→被降为 observation，hard_violations 仍为空；有 L1/L2 HARD 时 `level3_fn` 不被调用（用计数断言）；State 逐字节不变（I3）。
- [ ] Commit `feat(plot-engine): optional Level-3 validator seam, never produces HARD (05 §7/§9 I1)`

## Task 4: Stage-0 贯通 e2e + 回归

**Files:** Test `test_stage0_e2e.py`
- [ ] Tests: `compose_chapter_draft`（占位 writer 产带 reader/hook 的段）→ `stage0_extract`（注入 rule/llm 产 OBSERVES+INFERS，一致 hybrid）→ `Validator.validate`（金标契约）→ `CommitOrchestrator.commit` → OK + parity。再跑一条 rule≠llm 冲突：cross 产 500 → H8.2 隔离 → 批 FAIL（required 未满足）或 applied 不含冲突者。
- [ ] `python -m pytest plot_engine/tests -q` 全绿。
- [ ] Commit `test(plot-engine): stage-0 extraction e2e + writer/validator regression`

## Out of scope (subsequent plans)

- 真实 LLM 抽取/写手模型接入与非确定性置信度（实验期注入，08 Day 20–22）。
- Revision/重抽取循环与 RootCause 分类落地（06）。
- 规则通道具体模板文法（CHANGES/ITEM_*/RELATIONSHIP 字段抽取）——Phase 1。
