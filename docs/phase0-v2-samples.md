# 冻结面 v2 三次采样原始读数

冻结提交 `f99cc00`。模型：`qwen2.5:14b` @ `http://127.0.0.1:11434/v1`（`router_local.json` sha12 `a820beb0d944`）。
口径见 `docs/phase0-batch6-model-plan.md` §2 步骤 5：主口径 = E1–E6 六个布尔值三次完全一致；辅口径 = 逐章 commit/fail 模式一致；主口径不一致时三次完整并列，禁止取多数/合并/挑最好看的一次。
串行执行，每次 detached + `run.log`/`run.err` 留痕，跑后先验 `run.log` 非空才采信。

## s1 — `C:\Users\tff\AppData\Local\Temp\phase0-v2-s1`

08:54:13 → 09:07，813s，tokens=39552，cost=$0.0000。`run.log` 非空、`run.err` 0 字节。

抽取产出 57 条 / 坏料 `{'unknown_id': 1, 'unknown_event_type': 1}`

生成 10 / 提交 6 / 未决 `[2, 5, 7, 10]` / replay 一致 True

| 节 | 读数 |
|---|---|
| §6 | Writer/Validator 2（H2.2）｜Contract/Arc 6（ARC_CONFLICT, H5.1, H5.3, H5.6） |
| §7 | G1 True｜G2 False｜G3 True｜G4 False｜可讨论改架构 True |
| §8 | E1 True｜E2 False｜E3 N/A｜E4 True｜E5 True｜E6 True |

逐章（status / contract_version / rounds / HARD）：

| 章 | status | v | rounds | HARD |
|---|---|---|---|---|
| 01 | OK | 1 | 0 | |
| 02 | FAIL | 2 | 1 | H2.2、H5.3、H5.6 |
| 03 | OK | 2 | 1 | |
| 04 | OK | 1 | 0 | |
| 05 | ARC_CONFLICT | 1 | 0 | `arc_003 第 5 章落空的事件类型是 Arc 强制项，契约层无权放宽：['INFERS']` |
| 06 | OK | 2 | 1 | |
| 07 | FAIL | 4 | 3 | H5.1、H5.3 |
| 08 | OK | 1 | 0 | |
| 09 | OK | 1 | 0 | |
| 10 | FAIL | 3 | 2 | H2.2、H5.6 |

## finding-1：v2 冻结面上「需人工判定的修订」会让 E3 假降级为 N/A（采样期不修）——详见文末

## s2 — `C:\Users\tff\AppData\Local\Temp\phase0-v2-s2`

09:08 → 09:25，1026s，tokens=46725，cost=$0.0000。`run.log` 非空、`run.err` 0 字节。

抽取产出 74 条 / 坏料 `{'id_value_not_id': 2}`

生成 10 / 提交 4 / 未决 `[1, 2, 5, 7, 9, 10]` / replay 一致 True

| 节 | 读数 |
|---|---|
| §6 | Writer/Validator 3（H2.2）｜Contract/Arc 8（ARC_CONFLICT, H5.3, H5.6） |
| §7 | G1 True｜G2 False｜G3 True｜G4 False｜可讨论改架构 True |
| §8 | E1 True｜E2 False｜E3 N/A｜E4 True｜E5 True｜E6 True |

逐章：

| 章 | status | v | rounds | 判定 |
|---|---|---|---|---|
| 01 | ARC_CONFLICT | 1 | 0 | mid-loop：`arc_003 第 1 章落空的事件类型是 Arc 强制项，契约层无权放宽：['INFERS']` |
| 02 | FAIL | 2 | 1 | HARD H2.2（fact_000001 期望 known）等 3 条 |
| 03 | OK | 1 | 0 | |
| 04 | OK | 1 | 0 | |
| 05 | FAIL | 2 | 1 | HARD H2.2（fact_000004 期望 suspected）等 3 条 |
| 06 | OK | 2 | 1 | |
| 07 | FAIL | 4 | 3 | HARD H5.3：must_change char_000001.belief 无实现事件（W1） |
| 08 | OK | 1 | 0 | |
| 09 | ARC_CONFLICT | 2 | 1 | mid-loop：`['BELIEVES']` 落空且为 Arc 强制项 |
| 10 | FAIL | 1 | 3 | HARD H2.2（fact_000002 期望 known）等 2 条 |

## s3 — `C:\Users\tff\AppData\Local\Temp\phase0-v2-s3`

09:26 → 09:45，1124s，tokens=50050，cost=$0.0000。`run.log` 非空、`run.err` 0 字节。

抽取产出 89 条 / 坏料 `{'id_value_not_id': 1, 'stripped_payload_key': 1}`

生成 10 / 提交 3 / 未决 `[1, 2, 3, 6, 7, 9, 10]` / replay 一致 True

| 节 | 读数 |
|---|---|
| §6 | Writer/Validator 3（H2.2）｜Contract/Arc 9（ARC_CONFLICT, H5.3, H5.6） |
| §7 | G1 True｜G2 False｜G3 True｜G4 False｜可讨论改架构 True |
| §8 | E1 True｜E2 False｜E3 N/A｜E4 True｜E5 True｜E6 True |

逐章：

| 章 | status | v | rounds | 判定 |
|---|---|---|---|---|
| 01 | ARC_CONFLICT | 1 | 0 | mid-loop：`['INFERS']` 落空且为 Arc 强制项 |
| 02 | FAIL | 2 | 1 | HARD H2.2（fact_000001 期望 known）、H5.3、H5.6 |
| 03 | FAIL | 3 | 2 | HARD H5.3：must_change char_000001.belief 无实现事件（W1） |
| 04 | OK | 1 | 0 | |
| 05 | OK | 1 | 0 | |
| 06 | FAIL | 2 | 1 | HARD H2.2（fact_000004 期望 known）、H5.3、H5.6 |
| 07 | FAIL | 4 | 3 | HARD H5.3：must_change char_000001.belief 无实现事件（W1） |
| 08 | OK | 1 | 0 | |
| 09 | ARC_CONFLICT | 2 | 1 | mid-loop：`['BELIEVES', 'INFERS']` 落空且为 Arc 强制项 |
| 10 | FAIL | 1 | 3 | HARD H2.2（fact_000002 期望 known）、H5.6 |

## finding-2：三次样本的 `experiment_id` 都是 `exp-s1-42`（仅报告标签，不影响数据）

`experiment.py:155` 的 `experiment_id = f"exp-{story}-{config.seed}"`，live 路径里 `story_id` 恒为 `s1`、`seed` 恒为 `42`，与第几次采样无关。三次样本唯一可信的区分是 `--dump-dir` 目录名与各自 `run.log`；状态库/事件库走 `tempfile.mkdtemp(prefix="phase0-live-")`，每次全新实例，不存在跨样本复用。冻结后修法：把尝试序号并入 `story_id` 或 `experiment_id`。

---

## 三次并列对比与结论

### 主口径：E1–E6 六个布尔值 —— **三次完全一致**

| | s1 | s2 | s3 |
|---|---|---|---|
| 生成 / 提交 / 未决 | 10 / 6 / 4 章 | 10 / 4 / 6 章 | 10 / 3 / 7 章 |
| replay 一致 | True | True | True |
| §7 G1 / G2 / G3 / G4 / 可讨论改架构 | T / F / T / F / T | T / F / T / F / T | T / F / T / F / T |
| §8 E1 / E2 / E3 / E4 / E5 / E6 | T / F / N/A / T / T / T | T / F / N/A / T / T / T | T / F / N/A / T / T / T |

E2 三次同为 False，提交率 60% / 40% / 30% 都在阈值 `commit_rate >= 0.70`（`experiment.py:184`）之下；
裕度不等宽——s1 的 6/10 只差一章就翻真，s2/s3 远离阈值（详见 `docs/phase0-v2-review-verification.md` §4）。
E3 三次同为 N/A，原因见 finding-1，**不是「修订没跑」**（逐章快照里 r≥1 的章：s1 5 章、s2 6 章、s3 6 章）。

### 辅口径：逐章 commit/fail 模式 —— **三次不一致**

| 章 | s1 | s2 | s3 | 一致性 |
|---|---|---|---|---|
| 01 | OK | ARC_CONFLICT | ARC_CONFLICT | 抖动 |
| 02 | FAIL | FAIL | FAIL | 稳定失败 |
| 03 | OK | OK | FAIL | 抖动 |
| 04 | OK | OK | OK | 稳定通过 |
| 05 | ARC_CONFLICT | FAIL | OK | 三种结局 |
| 06 | OK | OK | FAIL | 抖动 |
| 07 | FAIL | FAIL | FAIL | 稳定失败 |
| 08 | OK | OK | OK | 稳定通过 |
| 09 | OK | ARC_CONFLICT | ARC_CONFLICT | 抖动 |
| 10 | FAIL | FAIL | FAIL | 稳定失败 |

5 章三次同一结论（02/04/07/08/10），5 章抖动（01/03/05/06/09）。请求体没有 seed / top_p（`llm.py:111-115`），writer 温度 0.8 ⇒ 三次是同一分布的三次独立抽样，逐章边界翻转是预期行为，不视为回归。

抖动的 5 章恰好全在**转折章 1/5/9 及其邻章**：`ARC_CONFLICT` 只出现在 arc_003 强制 `INFERS`/`BELIEVES` 的章（1/5/9），它是否触发取决于那一轮模型有没有写出该事件——批次 4 的 fail-fast 守卫按设计只在强制项落空时开火，三次都没让它静默放过。

稳定失败的三章是同一批根因：ch02 / ch10 都是 `H2.2` 知识跃迁（fact_000001 / fact_000002 期望 known）没实现，配对的 `H5.3`+`H5.6`；ch07 三次都停在 `H5.3 must_change char_000001.belief 无实现事件`，且三次都走满 3 轮并 renegotiate 到 `contract_version=4` 后仍不合格。

### 结论（只按预注册口径下）

1. **尺在三次之间可比**：主口径六布尔值零分歧，§7 四闸零分歧，replay 一致零分歧。冻结面 v2 的度量输出稳定。
2. **Phase 0 → Phase 1 未达成**：E2 三次同判 False（提交率 30%–60%），E3 因 finding-1 三次不可判。按 08 §8，E2 不过即不放行。
3. **稳定失败核先于抖动**：要提提交率，第一顺位是 ch02/ch10 的 `H2.2` 知识跃迁与 ch07 的 belief `H5.3`——这三章在三次抽样里没有一个侥幸过；抖动章的处置要等一个可控变量（seed / 更低温度）才有意义。
4. **禁止事项已遵守**：未取多数、未合并、未挑任一次作为代表读数；三个 `run.log` 与 30 份逐章快照全部保留。
5. 与旧尺对照：`docs/phase0-live-run-10ch.md` 的 `fix-1`（8/10）与 `fix-2` 残片是 D+A 两次 alignment 之前的读数，**不与本节并列比较**，仅作历史留档。

## finding-1：v2 冻结面上「中途判死章」会让 E3 假降级为 N/A（采样期不修）

`review.py:87` 的 `revision_ran = len(report.revision_rounds) == report.chapters_generated`，
而 `experiment.py:108-113` 里中途抛 `ArcConflict` 的章只 `generated += 1` 就 `continue`，不写 `rounds_by_chapter`。
⇒ s1 的 ch05、s2 的 ch01/ch09、s3 的 ch01/ch09 各自让 `len(rounds_by_chapter) < generated`，
`render_review_text` 落进「未运行」分支、E3 变 N/A——**而修订确实跑过**。

三次采样同码 ⇒ 该读数在三次之间可比，主口径不受影响；E3 三次都不可判。
冻结后修法：quarantine 分支同样落 `rounds_by_chapter[ch]`（一行：`max(len(captured) - 1, 0)`），
同一判据在两处（`review.py:87` 渲染、`experiment.py:194` E3 计算），记快照即可两处同时好
——见 `docs/phase0-v2-review-verification.md` §1。
