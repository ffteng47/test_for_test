# 08 实验协议

> 版本：v0.2（排期重排 3.5 周；退出条件改为收敛制；新增 Scene/Beat 层与 Extraction 失败分类）
> epoch：epoch_0（定义见 09 §2.5）

## 1. 目的

定义 Phase 0 的 10 章实验协议。
实验目标不是"证明 Alexandria 能写好小说"，而是：

> 证明 Alexandria 能否让一个非确定性的 LLM，
> 在 10 个连续章节中遵守一个确定性的故事世界。

## 2. 实验输入

```python
class ExperimentConfig(BaseModel):
    story_id: str
    chapters: int = 10
    arc_contract: ArcContract
    initial_state: StoryState
    seed: int
    epoch: str
    model_router_config: dict
3. 实验输出
python
class ExperimentReport(BaseModel):
    experiment_id: str
    config: ExperimentConfig

    # 生成结果
    chapters_generated: int
    chapters_committed: int

    # 硬指标
    hard_violations: Dict[str, int]   # 按 rule_id 分类
    soft_warnings: Dict[str, int]
    observations: Dict[str, int]

    # 状态完整性
    canon_contradictions: int
    knowledge_contradictions: int
    timeline_contradictions: int

    # Replay 一致性
    replay_consistency: bool
    replay_mismatch_chapters: List[int]

    # Revision
    revision_rounds: Dict[int, int]   # 每章 revision 轮数
    revision_success_rate: float
    unresolved_chapters: List[int]

    # 成本
    total_tokens: int
    total_cost_usd: float

    # 时间
    total_duration_ms: int

    timestamp: str
4. 硬指标（Phase 0 唯一 KPI）
text
┌─────────────────────────────────────┬──────────┐
│ 指标                                │ 目标     │
├─────────────────────────────────────┼──────────┤
│ Canon contradiction                 │ 0        │
│ Knowledge contradiction             │ 0        │
│ Timeline contradiction              │ 0        │
│ Character impossible action         │ 0        │
│ Dead character reappears            │ 0        │
│ Unavailable item used               │ 0        │
│ Forbidden knowledge leak            │ 0        │
│ Required plot event missing         │ 0        │
│ Replay inconsistency                │ 0        │
└─────────────────────────────────────┴──────────┘
Phase 0 不追求"好看"，只追求"不崩"。

5. 实验流程（v0.2 重排，总计 3.5 周）
text
Day 1-3    Protocol Freeze（v0.2）
           - 复跑引用一致性检查清单（docs/alexandria-spec-consistency-check.md §4）
           - 冻结 00~10 全部 11 份协议 + epoch_0 定义（09 §2.5）

Day 4-7    State Store + EventLog + Reducer
           - StoryState（10 §13）+ canonical 序列化（05 §5.5）
           - append-only Event Log + CAS + Snapshot（N=5）

Day 8-11   Validator（HARD 规则集）
           - H1 / H2 / H3 / H4 / H5 / H6 / H7 / H8 全量确定性实现
           - markup 解析通道（07 §4.4）

Day 12-13  Commit 事务
           - 四阶段管道 + Commit 后 Replay 校验（07 §7.5）

Day 14-16  Plot → Scene → Beat
           - Arc/Chapter Contract 派生（04）
           - ScenePlan 生成 + SP1~SP7 自校验（04 附录 B）

Day 17-19  Writer 对接 + Extraction
           - 四通道 Proposal 生成与置信度联动（07 §4.3）
           - 双通道交叉验证

Day 20-22  10 Chapter Experiment
           - 跑 10 章，记录所有硬指标
           - 不做美化，允许失败

Day 23-25  Architecture Review
           - 分析 Failure Classification
           - 决定是否进入 Phase 1
5.5 Scene / Beat 层（v0.2 新增，实验链路强制）
text
Chapter Contract → ScenePlan（3~7 Scene）→ Beat（每 Scene 3~7 个）→ Writer
Schema 与自校验规则见 04 附录 B（SP1~SP7）。
Writer 失败以章为最小重写单位（06 §4.1，v0.12 裁定 2A 改判——原 scene 级为虚阶梯）。
6. Failure Classification
text
实验结束后，每个 failure 必须分类：

| 问题                      | 结论                    |
|--------------------------|------------------------|
| Proposal 抽取错误/漏抽/置信度不足 | Extraction 问题（06 §4.0） |
| Writer 违反知识约束        | Writer / Validator 问题 |
| Fact 无法归一化            | Fact Ontology 问题      |
| Contract 无法满足          | Contract / Arc 问题     |
| State Commit 正确但剧情不好 | 不属于 Phase 0          |
| LLM 偶尔写出奇怪句子        | 不属于 Phase 0          |
| Event 无法 replay          | 架构阻断问题            |

勘误（v0.12 冻结会追认，裁定 3）：上表无 extraction 独立桶位，H8.1/H8.2 的置信度失败
**只记 by_rule 明细，不进分类桶聚合**——落桶会污染 G4/E6 类读数（WP-E 前实测教训）。
7. Architecture Freeze Gate
Day 23-25 的 Review 禁止因为单个小说样本失败就随意改架构。

必须满足以下条件之一才能改架构：

text
G1. 同类 failure 出现 ≥ 3 次
G2. failure 属于"架构阻断问题"（如 Replay 不一致）
G3. failure 导致 ≥ 2 章无法 Commit
G4. failure 导致 State 不一致
否则：记录到 backlog，进入 Phase 1 再处理。

8. Phase 0 退出条件（v0.2 改为收敛制）
text
满足以下全部条件，才能进入 Phase 1：

E1'. 10 章全部生成（不要求全部 Commit）
E2'. 首轮 Commit 成功率 ≥ 70%
E3'. 经过 ≤ 3 轮 Revision 后，Commit 成功率 ≥ 90%
E4'. Hard violations 按 rule_id 分布明确，无单一规则占比 > 40%
E5'. Replay 一致性 ≥ 90%（增量 Replay 校验通过率）
E6'. 无架构阻断问题（Replay 不一致 / State 不一致 / Event 无法表达）
不满足 → 继续 Phase 0，修问题。

9. Phase 1 预告（不在本协议范围）
text
Phase 1：证明"好看"
  - Critic / Revision Loop
  - Style Engine
  - Pacing Model
  - Reader Model（首次）
  - Emotion Model
10. 不变量
text
I1. 实验期间不得修改协议
I2. 实验期间不得修改 HARD 规则
I3. 所有 failure 必须记录
I4. 所有 Commit 必须落 trace
I5. Replay 一致性必须被验证
I6. Architecture Freeze Gate 必须被尊重