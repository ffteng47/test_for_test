# 项目路线图（层 × 路线对照）

> 版本：v0.2（2026-10-15，按审查意见修订：排期层吸收 phase1-rebaseline-v33 §14–§21 裁定与在跑批次 #68/#69/#70/#78；并行条件改为带撞车矩阵的条件式）
> 性质：诊断级路线文档。所有"现状"条目均有代码/文档证据；"路线"条目为待审方案，确认后才进开发。
> 证据基线：plot_engine 模块诊断（2026-10-15）、alexandria-spec-v0.2（2026-10-08 冻结）、docs/migration-plan.md。

---

## 0. 总路线一张图

```
双轨制：
轨道一（生成侧）plot_engine：协议冻结的内核已建 → 语义层补强 → 质量收敛 → 商业验证
轨道二（交付侧）backend 有声书管线：骨架已建（S2 进行中）→ 接生成侧产物 → TTS/QC/导出 → 读者产品

当前位置：
  轨道一 = 用户四阶段计划的 "Phase 0 收尾 + Phase 2 部分超前 + Phase 1 语义层未开工"
  轨道二 = migration-plan 的 S2（后端骨架+核心移植）阶段，与 plot_engine 未接线
```

---

## 1. 层 × 路线总矩阵

| 层 | 模块 | 现状 | 对应路线 | 路线阶段 |
|---|---|---|---|---|
| L0 契约层 | `models/` + alexandria-spec | epoch_0 冻结（v0.2） | **R0 契约演进路线**：epoch_1 设计（伏笔/人物目标/冲突网络） | Phase 1 前置 |
| L1 状态内核 | `reducer/reducers/store/eventlog/replay/commit` | 完整；plot reducer 为 no-op | **R1 剧情语义路线**：伏笔生命周期、人物目标落账 | Phase 1 主线 |
| L2 判定层 | `validator/derive/sceneplan/classify` | L1/L2 确定性判定完整 | **R2 判定扩展路线**：剧情规则族（H9.x）；L3 LLM 软判定预留 | Phase 1 伴随 |
| L3 修订层 | `revision/revision_actions/rescue` | 归因阶梯 + 人工重入完整 | **R3 定向返工路线**：arc 级自动动作从"升级人工"走向"半自动" | Phase 1→2 |
| L4 生成层 | `llm/llm_writer/llm_extract/writer/live` | 角色路由 + 后置校验完整；无前置约束 | **R4 生成约束路线**：guided decoding 接入（仅治语法病，不治刀锋，§21）；车道已收敛：尺=14b 稠密、升级路径关闭（§19/§21） | Phase 2 前置 |
| L5 测量层 | `metrics/prose_audit/ai_flavor_*/instr_*/reanchor/counterfactual` | 体系最完整，尺号制度化 | **R5 测量运营路线**：50 章压测、lint 扩充、盲测运营 | 贯穿全程 |
| L6 出口层 | `reading/sample/readout/viewer/blind_review` | 内部出口完整 | **R6 交付接线路线**：state.db → noveldb 导入 → 有声书管线 | Phase 2→3 |
| 轨道二 | `backend/`（noveldb/asr_qc/master_audio 等） | S2 骨架阶段 | **R7 有声书管线路线**：migration-plan S2→S3→S4 | 并行轨 |

---

## 2. 各层路线详述

### L0 契约层 → R0 契约演进路线

- **现状**：`models/` 逐字对齐 alexandria-spec-v0.2 十份协议；epoch_0 已于 2026-10-08 重冻结（`09_versioning.md` §2.5）。
- **路线**：
  1. epoch_1 设计稿：伏笔生命周期条目（planted/hinted/due/paid/expired）、人物级目标模型、冲突关系边（`FactRelation` 现为 Phase 0 静态，见 `models/fact.py:31`）。
  2. 契约冻结会：一次性定稿，触发条件 T1/T2/T5（Event 增删、payload 变更、HARD 增删）全部命中，必须升 epoch。
  3. 迁移脚本 + 全量 Replay 验证（V3/V5/V6 强制）。
- **里程碑**：epoch_1 冻结 = Phase 1 全线的开工枪。
- **验收**：迁移后旧 epoch_0 数据只读可 replay（V4/V6）。

### L1 状态内核 → R1 剧情语义路线

- **现状**：四族 reducer（knowledge/belief/world/reader）完整纯函数；`reducers/plot.py` 明确标注 no-op（"语义留给后续计划"）；`state.foreshadowing: List[str]` 仅占位。
- **路线**：
  1. `reduce_plot` 语义化：FORESHADOWING_SET/PAID 落台账，CASE_SOLVED/CONTRACT_* 记弧进度。
  2. 人物目标落账：目标→冲突→代价→后果的事件链在 ledger 可查（对应用户 Phase 1 验收"有原因、有代价、有后果"）。
  3. 弧进度状态机：`active_arc`（`models/state.py:59`）从 Any 升级为结构化弧进度。
- **验收**：planted→paid 全生命周期纯函数单测；replay parity 不回归。

### L2 判定层 → R2 判定扩展路线

- **现状**：沙盒模拟 + HARD/SOFT/OBS 三层判定完整；H5.3 生成守卫与 derive 共用映射表。
- **路线**：
  1. 新增剧情 HARD 族（建议 H9.x）：伏笔逾期未回收（对照 `KnowledgeGate.must_reveal_by_chapter`）、张力曲线偏离、转折点缺席。
  2. L3 LLM-as-validator 软判定（`validator.py` 头部已预留"Phase 0 不接入"）在 Phase 2 接入，仅 SOFT/OBSERVATION。
- **验收**：新规则族触发/不误报各有用例；规则进 `RULE_TO_LEVEL` 归因表。

### L3 修订层 → R3 定向返工路线

- **现状**：Root Cause 八层归因 + 阶梯动作 + `max_rounds=3` + 人工升级；`escalate_to_arc` 目前=人工。
- **路线**：
  1. arc 级半自动动作：弧张力偏离时自动重派生后续章 Contract（挂既有 `derive.py`）。
  2. "阶段性奖励"机制：以弧里程碑（turning point 达成）驱动后续章目标注入。
- **验收**：定向返工后首轮通过率（first_pass）不劣化；trace 全程可回放。

### L4 生成层 → R4 生成约束路线

- **现状**：后置校验链完整但无前置约束；`extra_body` 透传口已在（`llm.py:44`）；温度定点、W5 温度 0。
- **路线**：
  1. extract 角色接 guided decoding（vLLM `guided_json`/`structured_outputs`，Ollama 降级 `format`）——配置面先行，代码面小改。**边界（§19/§21）**：语法约束只消灭坏料类失败；刀锋章类型互翻（BELIEVES↔DOUBTS↔IS_TOLD 竞争同一事实）不受 schema 影响，正解=self-consistency×3 + 型别判据批（#70）。此项为 **instr-v3 尺改**，须走尺戳队列（#68 归档→#69→#70 之后），一因一批。
  2. 模型 bakeoff **已收口**：qwen3 世代 MoE 禁上尺（§18）；qwen3.5:27b temp0 复读退化判负（§19）；qwen2.5:32b 容量闸判负⇒升级路径关闭（§21）。生产双车道 = **尺/生成：qwen2.5:14b @213**（本地 3090 车道上限 14b，§19 WDDM 实测）；Writer 面跨机等价未证（#78 排队闸），过闸前生成长驻 213。
  3. Writer 表面继续按尺号制度迭代（WRITER_SURFACE bump 纪律不变）。
- **验收**：guided 模式**坏料率对比报告**（走 instr 仪器，口径=parse_proposals 实际拒收 reason：`malformed_reply`/`not_an_object`/`unknown_event_type`/`type_not_supported`/`float_in_payload`，含 A 批 `raw_head` 留证）；新旧尺号读数分表不并列；双遍/跨遍比较**须同缓存谱系**（§20 纪律）；读数按 §13 落盘纪律带 `sampling/` 档案路径 + 复现命令。

### L5 测量层 → R5 测量运营路线

- **现状**：体系最完整的一层：决策桶/E2 率、n-gram 复述、AI 味 lint+基线、反事实、重锚、instr 仪器、尺号制度。
- **路线**：
  1. **50–100 章压测**（归属：**§15 预注册商用闸**，门数 E2≥50%/待人工≤30%，非 Phase 0 验收——仪器闸为 10 章 T10=70%）：可追溯/发现违规/状态恢复三条逐条出证据。
  2. lint 规则持续扩充（每条规则 1 正 1 反用例纪律）。
  3. 盲测运营常态化（`blind_review.py` ≥30 章/≥15 失败章下限）。
- **验收**：压测报告 + 盲评工作表 + 答案键分离。

### L6 出口层 → R6 交付接线路线

- **现状**：reading 唯一取数路径，sample/readout/viewer/blind_review 四出口；与 backend 零接线（grep 证据）。
- **路线**：
  1. `state.db → noveldb` 导入器：StoryState → projects.bible + characters；`chNN.md` Draft → chapters。
  2. 幂等导入（对齐 noveldb"所有写接口幂等"约束）。
  3. 导入后交 R7 管线。
- **验收**：fixture 三方对账（人物/facts/章节数）；重复导入零重复行。

### 轨道二 backend → R7 有声书管线路线

- **现状**：migration-plan 阶段 2 进行中（`noveldb.py` 已建：projects/characters/bible/chapter memory/audio 版本）。
- **路线**（按 migration-plan S2→S4 不变）：
  1. S2 收尾：ebook/story 移植、中文提示词三件套。
  2. S3：GPU worker + TTS Provider + 声音工厂。
  3. S4：导出 M4B + Vue 前端 + 端到端验收（20 章 EPUB 全链）。
  4. 接 R6 后：plot_engine 自产小说走同一管线 = Phase 3 读者验证的交付物。
- **验收**：migration-plan 各阶段既有验收标准原样沿用。

---

## 3. 阶段路线（用户四阶段计划 ↔ 项目映射）

| 用户计划 | 项目映射 | 涉及路线 | 当前状态 | 下一步 |
|---|---|---|---|---|
| Phase 0 生产内核 | alexandria Phase 0 | L0–L3 + R5 压测 | 已建成；10 章仪器闸证据在案（§15 T10=70% 预注册），50–100 章压测属商用闸非 Phase 0 | WP-E 压测出商用闸证据 |
| Phase 1 剧情能力 | epoch_1 语义层 | R0→R1→R2→R3 | **语义层未开工**；尺/Writer 面批次线在跑（#68 v4e 三臂、#69/#70 判据批、#78 跨机闸，详见 rebaseline-v33 §14–§21） | 契约冻结会 → WP-A（epoch_1 冻结枪只打语义线） |
| Phase 2 成品质量 | 测量/文风/生成约束 | R4 + R5 + R6 | 部分超前开工（量化依据未载，待补证据） | WP-C/D 并行；WP-B 进尺戳队列 |
| Phase 3 商业验证 | 盲测→读者→付费 | R6 + R7 + 盲测 | 工具已备，数据未启动 | 50 章产物 → 盲评 → 接 R7 |

**顺序律（v0.2 改条件式）**：R0（契约冻结）是 R1/R2/R3 的硬前置；R4/R5/R6 **并非无条件并行**——凡触碰
`llm_extract.py`/`review.py`/尺戳或需 213 生成车道的工作流，须避开在跑批次窗口（见 §4 撞车矩阵）；
真正无前置并行的只有 R5-lint（WP-C）与 R6/R7（WP-D，backend 零接线已证）；R7 全程并行、在 R6 后汇合。

---

## 4. 工作包路线（并行分工 → 本图的执行层）

| 工作包 | 对应路线 | 写集 | 前置 |
|---|---|---|---|
| WP-0 集成中枢 | 全部（仲裁） | live/review/experiment + spec CHANGELOG | 写集含 `review.py`——与 #69(a) 撞面，须窗口外改或错面 |
| WP-A 伏笔生命周期 | R0+R1+R2 | models（冻结窗口）/reducers/plot/validator 规则族 | 契约冻结；且 models/ 变更须待 #68–#70 三跑归档（可比性依赖现行冻结面） |
| WP-B guided decoding | R4 | llm.py + llm_extract + 测试 + router 配置 | **尺戳队列**：instr-v3 尺改，一因一批，施加窗口 = #68 归档→#69→#70 之后；与两批共用 `llm_extract.py` |
| WP-C 文风 lint | R5 | ai_flavor_lint.py + 测试 | 无（正交已证，可真并行） |
| WP-D noveldb 导入 | R6 | backend 新导入器 + 测试 | 无（backend 零接线已证，可真并行） |
| WP-E 50 章压测+盲测 | R5/§15 商用闸 | sampling/ + docs 报告 | **tff 显式放行 + 213 生成车道窗口**（单车道，被 #68→#69→#70→#78 串行占用） |

### 撞车矩阵（v0.2 新增，2026-10-15 实况）

| 文件/资源 | 占用批次 | 声称并行的 WP | 判定 |
|---|---|---|---|
| `llm_extract.py` | #69(a)、#70(b12) | WP-B | 冲突（文件+尺戳双撞） |
| `review.py` | #69(a) | WP-0 | 冲突 |
| `derive.py` | #70(b3) | WP-A | 低度撞 |
| `tests/test_instr*` | #69、#70 | WP-B | 冲突 |
| 213 生成车道 + `sampling/` | #68→#69→#70→#78 | WP-E | 冲突（单车道+放行制） |
| `models/`（ladder-v4 冻结面） | #68–#70 可比性依赖 | WP-A | 窗口冲突 |
| `ai_flavor_lint.py` / `backend/` | 无 | WP-C / WP-D | **正交，可真并行** |

---

## 5. 风险登记（路线级）

| 风险 | 影响路线 | 缓解 |
|---|---|---|
| epoch_1 设计质量不足 → 全线返工 | R0–R3 | 设计稿先审后冻，一次定稿 |
| 50 章压测暴露长尾（CAS 冲突/快照膨胀） | R5/L1 | 压测报告先行，问题分级再修 |
| Ollama guided 能力弱于 vLLM | R4 | 双路径设计，配置切换 |
| 导入通道遇上 epoch_1 schema 变更 | R6 | WP-D 与 WP-0 对齐 epoch 时点 |
| 读者验证样本不足 | Phase 3 | 盲测下限纪律已内置（blind_review） |

---

> 本文档待审。审查意见以批注形式给出后，按意见更新版本号与内容；实施层面的代码改动一律走开发助手 + 稽核流程。
