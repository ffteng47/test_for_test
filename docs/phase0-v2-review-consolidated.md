# Phase 0 审查汇总：H5.3 契约问题 → 冻结面 v2 三次采样

> 生成时间：2026-10-10
> 适用冻结面：v1 `66f87e2`（旧尺）→ v2 `f99cc00`（新尺）
> 性质：审查意见汇总，可直接作为 `docs/phase0-live-run-10ch.md` v2 新节的底稿

---

## 目录

1. [问题起源：H5.3 契约不可满足](#1-问题起源h5-契约不可满足)
2. [协议裁定（QA 六问）](#2-协议裁定qa-六问)
3. [冻结面 v2 修复清单](#3-冻结面-v2-修复清单)
4. [批次 6：三次采样原始读数](#4-批次-6三次采样原始读数)
5. [三次并列对比与结论](#5-三次并列对比与结论)
6. [审查发现：finding-1 / 2 / 3](#6-审查发现finding-1--2--3)
7. [Phase 1 backlog 增补](#7-phase-1-backlog-增补)
8. [附录：关键证据链](#8-附录关键证据链)

---

## 1. 问题起源：H5.3 契约不可满足

真实模型 10 章实验（旧尺 `66f87e2`）中，ch06/ch07 被拒，两章失败信息完全相同：

```
HARD H5.3: must_change char_000001.knowledge 无实现事件（W1）
```

### 根因（三层）

1. **夹具错误**：`experiment_10ch.py:51-55` 把 04 附录 A 的**单章示例契约**（第 47 章）字节级抄成了 10 章的逐章意图——每章都要求重新建立同一对 fact（fact_000003 known / fact_000001 suspected）。
2. **Δ 语义是协议规定**：04 §4.2 / 04 §5.2 W1 / 10 §4.3 三处协议文本一致——`must_change` 的实现条件是"**本批事件里存在一条实现该变更的 Event**"，不是"章末状态满足谓词"。⇒ 同一 target 写进 10 章 ⇒ 每章都必须重新发生一次该跃迁。这是协议的**正确后果**，不是误读。
3. **修订循环修不了它**：06 对 must_change 类失败**没有定义归属**；`renegotiate_contract` 只放宽 `required_events` 轴，`must_change` 逐字拷贝回来 ⇒ 重议成功概率恒为 0。

### 旧尺的修正

- 问题记录：`docs/phase0-h53-contract-infeasibility.md`（诊断）
- 裁定记录：`docs/phase0-h53-spec-qa.md`（QA 六问）
- 采样状态：`docs/phase0-sample-status-and-revision-trace.md`
- 模型配置：`docs/phase0-batch6-model-plan.md`

**结论：A（修夹具）是正解；C（往 04 §4.3 补 D10）撤回。**

---

## 2. 协议裁定（QA 六问）

| 问 | 裁定 | 关键依据 |
|---|---|---|
| Q1 must_change 语义 | **Δ（跃迁）**，确定无疑 | 04 §4.2:181、04 §5.2 W1:240、10 §4.3:106-121 三处一致；`validator.py:496-501` 查 `sim.applied` 存在性，与协议一致 |
| Q2 I2 边界 | 判据 = 协议文本的 rule 语义 + severity + 映射表；**代码向文本靠拢 ≠ 改判据** | D（分表）使判定变严，但旧读数本来就不是协议的数 |
| Q3 尺的偏差 | **两个方向都偏**：偏严（夹具重复 Δ）+ 偏松（`_KNOWLEDGE_ESTABLISH` 合并了 knowledge/belief 两个 field，且漏 `DOUBTS`） | 10 §4.3 分表：knowledge→OBSERVES/READS/IS_TOLD/INFERS；belief→BELIEVES/SUSPECTS/DOUBTS。严格按协议，fix-1 的 8/10 应读作 **5/10**（ch02/08/10 靠 BELIEVES 满足 knowledge 要求，按协议不该算） |
| Q4 采样状态 | fix-1 = 第 1 次（完整）；fix-2 中断在第 4 章、无报告 | 三次一致性当时无数据 |
| Q5 escalate_to_arc | **不注册 = 刻意**（Auto-Mode #6 明文）；真正漏的是**入路**：`RULE_TO_LEVEL` 无 rule 归 arc 层 + `renegotiate_contract` 静默减掉 Arc 强制项 | 后者是"伪装成通过"的洞，已在批次 4 修复（fail-fast 上抛） |
| Q6 operation | H5.3 **完全不看 operation/expected_value**；`add` 改 `update` 无效果 | `validator.py:496-509` 只匹配 field + 事件类型集合 + target + actor |

---

## 3. 冻结面 v2 修复清单

| 批次 | 内容 | 状态 |
|---|---|---|
| 0 | 核实 `RULE_TO_METRIC` I9 条目进版历史 | 完成（I9→KNOWLEDGE、H5.3→REQUIRED_EVENT_MISSING 已在映射表内） |
| 1 | **D**：H5.3 按 field 分表（knowledge / belief 各自实现者集合，补 DOUBTS）；**H5.7 的 `_KNOWLEDGE_ESTABLISH` 保持原样**（两个消费者不能共用一处改动） | 完成 |
| 2 | **A**：夹具逐章意图重写（每章 must_change 只指向本章尚未建立的跃迁；rank 推进是合法新 Δ；每条 must_change 配实现类型的 required_event；expected_value ≤ 事件类型的 reducer 上限；允许部分章 must_change 为空） | 完成 |
| 3 | **B**：`derive.py` 守卫——must_change 无可实现 required_event 类型 ⇒ `raise ArcConflict`（只 raise，不自动补事件） | 完成 |
| 4 | `RULE_TO_LEVEL["H5.3"]="contract"`；`renegotiate_contract` 遇 Arc 强制项落空 ⇒ **fail-fast raise**（实验当场停，不静默继续）；`consistency_counts` 未映射 code ⇒ CANON 兜底对齐 | 完成 |
| 5 | 取证三项：逐章渲染 `revision_rounds`；dump 落 `trace.steps`（`## Revision` 段）；dump 改打最终 ctx + 第 0 轮另起一段 | 完成 |
| 6 | 三次采样（同模型、串行、detached、run.log 留痕） | 完成，读数见 §4 |

**执行顺序**：批次 4 → 批次 5 → 全量绿 → freeze `f99cc00` → 可达性核实 → s1/s2/s3 串行 → 报告新节。

---

## 4. 批次 6：三次采样原始读数

冻结提交 `f99cc00`。模型：`qwen2.5:14b` @ `http://127.0.0.1:11434/v1`（`router_local.json` sha12 `a820beb0d944`）。
请求体无 seed/top_p（`llm.py:111-115`），writer 温度 0.8 ⇒ 三次是同一分布的三次独立抽样，不是可复现回放。
口径：主口径 = E1–E6 六布尔值三次完全一致；辅口径 = 逐章 commit/fail 模式一致；主口径不一致时三次完整并列，禁止取多数/合并/挑最好看的一次。

### s1（813s，tokens=39552）

生成 10 / 提交 6 / 未决 `[2,5,7,10]` / replay 一致 True
§6：Writer/Validator 2（H2.2）｜Contract/Arc 6（ARC_CONFLICT, H5.1, H5.3, H5.6）
§7：G1 T / G2 F / G3 T / G4 F / 可讨论改架构 T
§8：E1 T / E2 F / E3 N/A / E4 T / E5 T / E6 T

| 章 | status | v | rounds | HARD |
|---|---|---|---|---|
| 01 | OK | 1 | 0 | |
| 02 | FAIL | 2 | 1 | H2.2、H5.3、H5.6 |
| 03 | OK | 2 | 1 | |
| 04 | OK | 1 | 0 | |
| 05 | ARC_CONFLICT | 1 | 0 | arc_003 第 5 章落空的事件类型是 Arc 强制项：['INFERS'] |
| 06 | OK | 2 | 1 | |
| 07 | FAIL | 4 | 3 | H5.1、H5.3 |
| 08 | OK | 1 | 0 | |
| 09 | OK | 1 | 0 | |
| 10 | FAIL | 3 | 2 | H2.2、H5.6 |

### s2（1026s，tokens=46725）

生成 10 / 提交 4 / 未决 `[1,2,5,7,9,10]` / replay 一致 True
§6：Writer/Validator 3（H2.2）｜Contract/Arc 8（ARC_CONFLICT, H5.3, H5.6）
§7：G1 T / G2 F / G3 T / G4 F / 可讨论改架构 T
§8：E1 T / E2 F / E3 N/A / E4 T / E5 T / E6 T

| 章 | status | v | rounds | 判定 |
|---|---|---|---|---|
| 01 | ARC_CONFLICT | 1 | 0 | ['INFERS'] 落空且为 Arc 强制项 |
| 02 | FAIL | 2 | 1 | H2.2（fact_000001 期望 known）等 3 条 |
| 03 | OK | 1 | 0 | |
| 04 | OK | 1 | 0 | |
| 05 | FAIL | 2 | 1 | H2.2（fact_000004 期望 suspected）等 3 条 |
| 06 | OK | 2 | 1 | |
| 07 | FAIL | 4 | 3 | H5.3：must_change char_000001.belief 无实现事件 |
| 08 | OK | 1 | 0 | |
| 09 | ARC_CONFLICT | 2 | 1 | ['BELIEVES'] 落空且为 Arc 强制项 |
| 10 | FAIL | 1 | 3 | H2.2（fact_000002 期望 known）等 2 条 |

### s3（1124s，tokens=50050）

生成 10 / 提交 3 / 未决 `[1,2,3,6,7,9,10]` / replay 一致 True
§6：Writer/Validator 3（H2.2）｜Contract/Arc 9（ARC_CONFLICT, H5.3, H5.6）
§7：G1 T / G2 F / G3 T / G4 F / 可讨论改架构 T
§8：E1 T / E2 F / E3 N/A / E4 T / E5 T / E6 T

| 章 | status | v | rounds | 判定 |
|---|---|---|---|---|
| 01 | ARC_CONFLICT | 1 | 0 | ['INFERS'] 落空且为 Arc 强制项 |
| 02 | FAIL | 2 | 1 | H2.2（fact_000001 期望 known）、H5.3、H5.6 |
| 03 | FAIL | 3 | 2 | H5.3：must_change char_000001.belief 无实现事件 |
| 04 | OK | 1 | 0 | |
| 05 | OK | 1 | 0 | |
| 06 | FAIL | 2 | 1 | H2.2（fact_000004 期望 known）、H5.3、H5.6 |
| 07 | FAIL | 4 | 3 | H5.3：must_change char_000001.belief 无实现事件 |
| 08 | OK | 1 | 0 | |
| 09 | ARC_CONFLICT | 2 | 1 | ['BELIEVES', 'INFERS'] 落空且为 Arc 强制项 |
| 10 | FAIL | 1 | 3 | H2.2（fact_000002 期望 known）、H5.6 |

---

## 5. 三次并列对比与结论

### 主口径：E1–E6 六布尔值 —— **三次完全一致**

| | s1 | s2 | s3 |
|---|---|---|---|
| 生成 / 提交 / 未决 | 10 / 6 / 4 | 10 / 4 / 6 | 10 / 3 / 7 |
| replay 一致 | True | True | True |
| §7 G1/G2/G3/G4/可讨论改架构 | T/F/T/F/T | T/F/T/F/T | T/F/T/F/T |
| §8 E1/E2/E3/E4/E5/E6 | T/F/N/A/T/T/T | T/F/N/A/T/T/T | T/F/N/A/T/T/T |

### 辅口径：逐章 commit/fail —— **三次不一致**

| 章 | s1 | s2 | s3 | 一致性 |
|---|---|---|---|---|
| 01 | OK | ARC_CONFLICT | ARC_CONFLICT | 抖动 |
| 02 | FAIL | FAIL | FAIL | **稳定失败** |
| 03 | OK | OK | FAIL | 抖动 |
| 04 | OK | OK | OK | 稳定通过 |
| 05 | ARC_CONFLICT | FAIL | OK | 三种结局 |
| 06 | OK | OK | FAIL | 抖动 |
| 07 | FAIL | FAIL | FAIL | **稳定失败** |
| 08 | OK | OK | OK | 稳定通过 |
| 09 | OK | ARC_CONFLICT | ARC_CONFLICT | 抖动 |
| 10 | FAIL | FAIL | FAIL | **稳定失败** |

### 结论

1. **闸门判定层稳定**：replay、§7 四闸、§8 六值三次零分歧，无崩溃、无 IO_ERROR，pipeline 完整。
   注意收窄表述：**逐章结果存在显著采样方差**（提交率 60/40/30 差 2 倍），"度量输出稳定"
   仅指闸门判定层，不指逐章输出。E2 距阈值（90%）差距足够大（≤60%），判定结论对采样方差鲁棒。
2. **Phase 0 → Phase 1 未达成**：E2 三次同判 False（30%–60%），E3 因 finding-1 三次不可判。
   按 08 §8，E2 不过即不放行。
3. **稳定失败核先于抖动**：ch02/ch10（H2.2 知识跃迁未达 expected rank）与 ch07（belief H5.3，
   9 次尝试从未产出 belief 事件）在三次抽样中无一侥幸通过；抖动章（1/3/5/6/9）的处置要等
   可控变量（seed / 更低温度）才有意义。
4. **预注册口径执行干净**：未取多数、未合并、未挑代表读数；run.log 与 30 份逐章快照全保留。
5. **旧尺数据不并列**：fix-1（8/10，严格读法 5/10）与 fix-2 残片是 D+A 两次 alignment 之前的
   读数，仅作历史留档。

---

## 6. 审查发现：finding-1 / 2 / 3

### finding-1：中途判死章让 E3 假降级为 N/A（采样期不修）

`review.py:87` `revision_ran = len(report.revision_rounds) == chapters_generated`，
而中途抛 `ArcConflict` 的章只 `generated += 1` 就 `continue`，不写 `rounds_by_chapter`。
⇒ E3 被渲染成 N/A，而修订确实跑过（r≥1 的章：s1 五章、s2/s3 各六章）。
**修复**（解冻后）：quarantine 分支同样落 `rounds_by_chapter[ch]`，或 `revision_ran` 改语义。

### finding-2：`experiment_id` 恒为 `exp-s1-42`（仅标签，不影响数据）

`experiment.py:155` `experiment_id = f"exp-{story}-{config.seed}"`，live 路径 story/seed 恒定。
样本区分只能靠 dump 目录名 + run.log。**修复**（解冻后）：尝试序号并入 story_id 或 experiment_id。

### finding-3：must_change 系失败结构性烧预算（本轮新立）

H5.3 / H2.2 / H5.6 的根都在 `must_change` 轴上，`renegotiate_contract` 按设计只动
`required_events` 轴 ⇒ **这类失败重议成功概率恒为 0，但 ladder 会一遍遍 renegotiate 烧满预算**。

实测证据（v2 三次采样）：

- ch07 三次都 renegotiate 到 `contract_version=4` 后仍败于同一 H5.3；
- ch02/ch10 的 H2.2 系失败同理（s2 ch10 三次 writer 层重写 v 恒为 1；其余各烧 1 轮注定无效的 renegotiate）。

**处置**：记 Phase 1 backlog（must_change 系失败的归因与终止策略）；本次报告中把
"修订烧掉的 token 中注定无效的比例"单独呈现一行——它是 E3 未来是否可救的关键背景。

### 语义细节（防误读）：rounds 计数口径

ARC_CONFLICT 章的模式（ch05 v1/r0、ch09 v2/r1）反推出：**rounds 只计成功完成的步，
致命那一步不计入**（raise 发生在动作执行中，step 未落账）。自洽，但报告必须写明，
否则 ch05 的 r0 会被误读成"修订没跑"——与 finding-1 是外观相似的两个不同坑。

---

## 7. Phase 1 backlog 增补

| # | 项 | 来源 |
|---|---|---|
| 1 | must_change 系失败（H5.3/H2.2/H5.6）的归因与终止策略：06 未定义归属，v2 实测其重议成功概率恒为 0 却烧满预算 | finding-3 |
| 2 | `rewrite_scene` ≡ `rewrite_chapter`（同一个 lambda 注册两个名字），阶梯前两级是名义升级 | v2 前既有 |
| 3 | H8.1/H8.2 落 CANON 桶污染 G4/E6 的归类裁定（需核对 08 §4 原文；倾向：只记 by_rule、不进九桶） | v2 前既有 |
| 4 | `revision_ran` 语义修复（finding-1）；`experiment_id` 尝试序号（finding-2） | 本轮 |
| 5 | writer 提示词是否渲染本章 required_events/turning point 的核查（影响 ARC_CONFLICT 抖动的归因：模型能力 vs 引擎接线） | 本轮待查 |
| 6 | ch07 belief Δ 的定性：刻意测 belief 层 vs 夹具顺手目标（决定报告写"模型弱项"还是"夹具方法论教训"） | 本轮待拍板 |
| 7 | 稳定失败核的三层归因核查（Writer 没写 / 抽取漏了 / 提示词没给）——需读 ch02 Proposals 段 + ch07 Revision 段 dump | 本轮待查 |
| 8 | seed / 低温度对照轮（抖动章处置的前提）；qwen3 / deepseek-r1:32b 对照轮（服务端 Ollama 修复前置） | 批次 6 计划 §4 |

---

## 8. 附录：关键证据链

### A. 旧尺 ch06/07 修订轨迹（代码确定性重建，非测量）

`RULE_TO_LEVEL` 无 H5.3 ⇒ 归 writer ⇒ 逐轮：rewrite_scene →（振荡）rewrite_chapter →
（振荡）renegotiate_contract ⇒ 触顶 `min(max_rounds=3, human_threshold=3)` ⇒ FAIL + needs_human。
且 `review.py:245` 的 `rewrite_scene` 与 `rewrite_chapter` 是**同一个 lambda**——前两级字面同义。

### B. 旧尺取证缺陷（批次 5 已修）

- `experiment.py:87` dump 回调收的是修订**前** ctx ⇒ `contract_version=1` 不能证明 renegotiate 没跑过；
- `recommit` 每轮覆盖 `captured["props"]` ⇒ dump 是混合体（Draft 来自第 0 轮、Proposals 来自最后一轮）。

### C. 样本完整性核验（本轮审查复算）

- 三章未决集合与逐章表逐条对账一致（s3：10 − 3 = 7 ✓）；
- §6 分桶与逐章 HARD 计数吻合（s1：H2.2×2 + H5.3×2 + H5.6×2 + H5.1×1 + ARC_CONFLICT×1 = 8 ✓）；
- tokens 随未决章数递增（39552→46725→50050），与"未决章烧满 3 轮预算"机制一致；
- ARC_CONFLICT 只落在 arc_003 强制章（1/5/9），fail-fast 守卫三次均按设计开火、无静默放行。

### D. 引用文档

| 文档 | 内容 |
|---|---|
| `docs/phase0-h53-contract-infeasibility.md` | H5.3 问题诊断 v1 |
| `docs/phase0-h53-spec-qa.md` | 协议裁定（QA 六问） |
| `docs/phase0-sample-status-and-revision-trace.md` | 采样状态与旧轨迹重建 |
| `docs/phase0-batch6-model-plan.md` | 批次 6 模型配置（同模型三次 + 身份写死） |
| `docs/phase0-v2-samples.md` | 三次采样原始读数（本汇总的数据源） |
