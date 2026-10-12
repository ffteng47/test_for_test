# 01 Event 协议

> 版本：v0.2
> 冻结日期：2026-10-08
> epoch：epoch_0（定义见 09 §2.5）
> 上位协议：00_principles.md
> 数据依赖：10_world_state_protocol.md（实体 Schema）、02（Fact）、03（Ledger）

## 1. 目的与范围

定义 Alexandria 中所有状态变更的唯一合法载体：Event。

- Event 是"发生过什么"的不可变记录。
- State 是 Event 经过 Reducer 后的当前投影。
- 任何不经 Event 的状态变更一律非法。

本协议不含：Event 如何生成（Plot/Writer 层）、Event 如何验证（Validator 层，见 05）、Event 如何存储（Store 层，见 07）。

## 2. 核心原则

| # | 原则 |
|---|------|
| E1 | 不可变：Event 一经 commit，永不修改、永不删除 |
| E2 | 可重放：给定同一 Event 序列，Reducer 必须产出同一 State（整数定点运算，05 §5.5） |
| E3' | 因果完整性（v0.2 放宽）：Phase 0 preconditions / causes 可为空；因果图环检测仍执行但只警告；同章内按 seq 全序即可。Phase 1 升为 HARD |
| E4 | 有拓扑：同章内 Event 构成 DAG，跨章按 chapter_no + seq 全序 |
| E5 | 有版本：所有 Event 携带 epoch，跨 epoch 不可直接混用 |
| E6 | 可拒收：未在 Taxonomy 中定义的 event_type 一律拒收 |
| E7 | 数值定点：payload 与元数据中的一切"浮点"均为 ×1000 定点整数（05 §5.5） |

## 3. Event Taxonomy（v0.2：6 类 26 型）

Event 分六类，每类对应独立 Reducer 路径，禁止合并。

### 3.1 KnowledgeEvents（知识事件）

角色获得事实（写入 Knowledge Ledger，03 §4）。

```text
OBSERVES          亲历观察      → knowledge_strength 高，source = 场景
READS             阅读文档      → 中，source = 文档
IS_TOLD           被他人告知    → 中，source = 说话人（带 trust_level）
INFERS            自己推断      → 中，source = 推断链（preconditions 指向证据 Event）
FACT_CONTRADICTED 事实矛盾冲击  → 持有者相关 Knowledge/Belief 降级（03 §5.4）
```

### 3.2 BeliefEvents（信念事件）

角色形成或改变看法（写入 Belief Ledger，可含假）。

```text
BELIEVES   相信为真      → belief_strength 高
SUSPECTS   怀疑          → 中低
DOUBTS     动摇          → 降低已有信念
```

### 3.3 StatementEvents（陈述事件）

角色对外的言语行为。不写自己的 Knowledge/Belief，只写听众的 Belief。

```text
STATES   如实陈述      → 听众 IS_TOLD（trust = 说话人可信度）
LIES     故意谎报      → 听众 BELIEVES（内容为假）
OMITS    隐瞒          → 听众 Knowledge 不变，但记录 "未告知"
HINTS    暗示          → 听众 SUSPECTS（弱）
```

关键：LIES 更新的是听众的 Belief，不是世界 Fact，也不是说话人的 Belief。说话人自己的 Belief 保持不变。

### 3.4 WorldEvents（世界事件）

世界客观状态变化，与角色认知无关。实体落点见 10 §4.3。

```text
HAPPENS              事件发生      → 更新 World State
REVEALS              真相揭示      → 翻转 Fact.narrative_truth
CHANGES              状态改变      → 角色字段变更（field 枚举见 §4.1）
ITEM_ACQUIRED        获得物品      → Inventory 表新增/合并（10 §10.1）
ITEM_CONSUMED        消耗物品      → Inventory 表扣减（quantity >= 0）
RELATIONSHIP_CHANGED 关系变更      → Relationship 表（建立/变更/终结，10 §9.1 R4）
```

### 3.5 ReaderEvents（读者事件，v0.2 新增）

叙事文本对读者认知的作用，唯一写入 Reader Ledger 的通道（03 §6）。
由 Draft 标注 `<!-- reader_learns/hinted/deceived: fact_id -->` 确定性抽取产生（07 §4.4）。

```text
READER_LEARNS    叙事文本使读者获知某 fact   → reader_state = knows
READER_DECEIVED  叙事文本使读者形成错误印象  → reader_state = deceived
READER_HINTED    叙事文本给读者暗示          → reader_state = hinted
```

### 3.6 PlotEvents（剧情事件）

剧情结构层的事件，影响 Arc/Chapter 进度。

```text
CASE_SOLVED
FORESHADOWING_SET
FORESHADOWING_PAID
CONTRACT_FULFILLED
CONTRACT_VIOLATED
```

分类纪律：写 Event 时必须明确属于六类中的哪一类。跨类语义（如"主角发现叛徒"）必须拆成多个 Event（OBSERVES + INFERS），不得塞进一个 Event 的 payload。

## 4. Event Schema

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

EventType = Literal[
    # Knowledge（5）
    "OBSERVES", "READS", "IS_TOLD", "INFERS", "FACT_CONTRADICTED",
    # Belief（3）
    "BELIEVES", "SUSPECTS", "DOUBTS",
    # Statement（4）
    "STATES", "LIES", "OMITS", "HINTS",
    # World（6）
    "HAPPENS", "REVEALS", "CHANGES",
    "ITEM_ACQUIRED", "ITEM_CONSUMED", "RELATIONSHIP_CHANGED",
    # Reader（3）
    "READER_LEARNS", "READER_DECEIVED", "READER_HINTED",
    # Plot（5）
    "CASE_SOLVED", "FORESHADOWING_SET", "FORESHADOWING_PAID",
    "CONTRACT_FULFILLED", "CONTRACT_VIOLATED",
]

class Event(BaseModel):
    # 标识
    event_id: str = Field(..., pattern=r"^evt_\d{8}_\d{3}$")  # evt_00000047_003
    epoch: str = Field(..., pattern=r"^epoch_\d+$")           # epoch_0
    schema_version: int = 2

    # 分类
    event_type: EventType

    # 主体
    actor: Optional[str]                 # 执行者（char_id）；World 事件可为空
    target: Optional[str]                # 受体（char_id / fact_id / item_id / loc_id）
    location: Optional[str]              # 发生地点（loc_id）

    # 时序
    chapter: int = Field(..., ge=1)
    scene: Optional[str]                 # scn_id（04 附录 B）
    seq: int = Field(..., ge=0)          # 同一章内的顺序，从 0 起

    # 因果（E3'：Phase 0 允许为空）
    preconditions: List[str] = []        # 前置 event_id（若填写必须已 commit）
    causes: List[str] = []               # 后果 event_id（可空，允许后续回填）

    # 载荷（按 event_type 严格区分，见 §4.1）
    payload: Dict = {}

    # 元数据
    confidence: int = Field(1000, ge=0, le=1000)  # 抽取置信度，定点 ×1000（07 §4.3）
    source_ref: Optional[str] = None     # 正文段落引用，用于 Debug
```

### 4.1 payload 规范（按类型）

```python
OBSERVES:
  fact_id: str              # 观察到的事实（02 §3）
  method: str               # "sight" | "hearing" | "touch" | "inference"

IS_TOLD:
  speaker: str              # 告知者 char_id
  fact_id: str
  trust_level: int          # 0~1000，告知者可信度（定点）
  message_strength: int     # 0~1000，陈述强度（定点）
  # Reducer: strength_fixed = (trust_fixed * message_fixed) // 1000（05 §5.5）

INFERS:
  conclusion_fact_id: str   # 推断结论
  evidence_fact_ids: list   # 证据事实列表

FACT_CONTRADICTED:
  fact_id: str              # 被削弱/证伪的结论
  contradicting_fact_id: str  # 反证（03 §5.4，字段名以其为准）

BELIEVES:
  fact_id: str
  belief_strength: int      # 0~1000

STATES:
  audience: list            # 听众 char_id 列表
  fact_id: str

LIES:
  audience: list
  stated_fact_id: str       # 声称的内容（可能是假 fact）
  actual_belief_id: str     # 说话人真实信念（与 stated 不同）

REVEALS:
  fact_id: str
  new_narrative_truth: str  # "true" | "false" | "unknown"

CHANGES:
  field: Literal["status", "realm", "location", "faction",
                 "attributes", "abilities"]   # v0.2 统一枚举（10 §14）
  old_value: Any
  new_value: Any
  # 不再允许 inventory / relationship（改用 ITEM_* / RELATIONSHIP_CHANGED）

ITEM_ACQUIRED:
  character_id: str
  item_id: str
  quantity: int             # >= 1

ITEM_CONSUMED:
  character_id: str
  item_id: str
  quantity: int             # >= 1，扣减后总量 >= 0（H4.2）

RELATIONSHIP_CHANGED:
  from: str                 # char_id
  to: str                   # char_id
  relationship_type: str    # 10 §9 枚举
  strength_delta: int       # -1000~1000（定点增量）
  trust_delta: int          # -1000~1000

READER_LEARNS / READER_DECEIVED / READER_HINTED:
  fact_id: str              # 读者认知涉及的 fact
  # 唯一来源：Draft 标注通道（07 §4.4 M1~M3；缺失即 H2.3 违规，05 §4）
```

## 5. Event 因果关系

### 5.1 两类关系

| 关系 | 语义 | 方向 |
|------|------|------|
| preconditions | 必须已 commit 的前置事件 | 反向（指向已发生） |
| causes | 本次导致的后续事件 | 正向（可延迟回填） |

### 5.2 强制规则（v0.2 分级）

```text
R1'. 图结构：Event 图应为 DAG
      Phase 0：检测到环只落 finding（H6.3 SOFT 化），不阻断 Commit
      Phase 1：升为 HARD
R2.  前置性：preconditions 非空时，引用的 event_id 必须已 commit
R3.  时序性：preconditions 的 chapter <= 当前 chapter
R4.  跨章约束：causes 若指向未 commit 的事件，允许；
      但 preconditions 不允许指向未来事件（H6.5 保持 HARD）
R5.  自环：causes 不得包含自身
R6.  章内排序：同章内按 seq 升序应用（Phase 0 唯一强制顺序）
```

### 5.3 环检测

Commit 前必须执行：

```python
def detect_cycle(events: List[Event]) -> Optional[List[str]]:
    """返回环上的 event_id 列表，无环返回 None"""
```

Phase 0：检测到环 → 落 finding `EVENT_CYCLE_WARNING`，不拒绝 Commit。
Phase 1：检测到环 → 拒绝整章 Commit，进 rejection_log，触发 Revision。

## 6. Replay 协议

### 6.1 Replay 输入

```text
- 起始快照（snapshot at chapter N）
- Event Log 从 N+1 到目标 chapter
```

### 6.2 Replay 算法

```text
1. 加载快照 → state_0
2. 按 (chapter, seq) 排序所有 events
3. 对每个 event：
    a. 校验 preconditions 全部满足（若填写）
    b. 应用 Reducer（按 event_type 分派，03 §8 / 10）
    c. 校验不变量（assert_consistent）
4. 输出 state_target
```

### 6.3 Replay 一致性保证

```text
P1. 同一 Event 序列，Replay 与在线 Commit 必须产出同一 State
P2. State 的 hash 必须匹配（state_hash = SHA256(canonical_json(state))，05 §5.5）
P3. 任何不一致视为架构级 bug：回滚 Commit、落 REPLAY_INCONSISTENT、停止 pipeline（07 §7.5）
```

### 6.4 确定性来源

Replay 位级一致依赖三条硬约束：

```text
D1. Canonical 序列化：05 §5.5（key 字典序、无空白、UTF-8）
D2. 全整型定点化：一切 strength / confidence / tension / trust / attribute
    均为 int（×1000），禁止 float 进入 Replay 关键路径
D3. Reducer 纯函数：同一 (state, event) 必须产出同一 state'，
    不得读取时钟 / 随机数 / 环境
```

## 7. Epoch 与版本

### 7.1 epoch 定义

epoch_0 := v0.2 冻结版本（重冻结条款见 09 §2.5）。

```text
epoch_0: Phase 0 冻结版本（v0.2 文档集）
epoch_1: 第一次协议变更后的版本
...
```

### 7.2 升级触发条件（任一）

```text
- Event type 增删改
- payload 字段增删改
- 因果规则变更
- Reducer 语义变更
```

### 7.3 升级流程

```text
1. 冻结当前 epoch 的写入（进入只读模式）
2. 全量 Replay 验证（必须通过）
3. 执行迁移脚本
4. 开放新 epoch 写入
5. 旧 epoch 数据永久只读
```

### 7.4 迁移保证

```text
M1. 迁移脚本必须幂等
M2. 迁移后新 State 的 Replay 结果必须与迁移前一致
M3. 迁移失败必须可回滚到迁移前快照
```

## 8. 附录：JSON 示例

```json
{
  "event_id": "evt_00000047_003",
  "epoch": "epoch_0",
  "schema_version": 2,
  "event_type": "INFERS",
  "actor": "char_000001",
  "target": "fact_000001",
  "location": "loc_000012",
  "chapter": 47,
  "scene": "scn_0047_01",
  "seq": 3,
  "preconditions": ["evt_00000047_001", "evt_00000047_002"],
  "causes": [],
  "payload": {
    "conclusion_fact_id": "fact_000001",
    "evidence_fact_ids": ["fact_000003", "fact_000004"]
  },
  "confidence": 1000,
  "source_ref": "chapter_47_para_12"
}
```

## 9. 不变量（Invariants）

```text
I1. 每个 Event 的 event_id 全局唯一
I2. 同 (chapter, seq) 下只有一个 Event
I3. Event 图应为 DAG（Phase 0 检出环只落 finding，见 §5.3）
I4. preconditions 非空时，指向的 Event 均存在且已 commit
I5. 所有 event_type ∈ Taxonomy（六类 26 型）
I6. 所有 Event 的 epoch 与当前写入 epoch 一致
I7. Replay 结果与在线结果位级一致（canonical hash 相等）
I8. Draft 中每个 <!-- reader_learns/hinted/deceived --> 标注必须对应一条
    READER_* Event（07 §4.4 M2；缺失即 05 H2.3 HARD 违规）
I9. payload / 元数据中的全部数值为 int；Replay 路径禁止 float 运算（§6.4 D2）
```
