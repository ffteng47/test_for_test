# 对 `docs/phase0-v2-review-consolidated.md` 的逐条核验

审查稿入库为 `docs/phase0-v2-review-consolidated.md`（原样，不改写）。本文只记核验结果与更正，
每条都给出可复核的代码/快照坐标。核验范围是审查稿**新增**的内容（§5 结论、§6 finding-1/2/3、§7 backlog、§8 附录）；
§1–§4 与 `docs/phase0-v2-samples.md` 的读数逐条对过，无差异。

## 结论一览

| 审查稿断言 | 裁定 |
|---|---|
| finding-1（E3 假降级 N/A） | **成立**，且影响面比文中更大（同一判据在两处） |
| finding-2（`experiment_id` 恒为 `exp-s1-42`） | **成立** |
| finding-3（must_change 系结构性烧预算） | **方向成立，机制写错一半** |
| 「ch07 9 次尝试从未产出 belief 事件」 | **不成立** —— 产出了，但目标 fact 错 |
| §5 结论 1「E2 阈值 90%」 | **不成立** —— E2 是 70%，90% 属 E5/E3 |
| rounds 计数口径「致命那步不计入」 | **成立**，机制可精确到行 |
| 附录 A「`rewrite_scene` ≡ `rewrite_chapter` 同一 lambda」 | **成立**，行号应为 `review.py:279-280`（live）与 `163-164`（offline），不是 245 |

## 1. finding-1 的修法位置只有一处，且必须同时救 E3

审查稿把 finding-1 定位在 `review.py:87`。实际上**同一个判据在引擎里出现了两次**：

- `review.py:87` `revision_ran = len(report.revision_rounds) == chapters_generated` → 渲染成「未运行」；
- `experiment.py:194` `if len(rounds) == gen and gen:` → E3 直接算成 `None`，连「False」都不给。

⇒ 逐章快照记录才是根因，两处消费者都跟着好。中途判死的章在 `experiment.py:108-113` 抛异常后
**trace 随异常丢失**（`run_chapter` 没把 trace 挂到异常上），但 `captured` 已带着每一轮 recom
mit 的记录 ⇒ 修法是一行：`rounds_by_chapter[ch] = max(len(captured) - 1, 0)`。
`-1` 是第 0 轮（首次提交尝试），与快照头部 `rounds=len(rounds)-1` 同口径。

## 2. ch07 稳定失败的真正归因：belief 事件写了，但写在了错的 fact 上

审查稿说「9 次尝试从未产出 belief 事件」。逐章快照的最终轮 Proposals 三次都有 belief 类事件：

| 样本 | 最终轮 belief 事件 | 契约要求的 belief Δ |
|---|---|---|
| s1 | `SUSPECTS fact_000001`（Round 0 产出，最终轮只剩 OBSERVES/INFERS） | `char_000001.belief` `add` **fact_000004** → suspects |
| s2 | `BELIEVES fact_000001 belief_strength=85` | 同上 |
| s3 | `BELIEVES fact_000001 belief_strength=5` | 同上 |

目标 fact 来自夹具逐章意图第 7 步（`experiment_10ch.py:93-94`：
`events=[_belief("SUSPECTS", _F4, 500)]`，`must_change=[_holds("add", _F4, "suspects")]`，`_F4 = fact_000004`）。

⇒ **H5.3 三次都判对了**，模型三次都把 belief 写在了 `fact_000001` 上。这把审查稿 backlog #7 的
ch07 部分答掉一半：不是「模型写不出 belief」，而是「belief 的对象不跟着契约走」。
也顺带把 backlog #5 从「待查」变成「已查到」：`llm_writer.py:37-51` 的 writer 提示词只渲染
场景目的、节拍 `intent` 文本和「可以使用的事实」清单，**既没有 `required_events` 的
`expected_event_types`，也没有 `must_change` 的 target/expected_value**。模型能看见 F1 也能看见
F4（都在允许清单里），没有任何东西告诉它本章要在 F4 上发生 belief 跃迁。

注意分寸：这是**归因证据**，不是「加进提示词就能修」的承诺——把 must_change 渲染进提示词属于
Writer 侧协议变更，会改变度量对象，必须走新一轮冻结。

## 3. finding-3：无效预算烧在两个不同动作上

「ladder 会一遍遍 renegotiate 烧满预算」只在失败集合含契约层规则时成立。实测分裂：

| 章 | 三次 `contract_version` / rounds | 实际烧的动作 |
|---|---|---|
| ch07（H5.3 + 常伴 H5.1） | 4/3、4/3、4/3 | 全是 `renegotiate_contract`（共 9 次），重议只动 `required_events` 轴，`must_change` 逐字保留 ⇒ 成功概率恒为 0，审查稿这半是对的 |
| ch10（H2.2 系） | 3/2、**1/3**、**1/3** | s2/s3 的 v 恒为 1 ⇒ 三轮**一次 renegotiate 都没有**，烧的是 writer 层重写（`rewrite_scene`/`rewrite_chapter` 同一 lambda，重写后还是同一条 not-observed F2） |

⇒ backlog #1 的表述要改成「must_change 系失败无论路由到哪一级都没有有效动作：契约层重议碰不到 `must_change` 轴，writer 层重写改变不了抽取没产出的事件」，
终止策略要按路由分档，不是只给 `renegotiate_contract` 加闸。

## 4. E2 阈值与鲁棒性（审查稿 §5 结论 1 需按此改写）

`experiment.py:184` `e2 = commit_rate >= 0.70`；0.90 属 E5（:189）与 E3（:195）。
差值不是「足够大」而是：s1 提交 6/10 = 60%，**多成一章就是 7/10 = 70% ⇒ E2 翻真**。
所以「E2 三次同判 False」在 s1 那一侧只有一章的裕度，鲁棒性结论应限定为：
s2（40%）、s3（30%）远离阈值；s1（60%）距阈值一章。三次都不放行，但「判定对采样方差鲁棒」这句不能整段保留。

## 5. rounds 计数口径（成立，精确到行）

`revision.py:153-173`：只有**成功执行完的一轮**才 `trace.rounds += 1` 并落 `steps`；
`renegotiate_contract` 在执行中 raise 时该轮不落账。配合 §1 的 `len(captured)-1`，
两个 ARC_CONFLICT 形态自洽：`v1/r0` = 第一次重议就撞死（s1 ch05、s2/s3 ch01，撞的是 Arc 强制 `INFERS`）；
`v2/r1` = 先成功重议一轮、下一轮撞死（s2 ch09、s3 ch09）。

## 6. backlog 的落点调整

| # | 审查稿 | 核验后 |
|---|---|---|
| 1 | must_change 系归因与终止策略 | 保留，按本文 §3 改写机制描述 |
| 2 | `rewrite_scene` ≡ `rewrite_chapter` | 保留（行号更正为 `review.py:279-280`） |
| 3 | H8.x 九桶归类待 08 §4 裁定 | 保留 |
| 4 | finding-1 / finding-2 修复 | 保留，修法按本文 §1 收敛成一行 |
| 5 | writer 提示词是否渲染 required_events / turning point | **已核完**：都没渲染（`llm_writer.py:37-51`）。转为「是否要改 Writer 协议」的拍板项 |
| 6 | ch07 belief Δ 定性 | 按本文 §2 定性为「契约目标 fact 未进入 Writer 视野」，属夹具方法论 + Writer 接线，不是模型弱项 |
| 7 | 稳定失败核三层归因 | **已答完**，见本文 §7 |
| 8 | seed / 低温度对照轮、qwen3/deepseek-r1:32b 对照轮 | 保留 |

## 7. 三个稳定失败章的三层归因（读最终轮 Proposals 得出）

| 章 | 契约要求 | 三次最终轮实际产出 | 判定 |
|---|---|---|---|
| ch02 | knowledge Δ：F1 → `known`（实现者须为 OBSERVES/READS/IS_TOLD/INFERS） | s1 `BELIEVES F1`；s2/s3 `INFERS F3（evidence 含 F1）`+`OBSERVES F3`。三次都**没有任何以 F1 为对象的知识事件** | H5.3 三次都报 ⇒ **Writer/抽取层**：模型对 F1 写「相信」或「拿它当证据」，而不是「获知」 |
| ch07 | belief Δ：F4 → suspects | s1 `SUSPECTS F1`（仅 Round 0）；s2 `BELIEVES F1 85`；s3 `BELIEVES F1 5` | 事件类型对、**目标 fact 错** ⇒ 同 ch02 的 field 混淆换个方向：模型认定 F1 是本章的心理对象 |
| ch10 | knowledge Δ：F2 → `known`（夹具配的 `OBSERVES F2`） | 三次都有 `INFERS F2`，三次都**没有** `OBSERVES F2` | H5.3 不报、只报 H2.2/H5.6 ⇒ **rank 上限问题**：INFERS 只能到 suspected，契约要 known。抽取没错，Writer 少了一次直接观察 |

三条合起来指向同一个上游：模型没有被告知「哪条 fact 的哪个 field 要在本章发生跃迁」（`llm_writer.py:37-51`），
于是 F1/F3/F4 这些「允许清单里的事实」被自由组合，field 与 rank 全靠采样运气。
**这把抖动的来源也解释了**：ch01/03/05/06/09 的成败取决于那一轮有没有恰好写对对象。
是否把 `required_events` / `must_change` 渲染进 Writer 提示词 = Writer 协议变更，需重新冻结并重采三次，不能当成 finding 的顺手修补。
