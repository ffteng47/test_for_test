# Phase 0 真实模型实验报告（10 章）

日期：2026-10-09。接续 Day 28–30 计划（`docs/superpowers/plans/2026-10-09-alexandria-live-model-day28-30.md`）Task 5。
协议依据：`alexandria-spec-v0.2/` 07 §4.3/§5.3、08 §4/§6/§7/§8/§10。

## 1. 结论

**不进 Phase 1，也不改架构。** 有效基线是 `生成 10 / 提交 2 / 未决 8`，§8 E2/E3/E4 不达标；
但这 8 章的失败全部指向同一个尚未实现的东西——`Arc → ChapterContract → ScenePlan` 生成器——
而不是协议本身。§7 冻结闸命中 G1/G3，按 08 §7 只记 backlog，不动 HARD。

真正值得写进报告的，是本轮**推翻了此前两次「成功」**：那两次实验的通过与否由我的抽取提示词决定，
与引擎和模型都无关。一个会被提示词左右的实验，样本量再大也没有意义。

## 2. 环境与复现

模型跑在局域网 Ubuntu 服务器（RTX 3090 24G，Ollama 0.35.1），Ollama 只监听 `127.0.0.1:11434`。
本机不直连该端口（不把无认证端口暴露到局域网），走 SSH 隧道：

```bash
ssh -o ExitOnForwardFailure=yes -f -N -L 11500:localhost:11434 tff@192.168.31.213
python -m plot_engine.review --live --chapters 10 \
  --model-config @router_qwen3.json --dump-dir <dir>
```

`router_qwen3.json` 三个角色（writer/extract/plan）都指向 `http://127.0.0.1:11500/v1`、
`model: qwen3:8b`、`extra_body: {"reasoning_effort": "none"}`。
最后一项是必需的：qwen3 默认把全部输出写进非标准的 `reasoning` 字段，`content` 为空，
`/no_think` 与 `think:false` 在 OpenAI 兼容层都无效（实测），只有 `reasoning_effort: none` 生效。

## 3. 实验历史（前两次作废）

| # | 模型 | 代码状态 | 结果 | 是否可用 |
|---|---|---|---|---|
| 1 | qwen2.5:14b（本机） | 抽取提示词含答案键 | 生成 10 / 提交 8 | 作废：归因受污染 |
| 2 | qwen3:8b（服务器） | 抽取提示词含答案键 | 生成 10 / 提交 10，E1–E6 全 True | **作废：假通过** |
| 3 | qwen3:8b（服务器） | 通道独立后 | 生成 10 / 提交 2 / 未决 8 | **有效基线** |

第 2 次与第 3 次之间**没有改过模型、夹具、验证器、Reducer**，只改了我的抽取提示词与解析器。
10/10 与 2/10 的差值就是这次实验最有价值的测量结果。

## 4. 有效基线明细（第 3 次）

```
生成 10 / 提交 2 / 未决 [2, 3, 4, 5, 6, 8, 9, 10] / replay一致 True
tokens=52795 用时=307s｜抽取产出 114 条 / 坏料 无
Revision：需修 2 章 / 最多 2 轮 / 修复率 0.50

§6  Contract / Arc 问题: 7 (H5.1, H5.2, H5.3)
§7  G1=True G2=False G3=True G4=False → 可讨论改架构（本轮决定：不改）
§8  E1=True E2=False E3=False E4=False E5=True E6=True
```

硬指标全部立住：replay 一致 True，已提交章的设定/知识/时序矛盾 0，禁用事实零泄露。
**崩溃防线没有被真实模型击穿**——这是 08 §4「Phase 0 只追求不崩」正面成立的部分。

失败侧的形态：`H5.1 必需事件 INFERS 数量不足（0<1）` 反复出现，`H5.2` 出现一次禁用事件 REVEALS，
`H5.3 must_change 无实现事件`。抽取产出从第 2 次的 20 条涨到 114 条（不再被答案键锚定后，
模型开始照实报告正文里的事件）。

## 5. 本轮修掉的缺陷

| commit | 缺陷 | 证据 |
|---|---|---|
| `bce8b7b` | 模型把 schema 提示 `OBSERVES:fact_id` 回声成 payload 键，一路进 EventLog | 4/10 章的 dump |
| `ef68f0d` | 抽取提示词泄露 Contract 的 required_events（答案键） | null-draft 对照：正文毫无事件仍回 2 条 |
| `09db48c` | LLM 通道输入里保留 composer 的 `<!-- reader_learns -->` 标记 | 对照：有 markup 时照抄 fact_000003，剥离后两种输入结果一致 |
| `3e783a3` | FAIL 消息 `"not committable (hard violations or empty batch)"` 二选一，等于没说 | 8 章 FAIL 无从归因，白烧一轮 GPU |

`3e783a3` 之后 message 会写明 `HARD=n` / `consistency_hard=n` / `empty batch` / `H8.1 整批短路`。

## 6. 同正文 A/B：失败到底在 Writer 侧还是抽取侧

同一批正文（第 3 次实验的 dump，逐章快照即 `--dump-dir` 的用途），只换抽取模型。
State 统一用 genesis，因此这一列与第 3 次实验的绝对事件数不可直接比较，只比较**同一正文上两个模型的读法**。

| 章 | qwen3:8b 事件类型 | deepseek-r1:32b 事件类型 | 8b 有 INFERS | 32b 有 INFERS |
|---|---|---|---|---|
| 01 | HAPPENS HINTS INFERS OBSERVES REVEALS | BELIEVES FACT_CONTRADICTED | 有 | 无 |
| 02 | HAPPENS HINTS OBSERVES REVEALS | OBSERVES SUSPECTS | 无 | 无 |
| 03 | HAPPENS INFERS OBSERVES | FACT_CONTRADICTED INFERS OBSERVES SUSPECTS | 有 | 有 |
| 04 | HAPPENS INFERS OBSERVES | FACT_CONTRADICTED INFERS OBSERVES | 有 | 有 |
| 05 | HAPPENS INFERS OBSERVES | BELIEVES OBSERVES | 有 | 无 |
| 06 | OBSERVES | OBSERVES READS | 无 | 无 |
| 07 | HAPPENS HINTS INFERS OBSERVES | OBSERVES SUSPECTS | 有 | 无 |
| 08 | HAPPENS HINTS OBSERVES | FACT_CONTRADICTED OBSERVES READS | 无 | 无 |
| 09 | HAPPENS OBSERVES | 未完成 | 无 | — |
| 10 | HINTS OBSERVES REVEALS | 未完成 | 无 | — |

**决定性的一行：32B 在 8B 漏掉 INFERS 的 3 章（02/06/08）里，一次都没有找回来（0/3）；
反过来 32B 在 8B 找到了的章里丢了 3 次（01/05/07）。**
所以 `H5.1 必需事件 INFERS 数量不足` 不是抽取器太弱，而是**正文里确实没有一段可判定的推理步骤**——
Writer 没有写出来，任何规模的模型都抽不出来。§6 把这些失败归到 Contract / Arc 一侧，由这一条数据支持。

附带两条：

- **32B 更保守**：事件类型数普遍更少，且从不输出被契约禁用的 REVEALS；8B 在 3 个章里输出了 REVEALS。
- **抽取本身不可作单次判定**：32B 的 ch01 在两次输入完全相同（同模型、同正文、同词表、同温度 0.2）的
  连续运行中分别给出 `FACT_CONTRADICTED OBSERVES` 与 `BELIEVES FACT_CONTRADICTED`。
  这意味着本报告第 3/4 节的 E2、E4 带有一次采样无法给出的方差；
  Phase 1 的退出条件必须按**多次重复**或 temp=0 来判定，单次 10 章运行不足以判定架构级结论。

成本：8B 抽取 3–8s/章；32B 抽取 87–180s/章（19–30 倍）。
服务器 `OLLAMA_KEEP_ALIVE=60s` 而逐章间隔超过 60 秒，因此**每次调用都在重载 19GB 权重**——
若要常态使用 32B，需把 keep-alive 调大（服务器配置改动，未做）。ch09/10 因本地进程被终止而未完成。

## 7. Backlog（Phase 1 前置，不改协议）

1. **`Arc → ChapterContract → ScenePlan` 生成器不存在**（08 §6 归因至今只被夹具部分验证）。
   夹具 10 章的契约完全相同：同一 required_events、同一 must_change、同一 reader_signal，
   所以「10 章实验」实际上没有测试任何跨章推进。这是 E2/E4 不达标的根因。
2. **live harness 的 RevisionLoop 缺 `renegotiate_contract` 动作**：`_LEVEL_TO_ACTION["contract"]`
   指向它，缺失即 NEEDS_HUMAN 0 轮。第 3 次实验 8 章失败只有 2 章进过修订循环，就是这个原因。
3. **被拒章的 `consistency` HARD 不进 §6 计数**：`classify.consistency_counts` 只统计已提交章，
   沙盒矛盾目前只能从 `message` 读到 `consistency_hard=n`，没有独立 rule_id。Phase 1 需要能被分类。
4. **r1 系列不可用 `reasoning_effort`**：思考无法关闭，`max_tokens` 必须显著大于思考预算，
   且吞吐 6.3 tok/s（3090 单层）——不适合做迭代主力模型，只适合作对照。
5. **空批次 FAIL 的可达路径未在 Phase 0 内构造出确定性用例**：`_review` 会从 markup 通道补
   READER_* 事件，因此 `proposals=[]` 也不产生空批；`3e783a3` 的分原因消息已覆盖该情形，
   但缺一个专门钉住它的测试。
6. **退出条件需要重复采样**：§6 的稳定性证据表明单次运行的 E2/E4 含不可量化的方差。
   Phase 1 判定应以 N 次重复（或 temp=0）给出通过率区间，而不是取一次结果作数。

## 8. 本轮未做（明确留在范围外）

- 未改任何协议/HARD/架构（08 §7 冻结）。
- 未改服务器配置（keep-alive、端口暴露）。
- 未接 `Arc → ChapterContract → ScenePlan` 生成器——需要产品决策（生成什么故事），不是接线工作。

## 9. v3.8 冻结面三采样 + 本地跨硬件横批（2026-10-16，epoch_1/WP-A 收口后首采）

**采样设计**：WP-A v3.8 码批（契约面修订：逐章意图 must_change + D10/D11 前置拦截 + H9 族）落地后，
按 §7 条 6 的自欠（"退出条件需要重复采样"）跑 **同模型（qwen2.5:14b）同规划（ladder-v4 十章）三次**，
判据只按"三次是否一致"下，不再取单次作数。另起**本地 3090 第四批**作跨硬件对照（tff 裁定方案 A：
主三批不动，横批分表）。首批过 R8 #1 确认闸：**闸单 jobs#1**（project 1，
`plan_sha256=8c085a8a1b49b6460db69efe2a10085529ba84eb2153b10348fccdfa23d606d2`，confirmed_by=tff）。

**尺戳纪律**：本表全部为 **v3.8-foreshadow-payload** 尺面读数；§4 的 8/10（fix-1，严格协议读 5/10）
与 `docs/phase0-50ch-stress.md`（wpe50ch）均为**旧尺（v3.6）对照，分表不并列**。

| 批 | 车道 | 终态（OK/NH/ARC） | 需修章/最多轮/修复率 | §6：Writer 类 : Contract/Arc 类 | E1–E6 | tokens/用时 |
|---|---|---|---|---|---|---|
| r1 | 213 | 3 / 7 / 0 | 7 章 / 3 轮 / 0.00 | 12 : 17（H5.1,H5.3,H5.4,H5.6） | T **F F** T T T | 165,652 / 1,448s |
| r2 | 213 | 2 / 7 / 1 | 8 章 / 3 轮 / 0.12 | 8 : 12（ARC,H5.3,H5.4,H5.6） | T **F F** T T T | 203,382 / 1,580s |
| r3 | 213 | 3 / 7 / 0 | 10 章 / 3 轮 / 0.30 | 12 : 16（H5.1,H5.3,H5.4,H5.6） | T **F F** T T T | 228,325 / 1,811s |
| l1 | 3090 本地 | 3 / 6 / 1 | 8 章 / 3 轮 / 0.14 | 9 : 14（ARC,H5.1,H5.3,H5.4,H5.6） | T **F F** T T T | 166,641 / 3,726s |

**一致性判定（主三批）**：
- OK 率 30/20/30%，E1/E4/E5/E6 三批同真、**E2（提交率≥70%）与 E3（≥90%）三批同假**——读数稳定，不是单次方差假象。
- 失败主体三批一致落在 **Contract/Arc 类**（17/12/16 居首，H5.3 must_change 未实现领衔），Writer 类（H2.2/H5.7）为次。
- **结论：契约面修订（ladder-v4 逐章意图 + D10/D11 拦截）不改变判负——"十章规模成立"在 v3.8 冻结面下判否**。
  这与 WP-E 五十章判负（处置率 74%，同谱系 H5.3×110）同向：缺陷在契约/Arc 语义层本身，不在夹具写法。
- G1（同类 failure ≥3）命中 → 08 §7 冻结闸**允许讨论**改架构（非自动改）。议程候选=既有挂账：Level-3 在场一致性/WP-F
  方法论吸收（`docs/project-roadmap.md` WP-E  backlog 行）+ must_change 归属空白（06 §4）。

**跨硬件对照（l1 分表）**：本地 3090 同模型同参（extract 上限 2400/温度 200，路由逐字段镜像仅换 base_url）
读数 OK=3/10、E2/E3 同假、失败同谱系——**尺读数不依赖 213 硬件，测量面跨机器稳定**。
效率面：213 单章均速 ~2.5 min（r2 十章 25 min），3090 ~6.6 min（十章 ~62 min），慢 ~2.6 倍；
适合对照批不适合主采样车道（且与主三批并行不占隧道）。

**复现（§13 落盘）**：
```
.venv/Scripts/python.exe -m plot_engine.review --live --chapters 10 \
  --model-config @router_q25_14b.json --gate-project 1 --dump-dir sampling/ep1v38-rN   # N=1,2,3（@213 隧道 11500）
.venv/Scripts/python.exe -m plot_engine.review --live --chapters 10 \
  --model-config @router_local_q25_14b.json --gate-project 1 --dump-dir sampling/ep1v38-l1  # 本地 Ollama 11434
```
归档：`sampling/ep1v38-r1/ r2/ r3/ l1/`（各含 ch01–10.md、run.log、_junk.json、state/{state.db,event.db}）+ 同名 `.log` 控制台。
坏料合计 r1=21 / r2=69 / r3=44 / l1=36 条（`_junk.json` 逐条可数；大头 `stripped_payload_key` 与 `id_value_not_id`，instr-v2 修复环后仍能出稿的部分未计入失败）。
