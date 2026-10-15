# WP-D 字段映射表：plot_engine → noveldb 导入通道（开发助手入场券）

> 版本：v0.3（2026-10-15 补齐，问题助手产出）
> v0.1→v0.2 变更：开放问题①按稽核裁决关闭——正文等 S2 §2.3 `novel_chapters` 表，暂存 `state.text` 方案弃用；WP-D 即刻可开工。
> v0.2→v0.3 变更：§3.4 scenes 补读侧数据源缺口注明（ScenePlan 无持久化通道）；行号校正 reading.py:21/:51；§4.1 查重口径对齐 noveldb.py:136。
> 性质：纯离线工作包（collaborator-guide §3 点名），不需要 GPU，不占 @213 车道。
> 写集纪律：**只写 backend/（新导入器模块 + 测试），plot_engine 侧零改动**；新文件创建前须经 tff 确认。
> 读侧均为既有只读接口，本表字段逐一有代码证据。

---

## 1. 读侧接口（plot_engine，只读）

| 接口 | 位置 | 产出 |
|---|---|---|
| `StateStore.load_latest(story_id)` | `plot_engine/store.py:84` | `StateEnvelope(story_id, version, chapter_no, state: StoryState, state_hash)` |
| `StateStore.load_snapshot_at_or_before(...)` | `plot_engine/store.py:95` | 历史快照（导入器只用于校验，不作主数据源） |
| `reading.chapter_texts(dump_dir)` | `plot_engine/reading.py:21` | `Dict[int, {text, findings, guide}]`（正文已剥 markup） |
| `reading.read_run(run_dir)` | `plot_engine/reading.py:51` | 章状态/轮次/桶（导入器取 `status` 过滤，仅导 `OK`/`rewrite_rescued` 章） |

**StoryState 关键字段**（`models/state.py`）：`characters/facts/knowledge_ledger/belief_ledger/reader_ledger/relationships/inventory/locations` + 元数据 `story_id/chapter_no/version/epoch`。
**Character 字段**（`models/entity.py:9-21`）：`character_id(^char_\d{6}$)/name/aliases/gender/status/realm/...`。

## 2. 写侧接口（backend/noveldb.py，既有）

| 接口 | 幂等键（schema UNIQUE） | 用途 |
|---|---|---|
| `Db.upsert_project(title, author)` → project_id | （导入器需自查重：title 一致即复用，见 §4 幂等设计） | 作品行 + `bible` JSON 列 |
| characters 表 upsert | `UNIQUE(project_id, key)` | 人物 |
| chapters 表 upsert | `UNIQUE(project_id, no)` | 章节 + `state` JSON（chapter memory） |
| scenes 表 upsert | `(project_id, chapter_id, ord)` 逻辑去重 | 场景（可选导入，见 §3） |

> noveldb 设计约束（`backend/noveldb.py:5-8`）：单 worker + WAL、JSON 列 TEXT 存储、**所有写接口幂等——重复 sync 不产生重复行**。导入器必须遵守同一约束。

## 3. 字段映射表

### 3.1 projects（作品）

| noveldb 字段 | 来源 | 转换 |
|---|---|---|
| `title` | 导入参数（作品名） | story_id 是机读 id（如 v33r1），**不作 title**；title 由人工/配置给定 |
| `author` | 导入参数 | 默认 `''` |
| `lang` | 常量 | `'zh'` |
| `bible` (TEXT JSON) | StoryState 聚合 | 建议结构：`{"facts": {fact_id: proposition}, "fact_relations": [...], "world": {"locations": [...], "factions": [...], "realms": [...]}, "global_style": "", "source": {"story_id": ..., "epoch": ..., "state_version": ..., "state_hash": ...}}` —— `source` 块必须带，溯源用 |

### 3.2 characters（人物）

| noveldb 字段 | 来源（plot_engine） | 转换 |
|---|---|---|
| `key` | `Character.character_id` | `char_000001` → 原样作 key（已归一、唯一） |
| `label` | `Character.name` | 原样 |
| `gender` | `Character.gender` | 原样（可空） |
| `aliases` | `Character.aliases` | JSON list 原样 |
| `personality` | 无对应 | `[]`（plot_engine 不建人格维度，不编造） |
| `voice_config` | 无对应 | NULL（声音设计归 R7 管线） |
| 附加（可选，进 aliases 或 bible） | `status/realm` | **不进 characters 表**——这些是动态状态，bible 的 world 块或 chapters.state 承载 |

### 3.3 chapters（章节 + chapter memory）

| noveldb 字段 | 来源 | 转换 |
|---|---|---|
| `no` | `reading.chapter_texts` 的章号 | 原样 int |
| `title` | 无对应 | NULL（plot_engine 无章标题概念） |
| `state` (TEXT JSON) | 章级 memory | 建议结构：`{"characters_on_stage": [...], "locations": [...], "knowledge_delta_count": n, "findings": [...], "guide": [...]}`——findings/guide 来自 `chapter_texts`，供下游 continuity_checker 消费 |
| 过滤 | `read_run` 的章 `status` | 仅导 `OK` 与 `rewrite_rescued`；`NEEDS_HUMAN/FAIL/HALT` 不入库（残章不进交付管线） |
| 正文去向 | `text` | **本包只到 chapters 元数据层**；正文等 S2 §2.3 `novel_chapters/novel_paragraphs` 表就绪后由 ebook 管线承载（稽核 2026-10-15 裁决：暂存 `state.text` 会造二次迁移，**弃用**）——开放问题①已关闭 |

### 3.4 scenes（可选，二期内）

**读侧数据源缺口（2026-10-15 补齐注明）**：下表字段目前**没有直接读路径**——ScenePlan 由 `derive_scene_plan(contract, state)`（`plot_engine/derive.py:258`，确定性）在 run 内即席生成，只活在 `ChapterArtifacts`（`plot_engine/live.py:75`）；commit 编排不持久化它（`plot_engine/commit.py` 无 scene_plan 写入，`models/commit.py:27` 仅是 schema 承载位），run dump 也不含。导入器取 scenes 数据只有两条路：(a) 用与 run 同款的 contract+各章 state 快照**重新调用 `derive_scene_plan` 重建**（确定性可复现，但 contract 目前来自 run 输入夹具而非库，需先解决 contract 来源）；(b) 等 plot_engine 侧 scene_plan 持久化（Phase 1，非 WP-D 范围）。**一期按现状：scenes 不导**，本表仅作文档预备。

| noveldb 字段 | 来源 | 转换 |
|---|---|---|
| `ord` | `Scene.seq` | 原样 |
| `setting` | `Scene.location` → Location.name | id → 名解析 |
| `tension` | `Scene.tension` | **定点×1000 → REAL ÷1000**（全表唯一定点转换点，必须显式） |
| `summary` | `Scene.purpose` | 原样 |

**不在导入范围**：`segments/audio_versions/voice_samples/jobs`——属 TTS 生成期产物（R7），plot_engine 无对应数据，严禁编造。

## 4. 幂等设计（对齐 noveldb 约束）

1. project：直接复用 `Db.upsert_project`——其内置查重为 `SELECT id FROM projects WHERE title=?`（`backend/noveldb.py:136`，不含 lang 条件），命中即复用 id，不插新行。
2. characters/chapters：走表级 UNIQUE 键 upsert（`INSERT ... ON CONFLICT DO UPDATE`）。
3. 重导入校验：二次导入后 `SELECT COUNT(*)` 三张表与首次一致 = 零重复行。
4. `bible.source.state_version` 与现库一致时可跳过（增量优化，一期可不做）。

## 5. 验收测试（backend/tests/，无基建则按相邻模式补最小）

- [ ] fixture 导入：用 `plot_engine/tests/fixtures/traitor_arc.json` 或一个 10 章 run 的 `state.db` + `dump/`——断言 characters 数 = `len(state.characters)`、chapters 数 = dump 中 OK/rescued 章数、bible.facts 数 = `len(state.facts)`，**三方对账一致**
- [ ] 幂等：同一 fixture 连导两次，三表行数不变、无报错
- [ ] 过滤：含 FAIL 章的 dump 只导合格章
- [ ] 定点转换：scenes.tension 导入值 = 源值 ÷1000（如 700 → 0.7）
- [ ] bible JSON 可 `json.loads` 且 `source` 块四字段齐全（story_id/epoch/state_version/state_hash）
- [ ] SQL 字段验证：实施时先 `PRAGMA table_info(...)` 核对本表每一个列名（开发规范：SQL 字段必须验证）

## 6. 风险与开放问题

| 项 | 说明 | 处置 |
|---|---|---|
| 正文落点 | noveldb 现 schema 无正文表 | **已裁决（2026-10-15 稽核）**：等 S2 §2.3 novel_chapters 表；暂存 state.text 弃用（防二次迁移） |
| epoch_1 冲击 | epoch_1 后 StoryState 增 character_goals/伏笔台账 | 映射表无需改（走 bible 聚合），但导入器读取应**字段缺失容忍**（getattr 默认），不硬解版本 |
| 多 run 同源 | 同一作品多个采样 run（v33r1/r2/r3） | 导入器需 `--run` 参数指定批次 + bible.source 记录；不自动合并多 run |

## 7. 实施交接

- 交开发助手：本文 + `backend/noveldb.py` + `plot_engine/store.py` + `plot_engine/reading.py` 四个文件即全部上下文；**开放问题①已关闭，即刻可开工**
- 稽核点：新建文件确认、SQL 字段验证、幂等用例、真实 fixture 测试（禁 mock 数据充数）
- 验收后回填：本表 v0.3 记录实施偏差（哪些字段实际不可用）

---

> 开放问题①已由稽核裁决关闭（2026-10-15），本包即刻可移交开发助手开工。
