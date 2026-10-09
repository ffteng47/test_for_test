# Phase 0 接入本地真实模型（Day 28–30）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 08 §2 的 `model_router_config` 变成可配置的真实模型接入层，并用本地 Ollama（RTX 3090 / `qwen2.5:14b`）跑通一章真实 Writer→抽取→Commit，为 10 章 Gate-A 实验做好准备。

**Architecture:** 三层，全部通过既有注入缝接入，不改管道与 HARD：
1. `llm.py` —— OpenAI 兼容协议的传输层 + 角色路由（writer/extract/plan），本地默认、密钥只走环境变量。
2. `llm_writer.py` / `llm_extract.py` —— 把 `LlmClient` 适配成 `SceneWriter`（07 §4.4 正文）与 `llm_channel`（07 §4.3 通道 3，产出 `EventProposal`）。
3. `review.py --live` —— 用真实模型替换夹具 Writer/通道，产出同一份决策单，并把 `total_tokens` / `total_cost_usd` 落进报告。

**Tech Stack:** Python 3.13（目标 3.12）、pydantic v2、pytest；**零新增依赖**（venv 无 `openai`/`httpx`/`requests`，用标准库 `urllib.request`）。

**Spec:** `alexandria-spec-v0.2/08_experiment_protocol.md` §2（配置）、`07_extraction` §4.3/§4.4、`06_revision_protocol.md` §5、`05_validation` H8。

## Global Constraints

- 网络边界：只允许访问本机回环地址（`http://127.0.0.1:11434`）。禁止把故事内容发往任何云端 API——这是 08 §10 与本机 Auto Mode「不把数据带离本机」的双重硬线。
- 数值一律定点整数 ×1000；`canonical_json` 拒绝 float（05 §5.5）。
- 实验期间不得修改协议、不得新增/放宽 HARD 判据（08 §10 I1/I2）。本计划只做**接线**。
- 所有 offline 单测必须网络无关：模型调用一律经可注入的 `transport` 伪函数，`pytest` 全绿不得依赖 Ollama 进程。
- 模型输出是**不可信输入**：解析必须容错，解析失败产出 `MALFORMED_PROPOSAL` 或空列表，绝不抛穿管道。
- Commit 风格：`feat|test|docs(plot-engine): … (0X §Y)`。

## Review Focus

1. **不可信模型输出的解析**：模型返回带 ```json 围栏、前后废话、`payload` 里带 float、`event_type` 拼错、缺 `source_ref` —— 每一种都必须落到可判定的产物（被丢弃并计数，或转成 `MALFORMED_PROPOSAL`），而不是崩掉实验。
2. **章内 seq 唯一性**：模型可能重复 `seq` 或从 1 起编号；`proposal_event_id` 由 `(chapter, seq)` 推出，重复即同 id → H6.4 误爆。通道必须重编连续 seq。
3. **知识约束泄漏到提示词**：`contract.knowledge_forbidden` 里的 fact 不得作为「可写内容」进入 Writer prompt，否则模型必然写出 H5.7 违例，浪费一整轮预算。
4. **计时与花费的真实记账**：08 §3 要求 `total_tokens` / `total_cost_usd`；本地模型单价 0 但 token 必须真实累计，且超时/重试不得重复计费。
5. **冷启动**：首次调用含模型加载（实测 ≈65s），`timeout_s` 默认必须覆盖冷启动，否则第一章稳定超时——这不是模型问题而是接线问题。
6. **对外承诺的命令必须真能跑出结果**（Day 23–25 教训）：`--live` 若写进文档，必须在有 Ollama 的机器上实测过，且缺 Ollama 时报可读错误而非堆栈。

---

### Task 1: 可配置 LLM 路由层（`plot_engine/llm.py`）

**Files:**
- Create: `plot_engine/llm.py`
- Test: `plot_engine/tests/test_llm_client.py`

**Interfaces:**
- Consumes: 无（标准库 `urllib.request`）。
- Produces:
  - `ModelEndpoint(base_url, model, max_tokens, temperature:int×1000, usd_per_1k_tokens, timeout_s, api_key_env, api_key)`
  - `LlmRouter.endpoints: Dict[str, ModelEndpoint]`；`LlmRouter.default()` → 角色 `writer`/`extract`/`plan`；`LlmRouter.from_config(dict)`（解析 `api_key_env`）；`router.to_config()`（排除 `api_key`）；`router.roles()`
  - `LlmClient(router, *, transport=None)`；`client.complete(role, messages) -> (text, Usage)`；`Usage(prompt_tokens, completion_tokens, total)`；`client.total_tokens` / `client.total_cost_usd`
  - `DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"`

- [x] **Step 1–5:** 已完成并全绿（11 tests）：默认本地、密钥仅走 env 且绝不出现在请求体、OpenAI payload 形状与 `/chat/completions`、温度定点换算、成本仅在配置单价时产生、未知角色 `KeyError`、`to_config/from_config` 往返、局部覆盖继承默认。

### Task 2: LLM 抽取通道（`plot_engine/llm_extract.py`）

**Files:**
- Create: `plot_engine/llm_extract.py`
- Test: `plot_engine/tests/test_llm_extract.py`

**Interfaces:**
- Consumes: `LlmClient.complete("extract", messages)`（Task 1）；`EventProposal`（07 §4.2）；`stage0_extract(..., llm_channel=)` 签名 `llm_channel(draft, scene_plan, contract, state)`。
- Produces: `make_llm_channel(client: LlmClient, *, max_items: int = 24) -> RuleChannel`；`parse_proposals(raw: str, chapter: int) -> Tuple[List[EventProposal], List[dict]]`（返回 proposals + 坏条目记录）。

- [ ] **Step 1: 写失败测试** —— 覆盖：围栏 JSON 可解析；`extraction_method == "llm"`；seq 被重编为 `0..n-1`；非法 `event_type`/缺字段进 `bad` 列表且不产 Proposal；非 JSON 回复 → 空列表 + 一条 `MALFORMED_PROPOSAL` 记录；payload float 被拒或转定点。

Run: `python -m pytest plot_engine/tests/test_llm_extract.py -q` → 预期 FAIL（模块不存在）。

- [ ] **Step 2: 实现** —— prompt 含 Draft、`contract` 的 required_events/knowledge_allowed、以及**明确禁止清单**；要求模型只回 JSON 数组，元素字段 `event_type/actor/target/payload/source_ref`。解析用「抓第一个 `[`…最后一个 `]`」再 `json.loads`，逐条 `EventProposal.model_validate` + 校验 `extraction_confidence`。
- [ ] **Step 3: 全绿后提交** `feat(plot-engine): LLM extraction channel with untrusted-output parsing (07 §4.3)`。

### Task 3: 真实 SceneWriter（`plot_engine/llm_writer.py`）

**Files:**
- Create: `plot_engine/llm_writer.py`
- Test: `plot_engine/tests/test_llm_writer.py`

**Interfaces:**
- Consumes: `LlmClient.complete("writer", messages)`；`SceneWriter = Callable[[Scene, ChapterContract, Optional[StoryState]], str]`；`compose_chapter_draft`（负责补 hook / reader 标注，Writer 自身**不得**产 markup）。
- Produces: `make_scene_writer(client: LlmClient, *, min_paras: int = 2, max_chars: int = 1200) -> SceneWriter`；`scene_prompt(scene, contract, state) -> list[dict]`。

- [ ] **Step 1: 写失败测试** —— 覆盖：返回段落以空行分隔；输出不含 `<!--`（markup 由组装器负责）；prompt 中不出现 `knowledge_forbidden` 的 fact_id；空回复 → 抛 `WriterError`（让 `compose_chapter_draft` 记 `scene_failed`，不静默产空章）；角色名/地点从 `state` 取，未知 id 不崩。
- [ ] **Step 2: 实现**：system 提示写明「悬疑长篇正文，中文，只写本 Scene 目的，不揭示禁止知识，不写元数据」；temperature 走 endpoint 配置。
- [ ] **Step 3: 提交** `feat(plot-engine): LLM scene writer seam (07 §4.4)`。

### Task 4: 真实逐章源 + `review --live` 接线

**Files:**
- Modify: `plot_engine/review.py`（新增 `--live` / `--model-config` / `--max-chapters`）
- Modify: `plot_engine/experiment.py`（`run_experiment` 接受 `llm_client`，把 `total_tokens`/`total_cost_usd`/`total_duration_ms` 写入报告）
- Create: `plot_engine/live.py`（`build_live_source(...)`：契约沿用夹具的协议合法契约，Draft/抽取通道换成真实模型）
- Test: `plot_engine/tests/test_live_wiring.py`

**Interfaces:**
- Consumes: Task 1–3 全部；`ChapterArtifacts`；`RevisionLoop`（06 §5）。
- Produces: `build_live_source(client, *, contracts, plans) -> ChapterSource`；`main()` 支持 `--live`；缺 Ollama 时打印「本地模型不可达：<url>」并返回 2。

- [ ] **Step 1: 写失败测试** —— 用 fake transport 走 `run_experiment(..., llm_client=client)`，断言报告 `total_tokens > 0`、`total_duration_ms >= 0`、且离线（无 client）路径逐字节不变。
- [ ] **Step 2: 实现并全绿**。
- [ ] **Step 3: 单章真实冒烟** `python -m plot_engine.review --live --chapters 1`，记录耗时与 token；确认 Draft 长度、Proposal 数量、Commit 状态合理后再进 Step 4。
- [ ] **Step 4: 提交** `feat(plot-engine): live model wiring + token/cost accounting (08 §2/§3)`。

### Task 5: 10 章真实实验与决策单落盘

- [ ] **Step 1:** `python -m plot_engine.review --live --chapters 10 > docs/phase0-live-run-10ch.md`（预计 45–60 分钟，后台跑）。
- [ ] **Step 2:** 按 08 §6/§7 归类每个 failure；不满足冻结闸的一律记 backlog，**不改架构、不改 HARD**。
- [ ] **Step 3:** 按 08 §8 判 E1'–E6'，写结论：进 Phase 1 / 继续 Phase 0。
- [ ] **Step 4:** 提交 `test(plot-engine): Phase-0 live-model 10-chapter experiment report`。

## Known Gap（本计划不覆盖）

`Arc → ChapterContract → ScenePlan` 生成器仍不存在。Task 4 沿用夹具里协议合法的手工契约，因此 08 §6「Contract / Arc 问题」归因在真实链路上仍只被部分验证。这一项单独排期，需要产品决策（生成什么故事），不属于接线工作。
