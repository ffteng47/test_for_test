# WP-E：ladder-v5 五十章压力测试读数（2026-10-15）

> 版本：v0.1（问题批次收口报告，roadmap WP-E 行对应物）
> 尺戳：抽取尺 v3.6-is-told-actor（run.log 首行指纹为凭）；指引 g3-keep-reading-scenes；Writer 面 w4-scene700-1000+ledger；夹具 ladder-v5-50ch；仪器 instr-v2-local；模型 qwen2.5:14b（@213 隧道 127.0.0.1:11500）。
> 归档（§13）：`sampling/wpe50ch/`（dump 50/50 + run.log + state/）+ `sampling/wpe50ch_console.log`。
> 复现：`.venv/Scripts/python.exe -m plot_engine.review --live --chapters 50 --fixture experiment_50ch --model-config @router_q25_14b.json --dump-dir sampling/wpe50ch`
> 读数命令：`.venv/Scripts/python.exe -m plot_engine.readout sampling/wpe50ch`
> **并表禁**（roadmap v0.10 稽核裁定）：50 章读数与 v4 十章基线（带 [20,40]）规模不可比，只作参照、不同表并列。

## 1. 主读数

| 指标 | 值 | 口径 |
|---|---|---|
| 生成 | 50/50，用时 8551s（≈2.38min/章），tokens 1,177,668，cost $0 | 隧道内本地算力 |
| 终态 | OK 13（首轮 5 + rewrite 救回 5 + renegotiate-only 3）／NEEDS_HUMAN 36／ARC_CONFLICT 1 | run.log；dump 头行 status=FAIL 36 = trace_status=NEEDS_HUMAN |
| 处置率 | **74%** | (36+1)/50 |
| 干净口径 E2 | 20%（§8 名义提交率 26%） | (5+5)/50，renegotiate-only 进分母不进分子 |
| §8 退出闸 | E1 ✓ / **E2 ✗** / **E3 ✗** / E4 ✓ / E5 ✓ / E6 ✓ | E2=提交率≥0.70；E3=提交率≥0.90 且 max 轮≤3 |
| Revision | 需修 44 章，修复率 **0.18**，烧满 3 轮章 16（2,3,5,6,14,15,20,28,30,32,34,35,36,37,45,50） | 逐章轮数见 console |
| replay | 一致 True；穿帮章 11；跨章重复 9；章首同主语 28/50；废卷率 0% | readout |

## 2. §6 失败分类与 rule 频次

- Writer/Validator 问题 20（H2.2, H5.7）；Contract/Arc 问题 74（ARC_CONFLICT, H5.1, H5.3, H5.4, H5.6）——**失败主体在契约/Arc 面，不在写作面**。
- dump rule 提及计数：H5.3×110、H5.4×97、H5.6×72、H2.2×72、H5.1×14、H5.7×11。**H5.3（must_change 未实现）居首**，与冻结会议程 #1（must_change 系归属空白，`docs/freeze-meeting-and-r8-briefs.md`）和 backlog #1 同源；本批不判其语义（尺冻结面 v3.6，A/D 对齐批未入）。

## 3. 仪器面

- 抽取产出 1884 条（规则提升 1）；坏料合计 ~75：stripped_payload_key 29／id_value_not_id 10／truncated_segment 10／missing_payload_keys 6／unknown_id 6／over_cap 8／unknown_event_type 2／segment_failed 2／segment_unparsable 2。
- 分段 258／修复 8／合并去重 591／段级废卷 2 段（0%）。
- **finish=length 可疑 8 次**：extract 请求上限 2400，正文实出 5582–6033 后截停——与 rule 频次里 over_cap/truncated 同族，属抽取上限面而非 Writer 面； instr-v3 预注册（`docs/r4-guided-decoding-prereg.md`）对表时把 length 率列为首读数之一。

## 4. 判死章靶位漂移

- wpe50ch 判死 ch09（`arc_003 第 9 章落空的事件类型是 Arc 强制项，契约层无权放宽：['BELIEVES']`）；v4gL（十章）判死 ch05，两跑互看对方章：wpe ch05=FAIL、v4gL ch09=FAIL。
- 即 **temp0 贪心下 Arc 冲突触发章位不固定**——与 §24 (b) 批"存在性整面抖动"同谱系的章间表现，非夹具缺陷（见 §5）。

## 5. 夹具结论与批次判语

- **ladder-v5 验证通过**：readout「夹具不可达章（构造级）：无」；ch11–50 阶梯段无系统性早爆——OK 率前 10 章 2/10 vs 后 40 章 11/40（20% vs 27.5%），后段不劣于前段，判负主体与章位无关。
- **主判语**：在当前冻结面（尺 v3.6 + H5.3 归属空白未修 + 抽取上限 2400）下，**50 章规模不成立**——74% 处置率、修复率 0.18，三轮预算被契约类失败（H5.3/4/6 族）消化殆尽。这是规模化前置压力测试的预期产出：暴露的不是 Writer 不行，而是**修订阶梯对契约层缺陷没有出口**（正是冻结会议程 #1/#2 的实据）。
- 后续依赖登记：①H5.3 族语义→ 冻结会/backlog #1；②finish=length 与坏料→ instr-v3 预注册对表；③判死章位漂移→ (b')/temp0 自洽族既有结论，本批不新开刀。

## 6. 章内在场穿帮盲区（tff 人眼实证，2026-10-16 补录）

ch50 人眼三连矛盾，机检全漏（`:行号` 指 `sampling/wpe50ch/ch50.md` Draft 段）：
- :22「藏宝阁内只剩下赵六一人」→ :38「张三和赵六坐在藏宝阁内」——张三凭空进场；
- :60「离开了藏宝阁」→ :62 走在路上 → :64「藏宝阁内……张三和赵六背对背坐着」——空间回卷；
- :26「钥匙仅此两枚，一把高层一枚赵六」vs :66「守卫历来两个人，钥匙两个人共同保管」——规则漂移。

**为什么机检不到**：①该章 3 条 HARD（H2.2/H5.4/H5.6）全是知识跃迁族——张三的进场只以「char_000001.knowledge 被改动」的 H5.4 副作用**间接留痕**，引擎看见后果、没判原因；②`consistency.py` 查的是台账引用/地点定义/事件驱动跃迁（跨章、账级），「谁在屋里」这种静态在场关系**没有任何账**（01 Taxonomy 无 presence 型事实，`current_location` 只由 CHANGES 更新）；③`prose_audit.py` 穿帮 = 词表级（现代词/同构/重复），无空间逻辑。
**为什么修订环帮倒忙**：三轮指引均为「补一场他亲眼看到/被告知该事实的戏」（修稿指引 H2.2 原文），模型补了问话戏、旧场景未删——:60–64 的回卷即缝合产物。#70 泛化教训（加规则文字≠加遵守）在 Writer 面的实例。
**兜底有效**：ch50 本就 NEEDS_HUMAN 未提交——人审闸干的事被 tff 干了。
**归属登记**（roadmap backlog，本批不动刀）：章内在场一致性候选 = (a) Level-3 语义层（`level3_fn` 位已在，判分线待 tff 定标）；(b) 账本级建模（在场/位置静态事实 = T1 新事件型 → epoch_2 / WP-F 双层追踪面）。


## 7. 谱系一致性自检

同缓存谱系：run.log 首行含 `夹具=ladder-v5-50ch｜抽取尺=v3.6-is-told-actor` ✓；dump 50/50 ✓；console 尾报 E1–E6 齐 ✓；未并 v4 十章表 ✓。
