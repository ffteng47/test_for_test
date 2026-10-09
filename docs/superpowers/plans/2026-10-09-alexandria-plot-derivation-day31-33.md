# Arc → Contract → ScenePlan 生成器 (Day 31–33) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让实验的每一章拿到**从 Arc 派生出来的、彼此不同**的 Chapter Contract 与 ScenePlan，并把 06 §4.2 的 `renegotiate_contract` 接到真实修订循环上。

**Architecture:** 新模块 `plot_engine/derive.py` 只做**确定性派生**：04 §4.3 D1–D9 能算的全算（张力取曲线、turning_point→required_events、gate 到期→allowed/forbidden、逾期 gate→REVEALS、reader_signals 只指向已到期事实），算不出来的作者意图（story_goal / must_change / ending）显式读 Arc 的 `reader_beats` 槽位（04 §3.1，SOFT 元数据）——放在 Arc 里才不违反 C2「不得自我生成」，生成器绝不编造剧情。Arc 自相矛盾一律抛 `ArcConflict`（06 §4.3 → 回 Arc 层），不在生成器里悄悄放宽。实验夹具改为提供一份**有内容的 Arc**（多 gate、多 turning point、逐章意图），`review.py` 的 live/offline 两条路都用派生物取代十份相同的 `contract_for/plan_for`。

**Tech Stack:** Python 3.12、pydantic v2、pytest；复用 `plot_engine` 既有 `Validator.validate_contract`（H7）与 `sceneplan.validate_scene_plan`（SP1–SP7），零新依赖、零网络。

**Spec:** `alexandria-spec-v0.2/04_contract_protocol.md` §3.1/§4.3/§4.4/§5.1/附录 B；`06_revision_protocol.md` §4.2/§4.3/§5；`08_experiment_protocol.md` §5 Day 14–16、§8。上游结论：`docs/phase0-live-run-10ch.md` §7 backlog #1/#2/#6。

## Global Constraints

- 生成器只读、无时钟（`created_at` 由调用方给定）、无网络；同输入必同产物（Auto-Mode #6，离线 CI 不碰 GPU）。
- 派生规则逐字对齐 04 §4.3：**不新增 HARD 判据**（08 I2），产物必须过既有 H7 / SP 校验且不产生 SOFT。
- 数值一律定点整数 ×1000，无 float（05 §5.5）。
- 冲突（gate 互斥、required∩forbidden、逾期揭示的事实又被禁）一律 `ArcConflict` 抛出；**禁止**用「删掉约束让实验通过」的方式兜底。
- `plot_engine/tests/` 下测试；`.venv` 内 `python -m pytest plot_engine -q`（仓库根 `pytest` 会误收 `upstream/`、`deploy/`）。

## Review Focus

1. **生成器不得替作者编故事** —— 缺 `reader_beats` 意图时必须失败，而不是补一个 `story_goal`；否则「契约被满足」退化成模型自证。→ Task 1。
2. **逾期 gate 的 REVEALS 与作者显式 forbidden 相撞** —— 这是 Arc 层矛盾（06 §4.3），必须抛错并留人工，不能悄悄二选一。→ Task 1。
3. **同一 fact 两个 gate 意见相反**（R4 允许）—— allowed 与 forbidden 交集非空时，产物若直接进契约就会撞 H7.4；必须在上游拦下。→ Task 1。
4. **十份契约真的互不相同** —— 派生完成后若各章 `required_events`/`knowledge_*` 全等，说明 Arc 仍然只有一个 turning point，实验依旧没测跨章推进。→ Task 3。
5. **重议契约不是降标准** —— `renegotiate_contract` 只能放宽**作者自订**的要求，绝不许丢掉 Arc 强制（D3/D6）派生的事件；违反即 `escalate_to_arc`。→ Task 3。

---

## File Structure

```
plot_engine/
├── derive.py                          # ChapterIntent + derive_chapter_contract + derive_scene_plan   [Task 1, 2]
├── revision_actions.py                # renegotiate_contract：按 06 §4.2 重派生 version+1            [Task 3]
├── tests/fixtures/traitor_arc_full.py # 有内容的 Arc：3 turning points、3 gates、10 章逐章意图        [Task 3]
└── tests/
    ├── test_derive_contract.py        # D1–D9 + ArcConflict + H7 零 HARD                             [Task 1]
    ├── test_derive_sceneplan.py       # SP1–SP7 零 finding + 结构上下界                               [Task 2]
    └── test_revision_renegotiate.py   # version+1、Arc 强制项不可丢、报告可见性                       [Task 3]
```

## Task 1: Arc → Chapter Contract 派生（04 §4.3 D1–D9）

- [x] Step 1：写失败测试 `test_derive_contract.py`（D1 越界、缺意图响亮失败、D3 turning_point、D4/D5 gate 到期翻转、D4 非本章角色 gate 两边都不进、D6 逾期补 REVEALS、D6 与 forbidden 相撞 → `ArcConflict`、同 fact 两 gate 互斥 → `ArcConflict`、D9 信号只指向已到期、D2' 张力取曲线、十章逐章 H7 零 HARD 零 SOFT、元数据与 `derived_from` 落款、非法意图报错、同输入同产物）。
- [x] Step 2：确认失败 = `ModuleNotFoundError: plot_engine.derive`。
- [x] Step 3：实现 `derive.py`：`ChapterIntent`（只含 D 推不出的字段）、`NoChapterIntent`、`ArcConflict(ValueError)`、`derive_chapter_contract(arc, chapter_no, state, *, created_at, version=1)`。
- [x] Step 4：`pytest plot_engine/tests/test_derive_contract.py -q` 全绿。
- [x] Step 5：Commit `feat(plot-engine): Arc→Chapter Contract 派生（04 §4.3 D1–D9）` → `250b10e`。

**Produces:** `derive_chapter_contract(arc, chapter_no, state, *, created_at, version=1) -> ChapterContract`；`ChapterIntent`（`arc.reader_beats` 条目 schema）；`ArcConflict` / `NoChapterIntent`（均 `ValueError` 子类）。

## Task 2: Contract → ScenePlan 派生（04 附录 B）

**Interfaces:** Consumes Task 1 的 `ChapterContract` 与 `sceneplan._SIGNAL_TO_READER`（单一映射源，避免 SP4 两套语义）。

- [x] Step 1：写失败测试 `test_derive_sceneplan.py`（SP1–SP7 零 finding；负载 0/1/5/12 个额外 required_events 时场景数 3–7、每场景拍数 3–7 且仍零 HARD；SP2 逐类型覆盖；SP4 每条已建立信号有对应拍且不多不少；SP3 从不声明禁用类型；`bt_*` 唯一 + `scn_{章}_*` 前缀；`plan_id/contract_version/epoch` 落款；场景地点仅在 State 位置唯一时继承、否则 None；场景角色覆盖其拍的角色且存在于 State；同输入同产物）。
- [x] Step 2：确认失败 = `ImportError`（`derive_scene_plan` 不存在）。
- [x] Step 3：实现 `derive_scene_plan(contract, state, *, created_at) -> ScenePlan`：信号拍**先**占槽（`_pack` 轮转分桶，保证不被合并吃掉），事件拍随后；`beat.location` 一律 None → SP5 无声明即不违反；`scene.tension = contract.tension_target` → SP7 零 finding；不足 3×3 补纯结构「过渡」拍（无事件、无事实）。
- [x] Step 4：全绿；全量 373 passed。
- [x] Step 5：Commit `feat(plot-engine): Contract→ScenePlan 派生（04 附录 B，SP2/SP3/SP4 由构造保证）` → `4ed6838`。

## Task 3：有内容的 Arc 夹具 + 接入两条实验路径 + `renegotiate_contract`

**Interfaces:** Consumes `derive_*`、`RevisionLoop(actions=...)`、`run_experiment(..., chapter_source=...)`；Produces `traitor_arc_full.arc()` / `.intent_for(ch)` 与 `renegotiate(ctx) -> ChapterContext`。

- [ ] Step 1：写失败测试 `test_revision_renegotiate.py`：
  - 契约层 RootCause 触发重议 → `ctx.contract.version == 原版本 + 1`，`draft` 未被重写（06 §4.2「不重写 Draft」）；
  - **重议不得丢掉 Arc 强制项**：由 D3 turning_point 或 D6 逾期 gate 派生的 event_type，重议后仍在 `required_events` 里；
  - 只剩作者自订要求可放宽时，重议把该要求去掉并记 `reason`；
  - Arc 强制项就是失败原因且无法放宽 → 走 `escalate_to_arc`（`_LEVEL_TO_ACTION["arc"]`），落 `needs_human`，不静默通过。
- [ ] Step 2：确认失败 = `ModuleNotFoundError: plot_engine.revision_actions`。
- [ ] Step 3：实现 `revision_actions.py`：`renegotiate_contract(arc, chapter_no, state, *, created_at)` → 用 `derive_chapter_contract(..., version=cur+1)` 重派生，剔除**仅作者自订**且被 HARD 判 impossible 的 required/forbidden 项；Arc 派生项保留；`ArcConflict` 继续上抛。
- [ ] Step 4：夹具 `tests/fixtures/traitor_arc_full.py`：`chapter_range=(1,10)`、`tension_curve` 10 值、3 个 turning_points（第 3/6/9 章）、3 个 knowledge_gates（含一个 `must_reveal_by_chapter` 逾期）、10 条逐章 `reader_beats` 意图。
- [ ] Step 5：改 `review.py` 的 `_offline_dry_run` 与 `_live_run`：`contracts=lambda ch: derive_chapter_contract(arc, ch, state, ...)`、`plans=lambda ...: derive_scene_plan(...)`，并把 `renegotiate_contract` 注册进 `RevisionLoop.actions`。`chapter_source` 需要「当前 State」，而派生发生在 `source(ch, cur)` 里 → 用 `cur` 派生，不用 genesis。
- [ ] Step 6：加回归：同一 fixture 跑 10 章，断言各章 `required_events` 类型集合**不全相同**（Review Focus #4）；`contract.version` 在报告里可见。
- [ ] Step 7：全绿 + Commit `feat(plot-engine): 派生契约接入实验 + renegotiate_contract（06 §4.2）`。

## Task 4：带逐章契约的重跑 + 重复采样判定 E2/E4

- [ ] Step 1：`ssh -f -N -L 11500:localhost:11434 tff@192.168.31.213`（隧道，不改服务器配置）。
- [ ] Step 2：`python -m plot_engine.review --live --chapters 10 --model-config @router_qwen3.json --dump-dir <新目录>`，记录 `生成/提交/未决`、`tokens`、§6 分类、§7 闸、§8 E1–E6。
- [ ] Step 3：**同一配置再跑 2 次**（backlog #6：单次运行含不可量化方差），把三次的 E2/E4 结果并列写进 `docs/phase0-live-run-10ch.md` 新节；结论只按「三次是否一致」下，不取单次作数。
- [ ] Step 4：把派生契约带来的变化写进报告 §7 backlog（#1 关闭、#2 关闭，以及新暴露的项）。Commit `test(plot-engine): 逐章派生契约下的 10 章重跑（三次采样）`。
