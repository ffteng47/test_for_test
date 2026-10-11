# Alexandria 产品定位声明与 Phase 1 文笔层接入需求

> 状态：评估结论落盘（2026-10-08，Phase 0 核心状态层交付后商业评估的正式产出）
> 关联：`alexandria-spec-v0.2/`（冻结协议集）、`docs/superpowers/plans/2026-10-08-alexandria-core-state-layer.md`（已执行完毕）
> 本文档不修改 v0.2 协议；它为 Phase 1 立项提供定位与需求边界。

---

## 1. 定位声明（一句话）

**当前实现的 Alexandria 是一台"悬疑/布局型长篇"骨架机——它是小说情节引擎（plot engine），不是小说写手。**

它保证的是"不崩"，不保证"好看"。这不是缺陷，是 v0.2 的设计边界：
设计者在 `中间设计过程.txt`（Phase 1 章节）明确写下——"证明'好看'"属于
Phase 1，且"这一阶段才是真正决定 Alexandria 有没有商业价值"。

两个商业必须分开陈述：

| 商业 | 载体 | 状态 |
|------|------|------|
| 有声书制作 | `backend/` + `frontend/`（QC 工具链） | 已可用，与本文档无关 |
| 小说生产 | `plot_engine/` + alexandria 协议 | **情节引擎已具备；文笔层不存在** |

## 2. 能力谱对照（付费阅读驱动因素 × v0.2 覆盖）

| 付费驱动因素 | v0.2 覆盖 | 依据 |
|---|---|---|
| 长篇剧情不崩（设定/时间线/人物状态） | ✅ 核心能力 | 10 号协议全篇、Phase 0 硬指标 |
| 知识边界与欺诈管理（谁知道什么、读者被误导到什么程度） | ✅ 核心能力 | 03 三本账、REVEALS/LIES/OMITS/HINTS、narrative_truth ≠ objective_truth |
| 伏笔可追踪、必兑现 | ❌ **未实现**（原标 ✅，2026-10-12 勘误） | 类型名在（01 §3）、`foreshadowing: List[str]` 无 ID 无兑现条件、reducer 是显式 no-op（`reducers/plot.py:14`）、抽取通道拒收（`llm_extract.py:163`）。见 `docs/style-acceptance-v1.1.md` §7 |
| 章节目标张力受控 | ⚠️ 仅记录 | tension_target/tension_curve v0.2 全降 SOFT（04 §3.2、CHANGELOG 修改 8），无兑现压力 |
| 章尾钩子 | ⚠️ 仅结构检查 | `<!-- hook -->` 标注存在性 = HARD（05 H5.5），强度值自报无校验 |
| 黄金三章 / 留存 | ❌ 空白 | 无任何读者侧信号回路 |
| 爽点密度 / 情绪兑现 | ❌ 空白 | Emotion Model 未设计 |
| 文笔 / 风格 / 句式 | ❌ 空白 | Writer 层是黑盒 prompt，协议只消费其 markup 标注 |
| 节奏（Scene 级张弛） | ❌ 空白 | Pacing Model 未设计；SP7 仅 SOFT 比对 |

结论：✅ 全部集中在**剧情骨架与认知管理**；❌ 全部集中在**文本体验层**。
引擎独有护城河（知识边界欺诈 + 长篇不崩）与题材强绑定——**长篇悬疑、规则怪谈、
无限流、权谋布局类**。对文笔敏感的都市/言情赛道，该引擎差异化≈0。

## 3. Phase 1 必须接入的部件：文笔层（Prose Layer）

Phase 1 原设计五模型（Reader / Emotion / Pacing / Style / Hook）在本文档中
收敛为一个工程单元——**文笔层**，理由是五者的作用面都在 Draft 文本上，
共享同一条质量流水线：

```text
Plan（Contract，已有）
  ↓
Write（Writer prompt + Style Profile）        ← 新增
  ↓
Critic × N（多维评分：文笔/钩子/情绪/节奏）      ← 新增
  ↓
Revision（质量触发，区别于 06 的违规触发）        ← 扩展
  ↓
Quality Gate（发布阈值）                          ← 新增
  ↓
Publish
```

### 3.1 组件需求（不定义实现，Phase 1 spec 再展开）

| 组件 | 需求 | Phase 0 已有接缝 |
|------|------|------------------|
| **Style Profile** | 每部作品一份"风格圣经"：叙述人称、句长分布、词汇白名单、修辞禁忌、对话风格；注入 Writer prompt；变更走 epoch 升级（09） | Draft 是纯文本通道，prompt 组装点尚未被协议管辖——正好留白 |
| **Critic 多维评分** | 对 Draft 按维度打分（定点 ×1000，复用 05 §5.5 序列化）：文笔流畅、钩子有效性、情绪兑现、节奏偏差；输出 Finding 形状 `{code, ord, severity, detail}` | 05 已有 LLM-as-Validator Level 3 预留位；`backend/rules.py` 同形 Finding |
| **质量修订通道** | 06 Revision 目前只由 HARD/soft 违规触发；需新增"评分低于阈值触发重写/润色"的独立轮次预算，与违规轮分账 | 06 escalation 链（rerun_extraction 等）结构可复用 |
| **钩子强度校验** | `hook strength` 自报值与 Critic 盲测值比对，偏差 > 阈值落 finding；黄金三章设专项 Gate | markup 通道（07 §4.4）与 H2.3 缺标注即 HARD 的机制原样可用 |
| **tension 升级路径** | Phase 1 将 tension 偏差从纯 SOFT 升为 Quality Gate 输入（不升 HARD，避免阻断收敛） | 偏差 > 200/300 落 finding 的比对逻辑已在 04/05 定义 |
| **读者信号回路** | 发布侧指标（完读率/追读率）回流，作为 Critic 阈值与 Style Profile 的调参信号 | Reader Ledger 是认知模型不是体验模型——保持独立，信号回路新建于协议外（DB 层） |

### 3.2 明确不进 Phase 1 的（防止范围蔓延）

- 生产化基础设施（Job Queue/Worker/成本控制器——原设计 Phase 2）；
- 多境界体系并存（10 §8.2 Phase 1 才放开的部分按 08 评审结论另立项）；
- 文笔"生成"的任何协议化尝试——文笔层只管**评估与门控**，生成永远归 Writer
  模型与 prompt；协议不规定句子怎么写。

## 4. 商业验证阶梯（文笔层立项前的三道 Gate）

| Gate | 时点 | 判据 | 不通过的动作 |
|------|------|------|--------------|
| A：可运行 | 08 Day 20–22（10 章实验） | 9 项硬指标全 0；≤3 轮 Revision 收敛率 ≥90%；记录单章成本 `total_cost_usd` | 归因 Extraction → 改走 Writer 直出 markup（07 §4.4 通道），砍四通道抽取层 |
| B：可读性初证 | A 后 +2–3 周 | 30 章悬疑试点（人类只润笔、不动剧情）发免费平台；**完读率/追读率进入同类目前列** | 追读平庸 → 商业形态退为"一致性检查器"工具售卖（H1~H8 Validator 独立可售），不做内容方 |
| C：付费信号 | B 达标后 | 付费转化率与编辑成本测算，决定文笔层投入规模 | C 未过不启动 Phase 1 全量立项，只保留 Critic 单点试验 |

**核心原则：在拿到 Gate B 数据之前，不投入文笔层工程。** Gate A 验证的是
骨架机成立；Gate B 验证的是"骨架 + 人润笔"已可换钱；文笔层的本质是
把 B 里的"人"逐步换成 Critic + Gate，那是 C 之后的事。

## 5. 对 v0.2 协议的影响

无。Phase 0 全部行为保持冻结语义（epoch_0）。
本文档第 3 节即 Phase 1 立项时的需求输入；届时按 brainstorming → spec →
plan 流程另出 `2026-XX-XX-alexandria-prose-layer-design.md`。
