# 协作者须知（并行开发入场券）

> 版本：v1.0（2026-10-15）。配套 `docs/project-roadmap.md` v0.2 使用：roadmap 告诉你**做什么、能不能做**，本文告诉你**怎么做才不毁掉别人的读数**。
> 冲突时以本文为准于"纪律/禁区"，以 roadmap §4 撞车矩阵为准于"并行窗口"。

## 1. 纪律包（尺与读数——违反 = 数据作废）

1. **落盘纪律（§13）**：任何读数进结论前必须落盘——`sampling/<批次>/` 档案路径 + 可复现命令写进报告（源：`docs/phase1-rebaseline-v33.md` §13 + 入册 commit c59c02b）。未落盘的读数不进结论。
2. **一因一批 + 尺戳 bump**：改变尺面（抽取提示词/parse 判据/payload schema，即 `plot_engine/llm_extract.py` 行为面）的代码批，必须同步 bump `EXTRACTION_RULER` 版本戳并钉进测试（`plot_engine/tests/test_instr.py` 的尺戳用例）；**新旧尺号读数分表，绝不并列比较**。
3. **同缓存谱系纪律（§20）**：temp0 的"跨遍确定性"只在同谱系内成立。双遍/重采样二选一：全程不逐出（暖）或每遍前逐出（冷），混谱系的跨遍比较作废。
4. **仪器与产物分离**：坏料只记录不修补（`parse_proposals` docstring）；改判据 = 改尺 = 走第 2 条，不走"顺手修一下"。
5. **车道边界（§19/§21）**：尺/生成 = **qwen2.5:14b**（稠密）。qwen3 世代 MoE 禁上尺（§18）；qwen3.5:27b、qwen2.5:32b 判负、升级路径关闭（§19/§21）。跨机同表仅限**抽取回放**（J=1.0 已证）；**Writer/生成面跨机等价未证**（#78 闸前，生成批只走 @213）。

## 2. 禁区清单（触碰即回滚）

| 禁区 | 原因 |
|---|---|
| 禁读 `docs/samples/blind-v2paired-key.md` | 盲评答案键——读过的模型/人即污染该锚点 |
| 勿 stage/commit 业主脏文件：`docs/usage-wiki.md`、`docs/ebooks-standard.md`、`frontend/src/api/*`、`frontend/src/views/*`、`frontend/src/data/store.js`、`deploy/patches/*`、`.qoder/settings.local.json`、`plot_engine/ai_flavor_*.py`、sqlite `-shm/-wal`、`_aiflavor_*` | 他人在做的工作面 |
| 禁 C 盘下载模型 | `OLLAMA_MODELS=E:\github\LLM\ollama`，磁盘约束 |
| 禁 `api_key` 明文进任何配置/代码 | 只走 `api_key_env` |
| 禁自行发起 GPU 生成批 | 放行权在 tff（显式"放行"）；零生成回放闸不需放行 |
| 批次在跑时勿改 `plot_engine/`（尺面/仲裁面文件） | 后臂进程会加载新码，一臂一张嘴 |
| `1.txt` 为临时任务单 | 随时被覆盖，禁载纪律/结论（§13 落盘纪律 §②） |

## 3. 验证基线（改码前后都要绿）

- 全链：`.venv/Scripts/python.exe -m pytest plot_engine/tests -q`（2026-10-15 现势 **525 passed**）。
- 每条新判据/lint 规则 **1 正 1 反**用例钉住（lint 纪律，roadmap L5）。
- 纯离线工作（WP-C/WP-D/R7/WP-A 设计稿）不需要 GPU，也不得借口"测一下"占 213 车道。

## 4. Git 约定

- 直推 `main`；commit 前缀沿用现史：`feat/fix/data/docs/chore(review)` + 中文摘要。
- 永不 `--no-verify`、永不 `git stash`（共享工作树，见 §13 附注）、危险命令（`reset --hard`/`checkout --.`）须二次确认。

---
拿不准的边界问题：停下问 tff，别替项目做裁定。
