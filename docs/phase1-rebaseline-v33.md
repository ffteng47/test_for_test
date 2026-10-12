# v3.3 重基线 ×3（qwen2.5:14b @11500）——读数、一致性裁定与一个未归因的机制

冻结面：`1baea7d`（`抽取尺=v3.3-belief-type-criteria｜指引=g2-suspects-added｜夹具=ladder-v2-f1-belief-arc`）。
命令：`python -m plot_engine.review --live --chapters 10 --model-config @router_q25_14b.json --prompt persona --dump-dir sampling/v33rN --state-dir sampling/v33rN/state`，N=1,2,3，串行、每跑独占日志（E16/E21）。
对照：`sampling/ladder2_r{1,2,3}` = 同一模型、同一夹具、**v3.2 尺**。判据线（§7 冻结）：干净 E2 = (首轮 + 改写救回)/生成章次；三跑互差 >10pp ⇒ 不可判、报方差；臂间均值差 <15pp 一律不读。

## 1. 读数

| 跑法 | 尺 | 生成 | 干净 E2 | 处置率 | 首轮 | 救回 | 判死 | 待人工 | tokens | 坏料（缺键/剥键） |
|---|---|---|---|---|---|---|---|---|---|---|
| ladder2_r1 | v3.2 | 10 | 50% | 50% | 5 | 0 | 1 | 4 | 40417 | 3 / 8 |
| ladder2_r2 | v3.2 | 10 | 50% | 40% | 5 | 1 | 2 | 2 | ？（E21 截断） | ？ |
| ladder2_r3 | v3.2 | 10 | 70% | 30% | 7 | 0 | 0 | 3 | ？（E21 截断） | ？ |
| **v33r1** | v3.3 | 10 | **30%** | 70% | 3 | 0 | 1 | 6 | 46908 | **33** / 1 |
| **v33r2** | v3.3 | 10 | **10%** | 80% | 1 | 1 | 2 | 6 | 55643 | **60** / 4 |
| **v33r3** | v3.3 | 10 | **10%** | 80% | 1 | 1 | 3 | 5 | 47101 | **34** / 4 |

`?` 是 E21 那次「两条启动链共用日志名」留下的洞，不是这次的。v33 三跑的 dump 落成了 `sampling/v33rN/chNN.md`（`--dump-dir` 给到了跑法目录本身），已移进 `dump/` 子目录以对齐 `read_run` 的取料路径；内容未动。

## 2. 一致性裁定

v3.3 三跑 = 30 / 10 / 10，均值 16.7%，**互差 20pp > 10pp ⇒ 按 §7 铁律这次重基线本身「不可判」，只报方差**。
方向上三跑全部低于 v3.2 三跑的任何一跑（最高 10/30 对最低 50/50/70），且 v3.3 内部 r2/r3 完全一致、r1 独高 ⇒ 差异不是模型抖动，是**换了输入面**：v3.3 相对 v3.2 只动了尺面文本（抽取提示词加「类型怎么选」判据 + `FIX_GUIDE["H5.1"]` 补 SUSPECTS），判据语义一个字没动（E22 的等价类矛盾另案、已裁定认单类型）。所以这组数读作「**v3.3 这把尺现在测的是抽取器能不能给全 payload 键**」，不读作「模型文体变差了」。

## 3. 坏料：一个抓到的现象，一个没抓到的原因

已提交事件前，抽取产物先被 schema 校验拦一道。缺键拦截数 3 → 33/60/34（10~20×），拦掉的全是 `缺 fact_id`，且**横跨 knowledge 与 belief 各类型**（探针实测 `OBSERVES/READS/IS_TOLD/BELIEVES/SUSPECTS/DOUBTS 缺 fact_id`）。

归因探针（一次性脚本，跑完即删；同一份正文、同一 contract，A/B 只差那三行判据，ch03/06/07 各一对）：

| 章 | v3.3 提示词 | 无判据（v3.2 面） |
|---|---|---|
| ch03 | 收下 2，缺键 2（OBSERVES×2） | 收下 7，缺键 2（OBSERVES×2） |
| ch06 | 收下 6，缺键 4（OBSERVES×2 READS IS_TOLD） | 收下 1，缺键 6（六类各一） |
| ch07 | 收下 7，缺键 2（OBSERVES READS） | 收下 4，缺键 1（OBSERVES） |

⇒ **判据行不是缺键的原因**（去掉判据的那一臂缺键不少、反而更多）。三对样本、单抽样，n 太小，只能说「未能在探针里复现因果关系」，不能说「无关」。全库 10~20× 的位移机制**未归因**，候选剩两个：①正文变了（指引 g2 改的是修稿轮次的稿子，而缺键也出现在 rounds=0 的首轮章 ⇒ 削弱这一条，没排除）；②抽取端点/服务的状态变了（同端点、同模型、温度 0.2 之外无记录）。下一批跑批带 `坏料明细` 落盘（现在只有计数，`item` 没进 dump ⇒ 这是取证缺口，不是分析缺口）。

## 4. 彩票税（E22 裁定一的落地列）

裁定：H5.1 认单类型，E2 定义不动；本列只进报告。**实测已落地**：`readout.py` 新增「H5.1等价税」列
（`_flippable`：当轮 Findings 里 HARD 只剩 H5.1、且每个欠账类型在同 field 等价类里有已抽取的替代 ⇒ 该章可翻；
上界读法，软判据与 minimum_count 一概从宽）。命令：

```
python -m plot_engine.readout sampling/ladder2_r1 sampling/ladder2_r2 sampling/ladder2_r3 \
    sampling/v33r1 sampling/v33r2 sampling/v33r3 sampling/bo_ctrl
python -m plot_engine.readout sampling/v32r1 sampling/v32r2 sampling/v32r3
```

读数（税/生成章，括号为翻税后的 E2 上界）：ladder2 三跑各 **1/10**（上界 60/60/80%），
v33r1 1/10（40%）、v33r2 0（10%）、v33r3 1/10（20%）、bo_ctrl 0；v32 三跑 0/0/1。
这与 E22 当初全库离线重算的 +10.4pp（25 章/240 ≈ 1 章/跑）**同量级互证**：税真实存在，
但每跑只吃一章——被 H5.1 卡死的章多数同时压着 H2.2/H5.3/H5.6（抽取洞整链塌方），
单剩 H5.1 一门的属少数。

翻税章是夹具性的：**ladder2 三跑全翻 ch06**（要 READS，模型给了 IS_TOLD+6×OBSERVES——内容到了、类型没 roll 中），
**v33 翻 ch08**（要 OBSERVES，模型给 4×INFERS）。⇒ 税不是随机噪声，是**夹具在特定章押了模型不常 roll 的类型**；
v4.0 夹具应把 must_change 的类型改押等价类（或直接由服务端按 field 判），这一列届时应趋零。
本列不改变任何 E2 读数。

## 5. 下一步（按 tff 裁定序）

配对打分表（同段剧情的多次渲染排优劣）→ 我打第一棒、tff 第二棒、算 Kendall's W → v4.0 设计稿（多场面夹具 + `_STEPS` 周期 ≥50 + 章长 2000–3000 字 + Writer 段数死规格改 6–12 段或删 + E25 已渲染台账与重锚计数同批）。

## 6. ch05/ch09 全库首轮率重读（E14/E17 欠项，2026-10-12 已清）

命令（27 臂全库，bucket 走 `metrics_from_dump`，逐臂非反推，守 E15 纪律）：

```python
from pathlib import Path
from plot_engine.metrics import metrics_from_dump
c5=[0,0]; c9=[0,0]
for d in sorted(Path("sampling").glob("*/dump")):
    r = {x.chapter_no: x.bucket for x in metrics_from_dump(d).reads}
    for ch,c in ((5,c5),(9,c9)):
        if ch in r: c[1]+=1; c[0]+= (r[ch]=="first_pass")
print(c5, c9)
```

**ch05 首轮 11/27、ch09 首轮 3/27**（旧记 ch05 13/24、ch09 2/24 为 ladder-v1 的 24 臂口径，不可直接比）。
新夹具 ladder-v2 三臂：ch05 三跑全首轮（v32/v33 各 0–1 首轮）；**ch09 仅 ladder2_r3、v33r1 首轮，其余 disposition/ARC**。
机制变了：ch09 现钉 `required_events=['BELIEVES','INFERS','OBSERVES']` 三个单类型，
落空任一即 ARC_CONFLICT（`arc_003 第 9 章落空的事件类型是 Arc 强制项`）——**不再是 E14 的信念探针钉错对象，
而是 required_events 三元组类型钉死**，正是 v4.0 §3.2「场级断言」要吃掉的东西（must_change 兑现事件移出
required_events，类型交给 H5.3 按 field 判）。§3.2 的验收标准据此收紧：v4 夹具的 ch09 必须不再同时钉三个类型。
