# 确认闸设计稿（R8 #1，待冻结）

> 版本：**v1.0 已冻结**（2026-10-16 tff 拍板：Q1–Q5 全按推荐；Q3=A——`review.py` 入口 preflight 的 WP-0 写集例外**已亲批**。v0.1 待冻结版协议同 WP-A 设计稿模式）
> 需求原文：`docs/commercial/r8-commercial-input-requirements-v1.0.md` §4.2（开书前置确认闸）。
> 已有裁定（不问）：确认账落 **backend jobs 表，不进 EventLog，不触发 T1 升 epoch**（v0.12 冻结会追认，`docs/freeze-meeting-and-r8-briefs.md` 拍板表）。
> 澄清提纲（五问）：同文 §①——本稿逐问给推荐+备选，供 tff 拍板。

---

## 1. 现状事实（调研坐标，2026-10-16）

- `jobs` 表已建**从未启用**：schema `id/project_id/task/name/status/payload/created_at`（`backend/noveldb.py:95-102`），status 默认 `'queued'` 无枚举约束；`add_job`（:251-256）全仓零调用，无读/推进函数。**字段够本闸用，零迁移。**
- backend 无 HTTP API 面（路由在 Alexandria `app.py`，经 `deploy/patches/` 注入——该目录是用户脏面/禁区）；审听工位先例即 patch 注入（`deploy/patches/add_prooflisten.py`，四类判定 ok/misread/timbre/regen 落 `prooflisten.jsonl`）。
- 生成批启动 = 手工命令行 `python -m plot_engine.review --live …`；backend 无任何调度拉起路径。集成中枢 `live.py/review.py/experiment.py` 归 WP-0（tff）。
- 协作者纪律：禁自行发起生成批，放行权在 tff（`docs/commercial/collaborator-guide.md:22`）。

## 2. 账面设计（无争议区，拍板即可码）

状态机（单向，代码层枚举，SQL 不动）：

```
queued → confirmed          （放行，payload 冻结规划快照哈希）
       → rejected → queued  （打回改规划后重新提交）
```

- **写入方**：`backend/noveldb.py` 新增 `add_confirm_job(project_id, task, name, payload)`（复用 add_job，payload=设定/卷纲/前三章规划的 JSON 或其 sha256 指针对 workspace JSON）、`get_job(job_id)`、`set_job_status(job_id, status, expected_status)`（CAS 推进，防并发双确认）。
- **可追溯** = created_at/updated 顺序 + payload 哈希（确认对象内容变了旧确认自动失效，见 §4 拦截判据）。**可回放**按裁定降级为"可查询"——不进 EventLog 即无 replay 承诺，R8 原文该条以裁定为准。
- 不做 UI、不做 HTTP 端点（YAGNI：frontend/ 是他人脏面，deploy/patches/ 禁区；审听工位已有先例通道，需要时另批申报）。

## 3. 拍板项（四问 + 一项形态）

| # | 问题 | 推荐 | 备选 |
|---|---|---|---|
| Q1 谁确认 | 且仅是 tff（与放行权同体，collaborator-guide:22） | 同左 | 扩到作者位多人=需身份面，backend 现无账号概念 |
| Q2 粒度 | **开书级一次**：确认对象=设定+卷纲+前三章规划（R8 §4.2 原话即此）；Chapter Contract 不设人闸（闸频×50 章工时模型崩塌，`docs/cost-model.md`） | 开书级 | 每章契约人过=否决需重做工时账 |
| Q3 拦截点位 | **`review.py` 入口 preflight**（唯一满足 R8"确定性拦截，非提示性"的位置）：`--live` 启动时查 jobs 表——本 project 无 status=confirmed 且 payload 哈希==当前规划哈希 → 拒绝启动并打印拦截原因（R8 验收原文）。**触 WP-0，需 tff 开一次写集例外或亲授改动** | A：内置 preflight | B：包装器 `python -m backend.gate review --live …`（零禁区，但绕过 gate 直跑 review=提示性，不合 R8）；C：仅纪律面（最弱，不合"确定性"） |
| Q4 失败回路 | rejected 只回规划层重做，**不计入 max_rounds/成本上限**（那是章内自动阶梯，06 §5；人闸独立计数） | 同左 | 计入=人打回烧自动预算，语义混 |
| Q5 存量处置 | **豁免**：wpe50ch / bo_ctrl 等闸前产物不追溯补确认（归档指纹已定，追溯=改历史读数谱系）；闸只对**新开工书**的后续生成批生效 | 同左 | 追溯补确认=验收样本必须新一本开书 |

## 4. 验收（码批入场券，拍板后细化）

- [ ] 未确认 project 跑 `review --live` → 退出码非零 + stderr 含拦截原因（Q3-A）/ gate 拒绝启动（Q3-B）
- [ ] confirmed 后放行；改规划 payload 哈希 → 旧确认失效再拦截
- [ ] `set_job_status` 双写并发只有一个成功（CAS）
- [ ] `backend/tests/` +4 用例（现 6 用例基线不回归）；plot_engine 全链 554 不动（账面零耦合）

## 5. 写集与禁区

- **写集**：`backend/noveldb.py`（jobs 读写函数）、`backend/tests/`、Q3-A 时 `plot_engine/review.py`（仅 --live 入口 preflight 一处，**需 tff 亲批 WP-0 例外**）、`docs/project-roadmap.md`（v0.14 同步）、本稿。
- **禁区核对**：不碰 `deploy/patches/*`、`frontend/*`、EventLog/plot_engine 协议面（裁定：不进 T1）；`live.py/experiment.py` 不动。

---

> 冻结方式：tff 对 §3 五拍板逐条裁定 + §2 无异议 → 本文改 v1.0「已冻结」→ 码批入场。
