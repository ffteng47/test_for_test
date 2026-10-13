# 夹具 v4.0 设计稿（多局面 · 场级断言 · 章长规格 · E25 机制修）

状态：**设计稿，待 tff 定标后实施**。本稿只依据两类证据：仓库内已冻结的判据文本，
和下面 §1 里**每条都带复现命令**的实测基线（六跑 ladder-v2 语料，尺戳
`抽取尺=v3.3｜指引=g2｜夹具=ladder-v2-f1-belief-arc`）。

**§1.0 章长+段数 heredoc**（`.venv/Scripts/python.exe -` 喂入）：

```python
import statistics as st
from pathlib import Path
from plot_engine.reading import chapter_texts, paragraphs
runs = ["ladder2_r1","ladder2_r2","ladder2_r3","v33r1","v33r2","v33r3"]
L = [len(c["text"]) for r in runs for c in chapter_texts(Path("sampling")/r/"dump").values()]
P = [len(paragraphs(t)) for t in
     (c["text"] for r in runs for c in chapter_texts(Path("sampling")/r/"dump").values())]
print(len(L), st.median(L), round(st.mean(L),1), sum(1 for x in L if x>=2000), sum(L),
      min(P), st.median(P), max(P), sum(1 for x in P if x<=4))
```

**重复词汇 heredoc**：同上取 `texts`，`blob="".join(texts)`，逐词 `print(w, blob.count(w), round(blob.count(w)*1000/len(blob),2))`，`w ∈ 印章/张三/伪造/宗门/怀疑`。

**末版状态集合计数**：`sqlite3` 只读开 `sampling/<run>/state/state.db`，
`SELECT envelope FROM states ORDER BY version DESC LIMIT 1` → `StoryState.model_validate(json.loads(...))`
数 `characters/facts/items/locations/factions/relationships`（六跑一致：2/4/0/1/0/0）。

## 1. 实测基线（全部已复验，2026-10-12）

| 量 | 读数 | 复现命令 |
|---|---|---|
| 章长 | 60 章：中位 **973**、均值 985、≥2000 字 **0 章**、总 59,121 字 | §1.0 的 heredoc（一次出章长+段数两行） |
| 段数 | 每章 **5–7 段**（中位 6），≤4 段 **0/60** | 同上 |
| Writer 死规格 | `plot_engine/llm_writer.py:104`：`写 2~4 个自然段…总长不超过 {max_chars} 字`，`max_chars` 默认 1200（:99） | `grep -n 自然段 plot_engine/llm_writer.py` |
| 夹具规模 | `_STEPS` 周期 **10**（10 章跑满一轮、无冗余）、fact **4**、有名人物 **2**、locations 1、items 0、relationships 0、factions 0 | `python -c "import plot_engine.tests.fixtures.experiment_10ch as fx; print(len(fx._STEPS), fx.LADDER_VERSION)"` + 末版 `states.envelope` 集合计数（见 §1 命令同款 heredoc） |
| 重复词汇 | 印章 14.16/千字、张三 10.10/千字、伪造 3.87、宗门 8.15（六跑 59,121 字） | `blob="".join(texts); blob.count(w)` heredoc（E23 九臂口径已原样复现 1096/916/374） |
| 事实重锚 | ladder2_r1：**20 重锚 / 37 有效断言**，其中夹具命令 5、引擎自发 15（knowledge 6 / reader 5 / belief 4）；advancing 仅 4 | `python -m plot_engine.reanchor sampling/ladder2_r1` |
| 彩票税 | 每跑 **≤1 章**可翻（ladder2 三跑全翻 ch06、v33 全翻 ch08），与全库 +10.4pp 同量级 | `python -m plot_engine.readout sampling/ladder2_r1 … sampling/v33r3 sampling/bo_ctrl` |

## 2. 基线读出的四个病

1. **规模饥饿**：4 fact / 2 人物 / 10 步周期 ⇒ 10 章正好把 ladder 跑满一遍，第 5 章起模型除了换着说法重述同一枚印章无事可做。重复词汇率和 E25 重锚（15 章次自发重锚）至少有一部分是**夹具喂不出新料**的病，不能记在引擎头上。
2. **章长被 Writer 死规格钉死**：规格写 2–4 段 / ≤1200 字，实测 5–7 段 / 中位 973 字——两头都不达标，且离判据关心的 2000–3000 字区间差一个倍数。段数规格是名义规格（无人判定），留着只会继续被违反。
3. **类型彩票**：夹具的 required_event 押单个事件类型，抽取器在同 field 等价类里换一种写法就判死。税不大（≤1 章/跑）但**章号固定**——ch06/ch08 三臂全挂同一章，说明这是夹具的系统性押注错误，不是模型方差。**多类型钉死是其放大版**：ch09 钉 `required_events=['BELIEVES','INFERS','OBSERVES']`，落空任一即 `ARC_CONFLICT`（契约层无权放宽 Arc 强制项），重读后 ch09 全库首轮仅 **3/27**（见 rebaseline §6）——一章被三种单类型同时卡，通过率是三张彩票的乘积。
4. **reader_signals 机械重锚**（`derive.py:182-188`）：gate 一旦成熟，其 reader 信号**永久出现在每章契约里**，不检查读者是否已到达目标态 ⇒ 引擎被契约逼着反复重锚同一事实。这是 E25 里 reader 类 5 章次的来源，归属 derive，不归属模型。

## 3. v4.0 改动清单（按可独立提交排序）

### 3.1 夹具规模（`plot_engine/tests/fixtures/experiment_10ch.py`，`LADDER_VERSION → "ladder-v4-multi-scene"`）

**已落地（v4.1 批次，2026-10-13）**：4 有名人物（张三/李四/王五/赵六，李四王五赵六各有
belief/知识线并进自己角色的 ledger）、12 fact、3 locations、2 items、2 relationships、1 faction；
10 章 (actor, field, fact) 三元组全库唯一不回环；9/10 章 must_change ≥2（第 8 章「本章不推进」保留）。
`traitor_arc.json` 被 8 个 golden 测试共用、一字未动，扩容在 `make_config` 程序化追加。
世界表规模、三元组唯一、拐点钉形已全部静态钉死在 `test_experiment_e2e`。

- **≥4 有名人物**（char_000001 之外至少 3 个有名字、有 belief 线的角色），**≥12 fact**，
  3 locations、≥2 items、≥2 relationships、≥1 faction——多局面 = 每章 2–3 条并行线在不同人物对上展开。
  定标（tff 2026-10-11）：每章**有效出场人物 ≥1**，主要互动场景通常 **2–4 人**，不设全章统一的两人硬门槛。
  「有效出场」取可机检定义：**本章内有台词、行动、或改变了至少一条事件状态**；仅被提及名字不算——
  写进夹具规格，H 系列按此判定。双池门槛只进 v4.1，§3.2 批次不许顺手加人物。
- `_STEPS` 周期 **≥50 或在 10 章内不回环**：10 章实验里每章的 (人物对, fact, field) 组合唯一。
- 每章 must_change 只声明本章真实发生的跃迁（沿用 v2 的规则），但因为规模上来了，
  **允许多数章 must_change ≥2 条**，逼近 08 对真实契约的假设。

### 3.2 场级断言（消类型彩票，**不动 H5.1 判据**）

**收尾已落地（ladder-v4，同一批）**：ch08 式「纯再锚钉」清零（该章 mandatory=[]，再锚事件照进
事件流）；其余每一钉都是本章的叙事模态（亲眼验印 OBSERVES / 读簿 READS / 下山来报 IS_TOLD /
串线 INFERS / 内心确认 BELIEVES）。derive 04 §4.2 守卫仍要求每 field 有族内钉——该守卫读的是
required_events，所以「兑现事件完全不钉」在现引擎下不可行，v4 的形态是**每 field 至多一枚模态钉**
（v3 是每事件一枚）。`fixture_audit.unreachable_by_construction` 随之改读步的事件流（钉子集化后
required_events 不再是可达性的全集）；缺陷注入 `no_obs` 泛化为 `no_nail`（drop 本章强制集类型）。

- 规则：required_event 只在**叙事模态本身是剧情**时押单类型（例：「他读到密信」这一拍非 READS 不可）；
  纯粹为兑现 must_change 而生的事件**不再写进 required_events**——H5.3 已按 `FIELD_EVENT_TYPES`
  做 field 级实现检查，类型由抽取器自由 roll。
- **首笔落地（ladder-v3，2026-10-11）**：夹具 `_STEPS` 的步可带 `"mandatory"` 覆盖，`build_arc`
  的 intent.required_events 与 turning-point `required_event_types` 只取强制集，`events` 整条照旧进
  离线抽取道与正文。本批**只改 ch09 一处**（三元组 → 单钉 BELIEVES，即本章 must_change belief→F3
  的模态；derive 04 §4.2 守卫要求 belief 族类型留在强制集内），LADDER_VERSION 一次 bump 一个因。
- 验收（tff 裁定①：静态属性静态验，不拿 3 次采样宣判）：
  - 「ch09 不再被三类型同钉」是**契约静态属性**——直接读 required_events 确定性验证，
    已钉死在 `test_experiment_e2e.py::test_ten_chapters_do_not_share_one_constraint_set`
    （ch09 == {BELIEVES}、tp9 == ["BELIEVES"]、强制集 ⊆ 事件流、每条 must_change 的实现类型仍在强制集内）；
  - 三跑**只报观测值**（H5.1等价税列），「税是否消除」的结论挂在重基线**全量读数**上判——
    旧税率 ~42% 章次下三跑全 0 的先验概率仍有约 20%，0/3 不构成宣判；
  - 若仍有税，税章不得固定在同一章号（固定 ⇒ 夹具病，散开 ⇒ 模型病，进观察列）。

### 3.3 Writer 规格（`llm_writer.py:99-105`）

- `max_chars` 实验默认改 **2000–3000** 区间（prompt 写「总长 2000~3000 字」），
  段数死规格 **删除**（不给无人判定的名义规格）；改成 `章长规格=w4-2000-3000` 打进尺戳首行，
  与 `抽取尺/指引/夹具` 并列——换规格 = 换尺，旧语料不得与新语料同表比较。
- 风险注记：章长 ×3 会把单次写作的截断/漂移暴露出来（E21 截断只在 14b 长输出上发生过），
  三采样前先用离线 dry-run 验证 `接线：正常（无空正文、无截断）` 断言在长章下仍绿。

### 3.4 derive：reader_signals 按「未到达」过滤 + 已渲染事实台账（E25 机制修）

- `derive.py:182-188`：signal 只在**该 fact 的 reader 条目尚未到达（或强于）target** 时才产出——
  已到达的信号不再进契约。
- Writer prompt 注入**已渲染事实清单**（actor, fact, 当前 state/strength，来自末版 StoryState）：
  「以下事实已建立，勿重复锚定」。
- 判定口径：`python -m plot_engine.reanchor` 的**无命令重锚计数进报告观察列，不设门槛**（裁定序）；
  v4 三采样相对 v2 基线（r1：15 章次无命令重锚）应显著下降，降不动 ⇒ 机制修没生效，回查。

### 3.5 取证 carry-over（冻结前置）

- 坏料 `item` 明细进 dump（§3 探针的取证缺口：junk reason 只在内存里，无法归因）；
- ~~ch05/ch09 全库率重读~~ **已清（2026-10-12）**：ch05 首轮 11/27、ch09 首轮 3/27，机制已从 E14 的信念探针钉错**换相**为 `required_events=['BELIEVES','INFERS','OBSERVES']` 三元组类型钉死 ⇒ §3.2 的验收收紧为「v4 的 ch09 不得同时钉三个类型」。读数与命令见 `phase1-rebaseline-v33.md` §6。

## 4. 不做清单（本稿明确排除）

- H5.1 认等价类——裁定一已否，税列只进报告；
- H8.1/H8.2 的九桶归类（08 §4 待原文裁定，backlog）；
- `rewrite_scene`≡`rewrite_chapter` 名义阶梯（backlog）；
- 配对打分表的「愿意付费读」维度（E23 裁定：单局面语料下无效，v4 多局面语料出来前不重开）。

## 5. 实施序与门禁（tff 2026-10-11 裁定：一次一个因，先钉死修复再按读数扩规格）

1. **§3.2 单批**（ladder-v3）：只动 ch09 契约一处 + LADDER_VERSION bump → 单测静态钉死（见 §3.2 验收）；
   人物池、章长、尺面改动一律不混入本批。
2. **freeze commit → 同模型三次采样**：E21 纪律（各自 `--state-dir`、各自 log、并行后接线断言），
   只报 E1–E6/§6/§7/税列观测值 → 一致性铁律裁定（>10pp 差异 ⇒ 不可判、报方差）。
3. **依据读数决定 v4.1**：3.1（人物/Fact 双池）、3.3（Writer 章长 2000–3000 + 尺戳）、
   3.4b（已渲染事实台账进 prompt）、3.5（junk `item` 明细进 dump）——若 §3.2 单独已把关键读数
   拉出病区间，扩规格批次可缓行；「税是否消除」在 v4.1 重基线全量读数上判。

每步一次提交；2000–3000 字与 ≥4 人物两个数已定标（§3.1/§3.3），其余按已冻结判据执行。
