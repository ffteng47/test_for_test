# R8 #2 爽点工程——拍板材料包

> 版本：v0.1（2026-10-17）。产出：需求澄清助手（本会话惯例格式＝ `docs/freeze-meeting-and-r8-briefs.md` 材料一~四：每题=选项+代码坐标证据+推荐+一句影响面）。纸面材料，零代码承诺。
> 定位：R8 入队序第 2 项（确认闸已收口 roadmap v0.14；入队序裁定 roadmap:112）。承接面 = **WP-A（R1 语义层是地基，不另起炉灶）**（roadmap:113）。
> 前提更新（相对 briefs 当日）：① WP-A v3.8 码批**已收口落库**（roadmap v0.13，链验 554）——epoch_1 契约已生效，`ArcProgress` 已随裁定 6A 冻字段（`alexandria-spec-v0.2/09_versioning.md:56-57`："字段先行、语义后置"，路由语义 epoch_2）；② 尺面现行 **v3.9-is-told-reattach**（`plot_engine/llm_extract.py:61`，briefs/roadmap 旧文写 v3.8@:49 已漂移）；③ `plot_engine/` 全冻结已解除（WP-E 收口，roadmap:167），但指南 §2「批次在跑时勿改尺面/仲裁面」与一因一批纪律不变（`docs/commercial/collaborator-guide.md:9`）；④ S 批已开批收口（roadmap v0.25，2026-10-17），当前无在跑生成批——爽点工程码批若要采样验收，仍需 tff 放行 GPU 批。
> 纪律：本文只做取证与选项摆布，不预写任何实现。

---

## 0. 坐标勘误总表（briefs 材料二②原文坐标 → 2026-10-17 现位）

| briefs 原文坐标 | 内容 | 现状 |
|---|---|---|
| `plot_engine/models/state.py:59` | `active_arc: Optional[ArcProgress]` | **已漂移**：现位于 `state.py:62`；`ArcProgress` 类本体在 `models/ledger.py:98-104`（`tension_actual: List[int]` 在 :103，注释即写明"R8 爽点工程承接位"） |
| `plot_engine/llm_extract.py:49,53`（尺戳/PAYLOAD_SCHEMA） | 尺面红线坐标 | **已漂移**：`EXTRACTION_RULER` 常量现位于 `llm_extract.py:61`（值 v3.9）；`PAYLOAD_SCHEMA` 现位于 :65（:49-60 为版本注释，v3.8 伏笔 payload 注记在 :50-55） |
| `plot_engine/derive.py:129,204,283`（三级张力链） | curve→contract→scene | **已漂移**：现位于 `derive.py:130`（取曲线本章值）、`:246`（写 `tension_target`）、`:325`（写 `scene.tension`） |
| `models/contract.py:35,131` | tension_curve / tension_target | :35 仍准；`tension_target` 现位于 **:142** |
| `models/contract.py:89`（章尾钩子存在性） | ChapterHook | **已漂移**：`ChapterHook` 类现位于 `contract.py:100-104`，`ending` 字段在 :145 |
| `04:343` = `sceneplan.py:18` | beat_type 五值 | `sceneplan.py:18` 仍准；04 协议内现位于 **:346** |
| `04:77-80,391`（R3'-R6'/SP7 SOFT） | 伪定量先例 | :77-80 仍准；SP7 现位于 **04:394** |
| `04:59,164,366`（张力 schema 三处） | — | :59、:164 仍准；Scene.tension 现位于 **04:369** |
| `05:76-79`（H5.5）、`04:246`（W7） | 钩子判定 | H5.5 现位于 **05:81-84**（05:74-79 已被 v3.9 的 H5.3 双判据注记占据）；W7 现位于 **04:249** |
| `blind_review.py:16-17`（章级表） | 出口候选 | 欠准：:16-17 是出题下限常量（MIN_CHAPTERS=30/MIN_FAILURES=15），章级工作表构造在 `pool()/build()`（:20-46）——**该表是人工盲评工作表，非统计出口**（见题3） |
| `docs/epoch1-foreshadow-design.md:18,122` | ArcProgress 预留 | 仍准；且该设计稿**已冻结并实施落库**（roadmap v0.13），:122 的"预留"已成真字段（`ledger.py:103`），仅无写入方 |
| roadmap:113 承接映射 | 爽点工程→WP-A | 仍准 |
| `r8:12`（双通道）、`r8:46`（旧序）、`r8:65-73` | 商业原文 | 仍准（旧序 :46 已被 roadmap:112 覆盖，待 errata 一事 briefs 已记，非本题议题） |

现调新证据（briefs 未列）：H9 族已在码（`validator.py:549-577`，H9.1 hard/H9.3 soft/H9.4 observation）；`RULE_TO_LEVEL` 现位于 `revision.py:42-60`（H9 已登记 :57）；hook markup 解析器 `markup.py:14`（正则含 `strength=\d+`）、`_hook_ok` 判定 `validator.py:538-546`；`metrics.py` 全文无 tension/hook/beat 读数（briefs 断言复核仍成立）；`readout.py/viewer.py/sample.py/reading.py` 无曲线出口（grep 零命中，唯一消费点在 Writer 提示词 `llm_writer.py:67`）；plot_engine 内无「黄金三章/爽点/付费卡点」任何代码锚（grep 仅 "density" 误中）；`reducers/plot.py` 对 `active_arc` **零写入**（文件全貌只处理伏笔三事件，CASE_SOLVED/CONTRACT_* 仍 no-op :70）。

---

## 题1 情绪类型词表选哪个（逐字：「情绪类型词表选哪个：复用 Beat.beat_type 五值、新建叙事情绪枚举、还是借交付侧 `backend/emotion_map.py:1,68` 的词表？三者现互不相通（后者量的是 TTS 音色情绪，非剧情爽点）——不定此项，『每章情绪类型落台账』无落点。」）

**取证**：
- 五值节拍枚举：`models/sceneplan.py:18`（`setup/pressure/turn/release/foreshadow`），协议同源 04:346。但 ScenePlan **不进 Event Log、不是 Contract**（`sceneplan.py:3-4` 头注）——它是规划产物，落不了"每章实读情绪类型"的账。
- ArcContract 另有 `reader_beats: List[dict]`（SOFT 元数据，Phase 0 不进 Validator，`models/contract.py:39`、04:64）——无类型约束的开放槽。
- `backend/emotion_map.py:22-42`：16 类 EMOTIONS（calm/sarcasm/…/smug/daze），量的是**TTS 段落演绎情绪**（instruct⇄emotion 双向量化，:1-11 头注），词表和 intensity 标度都为配音服务，与剧情爽点是两套语义；且 plot_engine→backend 现零依赖（roadmap L6"与 `backend/` 零接线"），借词表=跨轨反向依赖。
- 01 Taxonomy 现 21 事件型（`models/event.py:8-23`）无任何情绪/爽点型。

| 选项 | 内容 | 代码落点 | 动尺? | 动契约面? |
|---|---|---|---|---|
| A | **首期复用 beat_type 五值**：爽点"类型"维度=既有规划层 beat 分布读数（pressure/turn/release 计数），不新建词表 | 读 `models/sceneplan.py` 产物（state.db/归档），报表在测量层新增；**零 schema 改动** | 不动 | 不动 |
| B | 新建叙事情绪枚举（落 Contract/ScenePlan/台账字段） | `models/contract.py` 或 `models/ledger.py` 加字段 = **契约面增项**（按冻结会材料一 #6/Q4 同一口径执行 **T2**；须上冻结会/裁定批）；若要"每章实读"落账还需事件型 = T1 = 升 epoch | 不动尺（除非 B+抽取，见题5 红线） | **动契约面（T2）** |
| C | 借 `emotion_map.py` 16 词表 | 跨轨依赖 backend→plot_engine；语义错位（音色≠剧情爽点） | — | 不推荐否决 |

**推荐**：**A（首期）**——"类型"先以 beat_type 分布承接，零新面；B 仅在 tff 坚持"每章情绪类型**实读**落台账"时启用，且必须单拍 T2 批（禁塞进报表批）；C 否决（两套语义，硬接=双标）。**影响面一句话**：A 零契约零尺改动、报表即得；B 把爽点工程直接挂回冻结会契约面，首期交付被 epoch 批卡死。

---

## 题2 爽点密度进不进闸（逐字：「爽点密度进不进闸：只出报告（对齐 R3'-R6'『伪定量不阻断』先例，`04:82-83`），还是进评审门禁？若进门禁，是 HARD 还是 SOFT finding？——决定 validator 是新增规则族还是 metrics 加列。」）

**取证**：
- 先例原文（04:82-83 复核逐字）：「v0.2 理由：伪定量规则会把小说倒过来拟合数字。R3'~R6' 供 Phase 1 Critic 使用，Phase 0 一律不阻断 Commit」——R3'-R6'（04:77-80）全部 SOFT 只落 finding；SP7 同源（04:394、实现 `plot_engine/sceneplan.py:126-130`，偏差>300 只 SOFT）。
- validator 三层判定先例：`Finding.severity ∈ {hard, soft, observation}`（`validator.py:31`）；SOFT/OBS 不阻断的成例即 H9.3/H9.4（`validator.py:566,571`）；**HARD 新增 = T5 = epoch 升级触发**（`09_versioning.md:61-66`；H9.1/H9.2 当年正是靠 T5 进的 epoch_1，09:46-47）。
- 新 SOFT 规则登记面：`revision.py:42-60` `RULE_TO_LEVEL`（归因表，validator.py 内无此表——briefs 材料一已注明该坑）。

| 选项 | 内容 | 代码落点 | 动尺? | 动契约面? |
|---|---|---|---|---|
| A | **只出报告**（不进任何闸） | 测量层 `metrics.py` 加列或新报表模块 + 出口层接线；validator 零改动 | 不动 | 不动 |
| B | 进 validator 但 **SOFT** 只落 finding | `validator.py` 新规则族（如 H10.x）+ `revision.py` RULE_TO_LEVEL 登记 + 1正1反用例（指南 §3） | 不动尺 | 不动契约面（05 勘误/CHANGELOG 文档批） |
| C | 进 validator **HARD** 门禁 | 同上但 T5 命中 ⇒ **升 epoch**（epoch_2 批），阻断 Commit | 不动尺 | **动（T5→epoch）** |

**推荐**：**A（首期），B 留作二期**——密度是典型伪定量，04:82-83 的"倒过来拟合数字"警示一字未过时；C 否决：新增 HARD=epoch 级动作，且把 SOFT 降档史（v0.2 整族降档）倒着走。**影响面一句话**：A 只碰测量层一个码批；B 加归因表一行+两用例；C 把爽点工程塞进 epoch_2 大车，排期失控。

---

## 题3 钩子命中率怎么算（逐字：「钩子命中率怎么算：H5.5 已判『markup 存在且 type==contract.ending.type』；命中率还需 strength 达标吗（`ending.strength` 现 SOFT，`04:190`）？统计出口挂 R5 测量层新报表，还是并入 `blind_review.py:16-17` 的章级表？」）

**取证**：
- H5.5 现判据（`validator.py:466-470,538-546`；05:81-84；04:249 W7）：末 3 段内**恰好一条** `<!-- hook: {type} strength={0..1000} -->`、type==contract.ending.type、strength 仅做值域检查（:544）——**与 contract.ending.strength 不做比对**，达标语义现在不存在。
- `ending.strength` 字段语义=SOFT"供 Critic 评估"（`models/contract.py:103`、04:190）；derive 已把 ending 原样带进 Chapter Contract（`derive.py:246`），规划侧强度账**已有**。
- 出口候选辨析：`blind_review.py` 是**人工盲评出题器**（:1-9 头注：打散去出处、答案键分离），不是统计出口——把机检读数并进人评委表=污染解耦纪律（:3-5 明言两读数必须解耦）。机检统计的家在测量/出口层（`metrics.py`/`readout.py`）。

| 选项 | 内容 | 代码落点 | 动尺? | 动契约面? |
|---|---|---|---|---|
| A | **命中率=H5.5 PASS 章占比**（存在+type 匹配即"命中"），strength 分布**另列观察值**不比达标 | 新报表列（`readout.py` 或 `metrics.py`），纯读 `markup.py` 已解析的 HookAnno.strength | 不动 | 不动 |
| B | 命中率加 **strength≥contract.ending.strength 偏差线**（如 ≥ 目标−200，对齐 D2'/H7.3 偏差先例 04:197、validator.py:642-647） | 若只进报表=不动尺；**若进 H5.5 判定=改 HARD 判据=协议变更**（先例：材料三"H5.3 判据改动=协议变更"；HARD 语义增删触 T5） | 不动抽取尺；但改判据=动**仲裁面**（validator），批需单独走 | 视口径：报表不动；判据=T5 候选 |
| C | 并入 `blind_review.py` 章级表 | 违背该模块解耦头注 | — | 否决 |

**推荐**：**A（首期）**——命中率维持 H5.5 同谓词（尺判什么报表算什么，零双标），strength 达标做**观察列**不做判据；B 的判据化等报表读数攒出阈值依据再议（届时按材料三纪律上冻结会）。C 否决。**影响面一句话**：A 纯读数批；B 改判据要重演 v3.9 那场"改尺需三采样分表"的成本，首期不值。

---

## 题4 实测曲线落 ArcProgress 还是另起字段（逐字：「实测曲线落 ArcProgress 还是另起字段：爽点工程的『规划 vs 实测量』偏差账，是直接用 epoch_1 待冻的 `tension_actual: List[int]`（则本项与冻结会议程 #6 联动、零新契约面），还是 ScenePlan/Contract 加字段（= T2，须赶在冻结会前入议程）？」）

**取证**（briefs 写于 WP-A 收口前，现状已变）：
- **"待冻"已成真**：裁定 6A 落库（roadmap v0.12-13），`ArcProgress` 含 `tension_actual: List[int]`（`models/ledger.py:98-104`）、`turning_points_hit`（:104 同类）、`state.active_arc`（`state.py:62`）——**字段面零新增即可承接**，09:56-57 生效记录白纸黑字"ArcProgress 只冻字段，路由语义 epoch_2"。
- **无写入方**：`reducers/plot.py` 不碰 `active_arc`（全库 grep：`active_arc` 除模型定义外零读写）——落"实测量"需新增写路径。写路径若走 reducer=**T6「Reducer 语义变更」**（09:66）→ epoch 级；若走非事件派生=破坏 replay 确定性（StoryState 参与 `state_hash`，`state.py:70-77`）——**台账写入必须事件溯源，无免费通道**。
- `turning_points_hit` 同样零写入方（grep 仅定义处）。

| 选项 | 内容 | 代码落点 | 动尺? | 动契约面? |
|---|---|---|---|---|
| A | **复用 `tension_actual`，但首期不落账**——偏差账先做离线报表（从归档/dump/state 现算规划 vs 实读），台账写入留二期"语义启用批" | 报表层零契约面；二期写账=新事件型（T1）或 reducer 扩展（T6）→ **epoch_2 议程项，非本包议题** | 不动 | **不动**（字段已冻，读不写零风险） |
| B | 复用 `tension_actual` 且首期就写账 | `reducers/plot.py` 或新事件驱动写入 = T6/T1 → epoch 升级 + replay parity（V6）全套 | 不动尺 | **动（T6→epoch_2）** |
| C | ScenePlan/Contract 另起字段 | 契约面增项 = T2 口径（briefs Q4 原话），且与已冻 `tension_actual` 双写漂移——正是 D11 单源纪律要防的（04:207 先例） | 不动尺 | **动（T2），且制造重复账** |

**推荐**：**A**——briefs 设想的"零新契约面"兑现了（6A 先见），但"零契约面≠零账"：写账欠着 T6/epoch_2 的债，首期用离线报表把偏差账**先读出来**，`tension_actual` 作为未来落账位预留并在报表口径里对齐（同名同标度 ×1000，免二次翻译）。C 否决（双写漂移）。**影响面一句话**：A 首期不动任何面只加读数；B 把爽点工程变成 epoch_2 开幕战；C 花 T2 的钱买一个已有抽屉。

---

## 题5 要不要动抽取面：派生还是抽取（逐字：「要不要动抽取面：爽点读数若全从既有 ledger/Contract/ScenePlan 确定性派生 = 非尺面；若要新增『从正文抽取爽点/情绪标记』则触 `PAYLOAD_SCHEMA`/markup = 尺面变更，与 WP-A v3.8 撞一因一批（`plot_engine/llm_extract.py:49,53`；须知 §1.2）——**tff 须先答：派生还是抽取？**」）

**取证**（红线坐标现势；原文坐标 :49,53 已漂移，见 §0 表）：
- 抽取面 = `EXTRACTION_RULER = "v3.9-is-told-reattach"`（`llm_extract.py:61`）+ `PAYLOAD_SCHEMA`（:65 起）；凡改其读出语义=尺面变更：一因一批 + bump + 新旧分表（指南 §1.2 `collaborator-guide.md:9`；先例链 v3.6→v3.8→v3.9 全程分表，09:54-55）。
- 既有**确定性派生源已够首期读数**：三级张力标量链全通（`derive.py:130→:246→:325`；schema 04:59/:164/:369=`models/contract.py:35,:142`、`models/sceneplan.py:42`）；beat_type 五值（`sceneplan.py:18`）；turning_points 五型（04:45-50=`models/contract.py:23-27`）；钩子存在性+strength 已由 **markup 通道**确定性可判（`markup.py:14` 正则、H5.5 `validator.py:538-546`）——**markup 是 Writer 自标注通道（07 §4.4），不是抽取面**，扩 markup 不等于动尺，但等于加判据输入（需 07/05 协议文本批，参照钩子先例走裁定）。
- "从正文抽取爽点/情绪标记"现无任何事件型承接（`models/event.py:8-23` 21 型零爽点位）。

| 选项 | 内容 | 代码落点 | 动尺? | 动契约面? |
|---|---|---|---|---|
| A | **全派生**（首期）：爽点读数=既有 Contract/ScenePlan/ledger/H5.5 读数的确定性组合 | 测量层新报表 +（可选）`reading.py/viewer.py` 出口接线；**`llm_extract.py` 一字不动** | **不动**（EXTRACTION_RULER 维持 v3.9，无 bump 无分表债） | 不动 |
| B | 扩 **markup 通道**（Writer 自标注 `<!-- beat: 爽点类型 -->` 类） | `markup.py` 正则 + 07 §4.4/05 协议文本 + validator 新判据；不动 PAYLOAD_SCHEMA，但新判据=仲裁面变更（Writer 提示词面同步=生成面变更，WRITER_SURFACE bump 纪律 roadmap :105） | 不动抽取尺；**动 Writer 面**（需单独批） | 协议文本批（05/07） |
| C | 新增「从正文抽取爽点/情绪标记」事件族 | `models/event.py`（T1）+ **`llm_extract.py:65 PAYLOAD_SCHEMA` 键名面 = 尺面变更**：EXTRACTION_RULER v3.9→v4.0 bump、`test_instr.py` 尺戳用例、新旧读数分表、且 T1+T2 触发 **epoch 升级**（09:62-63）；与 WP-A 的"撞一因一批"已随 WP-A 收口失效，但**须单独拍板**的历史纪律不变——现势：**这是 epoch_2 议程，不是爽点工程批内议题** | **动尺（红线）** | **动（T1/T2→epoch）** |

**推荐**：**A（首期），且 C 明确列为需单独拍板的红线项**。briefs 原话"tff 须先答派生还是抽取"——本包给的判定是：首期可派生的东西比想象的多（钩子连 strength 都已在 markup 通道确定性可判），"抽取"路线的独占价值只剩**正文内在场爽感语义**（事件账表达不了的部分），那一半属于 epoch_2 的 T1 大车，不该由爽点工程报表来开车。B 作为二期观察项（Writer 自标注的可靠性先例是 hook，而 hook 判据至今靠存在性不靠自觉质量）。**影响面一句话**：A=零尺零契约纯报表批；C=尺戳 bump+分表+epoch 升级三债同晚到期，必须独立拍板。

---

## 题6 双通道验收线（逐字：「双通道验收线：R8 商业终点为网文连载+有声双通道（`r8:12`），爽点密度/黄金三章阈值按哪个通道定首版验收？两通道标准不一致时听谁的？」）

**取证**：
- 商业原文：`r8:12`（双通道=网文平台连载付费+有声书付费，互为放大器）、`r8:14`（"**本路线只覆盖『接入网文平台』侧的新增需求**。有声书通道沿用现有 audiobook 流水线"——爽点工程的需求源头全在网文侧）、`r8:62`（§4.1 验收需求级原文："连续 N 章可输出『情绪曲线+爽点分布+钩子命中率』报告，且每章标注可追溯至细纲承诺"——注意：**验收定义里没有任何通道阈值**，只有"可输出+可追溯"）。
- 代码面：plot_engine 内"黄金三章/付费卡点"**零锚**（grep 零命中）——阈值现在无处执行，写在哪都属新造面；有声侧既有节奏账在交付轨（`docs/post-production-plan.md` 审听工位），与爽点工程的账不同层不同库（`backend/emotion_map.py` 见题1）。
- 两通道"标准不一致"的实际形态：网文侧=前 N 章钩密度/卡点位置（运营经验值，无内部数据校准）；有声侧=悬念停留/停顿节奏（听感，人工闸判）——**首期根本没有可比的两套数**。

| 选项 | 内容 | 代码落点 | 动尺? | 动契约面? |
|---|---|---|---|---|
| A | **首版验收线按网文通道定，且只定 r8:62 的"可输出+可追溯"线**（报表存在性、章级可追溯性），**不钉阈值数值**——阈值等第一批真实曲线读数出来再拍 | 出口层报表（题2A 同批）；不新增判据 | 不动 | 不动 |
| B | 首版就钉黄金三章/爽点密度阈值（数值进 validator 或报表红绿灯） | 数值进闸=题2 B/C 路径重演；进报表观察=可行但阈值来源无据（内部数据 0 批） | 不动尺 | 视口径 |
| C | 双通道各定一套验收线 | 有声侧要接 `backend/` 判据=R6/R7 接线未成的现状下空头支票（roadmap L6：零接线） | 不动 | 不动但空转 |

**推荐**：**A**——需求文档自己把"本路线只覆盖网文侧"（r8:14）和验收线（r8:62）都写成了通道中立的输出能力线，首期就照它执行；"两通道不一致听谁的"随 A 自然消解：**账本单一（plot_engine 台账），通道各自消费**——有声通道经 R6 接线后读同一条曲线，不另立词表不另立账（题1 否决 C 的同一条理由）；阈值分歧将来出现时按"需求源头在哪个通道哪个算"裁定=网文侧定规划红线、有声侧只做听感观察列。**影响面一句话**：A 零新增面、把阈值决策推到有数据之后；B 是"倒过来拟合数字"先例（04:82-83）的商业版翻车路径；C 在未接线的轨道上画饼。

---

## 最小可实施方案候选（全题取最保守组合：派生 + 不进门禁 + 复用既有字段）

**组合**＝题1A + 题2A + 题3A + 题4A + 题5A + 题6A。零尺面、零契约面、零 epoch、零 validator 判据改动、零 GPU。首期交付物是一张**离线「爽点工程读数表」**（章/卷两级），从既有确定性源派生：

| # | 交付读数 | 数据源（全部现成，只读） | 涉及文件（写集） |
|---|---|---|---|
| 1 | 规划张力曲线 vs 章内承诺：`arc.tension_curve[idx]` ↔ `contract.tension_target` ↔ 各 `scene.tension` 逐章三列 | `derive.py:130/246/325` 已写入的既有产物（state.db/归档/fixture dump） | 新增读数函数：`plot_engine/metrics.py` 扩列（或经 tff 确认新文件 `plot_engine/tension_readout.py`——新建文件需点头） |
| 2 | 钩子命中率（=H5.5 同谓词 PASS 章占比）+ 钩子 strength 观察列（分布，不比达标） | `markup.py:14` 解析产物、`validator.py:466-470` 判据结果 | 同上 + 出口接线 `plot_engine/readout.py`（md 报表列） |
| 3 | 爽点密度分布：章级 beat_type 计数（pressure/turn/release/foreshadow/setup 五桶）+ Scene 数×Beat 数分母 | ScenePlan 既有产物（`models/sceneplan.py:18`） | 同上 |
| 4 | 转折点兑现观察：`turning_points` 五型规划位 vs H5.1/H5.3 既有 finding 读数（**只并列展示，不新建"命中"判据**——命中账本属题4 二期 `turning_points_hit` 写入批） | `validator.py` 既有 finding、`metrics.py` dump 读数面 | 同上 |
| 5 | R3'-R6' 伪定量观察行（注水/疲劳/高峰稀缺/转折低张力——从 v0.2 "供 Critic 使用"的悬置状态搬进**报表**，不搬进闸） | `arc.tension_curve` 纯计算（04:77-80 逐条复算） | 同上 |
| 6 | 卷级聚合视图（章报表求和/滑窗） | #1-#5 输出 | 同上 |

**验收**（照 r8:62 逐字）："连续 N 章可输出情绪曲线+爽点分布+钩子命中率报告，且每章标注可追溯至细纲承诺"——追溯键=既有 `derived_from`（`models/contract.py:148`、04:202 D7）现成在账；样本可直接用已归档的 `sampling/ep1v39pv2c-r2`（S 批 r2，E2 判是批）与 wpe50ch 存量，**不开新 GPU 批**。用例纪律：读数函数 1 正 1 反钉进 `plot_engine/tests/`（指南 §3）。

**明确不含**（都欠着独立拍板债，防搭车）：任何台账写入（`tension_actual`/`turning_points_hit` 落账=T6/epoch_2）；任何新枚举上契约（题1B=T2）；任何 markup 新标注（题5B=Writer 面+协议批）；任何抽取新事件族（题5C=尺面红线，v4.0 bump+分表+T1 升 epoch）；任何阈值进门禁（题2B/C、题6B）。

**tff 一句话拍板模板**：「爽点工程首期=全派生离线读数表（题1A/2A/3A/4A/5A/6A），零尺零契约零门禁，台账落账与抽取红线项各自单列待批」——拍板即出码批写集（预计 1-2 文件 + tests）。

---

*索引：题1 词表（3 选项）·题2 进闸（3）·题3 命中率（3）·题4 承接位（3）·题5 派生vs抽取（3，红线单列）·题6 双通道（3）。坐标全部 2026-10-17 当日打开核对，漂移项见 §0。确认闸（R8 #1）已收口不入本题；材料一~四既有裁定不重问。*

---

## 稽核验证记录（2026-10-17，随审查报告修正回写）

1. **「全库零写入方」取证命令与结果**：
   ```
   grep -rn "tension_actual" plot_engine/ backend/ --include="*.py"
   ```
   全库仅 1 处命中=定义行 `plot_engine/models/ledger.py:103`（字段默认值 `List[int] = []`，含注释
   「R8 爽点工程承接位」）；排除定义/注释后的写方检索为空 ⇒ **零写入方成立（含 tests 与 backend）**。
2. **证据引用勘误**（稽核严重项）：收口播报曾把三处抽查写成一行括号列举，读起来像
   `ledger.py:103` 兼证 MIT——更正为两条独立证据：
   - `plot_engine/models/ledger.py:103` = tension_actual 承接位 + 全库零写入方；
   - `refrence_projects/oh-story-claudecode/LICENSE:1`（"MIT License"，独立文件）= WP-F 许可证核实。
3. **链验现跑**（稽核⚠项补实）：plot_engine **585 passed**、backend **10 passed**（2026-10-17，
   本包落库后无码改，纯文档修正不影响基线）。

---

## 拍板记录（2026-10-17，tff）

**裁定：六题全部按推荐选项确认 = 全-A（题1A/2A/3A/4A/5A/6A）；未验证的其他选项不一票否决，
逐题登记为保留选项，保留后续选择的可能性。**

- 首期执行面 = 「最小可实施方案候选」全-A 组合：离线爽点工程读数表（6 项读数），
  写集 = `plot_engine/metrics.py` 扩列 + `plot_engine/readout.py` 出口接线 + tests 一正一反；
  **不新建文件**（§最小方案中「新文件 tension_readout.py 需点头」未获点头，按不建处理）。
- 保留选项登记（未实施≠废弃，重提条件注明）：
  - 题1B 叙事情绪枚举上契约 = **T2 单独拍板债**，重提条件=tff 要求「每章情绪类型实读落台账」；
  - 题1C 借 emotion_map 词表 = 保留但记语义错位否决理由（音色≠剧情爽点，跨轨反向依赖）；
  - 题2B SOFT 进 validator = 二期候选，重提条件=报表读数攒出规则需求；题2C HARD = T5/epoch 债；
  - 题3B strength 达标判据化 = 重提条件=观察列读数先出阈值依据（届时按材料三纪律上冻结会）；
  - 题4B 首期写账 = T6/epoch_2 债，重提条件=epoch_2 批开；题4C 另起字段 = 保留但记 D11 双写漂移否决理由；
  - 题5B markup 自标注 = Writer 面+协议批，单独拍板；**题5C 抽取爽点事件族 = 尺面红线，永久单列**（v4.0 bump+分表+T1 升 epoch 三债），本裁定不覆盖；
  - 题6B 首版钉阈值 = 重提条件=第一批真实曲线读数落地；题6C 双通道各定线 = 保留待 R6/R7 接线。
- 验收线照 r8:62「可输出+可追溯」，不钉阈值数值；样本用归档
  `sampling/ep1v39pv2c-r2` + `sampling/wpe50ch` 存量，**不开新 GPU 批**。

**首期兑现（2026-10-17，commit af7e923）**：读数表已落 `plot_engine/metrics.py`（`thrill_table`/`r3r6_flags`）
+ `plot_engine/readout.py --thrill` 出口；写集=packs 承诺的 metrics+readout+tests，零新文件（读数模块内联 metrics）、
零尺零契约零门禁、只读消费夹具公开派生面（replay 归档 state/event.db 重建 pre-state，不可得章记「-」不入分母）。
复现：`PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m plot_engine.readout sampling/ep1v39pv2c-r2 --thrill`
（50ch 加 `--fixture=experiment_50ch`）。首跑读数：S 批 r2 钩 10/10、strength [500..900]、
规划↔契约偏差恒 0（derive 单源所致，符合预期）；wpe50ch 钩 46/46 可判章、R3'@ch11-50/R4'/R6' 观察行——
阶梯夹具曲线本身即单调梯（伪定量行如实反映夹具形态，不作判据）。链验 585→587/backend 10。
