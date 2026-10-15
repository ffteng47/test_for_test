# epoch_1 契约设计稿：伏笔生命周期 + 人物目标（WP-A，待冻结）

> 版本：v0.2（2026-10-15 14:36 稽核修正，问题助手产出，**未经冻结前任何人不得据此写代码**）
> v0.1→v0.2 变更：① 尺戳 v3.7→**v3.8**（v3.7 已由在队 #70 型别批占用，本批串行于 #70 之后，一因一批）；② H9 登记处补登 `plot_engine/revision.py:38` RULE_TO_LEVEL；③ derive.py 增补声明串行于在队 b3 补丁之后。
> 协议依据：alexandria-spec-v0.2 `01_event_protocol` / `03_knowledge_protocol` / `04_contract_protocol` / `05_validation_protocol` / `09_versioning`。
> 升级触发：T1（Event payload 变更）+ T2（字段增删）+ T5（HARD 增删）——必须升 epoch_1，不允许 epoch_0 内偷跑。
> 现状证据：`reducers/plot.py` no-op（"语义留给后续计划"）；`state.foreshadowing: List[str]` 占位；`llm_extract.PAYLOAD_SCHEMA` 不含剧情事件 → **当前无任何写入方，存量迁移对象为空集**。

---

## 1. 范围与优先级

| 模块 | 优先级 | 说明 |
|---|---|---|
| 伏笔生命周期（ForeshadowingEntry + 事件语义 + H9 规则） | **P0（epoch_1 必做）** | 用户 Phase 1 验收"伏笔回收"的可测账本 |
| 人物目标（CharacterGoalEntry） | **P0（epoch_1 必做）** | "有原因、有代价、有后果"的归因锚点 |
| 冲突网络（FactRelation 动态化） | P1（epoch_1 可选字段，语义 epoch_2） | `models/fact.py:31` 注明"Phase 0 静态"；先留字段 |
| 弧进度结构化（active_arc: Any → ArcProgress） | P1（同随 epoch_1 冻结字段） | 避免 epoch_2 再升一次 |

**设计原则**：镜像既有 ledger 条目形态（`models/ledger.py`：状态枚举 + 定点×1000 + source_event_id + acquired/last_updated 双章号 + epoch），不发明新约定。

---

## 2. 数据模型（models/ 变更）

### 2.1 ForeshadowingEntry（新增，`models/ledger.py`）

```python
class ForeshadowingEntry(BaseModel):
    """伏笔台账条目：埋点→提示→到期→回收/逾期 的全生命周期记录。"""
    foreshadow_id: str = Field(..., pattern=r"^fsh_\d{6}$")
    fact_id: str                              # 伏笔指向的事实（回收时揭示）
    lifecycle: Literal["planted", "hinted", "due", "paid", "expired"]
    strength: int = Field(..., ge=0, le=1000)  # 定点 ×1000（显著度）

    planted_chapter: int
    due_by_chapter: int                        # 对照 KnowledgeGate.must_reveal_by_chapter
    paid_chapter: Optional[int] = None

    source_event_id: str
    last_updated_chapter: int
    epoch: str
```

生命周期状态机（迁移只允许单向，回退视为新事件而非状态回写）：

```
planted → hinted → due → paid
                ↘ due → expired（超过 due_by_chapter 未回收，由 validator 判定打标，不是 reducer 自发）
```

### 2.2 CharacterGoalEntry（新增，`models/ledger.py`）

```python
class CharacterGoalEntry(BaseModel):
    """人物级目标：章级 story_goal 的上层归因锚（Phase 1「有原因」的账本）。"""
    goal_id: str = Field(..., pattern=r"^goal_\d{6}$")
    character_id: str
    objective: str                             # 一句话目标（SOFT）
    stakes: str = ""                           # 失败的代价（SOFT，「有代价」的载体）
    status: Literal["active", "achieved", "failed", "abandoned"]

    linked_fact_ids: List[str] = []            # 目标相关事实（冲突网络的挂点，P1 用）

    source_event_id: str
    acquired_at_chapter: int
    last_updated_chapter: int
    epoch: str
```

### 2.3 StoryState 字段变更（`models/state.py`）

| 字段 | epoch_0 | epoch_1 | 迁移 |
|---|---|---|---|
| `foreshadowing` | `List[str]`（占位，无写入方） | `List[ForeshadowingEntry]` | 存量为空 → 空迁移 |
| `character_goals` | 不存在 | `List[CharacterGoalEntry] = []` | 新增默认空 |
| `active_arc` | `Optional[Any]` | `Optional[ArcProgress]`（P1 结构化，本稿 §6） | 现网存量为 Any/null → 直读 |

### 2.4 事件 payload 变更（`models/event.py` + `llm_extract.PAYLOAD_SCHEMA`）

| 事件 | epoch_0 payload | epoch_1 payload |
|---|---|---|
| `FORESHADOWING_SET` | 未定义（不产） | `{foreshadow_id, fact_id, due_by_chapter, strength}` |
| `FORESHADOWING_PAID` | 未定义（不产） | `{foreshadow_id}` |
| `CONTRACT_FULFILLED/VIOLATED` | 未定义 | 不变（本轮不动） |
| `CASE_SOLVED` | 未定义 | 不变（本轮不动） |

注意：`PAYLOAD_SCHEMA` 变更 = `llm_extract.py` 行为面变更 = **尺面变更**，按纪律 §1.2 同步 bump `EXTRACTION_RULER`（当前 v3.6 → **v3.8**（v3.7 已烧不复用）；v3.7 已由在队 #70 型别批 `_patch_b12_typecriteria.diff:9-13` 占用，本批**串行于 #70 施加之后**，一因一批不双占）并钉进 `test_instr.py` 尺戳用例；新旧尺号读数分表。

---

## 3. Reducer 语义（`reducers/plot.py`，替换 no-op）

纯函数约束不变（不落盘、无副作用、按 (chapter, seq) 拓扑序）：

- `FORESHADOWING_SET`： upsert `ForeshadowingEntry(lifecycle="planted")`；同 `foreshadow_id` 重复 SET = ValueError（与 duplicate_id 纪律一致，交沙盒 `failed` 记账，不炸进程）。
- `FORESHADOWING_PAID`： 目标条目必须存在且 lifecycle ∈ {planted, hinted, due} → 转 `paid` 并记 `paid_chapter`；条目不存在或已 paid/expired = ValueError（由 validator H9.2 先判，reducer 兜底）。
- `hinted`/`due` 迁移不由独立事件驱动：`hinted` 由 `HINTS`/`READER_HINTED` 事件联动（reducer 内同批检查 linked fact）；`due` 是派生态（chapter_no ≥ due_by_chapter - 1 时 validator 视图计算），**不落账**，保持 replay 确定性。
- `expired`：不由 reducer 自发写入——validator 在章提交前判 `chapter_no > due_by_chapter 且 lifecycle != paid` → H9.1 HARD；人工选择"放弃伏笔"时走 `revision_actions` 显式动作写 expired（保证账可溯）。

## 4. Validator 新规则族 H9（`validator.py`）

| rule_id | 级别 | 判据 | 归因层级（RULE_TO_LEVEL） |
|---|---|---|---|
| H9.1 | HARD | 章提交时存在 `chapter_no > due_by_chapter` 且未 paid 的伏笔 | arc |
| H9.2 | HARD | PAID 引用不存在的 foreshadow_id，或对已 paid/expired 重复回收 | extraction |
| H9.3 | SOFT | 伏笔 planted 后连续 N 章（建议 N=5，入 RevisionPolicy 可调）无任何 hint 联动 | writer |
| H9.4 | OBSERVATION | 伏笔回收距埋点 < 3 章（伏笔过浅，读者无期待感） | — |

> 登记处说明：H9 族进 `RULE_TO_LEVEL` 的位置是 **`plot_engine/revision.py:38`**（不在 validator.py）——写集已补登该文件。

1 正 1 反用例纪律：每条规则至少一个触发用例 + 一个不触发用例。

## 5. Contract / Derive 联动

- `KnowledgeGate.must_reveal_by_chapter`（`models/contract.py:17`）与 `due_by_chapter` 语义重叠：**epoch_1 统一为由 derive 从 knowledge_gates 生成 FORESHADOWING_SET 的 due_by_chapter**，两处不得独立漂移（D 规则增补，进 04 协议修订）。
- **排队声明**：本节对 `derive.py` 的增补与在队 b3 补丁（`_patch_b3_deadfilter.diff`，同改 `derive_chapter_contract` 函数区 154-169 行）**串行，施加在其后**
- ArcContract.turning_points 的 `revelation` 类型转折点：derive 校验其所在章必须有至少一条伏笔进入 due/paid（否则 SOFT 警告，H9.3 同族）。

## 6. P1 预留（随 epoch_1 冻结字段、语义后置）

- `ArcProgress`：`{arc_id, current_chapter, tension_actual: List[int], turning_points_hit: List[int]}` 替换 `active_arc: Any`；epoch_1 只落字段与 schema，r_outes 语义 epoch_2。
- `FactRelation` 动态化：epoch_1 仅允许 reducer 读，不写；冲突网络的事件族（如 `CONFLICT_ESCALATED`）留 epoch_2，避免一次冻结过大。

## 7. 迁移方案（09 V1–V6）

1. **迁移对象为空集**：`foreshadowing` 占位无写入方（证据见文头）；`character_goals`/`active_arc` 新增或 null → 迁移脚本 = schema 升级 + 空集校验断言。
2. 迁移脚本可回滚（V5）：epoch_1 → epoch_0 = 丢弃三张新台账字段。
3. 全量 Replay 验证（V6）：对既有 10 章 fixture（`tests/fixtures/experiment_10ch.py`）跑 replay parity，state_hash 除新字段外逐位一致。
4. 旧 epoch_0 数据只读（V4）。

## 8. 验收测试清单（码批入场券）

- [ ] `test_reducer_plot.py`（新）：SET→HINT 联动→PAID 全生命周期；重复 SET 拒绝；无源 PAID 拒绝（对齐 `test_reducer_knowledge.py` 形态）
- [ ] `test_validator_l1.py` 增补：H9.1 逾期触发 / 未逾期不触发；H9.2 无源回收触发 / 正常回收不触发
- [ ] `test_instr.py` 尺戳用例：**v3.8** 钉死（串行 #70 之后）
- [ ] `test_replay.py`：epoch_1 全量 replay parity（新旧 fixture 各一）
- [ ] 全链 `pytest plot_engine/tests -q` ≥ 526 全绿（非沙盒环境跑，防 WinError 5 假象）
- [ ] 协议文档修订：01（payload）/03（台账）/04（derive 联动）/05（H9 族）/09（epoch_1 生效记录 + CHANGELOG）

## 9. 写集与禁区对照

- **写集**：`models/ledger.py`、`models/state.py`、`models/event.py`、`reducers/plot.py`、`validator.py`（仅 H9 族）、`llm_extract.py`（仅 PAYLOAD_SCHEMA + 尺戳，**串行 #70 后**）、`derive.py`（仅联动校验，**串行 b3 后**）、`plot_engine/revision.py`（仅 RULE_TO_LEVEL 登记 H9 族）、`tests/`（新增/增补）、`alexandria-spec-v0.2/`（协议修订）
- **禁区核对**：不碰 `ai_flavor_*.py`（他人在做面）；不碰集成中枢（live/review/experiment 归 WP-0）；码批期间若有生成批在跑则冻结等待（指南 §2）

---

> 本稿为冻结候选。冻结方式：tff 审查 → 批注 → 定稿 → 记入 alexandria-spec CHANGELOG（epoch_1 生效）。冻结前基于本稿的任何代码均视为无效。
