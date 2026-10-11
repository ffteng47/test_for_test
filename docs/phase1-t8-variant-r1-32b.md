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

1. **换到 r1:32b 没有让闸口变松**：三份 E2 的取值区间是 **10–40%**，整体压在冻结轮 C 的 40–50% 之下
   （均值 30% 对 47%，只作刻度参照）；`ARC_CONFLICT` 判死率 3/30 → **6/30**，且章谱多了一章 ch01。
   **「14b 是绑定项」不成立**——卡点在架构侧（Arc 强制项不可满足 + 重议不收敛），不在模型解码质量侧。
2. **⇒ A1 的推迟理由消失**：形态不必再为「等更强模型重选」而推迟，D1 可按现有 C-vs-B 结论冻结。
3. **两条必须挂在上文的限制**：
   - **一致性铁律触发**：三份 E2 = 40% / 40% / 10%，互差 30pp（>10pp）⇒ 本组判「**不可判并报方差**」，
     不取多数、不合并、不挑最好看的一份。第三份低是因为 ch02/03/04/06/09/10 六章集体 `NEEDS_HUMAN`
     （首轮只 1 章），不是尺变了。⇒ **T8 不出判定数**，只支撑「方向」那一条。
   - 两变量（模型 + 生成预算）⇒ 不与 v3 跨比，第 1 条里的 47% 只作刻度参照，不作差值凭据。
4. **一条计划外发现**：r1 的抽取 JSON 纪律比 14b 差（坏料 21 条 / 463 提案 = 4.5%，
   含 2 条整条不可解析）。「更强模型」不覆盖这一面，Phase 2 若要换模型，抽取侧要重测。

## 5. 下一步

- T9 产品形态组 ×3：与 v3 同 router、同解码参数，出正式判据数（端点三选一待裁定，见 `phase1-v3.1-freeze.md` §6）。
- `arc_003` 的 `INFERS` 强制项在 ch01/ch05 上三轮全落空 ⇒ 这是 Phase 1 的一个独立议题（夹具意图 vs 模型能力，
  与 v3 §4 的「臂 A 判死章身份」同源），T10 判定前不动码。

原始 dump 与 state 库在 `sampling/t8r{1,2,3}/`（`.gitignore` 已排除，非入库物）。
