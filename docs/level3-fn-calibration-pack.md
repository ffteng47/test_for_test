# level3_fn 判分线定标材料包（v0.1，2026-10-17）

> 任务来源：`docs/project-roadmap.md:196` backlog 行 (a)——「章内在场一致性盲区（WP-E ch50 实证三连穿帮机检全漏，
> `docs/phase0-50ch-stress.md` §6）：(a) level3_fn 判分线待 tff 定标」。
> 本文档只做**取证与候选定义**，不定阈值——画线权在 tff。
> 纪律声明：本批全程只读（读 dump/state.db/event.db + 回代码），未写代码、未动 roadmap、未做 git 操作；
> 除本文件外未新建任何文件。原型读数用一次性内存内脚本计算，可复算。
> 谱系锚点：材料出自 `sampling/wpe50ch/`（尺 v3.6-is-told-actor、夹具 ladder-v5-50ch、
> run.log 首行戳；见 `docs/phase0-50ch-stress.md:6-8,59`）。

---

## 1. 样本取证：ch50 三连穿帮与「机检全漏」的逐层证据

### 1.1 原始案例（出处 `docs/phase0-50ch-stress.md:46-49`；`:行号` 指 `sampling/wpe50ch/ch50.md`，
`## Draft` 段在 ch50.md:21 起，最终轮正文=ch50.md:22–83，行号已逐条对回原文核实无误）

| # | 锚点行 | 原文（摘） | 穿帮类型 |
|---|---|---|---|
| ① | ch50.md:22 → ch50.md:38 | 「藏宝阁内只剩下赵六一人」→「张三和赵六坐在藏宝阁内」 | 凭空进场（在场集合无来源扩张；张三在 Draft 中首次露面即 :38，:22–:37 无进场戏） |
| ② | ch50.md:60 → :62 → :64 | 「随后便离开了藏宝阁」→「张三与赵六走在回门主府的路上」→「藏宝阁内……张三和赵六背对背坐着」 | 空间回卷（离场+在路上之后，无进场断言又回到原地点在场） |
| ③ | ch50.md:26 → ch50.md:66 | 「钥匙仅此两枚，一把（在）高层一枚赵六」vs「守卫历来两个人，钥匙两个人共同保管」 | 规则漂移（同章内静态规则两次陈述不一致） |

ch50 终态 NEEDS_HUMAN（ch50.md:2 `status=FAIL`、:3 `trace_status=NEEDS_HUMAN`、:4 `HARD=3`），
未提交——人审闸兜住（`docs/phase0-50ch-stress.md:53`）。

### 1.2 漏检机制回代码验证（现有机检各层为什么抓不到）

**Validator 层级结构**（`plot_engine/validator.py`）：

- **L1（确定性账级）**：`_run_l1` = H1 系/H3 系/H4/H6（validator.py:339-349）。与「在场」沾边的只有两条，且都吃抽取产物里的地点：
  - H1.3 事件地点 vs `current_location`（validator.py:130-140）：判据来自 `_event_location(ev)` = `ev.payload.get("location")`（validator.py:99-100）——**事件级、actor 单点**，查的是「他人在 A，事件却发生在 B」，查不了「同章两段互相打脸」。
  - H3.4 同批两地点（validator.py:201-219）：同样只吃 `payload.location` 和 CHANGES 事件。
- **L2（契约/知识/伏笔账）**：`_run_l2` = H2/H5/H9（validator.py:583-589）——全是知识跃迁、must_change、伏笔生命周期，**无一列查空间在场**。
- **Level-3 位**：`level3_fn` 形参在 validator.py:794，调用在 validator.py:828-829——
  **① 仅当 L1/L2 无 HARD 才触发**（validator.py:828）：ch50 恰有 HARD=3（H2.2/H5.4/H5.6，ch50.md:12-15），
  即现有闸序下就算接了满分 L3 也轮不到它在 ch50 跑——这是定标必须一并裁的「闸序问题」；
  **② L3 永不产 HARD**，HARD 一律降级 observation（`_demote_l3`，validator.py:776-786；05 §9 I1，
  validator.py:5 亦注「本 Phase 0 不接入」）；
  **③ 全仓 grep 实据：live 管道没有任何地方传入 level3_fn**——出现处只有 validator.py 形参与
  `plot_engine/tests/test_validator_l3.py:39-83`（单测桩），即它是**空插槽**，不是「接了但漏报」。

**在场信息从何而来（现状盘点）**：

- 抽取产物**无在场字段**：`PAYLOAD_SCHEMA` 全部 16 事件型的 payload 键里没有一个 `location`
  （`plot_engine/llm_extract.py:65-82`）；实据——50 份 dump grep `location` **0 命中**
  （`sampling/wpe50ch/ch*.md` 全量 grep）；归档 `sampling/wpe50ch/state/event.db` events 表 198 条事件
  反序列化实测：`Event.location` 全 None（198/198），事件型分布里 **CHANGES=0 条**
  （有 OBSERVES 43/INFERS 59/SUSPECTS 18/IS_TOLD 17 等）。即：整个 50 章跑，H1.3/H3.4 两把尺**没吃过一口料**。
  代码侧还有半截线：`Event` 模型本有 `location` 字段（`plot_engine/models/event.py:40`），
  但 `to_event` 不从 proposal 映 location（`plot_engine/models/proposal.py:40-56` 无该参数）——
  即便抽取给出，也要补这一跳（或走 payload 键，validator.py:99-100 现读 payload）。
- State 侧承接位：`Character.current_location`（`plot_engine/models/entity.py:25`）是唯一的「在哪」账，
  且**只由 CHANGES(field=location) 更新**（`plot_engine/models/contract.py:65-74` FIELD_EVENT_TYPES:
  `"location": {"CHANGES"}`）——事件驱动，无「章内静态在场」承接位；
  认知层账（knowledge/belief/reader ledger，`plot_engine/models/state.py:55-59`）装的是 fact 引用，
  夹具 12 条种子 fact 全是剧情知识（`sampling/wpe50ch/state/state.db` states v0 envelope 实测），
  没有一条是「X 此刻在 Y」的在场属性事实（最接近的 fact_000006「赵六那夜在藏宝阁值守」是 event 型，不进在场账）。
  归档终态实测：char_000002/3/4（李四/王五/赵六）current_location=loc_000012（藏宝阁），
  **char_000001（张三）=None**——张三压根没有位置账可查。
- ScenePlan 有在场规划位但 Validator 不吃：`Scene.location/characters`、`Beat.actors/location`
  （`plot_engine/models/sceneplan.py:25-28,39-40`）；由 `derive_scene_plan` 确定性派生
  （`plot_engine/derive.py:290-335`；场景地点仅当本章角色在 State 里位置唯一才带上，derive.py:261-266
  `_scene_location`；cast 取契约演员表，derive.py:254）。ScenePlan 走 CommitRequest 进编排
  （`plot_engine/models/commit.py:27`），但 `reduce_commit`→`Validator._review` 的入参
  只有 draft/proposals/contract/state（`plot_engine/reduce.py:38-43`、validator.py:801-803）——
  **在场规划信息在判定时是断线的**。
- 账级巡检也不查：`consistency.py`（`assert_consistent`，consistency.py:183）查引用/唯一性/超额消耗/
  actor 生死状态（如 I7，consistency.py:138-152——missing 角色带具体位置才落 soft，
  且因事件 location 全 None 同样空转）；`prose_audit.py` 穿帮 = 词表级
  （现代词表 `_ANACHRONISM`，prose_audit.py:13-26 + 章首同构/跨章重复，prose_audit.py:35-60），无空间逻辑。
  即 `docs/phase0-50ch-stress.md:51` 三句归因（H5.4 间接留痕 / 无在场账 / 词表级）逐条代码复核成立。
- 修订环帮倒忙的回代码：修稿指引 H2.2 原文「补一场他亲眼看到 / 读到 / 被告知该事实的戏」
  （`plot_engine/review.py:196`），ch50 三轮全是 rewrite（ch50.md:8-10）——只补戏不删旧场，
  :60–:64 回卷即缝合产物（`docs/phase0-50ch-stress.md:52`）。

---

## 2. level3_fn 判分函数候选（三个形态）

统一接口事实：现插槽签名 `level3_fn(draft: str, state_after_sim: StoryState, contract) -> List[Finding]`
（validator.py:794, 829）；输出受 `_demote_l3` 硬约束（validator.py:776-786），**永远只到 SOFT/OBSERVATION**。
凡需扩签名（加 proposals/scene_plan 入参）或改闸序（validator.py:828）的，都属判分线之外的**管线变更**，下表单列。

### 候选 A：「在场文本对账」（静态断言回卷计数，per-章分值）

- **输入**（全部既有产物，可纯派生）：本章 Draft 文本 + State 词表（角色名/地点名，state.db 即可拿到）。
- **函数**：正则抽取「静态在场断言」三元组（角色, 地点, 段号）；章内求在场集合转移：
  S1 = 无进场词的首次静态在场断言数（①凭空进场族）；S2 = 「离开 L」后 n 段内无进场词又断言在 L（②空间回卷族）；
  总分 = S1 + S2。③规则漂移族不在本候选面（属内容一致，不是在场）。
- **需新增抽取字段？** 不需要（词表已在账内，断言正则器是新判分旋钮、不碰抽取尺——但它喂 L3 输出，
  措辞变更纪律参照 review.py:186-191 指引尺戳族单列）。
- **可否纯派生**：可以（本次已在 50 章上跑通原型，见 §3.1）。
- **可否复用 WP-A 现有事件型**：不能——WP-A 事件型 = FORESHADOWING_SET/PAID
  （llm_extract.py:50, 79-80；validator.py:549-580 H9 族），伏笔账不携带在场语义。
- **可复用既有机制**：finding 分桶幂等（validator.py:761-773）；输出走 observation 桶零障碍。

### 候选 B：「事件地点投影」（账级在场投影，per-章 finding 列表）

- **输入**：Proposals 新增 `payload.location`（或接通 `to_event` 的 location 一跳，proposal.py:40-56）
  + state 位置账 + ScenePlan.scenes（可选第二对照面，需扩 `_review` 签名传入）。
- **函数**：H1.3（validator.py:130-140）/H3.4（validator.py:201-219）两把**已写好但饿死**的尺的章内推广：
  按 seq 序维护「actor 最后断言地点」running 表，逐事件比对；再加在场集投影：
  场景段 actor 集 vs 事件 location 聚集——同章同地断言在场者集合的无来源变化出 finding。
- **需新增抽取字段？** **需要：payload.location = 抽取尺面变更红线**（PAYLOAD_SCHEMA 加键
  = v3.8→v3.9，llm_extract.py:50 注释明写「改它=尺面变更」；且 50 章归档尺是 v3.6）——单列见 §5 红线表。
- **可否纯派生**：不能——存量产物零料（§1.2 实测 0/198、0/50 dump），必须重抽取才有读数。
- **可否复用 WP-A 现有事件型**：不能（同候选 A 的理由）；能复用的是 L1 现成判据函数与
  consistency I7「missing 带位置」检查器（consistency.py:149-152，同样等料下锅）。
- **额外依赖**：`current_location` 覆盖率——归档实测张三=None（无账可对），候选 B 对「凭空进场」①
  仍只能判「进场后与账不符」，判不了「进场无来源」；后者要 (b) 项在场账补齐后才闭环。

### 候选 C：「LLM 在场审读」（05 原生 level3 形态，per-章 finding 列表）

- **输入**：现签名三件套（draft, sim.cur, contract）**正好够用，零管线改动**（validator.py:794）。
- **函数**：LLM 逐段抽「叙事在场断言 + 静态规则陈述」→ 与同章前文断言集比对，输出三类 finding：
  进场无源 / 空间回卷 / 章内规则漂移（覆盖①②③全部——③只有本候选或人工能判）。
- **需新增抽取字段？** 不需要进 State/抽取尺；但 **L3 提示词 = 新增第三把判分尺面**
  （独立于抽取尺 v3.x 与指引尺 g3，建议单独尺戳，红线单列 §5）。
- **可否纯派生**：不能（要 LLM 实调用）；但**输入料全部已在归档**（50 份 Draft + state.db 快照），
  试点不需要重跑 Writer。
- **可否复用 WP-A 现有事件型**：不涉及（不读事件型）。
- **可复用**：`_demote_l3` 语义护栏现成（validator.py:776-786）——天然满足「L3 永不产 HARD」。

---

## 3. 阈值标定方法：已知坏章 vs 已知好章上的读数分布

已知正例（坏）：**ch50**（§1.1 三锚点）。已知负例（好）：**13 个终态 OK 章**
（从各 dump `trace_status=OK` 行枚举实测：ch01, 08, 12, 13, 21, 22, 23, 26, 35, 40, 42, 44, 48；
与 `docs/phase0-50ch-stress.md:15` OK 13 对齐）。中间层：36 个 NEEDS_HUMAN（含真穿帮混噪，只作参照不作标尺）。

### 3.1 候选 A：本批已实算（read-only 原型，两档口径）

原型 1（宽口径：段内人名×地点名共现即算在场断言）per-章 S 值分布（49 章可算，ch09 ARC_CONFLICT 无 Draft）：

| 分组 | 读数 |
|---|---|
| 直方图（全部 49 章） | {0:1, 1:4, 2:19, 3:14, 4:10, 5:1, 6:1} |
| 13 个 OK 章 | [0,1,1,2,2,2,2,2,3,3,4,4,5]，均值 2.38 |
| 36 个 NEEDS_HUMAN | 均值 2.81，范围 1–6 |
| **ch50（已知必揪出）** | **2** |

原型 2（严口径：只认静态谓词句式「坐在/只剩/背对背/留在/值守+loc」）：

| 分组 | 读数 |
|---|---|
| 直方图（49 章） | {0:2, 1:15, 2:26, 3:7} |
| 13 个 OK 章 | [0,1,1,1,1,1,2,2,2,2,2,2,3] |
| ch50 | **2** |

**标定结论（把实数摊开给 tff，不代画线）**：两档原型在现有 50 章归档上**均无阈值可分**——
要揪住 ch50（=2）须把线画在 ≥2：原型 1 由此误报 OK 章 10/13（77%），原型 2 误报 7/13（54%）。
即：**候选 A 的正则断言表不足以支撑判分线**——没有一条线能同时满足「ch50 必揪、OK 章低误报」；
要么升级断言表（仍是尺面工作、可再离线复算），要么降格为 OBS 观察列（不设阈值、不进判死，只给人审排序）。
这是归档能给的极限读数。

### 3.2 候选 B：归档读数全零，无法标定

缺口数据 = **带 location 的抽取产物**（现归档：0/198 事件、0/50 dump 有地点，§1.2 实测）。
零成本复算命令核查结论：**不存在纯离线重算路径**——payload.location 要经 LLM 重抽取
（`llm_extract.py` 通道），不是既有账内确定性计算。可复算的最省路径：
- 单章闭环重放（人稿回灌验证判分线用）：`.venv/Scripts/python.exe -m plot_engine.review --rescue CH:文件 --state-dir sampling/wpe50ch/state --fixture experiment_50ch`
  （review.py:575-597, 618-620）——仍需模型在线，但 Writer 面零成本（不重写正文）。
- 50 章 Draft 全量重抽取：dump 正文即输入，挂 v3.9 抽取尺重打 llm_channel——一次抽取批的 token 成本。

### 3.3 候选 C：无既有读数，试点即得

缺口数据 = **L3 提示词的首跑读数**（现插槽空转，§1.2 ③）。标定试点零 Writer 成本：
输入=13 个 OK 章 + ch50 + 抽 6 个 NH 章（覆盖烧满 3 轮的缝合嫌疑户：ch2,5,6,14,15,20——
`docs/phase0-50ch-stress.md:19`），每章一次短 prompt（Draft 均 <2 万字符）。
产出即 tff 要的两侧分布：好章 L3-finding 数 vs ch50 是否 ≥3 条（三锚点各中）。
判定线之外的闸序问题一并定标：**ch50 这类带 HARD 章 L3 不会被调用**（validator.py:828）——
若要求 L3 在 NEEDS_HUMAN 章也出数（给人审排序用），需要改闸序或旁路批跑（dump 离线全量跑 L3 不经 validator），
后者零管线改动，建议标定材料按旁路口径先出数。

---

## 4. 与 (b) 项「在场静态事实 = T1 新事件型」的联动

roadmap:196 (b)：在场/位置静态事实进账 = T1 新事件型，归 epoch_2/WP-F 双层追踪；WP-A 范围已冻结。
归档谱系实测：wpe50ch 全部状态为 **epoch_0**（state.db v0 envelope `epoch=epoch_0`），
即便今天接候选 B 也只对 epoch_0 账本读 `current_location` 旧值——(b) 落地后账升 epoch_2，
候选 B 的判据（位置对账）**随迁无需改函数体，但历史读数跨 epoch 不可并表**
（谱系纪律参照 `docs/phase0-50ch-stress.md:8` 并表禁同款逻辑）。

- **先后关系**：(a) 判分线**不必等** (b)。候选 C（及 A 的升级版）判的是「章内自相矛盾」，
  参照面是同章前文断言，不是跨章账本——(b) 的在场账解决的是**跨章**「他在哪」溯源，两者正交。
  (b) 落地后候选 B 才从「事件地点瞬断」升级为「在场账闭环」（凭空进场①型判据才配齐来源核查）。
- **保守可判子集（降级方案）——有**：不等 T1 新事件型，先用两条既有账内可判的面：
  ① **章内文本自反面**（候选 C/A）：只判「本章后段打脸本章前段」，零账依赖；
  ② **current_location 非空者的位置矛盾**（候选 B 的收窄版）：只对有位置账的角色判
  （归档实测仅 char_000002/3/4 有账，覆盖率 3/4 活角色，张三恰是无账那个——报告必须带覆盖率读数，
  否则把「没账」读成「没穿帮」，教训同 readout.py:40「没测≠全好」纪律）。
- 红线预告：在场静态事实若要**进 HARD 判死**，与 05 §9 I1「L3 永不产 HARD」正面冲突——
  唯一正路是 (b) 进账后由 L1/L2 账级规则承接（epoch_2/WP-F），level3_fn 定标阶段目标只到
  SOFT/OBS + 人审排序，不含判死权。

---

## 5. 尺面变更红线清单（本文档只登记，不裁决）

| # | 红线 | 触点 | 若动的代价 |
|---|---|---|---|
| R1 | PAYLOAD_SCHEMA 增 location 键 | llm_extract.py:65-82 | 抽取尺 v3.8→v3.9；50 章历史读数作废不可并表；坏料口径（missing_payload_keys 族）全重基线 |
| R2 | L3 提示词/断言正则表 | 新增件（独立第三尺面） | 必须带戳归档（参照 EXTRACTION_RULER/GUIDE_VERSION 双尺先例，review.py:186-191）；改措辞=改读数 |
| R3 | 指引尺 FIX_GUIDE | review.py:193-211 | g3→g4；修订环读数漂移（#70 教训面） |
| R4 | `_review` 签名/闸序（scene_plan 入参、L3 触发条件） | validator.py:801-830 | 05 §7 协议文档同步，属判据流程变更非尺面微调 |
| R5 | `to_event` 补 location 一跳（若走 Event.location 而非 payload） | proposal.py:40-56 | canonical 哈希面变化 → replay parity 全链重验 |

---

## 6. 一页结论（供 tff 画线）

| 候选 | 可纯派生? | 需尺面变更? | 标定样本够不够 |
|---|---|---|---|
| A 在场文本对账 | ✅ 是（本批已实算两档） | 断言表=新判分旋钮（轻） | 样本够但**分布无分离度**（ch50=2 落在 OK 章堆里）→ 需升级断言表再复算，或降 OBS 不设线 |
| B 事件地点投影 | ❌ 否 | **R1 抽取尺 v3.9（重红线）** | 不够：存量读数全零（0/198 事件、0/50 dump）；需重抽取批才能首算 |
| C LLM 在场审读 | ❌ 否（要 LLM 实调用） | R2 新尺戳（中） | 输入料够（13 OK + ch50 + 6 NH 全在案）；缺 L3 首跑读数——一次旁路试点即得；另附闸序裁定（validator.py:828） |

复现命令：读数命令同压力测试报告 `.venv/Scripts/python.exe -m plot_engine.readout sampling/wpe50ch`
（`docs/phase0-50ch-stress.md:7`）；本批原型 A 的数字可用 state.db/event.db + dump 只读重算（§3.1 口径描述即算法）。
