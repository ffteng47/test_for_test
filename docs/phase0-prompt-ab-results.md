# Writer 提示词 A/B：告知型（v1-told）三次采样读数

方案与预注册条款见 `docs/phase0-writer-prompt-ab.md`。基线（盲写 v0-blind，冻在 `f99cc00`）见
`docs/phase0-v2-samples.md`：首轮通过率 40% / 30% / 30%，最终提交率 60% / 40% / 30%，H5.7 泄漏 0/30 章。

代码坐标：finding-1 修复 `08745a7`（E3 恢复机器可判）、提示词配置化 `08b9485`（`--prompt blind|told`）。
模型仍为 `qwen2.5:14b` @ `http://127.0.0.1:11434/v1`，解码参数与基线逐字一致，唯一变量是提示词。

## 变量有效性自检（跑第一枪之前该做、实际在 t1 之后补做）

红线过滤器（目标 fact ∈ `knowledge_forbidden` 就不渲染）没有把要告知的东西抹掉。逐章实渲染结果：

| 章 | 渲染进提示词的告知条目 |
|---|---|
| ch1 | `knowledge add fact_000003 → known`、`knowledge add fact_000001 → suspected`、类型 INFERS、OBSERVES |
| ch2 | `knowledge update fact_000001 → known`、类型 OBSERVES |
| ch6 | `knowledge update fact_000004 → known`、类型 READS |
| ch7 | `belief add fact_000004 → suspects`、类型 SUSPECTS |
| ch10 | `knowledge add fact_000002 → known`、类型 OBSERVES |

⇒ 五个稳定失败章的「跃迁目标 + 必需事件类型」都确实到达了模型。所以下面的失败不能推给「没告诉它」。

## t1 — `C:\Users\tff\AppData\Local\Temp\phase0-v2-t1`

14:47:37 → 15:04:59，1041s，tokens=47453。`run.log` 首行带 `｜prompt=v1-told`，`run.err` 0 字节。

生成 10 / 提交 5 / 未决 `[1, 2, 6, 7, 10]` / replay 一致 True
**首轮通过率 40%**（ch3/5/8/9 第 0 轮即过），修订救回 1 章（ch4，3 轮）。
逐章轮数：`1:0 2:1 3:0 4:3 5:0 6:3 7:2 8:0 9:0 10:1`

| 节 | 读数 |
|---|---|
| §6 | Writer/Validator 3（H2.2）｜Contract/Arc 8（ARC_CONFLICT, H5.3, H5.6） |
| §7 | G1 True｜G2 False｜G3 True｜G4 False｜可讨论改架构 True |
| §8 | E1 True｜E2 **False**（50% < 70%）｜E3 **False**（提交率 < 90%；渲染器已能机器判出，finding-1 修复在真实路径上生效）｜E4 True｜E5 True｜E6 True |

| 章 | status | 判定 | 最终轮抽取产物里的关键事件 |
|---|---|---|---|
| 01 | ARC_CONFLICT | `['INFERS']` 落空且为 Arc 强制项 | — |
| 02 | FAIL | H2.2 `fact_000001` 期望 known 等 3 条 | 只有 `OBSERVES fact_000003`（告知要 OBSERVES F1，它观察了 F3） |
| 03 | OK | | |
| 04 | OK | | |
| 05 | OK | | |
| 06 | FAIL | H2.2 `fact_000004` 期望 known 等 3 条 | |
| 07 | FAIL | H5.3 `char_000001.belief` 无实现事件 | `SUSPECTS fact_000003`、`READS fact_000004`（告知要 belief **F4**，它怀疑了 F3；F4 上写的是 knowledge 类事件） |
| 08 | OK | | |
| 09 | OK | | |
| 10 | FAIL | H2.2 `fact_000002` 期望 known 等 3 条 | `OBSERVES F3`、`OBSERVES F4`（告知要 OBSERVES **F2**，它观察了别的） |

**t1 的读法**：告知条目到场，模型仍然把「跃迁的 field / target」配错对——`SUSPECTS` 用在 F3、`READS` 用在 F4、
`OBSERVES` 用在 F3/F4 而不是被点名的 F1/F2。基线里三个稳定失败章（ch02/ch07/ch10）**一个都没被告知救回来**。
按预注册决策规则，这指向第三分支：**告知不是瓶颈**。等 t2/t3 齐了再落结论。

## 防线一（机械服从）人工抽检 — t1 已做

抽检 t1 提交章 ch04 / ch08 / ch09 的 `## Draft` 全文，判据是「成文与否」而非「是否命中关键词」：

- ch04：DOUBTS 章，内心独白推进（印章 17 粗糙 → 怀疑伪造 → 推到「宗门内有叛徒」），无枚举式填空；
- ch08：OBSERVES 章，有场景、有对白（李四进门发问），观察落到具体物件；
- ch09：三事件章（OBSERVES+BELIEVES+INFERS），从褪色痕迹推到「这枚印章有问题」，推理链在文本里可读。

**3/3 成文 ⇒ 未触发机械服从**（预注册阈值 ≥2/3）。告知没有把模型变成关键词复读机，
所以 t1 的低分不能靠「文体塌了」来解释，只能落在「跃迁的 field/target 配错」上。

另记一条不属于红线的质量观察：三章都把同一场景近似重写了 2–3 遍（段落级复述），
这是 writer 侧的既有文体缺陷，与本次 A/B 的变量无关，进 Phase 1 质量 backlog。

## t2 — `C:\Users\tff\AppData\Local\Temp\phase0-v2-t2`

15:09:06 → 15:30，1268s，tokens=55129。`run.log` 首行带 `｜prompt=v1-told`，`run.err` 0 字节。

生成 10 / 提交 7 / 未决 `[4, 7, 10]` / replay 一致 True
**首轮通过率 50%**（ch1/3/5/6/8 第 0 轮即过），修订救回 2 章（ch2 两轮、ch9 两轮）。
逐章轮数：`1:0 2:2 3:0 4:1 5:0 6:0 7:3 8:0 9:2 10:3`

| 节 | 读数 |
|---|---|
| §6 | Writer/Validator 1（H2.2）｜Contract/Arc 4（H5.1, H5.3, H5.6） |
| §7 | G1 True｜G2 False｜G3 True｜G4 False｜可讨论改架构 True |
| §8 | E1 True｜E2 **True**（70% ≥ 70%，六次采样里第一次过）｜E3 **False**（提交率 70% < 90%）｜E4 True｜E5 True｜E6 True |

| 章 | status | 判定 | 关键事件（最终轮） |
|---|---|---|---|
| 01 | OK | 首轮过（盲写三次里 ch01 抖动两次 ARC_CONFLICT） | |
| 02 | OK | 第 2 轮救回 | `OBSERVES fact_000001` —— 告知的目标终于命中 |
| 03 | OK | | `BELIEVES fact_000001` |
| 04 | FAIL | H5.3 `char_000001.belief` 无实现事件 | `DOUBTS fact_000003` ×2（告知要 DOUBTS **F1**：类型命中、target 绑错） |
| 05 | OK | | |
| 06 | OK | 盲写三次里 ch06 抖动两次 | `READS` 类事实落地 |
| 07 | FAIL | H5.3，renegotiate 三轮到 `contract_version=4` 仍败 | 只有 `INFERS fact_000004`，**没有任何 belief 事件**（告知要 SUSPECTS F4） |
| 08 | OK | | |
| 09 | OK | 第 2 轮救回（第 1 轮因 H5.7 泄漏被打回） | `BELIEVES F1/F3`、`SUSPECTS F2` |
| 10 | FAIL | H2.2 + H5.1（OBSERVES 0<1）+ H5.6 | `OBSERVES fact_000004`（告知要 OBSERVES **F2**） |

**H5.7 泄漏**：提交章里 0 条（ch09 第 1 轮触发过、第 2 轮改掉）⇒ 未劣于盲写基线 0/30。

## 归因（t1+t2 合并，backlog #7 的那三层核查现在有答案了）

告知把变量收窄成了三选一，实测落点是第二类：

1. **提示词没给** —— 排除。§变量有效性 已证告知条目到场，且 t2 ch02 直接命中 `OBSERVES F1`。
2. **Writer 写了但绑错 target** —— **主要失败模式**。事件类型命中率的改善是看得见的：
   t2 里 DOUBTS / OBSERVES / READS / BELIEVES 都按告知出现了，但 target 系统性偏向 F1/F3/F4 轮换，
   被点名的 F2（ch10）与 F1（ch04）两次都被换成别的 fact。ch04/ch07/ch10 三章都是「类型对、fact 错」。
3. **抽取漏了** —— 未见证据（`run.err` 空，坏料仅 2 条：`id_value_not_id` / `missing_payload_keys`）。

补充一条：belief 事件在告知型里**写得出来**（ch03 `BELIEVES F1`、ch09 `BELIEVES F1/F3`、`SUSPECTS F2`），
所以 ch07 的死结不是「模型不会写 belief」，而是**F4 这个 fact 在五轮抽样里（盲写 3 + 告知 2）
只被当成 knowledge 处理，从来没被挂上 belief 动词**。这一条把 backlog #6（ch07 定性）从
「模型弱项」推向「夹具目标选得不对」——F4 在 ch05/ch06 被写成推理与阅读的客体，
再要求同一 fact 突然变成怀疑对象，叙事上没有台阶。

## t3 — 待跑
