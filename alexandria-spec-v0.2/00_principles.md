# 00 原则与术语

> 版本：v0.2（2026-10-08 同步修订：HARD 分类增 Extraction、边界矩阵增 markup 职责与 ScenePlan、术语表扩充）
> epoch：epoch_0（定义见 09 §2.5）

## 1. 八条核心原则

### P1. LLM 不直接修改 State
LLM 只能生成 Proposal；State 变更必须经过
Validate → Reduce → Commit 三段管道。

### P2. 所有故事事实必须通过 Event 表达
不经 Event 的状态变更一律非法。
"发生过什么"是唯一的事实来源。

### P3. 所有 Event 必须经过确定性验证后才能 Commit
HARD violations 非空 → 拒绝 Commit。
SOFT / OBSERVATION 只记录，不阻断。

### P4. Chapter Contract 必须来源于 Arc Contract
Chapter Contract 不得自我生成、自我验证。
每条约束必须记录 derived_from。

### P5. Knowledge 必须区分三层
World Fact     ≠  Character Knowledge  ≠  Character Belief
三层独立存储，不得混用。

### P6. Revision 必须寻找错误根因
Revision 不是"多写几遍"，而是"定位错误发生在哪一层"。
错误层级决定回退层级。

### P7. 协议变更必须有 epoch 与迁移路径
"冻结"不是口头承诺。
同一 epoch 内只允许向后兼容的新增字段。

### P8. 所有 Event 必须可 Replay
Replay 结果必须与在线 Commit 一致。
不一致视为架构级 bug，停止 pipeline。

## 2. 分层职责

```text
Arc Contract      ← 结构级约束
    ↓
Chapter Contract  ← 章级约束
    ↓
ScenePlan         ← Scene / Beat 场景级意图（Schema 见 04 附录 B，v0.2 新增）
    ↓
Writer            ← 文本生成（必须携带 07 §4.4 markup 标注）
    ↓
Proposal          ← 事件候选（抽取置信度联动见 07 §4.3）
    ↓
Validator         ← 确定性验证（规则唯一来源 05 §4）
    ↓
Reducer           ← 状态投影（StoryState 聚合根见 10 §13）
    ↓
Commit            ← 原子事务（WAL + CAS + Replay 校验）
    ↓
Snapshot          ← 持久化
```

## 3. LLM 边界矩阵

| 角色 | 可见 | 禁止可见 |
|------|------|----------|
| Arc Planner | objective_truth | — |
| Chapter Planner | narrative_truth | objective_truth |
| Scene Planner | Chapter Contract 全量 | gate 之外的 hidden fact 细节 / objective_truth |
| Writer | Chapter Contract + ScenePlan + WriterView | hidden_truth / false_leads / 候选池 |
| Evaluator | ScorerView | hidden_truth |
| Validator (LLM 层) | Draft + Contract | objective_truth |

Writer 附加职责（v0.2）：Draft 必须携带 07 §4.4 规定的 markup 标注——
`<!-- hook: ... -->` 必一条，`<!-- reader_learns/hinted/deceived: fact_id -->` 按 Contract.reader_signals 要求。

## 4. HARD / SOFT / OBSERVATION 三层

```text
HARD 阻断 Commit
    Canon / Knowledge / Timeline / Resource / Contract / Event / Extraction（H8，v0.2 新增）

SOFT 只记录
    Pacing / Repetition / Style / Dialogue / Sensory
    （v0.2 起张力曲线规则 R3'~R6' 与 tension_target 比对也归入 SOFT，见 04 §3.2）

OBSERVATION 只落盘
    Suspense / Emotion / Reader Beat / Literary Quality
    （v0.2 起 Phase 0 的因果图环警告归入 OBSERVATION，见 01 §5.2 R1'）
```

## 5. 术语

| 术语 | 定义 |
|------|------|
| Event | 状态变更的唯一合法载体（01） |
| Proposal | 未 commit 的 Event 候选（07 §4.2） |
| Fact | 世界层事实，双层真相（02） |
| Knowledge | 角色知道的事实（03 §4） |
| Belief | 角色相信的内容（03 §5） |
| Entity / World State | 角色/地点/物品/势力/境界/关系/库存等实体层（10，v0.2 新增） |
| Contract | 可验证的剧情约束（04） |
| ScenePlan / Beat | Chapter Contract 与 Writer 之间的规划层（04 附录 B，v0.2 新增） |
| Draft markup | Writer 在 Draft 中的 `<!-- ... -->` 标注，规则通道的确定性输入（07 §4.4） |
| Commit | 原子事务（07） |
| Snapshot | 状态快照（07 §7.3） |
| Event Log | append-only 事件日志 |
| epoch | 协议版本（09；epoch_0 定义见 09 §2.5） |
| Replay | 从 Event Log 重建 State（01 §6 / 07 §7.5） |
| CAS | 乐观锁：save(state, expected_version) |
| WAL | Write-Ahead Log：先日志后状态 |
| DAG | 有向无环图，Event 因果图与 Fact Relation 图应满足（Phase 0 警告，Phase 1 硬） |
| Canonical 序列化 | key 升序 + 定点整数的 JSON 规范，Replay 哈希的唯一依据（05 §5.5） |
| 定点化 | 浮点一律 ×1000 存整数，禁止 float 进入 Replay 关键路径（05 §5.5） |