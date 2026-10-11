# Phase 1 冻结面 v3.1（T7）

> 冻结对象是**尺**（判据 + 分类 + 状态机 + 闭环），不是产物。协议文本一字未动：
> 04/05/06/07/08 的 rule 语义、severity、映射表全部以 `alexandria-spec-v0.2/` 为准，
> 本文件记录的每一条都是「代码向文本靠拢」（alignment），不是协议变更。
> 判据（`docs/phase0-v3-three-arm-results.md` §7，封版于 `c6615d5`）不改写、不软化。

## 1. 落码清单

| 项 | commit | 内容 | 类型 |
|---|---|---|---|
| T1a | `c14f626` | 逐章快照头新增 `trace_status=`；触顶分支的 trace 终态由 `FAIL` 改判 `NEEDS_HUMAN` | 导出/状态机 |
| T2 | `c14f626` | `renegotiate_contract` 拒绝把 `required_events` 删空（backlog #9） | 判据下限 |
| T1b | `ca70937` | `rescue_chapter` + `review --rescue/--state-dir`；`count_dispositions` 从快照数终态分布 | 闭环/口径 |
| T3 | `c176dc6` | H8.1/H8.2 不进九桶，只记 `by_rule`（08 §4 无抽取桶） | 分类 |

全量测试：**425 passed**（`.venv/Scripts/python.exe -m pytest plot_engine -q`，零新增依赖）。
golden test 保持绿；新断言（`test_rescue.py` 3 条、`test_review.py` 3 条、
`test_revision_renegotiate.py` 3 条、`test_classify_metrics.py` 1 条）已随上述 commit 进 CI 面。

## 2. equivalence 证明（对已完成的 v3 九份读数逐条核对）

| 改动 | 对九份读数的影响 | 凭据 |
|---|---|---|
| T3（H8.x 出桶） | **无**。那批读数里没有任何 H8.x 命中，`canon/knowledge/timeline` 三个数一字不改 | 读数表内无 H8 条目（§6 分桶逐臂核对） |
| T1a（`trace_status=` 导出） | **无**。只加了一行输出，判据、状态机、commit 枚举都没动；`CommitStatus` 六值原样（07 §4.1） | `models/commit.py:17` 未改 |
| T1b（救援闭环） | **无**。新模块 + 新 CLI 参数，默认路径行为不变；既有 90 章次没有一章被救援过 | `rescue.py` 无既有调用方 |
| T2（#9 下限规则） | **有，且已在 §7 声明**。7 个「删空判据后空手通过」的章次在新尺下改判 `NEEDS_HUMAN` ⇒ §7 (ii) 的基线数字按该节增补的新尺换算表引用（C ≤10/30·每次 ≤5/10；B ≤5/30·每次 ≤4/10），旧 ≤9/30、≤2/30 作废。**判据公式与 20pp 间距不变** | `phase0-v3-three-arm-results.md` §7（ii）增补表 |

T2 换算的残留限制（D1 冻结会须原样抄进形态冻结记录）：换算是「同一批读数的终态重读」，
**只重分类、未模拟这 7 章不提交后对后续章的 State 后效**。

## 3. alignment 记录（逐条，含授权出处）

- **T2**：06 §4.2 授权的是「按 04 §4.3 重新派生」，不是「把判据删空」。空 `required_events`
  让 H5.1 永真，本章变成「靠删掉要求而通过」。拒绝时原样返回、`version` 也不加（不假装重议过）。
  Arc 强制项（D3 拐点 / D6 逾期 gate）一条都没被放宽——这条在 `c14f626` 之前就已成立。
- **T1a**：终态有两个字段，此前被混为一谈。`CommitOutcome.status` ∈ 07 §4.1 六值（无 `NEEDS_HUMAN`）；
  `RevisionTrace.final_status` ∈ 06 语义的四值（有 `NEEDS_HUMAN`）。触顶分支此前写 `FAIL`，
  与同一文件里另外三条人工出口（`rc is None`、`_HUMAN_LEVELS`、ladder 走穿）不一致 ⇒ 统一为 `NEEDS_HUMAN`。
  改的是**终态命名与导出**，`outcome` 侧一个字没动。
- **T1b**：失败章按 07 §5.3 R1 无副作用失败 ⇒ 没有提交残留可回滚，`store.revert_commit` 用不上；
  守卫改成「只能救链尾章」。非链尾 = 要重写链尾之后整段，属整链重跑，不在救援语义内。
  救援**不跑** `RevisionLoop`、**不重议**判据：人给的稿子就是最终稿。
- **T3**：08 §4 九项全是故事状态的账，没有一项量抽取可信度 ⇒ H8.x 兜底进 CANON 会让 §8 E6 与
  G4 因一次漏抽判成状态不一致，与 T3「不进任何闸口」的降级要求直接冲突。未知**非 H8** 的 rule
  仍兜底 CANON（05 §9 I6：可见性不丢）。

## 4. 本帧没带的东西

- **T4 persona observation 检测器**：**推迟到采样之后**，与本计划的第 1 周排期是一处偏离，理由写清：
  它没有判定基准（`Character` 只有 `faction_id/status/realm`，`models/entity.py:9-31`），
  第一版只能是未校准的启发式。把一把未校准的新尺在冻结前放进面里，风险是它事实上变成
  C 形态的加分依据——那正是 §7 防线禁止的「拿新尺替换人工抽检」。它降级后的定位（只进报告列、
  不进闸口）在采样前后落地都不影响判据，故后置。
- **`rewrite_scene ≡ rewrite_chapter`**（backlog #2）：名义阶梯，仍只记档不改。
- **06 对 must_change 类失败的归属空白**：Phase 1 议题，本帧不动。

## 5. 采样跑法（命令模板）

```
python -m plot_engine.review --live --chapters 10 --prompt <beats|told|persona> \
    --model-config @router_local.json --state-dir <chain_dir> --dump-dir <dump_dir>
```

三条都写进档上，一条都不能省：

1. **`--state-dir` 必带**。默认临时目录跑完即弃 ⇒ 链不在盘上，事后 `--rescue` 无账可救
   （闸口 #2 要求路由闭环的实跑证据，没链就没有证据）。同一目录再跑一批会被拒
   ——两批读数不并成一条账。
2. **臂纪律不变**：渲染过滤器只作用臂 A（`stripped`）；B（`told`）/C（`persona`）与 t1–t3
   逐字节一致，否则「同面可比」作废。
3. **人工处置率从 `<dump_dir>` 的 `trace_status=` 数**，不从 `status=` 数（后者没有 `NEEDS_HUMAN`）。
   判死章分母两种口径并列呈现的要求不变。

救援（被路由章）：`--rescue CH:改后正文文件 --state-dir <chain_dir> --model-config @router_local.json`，
要求 CH 是链尾章。

## 6. 采样前的阻塞项（一条，且是重启服务那么小的一条）

**勘误（本文件此前一版写错了机制，按代码/配置实核推翻）**：上一版把 `127.0.0.1:11434`
当成服务端隧道，据此断言「冻结模型已不在服务端 ⇒ T9 资格拿不到」。**两处都错**：

- 端口约定：`11434` = **本机 Windows Ollama**；服务端 Ollama 只监听它自己的 `127.0.0.1:11434`，
  经 `ssh -L 11500:localhost:11434` 映射为本地 **11500**（`phase0-batch6-model-plan.md:18,:23`）。
  v3 九份读数跑在**本机**，`router_local.json` 的 `base_url` 就是 `http://127.0.0.1:11434/v1`。
- 模型位置：上一版查的是默认目录 `C:\Users\tff\.ollama/models`（确实只剩 `llama3-zh-inst`），
  但这台机器把 `OLLAMA_MODELS` 重定向到了 `E:\github\LLM\ollama`（HKCU\Environment）。
  那个 store 里 **`qwen2.5:14b` 在架**：`manifests/registry.ollama.ai/library/qwen2.5/14b`
  ＋ 对应 8.4G blob 实存。同一 store 还有 `deepseek-r1/{7b,14b,32b}`（32b blob 19G 实存）。
  ⇒ 冻结模型**不需要重新下载**，服务端有没有它跟 T9 的资格无关。

| 阻塞 | 状态 | 说明 |
|---|---|---|
| 本机 Ollama 服务没起 | **唯一阻塞** | `netstat` 里 11434/11500 均无 LISTENING；`curl http://127.0.0.1:11434/v1/models` → exitcode 7。启动服务属 Auto Mode 权限外（起停服务不在授权内）⇒ **人起**：`ollama serve`（同一进程会读 `OLLAMA_MODELS`，起完 `curl /v1/models` 应能看到 `qwen2.5:14b`）。先例记录：`phase0-batch6-model-plan.md:137` 早把「本机 Ollama 服务当前没起（11434/11500 均无 LISTENING）」写成开跑前置 |

服务起来之后，T9 的「与 v3 同 router、同解码参数」直接由现成的 `router_local.json`
（sha12 `a820beb0d944`）满足，不需要任何新配置。

**顺带对 T5/T8 的影响（不改变排期，只改一手来源）**：`deepseek-r1:32b` 在本机 store 里就有，
T8 变体组可以走本地（`base_url` 换 11434）而不必先建隧道；代价是 19G 权重在本机推理，
v3 的 14b 已经把 `timeout_s` 放到 600，32b 更慢、可能更吃内存 ⇒ 本地跑 32b 前先用一章试一发，
慢到不可接受再回到「隧道 → 服务端 r1:32b」那条原计划（隧道仍是基础设施动作，需显式授权）。
