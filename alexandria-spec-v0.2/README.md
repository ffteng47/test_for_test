# Alexandria v0.2 协议规格

> 冻结日期：2026-10-08
> 冻结版本：epoch_0（重冻结定义见 09 §2.5：epoch_0 := v0.2 文档集）
> 目的：Phase 0 的 10 章实验所需的最小协议集
> 变更历史：见 CHANGELOG.md（v0.1 → v0.2，含落盘记录）

## 本规格回答什么

Alexandria 如何让一个非确定性的 LLM，在 10 个连续章节中
遵守一个确定性的故事世界。

## 核心原则（8 条）

① LLM 不直接修改 State。
② 所有故事事实必须通过 Event 表达。
③ 所有 Event 必须经过确定性验证后才能 Commit。
④ Chapter Contract 必须来源于 Arc Contract，而不能自我生成、自我验证。
⑤ Knowledge 必须区分 World Fact、Character Knowledge 和 Character Belief。
⑥ Revision 必须寻找错误根因，而不是无限重写文本。
⑦ 协议变更必须有 epoch 与迁移路径，"冻结"不是口头承诺。
⑧ 所有 Event 必须可 Replay，且 Replay 结果必须与在线 Commit 一致
（确定性保障：05 §5.5 canonical 序列化 + 全整型定点化）。

## 协议清单

| 文件 | 内容 | 状态 |
|------|------|------|
| 00_principles.md | 原则、流水线层级（含 ScenePlan）、边界矩阵、术语 | v0.2 修订 |
| 01_event_protocol.md | Event 分类（6 类 26 型，含 Reader/Item/Relationship）、Schema、因果、Replay | v0.2 重写 |
| 02_fact_protocol.md | Fact 本体（唯一定义处）、双层真相、Fact Relation（Phase 0 静态 DAG） | v0.2 修订 |
| 03_knowledge_protocol.md | Knowledge / Belief / Reader 三层与 Reducer（引用 02，含 FACT_CONTRADICTED） | v0.2 重写 |
| 04_contract_protocol.md | Arc / Chapter Contract（含 reader_signals）、附录 B：Scene / Beat Schema | v0.2 重写 |
| 05_validation_protocol.md | HARD H1~H8 / SOFT / OBSERVATION 三层验证 + §5.5 Canonical 序列化规范 | v0.2 修订 |
| 06_revision_protocol.md | Root Cause 分类（含 extraction）与回退层级 | v0.2 修订 |
| 07_commit_protocol.md | Proposal → Validate → Reduce → Commit（四通道抽取、隔离制、Replay 校验） | v0.2 重写 |
| 08_experiment_protocol.md | 3.5 周排期、10 章实验协议、Freeze Gate、退出条件 E1'~E6' | v0.2 修订 |
| 09_versioning.md | epoch 迁移流程 + §2.5 epoch_0 重冻结定义 | v0.2 修订 |
| 10_world_state_protocol.md | 实体与世界状态：Character / Location / Item / Faction / Realm / Relationship / Inventory / Ability / Region / StoryState | v0.2 新增 |
| CHANGELOG.md | v0.1 → v0.2 变更草案 + 落盘记录 | v0.2 新增 |

## 文档层级

```text
alexandria-spec-v0.2/      ← 协议层 source of truth
    ↓ 实现
alexandria/plot_engine/    ← 代码
    ↑ 参考
工程落地.txt                ← 早期架构设想（已被 spec 取代，降级为历史文档）
target-architecture.md     ← 一期部署范围（仍有效，source of truth）
```

**spec 是协议层的唯一事实来源。**

## 单一来源规则（v0.2 新增）

- Fact Schema 唯一定义处：02 §3（03 / 04 / 05 / 10 只引用）
- HARD / SOFT / OBSERVATION 规则清单唯一定义处：05 §4~§6（07 只引用）
- Scene / Beat Schema 唯一定义处：04 附录 B（08 只引用）
- 实体 / StoryState Schema 唯一定义处：10（01 / 03 / 05 只引用）
- 浮点一律 ×1000 定点化为 int：规范见 05 §5.5

## 使用方式

1. 所有实现代码必须引用本规格中定义的 Schema
2. 任何字段增删必须走 09_versioning.md 的 epoch 升级
3. 任何 HARD 规则增删必须走 epoch 升级
4. Phase 0 期间（Day 1~25，排期见 08 §5）禁止任何协议层面的"临时例外"

## 术语速查

- **Event**：状态变更的唯一合法载体
- **Proposal**：未 commit 的 Event 候选，可丢弃；置信度过低者隔离重抽取（07 §4.3）
- **Fact**：世界层的事实，有 narrative_truth / objective_truth 双层
- **Knowledge**：角色知道的事实（可信）
- **Belief**：角色相信的内容（可假）
- **Reader Ledger**：读者认知台账，仅由 READER_* 事件驱动（03 §6）
- **Contract**：可验证的剧情约束
- **ScenePlan**：Chapter Contract 与 Writer 之间的 Scene / Beat 计划（04 附录 B）
- **Draft markup**：Writer 在正文中嵌入的 `<!-- hook -->` / `<!-- reader_learns -->` 标注（07 §4.4）
- **Commit**：状态变更的原子事务
- **epoch**：协议版本，跨 epoch 不可直接混用；epoch_0 定义见 09 §2.5
- **定点化**：所有浮点字段 ×1000 存为整数，保障 Replay 位级一致（05 §5.5）
