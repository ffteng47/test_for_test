# 07 Commit 协议

> 版本：v0.2
> 冻结日期：2026-10-08
> epoch：epoch_0（定义见 09 §2.5）
> 上位协议：00_principles.md
> 引用：Event 见 01；Ledger 见 03；Contract 与 Scene/Beat 见 04；
> 规则清单与序列化规范见 05；Revision 见 06；实体与 StoryState 见 10

## 1. 目的与范围

定义 Alexandria 中所有状态变更的唯一合法写入路径：Commit。

Commit 是一个事务：要么全部成功，要么全部回滚。
Commit 之前，一切皆为 Proposal（可变、可丢弃）。
Commit 之后，一切皆为 State（不可变、可重放）。

本协议不含：Event 如何定义（01）、Contract 如何派生（04）、Validator 规则细节（05）。

## 2. 核心原则

| # | 原则 |
|---|------|
| P1 | 先日志后状态（WAL）：Event Log 先写，State 后更新 |
| P2 | 乐观锁（CAS）：写入必须带 expected_version，不匹配则拒绝 |
| P3 | 两阶段：Validate 通过后才允许 Reduce + Persist |
| P4 | 可回滚：任何阶段失败，State 必须回退到 Commit 前 |
| P5 | 幂等：同一 Commit 重复执行不得产生副作用 |
| P6 | 可重放：Commit 后的 Event Log 必须能重建同一 State（05 §5.5 序列化规范） |

## 3. 阶段划分

```text
┌─────────────────────────────────────────────────┐
│  Stage 0: Proposal                              │
│    输入：Draft + Chapter Contract + ScenePlan + State │
│    输出：Event Proposal List                    │
│    状态：可变、可丢弃                            │
├─────────────────────────────────────────────────┤
│  Stage 1: Validate                              │
│    输入：Proposal List + Contract + State       │
│    输出：PASS / FAIL + Findings                 │
│    状态：只读                                    │
├─────────────────────────────────────────────────┤
│  Stage 2: Reduce                                │
│    输入：Proposal List + State                  │
│    输出：New State (in-memory)                  │
│    状态：内存沙盒，不落盘                        │
├─────────────────────────────────────────────────┤
│  Stage 3: Persist (WAL + CAS + Replay 校验)     │
│    输入：New State + expected_version           │
│    输出：Committed State + Snapshot             │
│    状态：持久化                                  │
└─────────────────────────────────────────────────┘
```

## 4. Stage 0：Proposal

### 4.1 输入

```python
class CommitRequest(BaseModel):
    story_id: str
    chapter_no: int
    draft: str                       # 含 §4.4 markup 的整章文本
    contract: ChapterContract
    scene_plan: ScenePlan            # v0.2：04 附录 B
    expected_version: int            # CAS 用
    trace_id: str
```

### 4.2 Proposal 生成

```python
class EventProposal(BaseModel):
    """Stage 0 生成，尚未获得 event_id，尚未 commit"""
    proposed_event_type: str         # ∈ 01 §3 Taxonomy（v0.2 含 READER_* / ITEM_* 等）
    actor: Optional[str]
    target: Optional[str]
    chapter: int
    scene: Optional[str]
    seq: int
    preconditions: List[str] = []
    payload: dict
    confidence: int = Field(1000, ge=0, le=1000)   # 抽取置信度 ×1000（§4.3）
    source_ref: str                  # Draft 中的原文引用或 markup: 定位

    extraction_method: Literal["rule", "llm", "hybrid", "markup"]   # v0.2 增 markup 通道
    extraction_confidence: int = Field(1000, ge=0, le=1000)
```

Proposal 与 Event 的区别（不变）：Proposal 无 event_id、可丢弃、可重生成、
不进 Event Log、不受 CAS 保护。

### 4.3 Proposal 生成策略与抽取置信度联动（v0.2 修订）

四通道，优先级从高到低：

1. **markup 通道**（确定性）：Draft 中的 `<!-- ... -->` 标注（§4.4）直接映射为
   READER_* / hook 相关 Proposal，extraction_confidence = 1000。
2. **规则通道**：结构化信息（CHANGES/ITEM_*/RELATIONSHIP_CHANGED 的字段模板）直接映射。
3. **LLM 通道**：非结构化段落 → LLM 抽取。
4. **交叉验证**：规则与 LLM 对同一段落结果一致 → 1000；不一致 → 500；单通道 → 700。

置信度联动规则（替代 v0.2 草案的"HARD 动态降级"，理由见一致性检查报告 §2.3）：

| # | 规则 |
|---|------|
| R1 | 任何 Proposal 的 extraction_confidence < 500 → 整批 FAIL，归因 05 H8.1，RootCause = extraction（06 §4.0） |
| R2 | 500 ≤ extraction_confidence < 700 → 该 Proposal **隔离**：不进入本批 Commit，落 HARD finding H8.2（EXTRACTION_UNVERIFIED），触发 06 §4.0 重抽取（换 prompt / 换模型 / 补 markup 要求），**不触发 Writer 重写正文、不触发 Contract 重议** |
| R3 | 隔离后若 Contract 的 required_events 无法由剩余 Proposal 满足 → H5.1 违规照常成立，归因路径由 RootCause 分类决定 |
| R4 | markup 通道的标注引用不存在的 fact_id → 视同 H6.2（preconditions/引用缺失），归因 markup/抽取层 |

Phase 0：LLM 抽取为主，markup 通道为 Reader 类与 hook 判定的强制要求（§4.4）。

### 4.4 Draft markup 规范（v0.2 新增）

Writer 产出的 Draft 必须携带以下 HTML 注释标注（不渲染进正文，供规则通道消费）：

```text
章尾（必须，恰好一条，位于最后 3 段之内）：
    <!-- hook: <type> strength=<0-1000 整数> -->
    type ∈ ChapterHook.type（04 §4.1）

读者信号（按需，可多条）：
    <!-- reader_learns: fact_000123 -->
    <!-- reader_hinted: fact_000123 -->
    <!-- reader_deceived: fact_000123 -->
```

| # | 规则 | 等级 |
|---|------|------|
| M1 | 缺失 hook 标注，或 type 与 contract.ending.type 不一致 | HARD（05 H5.5） |
| M2 | reader_* 标注必须有对应 READER_* Proposal（规则通道生成） | HARD（05 H2.3 判定依据） |
| M3 | Ledger 有 READER_* 记录但 Draft 无对应标注 | SOFT |
| M4 | 标注引用的 fact_id 不存在 | HARD（H6 引用检查） |
| M5 | 定点值必须为 0~1000 整数 | HARD（Schema 校验） |

## 5. Stage 1：Validate

### 5.1 三层结果结构

```python
class ValidationResult(BaseModel):
    hard_violations: List[Finding] = []
    soft_warnings: List[Finding] = []
    observations: List[Finding] = []

    def can_commit(self) -> bool:
        return len(self.hard_violations) == 0
```

Finding 结构见 05 §3。

### 5.2 规则集（v0.2：单一来源化）

**HARD / SOFT / OBSERVATION 规则清单的唯一来源为 `05_validation_protocol.md` §4~§6（H1~H8 / S1~S5 / O1~O4）。**

本协议不再复制规则文本（v0.1 的 §5.2~§5.4 为全量复制，是引用断裂源头，已删除）。
Stage 1 执行语义：

- W1~W7（04 §5.2）与 H1~H8 由 Validator 顺序执行；
- 任何 HARD 非空 → FAIL，不进入 Stage 2；
- 结果必须落盘为 Commit 事务的一部分（05 §8）。

### 5.3 Validate 的硬规则

| # | 规则 |
|---|------|
| R1 | HARD violations 非空 → 立即 FAIL，不进入 Stage 2 |
| R2 | Validate 必须幂等：同一输入 → 同一输出（05 V3） |
| R3 | Validate 必须可回放：同一 State + Proposal + Contract → 同一结果 |
| R4 | Validate 不得修改任何 State（只读） |
| R5 | HARD 规则的增删必须走 epoch 升级（01 §7 / 09） |

## 6. Stage 2：Reduce

### 6.1 Reduce 语义

```python
class Reducer:
    def apply(self, event: Event, state: StoryState) -> StoryState:
        """纯函数：输入 State + Event → 输出新 State。
        分派表：03 §8（Ledger 类）+ 10 §16（实体类）。
        StoryState 聚合根定义见 10 §13。"""
```

### 6.2 Reduce 规则

| # | 规则 |
|---|------|
| R1 | Reduce 必须是纯函数：不得读写外部状态、不得有副作用 |
| R2 | Reduce 必须按 (chapter, seq) 拓扑序应用 |
| R3 | Reduce 必须在内存沙盒中执行，不落盘 |
| R4 | Reduce 后必须执行 assert_consistent（01 §6.2 / 10 §15） |
| R5 | assert_consistent 失败 → 回滚整个 Reduce，标记 HARD violation |
| R6 | v0.2：实体类事件（CHANGES/ITEM_*/RELATIONSHIP_CHANGED）更新 10 号协议定义的 StoryState 实体表；状态转换必须走 10 §4.2 合法路径 |
| R7 | v0.2：一切数值运算走定点整数（×1000）路径（05 §5.5） |

### 6.3 Reduce 后的不变量检查

```text
I1. Knowledge/Belief/Reader Ledger 无矛盾（03 §10）
I2. World State 无矛盾（10 §15）
I3. 已 commit 的 Event 因果边无环（Phase 0 环只警告，01 §5.2 R1'）
I4. 所有 Ledger 更新可追溯到 Event
I5. State hash 与前一版本不同（若无变化说明 Reduce 有问题）
```

## 7. Stage 3：Persist

### 7.1 写入顺序

```text
1. 开启事务
2. 写 Event Log（append-only）          ← WAL
3. 读当前 version（SELECT ... FOR UPDATE）
4. 比对 expected_version
     不匹配 → 回滚，返回 CONFLICT
5. 写 New State（Update）
6. 写 Snapshot（若命中快照频率）
7. 提交事务
8. 触发 Replay 校验（§7.5，v0.2 新增）
9. 返回 Committed State
```

### 7.2 CAS 语义

```python
def persist(
    story_id: str,
    new_state: StoryState,
    expected_version: int
) -> CommitResult:
    with transaction():
        current = store.load_latest(story_id)
        if current.version != expected_version:
            rollback()
            return CommitResult(
                status="CONFLICT",
                current_version=current.version,
                message="Another writer committed first",
            )
        event_log.append(new_state.events)
        store.save(StateEnvelope(
            story_id=story_id,
            version=expected_version + 1,
            chapter_no=new_state.chapter_no,
            state=new_state,
            state_hash=canonical_hash(new_state),   # 05 §5.5
        ))
        commit()
        return CommitResult(status="OK", new_version=expected_version + 1)
```

### 7.3 快照策略

| # | 规则 |
|---|------|
| R1 | 每章 Commit 后：写 Event Log（必有） |
| R2 | 每 N 章（默认 N=5）：写全量 Snapshot |
| R3 | Snapshot 必须包含：Story State / version / chapter_no / state_hash / epoch |
| R4 | Snapshot 与 Event Log 必须一致：从最近 Snapshot Replay 到当前章 = 当前 State |

### 7.4 失败处理

| # | 情形 | 处理 |
|---|------|------|
| F1 | WAL 写入失败 | 回滚，State 不变，返回 IO_ERROR |
| F2 | version 不匹配 | 回滚，返回 CONFLICT，触发上层重试 |
| F3 | State 写入失败 | 回滚，Event Log 保留（诊断用） |
| F4 | Snapshot 失败 | 不回滚（Event Log 已成功），告警 |
| F5 | 事务提交失败 | 全回滚，State 不变 |

### 7.5 Commit 后 Replay 校验（v0.2 新增）

| # | 规则 |
|---|------|
| R5 | 每次 Commit 成功后自动触发增量 Replay：从最近 Snapshot 重建本章 State |
| R6 | 若 replay_state_hash ≠ online_state_hash：**回滚本次 Commit**（version 回退、Event Log 标记 orphan 不删除），落 finding REPLAY_INCONSISTENT，停止 pipeline，归因 06 §4.7 State Error |
| R7 | Phase 0 每章必验；全量跨章 Replay 在 epoch 升级/迁移时必验（09） |

## 8. 幂等性

| # | 规则 |
|---|------|
| R1 | 幂等键：(story_id, chapter_no, expected_version, proposal_set_hash)。proposal_set_hash = SHA256(canonical_json(sorted proposals))，防止同键不同内容重放 |
| R2 | 同一幂等键已成功 → 直接返回缓存的 CommitResult，不重复写入 |
| R3 | commit_log 记录：{ story_id, chapter_no, version, state_hash, proposal_set_hash, timestamp } |

## 9. 回滚协议

### 9.1 回滚层级

```text
L1. Stage 1 失败（Validate FAIL）    → 无副作用，丢弃 Proposal
L2. Stage 2 失败（一致性检查失败）    → 内存 State 丢弃，不落盘
L3. Stage 3 失败（Persist 中途失败）  → 事务回滚；Event Log 若已写则保留（诊断），
                                        version 不更新
L4. 已 Commit 章节需要"撤销"（罕见）  → 不修改历史 Event Log；
                                        写"反向 Commit"，或从 Snapshot 回退 version 指针（标记 rollback）
```

### 9.2 跨章回滚

```text
若第 50 章 Commit 后发现第 47 章 Contract 有误：
  - 不修改 47 章的 Event
  - 从 48 章起写新 Contract（version+1，04 §6 I3/I4）
  - 后续章节按新 Contract 执行
  - 47 章历史保留，标记 "superseded_by_arc_revision"
```

## 10. 与 Revision 的接口

### 10.1 Revision 的三种触发

| # | 触发 | 处理 |
|---|------|------|
| T1 | Stage 1 FAIL（HARD violation） | 按 Root Cause 分类（06 §3，含 v0.2 新增 extraction 层） |
| T2 | Stage 3 CONFLICT（CAS 失败） | 重新拉取最新 State，重跑 Stage 0（非 Revision） |
| T3 | 人工介入 | 直接进 Revision |

### 10.2 Revision → Commit 反馈

```text
Revision 完成后：
  - 重跑 Stage 0（生成新 Proposal）
  - 重跑 Stage 1（重新 Validate）
  - 若连续 N 次 Stage 1 FAIL → 判定 Contract/Arc 级问题，触发 §10.3
```

### 10.3 升级到 Contract 级

```text
若 Chapter Contract 本身非法：
  - 拒绝所有 Proposal，返回 CONTRACT_INVALID
  - 触发 04 §5.1 自校验失败流程，由 Plot Engine 重新生成 Contract（version+1）
```

## 11. 可观测性

### 11.1 每次 Commit 必落

```python
class CommitTrace(BaseModel):
    trace_id: str
    story_id: str
    chapter_no: int

    stage_0_ms: int
    stage_1_ms: int
    stage_2_ms: int
    stage_3_ms: int
    replay_check_ms: int             # v0.2：§7.5 校验耗时

    result: Literal["OK", "FAIL", "CONFLICT", "IO_ERROR", "REPLAY_INCONSISTENT"]
    hard_violations: int
    soft_warnings: int
    observations: int
    quarantined_proposals: int       # v0.2：H8.2 隔离数

    version_before: int
    version_after: Optional[int]

    epoch: str
    schema_version: int
    timestamp: str
```

### 11.2 关键指标

```text
- commit_success_rate / commit_conflict_rate
- commit_hard_violation_rate（按 rule_id 分类，含 H8*）
- extraction_quarantine_rate（v0.2）
- replay_check_failure_rate（v0.2）
- commit_latency_p50 / p95 / p99
- snapshot_size_bytes
- event_log_growth_per_chapter
```

## 12. 不变量

```text
I1. 同一 (story_id, chapter_no) 只能被 Commit 一次（幂等键命中除外）
I2. version 单调递增，不允许跳号
I3. Event Log 与 State 严格一致（可 Replay 验证，05 §5.5）
I4. Snapshot 与 Event Log 严格一致
I5. 任何时刻：state_hash(current) = canonical_hash(replay(event_log))
I6. Commit 后，所有 HARD violations 必须为 0
I7. Commit 过程不得修改已提交章节的 Event
I8. 跨 epoch 不允许直接 Commit（必须先迁移，09）
I9. v0.2：被隔离（H8.2）的 Proposal 永不进入 Event Log
```

## 13. 附录：完整时序

```text
Client             Orchestrator       Validator        Reducer         Store
  │                    │                 │               │              │
  │── CommitRequest ──▶│                 │               │              │
  │                    │── Stage 0 ─────▶│               │              │
  │                    │   (Proposal，含  │               │              │
  │                    │    markup/置信度) │               │              │
  │                    │◀── Proposals ───│               │              │
  │                    │── Stage 1 ─────▶│               │              │
  │                    │   (Validate H1~H8)│              │              │
  │                    │◀── PASS ────────│               │              │
  │                    │── Stage 2 ─────────────────────▶│              │
  │                    │   (Reduce 纯函数)               │              │
  │                    │◀── New State ───────────────────│              │
  │                    │── Stage 3 ───────────────────────────────────▶│
  │                    │   (WAL+CAS)                                    │
  │                    │◀── OK + version+1 ─────────────────────────────│
  │                    │── Replay 校验（§7.5）──────────────────────▶│
  │                    │◀── hash match ────────────────────────────────│
  │◀── CommitResult ───│                 │               │              │
```

## 14. 与其他协议的接口

| 对象 | 关系 |
|------|------|
| Event (01) | Stage 2 的 Reducer 消费对象；Event Log 写入内容 |
| Fact (02) | 引用完整性检查的数据源 |
| Knowledge Ledger (03) | Stage 1 的 H2 数据源；Reader Ledger 由 markup→规则通道驱动 |
| Chapter Contract / ScenePlan (04) | Stage 0 输入；H5/W1~W7 数据源；附录 B 为 Scene 重写单位 |
| Validation 规则与序列化规范 (05) | Stage 1 唯一规则来源；canonical hash 规范 |
| Revision (06) | Stage 1 FAIL / Stage 3 CONFLICT 的下游 |
| World State / StoryState (10) | Stage 2 实体更新路径；H1/H4/Replay 的数据基础 |
