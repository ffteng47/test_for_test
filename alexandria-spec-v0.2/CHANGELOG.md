# Alexandria Spec CHANGELOG：v0.1 → v0.2

> 冻结日期：2026-10-08
> epoch：epoch_0（重冻结定义见 09 §2.5）
> 触发原因：8 条实质问题审查（World State 缺失、确定性矛盾、抽取根因缺失、
>           Taxonomy 对不齐、Replay 序列化、过度设计、排期、文档卫生）
> 变更范围：新增 1 份协议 + CHANGELOG.md，修订 00/01/02/03/04/05/06/07/08/09 全部
>           10 份协议与 README（草案只列 6 修订 + 1 新增，实际落盘见 §B）

本文件分两部分：

- **§A 草案**：v0.1→v0.2 的原始变更草案（修改 1~10）
- **§B 落盘记录**：实际落盘时对草案的偏离与补充决策（2026-10-08 一致性检查后执行）

---

## epoch_1 生效记录（2026-10-15 冻结会裁定 → WP-A v3.8 码批落盘，触发 T1+T2+T5）

> 设计依据：`docs/epoch1-foreshadow-design.md` v0.2 + 拍板六项（`docs/freeze-meeting-and-r8-briefs.md`）。
> 协议正文变更：01 §4.1（伏笔 payload 两行）/ 03 §6.5（剧情台账新节）/ 04 §4.3（D10、D11）/
> 05（H9 族 + Level-2 覆盖行）/ 06 §4.0-4.3 + §5 + §5.1（归属登记、四级阶梯、弃伏）/
> 08（Scene 重写单位改章 + H8.x 桶位勘误）/ 09 §3.1（生效记录）。
> 代码：models（ForeshadowingEntry/CharacterGoalEntry/ArcProgress）、reducers/plot.py 实装 +
> HINTS/READER_HINTED 联动、validator H9 族、derive D11 漂移拦截、阶梯四级化、
> EXTRACTION_RULER v3.6→v3.8-foreshadow-payload。
> 迁移：存量空集（foreshadowing 占位无写入方），schema 升级 + 全链 Replay parity 断言；
> fixture 层 EPOCH 字符串暂留 epoch_0，数据面首条 epoch_1 事件写入即按 09 §5 流程走。
> 尺面纪律：v3.8 起读数与 v3.6 分表，不并列。

---

## v3.9 码批生效记录（2026-10-16 二次冻结会材料三裁定 1A+1B / 2A / 3A+3B → 码批落盘）

> 设计依据：`docs/freeze-meeting-and-r8-briefs.md` 材料三拍板记录（四项裁定，4A 缓议）。
> 协议正文变更：04 §4.3（D10 扩展 rank 可达性 + 新增 D12 越界钉拦截）/
> 05 §4（H5.3 knowledge 分支双判据注记，与 H2.2 同谓词）/
> 06 §4（Arc 归属登记补 rank 超限与 D12 越界钉两行）。
> 代码：models/contract（K_RANK、KNOWLEDGE_RANK_CAP 单源表单消费者=derive D10/validator H5.3/fixture）、
> derive（D10 rank 可达性前置拦截/1A、D12 越界钉拦截/3A）、
> validator `_change_implemented` knowledge 分支实现事件∧终态达档（1B，belief 分支与 H5.7 宽集合不动）、
> llm_extract `_reattribute_is_told`（2A 结构兜底：说话人段落判定+唯一听者换挂，`is_told_reattributed` 记账入 malformed，
> 三漏斗位与 `_promote_infers` 同点接线）、
> EXTRACTION_RULER v3.8→**v3.9-is-told-reattach**。
> fixture：ch06 补证人钉（OBSERVES）、ch10 改钉 IS_TOLD Δ known→believed（3B，作者裁定）；
> LADDER_VERSION 基线/半密度 → ladder-v5b-*（50ch 文件经 import 继承，未动）。
> 背景裁定链：#70 教训"temp0 提示词面修不了行为型别"⇒ 2A 走结构面；
> ③族 rank-cap 穿帮 6 章 ⇒ 1B 从结构上消灭 H5.3-green/H2.2-red 互斥。
> 尺面纪律：v3.9 起读数与 v3.6/v3.7/v3.8 分表，不并列；v3.7 已由 #70 烧号，永不复用。
> 基线：plot_engine 561→573（#87 +5 / #88 +5 / #89 +2）、backend 10 不变。

## 材料四码批生效记录（2026-10-16 材料四裁定 1/2/3 → 修订环 patch_write 落盘）

> 设计依据：`docs/freeze-meeting-and-r8-briefs.md` 材料四（串联分诊：定向补写优先，
> 同条再失败才升级/判死）。
> 协议正文变更：06 §4.2（契约层第一动作 = 带缺失清单的定向补写 patch_write，先补写后重议）/
> 06 §4.3（needs_arc_replan 出口：同条 must_change 补写后再失败 ⇒ ArcConflict 作废本章，
> 落作者桌面；裁定 2：fail-fast/Arc 强制项章也先获得一轮补写；裁定 3：判死章不计修复率分母）/
> 06 §5（escalation 插入 patch_write，位于 renegotiate 之前）/ 06 §9（RevisionTrace 随轮记 items）。
> 代码：validator H5.3 evidence 升级条目全键（character|field|target|expected，
> 分诊靠它认出「同一条补写后再失败」）；models/revision（阶梯默认 + RevisionStep.items）、
> revision `_patch_items` 分诊态机（H5.3 补写后再失败 → raise ArcConflict；H5.1 后再失败 →
> 振荡升级重议；宿主未注入 patch_write 整体隐身 = 向后兼容）、
> llm_writer scene_prompt/make_scene_writer 可选 directive（常规轮提示词逐字节不变，有回归用例；
> 清单同过 forbidden 抹除闸）、review 双接线（离线注册确定性 writer 只走分诊机 /
> 实跑按 FIX_GUIDE 拼清单造补写 writer）、dump Revision 行 items 仪表、
> metrics._REWRITE 并 patch_write、run.log 加戳「修订环=patch-v1」。
> 尺面纪律：EXTRACTION_RULER 维持 v3.9（抽取通道一字未动）；批前/批后读数按修订环戳分表。
> 基线：plot_engine 573→581（分诊 4 / Writer 清单 2 / 全键 1 / dump 仪表 1）、backend 10 不变。

## 清单具名化批生效记录（2026-10-16 #98 指令面 → 修订环 patch-v1→v2）

> 归因驱动：§13 patch-v1 三采样——稳定死章 4/4 三批 item 键逐字一致，三分型共性=
> **型别模型会写、绑定在裸编号清单面上系统性串位**（actor 错绑/事实错绑/档位顶错）。
> 非结构不可写，是指令面欠明确 ⇒ 先走这条比 S 批（云端强模型）更便宜的指令面梯级。
> 协议正文变更：06 §4.2（补写清单**具名形态**下发：actor 用角色名、target 用事实命题、
> 档位可达型别从 KNOWLEDGE_RANK_CAP/FIELD_EVENT_TYPES 单源表筛出并点名排除不可达型别；
> 失败升非契约层时清单必空 ⇒ 落回该层默认动作、patch_write 不空挂开火）+
> 06 §4.3（判死 ArcConflict 必须携带已跑轮次 trace，dump `## Revision` 段可核对补写开火=S 批条件①）。
> 码批落盘：review.render_patch_directive 具名化 + 单源表 import、revision run_chapter
> 抛点挂 trace + Writer 层空清单不回头补写（`action==patch_write and rc.level!="contract"` → action_for）、
> experiment quarantine 收 `exc.trace`、run.log 戳「修订环=patch-v2」。
> 尺面纪律：items 全编号键 + EXTRACTION_RULER v3.9 一字未动；具名化改的是喂 Writer 的指令文本 ⇒
> 修订环戳 v1→v2，与 patch-v1（`sampling/ep1v39p-rN`）分表，禁与批前/批后混读。
> 基线：plot_engine 581→585（trace 携带 1 / 空清单不空挂 1 / directive 具名 1 / state 缺席兜底 1）、backend 10 不变。

---

## §A 变更草案（修改 1~10）

### 修改 1：新增 10_world_state_protocol.md

**理由**：v0.1 全套协议引用 character_id / location_id / item_id / realm /
inventory / StoryState，但无一份定义。H1(Canon) 与 H4(Resource) 悬空，
07 的 Reducer 无聚合根。

**连带修改**：

- 01 Event Taxonomy 新增：ITEM_ACQUIRED / ITEM_CONSUMED / RELATIONSHIP_CHANGED
- 01 CHANGES.field 枚举统一为：status / realm / location / faction /
  attributes / abilities（移除 inventory / relationship）
- 04 §4.3 CharacterChange.field 与 10 §4.3 建立强映射表
- 07 Stage 2 Reducer 增加对 10 号协议实体的更新路径

### 修改 2：确定性矛盾修复

- 2a. 05 §4 H2.3 改为可判定：Draft 中 `<!-- reader_learns: fact_id -->`
  标注与 Reader Ledger 比对；有标注无更新 → HARD，有记录无标注 → SOFT
- 2b. 05 §4 H5.5 改为可判定：Draft 末尾最后 3 段必须含
  `<!-- hook: {type} strength={0~1000} -->`，类型须等于 contract.ending.type
- 2c. 01 Taxonomy 新增 ReaderEvents：READER_LEARNS / READER_DECEIVED / READER_HINTED
- 2d. 03 §6 新增 Reader Reducer（READER_* → reader_state = knows/deceived/hinted），
  消解"Reader 知识唯一来源是叙事文本"与 P2（状态变更必须走 Event）的矛盾
- 2e. 04 Chapter Contract 新增 reader_signals 字段：

```python
reader_signals: List[ReaderSignal] = []

class ReaderSignal(BaseModel):
    fact_id: str
    target_state: Literal["unaware", "hinted", "knows", "deceived"]
    established_in_scene: Optional[str] = None
```

### 修改 3：extraction_error RootCause

- 3a. 06 §3 RootCause level 新增 `"extraction"`（优先级最高）
- 3b. 06 §4 新增 4.0 Extraction Error 回退路径：回退 Stage 0 重跑抽取，
  不触发 Writer 重写 / Contract 重议
- 3c. 07 Stage 0 抽取置信度联动：Proposal 携带 extraction_confidence；
  双通道（规则 + LLM）一致 = 1.0，不一致 = 0.5，单通道 = 0.7
- 3d. Stage 1 新增 H8 Extraction 违规（H8.1 置信度过低 / H8.2 双通道冲突 /
  H8.3 Proposal 与 Draft 语义不一致）

### 修改 4：Replay 序列化规范

- 4a. 05 新增 §5.5 Canonical 序列化：key 字典序、无空白、UTF-8；
  浮点全部 ×1000 定点化为整数（禁止 Python float 进入 Replay 关键路径）；
  `state_hash = SHA256(canonical_json(state))`；每章 Commit 后必须 Replay 校验
- 4b. 07 §7 新增：Commit 后自动 Replay，replay_state_hash ≠ online_state_hash
  → 回滚、落 REPLAY_INCONSISTENT、停止 pipeline
- 4c. 10 §13 StoryState 新增 `schema_version: int = 2`

### 修改 5：Fact 定义单一来源化

- 5a. 03 §3 删除 Fact Schema 重复定义，改为引用 02 §3
- 5b. 02 §5 补充：Fact Relation 图为 DAG，Commit 前环检测；
  Phase 0 视为静态（Arc 初始化定义，运行期不变），增删事件留待 v0.3
- 5c. 04 / 05 所有 fact_id 注明引用 02 §3

### 修改 6：08 排期与退出条件修订

- 6a. 排期改为 3.5 周（Day 1-3 Freeze / 4-7 Store+EventLog+Reducer /
  8-11 Validator / 12-13 Commit / 14-16 Plot→Scene→Beat /
  17-19 Writer+Extraction / 20-22 10 章实验 / 23-25 Review）
- 6b. 退出条件放宽：E1' 10 章全部生成即可；E2' 首轮 Commit 成功率 ≥ 70%；
  E3' ≤3 轮 Revision 后 ≥ 90%；E4' 无单一规则占比 > 40%；
  E5' Replay 一致性 ≥ 90%；E6' 无架构阻断问题
- 6c. 新增 Scene / Beat 层：Chapter Contract → ScenePlan（3~7 Scene，
  每 Scene 3~7 Beat）→ Writer；Schema 见 04 附录 B

### 修改 7：ID 上限修复

| 原 | 新 |
|----|----|
| `^fact_\d{4}$` | `^fact_\d{6}$` |
| `^char_\d{5}$` | `^char_\d{6}$` |
| `^loc_\d{5}$` | `^loc_\d{6}$` |
| `^item_\d{5}$` | `^item_\d{6}$` |
| `^evt_\d{6}_\d{3}$` | `^evt_\d{8}_\d{3}$` |

理由：长篇（设定库 + 伏笔 + 事件）会撞 9999 / 99999 上限。

### 修改 8：tension 规则降 SOFT

- 8a. 04 D2'：tension_target 与 arc.tension_curve 偏差 > 0.2（定点 200）
  只落 finding，不阻断
- 8b. 04 R3'~R6' 全部 SOFT：伪定量规则会把小说倒过来拟合数字，
  数据供 Phase 1 Critic 使用

### 修改 9：E3 孤岛 Event 规则降 OBSERVATION

- 9a. 01 E3'：Phase 0 preconditions/causes 可为空，环检测只警告，
  同章内按 seq 全序即可；Phase 1 升 HARD
- 9b. 01 §5.2 R1'：Event 图应为 DAG，Phase 0 检出环只落 finding 不阻断

### 修改 10：文档格式规范化

- 10a. 所有 Schema 用 ```python 代码块；示例用 ```json；表格用 Markdown 表格
- 10b. README 新增文档层级说明（spec = 协议层 source of truth；
  工程落地.txt 降级历史文档；target-architecture.md 仍为一期部署范围 source of truth）

---

## §B 落盘记录（2026-10-08 实际执行）

依据 `docs/alexandria-spec-consistency-check.md` 的核查结论：
v0.1 文件集内 §A 草案**零落盘**（仅内嵌于 10 号文档尾部），
且存在 12 项决策级矛盾。本次落盘在机械执行 §A 的同时，对矛盾点做了以下裁决：

### B1. epoch_0 重冻结（09 新增 §2.5）

§A 触发 09 §4 的 T1/T2/T5 升级条件，但 Day 4 开工前无任何已提交数据。
裁决：epoch_0 := v0.2 文档集，v0.1 的 epoch_0 定义作废；一次性"零数据重冻结"豁免；
Day 4 之后一律走 epoch_1。空集全量 Replay 恒成立。

### B2. H8.3 不得产出 HARD（保护 05 §9 I1）

§A-3d 的 H8.3 依赖 LLM-as-validator，与 05 I1"HARD 规则不得依赖 LLM 判断"冲突。
裁决：H8.3 只产 SOFT finding + 转人工，不阻断 Commit。

### B3. 隔离制替代"动态降级 HARD→SOFT"

§A-3c 的"< 0.7 → 该 Proposal 的 HARD 检查降级 SOFT"使 HARD 集合不稳定、不可 Replay。
裁决：confidence 500~699 的 Proposal 整条**隔离**（不入库、落 H8.2
EXTRACTION_UNVERIFIED、触发 06 §4.0 重抽取），HARD 规则集本身保持恒定。

### B4. 07 删除规则清单复制，05 为唯一来源

§A-3d 在 07 §5.2 复制了一份 HARD 清单，与 05 必然漂移。
裁决：07 §5.2 改为"规则清单唯一来源为 05 §4~§6（H1~H8）"，只做引用。

### B5. 新增 FACT_CONTRADICTED 事件（03 §5.4）

03 的信念降级（confirmed/known→suspected，×0.4）原本无事件驱动，违反 P2。
裁决：KnowledgeEvents 新增 FACT_CONTRADICTED，作为唯一降级通道。

### B6. Draft 标注通道成为抽取第一来源（07 §4.4 M1~M5）

H2.3 / H5.5 的可判定化依赖 Writer 在 Draft 中显式标注。
裁决：抽取四通道 markup / rule / llm / hybrid，markup 通道命中即
confidence = 1000；markup 标注必须生成对应 Proposal（01 I8），
否则 H2.3 违规；hook 标注强度用定点 0~1000（替代草案的 0.0~1.0）。

### B7. 04 附录 B 实写（消除死引用）

§A-6c 把 Scene/Beat Schema 指向"04 附录 B（v0.2 新增）"，但草案未给出内容。
裁决：实写 Beat / Scene / ScenePlan Schema 与 SP1~SP7 校验规则
（含 SP5 可达性走 10 W-S4）、Scene 为最小重写单元（§8.4）。
ID：`^scn_\d{4}_\d{2}$`、`^bt_\d{6}$`、`^sop_\d{8}$`。

### B8. 空间推理规则改名 W-S1~W-S6（10 §5.1）

原 S1~S6 与 05 SOFT 规则 S1~S5 命名空间撞车。裁决：统一改 W-S 前缀。

### B9. Location.unlocked 定为 Phase 0 静态（10 §5.2 / I8）

草案同时要求"CHANGES.field 枚举不含其他字段"与"unlocked 变更走
CHANGES(field=unlocked)"，二者矛盾。裁决：unlocked 初始化后运行期不变，
进入与否由 unlock_conditions 对当前 StoryState 实时求值决定；
unlocked 自身变更通道留待 v0.3。

### B10. Realm 新增 usable_realms（10 §8）

sealed 角色"能力受限"原本不可判定。裁决：Realm.usable_realms: List[int]
（Phase 0 通常 = [tier]，sealed 视为 []），H1.4 判定改用该字段。

### B11. 00 / 09 也纳入修订（草案标"不变"）

- 00：流水线层级补 ScenePlan 与 Draft 标注；边界矩阵加 Scene Planner 行、
  Writer 视图改为 Chapter Contract + ScenePlan + WriterView；HARD 类别补
  Extraction（H8）；术语表补 Entity/World State、Draft markup、
  Canonical 序列化、定点化，epoch 指向 09 §2.5
- 09：新增 §2.5（见 B1）

### B12. 实际落盘文件清单

| 文件 | 状态 |
|------|------|
| README.md | 重写：v0.2 文档清单 + 文档层级（10b） |
| CHANGELOG.md | 新建（本文件；原内嵌于 10 号文档尾部，已移出） |
| 00_principles.md | 修订（B11） |
| 01_event_protocol.md | 重写：2c / 7 / 9 / B5 / B6，hook 强度定点化 |
| 02_fact_protocol.md | 修订：5b / 7，fact_relations 静态化 |
| 03_knowledge_protocol.md | 重写：2d / 5a / B5，strength 定点化，Reader Reducer |
| 04_contract_protocol.md | 重写：2e / 8 / B7（附录 B），tension_curve 定点化 |
| 05_validation_protocol.md | 修订：2a / 2b / 4a / B2 / B3（H8 定稿） |
| 06_revision_protocol.md | 修订：3a / 3b，escalation 加 rerun_extraction |
| 07_commit_protocol.md | 重写：3c / 3d / 4b / B3 / B4 / B6，CommitRequest 加 scene_plan |
| 08_experiment_protocol.md | 修订：6a / 6b / 6c，Failure Classification 加 Extraction 行 |
| 09_versioning.md | 修订：B1（§2.5） |
| 10_world_state_protocol.md | 落成协议本体：B8 / B9 / B10；内嵌草案移出至本文件 |

### B13. 冻结检查清单（全部完成）

```text
[x] 10_world_state_protocol.md 完整落盘（CHANGELOG 移出）
[x] 01 Taxonomy 含 ITEM_ACQUIRED / ITEM_CONSUMED / RELATIONSHIP_CHANGED
[x] 01 Taxonomy 含 READER_LEARNS / READER_DECEIVED / READER_HINTED
[x] 01 CHANGES.field 枚举统一
[x] 03 §3 改为引用 02
[x] 05 §5.5 序列化规范落盘
[x] 06 RootCause 含 extraction
[x] 07 Stage 0 抽取置信度联动落盘（隔离制，B3）
[x] 07 Commit 后 Replay 校验落盘
[x] 08 排期改为 3.5 周
[x] 08 退出条件改为 ≤3 轮收敛
[x] 所有 ID 正则更新（fact/char/loc/item/rel/inv 6 位，evt 8 位）
[x] 所有 tension 规则降 SOFT
[x] 所有因果完整性规则降 OBSERVATION / Phase 0 警告
[x] 全部文档格式规范化（python/json/text 代码块 + Markdown 表格）
[x] README 文档层级说明落盘
```

16 项全部完成 → v0.2 冻结（epoch_0，09 §2.5）→ Day 4 开工写代码。

### B14. 冻结后卫生修复（Phase 0 实现期发现）

- 02 §5 `FactRelation.strength`：`float = Field(1.0, ge=0.0, le=1.0)` →
  `int = Field(1000, ge=0, le=1000)`（定点 ×1000，05 §5.5）。
  这是全协议最后一处 float 残留，违反 I8（"禁止 float 参与 Replay 关键路径"）；
  修正不改变协议语义，仅落实既有定点化决定，故不动 epoch、不改版本号。
- 发现途径：Day 4 `plot_engine/models/fact.py` 落码时的类型对照检查。
