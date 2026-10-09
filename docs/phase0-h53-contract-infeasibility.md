# H5.3 契约不可满足问题（2026-10-09 记录）

状态：**未修复，未改代码**。本文只记录问题、证据和涉及的架构缺陷，供决策。
引擎冻结在 `66f87e2`（386 tests green；离线 10 章 10/10、E1–E6 全 True）。

---

## 1. 一句话

真实模型 10 章实验里，被拒的章不是"模型写坏了"，而是**引擎发给模型的章节契约本身在逻辑上无法稳定满足**，
而且修订循环没有能力修它——它只会让 Writer 把同一道无解的题重写 3 遍，然后整章作废。

---

## 2. 现象

修复版第 1 次采样（`phase0-fix-1`）：10 章拒 2 章，两章失败信息完全相同：

```
# Chapter 6 — status=FAIL
message=not committable: HARD=1
contract_version=1 required_events=[]
- HARD H5.3: must_change char_000001.knowledge 无实现事件（W1）

# Chapter 7 — status=FAIL
message=not committable: HARD=1
contract_version=1 required_events=[]
- HARD H5.3: must_change char_000001.knowledge 无实现事件（W1）
```

第 6 章模型实际写出的事件（dump 的 Proposals 段）：

```
- OBSERVES actor=char_000001 payload={'fact_id': 'fact_000003'}
- OBSERVES actor=char_000001 payload={'fact_id': 'fact_000004'}
```

正文完全围绕"印章伪造 / 宗门内有叛徒 / 守阁的人碰过印泥"展开，章尾 markup 也齐（`reader_learns: fact_000003`、
`reader_hinted: fact_000004`、`hook: cliffhanger strength=600`）。**从写作质量上看不出任何该判死的理由。**

---

## 3. 契约是怎么生成的 —— 矛盾在这里

每章开工前 `plot_engine/derive.py` 产出 `ChapterContract`，两个关键字段走**两条互不知道对方的路**：

| 字段 | 含义 | 来源 |
|---|---|---|
| `must_change` | 本章**必须变成**的状态（结果） | 作者意图**逐字拷贝**：`must_change=intent.must_change`（`derive.py:183`） |
| `required_events` | 本章**必须出现**的事件（动作） | 引擎按 D3/D6 推导：只有 turning point 到章、逾期闸门才会加（`derive.py:130` 起） |

10 章的 `required_events` 实测：

```
ch01 ['OBSERVES']   ch02 []   ch03 []   ch04 []   ch05 ['INFERS']
ch06 []             ch07 []   ch08 []   ch09 ['INFERS','OBSERVES']  ch10 []
```

只有 3/10 章有"必现事件"，而 `must_change` 十章全有。所以 7 章拿到的是：
**「你必须改变 X，但我没要求你做任何事」**。

更要紧的是：夹具给这 10 章写的 `must_change` **两条 target 完全相同**
（`plot_engine/tests/fixtures/experiment_10ch.py:51-55`）：

```python
"must_change": [
    {"character_id": "char_000001", "field": "knowledge", "operation": "add",
     "target": "fact_000003", "expected_value": "known"},
    {"character_id": "char_000001", "field": "knowledge", "operation": "add",
     "target": "fact_000001", "expected_value": "suspected"}]
```

而 H5.3 的判定是"**本批事件里存在一条引用该 fact 的知识建立事件**"：

```python
# plot_engine/validator.py:496-501
def _change_implemented(sim: Simulation, ch) -> bool:
    if ch.field in ("knowledge", "belief"):
        return any(ev.event_type in _KNOWLEDGE_ESTABLISH
                   and (_referenced_fact(ev) == ch.target)
                   and (ev.actor == ch.character_id)
                   for ev in sim.applied)
```

`_KNOWLEDGE_ESTABLISH = {OBSERVES, READS, IS_TOLD, INFERS, BELIEVES, SUSPECTS}`（`validator.py:358`），
`_referenced_fact` 只看 `fact_id / conclusion_fact_id / stated_fact_id / target`，**不看 `evidence_fact_ids`**（`validator.py:364-366`）。

把两件事合起来，这份契约对模型的实际要求是：

> **连续 10 章里，每一章都必须重新让张三"第一次"知道 fact_000003，并且每一章都必须再有一条专门指向 fact_000001 的知识建立事件。**

这在叙事上是荒谬的（第 1 章就知道的事，为什么第 7 章还要再知道一次），在工程上就是**每章两个必须命中的固定靶**。
命中就过，打空就死。ch06 打了 0003/0004 两个靶没打 0001；ch07 打了 0004/0003 也没打 0001 → 双双判死。
其余 8 章过了，是因为模型**自发**写出了这两条——不是契约要求的。

**结论：一章能不能提交，取决于模型这一次手气，不取决于契约。** 这正是 backlog #6 说的"不可量化方差"，
但方差不是来自模型，是**我们欠定的契约转嫁给模型的方差**。测模型之前，先测到的是自己的噪声。

---

## 4. 涉及的四个架构问题

### 4.1 派生器不保证自己产出的契约可满足（根因）

结果要求（`must_change`）从作者意图拷贝，动作要求（`required_events`）由 D3/D6 推导，
**中间没有闭合规则**：没有任何一处保证"有结果要求时，至少有一个事件类型被要求去实现它"，
也没有任何一处校验"target fact 在本章是否还可能是新知识"。
派生器可以在零告警的情况下产出一章逻辑上无解、或可满足性完全靠运气的输入。

### 4.2 矛盾的检查放错了层

契约自己字段间的矛盾，本该由 H7（契约产出时的静态一致性，零成本）拦截。
`validator.py:582-652` 的 H7.1–H7.11 **没有一条**是"`must_change` 非空 ⇒ `required_events` 至少一条能实现它"。
于是这个矛盾一路走到 **Commit 阶段**才由 H5.3 引爆——此时 Writer 的章、抽取的事件、全部 token 已经花掉了。
`must_change` 与 `required_events` 的不对账，是**契约层**的缺陷，却以**写作层**失败的样子出现。

### 4.3 失败路由表漏一条就静默走错层

`plot_engine/revision.py:38-51`：

```python
RULE_TO_LEVEL = {
    ...
    "H5.1": "contract",     # ← 只有 H5.1，没有 H5.3
}
# 注释：未列出的 rule 保守归 writer
```

H5.3 未登记 ⇒ 归 **writer** 层 ⇒ 动作 `rewrite_chapter` ⇒ 契约一字不改地重写 3 轮 ⇒ budget 耗尽、章作废。
"保守归 writer"这个默认值，对**契约类**失败是错的，而代价是整轮 token。

同一张"漏一条就静默兜底"的表还有第二处：`plot_engine/classify.py` 的 `RULE_TO_METRIC` 没有 `I9` 条目，
落到 CANON 兜底，而 08 §3 的意图是归 KNOWLEDGE——即 §6 失败分桶现在也在悄悄错分。

### 4.4 路由对了也修不好：契约层的动作只能删要求

`plot_engine/revision_actions.py:20` 的 `renegotiate_contract` 按 04 §4.3 重新派生（version+1），
但它放宽的只有 **`required_events`** 这一侧，且 Arc 强制的（D3/D6）一条不许掉——这是防"把通过标准改成模型刚好够得到"的正确设计。
问题是：H5.3 的根子在 **`must_change`**，`renegotiate_contract` 重新派生出来的新契约里 `must_change` 一模一样，
**没有"补要求"或"撤销结果要求"的出路**。
真正的出路是回 Arc 层（作者意图写错了），但 `escalate_to_arc` 在实验主循环的 actions 字典里**未注册**，
`revision.py:159` 对未注册动作直接转人工。

**所以 06 §4 设计的三级修补（writer / contract / arc）对这一类失败全部不可达**：
writer 层修不到点上，contract 层只会删另一半要求，arc 层没接线。

---

## 5. 三条修法

| | 做法 | 性质 | 代价 / 风险 |
|---|---|---|---|
| **A** | 修夹具作者意图：逐章 `must_change` 各自不同、并与 `required_events` 配对（`operation` 用 `update` 表达已建立知识的推进） | **只改数据** | 最快，但只治这一部小说，换 Arc 会复发 |
| **B** | 派生器加守卫：`must_change` 非空而 `required_events` 里没有可实现它的类型 ⇒ `raise ArcConflict`，在契约产出时（零成本）炸出来 | 生成器自保护，**我判断不算改协议**（协议从未授权派生器产出自相矛盾的契约），但需你认这条判断 | 会立刻把当前 Arc 打回，必须先做 A |
| **C** | 往 04 §4.3 补一条 D10 推导规则：结果要求必须有动作实现 | **协议变更**，按 08 I1/I2 + §7 冻结门需明确批准 | 出 Phase 0 的冻结面 |

附带该修的（独立于 A/B/C）：`RULE_TO_LEVEL` 补 `H5.3 → contract`；`RULE_TO_METRIC` 补 `I9 → KNOWLEDGE`；
`escalate_to_arc` 是否在主循环注册。

**建议：A + B 现在做，C 写进 Phase 0 报告的 backlog。**
理由：这个 bug 的性质是"派生器产出了逻辑上不满足的输入"，B 是它的正确归属（快速失败、零成本、可解释）；
A 是让当前测量真的能测到模型而不是测到自己的噪声。C 是把它上升成协议承诺，那是 Phase 1 的决定，
不该在 Phase 0 测量中途悄悄做。

---

## 6. 与已修问题的关系（别混淆）

上一个已修复的根因（commit `66f87e2`）是**一致性闸拿错事件集**：增量 reduce 用"本批事件"当已提交集，
导致第 1 章 ledger 留下的 source 指针从第 2 章起永远"指向批外"，整条故事被 I9 判死。
那个 bug 表现为 `consistency_hard=n` 且**一个 rule_id 都没有**。

本文的 H5.3 是**另一个** bug：契约层。两者共同的模式是——**引擎在自己制造失败，然后把它算成模型的失败**。
`66f87e2` 修的 `CommitOutcome.consistency` 让被拒章的不变量违规带着 code 进 §6 桶和逐章 dump，
这就是本文能拿到 ch06/ch07 原始证据的原因。

---

## 7. 决策待定

A / B / C 选哪几条 —— 未定，**在选定之前不动任何引擎代码**。
采样继续按冻结的 `66f87e2` 跑（第 2 次进行中），三次并列结果写进 `docs/phase0-live-run-10ch.md`，
本文作为该 backlog 项的详细附件。
