# 05 验证协议

> 版本：v0.2（H2.3/H5.5 改为可判定信号；新增 H8 Extraction；新增 §5.5 Canonical 序列化规范；
> 本协议是 HARD/SOFT/OBSERVATION 规则清单的唯一来源，07 §5.2 已改为引用）
> epoch：epoch_0（定义见 09 §2.5）

## 1. 目的

定义 Alexandria 中"什么是合法的一章"的判定规则。
Validator 是 Commit 前的最后一道闸门。

## 2. 核心原则

| # | 原则 |
|---|------|
| V1 | HARD violations 非空 → 拒绝 Commit |
| V2 | SOFT / OBSERVATION 只记录，不阻断 |
| V3 | Validator 必须幂等：同一输入 → 同一输出 |
| V4 | Validator 必须只读：不得修改任何 State |
| V5 | HARD 规则的增删必须走 epoch 升级 |
| V6 | Validator 分层：确定性规则优先，LLM 规则兜底 |

## 3. 三层结构

```python
class ValidationResult(BaseModel):
    hard_violations: List[Finding] = []
    soft_warnings: List[Finding] = []
    observations: List[Finding] = []

    def can_commit(self) -> bool:
        return len(self.hard_violations) == 0

class Finding(BaseModel):
    rule_id: str
    severity: Literal["hard", "soft", "observation"]
    message: str
    location: Optional[str]
    evidence: Optional[str]
    suggestion: Optional[str]
4. HARD 规则集（Phase 0）
H1 Canon
text
H1.1 角色状态矛盾（死亡角色出场）
H1.2 物品状态矛盾（未持有物品被使用）
H1.3 地点矛盾（角色在 A 地，事件发生在 B 地）
H1.4 境界矛盾（低境界使用高境界能力）
H2 Knowledge
text
H2.1 角色使用 knowledge_forbidden 中的 fact
H2.2 角色缺失 contract.must_change 中要求的知识
H2.3 Reader 认知一致性（v0.2 修订为可判定信号）
      判定依据：Draft 中 Writer 显式标注的 <!-- reader_learns/hinted/deceived: fact_id -->
      （07 §4.4 markup 规范）与 Proposal / Reader Ledger 比对：
      - Draft 有标注但无对应 READER_* Proposal → HARD 违规（07 §4.4 M2）
      - Ledger 有 READER_* 记录但 Draft 无标注 → SOFT 警告（M3）
      本规则由规则通道确定性判定，不依赖 LLM
H2.4 角色使用从未学过的技能（数据源 10 §16）
H3 Timeline
text
H3.1 事件顺序与 seq 矛盾
H3.2 引用了未来章节的 event_id
H3.3 时间倒流
H3.4 同一角色同时出现在两个地点
H4 Resource
text
H4.1 消耗不存在的资源
H4.2 资源数量为负
H4.3 未解锁区域进入
H5 Contract
text
H5.1 required_event 未出现
H5.2 forbidden_event 出现
H5.3 must_change 未实现
      knowledge 字段判据（v3.9 码批/材料三 1B 对齐）：本章存在
      type+actor+fact 三项吻合的实现事件，且角色在该 fact 上的终态
      达到 expected_value 档位——与 H2.2 同谓词，超限事件（如 IS_TOLD
      顶 known）不再判实现。rank 序与事件档位上限表单源 04 D10。
      belief 字段维持纯实现事件判据（belief 无有序 rank 阶）。
H5.4 must_not_change 被违反
H5.5 ending.type 不匹配（v0.2 修订为可判定信号）
      判定依据：Draft 末尾最后 3 段内必须含
      <!-- hook: {type} strength={0-1000 整数} --> 标注（07 §4.4），
      type 必须等于 contract.ending.type；缺失标注或不匹配 → HARD
H5.6 knowledge_allowed 未建立
H5.7 knowledge_forbidden 被建立
H6 Event
text
H6.1 event_type 不在 Taxonomy 中
H6.2 preconditions 指向不存在的事件
H6.3 Event 图存在环
H6.4 event_id 重复
H6.5 preconditions 指向未来事件
H7 Contract 自校验
text
H7.1 Schema 不完整
H7.2 chapter_no 与 arc_id 不匹配
H7.3 tension_target 与 arc.tension_curve 不一致（v0.2 降档：SOFT 比对，偏差 > 300 落 finding，不阻断）
H7.4 knowledge_forbidden 与 knowledge_allowed 有交集
H7.5 required_events 与 forbidden_events 同类型冲突
H7.6 must_change 与 must_not_change 同字段冲突
H7.7 ending.type 与 story_goal_type 不兼容
H7.8 derived_from 引用不存在
H8 Extraction（v0.2 新增，联动语义见 07 §4.3）
text
H8.1 任一 Proposal extraction_confidence < 500 → HARD，整批 FAIL，归因 extraction（06 §4.0）
H8.2 500 ≤ extraction_confidence < 700 → 该 Proposal 隔离（不入本批 Commit），
     落 HARD finding EXTRACTION_UNVERIFIED，触发重抽取；不触发 Writer 重写、不触发 Contract 重议
H8.2x 双通道（规则 vs LLM）同段结果冲突 → confidence = 500，由 H8.1/H8.2 接住
H8.3 Proposal 与 Draft 疑似语义不一致：LLM-as-validator 只产 SOFT finding 并转人工复核，
     不产 HARD（维护 §9 I1）
H9 伏笔生命周期（epoch_1 新增，WP-A 设计稿 §4；台账语义 03 §6.5）
text
H9.1 章提交时存在 chapter_no > due_by_chapter 且未回收的伏笔（lifecycle ∉ {paid, expired}）
     → HARD，归因 arc（弧线债，06 §4）
H9.2 FORESHADOWING_PAID 引用不存在的 foreshadow_id，或对已 paid/expired 条目重复回收
     → HARD，归因 extraction（回收料本身错）
H9.3 伏笔 planted 后连续 N=5 章无任何 hint 联动（HINTS/READER_HINTED）→ SOFT，归因 writer
     （N 建议入 RevisionPolicy 可调，未落地前为模块常量）
H9.4 伏笔回收距埋点 < 3 章（伏笔过浅，读者无期待感）→ OBSERVATION
5. SOFT 规则集（Phase 0，只记录）
text
S1 Pacing：Scene 张力与 contract.tension_target 偏差 > 300（定点 ×1000）
S2 Repetition：连续 3 段句式结构相似
S3 Style：偏离 StyleProfile 显著
S4 Dialogue：对话过于解释性
S5 Sensory：连续 4 段使用同一感官描写
6. OBSERVATION（Phase 0，只落盘）
text
O1 Reader Beat 命中情况
O2 Emotion 曲线
O3 Literary Quality 评分
O4 Suspense 曲线
5.5 Canonical 序列化规范（v0.2 新增，Replay/Hash 一致性的唯一依据）

1. JSON Canonical
text
- key 按字典序升序
- 无空白字符
- 数字用定点表示，禁止科学计数法
- Unicode 用 UTF-8，不转义 ASCII 范围内字符
- 浮点一律以定点整数字符串出现在 JSON 中（见 2）

2. 浮点定点化
text
所有浮点语义字段（strength / confidence / tension / trust / plot_progress /
distance / 关系 strength&trust）：
- 存储为整数：原值 × 1000，取整（0~1000；distance 等业务量为无上限整数 ×1000）
- 内部计算用 Decimal 或整数，禁止 Python float 参与 Replay 关键路径
- 公式示例：
    strength = trust_level × message_strength
    → strength_fixed = (trust_fixed × message_fixed) ÷ 1000   （整数除法，向下取整）

3. Hash 规范
text
- state_hash = SHA256(canonical_json(state))
- 跨机器、跨语言必须一致：字段顺序由 key 升序保证，数值由定点化保证
- 定点值转显示字符串走统一函数：fixed_to_str(v) = f"{v/1000:.3f}"

4. Replay 一致性验证
text
- 每章 Commit 后必须自动跑一次增量 Replay（07 §7.5）
- Replay 结果 state_hash 必须等于在线 state_hash
- 不一致 → 回滚 Commit，落 finding REPLAY_INCONSISTENT，停止 pipeline（06 §4.7）
7. Validator 分层实现
Level 1：确定性规则（硬编码）
text
- 零容错
- 无需 LLM
- 覆盖 H1 / H3 / H4 / H6 / H7 / H8.1 / H8.2（置信度为确定性数值检查）
Level 2：结构化检查（基于 Ledger / Contract）
text
- 零容错
- 无需 LLM
- 覆盖 H2 / H5 / H9（H9 为 epoch_1 伏笔族，台账只读判定）
Level 3：LLM-as-validator
text
- 在 Level 1/2 判定完成后运行（不要求 L1/L2 通过；闸序修订 2026-10-17，tff 拍板，见 CHANGELOG）
- 必须返回结构化 evidence（引原文段落）+ confidence
- confidence 低于阈值 → 不裁定，转人工
- 只覆盖 SOFT 和 OBSERVATION（含 H8.3 转人工复核建议，不产 HARD，见 §9 I1）
8. 幂等与 Replay
text
R1. Validator 必须幂等
R2. 同一 State + Proposal + Contract → 同一 ValidationResult
R3. ValidationResult 必须可序列化，作为 Commit 的一部分落盘
R4. 重新跑 Validator（同一输入）结果必须一致
9. 不变量
text
I1. HARD 规则不得依赖 LLM 判断
I2. SOFT / OBSERVATION 不得阻断 Commit
I3. Validator 不得修改 State
I4. Validator 的输出必须可序列化
I5. HARD 规则的增删必须走 epoch 升级
I6. 任何 Validator 失败必须记录 finding，不得静默丢弃
10. 接口
python
class Validator:
    def validate(
        self,
        draft: str,
        proposals: List[EventProposal],
        contract: ChapterContract,
        state: StoryState,
    ) -> ValidationResult:
        ...

    def validate_contract(
        self,
        contract: ChapterContract,
        arc: ArcContract,
        state: StoryState,
    ) -> ValidationResult:
        ...