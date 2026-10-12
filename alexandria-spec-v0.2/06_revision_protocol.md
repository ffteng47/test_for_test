# 06 修订协议

> 版本：v0.2（RootCause 新增 extraction 层，优先级最高；回退层级表新增 §4.0）
> epoch：epoch_0（定义见 09 §2.5）

## 1. 目的

定义 Alexandria 中"当 Commit 失败时如何修复"的规则。
Revision 不是"多写几遍"，而是"定位错误发生在哪一层"。

## 2. 核心原则

| # | 原则 |
|---|------|
| R1 | Revision 必须先分类 Root Cause |
| R2 | 错误层级决定回退层级 |
| R3 | Revision 必须有收敛策略（max_rounds / 成本上限） |
| R4 | Revision 不得无限重写正文 |
| R5 | Contract 错误不得用重写正文弥补 |
| R6 | Revision 过程必须记录（用于后续调优） |

## 3. Root Cause 分类

```python
class RootCause(BaseModel):
    level: Literal[
        "extraction",   # v0.2 新增：Proposal 抽取错误，优先级最高（见 §4.0）
        "writer",       # 正文没按 Contract 写
        "contract",     # Chapter Contract 本身有问题
        "arc",          # Arc Contract 与当前状态矛盾
        "fact",         # Fact Ontology 无法归一化
        "event",        # Event 无法表达某语义
        "validator",    # Validator 规则误报
        "state",        # State 本身已不一致
    ]
    evidence: str
    violated_rule_id: Optional[str]
    confidence: int           # v0.2：定点 ×1000（0~1000，05 §5.5），禁止 float
4. 回退层级映射
text
Violation
    ↓
Classify Root Cause
    ↓
┌──────────────┬──────────────┬──────────────┐
│              │              │              │
Writer Error   Contract Error  Arc Error
│              │              │
Scene Rewrite  Contract        Arc Replan
               Renegotiate
4.0 Extraction Error（v0.2 新增，优先级最高）
症状：

- Proposal 抽取置信度 < 500（H8.1）或被隔离（H8.2，500~699）

- Draft 中明显发生的事件未被抽取

- 抽取出的 Event 与 Draft 语义不符（H8.3 SOFT 提示 + 人工确认）

- 同一 Draft 两次抽取结果不一致

- reader_*/hook markup 标注存在但规则通道未生成对应 Proposal

处理：

- 回退 Stage 0，重跑抽取（调整 prompt / 更换模型 / 要求 Writer 补 markup）

- 不触发 Writer 重写正文

- 不触发 Contract 重议

- 连续 2 轮未收敛 → 若违规集中在 Writer 内容 → 转 4.1；若 Taxonomy 无法表达 → 转 4.5

4.1 Writer Error
症状：

Contract 合理，但 Draft 未实现

角色说话不符合 VoiceBank

出现 forbidden_event

处理：

重写 Scene（不整章重写）

保留 Contract 不变

4.2 Contract Error
症状：

Contract 要求的事件在当前 State 下无法发生

Contract 的知识约束与 Arc 矛盾

Contract 的 tension_target 与 arc.tension_curve 冲突

处理：

重议 Chapter Contract

触发 Chapter Contract 重新生成

不重写 Draft

4.3 Arc Error
症状：

Arc 的 knowledge_gate 与角色当前状态矛盾

Arc 的 turning_point 在本 Arc 内无法达成

Arc 的 tension_curve 与故事进展不符

处理：

回退到 Arc 层重规划

重生成 Arc Contract

重生成受影响的 Chapter Contract

4.4 Fact Error
症状：

同一语义在 Fact 库中无法归一化

Fact Relation 图出现环

canonical_form 冲突

处理：

修 Fact Ontology

迁移已有 Fact（走 epoch 升级）

4.5 Event Error
症状：

某语义无法用现有 Event Taxonomy 表达

Event 因果图无法构造

处理：

扩 Event Taxonomy（走 epoch 升级）

4.6 Validator Error
症状：

Validator 误报（HARD 规则过严）

Validator 漏报（HARD 规则不足）

处理：

修 Validator 规则

记录误报/漏报案例

4.7 State Error
症状：

当前 State 本身已不一致

Replay 结果与 State 不匹配

处理：

停止 pipeline

回滚到最近一致性快照

排查不一致来源

5. 收敛策略
python
class RevisionPolicy(BaseModel):
    max_rounds: int = 3
    escalation: List[str] = [
        "rerun_extraction",       # v0.2 新增，置于最前
        "rewrite_scene",
        "rewrite_chapter",
        "renegotiate_contract",
        "escalate_to_arc",
    ]
    oscillation_detection: bool = True
    cost_ceiling_per_chapter_usd: float = 0.5
    human_escalation_threshold: int = 3
6. Revision 流程
text
1. 收到 ValidationResult
2. 分类 Root Cause
3. 按 Root Cause 选择回退层级
4. 执行回退
5. 重跑 Stage 0 → Stage 3
6. 若仍 FAIL：
     round += 1
     若 round >= max_rounds → 升级到下一层级
     若总 round >= human_escalation_threshold → 人工介入
7. 若 SUCCESS → 记录 RevisionTrace → 继续
7. 振荡检测
text
若连续两轮 Revision 的 violation 集合：
  - 第一轮：{A, B}
  - 第二轮：{B, A}（顺序不同但集合相同）
→ 判定为振荡
→ 立即升级到下一层级
→ 不允许继续在同一层级重试
8. 成本上限
text
R1. 每章 Revision 成本上限（默认 $0.5）
R2. 超过上限 → 停止 Revision，标记为 NEEDS_HUMAN
R3. 成本计入 Story Budget
R4. 成本异常告警
9. RevisionTrace
python
class RevisionTrace(BaseModel):
    trace_id: str
    story_id: str
    chapter_no: int

    round: int
    root_cause: RootCause
    action: str
    result: Literal["OK", "FAIL", "ESCALATED"]

    tokens_used: int
    cost_usd: float
    duration_ms: int

    timestamp: str
10. 不变量
text
I1. Revision 必须分类 Root Cause 后才能执行
I2. Revision 不得跳过层级（Extraction → Writer → Contract → Arc，v0.2 起 Extraction 最先）
I3. 振荡必须被检测并升级
I4. 成本上限必须被强制
I5. 所有 Revision 必须落 RevisionTrace
I6. Contract 错误不得用重写正文弥补
I7. Revision 后必须重跑完整 Validator
11. 与 07_commit_protocol 的接口
text
Stage 1 FAIL → 触发 Revision
Revision 完成后 → 重跑 Stage 0 → Stage 3
Stage 3 CONFLICT → 重新拉取 State → 重跑 Stage 0（非 Revision）