# H5.3 契约不可满足问题（v2，2026-10-09 协议核对后修订）

状态：**未改任何引擎代码**。引擎冻结在 `66f87e2`（386 tests green；离线 10 章 10/10、E1–E6 全 True）。
本文是待决策材料，不是结论报告。

> **v1 → v2 的更正（必读）**：v1 把根因写成「派生器不保证契约可满足，协议缺一条闭合规则」。
> 核对 04/05/10 协议原文后**该归属是错的**：协议语义清楚、没有洞。
> 根因是**夹具把协议附录 A 的单章示例契约逐字抄成了 10 章的逐章意图**（作者数据错误）。
> v1 的 C 提案（往 04 §4.3 补 D10）**撤回**。v2 新增一处**实现偏离协议**的发现（`_KNOWLEDGE_ESTABLISH`），
> 它使第 1 次采样的 8/10 在协议严格读法下只有 **5/10**。

---

## 1. 一句话

真实模型 10 章实验里被拒的章，不是模型写坏了。而现在测量用的尺子，**在两个方向上都偏离协议**：

- **偏严**：夹具要求同一对知识跃迁在每一章重复发生 → 每章两个固定靶。
- **偏松**：H5.3 的实现把 `knowledge` 和 `belief` 两个 field 的实现事件集合并了，
  于是 3 章靠 `BELIEVES` 满足了 `knowledge` 要求——协议不允许（10 §4.3 分表）。

第 1 次采样报的 8/10 提交，**两个数都不是协议说的那个数**。

---

## 2. 现象与第一次采样的完整报告

被拒两章的原始 dump（`phase0-fix-1`）：

```
# Chapter 6 — status=FAIL
message=not committable: HARD=1
contract_version=1 required_events=[]
- HARD H5.3: must_change char_000001.knowledge 无实现事件（W1）

# Chapter 7 — status=FAIL      （同上，逐字相同）
```

第 6 章模型实际写出的事件与标注：

```
- OBSERVES actor=char_000001 payload={'fact_id': 'fact_000003'}
- OBSERVES actor=char_000001 payload={'fact_id': 'fact_000004'}
<!-- reader_learns: fact_000003 -->  <!-- reader_hinted: fact_000004 -->  <!-- hook: cliffhanger strength=600 -->
```

正文完全围绕"印章伪造 / 宗门内有叛徒 / 守阁的人碰过印泥"，标注齐全。**写作质量上看不出任何该判死的理由。**

第 1 次采样完整报告：

```
tokens=55308  cost=$0.0000  用时=1187s
抽取产出 66 条 / 坏料 {'id_value_not_id': 6, 'missing_payload_keys': 4, 'unknown_event_type': 1}
生成 10 / 提交 8 / 未决 [6, 7] / replay一致 True
Revision：需修 6 章 / 最多 3 轮 / 修复率 0.67
§6: Contract / Arc 问题: 2 (H5.3)
§7: G3 True，其余 False → 可讨论改架构 True
§8: E1 True  E2 True  E3 False  E4 False  E5 True  E6 True
```

第 2 次采样（`phase0-fix-2`）**中途死掉**：`live.log` 空、只有 ch01–ch04 的 dump、系统内已无 python 进程。
**三次一致性目前无法回答。**

---

## 3. 协议语义核对：`must_change` 是 Δ（跃迁），不是章末谓词

三处原文一致：

| 出处 | 原文 |
|---|---|
| 04 §4.2（`04_contract_protocol.md:181`） | `must_change \| 结构化 \| HARD \| 每条必须被对应 Event 实现（映射表 10 §4.3）` |
| 04 §5.2 W1（`:240`） | `每条 must_change 是否被 10 §4.3 映射表指定的 Event 类型实现？` |
| 10 §4.3（`10_world_state_protocol.md:106-121`） | `Chapter Contract 的 must_change 写哪个 field，就必须由对应的 Event 类型实现，Validator 据此判定（04 §5.2 W1/W2）` |

⇒ 判定条件是"**本批事件里存在一条实现该变更的 Event**"，即 **Δ**；不是"章末状态满足谓词"。
`validator.py:496-501` 检查 `sim.applied` 中的存在性，**与协议一致**。

所以"同一对 target 出现在 10 章 ⇒ 每章都要重新发生一次该跃迁"**是协议的正确后果**。

### 3.1 根因位置：夹具抄了协议示例

`plot_engine/tests/fixtures/experiment_10ch.py:51-55`：

```python
"must_change": [
    {"character_id": "char_000001", "field": "knowledge", "operation": "add",
     "target": "fact_000003", "expected_value": "known"},
    {"character_id": "char_000001", "field": "knowledge", "operation": "add",
     "target": "fact_000001", "expected_value": "suspected"}]
```

与协议 **04 附录 A 示例契约**（`04_contract_protocol.md:275-279`，那是**第 47 章**）字节级相同。
示例是单章的；我把它当作 10 章的逐章意图复制粘贴了。
协议 D3–D9 从不要求派生器推导 `must_change`（D7 只要求声明 `derived_from`），`derive.py:183` 的逐字拷贝**正是协议规定的做法**。

⇒ **A（修夹具）是正解，不是权宜。**

---

## 4. 新发现：实现偏离协议（H5.3 的事件集）

10 §4.3 的映射表对两个 field 分得很清楚：

| field | 允许的 Event 类型（协议） |
|---|---|
| `knowledge` | OBSERVES / READS / IS_TOLD / INFERS |
| `belief` | BELIEVES / SUSPECTS / DOUBTS |

实现（`validator.py:358`）把它们**合并成一个集合，且不区分 `ch.field`**：

```python
_KNOWLEDGE_ESTABLISH = {"OBSERVES", "READS", "IS_TOLD", "INFERS", "BELIEVES", "SUSPECTS"}
# validator.py:497  if ch.field in ("knowledge", "belief"):   ← 两个 field 走同一集合
```

`DOUBTS` 还漏在集合外（belief 侧缺一类）。

### 4.1 实测影响：8/10 → 5/10

第 1 次采样 10 章，每个 `must_change` target 的实际覆盖事件类型：

```
ch01 OK   0003<- [INFERS,OBSERVES]      0001<- [INFERS]
ch02 OK   0003<- [BELIEVES]  ←偏差       0001<- [OBSERVES]
ch03 OK   0003<- [INFERS,STATES]        0001<- [OBSERVES]
ch04 OK   0003<- [OBSERVES]             0001<- [BELIEVES,INFERS,OBSERVES]
ch05 OK   0003<- [INFERS,OBSERVES]      0001<- [INFERS]
ch06 FAIL 0003<- [OBSERVES]             0001<- []          ←真未实现
ch07 FAIL 0003<- [READS]                0001<- []          ←真未实现
ch08 OK   0003<- [OBSERVES]             0001<- [BELIEVES]  ←偏差
ch09 OK   0003<- [OBSERVES]             0001<- [BELIEVES,INFERS]
ch10 OK   0003<- [OBSERVES]             0001<- [BELIEVES]  ←偏差
```

按 10 §4.3 严格判定，`knowledge` 要求被 `BELIEVES` 满足的 **ch02 / ch08 / ch10** 应判 FAIL。
⇒ 同一份模型输出，在协议尺下是 **5/10**（ch01/03/04/05/09），不是 8/10。

### 4.2 附带：H5.3 完全忽略 `operation` 与 `expected_value`

`validator.py:496-509` 只匹配 `field` + 事件类型集合 + `target` + `actor`。
`operation`（`add`/`remove`/`update`，`04_contract_protocol.md:111`）在 H5.3 里**不进入判定**，
`expected_value` 只在 H5.6 用到。

⇒ **修 A 时把 `add` 改成 `update` 是无效修改**：判定只看 `(character, field, target)`。
A 必须改 **`target`**（每章用自己那条真实推进的跃迁），或让部分章 `must_change` 为空。

---

## 5. 架构问题清单（v2 重排）

### 5.1 派生器不校验作者意图的合法性（B 的落点，不再是"根因"）

`must_change` 逐字拷贝是协议规定的，但派生器对"同一 target 在多章重复声明 add"、
"要求一个已建立的知识再建立一次"这类**明显不合法的作者意图**，零告警地放行到 Commit 才炸。
协议未授权派生器产出一章无解或纯靠运气的输入——B 就是补这条守卫。
严重性：**中**（放大 A 的错误、掩盖真实失败原因），不是独立根因。

### 5.2 契约自身字段间的矛盾检查放错层

H7.1–H7.11（`validator.py:582-652`）**没有一条**是"`must_change` 非空 ⇒ `required_events` 至少一条能实现它"。
注意 04 §5.1 **V6** 有 `must_change 与 must_not_change 无同字段冲突`——即"字段间对账"这类规则在协议里是存在的，
只是没有覆盖 `must_change × required_events`。于是矛盾一路走到 **Commit** 才由 H5.3 引爆，
此时 Writer 的章、抽取的事件、全部 token 已经花掉。

### 5.3 失败路由表漏一条就静默走错层

`revision.py:38-51` 的 `RULE_TO_LEVEL` 只有 `"H5.1": "contract"`，**没有 `H5.3`**；注释「未列出的 rule 保守归 writer」。
于是 H5.3 ⇒ writer 层 ⇒ `rewrite_chapter` ⇒ 契约一字不改地重写 3 轮 ⇒ budget 耗尽、章作废。
"保守归 writer"这个默认值对**契约类**失败是错的，代价是整轮 token。

同族第二处：`classify.py` 的 `RULE_TO_METRIC` 没有 `I9`，落 CANON 兜底，而 08 §3 意图归 KNOWLEDGE
⇒ §6 失败分桶现在也在静默错分。（`66f87e2` 修的是同一个模式的另一半：违规不带 code 出不了镜。）

### 5.4 路由对了也修不到点上——且这是**协议空白**，不是实现绕过

`revision_actions.py:28-33` 的 `relaxable` 三项全在 `required_events` 轴上，重新派生后 `must_change` 原样回来：

```python
authored  = {e.event_type for e in intents_by_chapter(arc)[ch].required_events}
relaxable = (set(ctx.unsatisfied_event_types) & authored) - arc_mandated_event_types(arc, ch)
kept      = [e for e in fresh.required_events if e.event_type not in relaxable]   # must_change 不参与
```

但 06 §4.2 对 contract error 的原文定义就是「Contract 要求的事件在当前 State 下无法发生」，讲的是 `required_events`。
**06 没有为 `must_change` 类失败定义任何归属**——协议空白。
它不阻塞当前：正确修法本来就是回作者意图（A），而不是让引擎放宽作者写错的要求
（那正是我们上次定下"Arc 强制的要求一条都不许掉"要避免的自欺）。记 Phase 1 backlog。

### 5.5 `escalate_to_arc` 未注册 = **漏项**

10 份计划里，`escalate_to_arc` 的注册**没在任何一份中被写出**；`_LEVEL_TO_ACTION` 有它（`revision.py:62`），
主循环 actions 里没有，`revision.py:159` 对未注册动作直接转人工。没有条文或注释说明它刻意不做 ⇒ 判定为漏项。
但现在**不该接**：真实模型下接上它，会把"作者意图写错"这类事自动升级成一条没人审的回路，
Phase 0 只有 10 章样本，看不出它是修好还是绕过。记 backlog。

---

## 6. 08 I2「不改 HARD 判据」的边界（我的裁定，需你确认）

**定义：判据 = 协议文本里的 rule 语义 + severity + 映射表。**
I2 禁止的是改这三者。代码向协议文本靠拢不是改判据（那本来就是 Phase 0 的实现义务）；
代码偏离协议文本才是 bug。

| 改动 | 改的是 | 违反 I2？ |
|---|---|---|
| **A** 修夹具意图 | 测试数据 | 否 |
| **D** 修 `_KNOWLEDGE_ESTABLISH` 按 10 §4.3 分表 + 补 `DOUBTS` | 实现偏离协议文本；**使判定变严** | 否（我的判断） |
| **B** 派生器守卫（`must_change` 无可实现类型 ⇒ `raise ArcConflict`） | 生成器对自己输入的校验；HARD 判据一条不动 | 否（我的判断） |
| **C** 往 04 §4.3 补 D10 | 协议文本 | **是，需批准 ⇒ 已撤回** |
| `RULE_TO_LEVEL` 补 `H5.3 → contract`；`RULE_TO_METRIC` 补 `I9 → KNOWLEDGE` | 失败归因路由，非判据 | 否 |

副作用要说清：B 确实会间接减少"判据被绕过"的机会，但它不改变任何 rule 的触发结果，
只改变"非法契约能不能走到 Commit"。
D 会**改变**触发结果（变严），因为当前结果本身就偏离协议。

---

## 7. 修法与我的建议

| | 做法 | 性质 | 备注 |
|---|---|---|---|
| **A** | 夹具逐章意图各自不同：每章只声明本章真正发生的那次跃迁（`operation=add` 只用于该 fact 首次建立的那一章） | 改数据 | **正解**，协议无错 |
| **D** | `_KNOWLEDGE_ESTABLISH` 按 10 §4.3 拆成 knowledge / belief 两张表，补 `DOUBTS` | 实现回协议 | 做完 8/10 → 5/10（数字变难看，但是协议的数） |
| **B** | 派生守卫：`must_change` 非空而 `required_events` 无可实现类型 ⇒ `raise ArcConflict` | 生成器自保护 | 可选；先做 A 才有意义 |
| ~~C~~ | ~~04 §4.3 补 D10~~ | ~~协议变更~~ | **撤回**：协议语义完整 |
| 附带 | `RULE_TO_LEVEL` 补 H5.3；`RULE_TO_METRIC` 补 I9；`escalate_to_arc` 注册与否 | 路由/归因 | 独立于 A/D，不改变判定结果 |

**建议顺序：A + D → 重跑三次 → 再决定 B。**
理由：现在跑第 2、3 次，是在一把已知两个方向都偏离协议的尺上读数；
两次采样各约 20 分钟、约 55k tokens，读出来的三次一致性只能证明"这把错尺很稳定"。

**采样已暂停**，等这条决定。

---

## 8. 与已修的 I9 问题别混淆

`66f87e2` 修的是**一致性闸拿错事件集**：增量 reduce 用"本批事件"当已提交集，
导致第 1 章 ledger 的 source 指针从第 2 章起永远"指向批外"，整条故事被 I9 判死；
且表现为 `consistency_hard=n` 而**一个 rule_id 都没有**。

本文是**契约层的两个独立问题**（夹具数据 + 实现偏离映射表）。
共同模式：**引擎自己制造（或掩盖）失败，然后把它算成模型的失败。**
`66f87e2` 新增的 `CommitOutcome.consistency` 让违规带 code 进 §6 桶和逐章 dump，
本文这些证据全部来自那次改动之后的 dump。

---

## 9. 待你拍板

1. **顺序**：A + D 后再跑三次？还是先跑完三次、带已知偏差写进报告？（我建议前者）
2. **D 的 I2 定性**：把 `knowledge` 的实现事件集从合并集合改回 10 §4.3 的分表，
   我判断是"实现符合协议"而非"改 HARD 判据"——但它会让通过率从 8/10 掉到 5/10，所以我不自己动手。
3. **B 做不做**、以及 `RULE_TO_LEVEL[H5.3]` / `RULE_TO_METRIC[I9]` / `escalate_to_arc` 这三项路由改动
   是现在做还是记 backlog。

在此之前不动引擎代码；`docs/phase0-live-run-10ch.md` 的三次并列也先欠着——它欠的是有效数据，不是拖延。
