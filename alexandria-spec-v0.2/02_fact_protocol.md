# 02 Fact 协议

> 版本：v0.2（fact_id 升 6 位；§5 增 Phase 0 静态关系条款；本协议为 Fact 唯一定义处，03 §3 已改为引用）
> epoch：epoch_0（定义见 09 §2.5）
> 宿主状态：Fact / FactRelation 实例存于 StoryState.facts / fact_relations（10_world_state_protocol.md §13）

## 1. 目的

定义 Alexandria 中"世界事实"的最小本体。
Fact 是比 Knowledge 更底层的概念：
- Knowledge 记录"谁知道了哪个 Fact"
- Belief 记录"谁相信了哪个 Fact"
- Reader 记录"读者知道了哪个 Fact"

## 2. 核心原则

| # | 原则 |
|---|------|
| F1 | Fact 有双层真相：narrative_truth / objective_truth |
| F2 | Fact 之间有关系：evidence_for / confirms / contradicts / implies / derives_from |
| F3 | Fact Relation 必须构成 DAG，禁止环 |
| F4 | narrative_truth 可随 REVEALS 翻转；objective_truth 不随章节变 |
| F5 | Writer 只能看到 narrative_truth；Arc Planner 才能看到 objective_truth |
| F6 | Fact 一经定义不可删除，只能新增 related_facts 或更新 reveal_stage |

## 3. Fact Schema

```python
class Fact(BaseModel):
    fact_id: str = Field(..., pattern=r"^fact_\d{6}$")
    fact_type: Literal["existence", "identity", "relation", "event", "state"]

    proposition: str          # 人类可读："宗门内存在叛徒"
    canonical_form: str       # 机器可比对："traitor_exists(sect_A)"

    related_facts: List[str] = []

    # 双层真相
    narrative_truth: Literal["true", "false", "unknown"]
    objective_truth: Literal["true", "false", "unknown"]

    reveal_stage: Literal["hidden", "hinted", "partial", "confirmed"] = "hidden"

    defined_at_chapter: int
    epoch: str
4. fact_type 语义
type	含义	示例
existence	存在性	"宗门内存在叛徒"
identity	身份	"李四是叛徒"
relation	关系	"张三是李四的师兄"
event	事件	"印章 17 是伪造品"
state	状态	"李四已死"
5. Fact Relation Schema
python
class FactRelation(BaseModel):
    relation_id: str
    source_fact_id: str
    target_fact_id: str
    relation_type: Literal[
        "evidence_for",    # A 是 B 的证据
        "confirms",        # A 确认 B
        "contradicts",     # A 与 B 矛盾
        "implies",         # A 蕴含 B
        "derives_from",    # A 从 B 推断而来
    ]
    strength: int = Field(1000, ge=0, le=1000)   # v0.2：定点 ×1000（05 §5.5），禁止 float
    epoch: str
```
6. 双层真相规则
6.1 为什么需要双层
长篇反转必须依赖"叙事层"和"客观层"的分离。

例：

第 1~40 章：叙事层认定"李四是叛徒"，所有角色相信

第 41 章：揭示"李四被陷害"

若只有一真值 → 要么反转不可实现，要么违反不可变性

6.2 规则
text
R1. narrative_truth 可以随 REVEALS 事件翻转
R2. objective_truth 只在 Arc 层定义，不随章节变
R3. 任何时刻：narrative_truth 可能与 objective_truth 不同
R4. Writer 只能看到 narrative_truth
R5. Arc Planner 可以看到 objective_truth
R6. Reader 看到的是 narrative_truth 的当前呈现
R7. narrative_truth != objective_truth 时，reveal_stage 不得为 confirmed
7. Fact Relation DAG
text
R1. 关系图必须是 DAG
R2. Commit 前必须执行环检测
R3. evidence_for 与 derives_from 方向一致（都是"从证据到结论"）
R4. contradicts 是双向语义，存储时只存一条
R5. 关系的增删必须通过 Event（不是直接修改）
R6. v0.2 Phase 0：Fact Relation 视为静态——Arc 初始化时定义，运行期不变；
    FACT_RELATION_ADDED / REMOVED 事件类型留待 v0.3（epoch 升级引入）
8. 不变量
text
I1. fact_id 全局唯一
I2. canonical_form 在同一 epoch 内唯一
I3. related_facts 引用的 fact 必须存在
I4. Fact Relation 图无环
I5. objective_truth 一经定义不可修改
I6. narrative_truth 翻转必须由 REVEALS 事件触发
I7. 所有 Fact 必须可被 Replay 重建
9. 示例
json
[
  {
    "fact_id": "fact_000001",
    "fact_type": "existence",
    "proposition": "宗门内存在叛徒",
    "canonical_form": "traitor_exists(sect_A)",
    "related_facts": ["fact_000002", "fact_000003"],
    "narrative_truth": "true",
    "objective_truth": "true",
    "reveal_stage": "hinted",
    "defined_at_chapter": 47,
    "epoch": "epoch_0"
  },
  {
    "fact_id": "fact_000002",
    "fact_type": "identity",
    "proposition": "李四是叛徒",
    "canonical_form": "traitor_identity(sect_A, li_si)",
    "related_facts": ["fact_000001"],
    "narrative_truth": "unknown",
    "objective_truth": "false",
    "reveal_stage": "hidden",
    "defined_at_chapter": 47,
    "epoch": "epoch_0"
  }
]