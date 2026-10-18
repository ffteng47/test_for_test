# L3 一致性检测三层架构设计（穿帮检测）

- 版本：v0.1（纸面设计，**零码改**；画线权/拍板权在 tff，本文不代画）
- 日期：2026-10-17
- 上游讨论：四参照系深度审查（`docs/commercial/refrence/deep-dive/`）+ 三层可查询结构提案 + `docs/level3-fn-calibration-pack.md` 在册证据链
- 本文回答两件事：① 三层穿帮检测的落地方案；② **是不是一个专门的模块——是，模块边界见 §2**

## 1. 问题定义与映射

穿帮 = 正文与"已确认叙事事实"之间的矛盾。我方 L3 缺陷三族（在册，§7 试点定名）：

| 族 | 定义 | 计算对象化（本文方案） |
|----|------|------------------------|
| A 进场无源 | 人未进场先在场互动 | 在场状态区间 vs 场景实体索引 |
| B 空间回卷 | 离开未交代到达又在原地互动 | 位置时序约束（最早可达时间） |
| C 规则漂移 | 配对矛盾（钥匙在谁手、设定前后不一） | 原子事实有效区间重叠 + 语义冲突 |

提案"审计 A/B/C 通道"与我方"A/B/C 族"不是一回事：审计 A（状态对照）≈ C 族+部分 A 族；审计 B（账外反证）≈ 三族兜底通道；审计 C（时间因果）≈ B 族。本文按**层**组织，不按通道组织。

## 2. 模块归属（回答"是不是专门模块"）

**是专门模块，且必须与现有两个物划清边界：**

```
plot_engine/
  consistency.py        # 既有（171行）：账面结构一致性 L0——ID唯一/引用完整/透支/
                        #   角色状态/台账/reveal_stage（assert_consistent）。管"账内部自洽"。不动。
  models/ reducers/     # 既有子包先例
  l3/                   # 【新子包】语义一致性层（本方案）。同名包会遮蔽 consistency.py，故不取 consistency/
    __init__.py
    scene_index.py      # 场景/实体索引（第一层，纯派生）
    fact_intervals.py   # 事实有效区间视图（第一层，纯派生）
    interval_conflicts.py  # 区间重叠矛盾候选检测（确定性）
    temporal_checks.py  # 位置/时序硬检查（确定性）
    triggers.py         # 选择性触发（轻/深两档）
  validator.py:830      # 既有 L3 插槽（level3_fn，闸序已修：判完即跑）——生产接线的唯一合法入口
sampling/
  level3_pilot.py       # 既有旁路试点车道（v0.2/v0.3/v0.4/v0.4.1 四代带戳归档）——判分器留这里
  quote_verify.py       # 既有五态引文核验（对照组，不退休）
```

**三条边界纪律**：
1. `l3/` 前两批全部是**纯派生投影**（同 B2 阅读卡/爽点读数批形态：零尺零契约零门禁、不回写上游、replay 不可得记「-」）
2. 判分器（NLI/LLM）**不进内核**，留 sampling/ 旁路车道带戳试点（R2 纪律：措辞/模型变更=读数变更）
3. 权威层扩字段（location 入 PAYLOAD_SCHEMA）= **R1 红线候选 B**，独立拍板；生产接线（level3_fn 传入方）触 WP-0/WP-A 申报

## 3. 三层可查询结构

### 3.1 第一层：权威状态层（场景索引 + 有效区间事实）

**缺口实证**：`models/fact.py` 的 Fact 只有 `defined_at_chapter`，**无有效区间**；event.db 198 条事件 location 全 None（漏检根因链在册）。

**3.1.1 场景索引（scene_index.py，纯派生，不触尺）**

从正文归档+既有 sceneplan 派生每章场景帧：

```python
class SceneFrame(BaseModel):      # 派生物，不入账、不改 schema
    chapter: int
    scene_seq: int                # 章内场景序号（场景边界=地点/时间/在场集合跳变）
    location_text: str            # 正文原话（出处指针锚点）
    line_start: int; line_end: int  # 行号区间（v0.4 行号制同源，宿主回填）
    present: list[str]            # 在场实体（首轮=主角/主要配角/关键道具白名单）
    departed: list[str]           # 本场景离场（"离开/动身/前往"触发，v0.4.1 B 族笨办法同源）
    arrived: list[str]            # 本场景到场
```

派生方式：首轮**确定性规则**（地点名词表+在场白名单+离开/到达触发词，复用 v0.4.1 已验证的 B 族指令逻辑做成代码），LLM 增强版留旁路车道。入账标准（提案原则本地化）：**不是"是否出现"，而是"其状态变化是否可能约束后续章节"**——路人只在约束后续时生成临时帧，不强制永久保留。

**3.1.2 有效区间视图（fact_intervals.py，纯派生）**

给既有 Fact/事件流加区间投影（InkOS `state-reducer.ts` applyFactOps 已互证该形态：`validFromChapter/validUntilChapter/sourceChapter`，expire 不删行）：

```python
class IntervalFact(BaseModel):    # 派生视图，不改 models/fact.py
    subject: str; predicate: str; object: str
    valid_from: int               # 生效章（事件章）
    valid_until: int | None       # 失效章（被同 subject+predicate 新事实顶替=chapter-1）
    source_chapter: int
    evidence_ref: str             # 出处指针（事件 id / 行号区间）
```

predicate 首轮白名单（只覆盖 C 族+B 族所需）：`holds(持有) / located_at(位于) / alive(存活) / knows(知悉)`。**predicate 表=尺面，变更须带戳**。

### 3.2 第二层：确定性候选检测（interval_conflicts.py + temporal_checks.py）

**核心思想：先把穿帮从语义判断降维成集合运算，LLM 只处理降维后的残余。**

- **区间重叠冲突**（FactTrack 式）：同一 subject+predicate 两条事实区间重叠且 object 不同 → 矛盾候选（如 ch10 `holds(钥匙, 长老)` 与 ch23 `holds(钥匙, 张三)` 无转移事件衔接）
- **在场冲突**：实体 e 出现在 SceneFrame[ch,k].present，但区间视图无 `located_at(e, 该场景地点)` 且无 arrived 记录 → A 族候选
- **最早可达检查**（B 族，TCSP 思想的最小实现）：实体在 ch_i 场景甲 departed、ch_j 场景乙 present（j>i），中间无 arrived/移动叙述帧 → 空间回卷候选。**不做全 TCSP 求解**——只算"区间是否相邻可行"（当前 198 事件规模下求解器是杀鸡用牛刀，见 §6）
- 输出物统一：`ConsistencyCandidate{ family: A|B|C, chapter, evidence_refs[], rule_id }`——**候选不是定罪**，severity 恒 OBS（I1/I2 不动：L3 永不产 HARD、SOFT/OBS 不阻断）

### 3.3 第三层：判分器（留 sampling/ 旁路，带戳）

确定性层产出的候选 + 账外反证（第二层检索不到解释时）→ 判分：

- **v0.4.1 行号区间 LLM 审读**（已验证形态，区间失守 0/20）：对候选相关场景帧送检，模型只交行号区间、宿主回填（`sampling/level3_pilot.py --v041` 已有实现，直接复用）
- **NLI 判分**（提案引入）：作为 LLM 的**平价对照组**试点，中文 paraphrase 是已知弱项（v0.3"语义摘述披着引文的皮"教训在册）——先跑分布再谈上岗，带戳归档
- **检索增强**（第二层完整形态）：候选触发时按场景索引+实体白名单**先检索后送检**（SEEM 式），替代现在的全章 12288 ctx 硬塞——送检面降一个量级，成本/误报/上下文稀释三面受益
- ConStory-Bench 式输出纪律（与 v0.4 同构）：每条判断必须绑**显式文本证据**（行号区间），无证据不出数

### 3.4 选择性触发（triggers.py）

- **轻档（每章默认）**：区间重叠冲突 + 时序先后硬检查（纯确定性，零 LLM 成本）
- **深档（高风险章触发）**：多线交汇/身份揭露/关键道具转移/时间跳跃/场景切换数超阈 → 追加在场冲突检查 + 判分器送检
- 高风险信号首轮用确定性代理（道具白名单命中、场景切换数、reveal_stage 变更），**不用 LLM 判断要不要用 LLM**
- ConStory 发现在册参考：一致性错误倾向出现在**叙事中段和高熵片段**——触发器按章位加权（中段权高）

## 4. 与现有物的对账（不重复造轮子）

| 现有物 | 关系 |
|--------|------|
| `consistency.py`（L0 账面检查） | 不动；l3/ 消费其通过的 StoryState，管"账与文的一致性"，不管"账内部自洽" |
| `models/fact.py` | 不改；IntervalFact 是投影（区间化在派生层完成，同 inkos  reducer 内 expire 逻辑） |
| `validator.py:830` L3 插槽 | 生产接线唯一入口；前两批不接（纯离线），接线=另批申报 |
| `sampling/level3_pilot.py` | 判分器实现直接复用；v0.4.1 提示词戳原位保留 |
| B5 裁决状态机（已入账） | l3/ 候选可作为 `needs_decision` 的输入源之一（接线=另批，同裁决账接线议程） |
| Oh Story 时间线双视图 / B2 阅读卡 | 作者真相视图=第一层调试界面；读者视图不泄露（已互证） |

## 5. 施工批次（按我方批纪律排）

| 批 | 内容 | 形态 | 前置 | 验证 |
|----|------|------|------|------|
| 0 | **乙′人核 32 条**出精确率 | 体力活（**已批**：tff 2026-10-17「可以批0」） | 无 | 人核记录在册 |
| 1 | `l3/scene_index.py` + `fact_intervals.py` + readout 出口 | **纯派生读数批**（零尺零契约零门禁；写集仅 l3/+readout 接线+tests） | 解冻 | 归档 replay 重算一致；wpe50ch 50 章全量出数 |
| 2 | `interval_conflicts.py` + `temporal_checks.py` + triggers 轻档 | 纯派生读数批 | 批 1 | ch50 三锚点候选必须全中（回归闸）；OK 章候选数分布入册 |
| 3 | 判分器对照试点（v0.4.1 LLM vs NLI），检索增强（先检索后送检） | **旁路试点批**（sampling/ 车道，带戳） | 批 2 候选集 | 精确率/成本/送检面三读数，对照 v0.4.1 基线 |
| 4a | 影子投影：新尺 v4.0 在 sampling/ 旁路对同一批章节重抽（零生产接触） | 旁路试点批（tff 已拍 direction=location 必须入 schema，执行走影子路线） | 批 1–3 读数 | 新旧双跑对照出数 |
| 4b | 平行校准：v3.x vs v4.0 同章对照，恢复跨代可比性 | 读数批 | 4a | 校准读数入册 |
| 4c | 切流：生产账本升 v4.0，历史读数留 v3 表**不删**（分代分表） | **R1 红线，独立拍板**（拍的是切流时点，不是"能不能加字段"） | 4b | tff 拍 |
| 5 | L3 生产接线（level3_fn 传入方）+ B5 裁决账联动 | **WP-0/WP-A 申报批** | 批 4 + 画线（甲/丙终拍） | 链验全绿+真数据冒烟 |
| 6 | TCSP/因果偏序重器 | **暂缓**——50–100 章验收跑（开牌日）后用真实穿帮分布决定 | 开牌日 | — |

每批纪律不变：带戳归档、console 留档、链验基线更新入 roadmap、画线权在 tff。

## 6. 成本与风险（如实）

- **批 1–2 零 LLM 成本**（纯确定性派生）；批 3 本地 32b 零成本（v0.4.1 单跑 ≈50k tokens 在册）；检索增强后送检面预计降 ≥5×（全章→候选场景帧）
- **风险① 区间化误配**：predicate 白名单抽取规则错配→假矛盾。缓释：批 2 只出候选不出数、ch50 锚点回归闸、OK 章分布入册供人核
- **风险② 场景边界切错**：地点/时间跳变识别错→在场索引污染。缓释：SceneFrame 带行号区间出处，一切结论可回原文核（v0.4 出处纪律下沉到派生层）
- **风险③ 尺面蔓延**：predicate 表/触发阈值=新尺面。缓释：全部带戳、变更=读数变更、首批白名单最小化（4 个 predicate）
- **风险④ 过度设计**（TCSP/信念图/fabula）：当前规模不需要，批 6 明确暂缓——**先有真穿帮分布，再决定上不上重器**
- **伦理上限（在册不变）**：真伪唯一终裁=人核抽检；机器全部产出物最高 OBS，画线权恒在 tff

## 7. 参照证据锚点

- 有效区间事实/钩子仲裁/入账即校验：inkos `state/state-reducer.ts`、`utils/hook-arbiter.ts`（deep-dive/inkos.md §3.1–3.4）
- 行号区间+宿主回填+子串核验：inkos `models/observation.ts` + 我方 v0.4/v0.4.1 本地化（level3-fn-calibration-pack §7.7/7.8）
- 时间线双视图/事务纪律：oh-story `tracking_commit.py:617/1095`（deep-dive/oh-story.md §3.2）
- 提案制状态+debt 溯源强制人核：AI-NWA `StateChangeProposal`/`stateProposalSourceQuality.ts`（deep-dive/ai-novel-writing-assistant.md §2.6）
- 关键词触发+预算注入召回：SillyTavern `world-info.js:4709`（deep-dive/sillytavern.md §3.1）
- FactTrack/SEEM/Amory/CO-Narrator/TCSP/ConStory-Bench：提案引入（外部文献，未独立核实，批 3 试点前需核实原文）

## 8. 版本纪律五级（2026-10-17 tff 定调入册）

**问题：字段升级（location 入 schema），历史读数是否全部作废？——不全部作废。作废的是"不再符合新口径的比较资格"，不是历史原文和历史证据。** 五级区分：

1. **原始章节**：不可变审计证据，永不作废（=event sourcing 事件层/数据湖 bronze 层）。**任何历史读数都可用新尺对原文重算重生**——这是"不废历史"的底气（我方 replay 能力同构）
2. **旧版抽取结果**：保留版本、字段和历史用途，分代分表**不删**
3. **新版结构化投影**：用新 schema 版本重新生成，与旧版并存（影子期）→ 校准后切流
4. **新版检测报告**：独立记录**版本三元组**——extractor 版本（抽取尺戳）/ schema 版本 / auditor 版本（审读提示词戳+模型身份）。目前我方只有尺戳一戳，批 4a 起补三元组
5. **历史校准结果**：继续作为旧版本实验记录有效，但**不能冒充新版校准结果**——跨代比较只允许经 4b 重算后的同口径对照

**additive vs breaking 分级**（行业惯例引入）：location 加字段 = **additive**（不改既有字段语义）⇒ 不破生产账本、不废历史读数；旧记录 `location=None` 的语义必须记为**「未抽取」（unknown）而非「不存在」（false）**——与我方 Fact `narrative_truth=unknown` 语义一致，严禁回填假账。breaking（删字段/改语义/改单位）才触发全量重估。