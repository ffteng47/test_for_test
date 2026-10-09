# 协议核对答复（2026-10-09，对齐你列的 6 问）

引擎状态：**冻结 `66f87e2`，未改任何代码**。本文只给答复与证据。
配套的问题报告见 `docs/phase0-h53-contract-infeasibility.md`（那份是诊断，本文是裁定）。

---

## Q1. `must_change` 的设计语义：Δ（跃迁），确定无疑

三处协议文本一致：

| 出处 | 原文 |
|---|---|
| 04 §4.2 字段语义表（`04_contract_protocol.md:181`） | `must_change \| 结构化 \| HARD \| 每条必须被对应 Event 实现（映射表 10 §4.3）` |
| 04 §5.2 W1（`:240`） | `每条 must_change 是否被 10 §4.3 映射表指定的 Event 类型实现？` |
| 10 §4.3（`10_world_state_protocol.md:106-121`） | 逐 field 列出「由哪类 Event 实现」，收口：`Chapter Contract 的 must_change 写哪个 field，就必须由对应的 Event 类型实现，Validator 据此判定（04 §5.2 W1/W2）` |

即：**实现条件是"本批事件里存在一条实现该变更的 Event"，不是"章末状态满足谓词"** ⇒ 是 **Δ**。
`validator.py:496-501` 检查 `sim.applied` 中的存在性，与协议一致。

**⇒ D 成立**：「同一对 target 写进 10 章 ⇒ 每章都要重新发生一次该跃迁、每章两个固定靶」是协议的**正确后果**，不是误读。

但责任归属要改：**不是协议有洞，是夹具错了。**
`plot_engine/tests/fixtures/experiment_10ch.py:51-55` 那两条 `must_change`，与协议 **04 附录 A 的示例契约**
（`04_contract_protocol.md:275-279`，那是**第 47 章**的单章示例）**字节级相同**——我把单章示例抄成了 10 章的逐章意图。
协议 D3–D9 从不要求派生器推导 `must_change`（D7 只要求声明 `derived_from`），`derive.py:183` 的逐字拷贝**正是协议规定的做法**。

⇒ **A 是正解，不是权宜；C（往 04 §4.3 补 D10）撤回。**

---

## Q2. 08 I2「不改 HARD 判据」的边界

**我的划线：判据 = 协议文本里的 rule 语义 + severity + 映射表。I2 禁止改这三者。**
代码向协议文本靠拢**不是**改判据（那本来就是 Phase 0 的实现义务）；代码偏离协议文本**是** bug。

你问的「改 H5.3 的读法（不改 severity、不改 rule_id，只改何时触发）」，我的判断是**不算改判据**，但要把两种情况分开：

- **代码当前偏离协议文本**（如事件集合并了两个 field，见 Q3）⇒ 改回对齐 = 实现修复，**不算改判据**。
  副作用是判定**变严**，因为当前结果本身不是协议的数。
- **代码当前符合协议文本，只是提前拒绝非法输入**（B：`must_change` 无可实现类型 ⇒ `raise ArcConflict`）
  ⇒ 不改任何 rule 的触发结果，只改"非法契约能不能走到 Commit"，**也不算改判据**。
  它的副作用确实会间接减少判据被绕过的机会，但不触碰 severity / rule_id / 语义。

| 改动 | 改的是 | 违反 I2？ |
|---|---|---|
| A 修夹具意图 | 测试数据 | 否 |
| D 修 `_KNOWLEDGE_ESTABLISH` 按 10 §4.3 分表 + 补 `DOUBTS` | 实现偏离协议文本；使判定变严 | 否（我的判断） |
| B 派生守卫 `raise ArcConflict` | 生成器对输入的校验，HARD 判据一条不动 | 否（我的判断） |
| C 补 04 §4.3 D10 | 协议文本 | **是，需批准 ⇒ 已撤回** |
| `RULE_TO_LEVEL` 补 `H5.3 → contract`；`consistency_counts` 未映射 code 的处置与 `classify_outcome` 对齐 | 失败归因路由，非判据 | 否 |

**更正（批次 0 核实）**：本文原列的「`RULE_TO_METRIC` 补 `I9 → KNOWLEDGE`」是**误报**。
表定义在 `models/experiment.py:35-57`（`classify.py:12` 只是 import），`"I9": HardMetric.KNOWLEDGE` 在 `:50`，
自 `ff37e2b` 起就存在、`66f87e2` 里也在 ⇒ 第 1 次采样的 §6 归桶**没有**把 I9 落 CANON，**无需重读**。
未映射 code 的**真**不一致在别处：`classify.py:70-72` 的 `consistency_counts` 是 `if key:` ⇒ 静默**丢弃**，
而 `classify_outcome:28` 是兜底归 CANON。两条路径对"未映射"处置不同，需对齐。

这条线涉及协议文本的解释权，**由你拍板**。

---

## Q3. 我的立场：Phase 0 **测引擎**；而现在采样用的是一把不是协议那把的尺

立场：**测引擎**。08 §4 明写 Phase 0「不追求好看，只追求不崩」，模型只是被要求"不崩"的外部演员。
所以首要条件是尺子等于协议。**现在它在两个方向上都不等：**

- **偏严**：夹具重复 Δ（Q1）。
- **偏松**（新发现）：`validator.py:358` 把两个 field 的事件集合并了——

```python
_KNOWLEDGE_ESTABLISH = {"OBSERVES", "READS", "IS_TOLD", "INFERS", "BELIEVES", "SUSPECTS"}
# validator.py:497   if ch.field in ("knowledge", "belief"):   ← 两个 field 走同一集合
```

10 §4.3 分得很清楚：`knowledge → OBSERVES/READS/IS_TOLD/INFERS`；`belief → BELIEVES/SUSPECTS/DOUBTS`
（`DOUBTS` 还漏在集合外）。

第 1 次采样 10 章每个 `must_change` target 的实际覆盖事件类型：

```
ch01 OK   0003<- [INFERS,OBSERVES]      0001<- [INFERS]
ch02 OK   0003<- [BELIEVES]  ←偏差       0001<- [OBSERVES]
ch03 OK   0003<- [INFERS,STATES]        0001<- [OBSERVES]
ch04 OK   0003<- [OBSERVES]             0001<- [BELIEVES,INFERS,OBSERVES]
ch05 OK   0003<- [INFERS,OBSERVES]      0001<- [INFERS]
ch06 FAIL 0003<- [OBSERVES]             0001<- []          ← 真未实现
ch07 FAIL 0003<- [READS]                0001<- []          ← 真未实现
ch08 OK   0003<- [OBSERVES]             0001<- [BELIEVES]  ← 偏差
ch09 OK   0003<- [OBSERVES]             0001<- [BELIEVES,INFERS]
ch10 OK   0003<- [OBSERVES]             0001<- [BELIEVES]  ← 偏差
```

**ch02 / ch08 / ch10 的 knowledge 要求是被 `BELIEVES` 满足的，按协议不该算。**
严格按 10 §4.3 判定，同一份模型输出是 **5/10**（ch01/03/04/05/09），不是 8/10——而这仍是夹具错误契约下的 5/10。

⇒ 所以「测引擎+模型、A+B'+显式记录也可接受」这个折中我现在**不接受**：
问题不是噪声大小，而是**通过率本身是假的**。
**建议：A + D（修事件集分表）→ 再跑三次 → 再决定 B。**

---

## Q4. 第 1 次采样结果 & 三次一致性

**先纠正一处命名**：`phase0-fix-1` 是**第 1 次**采样（已完成）；第 2 次是 `phase0-fix-2`。

第 1 次（`phase0-fix-1`）完整报告：

```
tokens=55308  cost=$0.0000  用时=1187s
抽取产出 66 条 / 坏料 {'id_value_not_id': 6, 'missing_payload_keys': 4, 'unknown_event_type': 1}
生成 10 / 提交 8 / 未决 [6, 7] / replay一致 True
Revision：需修 6 章 / 最多 3 轮 / 修复率 0.67
§6: Contract / Arc 问题: 2 (H5.3)
§7: G3 True，其余 False → 可讨论改架构 True
§8: E1 True  E2 True  E3 False  E4 False  E5 True  E6 True
```

**第 2 次（`phase0-fix-2`）死了**：`live.log` 空、只有 ch01–ch04 的 dump、系统内已无 python 进程
（最可能是承载它的后台 shell 随会话中断被终止；原因未查）。
**⇒ 三次一致性现在无法回答，手上只有一份完整数据。**

顺带：隧道里现在只列出 `qwen2.5:14b, deepseek-r1:14b/32b/7b`（服务端 Ollama 仍未修好，qwen3 系列不可见）。

我不建议照原样补跑第 2、3 次：按 Q3，它们会在同一把错尺下各花 ~20 分钟和 ~55k tokens，
三次一致性只能证明"这把错尺很稳定"。**采样已停，等你这一条决定。**

---

## Q5. `escalate_to_arc`：**一半刻意、一半漏项**（我先前只看到漏的那半）

**事实 1：它确实没被注册成动作。** 真实模型主循环只注入四个动作（`plot_engine/review.py:244-247`）：

```python
loop = RevisionLoop(actions={"rerun_extraction": ..., "rewrite_scene": rewrite,
                             "rewrite_chapter": rewrite,
                             "renegotiate_contract": renegotiate_contract(...)})   # 无 escalate_to_arc
```

**事实 2：「不自动执行 arc 层」是刻意设计，有明文。**
Day 26–27 计划 `docs/superpowers/plans/2026-10-09-alexandria-revision-loop.md:15`：

> `rerun_extraction / rewrite_scene / rewrite_chapter / renegotiate_contract / escalate_to_arc`
> 全为注入 `Callable`，默认 `None` → 该层级不可自动执行 → 记 `needs_human=True`（Auto-Mode #6）

Day 31–33 计划 `:72` 也写着「违反即 `escalate_to_arc` … 落 `needs_human`，不静默通过」。
⇒ 我上一轮答"漏项"**不准确**，这里更正。

**事实 3：真正漏的是入路——arc 层没有任何入口。**
`revision.py:38-51` 的 `RULE_TO_LEVEL` 里**没有任何 rule 映射到 `"arc"`**（只有 extraction / event / fact / contract / state，其余归 writer）。
⇒ `escalate_to_arc` 不但没被注入，**连被 `next_action` 选中的可能性都没有**：分类器永远不产出 arc 层。
而计划 `:72` 承诺的那条入路——「重议时发现 Arc 强制项就是失败原因 ⇒ 走 `escalate_to_arc`」——**没有实现**：

```python
# revision_actions.py:29-30
relaxable = (set(ctx.unsatisfied_event_types) & authored) - arc_mandated_event_types(arc, ch)
# Arc 强制项被静默从 relaxable 里减掉：不 raise、不上抛、不产生 arc 层 Root Cause
```

⇒ **精确结论：不自动执行 = 刻意（有明文）；Arc 强制冲突时应当上报 arc 层 = 漏项，且当前是静默吞掉的。**
后者意味着：如果将来某个 Arc 强制项真的不可满足，实验会报「契约已重议、要求未减」，
而不是报「需要人来看弧线」——**这是一个会伪装成通过的洞**。

建议：仍**不接成自动动作**（10 章样本看不出自动改弧线是修好还是绕过），
但应补**上抛**——撞上 Arc 强制项时 `raise`，让它按计划明文落 `needs_human`。记 backlog，待批准。

---

## Q6. `derive.py:183` 逐字拷贝 = **是**；`operation="update"` 合法但**换了也没用**

逐字拷贝，确认：`must_change=intent.must_change`（同文件 `must_not_change`、`forbidden_events` 一样逐字拷贝）。

`operation: Literal["add", "remove", "update"]`（`04_contract_protocol.md:111`），
协议示例的 `must_not_change` 就用了 `update`（`:282`）⇒ **A 是纯改数据，不改 intent schema。**

**但有个实测要点**：H5.3 **完全不看 `operation` 和 `expected_value`**——
`validator.py:496-509` 只匹配 `field` + 事件类型集合 + `target` + `actor`（`expected_value` 只在 H5.6 用到）。
⇒ **把 `add` 改成 `update` 不改变判定**。
A 必须改 **`target`**（每章只声明本章真正发生的那次跃迁，`operation=add` 只用于该 fact 首次建立的那一章），
或让部分章 `must_change` 为空；只在 `operation` 上做文章是无效修改。

---

## 附：`renegotiate_contract` 事实上无法放宽 `must_change` 侧（上一轮提问，一并答）

确认。`revision_actions.py:28-33` 三项运算全在 `required_events` 轴上，`fresh` 重新派生后 `must_change` 原样回来：

```python
authored  = {e.event_type for e in intents_by_chapter(arc)[ch].required_events}
relaxable = (set(ctx.unsatisfied_event_types) & authored) - arc_mandated_event_types(arc, ch)
fresh     = derive_chapter_contract(...)
kept      = [e for e in fresh.required_events if e.event_type not in relaxable]   # must_change 不参与
```

一处纠正：`renegotiate_contract` 的动作注册在 **Day 31–33 plot-derivation 计划 Task 3**（代码位 `review.py:246`）；
Day 26–27 计划里它只是**注入槽位**（默认 `None`）。

但它**不该**被改成 `must_change` 的逃生口：06 §4.2 对 contract error 的原文定义是
「Contract 要求的事件在当前 State 下无法发生」（`revision.py:48` 注释同此），讲的就是 `required_events`。
**06 没有为 `must_change` 类失败定义任何归属** ⇒ 协议空白，记 Phase 1 backlog，不阻塞当前
（当前正解是回作者意图 A，不是让引擎放宽作者写错的要求——那正是「Arc 强制的要求一条都不许掉」要避免的自欺）。

---

## 待你拍板

1. **顺序**：A + D 后再跑三次？还是先跑完三次、带已知偏差写进报告？（我建议前者）
2. **D 的 I2 定性**：把 `knowledge` 的实现事件集改回 10 §4.3 分表，算不算 I2 下可直接修的「实现不符合协议」？修完 8/10 → 5/10。
3. **B 做不做**；`RULE_TO_LEVEL[H5.3]` / `RULE_TO_METRIC[I9]` / Q5 的 arc 上抛，是现在做还是记 backlog。
