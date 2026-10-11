# Phase 1 T8 变体组：候选形态 C @ deepseek-r1:32b（×3，pre-freeze）

> 用途只有一个：回答 A1 悬着的「14b 是不是绑定项」——C-vs-B 的形态结论是不是换台更强模型就会翻盘。
> **本档不与 v3 跨比**：相对冻结轮动了两个变量（模型 + writer/extract `max_tokens` 800→2000，
> 因为 r1 的思考 token 与正文共用预算、`reasoning_effort:"none"` 与 `think:false` 在 ollama 0.40.2 上
> 都关不掉思考）。凭据见 `phase1-v3.1-freeze.md` §6。

## 1. 凭据

```
python -m plot_engine.review --live --chapters 10 --prompt persona \
    --model-config @router_r1_32b.json --state-dir sampling/t8rN/state --dump-dir sampling/t8rN/dump
```

- 端点：服务端 Ollama（隧道 `127.0.0.1:11500`），`/v1/models` 每轮自检都在架 `deepseek-r1:32b`。
- 配置：`router_r1_32b.json` sha12 `d76ce5d6a2e4`；`temperature=200` 是定点 ×1000（线上 0.2），
  与冻结轮 extract 逐字相同；`timeout_s=600`、章节数 10、臂 `persona`（=v1-told+persona）三条与冻结轮一致。
- 三轮独立 `--state-dir`（同一目录再跑一批会被拒，两批不并成一条账）。

| | 轮 1 | 轮 2 | 轮 3 | 合计 |
|---|---|---|---|---|
| tokens | 98 382 | 93 162 | 103 569 | 295 113 |
| 墙钟 | 4458s | 4033s | 4366s | 12 857s ≈ 3.6h |
| 抽取提案 / 坏料 | 145 / 4 | 132 / 10 | 186 / 7 | 463 / 21 |

坏料构成：`missing_payload_keys` 15、`id_value_not_id` 4、`malformed_reply` 2。

## 2. 读数（`python -m plot_engine.metrics <dump_dir>`，§7 新尺口径）

| 读数 | 轮 1 | 轮 2 | 轮 3 | 三份均值 |
|---|---|---|---|---|
| 终态 OK / ARC / NEEDS_HUMAN | 5 / 3 / 2 | 4 / 2 / 4 | 2 / 2 / 6 | — |
| 提交章 | 5 | 4 | 2 | 11/30 |
| 首轮通过 | 4 | 4 | 1 | 9/30 |
| rewrite 救回 / renegotiate-only 救回 | 0 / 1 | 0 / 0 | 0 / 1 | 0 / 2 |
| **干净口径 E2** | 40.0% | 40.0% | **10.0%** | **30.0%** |
| **人工处置率**（分母=生成章） | 50.0% | 60.0% | 80.0% | 63.3%（池 19/30） |
| §8 | E2、E3 False | E2、E3 False | E2、E3 False | replay 一致 True ×3 |
| §6 Contract/Arc 类命中 | 4 | 9 | 8 | — |

## 3. 稳定面 vs 漂移面（逐章终态）

| 章 | 轮 1 | 轮 2 | 轮 3 | 定性 |
|---|---|---|---|---|
| ch01 | `ARC_CONFLICT` 落空 `['INFERS']` | 同 | 同 | **3/3 同章同型同因** |
| ch05 | `ARC_CONFLICT` 落空 `['INFERS']` | 同 | 同 | **3/3 同章同型同因** |
| ch09 | `ARC_CONFLICT` 落空 `['BELIEVES']` | `NEEDS_HUMAN HARD=3` | `NEEDS_HUMAN HARD=1` | 漂移 |
| ch03/04/07/10 | 混合 NEEDS_HUMAN / OK | NEEDS_HUMAN（烧 2–3 轮） | NEEDS_HUMAN | 漂移 |

唯一的稳定信号是 `arc_003` 的 **`INFERS` 强制项**：每轮都在 ch01、ch05 落空，契约层无权放宽 ⇒ 首轮即止、
不跑修订。其余章次每轮换人死，是真随机。

**这组章谱与冻结轮不同**（刻度参照，非跨比判定）：v3 臂 C 的 ch01 是 首轮/首轮/FAIL、**0 判死**，
ch05 才是判死 2/3（`phase0-v3-three-arm-results.md` §5 章身份表）⇒ 换到 r1:32b 之后 Arc 强制项的
**覆盖面扩大了一章**，判死从 C 的 3/30 变成 6/30。更强模型在这条线上不是持平，是更差。

`NEEDS_HUMAN` 的签名都是 `not committable: HARD=1~4`，即三轮修订跑穿仍有硬约束未消化；
本轮组的 **rewrite 救回 = 0/30**——修订循环在 r1 上一点东西都没买回来（冻结轮 C 也只买回 0–1 章）。

## 4. 结论（只按「三轮是否一致」下）

1. **换到 r1:32b 没有让闸口变松**：三份 E2 的取值区间是 **10–40%**（中值 40%，均值 30%；n=3 下方差主导，
   不据以写"r1 更差"，只写**无增益**），整体压在冻结轮 C 的 40–50% 之下；`ARC_CONFLICT` 判死率 3/30 → **6/30**，
   且章谱多了一章 ch01。**「14b 是绑定项」不成立**——换模型既没抬高过关率，也没换掉卡点。
   卡点的机制见 §6 铲 1：**抽取通道对 `INFERS`/`BELIEVES` 的跨模型漏抽** + 重议不收敛，不是 Arc 产不出台阶。
2. **⇒ A1 的推迟理由消失**：形态不必再为「等更强模型重选」而推迟，D1 可按现有 C-vs-B 结论冻结。
3. **两条必须挂在上文的限制**：
   - **一致性铁律触发**：三份 E2 = 40% / 40% / 10%，互差 30pp（>10pp）⇒ 本组判「**不可判并报方差**」，
     不取多数、不合并、不挑最好看的一份。第三份低是因为 ch02/03/04/06/09/10 六章集体 `NEEDS_HUMAN`
     （首轮只 1 章），不是尺变了。⇒ **T8 不出判定数**，只支撑「方向」那一条。
   - 两变量（模型 + 生成预算）⇒ 不与 v3 跨比，第 1 条里的 47% 只作刻度参照，不作差值凭据。
4. **抽取纪律**（原"计划外发现"，按裁定升级为常驻规则）：**每次换模型，抽取解析失败率随首章干跑必测**，
   进报告模板；坏料计数器现成、零成本。本组坏料 21/463 = 4.5%（含 2 条整条不可解析），比 14b 差。
   但 §6 铲 1 定了世界 B ⇒ 这条不只是纪律：**`INFERS` 漏抽是跨模型的，现在就要修**，不是"以后注意"。

## 5. 下一步

- T9 产品形态组 ×3：`router_local.json`（同 router、同解码，端点 = 本机 11434）；
  端点残留面问题已按裁定关闭（模型在架，`qwen2.5:14b` 服务端与本机都在）。
- 抽取侧 `INFERS` 漏抽的修法与 T9 的先后顺序 ⇒ 见 §6 铲 1 的限制，待裁定。

## 6. 两铲（QA 裁定要求的取证，结论改变了投放方向）

### 铲 1｜`## Draft` vs 抽取产物 —— 判死是**世界 B**（正文写了、抽取器漏了）

读 `t8r1` 的 ch01、ch05 正文与各自的 `## Proposals`：

| 章 | 正文里实际写了什么 | 抽出来的事件类型 | 落空 |
|---|---|---|---|
| ch01 | 敲击听音→"真正的印章回音更沉闷"→"这不对劲"→"终于确定了——是伪造的"；取标准件对比、由差异推结论 | `OBSERVES`×3、`FACT_CONTRADICTED`×3、`HINTS`×2 | `INFERS` |
| ch05 | 供词值班时间与印泥痕迹矛盾→"或许这个人的供词本身就是伪造的"→"守阁的人或许才是关键" | `OBSERVES`×1、`FACT_CONTRADICTED`×2、`BELIEVES`×1 | `INFERS` |

⇒ **Arc 台阶不是产不出，是抽取通道把「推断」这一类系统性误判成 `OBSERVES`/`BELIEVES`**（ch05 里
`BELIEVES` 抽到了、`INFERS` 没抽到，说明漏的是特定候选类型而不是整条通道）。

**跨模型**：v3 冻结轮 14b 臂 C 在同一章 ch05 判死 2/3、落空类型同为 `INFERS` ⇒ 这个漏抽在 14b 与 r1:32b
上都成立 ⇒ 结论 3 从"以后注意"升级为**「现在就修，且不是 r1 专属」**：卡点是抽取侧的 `INFERS` 候选词表/prompt，
不是 Arc 设计层（backlog #6 的低先验 hard gate 假设，这批样本不支持）。

**一处必须挂的限制**：改抽取 prompt = 改尺。T8/T9 与 v3 的"同面可比"里包含抽取通道不动这一条 ⇒
先修抽取再跑 T9，T9 的数就**不能**再与 v3 基线（47%）比，得另立新基线；先跑 T9 再修，则 T9 的数
是在一把已知有系统性漏抽的尺上取的。**顺序要裁定，不能两全。**

### 铲 2｜人工章解剖（`t8r2` ch09）—— 一处前提更正

```
status=FAIL  trace_status=NEEDS_HUMAN  contract_version=4  rounds=3
required_events=['BELIEVES','INFERS','OBSERVES']
round 1 level=contract rules=H5.3        action=renegotiate_contract committed=False
round 2 level=contract rules=H5.3,H5.7  action=renegotiate_contract committed=False
round 3 level=contract rules=H5.3       action=renegotiate_contract committed=False
Findings: HARD H5.1 必需事件 BELIEVES 0<1 / HARD H5.1 必需事件 INFERS 0<1 / HARD H5.3 must_change char_000001.belief 无实现事件(W1)
```

**更正**：`NEEDS_HUMAN` 是 `revision.py:146/152/164/185` 在**阶梯走穿时**写的终态，
`not committable: HARD=n` 来自 `commit.py:77` 的**机器提交尝试**——这条章从头到尾没有经过人手。
T8 三轮里 `--rescue` **一次都没跑过**（救援需要人给改后正文 + `CH:文件` 参数）。
⇒ 闸口 #2「路由闭环实测过」的状态是**未测**，不是"实测不过"；「人改完重新提交仍被打回」在 T8 数据里
没有证据。这条更正很重要，因为它决定修的是 rescue 的 UX 还是 rescue 本身。

但该章残留的三条 HARD 里两条就是铲 1 的同一漏抽（`BELIEVES 0<1`、`INFERS 0<1`），第三条
`H5.3 must_change belief 无实现事件` 是同一族的派生 ⇒ **就算人改了稿，只要人补的是"推理/信念"场景
而抽取器仍不抽 `INFERS`，重提交照样被打回**。所以「给人看的修稿指引」这个补丁该做（现在 dump 只给
`rule_id`，没翻成"请加一场角色由 X 推出 Y 的戏"），但它**不解决**根因，根因在抽取侧。

## 7. 状态更正汇总

| 项 | 原写 | 更正后 |
|---|---|---|
| 结论 1 的机制 | 锁在架构（Arc 强制项 + 重议不收敛） | 锁在**抽取通道的 `INFERS`/`BELIEVES` 漏抽**（跨模型成立）+ 重议不收敛；"等更强模型"仍然否决（成立） |
| 结论 2 的读数 | 均值 30% | 均值 30% 与**中值 40%** 并列；n=3 下方差主导，"r1 更差"**不支持**，只写"无增益" |
| 结论 3 | 以后注意 | 现在就修（世界 B），且修尺与 T9 的顺序要裁定 |
| 闸口 #2 | 实测不过 | **未测**（rescue 在 T8 里 0 次调用）；修稿指引是 UX 补丁，不是闭环失败的补救 |
| 结论 4 墙钟 | 首轮 4–5min / 烧满 9–12min | r1:32b ≈ **7min/章**（本档 §1：12 857s / 30 章）对 14b ≈ **2min/章**（`phase0-h53-spec-qa.md` 的 fix-1：1187s / 10 章）⇒ **约 3.5 倍延迟换零增益**，本机 14b 是唯一生产候选；模型升级这条逃生梯不存在 |
| 救回 0/30 | — | 不是修订循环回归：判死章首轮即死、结构上绕过 loop；v3 里 loop 有救回记录，本组没坏、是它管不到的失败变多了 |

原始 dump 与 state 库在 `sampling/t8r{1,2,3}/`（`.gitignore` 已排除，非入库物）。
