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
