# Phase 0 收尾报告（核心章节）+ v3 冻结方案

> 生成时间：2026-10-10（含 16:31 审查修订）
> 数据冻结面：v2 `f99cc00`；A/B 前置修复 `08745a7`（finding-1）+ `08b9485`（提示词配置化）
> 模型：`qwen2.5:14b` @ `http://127.0.0.1:11434/v1`（`router_local.json` sha12 `a820beb0d944`），
> 解码参数全文见 `docs/phase0-batch6-model-plan.md` §1，所有采样逐字一致
> 性质：审查合并版，可直接作为 `docs/phase0-live-run-10ch.md` v2 新节底稿 + Phase 1 立项附件

---

## 目录

1. 问题起源：H5.3 契约不可满足
2. 协议裁定（QA 六问）与冻结面 v2 修复清单
3. v0-beats 基线：三次采样（原称"盲写"）
4. A/B 实验：设计与预注册
5. A/B 三次读数（v1-told）
6. 归因闭合：世界 A、beats 漏答案键、干净/名义提交率
7. 三次并列 + 决策规则落点（修订措辞）
8. finding-1 / 2 / 3 与 rounds 计数语义
9. Phase 1 backlog（完整版）
10. v3 冻结方案：捆包式第二次 A/B
11. 附录：证据链与引用文档

---

## 1. 问题起源：H5.3 契约不可满足

真实模型 10 章实验（旧尺 `66f87e2`）中 ch06/ch07 被拒于同一 HARD：

```
HARD H5.3: must_change char_000001.knowledge 无实现事件（W1）
```

**根因三层**：(a) 夹具把 04 附录 A 的单章示例契约字节级抄成 10 章逐章意图（每章重复同一对 must_change）；
(b) `must_change` 是 **Δ（跃迁）语义**（04 §4.2、04 §5.2 W1、10 §4.3 三处一致）——每章都要求
"本批事件里重新发生一次该跃迁"；(c) 06 对 must_change 类失败**没有定义归属**，修订循环修不到点。

诊断：`docs/phase0-h53-contract-infeasibility.md`；裁定：`docs/phase0-h53-spec-qa.md`。
**结论：A（修夹具）是正解；C（协议补 D10）撤回。**

## 2. 协议裁定（QA 六问）与冻结面 v2 修复清单

**QA 六问要点**：Q1 Δ 语义成立（三处协议引用 + `validator.py:496-501` 实现一致）；
Q2 判据 = 协议文本的 rule 语义 + severity + 映射表，**代码向文本靠拢 ≠ 改判据**；
Q3 **尺在两个方向上都偏**——偏严（夹具重复 Δ）+ 偏松（`_KNOWLEDGE_ESTABLISH` 合并 knowledge/belief
两 field 且漏 `DOUBTS`；严格按 10 §4.3 分表，fix-1 的 8/10 应读作 5/10）；
Q4 采样状态（fix-2 中断）；Q5 `escalate_to_arc` 不注册 = Auto-Mode #6 明文，真正漏的是入路；
Q6 H5.3 完全不看 `operation`/`expected_value`。

**v2 修复清单**（全部完成，冻结 `f99cc00`）：

| 批次 | 内容 |
|---|---|
| 1 | D：H5.3 按 field 分表（knowledge→OBSERVES/READS/IS_TOLD/INFERS；belief→BELIEVES/SUSPECTS/DOUBTS）；**H5.7 的宽泛集合不动**（两个消费者，只修 H5.3 侧） |
| 2 | A：夹具逐章意图重写（每章 must_change 只指向本章尚未建立的跃迁；rank 推进是合法新 Δ；expected_value ≤ 事件类型 reducer 上限） |
| 3 | B：`derive.py` 守卫——must_change 无可实现 required_event 类型 ⇒ `raise ArcConflict`（只 raise 不补事件） |
| 4 | `RULE_TO_LEVEL["H5.3"]="contract"`；`renegotiate_contract` 遇 Arc 强制项落空 ⇒ fail-fast raise；`consistency_counts` 未映射 code ⇒ CANON 兜底 |
| 5 | 取证三项：逐章渲染 revision_rounds；dump 落 trace.steps（`## Revision`）；dump 打最终 ctx + 第 0 轮另段 |

## 3. v0-beats 基线：三次采样（原称"盲写"）

> **命名更正（2026-10-10 晚）**：渲染核验证明 beats 的`节拍意图`行在两组提示词中逐字相同、
> 本身携带事件类型 + fact ID（见 §6.1）——v0 组从来不是盲写。历史文档中的"v0-blind / 盲写"
> 一律按 **v0-beats** 理解；不重命名已提交文档，以本文档注记为准。

模型与解码同上；串行、detached、`run.log` 留痕。

| | s1 | s2 | s3 |
|---|---|---|---|
| 提交率 | 60%（6/10） | 40% | 30% |
| 首轮通过率 | 40% | 30% | 30% |
| 未决章 | 2,5,7,10 | 1,2,5,7,9,10 | 1,2,3,6,7,9,10 |
| replay 一致 | True | True | True |
| §7 四闸 | G1 T / G2 F / G3 T / G4 F / 可讨论 T（三次相同） | 同左 | 同左 |
| §8 | E1 T / E2 F / E3 F / E4 T / E5 T / E6 T（三次相同） | 同左 | 同左 |
| H5.7 提交章泄漏 | 0 | 0 | 0 |
| 重议才过 / 提交 | 2/6 | 1/4 | 0/3 |
| tokens / 用时 | 39552/813s | 46725/1026s | 50050/1124s |

**逐章稳定性**：02/07/10 稳定失败，04/08 稳定通过，01/03/05/06/09 抖动。
稳定失败核：ch02/ch10 = H2.2 知识跃迁未达 expected rank（配 H5.3+H5.6）；
ch07 = H5.3 belief 无实现事件（三次烧满 3 轮、renegotiate 到 v4 仍败）。

## 4. A/B 实验：设计与预注册

方案：`docs/phase0-writer-prompt-ab.md`。核心条款：尺子冻、配置不冻（prompt 独立版本化，
`prompt_version` 进 run.log 与报告）；三条红线（答案键不进提示词——forbidden 的 fact/命题一律不给、
不改解码参数、不加 seed）；主指标首轮通过率三次均 ≥90%，防线一机械服从（人工抽检成文性），
防线二 H5.7 泄漏不得劣于基线；主口径不一致时三次完整并列、禁止取多数/合并/挑最好看的一次。

**执行前置**：finding-1 修复 `08745a7`（E3 恢复机器可判）；PROMPT_VERSION 落地 `08b9485`。

## 5. A/B 三次读数（v1-told）

v1-told = v0 模板 + 两行显式汇总（`必须发生的跃迁` / `必须出现的事件类型`）。
红线过滤器自检通过（五个稳定失败章的告知条目全部实渲染到场）。

| | t1 | t2 | t3 |
|---|---|---|---|
| 提交率（名义） | 50%（5/10） | 70%（7/10） | 80%（8/10） |
| 首轮通过率（主指标） | **40%** | **50%** | **40%** |
| 干净提交率（见 §6.4） | 50% | 70% | **50%** |
| E2（名义 ≥70%） | False | **True（干净）** | True（**仅名义**） |
| E3（≥90%） | False | False | False |
| H5.7 提交章泄漏 | 0 | 0（ch09 第 1 轮触发、第 2 轮改掉） | 0 |
| 重议才过 / 提交 | 0/5 | 0/7 | **3/8**（ch03/ch06/ch09 正文一字未改；ch06 最终 required_events=[] 空手通过） |
| 机械服从抽检 | 3/3 成文（ch04/08/09 全文抽检） | — | — |
| tokens / 用时 | 47453/1041s | 55129/1268s | 39577/863s |

预注册主指标在 t1=40% 时已数学封盘，t2/t3 仍跑完（协议完整性，堵挑停点）。

## 6. 归因闭合

### 6.1 交付一：渲染后的 prompt 翻出的更大问题——v0 从来不是盲写

v1-told ch02 实渲染（节选）：

```
节拍意图: 建立读者对 fact_000003 的认知 / OBSERVES fact_000001 / 过渡
可以使用的事实: fact_000001: 宗门内存在叛徒；fact_000003: 印章 17 为伪造品
必须发生的跃迁: char_000001.knowledge update fact_000001 → known
必须出现的事件类型: OBSERVES
```

- 告知块是裸 ID 但命题在上方两行、**两跳可查**，不存在空指针级信息缺口（C 项按"两跳版告知"记分）。
- **`节拍意图` 行来自 `_vocab`、两个实验组逐字相同，本身携带事件类型 + fact ID**——
  场景规划器把答案键写进了 beats，v0-beats 同样可见。
- ⇒ 本轮 A/B 的真实对比是「**beats 内嵌答案键** vs **beats + 显式汇总两行**」，
  +10pp 是汇总两行的边际价值。"告知 vs 不告知"**本轮未作答**，留待 v3（§10）。

### 6.2 交付二：四章失败章正文解剖——世界 A，世界 B 零出现

| 章 | 正文实际写的 | 定性 |
|---|---|---|
| t1 ch02 | 张三被改写成伪造者本人，正文主体是"17 号伪造印章样本"；F1 只作为作案计划出现（"让伪造的痕迹误导调查方向"） | **角色身份漂移**（protagonist→forger）；抽取如实（OBSERVES F3 与正文一致，reader_learns 标注都是模型自写） |
| t2 ch04 | 疑虑对象是"印章清单第十七项/朱雀之印"（F3 一族）；F1 只是别人转述的传闻 | **态度对象漂移**（怀疑 F3 而非被告知的 F1）；DOUBTS F3 对正文忠实 |
| t1 ch07 | 正文确实怀疑守阁之人，但命题是"守阁的人是伪造者"——**注册表里没有这条**（F4 仅"碰过印泥"，F2 在 forbidden） | 抽取器无合法落点；**命题不在注册表**（缺中间 fact） |
| t2 ch10 | "如果李四是叛徒，那他就有可能是伪造者"——推理路径 | **夹具低先验 gate**：F2 解禁后要求 OBSERVES→known，叙事先验低 |

**backlog #7 闭合**：提示词没给（否，两跳可查且 beats 已给）、抽取漏了（否，抽取器有带命题的候选
词表且产物与正文一致）、**主因 = Writer 正文层面的角色/命题漂移**。
**"target 绑错"的说法作废**——抽取产物是抽取器的输出，不是写手的输出，只看提案列表时分不清
世界 A/B；必须读正文。

### 6.3 backlog #6 定案（修订措辞，降级绝对化表述）

ch07 不是"模型不会写 belief"（t2 ch03/ch09、t3 ch07 都写出了 belief 事件，t3 甚至首轮命中
`SUSPECTS fact_000004`）；也不是"F4 承载不了怀疑"（被 t3 证伪）。准确表述：

> **对低先验跃迁设 hard gate = 把方差引进 E2。** F4-belief 五轮 1 中、F2-观察 三轮 1 中（均含
> 叙事可行的窄路径）。修复方向：给叙事台阶（补中间 fact / 改实现事件类型 / 降 expected rank），
> 或把此类跃迁降级为软要求。是**降方差**修复，不是"夹具写错了"的全称推广。

**backlog #5 定案**：writer 提示词确实渲染了 required events——以 beats `节拍意图` 的形式
（类型名 + fact ID），两组都有。ARC_CONFLICT 抖动的归因从"引擎没接线"排除，落在解码侧
（temp 0.8 + 无 seed），处置等 seed/低温对照轮。

### 6.4 干净/名义提交率分离（新立，E2 的必备注脚）

`renegotiate_contract` 不改正文，只放宽契约后重验。六份 dump（v2 三次 + told 三次）逐章比对：
**`## Draft` 与 `## Round 0` 逐字相同 ⟺ 该章没跑过任何 `rewrite_*` 动作**（全为 renegotiate 或 0 轮；
ARC_CONFLICT 章无修订动作，等式两边同成立）——六十章检查**零反例**。

⇒ "提交"有两个来源，必须分开报：

- **干净提交** = 首轮过 + rewrite 救回（正文真的变了）；
- **名义提交** = 干净提交 + renegotiate-only 通过（正文一字未改，要求被删松）。

| 采样 | 名义提交率 | 干净提交率 | 靠删要求 |
|---|---|---|---|
| v0-beats s1/s2/s3 | 60/40/30% | 40/30/30% | 2/6、1/4、0/3 |
| told t1/t2/t3 | 50/70/80% | 50/**70**/50% | 0/5、0/7、**3/8** |

**E2 六次采样只在干净口径下过闸一次（t2 70%）**；t3 的 80% 是名义的（ch06 删到 required_events=[]
空手通过）。ch06 型"空契约通过"已立为 Phase 1 backlog 候选（renegotiate 删光要求后的章算不算提交——
判据本身没改，只是承认一个退化情形，Phase 1 裁定）。

## 7. 三次并列 + 决策规则落点（修订措辞）

| | t1 | t2 | t3 | v0-beats s1/s2/s3 |
|---|---|---|---|---|
| 首轮通过率（主指标） | 40% | 50% | 40% | 40/30/30% |
| 干净提交率 | 50% | 70% | 50% | 40/30/30% |
| 名义提交率（E2 判据 ≥70%） | 50% F | 70% T | 80% T | 60 F/40 F/30 F |
| E3（≥90%） | F | F | F | 机器判 F |
| H5.7 泄漏 | 0 | 0 | 0 | 0/30 |

**结论措辞（按审查修订）**：

1. 本轮测的是「显式汇总行 vs 隐式 beats」，**+10pp 是汇总两行在 beats 已携带答案键基础上的边际
   价值**；不能为"告知 vs 不告知"定论（v3 作答，见 §10）。
2. 主指标未达三次 ≥90% ⇒ 第三分支；两道防线均未破（机械服从 3/3 成文、H5.7 三次 0）。
3. 产品形态**不能**据本轮判为"告知型 writer 达标"；也不能说"告知无用"——首轮 30–40%→40–50%、
   ch02 精确命中 OBSERVES F1、ch07 五次抽样首次命中 SUSPECTS F4、E2 干净口径首次过闸（t2）。
4. 与 v0-beats 基线比较时注明：两组共享 beats 答案键，差异只有汇总两行。

## 8. finding-1 / 2 / 3 与 rounds 计数语义

- **finding-1**（`08745a7` 已修，真实路径验证生效：t1/t2/t3 的 E3 全部由机器判出 False）：
  中途判死章只计 generated 不写 rounds_by_chapter ⇒ E3 假 N/A。修复后语义：quarantine 分支
  落 `rounds_by_chapter[ch] = max(len(captured)-1, 0)`。
- **finding-2**：`experiment_id` 恒为 `exp-s1-42`，样本区分靠 dump 目录 + run.log；修复=尝试序号
  并入 id（解冻后）。
- **finding-3**：must_change 系失败（H5.3/H2.2/H5.6）重议成功概率恒为 0 却烧满预算
  （v0-beats ch07 三次 v4；told t1 ch07 v2）。Phase 1：归因与终止策略。
- **rounds 语义**（防误读）：只计成功完成的步，**致命那一步不计入**（raise 发生在动作执行中）。
  ch05 v1/r0、ch09 v2/r1 的读法：r0 = 第 1 轮动作中 raise，不是"修订没跑"。

## 9. Phase 1 backlog（完整版）

| # | 项 | 来源 |
|---|---|---|
| 1 | must_change 系失败的归因与终止策略（06 未定义归属；重议碰不到 must_change 轴） | finding-3 |
| 2 | `rewrite_scene` ≡ `rewrite_chapter`（同一 lambda 两个名字，阶梯前两级名义升级） | v2 前既有 |
| 3 | H8.1/H8.2 的九桶归类（待 08 §4 原文裁定；倾向只记 by_rule 不进九桶） | v2 前既有 |
| 4 | finding-2（experiment_id）；rounds=0 与"无需修订"的等价性注记 | 本轮 |
| 5 | ~~writer 是否渲染 required events~~ **已定案：渲染（beats 形式，两组都有）** | 本轮闭合 |
| 6 | **低先验跃迁的 hard gate 处理规程**：给台阶 / 降 expected rank / 改实现类型 / 降级软要求；禁止把"低先验"写成"不可能" | 本轮定案（修订） |
| 7 | ~~稳定失败核三层归因~~ **已定案：世界 A（角色/命题漂移），世界 B 零出现** | 本轮闭合 |
| 8 | seed / 低温对照轮（抖动章处置前提）；qwen3、deepseek-r1:32b 对照轮（服务端 Ollama 修复前置） | v2 前既有 |
| 9 | **空契约通过**（renegotiate 删光要求后的提交算不算数） | 本轮新立 |
| 10 | **persona/角色一致性系统规则**（"张三是调查方，不是伪造者"——t1 ch02 型漂移的对策，比 seed/换模型便宜） | 本轮新立 |
| 11 | writer 文体缺陷：同场景段落级复述 2–3 遍 | 本轮新立（质量线） |

## 10. v3 冻结方案：捆包式第二次 A/B

### 10.1 为什么捆包

夹具修复、persona 规则、提示词变体若分步采样，各组读数互相不可比，每步都消耗三次采样。
合成**一次 v3 冻结**，所有非尺改动一并落地、一次 alignment 记录、同一面上跑全部臂。

### 10.2 v3 内容

**尺不动**：validator / reducer / commit / 分类表延续 v2，一字不改。

**输入面改动（各附 alignment 记录）**：
1. 夹具 ch07：给 F4-belief 补叙事台阶（新增中间 fact，如"守阁之人形迹可疑"层）或该章 belief 要求改软；
2. 夹具 ch10：F2 的实现事件类型改 INFERS→suspected（或 expected rank 降到推理可达）；
3. persona 系统规则进 writer 模板（角色身份/立场一致性，一条，不含答案键）。

**提示词臂（配置级，prompt_version 各自落 run.log）**：
- 臂 A `v2-stripped`：beats 的`节拍意图`去掉事件类型名与 fact ID，纯叙事意图——**第一次真正的盲写**；
- 臂 B `v1.1-told`：显式汇总行直接带命题（`张三.knowledge「宗门内存在叛徒」→ known`），省两跳；
- 臂 C `v1.1-told+persona` = B + persona 规则。
- **预算砍法**：砍到两臂 = A + C（persona 并入 told 臂）。

### 10.3 采样协议（预注册）

- 同模型、同解码、无 seed，每臂 × 3，串行 detached + run.log 留痕；
- 3 臂 × 3 = 9 次 ≈ 3 小时本机（砍臂则 6 次 ≈ 2 小时）；
- **开跑前硬门槛：三臂各 dump 一章实际渲染 prompt 并逐字段核验**——本轮"beats 漏答案键"
  的教训证明，A/B 的对照组不 dump 实际输入就不存在基线（此条升级为 Phase 1 实验规程）；
- 指标：首轮通过率（主）、干净提交率、名义提交率、H5.7 泄漏、机械服从抽检、ARC_CONFLICT 率；
- 决策规则（示例，执行前定稿）：臂 C 首轮三次均 ≥90% 且防线不破 ⇒ 产品形态定为
  "told+persona"；臂 A 与臂 C 的差 = "告知 vs 不告知"的第一次干净测量；
- 一致性铁律沿用：不一致 ⇒ 三次完整并列，预注册扩展规则（补采 2 次、5 取 4）防 gate 悬空。

## 11. 附录：证据链与引用文档

### A. 关键代码坐标

| 坐标 | 内容 |
|---|---|
| `validator.py:496-509` | `_change_implemented`：Δ 语义实现（不看 operation/expected_value） |
| `validator.py:358` | `_KNOWLEDGE_ESTABLISH`（H5.7 宽泛集合，D 修复不碰它） |
| `experiment.py:76-87` | 修订包装与 dump 回调（batch 5 后打最终 ctx + Round 0） |
| `experiment.py:108-113` | ArcConflict quarantine 分支（finding-1 修复点） |
| `experiment.py:155` | `experiment_id = f"exp-{story}-{seed}"`（finding-2） |
| `review.py:87` | `revision_ran` 判定（finding-1 修复后生效） |
| `review.py:245` | `rewrite_scene` ≡ `rewrite_chapter`（backlog #2） |
| `revision.py:38-51` | `RULE_TO_LEVEL`（H5.3→contract 已补） |
| `revision_actions.py:29-30` | Arc 强制项静默减掉（批次 4 改为 fail-fast raise） |
| `llm.py:111-115` | 请求体无 seed/top_p（独立抽样口径） |

### B. 证据方法

- **`Draft ≡ Round 0` 零反例检查法**（§6.4）：六份 dump × 10 章 = 60 章，正文逐字相同 ⟺ 无 rewrite 动作；
- **正文解剖法**（§6.2）：区分世界 A/B 的唯一手段是读 `## Draft`，提案列表做不到；
- **渲染核验法**（§6.1）：任何 A/B 先 dump 对照组实际输入。

### C. 引用文档

| 文档 | 内容 |
|---|---|
| `docs/phase0-h53-contract-infeasibility.md` | H5.3 诊断 v1 |
| `docs/phase0-h53-spec-qa.md` | QA 六问裁定 |
| `docs/phase0-sample-status-and-revision-trace.md` | 采样状态与旧轨迹重建 |
| `docs/phase0-batch6-model-plan.md` | 模型配置（同模型三次 + 身份写死 + sha12） |
| `docs/phase0-v2-samples.md` | v0-beats 三次采样原始读数 |
| `docs/phase0-writer-prompt-ab.md` | A/B 预注册方案 |
| `docs/phase0-prompt-ab-results.md` | told 三次读数 + 归因闭合（含被推翻的初判，证据链保留） |
