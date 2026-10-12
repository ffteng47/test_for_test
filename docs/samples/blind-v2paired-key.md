# 答案键（评分收齐前勿开）

| 盲评号 | 组 | 变体 | 跑法 | 原章号 | 判定终态 |
|---|---|---|---|---|---|
| 01 | 1 | A | v33r3 | 1 | ARC_CONFLICT |
| 02 | 1 | B | ladder2_r1 | 1 | OK |
| 03 | 1 | C | v33r1 | 1 | ARC_CONFLICT |
| 04 | 1 | D | v33r2 | 1 | ARC_CONFLICT |
| 05 | 1 | E | ladder2_r2 | 1 | ARC_CONFLICT |
| 06 | 1 | F | ladder2_r3 | 1 | OK |
| 07 | 2 | A | v33r3 | 2 | NEEDS_HUMAN |
| 08 | 2 | B | v33r1 | 2 | NEEDS_HUMAN |
| 09 | 2 | C | ladder2_r2 | 2 | OK |
| 10 | 2 | D | ladder2_r3 | 2 | OK |
| 11 | 2 | E | ladder2_r1 | 2 | NEEDS_HUMAN |
| 12 | 2 | F | v33r2 | 2 | OK |
| 13 | 3 | A | v33r1 | 3 | OK |
| 14 | 3 | B | ladder2_r1 | 3 | OK |
| 15 | 3 | C | ladder2_r3 | 3 | OK |
| 16 | 3 | D | ladder2_r2 | 3 | OK |
| 17 | 3 | E | v33r3 | 3 | OK |
| 18 | 3 | F | v33r2 | 3 | NEEDS_HUMAN |
| 19 | 4 | A | v33r2 | 4 | OK |
| 20 | 4 | B | ladder2_r3 | 4 | OK |
| 21 | 4 | C | ladder2_r2 | 4 | OK |
| 22 | 4 | D | ladder2_r1 | 4 | OK |
| 23 | 4 | E | v33r3 | 4 | OK |
| 24 | 4 | F | v33r1 | 4 | OK |
| 25 | 5 | A | v33r3 | 5 | ARC_CONFLICT |
| 26 | 5 | B | ladder2_r3 | 5 | OK |
| 27 | 5 | C | v33r2 | 5 | NEEDS_HUMAN |
| 28 | 5 | D | ladder2_r2 | 5 | OK |
| 29 | 5 | E | v33r1 | 5 | NEEDS_HUMAN |
| 30 | 5 | F | ladder2_r1 | 5 | OK |
| 31 | 6 | A | v33r2 | 6 | NEEDS_HUMAN |
| 32 | 6 | B | v33r1 | 6 | NEEDS_HUMAN |
| 33 | 6 | C | ladder2_r1 | 6 | NEEDS_HUMAN |
| 34 | 6 | D | ladder2_r2 | 6 | NEEDS_HUMAN |
| 35 | 6 | E | ladder2_r3 | 6 | NEEDS_HUMAN |
| 36 | 6 | F | v33r3 | 6 | NEEDS_HUMAN |
| 37 | 7 | A | ladder2_r1 | 7 | NEEDS_HUMAN |
| 38 | 7 | B | v33r3 | 7 | NEEDS_HUMAN |
| 39 | 7 | C | ladder2_r3 | 7 | NEEDS_HUMAN |
| 40 | 7 | D | v33r1 | 7 | NEEDS_HUMAN |
| 41 | 7 | E | ladder2_r2 | 7 | OK |
| 42 | 7 | F | v33r2 | 7 | NEEDS_HUMAN |
| 43 | 8 | A | ladder2_r3 | 8 | OK |
| 44 | 8 | B | v33r1 | 8 | NEEDS_HUMAN |
| 45 | 8 | C | v33r2 | 8 | NEEDS_HUMAN |
| 46 | 8 | D | v33r3 | 8 | NEEDS_HUMAN |
| 47 | 8 | E | ladder2_r1 | 8 | OK |
| 48 | 8 | F | ladder2_r2 | 8 | OK |
| 49 | 9 | A | ladder2_r2 | 9 | ARC_CONFLICT |
| 50 | 9 | B | ladder2_r3 | 9 | OK |
| 51 | 9 | C | v33r1 | 9 | OK |
| 52 | 9 | D | v33r2 | 9 | ARC_CONFLICT |
| 53 | 9 | E | ladder2_r1 | 9 | ARC_CONFLICT |
| 54 | 9 | F | v33r3 | 9 | ARC_CONFLICT |
| 55 | 10 | A | v33r1 | 10 | NEEDS_HUMAN |
| 56 | 10 | B | v33r3 | 10 | NEEDS_HUMAN |
| 57 | 10 | C | ladder2_r1 | 10 | NEEDS_HUMAN |
| 58 | 10 | D | v33r2 | 10 | NEEDS_HUMAN |
| 59 | 10 | E | ladder2_r2 | 10 | NEEDS_HUMAN |
| 60 | 10 | F | ladder2_r3 | 10 | NEEDS_HUMAN |

## 这份题消掉了什么、没消掉什么

**消掉了**：内容。一组 = 同一段剧情（同原章号、同夹具阶梯的第 N 步），六个变体是它对同一模型六次渲染；组内变体字母每组独立重洗，跨组不可对照（A 在每组是不同的跑法）。

**消掉了**：长度混淆。六臂同模型，中位字数（`ladder2_r1..r3`、`v33r1..r3` 依次）937 / 968 / 978 / 991 / 947 / 1038，最大差 10.8%——上一份 9 臂普查里 `qwen3.5:27b` 比 `14b` 长 2.7 倍那种「名次其实是篇幅」的读法，在这份表里没有立足点。验证：`python -c` 走 `plot_engine.blind_review.pool()` 对六个 `sampling/` 目录求 `statistics.median(len(text))`。

**没消掉**：尺。`ladder2_*` 是 v3.2 尺下的稿子，`v33r1..3` 是 v3.3 尺下（指引 g2）的稿子；三对三，组内不可区分，但**任何「v3.3 的文体更好/更差」的读法都不成立**——两份都是同一个模型，差的是判定与修稿指引的面，名次只能读作「这六次渲染里哪个最好读」，不能读作尺间对比。尺间对比归机检（`docs/phase1-rebaseline-v33.md` §2，那里已按铁律判为「不可判」）。

**没消掉**：局面。六个臂全部是「张三查印章」这一桩事（E23）⇒ 这份表**只配问配对名次**，不配问「愿意付费读」；那一列照旧收，但读数不作废也无效，只能当噪声基线看。

**已知出题缺陷**：`R1 不复述` 在跨组维度上必然全员不过（同一个事实在十段里被反复推进），所以 R1 只在组内比较时有效力；E25 的重锚计数（`python -m plot_engine.reanchor sampling/<run>`）是这一列的机器对应物，tff 打表时想加自己的「重锚次数」列就加。
