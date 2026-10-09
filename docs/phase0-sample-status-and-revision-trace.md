# 采样状态 & ch06/07 修订轨迹核查（2026-10-09）

本文回答两件事：① 第 2 次采样到底什么状态；② ch06/07 的修订 steps 实际烧了几轮。
配套：`docs/phase0-h53-spec-qa.md`（协议裁定）、`docs/phase0-h53-contract-infeasibility.md`（问题报告 v1）。

**结论先说**：第 2 次采样已中断，不在跑、也没有报告。
ch06/07 的**实际 revision trace 没有被持久化**，我从代码把它确定性地推了出来；
并且要更正你的那条推断——**dump 里的 `contract_version=1` 不能证明 renegotiate 没跑过**，
因为 dump 打印的是**修订前**的 ctx。这本身是个取证缺陷，得在新冻结面之前补掉。

---

## 1. 第 2 次采样状态：**已中断在第 4 章，无报告**

核查方式与结果：

```
$ tasklist //FI "IMAGENAME eq python.exe"
信息: 没有运行的任务匹配指定标准。        ← 系统内已无 python 进程

$ ls $TEMP/phase0-fix-2
ch01.md  ch02.md  ch03.md  ch04.md  live.log

$ wc -l $TEMP/phase0-fix-2/live.log
0                                            ← 报告为空
```

⇒ 状态 = **跑到第 4 章时进程消失**（最可能是承载它的后台 shell 随会话中断被一并终止；
真实原因未查，我没有留 stderr）。**既不是"未开跑"，也不是"在跑"。**

### 按你给的规则处置

| 规则 | 处置 |
|---|---|
| 已在跑就跑完这次 | **不适用**：它已经死了，不是"在跑"。跑完的那一半只有 ch01–ch04，且**无报告**（08 §3 的报告字段全部缺失）→ 这份残缺数据补不出一次有效采样 |
| 不要再跑第 3 次 | **执行**：第 3 次不跑 |
| 旧数据只作对照 | **执行**：第 1 次 `phase0-fix-1`（完整）+ 第 2 次残缺的 ch01–ch04，一律标为**旧尺对照**，不进结论 |
| 修完后在新冻结面上跑完整三采样 | **待你批准修复项**（见 §4）后执行 |

⇒ **当前手上只有 1 份完整采样数据，且它是在一把两个方向都偏离协议的尺上读的（见 QA 文档 Q3）。三次一致性尚无数据。**

---

## 2. ch06/07 的实际修订轨迹：数据**没落盘**，但可从代码确定性重建

### 2.1 先更正一条推断

> 你的推断：「dump 里 `contract_version=1` 说明 renegotiate 没跑过」

**这个推断不成立。** `experiment.py:87` 传给 dump 回调的是**第 76 行新建的那个原始 ctx**，
不是 `run_chapter` 返回的修订后 ctx：

```python
ctx = ChapterContext(contract=art.contract, scene_plan=art.scene_plan, draft=draft, state=cur)  # :76
if revision_loop is None:
    out = recommit(ctx)
else:
    trace, out = revision_loop.run_chapter(story, ch, ctx, recommit)   # :81  修订发生在循环内部
    rounds_by_chapter[ch] = trace.rounds                               # :82  ← 只有轮数被留下
if on_chapter is not None:
    on_chapter(ch, ctx, list(captured["props"]), out)                  # :87  ← 传的是原始 ctx
```

⇒ **dump 里的 `contract_version` / `required_events` / Draft 全部是"第 0 轮"（修订前）的值**，
无论 renegotiate 有没有跑，它们都会显示 1。

### 2.2 更糟的一点：Draft 与 Proposals 不是同一轮

`recommit` 每次重抽都覆盖同一份捕获：

```python
def recommit(ctx):
    props = stage0_extract(ctx.draft, ...)
    captured["props"] = props        # :69  每轮覆盖 → 最终留下的是**最后一轮**的抽取
```

⇒ dump 是**混合体**：`Draft` / `contract_version` 来自第 0 轮，`Proposals` 来自最后一轮。
影响面要说清：

- **不影响**我的 5/10 结论：那张覆盖表读的是 Proposals，而最终 `out` 的判定也正是对同一批 Proposals 做的，两者一致。
- **影响**我引用的那段正文：`ch06.md` 里贴的 Draft 可能**不是**产生那批 Proposals 的那一稿。
  所以"正文完全围绕印章伪造、看不出该判死的理由"这句，**证据强度要降一档**——它评的可能是修订前那一稿。
  这个措辞我在 QA/问题报告里没有加限定，需要在下次采样后重写。

### 2.3 确定性重建（代码路径唯一，无自由度）

以 `ch06` 为例，唯一 HARD = `H5.3`。逐步走 `revision.py`：

| 步 | 代码 | 结果 |
|---|---|---|
| 归因 | `RULE_TO_LEVEL` 无 `H5.3`（`:38-51`）→ `level = mapped or "writer"`，`confidence=500`（`:81`） | **writer 层、低置信** |
| 动作 | `_LEVEL_TO_ACTION["writer"] = "rewrite_scene"`（`:60`）；`action_for` 要求它在 `policy.escalation` 里（`:87-90`） | **round 1 = `rewrite_scene`** |
| 轮 2 | 违规集合不变 `{H5.3}` → `is_oscillating(prev,cur)`（`:103`）→ `_ladder_next("rewrite_scene")`（`:120-127`，只看 `self.actions` 里有的） | **round 2 = `rewrite_chapter`** |
| 轮 3 | 再次振荡 → `_ladder_next("rewrite_chapter")` → `renegotiate_contract`（**它在 actions 里**，`review.py:246`） | **round 3 = `renegotiate_contract`** |
| 触顶 | `trace.rounds >= min(max_rounds=3, human_escalation_threshold=3)`（`models/revision.py:26,32`；`revision.py:176-179`） | **FAIL + `needs_human=True`** |

⇒ **ch06/ch07 各烧 3 轮**（与第 1 次报告里的「最多 3 轮 / 需修 6 章 / 修复率 0.67 = 4/6」自洽：
6 章需修，ch06/07 两章 3 轮触顶未救回，另 4 章在 1–2 轮内修成）。

### 2.4 但 renegotiate **跑了也没用**——这正是路由修复的验证点

`renegotiate_contract` 会 `version+1` 重新派生（`revision_actions.py:31-33`），
而 `must_change` 是逐字拷贝回来的（`derive.py:183`）⇒ **新契约与旧契约在 `must_change` 轴上完全相同**，
round 3 之后 H5.3 必然复现。也就是说：

- 你的路由推断方向对（H5.3 兜底归 writer），**但结论要改**：不是"rewrite 三轮"，
  而是「**rewrite_scene → rewrite_chapter → renegotiate_contract**，三轮三种动作，全部无效」。
- **而且 ladder 的前两级在主循环里是同一个函数**——`review.py:245`：

```python
"rewrite_scene": rewrite, "rewrite_chapter": rewrite,   # ← 同一个 lambda
```

⇒ round 1 和 round 2 是**字面意义上的同一次重投**（同一 state、同一 contract、同一 plan，只差模型采样的随机性）。
所谓"升级到下一级"在前两级是名义的。

### 2.5 成本口径（不完整，标出来）

我没有每章 token 记账（`total_tokens` 只在报告级），所以无法给出 ch06/07 各自的 token 数。
可确定的是**调用次数**：每章基数 = 1 次 Writer + 1 次抽取；这三轮里
round1/round2 各 = 1 次 Writer + 1 次抽取，round3 = 1 次抽取（草稿未变）。
⇒ **ch06、ch07 各多烧 2 次 Writer + 3 次抽取**，两章合计 **4 Writer + 6 抽取** 的纯浪费。
全章均值参考：第 1 次 55308 tokens / 10 章 ≈ 5.5k/章（含浪费）。

---

## 3. 为什么这些拿不到：08 要求的取证没落盘

- **08 §3**：`revision_rounds: Dict[int,int]  # 每章 revision 轮数`
  ——代码**算出来了**（`experiment.py:134`），但渲染时只用了聚合值
  （`review.py:79-82`：`revision_chapters_needed` / `revision_max_rounds` / `revision_ran`），
  **逐章轮数从未打印**。
- **08 I4**：「所有 Commit 必须落 trace」——`RevisionTrace`（含 `steps[]`：round_no / root_cause / action /
  violations / committed）在 `run_chapter` 里构造完整，但主循环只留 `trace.rounds` 一个整数
  （`experiment.py:82`），**`trace.steps` 当场丢弃**。
- **08 §10 I3**：所有 failure 必须记录——`_write_chapter_dump` 记了，但记的是修订前的 ctx（§2.1/2.2）。

⇒ 你要的"实际 steps"在现有 artifact 里**不存在**，只能靠代码重建（§2.3）。
重建是确定性的、可信的，但它是**推理**，不是**测量**。路由修复要拿测量作验证证据，就得先把取证补上。

---

## 4. 建议补的三项（全部在**报告/取证面**，不触碰任何 HARD 判据）

1. **逐章渲染 `revision_rounds`**：报告里按章打印 `ch: rounds`，与 08 §3 字段一致。
2. **逐章落 `trace.steps`**：dump 里新增 `## Revision` 段，每轮一行
   `round_no / level / rule_ids / action / committed`。这是路由修复（`RULE_TO_LEVEL[H5.3]`）**唯一的可验证形式**。
3. **dump 打印最终 ctx，并标明轮次**：`contract_version` / Draft / Proposals 必须来自**同一轮**；
   原始第 0 轮另起一段保留（区分「Writer 没写出」与「抽取漏掉」仍需第 0 轮）。

这三项做完，才谈得上"新冻结面上跑完整三采样"——否则三次采样给的仍然是只能看聚合数的黑盒。

---

## 5. 待批准（与 QA 文档的三条并列，不重复）

1. 是否批准 §4 三项取证补齐（作为新冻结面的前置）。
2. 路由修复是否与新冻结面一起做：`RULE_TO_LEVEL` 补 `H5.3 → contract`；
   以及要不要顺手让 `rewrite_scene` / `rewrite_chapter` 在主循环里**真的不同**（现在同函数）。
3. QA 文档那三条：A + `_KNOWLEDGE_ESTABLISH` 分表是否现在做、B 做不做。

采样在此之前不重启——按你给的规则，旧数据只作对照，新三采样必须跑在批准后的冻结面上。
