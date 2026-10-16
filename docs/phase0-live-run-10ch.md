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

## 10. 归因双批：模型面 × 结构面（2026-10-16，判负后的单变量取证）

§9 判负的归因问题：**Contract/Arc 类失败（H5.3 领衔）是「任务单过重」还是「模型做不到」？**
两批各只动一个变量，读数都按 v3.8 尺（同抽取尺、同 Writer 面、同指引）：

- **M 批（模型面）**：213 车道，写手+抽取从 qwen2.5:14b 升**同族 32B**（deepseek-r1:32b 会掺推理模态、弃用）。
  契约/夹具/规划哈希全同基线 ⇒ 复用闸单 **jobs#1**。`sampling/attr_m32b_r1/`。
- **H 批（结构面）**：本地 3090 车道 14b（硬件对照已由 l1 背书），换新夹具
  `experiment_10ch_half`（ladder-v4-halfdensity）：非 turning point 章 must_change/强制事件**各减半**
  （全局 18→12 / 16→11），TP 章 1/5/9 与空推进章 8 逐字同基线。新规划哈希 `f7deae69b073…` ⇒
  新闸单 **jobs#3**。`sampling/attr_half_r1/`。夹具验收：离线 E1–E6 全绿 + `test_fixture_half_density.py` 4 钉。

| 批 | 变量 | 终态（OK/NH/ARC） | 需修章/最多轮/修复率 | §6：Writer : Contract/Arc | E1–E6 | tokens/用时 | 坏料 |
|---|---|---|---|---|---|---|---|
| 基线 r1/r2/r3 | —（14b 全密度@213） | 3/7/0 · 2/7/1 · 3/7/0 | 0.00 / 0.12 / 0.30 | 12:17 · 8:12 · 12:16 | T **F F** T T T | 165k–228k / 1448–1811s | 21/69/44 |
| **M** | 模型 ×2.3（32B） | **3/7/1** | 7 章 / 3 轮 / **0.14** | 5 : **13** | T **F F** T T T | 142,725 / 3,502s | **9** |
| **H** | 契约 ÷2（半密度） | **3/7/0** | 7 章 / 3 轮 / **0.00** | 5 : **11** | T **F F** T T T | 167,446 / 4,065s | 62 |

**归因判定：两个候选主因都被排除在解释位之外。**
1. **模型面无效**：32B 落在 14b 基线带内（OK 仍 3/10、E2/E3 同假、谱系同）；且 32B 抽取**坏料少一个量级**
   （9 条 vs 21–69）仍不换来提交率——抽取清洁度不是提交率的约束。规模 ×2.3 只买到更慢（3,502s）与更干净的废料堆。
2. **结构面（任务单过重）不成立**：契约负载减半后未决章数不变（7 章）、修复率 **0.00**、Contract/Arc 类失败
   只是等比缩小（13→11 含 H5.1/H5.3/H5.6）——模型**连一条钉都没稳写作**，不是「钉太多写不完」。
3. **剩余解释位**：① 尺面钉判 vs Writer「场景化写作」的模态错位（H5.1/H5.3 按事件类型+actor 匹配，正文可能真写了
   但抽取/判钉不认——Level-3 在场一致性挂账同谱系）；② **Revision 循环对 must_change 类失败无修复动作**
   （两批修复率 0.14/0.00 实证 06 §4「must_change 归属空白」backlog——3 轮预算空转）。

**确认闸事故记录（fail-closed 有效）**：首张 H 批闸单 jobs#2 以 `json.dumps` 字符串作 payload 入账（双重编码），
preflight 读回 `json.loads(payload)` 得 str → AttributeError 拦截，批次未启动、无预算烧失。处置：#2 作废留痕、
#3 以 dict payload 替身过闸。教训：`add_confirm_job` 的 payload **必须传 dict**（noveldb 层会再序列化）。

**复现（§13 落盘）**：
```
.venv/Scripts/python.exe -m plot_engine.review --live --chapters 10 \
  --model-config @router_q25_32b.json --gate-project 1 --dump-dir sampling/attr_m32b_r1      # @213 隧道 11500
.venv/Scripts/python.exe -m plot_engine.review --live --chapters 10 --fixture experiment_10ch_half \
  --model-config @router_local_q25_14b.json --gate-project 1 --dump-dir sampling/attr_half_r1  # 本地 11434
```
归档：`sampling/attr_m32b_r1/`、`sampling/attr_half_r1/`（各含 ch01–10.md、run.log、_junk.json、state/）+ 同名 `.log` 控制台。
测试基线：本批夹具+4 钉 ⇒ plot_engine **557→561**；backend **10** 不动。
下一步：冻结会读 §9+§10——改架构议程从「结构面 vs 模型面」收敛为「**钉判模态错位（尺/Writer 面）vs Revision 动作缺失（06）**」二选一或并列。

## 11. 取证裁决：43 个未决章次全量机检（2026-10-16，双口径判决）

§10 出局两个候选面后，剩余解释位靠人工逐章读正文不可规模化。本节改为**重放机检**：
pre-state = 夹具 genesis + 该批 `state/event.db` 里 `chapter<ch` 事件重放（`apply_events`）；
终轮契约 = dump 头部（`contract_version` + `required_events` 类型）套现算 `contract_for`；
提案 = `## Proposals` 段重建（conf=700，全 LLM 通道）；复跑 `Validator._review`。
**43/43 章次的复现 rule 集与 dump Findings 一致**，例外仅 ch09 三连（r2/l1/M）——dump Findings
为空是**契约开工前判死/重议中途判死**（M ch09 终态 ARC_CONFLICT，run.log 实证），复现出的
H5.1/H5.3 属假设面、不入判决。判决口径：**①** 正文没写钉；**②** 戏在正文、抽取没给/型漂移；
**③** 抽到了但判钉不认（actor 翻转，或族内弱动词撞 rank 上限=「全对仍FAIL」）；**④** 泄漏族
（H5.7，另按终稿有无文本依据分真漏/误报）；伴生=H5.6；漏驱动=H5.4。

**Δ 面（43 章次，章级最差判决）**：① 1 · ② 18 · ③ 19 · ④ 4 · ARC 判死 1。

| 类 | 章次 | 定死证据（句/账级） |
|---|---|---|
| ① | M ch07 | 终稿「笔迹/密信」零出现，王五只怀疑赵六夜值——F07 信念戏真没写 |
| ②（18） | H2,H3,H9 · M1,M6,M10 · r1 ch2,ch5,ch9 · r2 ch1,ch4,ch9 · r3 ch2,ch4,ch6,ch9 · l1 ch2,ch9 | 提案类型∉实现表（BELIEVES/DOUBTS/STATES/HINTS/OBSERVES 撞 knowledge/belief 表）、型漂移（READS→OBSERVES/INFERS）、正文有戏无提案（l1ch10 会饮段、r3ch6 商号段） |
| ③（19） | 翻转 13：M2,M4 · r1 ch4,ch6,ch10 · r2 ch2,ch7,ch10 · r3 ch7,ch10 · l1 ch4,ch6,ch7 | 钉在甲名下、提案全在乙名下（IS_TOLD actor 约定+信念归属互翻） |
| ③（续） | rank 互斥 6：r1 ch7 · r2 ch6 · l1 ch10 · H4,H7,H10 | 「抽取全对仍FAIL」= 族内弱动词撞上限：IS_TOLD cap=believed、INFERS cap=suspected，Δ 期望 known——H5.3 判「已实现」、H2.2 判「未取得」 |
| ④（4） | H8 · l1 ch3 · r2 ch5 · r3 ch5 | 章内主死因=禁止知识整批建立（H5.7/H5.4 漏驱动），非钉失败 |
| ARC | M ch9 | 契约开工前判死，run.log 终态 ARC_CONFLICT=1 |

**钉面（逐条钉，采纳稽核助手表 + l1ch10 补核）**：①≈21 · ②≈16（含 R0 有→终轮丢的抽取漂移）· ③≈9。
①里两类是**结构性写不出**：ch10 钉「OBSERVES 李四是叛徒」——隐藏身份不能被"亲眼看见"；
ch07 钉2「王五确认 F03」戏缺。l1ch10 补核终：李四否认台词在场（目标句「有人否认听说过叛徒」
兑现），钉①（无身份确证）与 Δ③（actor 翻转）并存。**结论：钉面①大头不是 Writer 偷懒，是钉本身越界。**

**H5.7 泄漏族 24 条（12 个 章×fact 去重）逐处对终稿**：**误报仅 4**——r1ch04-F12 / r3ch02-F06 /
l1ch04-F12 / halfch08-F02（终稿零文本依据）；**真漏 8**——r1ch05、r1ch09、r2ch05、r3ch05、r3ch09、
l1ch03、l1ch04(F02)、m32ch06（均有句，如 r1ch05「他越来越相信，李四很可能就是那名背叛宗门的叛徒」）。

**更正记录（双口径互查产出的三处翻案）**：
1. **halfch08 我方翻案**：先前判「Writer 真漏（正文写了'找出真正的叛徒'）」——该句在 dump 第 94 行
   `## Round 0` 段内，终稿（16–66 行）「叛」零出现 ⇒ 改判**抽取幻觉**。教训入册：关键词扫描必须
   圈定 `^## Draft` 段，dump 段序 Findings→修稿指引→Draft→Proposals→Round 0 是陷阱。
2. **m32ch06 稽核方翻案**：稽核列入误报清单，终稿含 ≥4 句叛徒（「这件事与门派内的叛徒是否有关」等）⇒ **真漏**。
3. **稽核「H5.7 误报 10 处」缩水为 4**；「H5.4 vs must_change 契约自冲突」否决——H5.4 的 F2 是
   must_not_change 目标，只在泄漏提案把 F2 rank 动了账后才触发，定性=**漏驱动**伴生，非自冲突。

**三大机制（把 §10 的「钉判模态错位」下钻成可修的三件）**：
① **H5.3↔H2.2 互斥面**（Δ③ rank 家族 6 章）：H5.3 实现表按类型放行、H2.2 按 rank 卡死，同一把尺
   自己跟自己不一致——**冻结会头号议程**（尺/契约面修订批）。
② **IS_TOLD actor 约定翻转**（Δ③ 13 章 + 钉③≈9）：约定 actor=听者、reducer 只给 actor 加分，
   说者永不入账 ⇒ 抽取按语义给说者、判钉按约定要听者。② 属抽取 prompt 面（backlog 既定优先序）。
③ **越界钉**（钉①大头）：隐藏身份类 OBSERVES 钉结构上不可满足——derive 层拦截候选（D10/D11 同族）。

**复现（§13 落盘）**：
```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/_forensics/adjudicate.py
```
脚本归档 `sampling/_forensics/adjudicate.py`（判决口径写进 docstring；①? 残余两章按上表人工定死）。
本节**零码改**——测试基线 plot_engine 561 / backend 10 不动。
下一步：冻结会议程 #1 = H5.3↔H2.2 一致性修订（尺面）；议程 #2 = IS_TOLD actor 约定入抽取 prompt；
「Revision 动作缺失（06 §4）」与 Δ② 抽取面并案讨论——③19+②18 的判负主力已被证实为**尺与约定**问题，Writer 纯失位（①）仅 1 章次+2 类越界钉。
