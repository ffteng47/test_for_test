# 04 Contract 协议

> 版本：v0.2
> 冻结日期：2026-10-08
> epoch：epoch_0（定义见 09 §2.5）
> 上位协议：00_principles.md
> 引用：Fact 定义见 02 §3；实体 ID 定义见 10_world_state_protocol.md；
> 数值定点化见 05 §5.5；ReaderSignal 对应 01 §3.5 ReaderEvents

## 1. 目的与范围

定义 Alexandria 中剧情约束的唯一合法载体：Contract。

Contract 是"本章/本 Arc 必须发生什么、禁止发生什么"的可验证规范。
Contract 不是 Prompt，不是建议，而是 Validator 的输入。
任何 Writer 生成的 Draft，必须逐条对照 Contract 才能进入 Commit。

本协议不含：Contract 如何生成（Plot 层）、Contract 如何被验证（Validator 层）。
Scene / Beat 规划层 Schema 见本文件附录 B（v0.2 新增，08 实验依赖）。

## 2. 核心原则

| # | 原则 |
|---|------|
| C1 | 可验证：Contract 中每一条都必须能被程序判定 true/false |
| C2 | 来源有据：Chapter Contract 必须从 Arc Contract 派生，不得自我生成 |
| C3 | 分层约束：Arc 级不变量 > Chapter 级约束 > Scene/Beat 级意图 |
| C4 | 硬软分离：硬约束可阻断 Commit，软约束只记录 |
| C5 | 不可膨胀：Contract 字段有限，不得演变为自然语言大段描述 |
| C6 | 可追溯：每条约束必须记录来源（哪个 Arc 目标、哪个 Knowledge Gate） |

## 3. Arc Contract

### 3.1 Schema

```python
class KnowledgeGate(BaseModel):
    """知识闸门：谁在第几章之后可以知道什么"""
    fact_id: str
    allowed_characters: List[str]        # 允许知道的角色（空 = 所有角色）
    allowed_after_chapter: int           # 允许知道的最早章节
    must_reveal_by_chapter: Optional[int] = None   # 必须揭示的最晚章节
    reveal_stage_target: Literal["hidden", "hinted", "partial", "confirmed"]

class TurningPoint(BaseModel):
    """Arc 转折点"""
    chapter: int
    type: Literal["reversal", "revelation", "escalation", "crisis", "climax"]
    description: str
    required_event_types: List[str]      # 该章必须出现的 Event 类型（01 §3）

class ArcContract(BaseModel):
    arc_id: str = Field(..., pattern=r"^arc_\d{3}$")
    epoch: str

    # 结构约束（HARD）
    chapter_range: Tuple[int, int]                    # (start, end)
    # SOFT 元数据（v0.2：张力规则整体降档，见 §3.2）
    tension_curve: List[int] = []                     # 每章目标张力 ×1000，长度 = end-start+1
    turning_points: List[TurningPoint]
    knowledge_gates: List[KnowledgeGate]

    # 元数据（SOFT，Phase 0 不进 Validator）
    reader_beats: List[dict] = []
    theme: Optional[str] = None

    created_at: str
    schema_version: int = 2
```

### 3.2 tension_curve 规则（v0.2：全部降为 SOFT）

| # | 规则 | 等级 |
|---|------|------|
| R1 | 长度必须严格等于 chapter_range 的章数 | HARD（结构） |
| R2 | 值域 [0, 1000]（×1000 定点化） | HARD（结构） |
| R3' | 连续 3 章张力差 < 50（疑似注水） | **SOFT**，只落 finding |
| R4' | 连续 5 章张力单调上升（疑似疲劳） | **SOFT**，只落 finding |
| R5' | 每 10 章内至少 1 次张力 ≥ 800 | **SOFT**，只落 finding |
| R6' | turning_points 所在章张力 ≥ 700 | **SOFT**，只落 finding |

> v0.2 理由：伪定量规则会把小说倒过来拟合数字。R3'~R6' 供 Phase 1 Critic 使用，
> Phase 0 一律不阻断 Commit。

### 3.3 knowledge_gates 规则

| # | 规则 | 等级 |
|---|------|------|
| R1 | 每个 gate 引用一个已存在的 fact_id | HARD |
| R2 | allowed_after_chapter ∈ chapter_range | HARD |
| R3 | must_reveal_by_chapter ≥ allowed_after_chapter | HARD |
| R4 | 同一 fact 允许多个 gate（不同角色不同闸门） | — |
| R5 | gate 必须覆盖所有"反转类" fact（objective_truth = false 且 narrative_truth = true） | HARD（Arc 自校验） |
| R6 | Phase 0：reader_beats 不产生 gate，reader knowledge 只做记录 | — |

## 4. Chapter Contract

### 4.1 Schema

```python
class CharacterChange(BaseModel):
    character_id: str
    # v0.2：field 枚举与 10 §4.3 映射表严格对齐
    field: Literal[
        "knowledge", "belief",            # → Knowledge/Belief Ledger
        "location", "realm", "status",    # → CHANGES(field=...)
        "faction", "attributes", "abilities",  # → CHANGES(field=...)
        "relationship",                   # → RELATIONSHIP_CHANGED
        "inventory",                      # → ITEM_ACQUIRED / ITEM_CONSUMED
    ]
    operation: Literal["add", "remove", "update"]
    target: str                           # fact_id / loc_id / item_id / char_id / realm_id
    expected_value: Optional[Any] = None

class RequiredEvent(BaseModel):
    event_type: str                       # ∈ 01 §3 Taxonomy
    description: str
    minimum_count: int = 1
    actors_involved: List[str] = []
    must_be_visible_to_reader: bool = True

class ForbiddenEvent(BaseModel):
    event_type: str
    description: str
    reason: str                           # 为什么禁止（追溯来源）

class ChapterHook(BaseModel):
    type: Literal["cliffhanger", "revelation", "decision", "arrival", "question", "none"]
    strength: int = Field(..., ge=0, le=1000)   # ×1000
    description: str

class ReaderSignal(BaseModel):            # v0.2 新增，对应 01 §3.5 / 03 §6
    fact_id: str
    target_state: Literal["unaware", "hinted", "knows", "deceived"]
    established_in_scene: Optional[str] = None   # scn_id

class ChapterContract(BaseModel):
    chapter_no: int
    arc_id: str
    epoch: str
    version: int = 1                      # 修订记于此（见 §6 I3/I4）

    story_goal: str                       # 人类可读
    story_goal_type: Literal[
        "revelation", "escalation", "setup", "resolution",
        "transition", "confrontation", "reflection"
    ]

    # 硬约束
    must_change: List[CharacterChange] = []
    must_not_change: List[CharacterChange] = []
    required_events: List[RequiredEvent] = []
    forbidden_events: List[ForbiddenEvent] = []

    # 知识约束（从 Arc knowledge_gates 派生）
    knowledge_allowed: List[str] = []
    knowledge_forbidden: List[str] = []

    # 读者信号（v0.2 新增）
    reader_signals: List[ReaderSignal] = []

    # 剧情推进
    plot_progress: Dict[str, int] = {}    # 线程进度 ×1000，SOFT
    tension_target: int = Field(500, ge=0, le=1000)   # ×1000，SOFT

    # 章尾
    ending: ChapterHook

    # 元数据
    derived_from: List[str] = []
    created_at: str
    schema_version: int = 2
```

### 4.2 字段语义

| 字段 | 类型 | HARD/SOFT | 说明 |
|------|------|-----------|------|
| story_goal | 描述 | SOFT | 给 Writer 的方向，不直接验证 |
| story_goal_type | 枚举 | HARD | 决定 Validator 用哪套检查规则 |
| must_change | 结构化 | HARD | 每条必须被对应 Event 实现（映射表 10 §4.3） |
| must_not_change | 结构化 | HARD | 任何相反变更即违规 |
| required_events | 结构化 | HARD | 至少出现 minimum_count 次 |
| forbidden_events | 结构化 | HARD | 出现 1 次即违规 |
| knowledge_allowed/forbidden | fact_id 列表 | HARD | 从 Arc gates 派生 |
| reader_signals | 结构化 | **SOFT**（Phase 0 只记录命中） | v0.2 新增；HARD 判定见 05 H2.3 对标注的校验 |
| plot_progress | 数值 | SOFT | 记录用，不阻断 |
| tension_target | 数值 | **SOFT**（v0.2 降档） | 供 Critic 评估；与曲线偏差 > 200 落 finding |
| ending.type | 枚举 | HARD | 章尾必须出现匹配 `<!-- hook: ... -->` 标注（05 H5.5 / 07 §4.4） |
| ending.strength | 数值 | SOFT | 供 Critic 评估 |

### 4.3 派生规则（Chapter ← Arc）

| # | 规则 |
|---|------|
| D1 | chapter_no 必须在 arc.chapter_range 内 |
| D2' | **v0.2 修订**：tension_target 为 SOFT 记录——与 arc.tension_curve[chapter_no - start] 比对，偏差 > 200 落 finding，不阻断 |
| D3 | 若 chapter_no 命中 turning_point：required_events 必须包含其 required_event_types（HARD） |
| D4 | knowledge_allowed 从 gate 派生：chapter_no ≥ gate.allowed_after_chapter 且（allowed_characters 为空或含本章角色）→ 加入 |
| D5 | knowledge_forbidden 从 gate 派生：chapter_no < gate.allowed_after_chapter → 加入 |
| D6 | 若 chapter_no > gate.must_reveal_by_chapter 且该 gate 未出现在 required_events → Chapter Contract 非法（HARD） |
| D7 | must_change / must_not_change 必须显式声明 derived_from |
| D8 | ending.type 必须与 story_goal_type 兼容（§4.4） |
| D9 | v0.2：reader_signals 引用的 fact_id 必须存在；target_state 与 gate 不冲突（未到期 gate 的 fact 不得标 knows） |
| D10 | **epoch_1 补记（v0.12 裁定 1A）**：每条 must_change 必须存在可兑现其 Δ 的 required_event（field→事件映射 10 §4.3）。derive 阶段前置拦截：不满足 → `ArcConflict`（06 §4.3 归属登记——Arc 输入错误，不是重写可修）；不许让它烧满三轮修订才以 H5.3 现形 |
| D11 | **epoch_1 新增（v0.12 裁定 4A）**：伏笔限期单源——`ForeshadowingEntry.due_by_chapter` 必须等于同名 fact 的 `gate.must_reveal_by_chapter`；漂移 → derive 抛 `ArcConflict`（回 Arc 层修账，抽取侧不得发明第二个期限） |

### 4.4 story_goal_type 与 ending.type 兼容矩阵

```text
revelation      → revelation / cliffhanger
escalation      → cliffhanger / decision
setup           → question / arrival
resolution      → none / decision
transition      → arrival / decision
confrontation   → cliffhanger / decision
reflection      → question / none
不兼容组合：Chapter Contract 非法，拒绝接受。
```

## 5. Contract 校验

### 5.1 Contract 自校验（生成后、使用前）

| # | 规则 | 等级 |
|---|------|------|
| V1 | Schema 完整（所有必填字段存在） | HARD |
| V2 | chapter_no 与 arc_id 存在且匹配 | HARD |
| V3 | tension_target 与 arc.tension_curve 比对 | **SOFT**（v0.2 降档） |
| V4 | knowledge_forbidden 与 knowledge_allowed 无交集 | HARD |
| V5 | required_events 与 forbidden_events 无同类型冲突 | HARD |
| V6 | must_change 与 must_not_change 无同字段冲突 | HARD |
| V7 | ending.type 与 story_goal_type 兼容（§4.4） | HARD |
| V8 | derived_from 中引用的 Arc 项均存在 | HARD |
| V9 | 所有 fact_id / character_id / location_id / item_id / realm_id 存在（02 / 10） | HARD |
| V10 | v0.2：must_change/must_not_change 的 field ∈ §4.1 枚举 | HARD |

### 5.2 Draft 对照 Contract 校验（Commit 前）

| # | 规则 |
|---|------|
| W1 | 每条 must_change 是否被 10 §4.3 映射表指定的 Event 类型实现？ |
| W2 | 每条 must_not_change 是否被相反变更违反？ |
| W3 | 每个 required_event 是否至少出现 minimum_count 次？ |
| W4 | 是否有 forbidden_event 出现？ |
| W5 | Draft Proposal 中是否有角色建立 knowledge_forbidden 中的 fact？ |
| W6 | Contract 要求建立的知识（must_change field=knowledge）是否缺失？ |
| W7 | Draft 末尾是否含 `<!-- hook: <type> strength=<0-1000> -->` 标注且 type == contract.ending.type？（05 H5.5 / 07 §4.4；缺失标注 = HARD） |
| W8 | reader_signals 命中情况（SOFT，Phase 0 只记录） |
| W9 | tension_target 匹配（SOFT，Phase 0 只记录） |

W1~W7 是 HARD，W8/W9 是 SOFT。

## 6. 不变量

```text
I1. 每个 Chapter 的每个 version 恰好有一个生效 Chapter Contract
I2. Chapter Contract 必须派生自一个已存在的 Arc Contract
I3. 同一 version 的 Contract 一经用于 Commit 不可修改；
    内容变更必须 version+1（修订记入 version 字段与变更原因），禁止原地改写
I4. Contract 变更必须显式记录变更原因（与 I3 同一机制）
I5. Contract 中所有引用（fact_id/character_id/...）必须存在于当前 Story State
I6. Contract 的 schema_version 必须与当前 epoch 一致
I7. knowledge_allowed/forbidden 不得同时包含同一 fact
```

## 7. 附录 A：完整示例（v0.2）

```json
{
  "chapter_no": 47,
  "arc_id": "arc_003",
  "epoch": "epoch_0",
  "version": 1,
  "story_goal": "张三在宗门大殿发现伪造印章，推断宗门内部存在叛徒，但无法确定身份",
  "story_goal_type": "revelation",
  "must_change": [
    { "character_id": "char_000001", "field": "knowledge", "operation": "add",
      "target": "fact_000003", "expected_value": "known" },
    { "character_id": "char_000001", "field": "knowledge", "operation": "add",
      "target": "fact_000001", "expected_value": "suspected" }
  ],
  "must_not_change": [
    { "character_id": "char_000001", "field": "knowledge", "operation": "update",
      "target": "fact_000002" }
  ],
  "required_events": [
    { "event_type": "OBSERVES", "description": "张三观察到伪造印章",
      "minimum_count": 1, "actors_involved": ["char_000001"],
      "must_be_visible_to_reader": true },
    { "event_type": "INFERS", "description": "张三推断宗门存在叛徒",
      "minimum_count": 1, "actors_involved": ["char_000001"],
      "must_be_visible_to_reader": true }
  ],
  "forbidden_events": [
    { "event_type": "REVEALS", "description": "揭示叛徒身份",
      "reason": "arc_003.knowledge_gates[fact_000002].allowed_after_chapter = 84" }
  ],
  "knowledge_allowed": ["fact_000001", "fact_000003"],
  "knowledge_forbidden": ["fact_000002"],
  "reader_signals": [
    { "fact_id": "fact_000003", "target_state": "knows",
      "established_in_scene": "scn_0047_01" }
  ],
  "plot_progress": { "main_thread": 80 },
  "tension_target": 720,
  "ending": { "type": "cliffhanger", "strength": 800,
    "description": "张三凝视印章，意识到叛徒可能就在身边" },
  "derived_from": [
    "arc_003.knowledge_gates[fact_000002]",
    "arc_003.turning_points[47]"
  ],
  "created_at": "2026-10-08T10:00:00Z",
  "schema_version": 2
}
```

---

## 8. 附录 B：Scene / Beat Schema（v0.2 新增）

> 08 实验协议"Plot → Scene → Beat → Writer"链路的规格依据。
> ScenePlan 是规划产物，**不进入 Event Log、不是 Contract**；
> 它被 Contract 约束、被 Validator 的 SP 规则自校验、供 Writer 消费。

### 8.1 层级

```text
Chapter Contract（04 §4）
    ↓ 派生（HARD：SP2/SP3/SP4）
ScenePlan：3~7 个 Scene
    ↓
Scene：3~7 个 Beat
    ↓
Writer（逐 Scene 生成 Draft 片段，拼装为整章 Draft）
```

### 8.2 Schema

```python
class Beat(BaseModel):
    beat_id: str = Field(..., pattern=r"^bt_\d{6}$")
    seq: int = Field(..., ge=0)               # 场景内顺序
    intent: str                                # 一句话意图（SOFT，供 Writer）
    beat_type: Literal["setup", "pressure", "turn", "release", "foreshadow"]

    # 结构化字段（scope-reduction C6：规则只比枚举/数值，不做关键词匹配）
    action_type: Optional[Literal[
        "combat", "dialogue", "investigation",
        "travel", "ritual", "reveal", "status_change"
    ]] = None
    actors: List[str] = []                     # char_id
    actor_realm: Optional[str] = None          # realm_id（H1.4 判定输入，10 §16）
    target_realm: Optional[str] = None
    location: Optional[str] = None             # loc_id

    expected_event_types: List[str] = []       # 本 Beat 预期触发的 01 §3 事件类型
    reader_target: Optional[Literal["learns", "hinted", "deceived"]] = None
    reader_fact_id: Optional[str] = None

class Scene(BaseModel):
    scene_id: str = Field(..., pattern=r"^scn_\d{4}_\d{2}$")   # scn_0047_01
    chapter_no: int
    seq: int = Field(..., ge=0, le=6)
    location: Optional[str] = None
    characters: List[str] = []
    purpose: str = ""                          # SOFT
    tension: int = Field(500, ge=0, le=1000)   # ×1000，SOFT
    beats: List[Beat] = Field(..., min_length=3, max_length=7)

class ScenePlan(BaseModel):
    plan_id: str = Field(..., pattern=r"^sop_\d{8}$")
    chapter_no: int
    arc_id: str
    contract_version: int                      # 绑定的 Chapter Contract 版本
    scenes: List[Scene] = Field(..., min_length=3, max_length=7)
    derived_from: List[str] = []               # 指向 Contract 条目
    epoch: str
    created_at: str
    schema_version: int = 2
```

### 8.3 ScenePlan 自校验（确定性，供 05 引用）

| # | 规则 | 等级 |
|---|------|------|
| SP1 | 所有引用的 char_id / loc_id / realm_id / fact_id 存在（10 / 02） | HARD |
| SP2 | ∪(beat.expected_event_types) 必须覆盖 contract.required_events 的每个 event_type | HARD |
| SP3 | 任何 beat 不得声明 contract.forbidden_events 中的 event_type | HARD |
| SP4 | contract.reader_signals 的每条 signal 必须被至少一个 beat（reader_target/reader_fact_id）覆盖 | HARD |
| SP5 | beat.location 若声明，必须在该 Scene 的 characters 各自 current_location 可达范围内（10 §5.1 W-S4）；travel 类 beat 除外 | HARD |
| SP6 | 同章内 scene_id / beat_id 唯一 | HARD |
| SP7 | scene.tension 与 contract.tension_target 偏差 | SOFT |

### 8.4 Scene 与 Writer / Revision 的接口

- Writer 以 Scene 为最小生成单位；一个 Scene 的 Draft 片段失败
  （Writer Error，06 §4.1）时**只重写该 Scene**，不整章重写。
- ScenePlan 可在不违反 SP2/SP3 的前提下重新生成（06 §4.0/§4.1）。
- Draft 拼装后按 07 §4.4 的 markup 规范携带 `<!-- hook: ... -->` 与
  `<!-- reader_learns/hinted/deceived: fact_id -->` 标注。
