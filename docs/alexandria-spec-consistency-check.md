# Alexandria Spec 引用一致性检查报告

> 检查日期：2026-10-08
> 检查对象：`alexandria-spec-v0.1/` 全部 12 份文件
> 触发原因：v0.2（新增 10 号协议 + CHANGELOG 所列修改）写代码前引用一致性检查
> 检查方法：逐条对照 `10_world_state_protocol.md` 尾部内嵌的 CHANGELOG（v0.1→v0.2）与 16 项冻结检查清单，grep 验证目标文件实际内容

## 状态：已全部处置完毕（2026-10-08 落盘）

本报告 §1（机械落盘 13 项）与 §2（12 项决策矛盾）已全部修复并验证：

- §1 各项：已逐条落入对应协议文件；核查中曾发现 `01_event_protocol.md` 首次重写未生效，已二次重写并 grep 验证（6 类 26 型、`evt_\d{8}`、CHANGES.field 统一枚举、E3'/R1' 放宽均在位）；`06` 的 `confidence: float` 残留已改定点 int。
- §2 决策：2.1→09 §2.5 epoch_0 重冻结；2.2→H8.3 只产 SOFT+人工（05 §4）；2.3→隔离制（07 §4.3 R2）；2.4→07 §5.2 删除复制、05 为唯一来源；2.5→00 同步修订；2.6→04 field 枚举扩至 10 值；2.7→04 附录 B 实写（Beat/Scene/ScenePlan + SP1~SP7）；2.8→新增 FACT_CONTRADICTED（01 §3.1 / 03 §5.4）；2.9→10 §5.1 改名 W-S1~W-S6；2.10→全部示例 ID 更新；2.11→CHANGELOG 拆出为独立文件、目录改名 `alexandria-spec-v0.2/`；2.12→各文件头部已加 10 号引用。
- 完整落盘记录与偏离裁决见 `alexandria-spec-v0.2/CHANGELOG.md` §B。

以下为原报告内容，保留作历史存档。


## 0. 总结论

**当前协议目录 = 纯 v0.1 文本 + 新增 10 号文件。**
CHANGELOG 声称"修订 6 份协议、新增 1 份、调整 3 类规范"，但逐项核查后发现：
**16 项冻结检查清单，0 项已在协议文件中落盘**（唯 10 号自身存在）。
所有 v0.2 修改目前只存在于 10 号文件尾部内嵌的 CHANGELOG 描述里。

后果：
- 若按"v0.2 协议"写代码 → 实际参照物不存在，代码与任何落盘文件都对不上；
- 若按当前落盘的 v0.1 文件写代码 → 10 号协议要求的 `ITEM_ACQUIRED` / `READER_LEARNS` 等事件会被 01 的 E6 规则（不在 Taxonomy 一律拒收）直接拒收，H1/H4 校验在 01/05 冻结版下依然无对应事件类型可消费。

这不是"交叉引用断裂"，而是**变更未执行**。必须先补落盘，再谈引用检查。

## 1. CHANGELOG 声明 vs 实际文件状态（逐项核查）

| CHANGELOG 项 | 目标位置 | 实际状态 | 证据 |
|---|---|---|---|
| 2c：01 新增 ReaderEvents（READER_LEARNS/DECEIVED/HINTED） | 01 §3 | ❌ 未落盘 | `01_event_protocol.md:71-83` EventType Literal 仍为 20 类，无 READER_* |
| 修改1：01 新增 ITEM_ACQUIRED / ITEM_CONSUMED / RELATIONSHIP_CHANGED | 01 §3 | ❌ 未落盘 | 同上；grep 全文件无命中 |
| 修改1：01 CHANGES.field 枚举改为 status/realm/location/faction/attributes/abilities | 01 §4.1 | ❌ 未落盘 | `01_event_protocol.md:147-149` 仍为 `location \| realm \| inventory \| relationship` |
| 7：01 event_id 正则升 8 位 | 01 §4 | ❌ 未落盘 | `01_event_protocol.md:87` 仍 `^evt_\d{6}_\d{3}$` |
| 9：01 E3 孤岛规则 / §5.2 R1 环检测降为 OBSERVATION | 01 §2/§5.2 | ❌ 未落盘 | `01_event_protocol.md:16` 仍"孤岛 Event 非法"；`:158` 仍"必须是 DAG（禁止环）" |
| 5b/7：02 Fact Relation 静态化声明 + fact_id 升 6 位 | 02 §3/§5 | ❌ 未落盘 | `02_fact_protocol.md:26` 仍 `^fact_\d{4}$`；§5 无 Phase 0 静态化条款 |
| 2d/5a：03 §3 改为引用 02 + Reader Reducer | 03 §3/§6/§8 | ❌ 未落盘 | `03_knowledge_protocol.md:24` 仍完整重定义 `class Fact`；§8 Reducer 无 apply_reader* |
| 2e/8：04 reader_signals 字段 + D2/R3~R6 降 SOFT | 04 §3.2/§4.1/§4.3 | ❌ 未落盘 | `04_contract_protocol.md:148` D2 仍"必须等于"；`:58-61` R3~R6 仍 HARD；Schema 无 reader_signals |
| 2a/2b/4a：05 H2.3/H5.5 可判定信号 + §5.5 序列化规范 | 05 §4/新增 | ❌ 未落盘 | `05_validation_protocol.md:48` H2.3 原文未改；`:67` H5.5 原文未改；无 §5.5 |
| 3a/3b：06 RootCause 增 extraction 层 + §4.0 回退路径 | 06 §3/§4 | ❌ 未落盘 | `06_revision_protocol.md:23-31` Literal 无 "extraction"；grep 全文件 0 命中 |
| 3c/3d/4b：07 抽取置信度联动 + H8 + Commit 后 Replay 校验 | 07 §4/§5.2/§7 | ❌ 未落盘 | `07_commit_protocol.md:69` 的 extraction_confidence 是 v0.1 原有字段；§5.2 无 H8；§7 无 replay 校验 |
| 6a/6b/6c：08 排期 3.5 周 + 退出条件 E1'~E6' + Scene/Beat 章节 | 08 §5/§8/新增 | ❌ 未落盘 | `08_experiment_protocol.md:86` 仍 "Day 5-10 Implementation"；`:129-136` 仍旧 E1~E6；无 Scene/Beat 章 |
| 10b：README 文档层级 + 10 号入清单 | README | ❌ 未落盘 | `README.md:25-36` 协议清单仍 10 项（无 10 号）；`:3` 冻结日期仍 2026-10-06 |

## 2. 即使照抄落盘后、仍会存在的引用矛盾（需决策，非机械修复）

### 2.1 epoch_0 与 09 号升级触发条件直接冲突 🔴
01 §7.2 / 09 §4 T1/T2 明确：**Event type 增删改、payload 字段增删改 → 必须触发 epoch 升级**。
v0.2 新增 6 个 Event 类型、改 CHANGES.field 枚举、04 加 reader_signals——按 09 应升 epoch_1，
但 10 号文件头仍写 `epoch：epoch_0`。
两种处理任选其一，必须在 README/09 里显式写死：
- (a) 声明"epoch_0 的冻结定义 = v0.2 最终落盘内容，v0.2 发布前无任何 epoch_0 数据"（实质合规，但要写明）；
- (b) 老实升 epoch_1。

### 2.2 H8.3 违反 05 §9 I1 🔴
CHANGELOG 3d 新增 "H8.3 Proposal 与 Draft 语义不一致（**由 LLM-as-validator 判定**）"，
且 H8 挂在 Stage 1 HARD 集下。05 §9 I1 白纸黑字："HARD 规则不得依赖 LLM 判断"。
落盘时要么把 H8.3 降 SOFT/转人工，要么修订 05 I1——二者必改其一，不能都原样落盘。

### 2.3 "HARD 检查动态降级 SOFT"与冻结纪律冲突 🟡
CHANGELOG 3c："min(extraction_confidence) < 0.7 → 该 Proposal 的 HARD 检查降级 SOFT"。
HARD 规则按 Proposal 置信度逐条动态失效，实质是在 epoch 内修改 HARD 规则效果（05 V5 / 09 §7 不允许）。
建议改为：低置信 Proposal 不产生 HARD 违规，但产生独立的 `EXTRACTION_UNVERIFIED` 记录 + 阻断该 Proposal 提交（不进 SOFT 降级语义）。

### 2.4 07 §5.2 复制了整套 05 HARD 规则清单 🔴（引用断裂重灾区）
`07_commit_protocol.md:104-138` 全文重述 H1~H7，CHANGELOG 修改 2a/2b 只改 05 不改 07。
落盘后 05（改过的 H2.3/H5.5）与 07（旧文案）立即不一致。
建议：07 §5.2 整段删除，改为"规则集见 05 §4"（单一来源化，与 5a 对 03 的处理同理）。

### 2.5 00 号文档会被 v0.2 悄悄作废 🟡
CHANGELOG 声明 "00_principles.md ← 不变"，但：
- 00 §4 HARD 分类清单（Canon/Knowledge/Timeline/Resource/Contract/Event）不含新增的 Extraction（H8）；
- 00 术语表无 Entity / WorldState / Inventory / ReaderEvent；
- 00 §3 LLM 边界矩阵未覆盖 Writer 现在要写 `<!-- reader_learns -->` / `<!-- hook -->` 标注这一新职责。
00 是上位文档，必须同步修订。

### 2.6 04 CharacterChange.field 与 10 §4.3 映射表仍不齐 🟡
10 §4.3 映射含 `status / attributes / abilities / faction`，
但 04 `CharacterChange.field` 注释枚举仍是 `knowledge|belief|location|realm|relationship|inventory`（04:76）。
落盘时需同步补 04 的 field 枚举，否则 must_change 写 `field: status` 无合法定义。

### 2.7 08 引用的 "04 附录 B（Scene/Beat Schema，v0.2 新增）" 不存在 🔴
CHANGELOG 6c 写明 "Scene Schema 与 Beat Schema 见 04 附录 B"，
但 CHANGELOG 修改清单里没有任何一项实际给 04 写附录 B。这是纯粹的死引用——而且 Scene/Beat 是中间设计过程点名的一期关键层。需要真的补写这两份 Schema，否则 Day 14-16 "Plot → Scene → Beat" 无规格可依。

### 2.8 03 R6 引用的 CONTRADICTS 在 Event Taxonomy 中仍不存在 🔴（v0.1 遗留，未进清单）
`03_knowledge_protocol.md:88` "任何 Event 不得降低 state（除显式 CONTRADICTS）"——
CONTRADICTS 只是 FactRelation 类型（02 §5），01 Taxonomy 无此事件。
v0.2 修改没覆盖这条。降级 Knowledge/Belief 目前仍无合法路径。需加 `FACT_CONTRADICTED` 事件或修订 R6。

### 2.9 规则编号命名空间冲突 🟢
10 §5.1 空间推理规则用 S1~S6，与 05 §5 SOFT 规则 S1~S5 撞名；
后续 trace/metrics 按 rule_id 引用时会产生歧义。建议 10 §5.1 改为 W-S1~W-S6 或 SP1~SP6。

### 2.10 ID 位数升位后，全部示例文本仍是旧格式 🟡
fact_\d{4}→\d{6}、evt_\d{6}→\d{8} 落盘后，01/02/03/04/10 的所有 JSON 示例（fact_0001、evt_000047_003 等）都匹配不上新正则。示例也是规格的一部分，需全量替换。

### 2.11 文档结构问题 🟡
- `10_world_state_protocol.md`（903 行）末尾 440 行起内嵌了整份 CHANGELOG 和 16 项冻结清单——协议文件混入了变更日志，两者应拆为 `10_world_state_protocol.md` + `CHANGELOG.md`；
- CHANGELOG 自称"修订 6 份协议"，实际清单列了 01/02/03/04/05/06/07/08 + README = 9 份；
- 目录名 `alexandria-spec-v0.1` 与内容目标版本 v0.2、CHANGELOG 末段"alexandria-spec-v0.2/" 三者不一致，改名要趁现在（还没代码引用路径）。

### 2.12 10 号协议的自我声明与实际不符 🟢
10 号文件头："下位协议：01 / 02 / 03 / 04 / 05 / 07 **全部引用本协议**"——
当前 6 份文件 grep `10_world` / "World State" 均 0 命中。落盘修改时需在上述文件目的/依据节各加一行显式引用。

## 3. 建议修复顺序

1. **机械落盘**：按 §1 表逐条把 CHANGELOG 修改写入 9 份文件（其中 2.4 项 07 §5.2 建议改引用而非复制；2.10 全量更新示例 ID）。
2. **决策项**（需拍板后一起落）：2.1 epoch 处理、2.2 H8.3 归属、2.3 置信度联动语义、2.8 CONTRADICTS 事件、2.7 Scene/Beat Schema 是否随 v0.2 冻结一起出（**建议必须出**，否则 Day 14-16 无规格）。
3. **卫生项**：拆分 10 号文件、README 更新清单与冻结日期、目录命名定版、00 号同步修订。
4. 落盘完成后复跑本报告 §1/§2 清单作为 v0.2 冻结 Gate，通过再开工写代码。

## 4. 附：核查命令（可复跑）

```bash
cd alexandria-spec-v0.1
grep -c "READER_LEARNS\|ITEM_ACQUIRED\|RELATIONSHIP_CHANGED" 01_event_protocol.md   # 期望落盘后 ≥6
grep -n "evt_\\\\d{8}" 01_event_protocol.md                                          # 期望落盘后命中
grep -n "fact_\\\\d{6}" 02_fact_protocol.md
grep -n "class Fact(BaseModel)" 03_knowledge_protocol.md                             # 期望落盘后 0 命中
grep -n "reader_signals" 04_contract_protocol.md
grep -n "5.5 序列化\|Canonical" 05_validation_protocol.md
grep -n '"extraction"' 06_revision_protocol.md
grep -n "H8\|REPLAY_INCONSISTENT" 07_commit_protocol.md
grep -n "E1'\|3.5 周\|Scene / Beat" 08_experiment_protocol.md
grep -n "10_world" README.md 01_event_protocol.md 05_validation_protocol.md 07_commit_protocol.md
```
