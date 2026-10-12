# 09 版本与迁移协议

> 版本：v0.2（新增 §2.5 epoch_0 重冻结条款）
> 冻结日期：2026-10-08

## 1. 目的

定义 Alexandria 中"协议如何演进"的规则。
"冻结"不是口头承诺，而是有明确升级路径的工程约定。

## 2. 核心原则

| # | 原则 |
|---|------|
| V1 | 每个 Event/Fact/Contract 携带 epoch |
| V2 | 同一 epoch 内只允许向后兼容的新增字段 |
| V3 | 跨 epoch 必须提供迁移脚本 |
| V4 | 迁移后旧 epoch 数据只读 |
| V5 | 迁移必须可回滚 |
| V6 | 迁移必须通过全量 Replay 验证 |

## 2.5 epoch_0 的重冻结定义（v0.2 新增）

```text
R1. epoch_0 的内容定义 = v0.2 文档集（2026-10-08 重冻结版，README 协议清单所列 11 份）。
    v0.1（2026-10-06）对 epoch_0 的定义作废。
R2. 依据：本文件 §4 升级触发条件 T1/T2/T5（Event 增删、payload 变更、HARD 增删）。
    但 epoch_0 数据面为空——v0.2 重冻结发生在 08 §5 Day 4 开工之前，
    不存在任何已 Commit 的 epoch_0 数据，故无迁移对象。
R3. 因此本次不升 epoch_1：直接以"重新定义 epoch_0 冻结内容"方式生效，
    这是本条款的一次性豁免，仅限"零数据重冻结"情形。
R4. 自 Day 4 起写入的第一条 Event 开始，任何 §4 触发条件一律走 epoch_1 升级 + 迁移，
    不得再援引本条款。
R5. 全量 Replay 验证在 v0.2 冻结 Gate 中以"空集验证"通过（0 条数据，恒成立）。
```

## 3. epoch 定义
epoch_0: Phase 0 冻结版本（内容以 v0.2 文档集为准，见 §2.5）
epoch_1: 第一次协议变更后的版本
epoch_2: ...

text

## 4. 升级触发条件

满足任一条件即触发 epoch 升级：
T1. Event type 增删改
T2. payload 字段增删改
T3. Fact canonical_form 规则变化
T4. Contract 必填字段变化
T5. Validator HARD 规则增删
T6. Reducer 语义变更
T7. 因果规则变更

text

## 5. 升级流程
冻结当前 epoch 的写入（进入只读模式）

全量 Replay 验证（必须通过）

编写迁移脚本

在 staging 环境执行迁移

验证迁移后 State 与迁移前一致

在生产环境执行迁移

开放新 epoch 写入

旧 epoch 数据永久只读

text

## 6. 迁移脚本要求

```python
class Migration:
    from_epoch: str
    to_epoch: str

    def migrate_state(self, state: StoryState) -> StoryState:
        """纯函数：旧 State → 新 State"""

    def migrate_event(self, event: Event) -> Event:
        """纯函数：旧 Event → 新 Event"""

    def migrate_fact(self, fact: Fact) -> Fact:
        ...

    def migrate_contract(self, contract: Contract) -> Contract:
        ...
要求：

text
M1. 迁移脚本必须幂等
M2. 迁移脚本必须是纯函数
M3. 迁移后新 State 的 Replay 结果必须与迁移前一致
M4. 迁移失败必须可回滚
M5. 迁移必须记录 MigrationTrace
7. 向后兼容规则
同一 epoch 内：

text
允许：
  - 新增可选字段（默认值必须有）
  - 新增 Event type（不影响旧数据）
  - 新增 Soft 规则

不允许：
  - 删除字段
  - 修改字段语义
  - 修改 HARD 规则
  - 修改 Reducer 行为
  - 修改 Event 因果规则
8. MigrationTrace
python
class MigrationTrace(BaseModel):
    migration_id: str
    from_epoch: str
    to_epoch: str

    records_migrated: int
    records_failed: int
    duration_ms: int

    replay_consistency_before: bool
    replay_consistency_after: bool

    result: Literal["OK", "FAIL", "ROLLED_BACK"]
    timestamp: str
9. 回滚
text
R1. 迁移前必须备份
R2. 迁移失败 → 从备份恢复
R3. 迁移成功但 Replay 不一致 → 从备份恢复
R4. 回滚必须记录
R5. 回滚后旧 epoch 保持只读
10. 不变量
text
I1. 任何数据必须携带 epoch
I2. 跨 epoch 不允许直接 Commit
I3. 迁移必须通过全量 Replay 验证
I4. 迁移必须可回滚
I5. 迁移必须幂等
I6. 旧 epoch 数据永久只读