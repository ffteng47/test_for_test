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
   读数器住在仓库里：`python -m plot_engine.metrics <dump_dir>`（`plot_engine/metrics.py`），
   它按 §7 的冻结定义出「干净口径 E2 / 人工处置率」两行，判死章分母两种口径并列；
   Phase 0 那版同类脚本因为落在仓库外临时目录，机器一清就没了——这次不再重演。
   `renegotiate-only` 章进分母不进分子，真 rewrite 救回进分子，靠 `## Revision` 的 `action=` 判。

救援（被路由章）：`--rescue CH:改后正文文件 --state-dir <chain_dir> --model-config @router_local.json`，
要求 CH 是链尾章。

## 6. 采样端点与 r1:32b 的接线事实（2026-10-11 实测，含两次作废的推断）

**端点裁定：采样只用服务端 Ollama**（用户指示）。隧道 `ssh -fN -L 11500:localhost:11434 tff@192.168.31.213`
由人建立；`ollama 0.40.2`，在架 `qwen2.5:14b / qwen3:{8b,14b,30b} / qwen3.5:27b / deepseek-r1:32b`。
两次被实测推翻的推断都记在这儿，免得下轮重排查：

| 推断 | 实测 |
|---|---|
| 「冻结模型不在服务端 ⇒ T9 资格拿不到」（把 11434 当成服务端隧道） | 错。11434 是**本机** Ollama，v3 就跑在本机（`phase0-batch6-model-plan.md:23`）；服务端一直有 `qwen2.5:14b` |
| 「换到服务端就能躲开 r1 的思考污染」 | 半对。0.40.2 的 `/v1` 把思考放进 `message.reasoning`，**`content` 干净** ⇒ 正文不被污染、`LlmClient` 不用加剥 think 的代码；但**思考 token 与正文共用 `max_tokens` 预算** |

**r1 的思考预算（T8 的一处声明变量）**：抽取角色在冻结预算 `max_tokens=800` 下实测
`finish_reason=length`、`completion_tokens=800`、`reasoning` 895 字 / `content` 774 字截在半截 JSON
⇒ 解析 0 提案 + 1 坏料。关思考的两条路在服务端都试过、都无效：`{"reasoning_effort":"none"}` 与
`{"think":false}` 均返回 `content=''`、思考照写（0.40.2 对本 GGUF 关不掉）。
⇒ **T8 把 writer/extract 的 `max_tokens` 放大到 2000，思考保留**——关掉思考等于自断一臂，
变体组要答的「14b 是不是绑定项」就不算数。代价写死在档：**T8 相对冻结轮有两个变量
（模型 + 抽取/写作预算）**，温度（writer 0.8 默认 / extract 0.2）、`timeout_s=600`、章节数 10、
提示词臂 `persona` 逐字相同；因此 T8 只作 pre-freeze 标注、不与 v3 跨比（A1 边界不变）。

**配置钉死**（sha256 前 12 位；配置文件不入库的规则沿用批次 6）：

| 用途 | 文件 | sha12 |
|---|---|---|
| 冻结轮 / T9 产品形态轮 | `router_local.json` | `a820beb0d944`（未改一个字节） |
| T8 变体组 | `router_r1_32b.json` | `d76ce5d6a2e4` |
| fallback（解码对照，未跑） | `router_local_t03.json` | `20428c6384f1` |

**T9 的残留面问题（要裁定，不阻塞 T8）**：v3 基线跑在**本机** 14b，T9 若按指示改跑**服务端** 14b，
`base_url` 与推理后端版本都变了 ⇒ 「与 v3 同 router」严格说不成立。三个选法：
① T9 走服务端 + 先在服务端重跑 14b 基线三次（吃掉额外预算）；② T9 回本机 14b（逐字同 router，
慢：warm 15.3 tok/s、冷启动 239s）；③ 承认「同 router」只指 model/解码参数，把端点差异作一条
声明写进判定节。①最干净、③最省，取哪个看你对预算的判。

**T8 开跑前的一发核实**（`--chapters 1`，`router_r1_32b.json`，321s）：抽取产出 7 条提案 /
坏料 1（`missing_payload_keys`），写作 `content` 无思考残留 ⇒ 接线通。但该章终态
`ARC_CONFLICT`，落空类型 `['INFERS']`（`OBSERVES` 已满足）；v3 臂 C 的 ch01 是首轮通过。
**不临场修**：r1 在 ch01 不产/不抽 INFERS 正是变体组要测的东西之一，三轮照同一条命令跑完再读。
