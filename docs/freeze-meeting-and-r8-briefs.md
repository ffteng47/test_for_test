# 契约冻结会议程草案 + R8 前两项需求澄清提纲

> 产出：需求澄清助手，2026-10-15。纸面材料，不落任何代码承诺。
> 前提纪律：WP-E（`sampling/wpe50ch/`）在跑，`plot_engine/` 全冻结（`docs/project-roadmap.md:151`，下称 roadmap）；本文所有 `文件:行号` 均当日打开核对，与 roadmap 内旧坐标不一致处以本文为准（例：backlog #2 坐标 `review.py:245` 已漂移到 `plot_engine/review.py:169,382`，见 `docs/phase0-closing-report-and-v3-plan.md:271`）。
> 链接勘误：roadmap 多处引用的 `docs/collaborator-guide.md` 实际不存在，协作者须知 v1.0 现位于 `docs/commercial/collaborator-guide.md`（单写者同步即可，非议题）。

---

## 材料一：契约冻结会议程草案（一页）

**会议定位**：一次性定稿 epoch_1 契约面；触发条件 T1/T2/T5 全部命中，必须升 epoch（roadmap:53；`alexandria-spec-v0.2/09_versioning.md:47-51`）。本会 = WP-A 码批硬前置（roadmap:131,146）。尺戳现状 v3.6（`plot_engine/llm_extract.py:49`），WP-A 预定用 v3.8（roadmap:85）：凡本轮动到抽取面（`PAYLOAD_SCHEMA`，`llm_extract.py:53`）的拍板项，直接决定 v3.8 尺面键名，须先拍板后钉戳（须知 §1.2 一因一批）。

| # | 悬项（争议一句话） | 协议出处（文件:行号） | 候选口径 | 与 WP-A v3.8 的依赖 |
|---|---|---|---|---|
| 1 | **must_change 系失败在 06 归属空白**：契约层缺陷（结果要求无可实现它的动作）以写作层失败样子出现，06 §4 未定义该归属，重议成功率恒 0 却烧满预算 | `06_revision_protocol.md:89-104`（§4.2 处理只有重议、碰不到 must_change 轴）；`04_contract_protocol.md:181,240,245`（W1/W6 语义）；`05_validation_protocol.md:51,74`；`docs/phase0-h53-contract-infeasibility.md:113-115,139-146`；`docs/phase0-closing-report-and-v3-plan.md:205,214`（backlog #1） | A：04 §4.3 补 D10「结果要求必须有动作实现」+ derive 前置 ArcConflict 拦截，06 §4 正式登记该归属（代码侧补丁 `plot_engine/revision.py:49-51` 已把 H5.3→contract，会议追认并补协议文本）；B：不改协议文本，只认「协议从未授权产出自相矛盾契约」为派生器工程守卫（h53 稿 §5 B 的判断，`docs/phase0-h53-contract-infeasibility.md:153-158`），C 案 D10 缓议 | 不动尺面；但 WP-A 写集同含 `revision.py:38`（H9 族登记），同表同批拍板 |
| 2 | **rewrite_scene ≡ rewrite_chapter 名义阶梯**：06 §5 阶梯前两级在实现里是同一 lambda，04 §8.4「只重写该 Scene」的承諾未落地 | `06_revision_protocol.md:181-186`；`04_contract_protocol.md:393-397`；`plot_engine/review.py:169,382`（两同名→同函数）；`docs/phase0-closing-report-and-v3-plan.md:215`（backlog #2） | A：诚实降级——06 §5 删一级，阶梯四级，协议承认 Phase 0/1 无场景级返工；B：兑现 §8.4——场景级重写进 R3 路线（写集触 `writer.py:38 compose_chapter_draft` + WP-0 面 `review.py`，撞车矩阵 roadmap:145） | 不动尺面；与 1 同场拍，避免 epoch_1 后再修 06 |
| 3 | **H8.x 九桶归类**——**已有现成记述，会上只追认入册、不再裁定**：08 §4 九桶全是状态账、无抽取桶 ⇒ H8.1/H8.2 只记 `by_rule` 不进九桶（`docs/phase1-v3.1-freeze.md:15,45-46`，T3 @`c176dc6`；`docs/phase1-merged-plan-final.md:64-68`；规则本体 `05_validation_protocol.md:99-105`；`06_revision_protocol.md:51-58`） | 同上 | 唯一动作：确认该裁定回填 `08_experiment_protocol.md` 勘误与 spec CHANGELOG，关闭 `RULE_TO_METRIC`（`plot_engine/models/experiment.py:36`，兜底 CANON 见 `classify.py:28`）的缺口遗留 | 无关 |
| 4 | **must_reveal_by_chapter ↔ due_by_chapter 统一口径**：epoch_1 稿判「由 derive 从 knowledge_gates 生成 due_by_chapter、两处不得独立漂移」并要求 04 补 D 规则——这是协议修订，需拍板 | `docs/epoch1-foreshadow-design.md:116`；`04_contract_protocol.md:42`；`plot_engine/models/contract.py:19` | A：按稿执行（derive 单源，gate→due 派生）；B：双字段并存、仅 validator 对账（不推荐，双写漂移正是稿中要防的） | **尺面强依赖**：due_by_chapter 进 FORESHADOWING_SET payload（`docs/epoch1-foreshadow-design.md:83`）⇒ v3.8 键名面由此项定稿后才能钉 `test_instr.py` 用例 |
| 5 | **expired 的写通道**：伏笔逾期由 validator 判 H9.1，但「人工放弃伏笔」要走显式动作写 expired——06 §5 阶梯现无此动作名，属 06 契约面增项 | `docs/epoch1-foreshadow-design.md:99,105-108`；`06_revision_protocol.md:181-186`；`plot_engine/models/revision.py:27-31` | A：新增动作名（如 abandon_foreshadowing）入阶梯/人工路径，账可溯；B：不加动作，expired 只由 rescue 人工重入路径（`plot_engine/rescue.py`）以事件补写 | 不动尺面（expired 非抽取事件）；写集与 WP-A `revision.py` 登记同文件 |
| 6 | **ArcProgress 是否随 epoch_1 冻结字段**（P1：`active_arc: Any → 结构化`，语义留 epoch_2）——冻结与否影响爽点工程曲线读数有无现成承接位（见材料二②） | `docs/epoch1-foreshadow-design.md:18,122`；`plot_engine/models/state.py:59` | A：按稿随 epoch_1 只冻字段（避免 epoch_2 再 T2 一戳）；B：剔出 epoch_1、爽点工程论证清楚后 epoch_2 再进 | 不动尺面（`active_arc` 不在抽取 `PAYLOAD_SCHEMA`）；但迁移断言进 V3/V6（`docs/epoch1-foreshadow-design.md:125-130`） |

**会上禁重问（已有裁定）**：R8 六项入队序以 roadmap v0.8 裁定为准（确认闸>爽点工程>…，roadmap:10,96）——`docs/commercial/r8-commercial-input-requirements-v1.0.md:46` 里的旧序「爽点工程>确认闸」是被覆盖文本，待 errata，不是议题；WP-A 尺戳 v3.8、串行条件（#70 撤销收口）已定（roadmap:85,146）。

---

## 材料二：R8 前两项需求澄清提纲

### ① 确认闸（人审卡点）——roadmap 承接面：R3+R5 审听出口（roadmap:97）

已定事实（不问）：需求定义见 `r8-commercial-input-requirements-v1.0.md:65-73`（确认落事件日志、确定性拦截、改走修订流程）；**交付侧人工闸已存在**——审听工位四类判定（✓对/✗错读/♪音色/↻重生成）落 `prooflisten.jsonl`（`docs/post-production-plan.md:118,145,152-155`），机检闸门+禁下载已跑通（同文 :24,59），旧「确认锁定」死字段已删（:165）。故开放问题集中在**生成侧开书前闸**与两闸关系。

- **谁确认**：开书前闸的确认人是不是且仅是 tff 一人（作者位）？交付侧审听（M3 工位）是否算第二道闸、二者判定结果是否互相可见？——触 `docs/commercial/collaborator-guide.md:22`（禁自行发起生成批，放行权在 tff）与 WP-0 面 `plot_engine/live.py:55`（build_live_source 现行自动流转，无任何人工停留点）。
- **确认什么（粒度）**：确认对象止于「设定/卷纲/前三章规划」（R8 §4.2 原话，`r8:67`），还是每章 Chapter Contract 都要人过？后者意味着闸频×章数，工时模型要重写——触 `docs/cost-model.md` 口径与 `plot_engine/derive.py:38`（NoChapterIntent：现由 reader_beats 自动派生）。
- **确认动作落哪条账**：R8 要求「可追溯、可回放」⇒ 进 plot_engine EventLog 需新增事件型 = T1 =  epoch 升级（`alexandria-spec-v0.2/09_versioning.md:47`，01 Taxonomy 现无确认类事件 `01_event_protocol.md:31-107`）；还是落 backend `jobs` 表（`backend/noveldb.py:95,251`）不进事件溯源？**若选前者，此题须追进冻结会新增议程项。**
- **失败回路**：人工打回后回到哪一层——重画规划（≈arc 层重议，`06_revision_protocol.md:106-122`）还是拒绝入 derive（零成本前置）？打回次数是否计入 max_rounds/成本上限（`06_revision_protocol.md:179-190,213-214`；`plot_engine/models/revision.py:26-33`）？「未确认硬拦截」的确定性闸点放在 chapter_source 路径（`plot_engine/experiment.py:36,101`）还是 live 装配层（`live.py:82` laned source）？
- **闸与 WP-E 存量**：wpe50ch 已跑/将跑的 50 章产物按新规矩属「未确认」态吗？追溯补确认还是豁免？——决定确认闸工作包的验收样本从哪批来。

### ② 爽点工程（tension/beat 曲线工程化）——roadmap 承接面：WP-A，R1 语义层是地基（roadmap:97）

现有数据面**能承接**（查证在案）：规划链三级张力标量已通——`arc.tension_curve[idx] → contract.tension_target → scene.tension`（`plot_engine/derive.py:129,204,283`；schema `04_contract_protocol.md:59,164,366` = `models/contract.py:35,131`、`models/sceneplan.py:42`）；节拍型枚举 setup/pressure/turn/release/foreshadow（`04:343`=`models/sceneplan.py:18`）；turning_points 五型（`04:45-50`=`models/contract.py:23`）；章尾钩子存在性已**确定性可判**（hook markup H5.5/W7，`05:76-79`、`04:246`；`models/contract.py:89`）。
**缺**（查证在案）：`metrics.py` 无任何 tension/hook/beat 读数（grep 零命中），`readout/viewer/sample` 无曲线出口；情绪**类型**无账（tension 只有强度）；R3'-R6'/SP7 全部 SOFT 只落 finding（`04:77-80,391`；`sceneplan.py:126-130`）；`ArcProgress.tension_actual` 仅 epoch_1 P1 预留（`docs/epoch1-foreshadow-design.md:122`）。

- **情绪类型词表选哪个**：复用 Beat.beat_type 五值、新建叙事情绪枚举、还是借交付侧 `backend/emotion_map.py:1,68` 的词表？三者现互不相通（后者量的是 TTS 音色情绪，非剧情爽点）——不定此项，「每章情绪类型落台账」无落点。
- **爽点密度进不进闸**：只出报告（对齐 R3'-R6'「伪定量不阻断」先例，`04:82-83`），还是进评审门禁？若进门禁，是 HARD 还是 SOFT finding？——决定 validator 是新增规则族还是 metrics 加列。
- **钩子命中率怎么算**：H5.5 已判「markup 存在且 type==contract.ending.type」；命中率还需 strength 达标吗（`ending.strength` 现 SOFT，`04:190`）？统计出口挂 R5 测量层新报表，还是并入 `blind_review.py:16-17` 的章级表？
- **实测曲线落 ArcProgress 还是另起字段**：爽点工程的「规划 vs 实测量」偏差账，是直接用 epoch_1 待冻的 `tension_actual: List[int]`（则本项与冻结会议程 #6 联动、零新契约面），还是 ScenePlan/Contract 加字段（= T2，须赶在冻结会前入议程）？
- **要不要动抽取面**：爽点读数若全从既有 ledger/Contract/ScenePlan 确定性派生 = 非尺面；若要新增「从正文抽取爽点/情绪标记」则触 `PAYLOAD_SCHEMA`/markup = 尺面变更，与 WP-A v3.8 撞一因一批（`plot_engine/llm_extract.py:49,53`；须知 §1.2 `docs/commercial/collaborator-guide.md:9`）——**tff 须先答：派生还是抽取？**
- **双通道验收线**：R8 商业终点为网文连载+有声双通道（`r8:12`），爽点密度/黄金三章阈值按哪个通道定首版验收？两通道标准不一致时听谁的？

---

*索引：材料一 = 冻结会 6 项（must_change 归属 / rewrite 阶梯 / H8.x 追认 / due 统一 / expired 通道 / ArcProgress）；材料二 = 确认闸 5 问 + 爽点工程 6 问。全部坐标经当日打开文件核对。*
