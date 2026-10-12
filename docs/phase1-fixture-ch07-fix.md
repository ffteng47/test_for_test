# 夹具修复：ch07 的信念阶梯从 F4 改回 F1（E14，ladder-v2）

状态：**已落码，ladder-v2 重基线 ×3 全部跑完**。跑后裁定见 §8——
本文 §2 的戏剧论证站得住，但它原来那句「代价是每一臂都交税」的**实测前提被推翻了**（E17），
改动因此从「修缺陷」降为「夹具卫生 + 没有可测效果」；ch07 真正的漏点在抽取与修订指引面（E18）。
一句话：第 7 章要求主角「怀疑 `fact_000004`」，而第 6 章他刚**读实**了这个事实 —— 这不是模型的错，
是夹具写了一出戏剧上不成立的戏。当时以为它的代价是**七个同端点跑法全在这一章交处置税**，
那个读数只覆盖了同端点一族，旧夹具全库里有 2 个跑法首过（见 E17）。

## 1. 逐行 diff

```diff
--- a/plot_engine/tests/fixtures/experiment_10ch.py
+++ b/plot_engine/tests/fixtures/experiment_10ch.py
@@ -34,4 +34,8 @@
 EPOCH = "epoch_0"
 NOW = "2026-10-09T00:00:00Z"
+# 阶梯版本进 run.log 第 1 行（与抽取尺戳同处）：**改 `_STEPS` 任意一项必须同时 bump 这里**。
+# 没有这一行，新旧基线并列时「这一跑跑在哪版夹具上」只能靠 commit 时间倒推（docs/measurement-errata.md §四）。
+# 戳进日志之前（含 v32r1–3、bo_* 、q3_14b_r* 、q25_11500_r*）的所有跑法一律是 ladder-v1。
+LADDER_VERSION = "ladder-v2-f1-belief-arc"
@@ -91,6 +95,10 @@
     {"events": [_infers(_F4, [_F1])], "must_change": [_knows("add", _F4, "suspected")]},
     {"events": [_reads(_F4)], "must_change": [_knows("update", _F4, "known")]},
-    {"events": [_belief("SUSPECTS", _F4, 500)],
-     "must_change": [_holds("add", _F4, "suspects")]},
+    # ch07：信念阶梯续在 F1 上（believes ch03 → doubts ch04 → suspects ch07）。
+    # 原先钉在 F4（E14）：ch06 刚用 READS 把 F4 升到 known，「怀疑一个自己刚读实的事实」
+    # 在戏剧上不成立 ⇒ 七个同端点跑法全在这里不通过（ch07 无一首轮），每臂白吃一章处置税。
+    # rank doubts(0) < suspects(1)，SUSPECTS 是升级不是降级（`reducers/belief.py:15,54-57`）。
+    {"events": [_belief("SUSPECTS", _F1, 500)],
+     "must_change": [_holds("update", _F1, "suspects")]},
     {"events": [_obs(_F3)], "must_change": []},          # 本章不推进：合法形态
```

```diff
--- a/plot_engine/review.py   (:365)
-    note = f"{msg}｜prompt={prompt_version(arm)}｜抽取尺={EXTRACTION_RULER}"
+    note = f"{msg}｜prompt={prompt_version(arm)}｜抽取尺={EXTRACTION_RULER}｜夹具={fx.LADDER_VERSION}"
```

```diff
--- a/plot_engine/tests/test_fixture_audit.py
+def test_ladder_pairs_every_must_change_with_a_same_fact_event():
+    """H5.3 的兑现前提：本章必须要求一个**同 field、同对象**的实现事件。…"""
+    for step in fx._STEPS:
+        for ch in step["must_change"]:
+            implementers = FIELD_EVENT_TYPES.get(ch["field"], set())   # 与 validator:500 同源，不用并集
+            assert any(e["event_type"] in implementers and e.get("fact") == ch["target"]
+                       for e in step["events"])
```

审查助手的第一轮里这条用的是 `knowledge ∪ belief` 并集，于是「`field=knowledge` 而本章只有
`BELIEVES` 事件」这种 **field 写串**能过审计、模型却怎么写都过不了 H5.3 ⇒ 已收紧为按 field 查表，
与 `validator._change_implemented` 同源。变异复核：field 写串现在**被抓到**，当前夹具 10 步全部通过。

## 2. 为什么 F1 是合法目标（不是把缺陷挪个位置）

四条都得成立，逐条对着代码核过：

1. **reducer 合法**：`_STATE_RANK = {"doubts":0, "suspects":1, "believes":2}`（`reducers/belief.py:15`），
   `SUSPECTS` 走 `_upsert(..., allow_downgrade=False)`（:54）。F1 在 ch04 被 `DOUBTS` 写成 `doubts`，
   ch07 要 `suspects`：**0→1 是升级**，`upgrade` 分支直接放行，不需要降级通道。
   改到 F4 上反而是 `known`（knowledge ledger）与 belief ledger 的跨面戏剧矛盾，reducer 判不了正文。
2. **H5.3 可兑现**：`validator.py:494-516` 的 `_change_implemented` 只看三件事 ——
   `event_type ∈ FIELD_EVENT_TYPES[field]`、`_referenced_fact(ev) == ch.target`、`ev.actor == ch.character_id`。
   本章事件 `SUSPECTS fact_000001` 与 `must_change.target` 同对象，actor 这一项**不由本次改动决定**：
   夹具全程单主角（`_ACTOR = char_000001`，:133 的 `actors_involved`、:172 的默认 actor 都是它），
   换 F4→F1 只换 target，不换 actor 条件。
3. **不越 Arc 面**：`_TURNS` 只挂第 1/5/9 步，ch07 不在 Arc 强制事件类型集合里，
   所以这次改动**不触碰 `required_event_types`** —— 那是 ch09 的战场，还押在裁定上。
4. **阶梯不断链**：F1 原本的信念轨迹 ch03 `BELIEVES`(believes) → ch04 `DOUBTS`(doubts) → ch07 `SUSPECTS`(suspects)
   是「先信、再疑、再生疑」的三段式，比原来 F1 在 ch04 之后信念列就断掉更完整。

**`operation` 从 `add` 改成 `update`**：全仓库只有两个消费者 ——
`validator.py:407` 的 H2.2 **只在 `field == "knowledge"` 时读**它， belief 侧不进这个分支；
`llm_writer.py:80` 把它原样拼进提示词。所以 `update` 是**正确的措辞**（F1 的信念条目 ch03 就存在，不是新建），
代价是 ch07 的提示词文本变了（见 §4）。

## 3. 等价性：除了 ch07，契约一个字节没动

离线装配跑过（不调模型），核对结果：

| 项 | 改前 | 改后 |
|---|---|---|
| ch07 `required_events` | `[('SUSPECTS','fact_000004')]` | `[('SUSPECTS','fact_000001')]` |
| ch07 `must_change` | `belief/fact_000004/add/suspects` | `belief/fact_000001/update/suspects` |
| ch01–ch06、ch08–ch10 | — | **逐字节相同** |
| turning points | `[(1,['INFERS','OBSERVES']),(5,['INFERS']),(9,['BELIEVES','INFERS','OBSERVES'])]` | 相同 |
| `knowledge_gates` | `[(F1,1),(F3,1),(F4,5),(F2,10)]` | 相同 |
| 章数 / 事件类型预算 / 闸门章号 | — | 相同 |

测试：`PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest plot_engine -q` → **462 passed**。
新那条不变式（同章同对象配对）在当前夹具上是**通过**的，它防的是下一次把目标 id 写串 ——
那种章模型无论怎么写都过不了。它**抓不到本次的 E14**（错在对象选得不合戏剧逻辑，不在配对），
文档里明说，别让后人以为这条测试是 E14 的防线。真正的防线是 E14 那条纪律：
**某一章在每一条臂上都不是首轮通过 ⇒ 先归夹具，不归模型**（`docs/measurement-errata.md` E14）。

## 4. 哪些历史读数作废 / 怎么标

- **ch07 的所有历史读数**（含 `sampling/bo_*`、`q3_14b_r*`、`q25_11500_r*`、v32r1–3 的 ch07 那一格）
  都是 **ladder-v1** 的读数，且它的提示词文本已经变了 ⇒ **不可跨版本比较**。旧文档不做追溯修改，
  重基线表另起一节，标题带 `ladder-v2`。
- **`修订环归属章` 与 `夹具硬伤占比` 两列**：这两列是读 dump 里的规则命中算出来的，
  ch07 的输入变了 ⇒ v1/v2 不可并列成同一指标。旧值保留原样，新表重新起算。
- **E2 / 处置率的分母、分子定义不变**（还是「生成章」和九桶），变的只是 ch07 这一章的期望。
- **run.log 第 1 行**：改动之前的日志里没有 `夹具=` 字段 ⇒ 一律按 `ladder-v1` 读，
  `readout` 不用改，戳是人读的。

## 5. 修复前的证据面与可证伪预测

`readout --matrix` 在**七个同端点跑法**（`bo_ctrl` + `q25_11500_r1–3` = `qwen2.5:14b`，
`q3_14b_r1–3` = `qwen3:14b`，皆 @11500）上读到的逐章终态，未做任何追溯修改：

| 跑法 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| bo_ctrl | 首 | 处 | 首 | 首 | 首 | 处 | **处** | 首 | 处✗ | 处 |
| q25_11500_r1 | 首 | 首 | 首 | 首 | 首 | 处 | **处** | 首 | 处 | 处 |
| q25_11500_r2 | 首 | 首 | 首 | 首 | 处✗ | 首 | **处** | 首 | 处✗ | 救 |
| q25_11500_r3 | 首 | 救 | 首 | 首 | 处✗ | 处 | **处** | 首 | 处✗ | 处 |
| q3_14b_r1 | 处✗ | 首 | 处 | 首 | 首 | 处 | **处** | 首 | 处✗ | 救 |
| q3_14b_r2 | 处✗ | 首 | 首 | 首 | 首 | 处 | **处** | 首 | 处✗ | 处 |
| q3_14b_r3 | 首 | 首 | 首 | 首 | 首 | 首 | **处** | 首 | 处 | 首 |

这张表里 ch07 是**唯一跨模型、跨臂、7/7 都不首轮**的一列，而 ch04 有 7/7 首轮 ——
两者形式同类（都是「对已 `known` 的事实动信念」），差别只在 ch07 的对象刚被**本章主角自己读实**。
这既立起 E14 的纪律，也说明为什么不能把它做成机检谓词。
**但「这张表」只有同端点一族**：旧夹具全库 21 个跑法里 ch07 有 4 个 OK，其中 `t8r1`、`v32r1`
是 `contract_version=1 rounds=0` 首轮通过 ⇒ 「跨臂必失败」这条纪律的前提被推翻，见勘误账 E17。
（ch09 的 7/7 无一首轮里只有 5 次是 `ARC_CONFLICT`，且轮数不是常数：`bo_ctrl` 那跑重议过一次
   （`contract_version=2 rounds=1`）仍判死 —— 见 `docs/measurement-errata.md` E15；机制与 ch05 同族，见 §5 预测 2。）

跑完重基线拿这三条对答案：

1. **ch07 不再在每条臂上都不是首轮通过。** ⇒ **这条已被推翻了两次**：
   (a) 前提就错了——旧夹具下 `t8r1`、`v32r1` 的 ch07 是 `rounds=0` **首轮通过**（E17，我当时只查了同端点一族）；
   (b) 实测也没兑现——v2 ×3 的 ch07 是 处/首/处，1/3 首轮 vs v1 的 0/7，Fisher **p≈0.39**，
   而 E2 均值 56.7% 对 v1 的 60.0%，两臂自身极差都 20pp ⇒ **按判据不可判，读不出改动的影响**。
2. 主力臂的 E2 **理论**天花板从 ~80% 抬到 ~90%，但这一格隐含「ch05 必过」，而压住它的机制没裁：
   ch05 的 `required_events` 恰也只剩 `['INFERS']`，v1 里 **2/7 判死**（`q25_11500_r2`、`r3`，
   `version=1 rounds=0`）——与 ch09 同族。所以读法应当是「未裁机制压 **ch05 + ch09** 两章，
   90% 是 ch05 走运、ch09 仍死的上界；80% 是两章都死的下界」。
   **实测**：v2 ×3 最好的 r3 = 70%（ch05 三跑全过、ch09 一过两死），天花板没被推到 90%。
3. `修订环归属` 列里 ch07 应当消失（v1 的 `bo_ctrl`、`q25_11500_r1`、`q3_14b_r1/r2/r3` 都点了它）。
   注意这一条不能读成「占比必然下降」：`q25_11500_r2` 的 ch07 也是处、但那一列是空的，
   说明同一章的失败在 v1 里就有 H5.3 主导与非 H5.3 两种形状 ⇒ **`E2` 才是主指标，那一列只是归因辅助。**

预测 2 只在「同端点、同模型、×3 一致」时才有资格读；极差 >10pp 的话按一致性铁律作废，只报方差。

## 6. 请审的四个问题

1. `operation: "update"`（我选）还是 `"add"`？我的依据是 F1 的信念条目在 ch03 已存在；它不进 H2.2 分支，
   所以这只是提示词措辞问题，但措辞会进模型上下文。
2. `belief_strength=500` 保留不变（与 ch04 的 `DOUBTS` 同值）。同值意味着「生疑的强度 = 当初怀疑的强度」，
   要不要给 ch07 一个更高的数（比如 700）让阶梯有推进感？我倾向**不动**， strength 没有任何规则读它。
3. F4 的 belief 列覆盖面：改完后 F4 只剩 knowledge ledger 的两次跃迁（ch05 suspected → ch06 known），
   它作为「信念对象」的那条不再存在。我的立场是**没有损失** —— 原来那条从没被任何规则判过对错，
   它的唯一作用是让 ch07 变成一个稳定的失败点。
4. 这次改动需不需要单独走「输入面变更」裁定？它只动 `_STEPS[6]`，不动 reducer、validator、判据文本；
   我按实现对齐处理，但 E2 的读数确实会变，值得你确认这个定性。

## 7. 明确未做

- **ch09 没碰，ch05 也没碰**：两章的失败机制同为 Arc 强制 `INFERS` 单一事件类型预算
  （ch09 五判死于七跑、ch05 两判死），`required_event_types` 等值类 INFERS ∪ SUSPECTS 能不能换是
  判据输入面的改动，需要单独裁定，不夹在这次修复里。等这条裁定，不等本文件。
- **没有跑 ×3**，`--rescue` 那条线也没动。等你和审查助手放行后，重基线只跑
  `qwen2.5:14b` @11500 ×3（串行，约 18 分钟），标 `ladder-v2`，与 round-2 的表**并列不替代**。
- **derive 期 id 检查**已撤回（反例：ch04 对 `known` 的 F1 要 `DOUBTS`，形式同类却七跑全首轮通过
  ⇒ 没有可机检的谓词），E14 的防线是纪律不是代码。
- `H8.1/H8.2` 不在 `RULE_TO_METRIC`、`rewrite_scene` 名义阶梯、08 §4 的 extraction 桶归类：仍挂 backlog。

## 8. 跑后裁定（ladder-v2 ×3，2026-10-12）

读数、判据结论与新归因在 **`docs/phase1-baseline-ladder-v2.md`**，这里只记对本文件的三处更正：

1. **保留改动，但降级定性**：从「修掉一章处置税」改成「夹具卫生 + 没有可测效果」。
   回退条件（§5 预测 1）在字面上触发了，但触发它的**前提**被 E17 证伪，
   且改动没有坏效果（E2 差在噪声内、ch07 首轮 0/7→1/3 方向为正）⇒ **不回退**。
2. **§2 第 1 条的戏剧论证仍然成立，但它不是失败的原因**。ch07 真正的卡点是
   `H5.1 必需事件 SUSPECTS 数量不足（0<1）`——正文写了「他开始怀疑守阁的人…」，
   抽取器只吐 `OBSERVES`/`INFERS`，一条 belief 族事件都没有（ladder2_r1 实读）。
3. **两处尺面文本洞**（E18）：`FIX_GUIDE["H5.1"]`（`review.py:182-184`）解释了六个类型怎么写，
   独缺 SUSPECTS；抽取提示词（`llm_extract.py:224-251`）给三兄弟裸类型名、无可区分判据。
   修它们属**协议变更**，要新的尺戳（v3.3），不能记在 ladder-v2 的账上。
