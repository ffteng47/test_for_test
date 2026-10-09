# Alexandria Architecture Review Decision Sheet (Day 23–25) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `ExperimentReport` produced by the Day 20–22 harness into the read-only decision sheet the human reviewer needs for 08 §6 (Failure Classification) / §7 (Architecture Freeze Gate G1–G4) / §8 (Exit Conditions E1'–E6'), so "是否进 Phase 1" 是一次人工判定而非一次自动发布。

**Architecture:** `plot_engine/review.py` 只做**映射与呈现**：把每条 rule_id 归到 §6 的六个失败类，把报告字段归到 §7 的四道冻结闸与 §8 的六条退出条件，再渲染成中文文本文档。绝不新增判据、绝不改判 HARD/SOFT、绝不写 store/log（08 I1/I2）。真实 LLM Writer 与 `Arc→Contract→ScenePlan` 生成器仍为注入 seam（Auto-Mode #6：无网络、无密钥），因此本工作表是对**机制实验**结果的分类，而非对剧情质量的评分。

**Tech Stack:** Python 3.12+, pydantic v2, pytest；复用 `plot_engine.models.experiment.ExperimentReport`、`plot_engine.classify.HardMetric/RULE_TO_METRIC`、`plot_engine.experiment.evaluate_exit_conditions`。

**Spec:** `08_experiment_protocol.md` §6（失败分类表）、§7（Architecture Freeze Gate G1–G4）、§8（退出条件 E1'–E6'）；`06_revision_protocol.md` §4.0（Extraction 归因）。

## Global Constraints

- 只读：review 层不写 store/eventlog，不调 commit，不触发任何副作用。
- 不得新增或修改 HARD 规则判据（08 I1）；本层只做 rule_id → 失败类的静态映射与计数。
- 网络无关、无密钥（Auto-Mode #6）；不落地任何前端/后端集成，除非用户另行批准。
- 中文文档串引协议节；`from __future__ import annotations`；测试置于 `plot_engine/tests/`，`.venv` 下 `python -m pytest`。
- 偏离记录：06 Revision 循环未落地 → E3' 恒为 `None`（N/A），工作表须显式标注而非默默通过。

## Review Focus

1. **未知 rule_id 不得静默消失** —— 任何未映射的 HARD 规则必须落到一个可见的兜底类，否则"0 硬违规"可能是漏计。→ T1。
2. **replay 不一致必须单独归"架构阻断"** —— `REPLAY_INCONSISTENT` / `replay_consistency=False` → G2，且不得与普通 Writer 问题混桶（08 §6 表末行、§7）。→ T2。
3. **未 commit 章不得算作通过** —— `unresolved_chapters` 参与 G3 判定，缺章即锁闸。→ T2。
4. **退出条件不得被工作表重新定义** —— E1/E2/E4/E5/E6 必须逐字来自 `evaluate_exit_conditions`，review 层只呈现。→ T3。
5. **工作表可序列化、可人工阅读** —— dict 结果需 JSON-safe，渲染文本需含 §6/§7/§8 三节标题。→ T4。
6. **对外承诺的命令必须真能跑出结果** —— 计划/说明里写过的 `python -m plot_engine.review` 若无 `__main__` 入口即静默退出（0 输出），等于交付不可复现；Windows GBK 控制台还需强制 stdout UTF-8 以免中文乱码。→ T5。

---

### Task 1: rule_id → 失败类映射（08 §6）

**Files:**
- Create: `plot_engine/review.py`
- Test: `plot_engine/tests/test_review.py`

**Interfaces:**
- Consumes: `ExperimentReport.hard_violations: Dict[str,int]`、`HardMetric`、`evaluate_exit_conditions`
- Produces: `FAILURE_EXTRACTION/FAILURE_WRITER_VALIDATOR/FAILURE_FACT_ONTOLOGY/FAILURE_CONTRACT_ARC/FAILURE_NOT_PHASE0/FAILURE_ARCH_BLOCKER: str`；`_class_for_rule(rule_id) -> str`

- [x] **Step 1:** 写失败测试：H8.1/H8.2/H6.x → Extraction；H5.x/H7.x → Contract/Arc；I1/R7 → Fact Ontology；REPLAY_INCONSISTENT → 架构阻断；未映射 id → Writer/Validator。
- [x] **Step 2:** 运行确认失败。
- [x] **Step 3:** 实现映射表 + 兜底分支。
- [x] **Step 4:** 运行确认通过。
- [x] **Step 5:** 提交。

### Task 2: `architecture_review(report)` —— §6 统计 + §7 四道冻结闸

**Files:**
- Modify: `plot_engine/review.py`
- Test: `plot_engine/tests/test_review.py`

**Interfaces:**
- Consumes: `ExperimentReport`（`replay_mismatch_chapters`、`unresolved_chapters`、`replay_consistency`、canon/knowledge/timeline 计数）
- Produces: `architecture_review(report) -> dict`，键 `experiment_id / summary / failure_classes / freeze_gate / exit_conditions / may_change_architecture`

- [x] **Step 1:** 写失败测试：健康跑 → 四闸全 False、`may_change_architecture=False`；`replay_consistency=False` → G2 True。
- [x] **Step 2:** 运行确认失败。
- [x] **Step 3:** 实现：G1 任一失败类计数 ≥3；G2 架构阻断类非空或 replay 不一致；G3 未决章 ≥2；G4 canon+knowledge+timeline > 0。
- [x] **Step 4:** 运行确认通过。
- [x] **Step 5:** 提交。

### Task 3: §8 退出条件直通

**Files:**
- Modify: `plot_engine/review.py`
- Test: `plot_engine/tests/test_review.py`

- [x] **Step 1:** 写失败测试：`sheet["exit_conditions"] == evaluate_exit_conditions(report)`（含 `E3 is None`）。
- [x] **Step 2 → Step 5:** 同上节奏；实现只复用既有函数，不重算阈值。

### Task 4: `render_review_text(sheet)` 人工可读呈现

**Files:**
- Modify: `plot_engine/review.py`
- Test: `plot_engine/tests/test_review.py`

- [x] **Step 1:** 写失败测试：sheet 经 `json.dumps` 可序列化；渲染文本含 `§6 失败分类` / `§7 架构冻结闸` / `§8 退出条件`。
- [x] **Step 2 → Step 5:** 同上节奏；渲染为 Markdown 三段，E3 显示 `N/A（06 Revision 未落地）`。

### Task 5: `python -m plot_engine.review` 离线演练入口（Review Focus #6）

**Files:**
- Modify: `plot_engine/review.py`（`_offline_dry_run` / `main` / `__main__`）
- Test: `plot_engine/tests/test_review.py`

**Interfaces:**
- Consumes: `tests/fixtures/experiment_10ch`（`make_config` / `build_source` / `dummy_writer`）、`StateStore`、`EventLog`、`run_experiment`
- Produces: `main(argv=None) -> int`；`--chapters N`（默认 10）、`--defect CH:KIND`（KIND ∈ leak|dead，可重复）

- [x] **Step 1:** 写失败测试：`review_main([])` 返回 0 且 stdout 含 `生成 10 / 提交 10`；`--defect 2:leak` → `未决 [2]`；`--defect 2:typo` → `SystemExit` 且 stderr 提示 `leak|dead`。
- [x] **Step 2:** 运行确认失败（原实现无入口，命令静默无输出）。
- [x] **Step 3:** 实现：临时目录建 store/eventlog → `init_genesis` → `run_experiment` → 渲染决策单；`sys.stdout.reconfigure(encoding="utf-8")` 保 Windows 控制台不乱码。夹具路径在 `_offline_dry_run` 内延迟导入，开发命令专用，不污染包导入图。
- [x] **Step 4:** 运行确认通过 → 246 passed。
- [x] **Step 5:** 提交。

---

## Self-Review

- 覆盖：08 §6 六类、§7 G1–G4、§8 E1'–E6' 全部有对应产出；无 TBD。
- 边界：本层无写操作、无网络；真实模型接入与 `frontend/`/`backend/` 页面**不在本计划内**，需用户单独批准。
- 全量测试：`python -m pytest plot_engine/tests -q` → 246 passed。
