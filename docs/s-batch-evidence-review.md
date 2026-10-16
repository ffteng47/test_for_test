# S 批（#97 云端强模型对照）取证材料审查文档

> 供 tff 拍板用。本文档**只收敛既有落盘读数，不新增任何实验**。
> 数字来源：`docs/phase0-live-run-10ch.md` §13/§14、归档 `sampling/ep1v39p-r1..3`、
> `sampling/ep1v39pv2-r1..3`（各含 ch01–10.md、run.log、_junk.json、state/{state.db,event.db}）。
> 生成：2026-10-16，mainline @ v0.24（commits d6f1db3 / 93b0bc3 已推送）。
> **后记（2026-10-17）**：tff 裁定「入库+开 S 批」已执行；云端三采样读数与判决见
> `docs/phase0-live-run-10ch.md` §15（要点：OK 均值 60%、E2 首判是 r2=9/10、
> 本地恒死 ch02/07 换眼即活、ch10 两车道恒死=纯作者债标本、三批云端成本 <$0.10）。

## 1. 材料谱系（这条证据链是怎么走到今天的）

| 代 | 冻结面唯一变量 | 落纸 |
|---|---|---|
| 批前 | v3.9 尺 + ladder-v5b 夹具，无修订环 | 报告 §12 |
| patch-v1 | 修订环加 `patch_write` 串联分诊 + `needs_arc_replan` 出口（06 §4.2/§4.3） | 报告 §13 |
| patch-v2 | 补写清单**具名化**（actor 角色名 / target 事实命题 / 可达型别点名排除）+ 判死 ArcConflict 携带 trace + 非契约层空清单不空挂 | 报告 §14 |

尺（EXTRACTION_RULER v3.9）、夹具（ladder-v5b-ch10istold）、闸单（job#4）、模型隧道
（qwen2.5:14b @ 127.0.0.1:11500）三代**一字未动**——所有读数差异只能来自修订环本身。

## 2. 六批总读数（三表并列）

### 2.1 patch-v1（§13）

| 批 | OK 率 | 终态 | 修复率 | E2/E3 |
|---|---|---|---|---|
| r1 | 30% | ARC=6 / NH=1 / OK=3 | 8 需修 / 0.50 | 否 / 否 |
| r2 | 40% | ARC=4 / NH=2 / OK=4 | 7 需修 / 0.33 | 否 / 否 |
| r3 | 30% | ARC=6 / NH=1 / OK=3 | 8 需修 / 0.50 | 否 / 否 |

均值 33.3%，vs 批前 33%——**patch_write 没抬起 OK 率，改的是判负形态**。

### 2.2 patch-v2（§14）

| 批 | OK 率 | 终态 | 修复率 | E2/E3 |
|---|---|---|---|---|
| r1 | 20% | ARC=6 / NH=2 / OK=2 | 9 需修 / 0.33 | 否 / 否 |
| r2 | 30% | ARC=6 / NH=1 / OK=3 | 8 需修 / 0.50 | 否 / 否 |
| r3 | 40% | ARC=5 / NH=1 / OK=4 | 9 需修 / 0.75 | 否 / 否 |

均值 30%。**E2 两代六批同否**；G1/G3=True、G2=False 六批同判。止损条款
（「管线成立、夹具 Arc 需作者重开」）**不触发**（ch05 等存在非 needs_arc_replan 型失败）。

## 3. 具名化的净效果：归因收敛，不是 OK 率

### 3.1 错绑消退（修复的实证）

- **ch07 死项迁移（单点实证）**：v1 三批恒死 `003|belief|f3|believes`；v2 r2 Proposals 中
  `BELIEVES actor=char_000003 → fact_000003` 已正确绑定出现、该死项消失。
- **ch05 转活**：v1 三批恒 NEEDS_HUMAN 的章，v2 在两批转 OK。
- **ch09**：v1 时代两批转 OK = 「BELIEVES 未必写不出」实证（裁定 2 兑现）。

### 3.2 残余谱系（v2 三批交叉机检，稳定死项 vs 终轮 Proposals）

| 章·死项 | r1 | r2 | r3 |
|---|---|---|---|
| ch02 `003\|belief\|f8→believes` | 没写+疑错绑 | 同 | 同 |
| ch03 `001\|knowledge\|f6→believed` | 没写 | INFERS 偷懒×3 | 没写 |
| ch04 `003\|knowledge\|f7→known` | INFERS 偷懒 | 没写+疑错绑 | INFERS 偷懒 |
| ch06 `004\|knowledge\|f10→known` | IS_TOLD+INFERS 偷懒 | IS_TOLD 偷懒 | IS_TOLD 偷懒 |
| ch10 `001\|knowledge\|f2→believed` | INFERS 偷懒 | 没写 | INFERS 偷懒×2 |

v1 主导=「型别对但绑错 actor/事实」；**v2 主导=「绑对了、仍写低档型别偷懒」**
（INFERS 顶 OBSERVES/READS、IS_TOLD 顶 known 档）。directive 明写
「可达该档只有 OBSERVES/READS，INFERS 只到 suspected」，模型照旧走捷径——
这三批是**「指令已到、仍不服从」的最干净标本**。

### 3.3 最硬残留

ch02 `003|belief|f8`：三批整场没写+疑错绑，**两代六批同判死项逐字一致**。

## 4. S 批三条件对账（入册口径 = 材料四裁定）

| 条件 | 要求 | 读数 |
|---|---|---|
| ① 补写开火且清单正确 | dump 直证 | **已过**：#98 微修后死章 dump 带 `## Revision` 段，r1 ch02 round 1 `action=patch_write items=H5.1\|BELIEVES;H5.1\|READS;H5.3\|…` 直读「清单到过 Writer」；空清单 patch_write **三批共 1 次**（v2r1 ch05 round 3，见 §4.1） |
| ② 残余非尺/夹具债 | 确定性排除 | **成立**：derive D10 保证档位可达才入契约（非尺债）；同项六批逐字同判死（非夹具债）⇒ 残余属模型服从面 |
| ③ 本地 ≥2 批复现 | 阈值 2 | **已 3 批×2 环**：ch04/06/10 型别偷懒、ch02 没写逐批复现 |

硬前置回顾（入册原话）：「必须要在确定性证据证明本地模型能力不够的前提下，才考虑云端大模型」。
当前归因链：指令面（#96→#98）已修两轮、型别偷懒在具名禁令下仍三批复现 ⇒
**剩余变量在模型面**。

### 4.1 空清单 patch_write 复现明细（稽核更正入册）

§14/初稿「0 次复现」**读错**，实为三批共 **1 次**：`sampling/ep1v39pv2-r1/ch05.md` round 3
`level=writer rules=H5.7 action=patch_write committed=False`（items 空，未渲染）。

根因（码证 + 离线行级 trace 复现，与 dump 逐轮同构）：#98 守门在 **`revision.py:192-195`**
（`if action == "patch_write" and rc.level != "contract"`），但它**先于**振荡升级执行——
`revision.py:198-199` 在连续两轮 violation 集合相同时走 `_ladder_next(action)`，而阶梯序是
`rerun_extraction → rewrite_chapter → patch_write → renegotiate_contract → escalate_to_arc`
（`models/revision.py:30-32`），于是 Writer 层振荡升级把 `rewrite_chapter` **换名**成 `patch_write`，
守门复查不到这个新选择。ch05 现场=round1 H5.4,H5.7→rewrite_chapter；round2 H5.7 同规则复现
→ rewrite_chapter；round3 振荡升级落 patch_write（空清单开火，功能≈rewrite_chapter）。
（注：稽核材料所写 `review.py:192` 应为 `revision.py:192`。）

**定性：微修候选（S 批前或批后做均可），非开批障碍**——修法=把守门后移到 `revision.py:200`
之前（覆盖振荡换名路径），一行移位 + 一条正反测试。不影响条件①的 ch02 dump 直证，
不影响条件②③的任何一格。初稿此格写错是文档问题，不是实验问题。
**勘误关系**：报告 §14「0 次复现」以本节为准；本文档入库时是否同时向 §14 回写一行勘误，
随拍板一并裁定（默认：回写，不改数、只加勘误指针）。

## 5. 若开 S 批的执行纪律（预承诺，未动）

- 走既有 `--lane cloud` / `--cloud-config` 接缝（W6 router），密钥只经 `api_key_env`；
- **只换 model**：尺 v3.9、夹具 ladder-v5b、patch-v2 具名清单、闸单 job#4 全部不动；
- 三采样同归档同分表（`sampling/<云批目录>-rN`），与 §13/§14 并列、不混读；
- 判读逻辑：云端过＋本地恒败 ⇒ 「Phase 1 升模型」候选；双败 ⇒ 封死能力归因、收回 S 批。

## 6. 审查关注点与核对方法

1. **数字核对**：三代的复现/核对命令在报告 `docs/phase0-live-run-10ch.md` 各节尾部——
   批前 §12、patch-v1 §13、patch-v2 §14（复跑属烧模型动作，仅在你明确授权后执行）。
   **不烧模型的核对法**：直接读归档 `sampling/ep1v39p-rN.console.log` /
   `sampling/ep1v39pv2-rN.console.log`（终态计数、修复率、E/G 闸均在 console 输出里），
   逐格对本文 §2 两张表；dump 明细对 `sampling/<批次目录>/ch01–10.md`。
2. **归因机检脚本已入库**：3.2 表由 `sampling/forensic_patchv2_attribution.py` 生成
   （仓库根目录运行 `.venv/Scripts/python.exe sampling/forensic_patchv2_attribution.py`，
   只读归档、不烧模型；本次审查已复跑，输出与表逐格一致）。「疑错绑」判型口径=
   **该 actor 对该 fact 无实现事件（无达档/偷懒命中）且 Proposals 中别的 actor 行出现了该 fact**；
   严格说它证的是「没写 + 该 fact 在别处被写过」，是**嫌疑标记而非绑定的直接证明**——
   如你认为此口径过宽/过严，影响的只是谱系标签，不动摇条件②（ch02 的「整场没写」半截
   在无错绑标记的批次也独立成立）与条件③。
3. 条件③的「本地能力不够」表述：严格说证据支持的是「本地模型对具名禁令不服从」，
   不服从≠不可能（更强模型可能仍偷懒）——这正是 S 批要回答的问题本身，不是已证结论。
