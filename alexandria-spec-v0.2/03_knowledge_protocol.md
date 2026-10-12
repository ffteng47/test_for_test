# 03 Knowledge 协议

> 版本：v0.2
> 冻结日期：2026-10-08
> epoch：epoch_0（定义见 09 §2.5）
> 上位协议：00_principles.md
> Fact Schema 唯一定义处：02_fact_protocol.md §3（v0.2 起本协议不再重定义）
> 数值定点化：遵循 05 §5.5（浮点一律 ×1000 存整数）

## 1. 目的与范围

定义 Alexandria 中"谁知道什么、相信什么、读者知道什么"的完整模型。

三层分离：

```text
World Fact          客观真相（narrative_truth / objective_truth，见 02）
Character Knowledge 角色知道的事实（可信）
Character Belief    角色相信的内容（可能为假）
Reader Knowledge    读者知道的信息
```

本协议不含：Fact 如何生成（Plot 层）、Knowledge 如何验证（Validator 层）、
实体 Schema（10_world_state_protocol.md）。

## 2. 核心原则

| # | 原则 |
|---|------|
| K1 | Fact ≠ Knowledge ≠ Belief：三者独立存储，不混用 |
| K2 | Knowledge 可信，Belief 可假：Knowledge 来自亲历/可靠来源，Belief 来自陈述/推断 |
| K3 | Knowledge ≠ Statement：角色说 X 不等于角色知道 X，也不等于听众相信 X |
| K4 | Reader 独立：读者知道什么与角色无关，由作者层控制 |
| K5 | 双层真相：Fact 有 narrative_truth 和 objective_truth（定义见 02） |
| K6 | 可追溯：每条 Knowledge/Belief/Reader 记录必须有 source_event |
| K7 | v0.2：所有 Ledger 变更必须由 Event 驱动（含 Reader，经 READER_* 事件） |

## 3. Fact Protocol（引用，不再重定义）

Fact 与 FactRelation 的 Schema、双层真相规则、关系语义与环检测，
**唯一来源为 `02_fact_protocol.md` §3~§7**。

本协议只定义 Knowledge / Belief / Reader 三层如何引用 Fact：

- 任何 `fact_id` 必须匹配 02 §3 的正则 `^fact_\d{6}$`
- `narrative_truth` 翻转只由 `REVEALS` 事件触发（01 §4.1）
- 同一语义的归一化以 `canonical_form` 为准（02 §8 I2）

## 4. Knowledge Ledger

### 4.1 Schema

```python
class KnowledgeEntry(BaseModel):
    character_id: str              # char_id（10 §4）
    fact_id: str                   # fact_id（02 §3）
    knowledge_state: Literal["unknown", "suspected", "believed", "known", "confirmed"]
    strength: int = Field(..., ge=0, le=1000)   # 定点化 ×1000

    source_event_id: str           # 建立/最后增强本记录的 Event（可多个，见 R1.5）
    acquired_at_chapter: int
    last_updated_chapter: int

    epoch: str
```

### 4.2 knowledge_state 语义

| state | 含义 | 典型来源 |
|-------|------|----------|
| unknown | 完全不知道 | 默认 |
| suspected | 有弱迹象 | HINTS / SUSPECTS / INFERS |
| believed | 相信为真 | IS_TOLD 低信任 / BELIEVES |
| known | 确定知道 | OBSERVES / READS / IS_TOLD 高信任 |
| confirmed | 确证（多重来源） | 多条 known 交叉 |

state 序：`unknown < suspected < believed < known < confirmed`

### 4.3 更新规则（定点化）

| # | 规则 |
|---|------|
| R1 | OBSERVES → state 至少 known，strength ≥ 900 |
| R2 | READS → state 至少 known，strength ≥ 800 |
| R3 | IS_TOLD → state 至少 believed，strength = trust_level × message_strength ÷ 1000（整数除，05 §5.5） |
| R4 | INFERS → state 至少 suspected，strength = min(证据 strength) 经置信度折算 |
| R5 | 同一 fact 多次事件 → 取最强，且记录所有 source_event_id |
| R6 | Event 不得**静默**降低 state；唯一降级路径为显式 `FACT_CONTRADICTED`（01 §3.1 / 本文件 §5.4） |
| R7 | 状态序内只升只降都必须由 Event 触发，禁止旁路改写 |

## 5. Belief Ledger

### 5.1 Schema

```python
class BeliefEntry(BaseModel):
    character_id: str
    fact_id: str
    belief_state: Literal["doubts", "suspects", "believes"]
    strength: int = Field(..., ge=0, le=1000)    # 定点化 ×1000

    source_event_id: str
    acquired_at_chapter: int
    last_updated_chapter: int

    is_true: Optional[bool] = None   # 与世界 truth 的一致性（事后计算派生值，不参与 Replay 关键路径）

    epoch: str
```

### 5.2 Knowledge 与 Belief 的边界

```text
- Knowledge 是"知道"（可信）；Belief 是"相信"（可假）
- 一个角色可以同时：
    Knowledge: fact_X unknown
    Belief:    fact_X believes (strength = 700)
- 允许 Knowledge 与 Belief 矛盾（这是戏剧张力的来源，必须显式记录，不是错误）
```

### 5.3 与 StatementEvents 的关系

| # | 规则 |
|---|------|
| R1 | STATES → 听众 BeliefEntry 更新（trust = 说话人可信度） |
| R2 | LIES → 听众 BeliefEntry 更新（内容 = stated_fact）；说话人自身 Belief 不变；记录 lie_event 引用 |
| R3 | OMITS → 听众无更新，但记录 omission_event |
| R4 | HINTS → 听众 BeliefEntry 更新为 suspects |

### 5.4 FACT_CONTRADICTED 的降级语义（v0.2 新增）

```python
FACT_CONTRADICTED:            # payload 见 01 §4.1
  fact_id: str                    # 被削弱的结论
  contradicting_fact_id: str      # 反证
```

Reducer 行为：

| 当前态 | 降级后 | strength |
|--------|--------|----------|
| confirmed / known | suspected | 取原值 × 0.4（定点化） |
| believed / suspected | doubts（Belief 侧）/ suspected | 取原值 × 0.4 |
| unknown | 不变，落 OBSERVATION | — |

- 降级同样可 Replay、进 Ledger 的 last_updated_chapter
- R6（02 §5 contradicts 关系）提供静态矛盾，FACT_CONTRADICTED 提供运行期降级事件

## 6. Reader Knowledge

### 6.1 Schema

```python
class ReaderKnowledgeEntry(BaseModel):
    fact_id: str
    reader_state: Literal["unaware", "hinted", "knows", "deceived"]
    reader_strength: int = Field(..., ge=0, le=1000)   # 定点化 ×1000

    established_at_chapter: int
    last_updated_chapter: int
    source_event_id: str         # v0.2 必填：READER_* 事件（01 §3.5）

    epoch: str
```

### 6.2 规则

| # | 规则 |
|---|------|
| R1 | Reader 与 Character 完全独立 |
| R2 | Reader 的知识由作者层控制（叙事呈现），不受角色行为影响 |
| R3 | **v0.2 修订**：Reader "知道"的唯一合法来源 = Draft markup 显式声明（07 §4.4）→ Stage 0 规则通道生成 READER_* Proposal → Commit 写入 Ledger。叙事文本本身不再"隐式"影响 Reader |
| R4 | Reader "被骗"（deceived）是合法状态，对应 READER_DECEIVED |
| R5 | Writer 不得直接修改 Reader Ledger，只能通过带 markup 的 Draft 间接影响 |

### 6.3 Reader Reducer（v0.2 新增）

```python
def apply_reader_learns(self, event, state):
    """READER_LEARNS   → reader_state = "knows", strength = max(旧值, payload.strength)"""

def apply_reader_deceived(self, event, state):
    """READER_DECEIVED → reader_state = "deceived"（对应 fact.narrative_truth 制造的错误印象）"""

def apply_reader_hinted(self, event, state):
    """READER_HINTED   → reader_state = "hinted"（unaware → hinted；不回退已 knows 的记录）"""
```

## 7. 一致性约束（Validator 使用，供 05 H2 引用）

```text
C1. 角色出场时，其 Knowledge/Belief 状态必须与当前 State 一致
C2. 角色使用某 fact 时，必须满足 knowledge_state ∈ {known, confirmed}
    或显式声明为 belief（允许错误行为）
C3. 角色不能使用"从未学过"的技能/物品（实体校验数据源见 10 §16）
C4. dead / unborn 角色不得产生新 Knowledge/Belief（10 §4.1 W7）
C5. Contract 的 knowledge_gates 必须被尊重：第 N 章前不得让角色越过闸门
C6. REVEALS / READER_* 事件必须引用存在的 fact_id
C7. Reader 一致性（05 H2.3 判定依据）：
    Draft 有 <!-- reader_learns: fact_id --> 标注 → 必须有对应 READER_LEARNS Proposal
    Ledger 有 READER_* 记录但本章 Draft 无对应标注 → SOFT 警告
C8. Belief 与 Knowledge 的矛盾必须显式记录（是特征不是错误）
```

## 8. Reducer 接口

```python
class KnowledgeReducer:
    def apply(self, event: Event, state: StoryState) -> StoryState:
        """按 event_type 分派，更新 Knowledge/Belief/Reader Ledger。
        StoryState 定义见 10_world_state_protocol.md §13。"""

    # Knowledge
    def apply_observes(self, event, state): ...
    def apply_reads(self, event, state): ...
    def apply_is_told(self, event, state): ...
    def apply_infers(self, event, state): ...
    def apply_fact_contradicted(self, event, state): ...
    # Belief
    def apply_believes(self, event, state): ...
    def apply_suspects(self, event, state): ...
    def apply_doubts(self, event, state): ...
    # Statement → 听众 Belief
    def apply_states(self, event, state): ...
    def apply_lies(self, event, state): ...
    def apply_omits(self, event, state): ...
    def apply_hints(self, event, state): ...
    # World（事实层）
    def apply_reveals(self, event, state): ...
    # Reader（v0.2 新增）
    def apply_reader_learns(self, event, state): ...
    def apply_reader_deceived(self, event, state): ...
    def apply_reader_hinted(self, event, state): ...
```

## 9. 附录：完整示例（v0.2 定点化 + 6 位 ID）

场景：第 47 章，张三发现伪造印章，推断宗门有叛徒，但未确定是谁；
读者同时获知"印章为伪"。

Facts（定义见 02，此处引用）：

```json
[
  { "fact_id": "fact_000001", "proposition": "宗门内存在叛徒",
    "canonical_form": "traitor_exists(sect_A)",
    "narrative_truth": "true", "objective_truth": "true",
    "reveal_stage": "hinted", "defined_at_chapter": 47, "epoch": "epoch_0" },
  { "fact_id": "fact_000002", "proposition": "李四是叛徒",
    "canonical_form": "traitor_identity(sect_A, li_si)",
    "narrative_truth": "unknown", "objective_truth": "false",
    "reveal_stage": "hidden", "defined_at_chapter": 47, "epoch": "epoch_0" },
  { "fact_id": "fact_000003", "proposition": "印章 17 为伪造品",
    "canonical_form": "forged_seal(seal_17, sect_A)",
    "narrative_truth": "true", "objective_truth": "true",
    "reveal_stage": "confirmed", "defined_at_chapter": 47, "epoch": "epoch_0" }
]
```

Events：

```json
[
  { "event_id": "evt_00000047_001", "epoch": "epoch_0", "schema_version": 2,
    "event_type": "OBSERVES", "actor": "char_000001", "target": "fact_000003",
    "location": "loc_000012", "chapter": 47, "scene": "scn_0047_01", "seq": 0,
    "preconditions": [], "causes": [],
    "payload": { "fact_id": "fact_000003", "method": "sight" },
    "confidence": 1000, "source_ref": "para:4" },
  { "event_id": "evt_00000047_002", "epoch": "epoch_0", "schema_version": 2,
    "event_type": "INFERS", "actor": "char_000001", "target": "fact_000001",
    "chapter": 47, "scene": "scn_0047_02", "seq": 1,
    "preconditions": ["evt_00000047_001"], "causes": [],
    "payload": { "conclusion_fact_id": "fact_000001", "evidence_fact_ids": ["fact_000003"] },
    "confidence": 700, "source_ref": "para:6" },
  { "event_id": "evt_00000047_003", "epoch": "epoch_0", "schema_version": 2,
    "event_type": "READER_LEARNS", "chapter": 47, "scene": "scn_0047_01", "seq": 2,
    "preconditions": ["evt_00000047_001"], "causes": [],
    "payload": { "fact_id": "fact_000003", "strength": 900 },
    "confidence": 1000, "source_ref": "markup:reader_learns#1" }
]
```

Knowledge Ledger 结果：

```json
[
  { "character_id": "char_000001", "fact_id": "fact_000003",
    "knowledge_state": "known", "strength": 1000,
    "source_event_id": "evt_00000047_001",
    "acquired_at_chapter": 47, "last_updated_chapter": 47, "epoch": "epoch_0" },
  { "character_id": "char_000001", "fact_id": "fact_000001",
    "knowledge_state": "suspected", "strength": 700,
    "source_event_id": "evt_00000047_002",
    "acquired_at_chapter": 47, "last_updated_chapter": 47, "epoch": "epoch_0" }
]
```

Belief Ledger 结果：无变化（张三未被告知、未确认）。

Reader Ledger 结果：

```json
[
  { "fact_id": "fact_000003", "reader_state": "knows", "reader_strength": 900,
    "established_at_chapter": 47, "last_updated_chapter": 47,
    "source_event_id": "evt_00000047_003", "epoch": "epoch_0" }
]
```

注意：fact_000002（李四是叛徒）在所有 Ledger 中均无记录——这是正确的：
本章没有任何角色知道或相信它，objective_truth = false（Arc 层已定义但未揭示）。

## 10. 不变量

```text
I1. 每条 KnowledgeEntry/BeliefEntry/ReaderKnowledgeEntry 必须引用存在的 fact_id
I2. 每条记录必须有 source_event_id，且该 Event 已 commit
I3. knowledge_state 演进必须单调——唯一例外是显式 FACT_CONTRADICTED（§5.4）
I4. Reader Knowledge 与 Character Knowledge 独立
I5. narrative_truth 与 objective_truth 不一致时，reveal_stage 不得为 confirmed（02 §8 I5）
I6. Writer Draft 中角色使用某 fact 时，对应 Ledger 状态必须满足 C2
I7. 所有 Ledger 更新必须由 Event Log 完整 Replay（含 Reader）
I8. 一切定点化数值必须为整数（05 §5.5），禁止 float 参与 Replay 关键路径
```
