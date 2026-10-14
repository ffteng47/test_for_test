# instr-fix-01 批次落档：仪器戳 `instr-v2`，与尺戳分开记账

任务单 `info.txt` 的执行记录。**边界声明（任务单原话）：不动判据语义、不动 H 系列、
不动协议字段、不动夹具钉。** 唯一触碰提示词文本的是 W4b（一行删除），默认**缓办**——
`instr.W4B_TOUCHED = False`，提示词那句留着也只是冗余，代码兜底在后（W4a）。

仪器戳与尺戳（`EXTRACTION_RULER = v3.3-belief-type-criteria`）**分开记账**：
run.log 首行新增 `仪器=instr-v2-local` / `｜车道=local|cloud`。
换车道 = 仪器版本变更（护栏 3），此前抽取读数按老规矩不与新戳同表。

## 三类废卷的分层（P0 的正当性）

| 层 | 问题 | 工程能不能治 | 本批次买到什么 |
|---|---|---|---|
| A 仪器完整性 | 截断、坏 JSON、人名代 id | 能，且可确定性验证 | W1–W4 全在这里 |
| B 仪器有效性 | 格式全对但该抽的没抽 | 有天花板（14B 语义召回上限） | W5 把它与格式噪声**分开定量** |
| C 引擎质量 | 尺可信后正文本身不过关 | 完全无关 | 不碰（H5.7 过度声明已交过学费） |

**谁要是承诺"P0 做完即达商用"，那就是 H5.7 式的过度声明。**

## 工作项落地位置

| 项 | 机制 | 代码 | 验收 |
|---|---|---|---|
| W1 | 场景标记 / ~1800 字窗口 + 200 字重叠带切分，逐段抽取（每段提示词都带角色注册表），按 `(event_type, actor, fact_id)` 确定性合并去重，段内段号重映射回全局 | `instr.split_draft_segments` / `instr.dedup_proposals` / `llm_extract.make_segmented_llm_channel` | 冻结 v4c 全语料重跑 `finish=length` = 0；能完整跑完的章合并后条目数 ≥ 单跑基线 95% |
| W2 | 解析失败 → 坏输出+错误回喂重试 1 次 → 仍失败**只废该段**（记 `segment_failed` + 缺失 `char_span`，章级 `malformed_reply` 恒 0） | `llm_extract.extract_with_repair` | `_junk.json` 三份历史坏输出离线回放（零采样）修复率 100% 或段级优雅降级 |
| W3 | actor/target 先精确匹配编号 → 命中注册表姓名/昵称映射到编号 → 未知/多义定向追问一次 → 仍解不出才拒收并记因 | `instr.build_alias_index` / `instr.resolve_actor_id` / `llm_extract._resolve_actor_field` | v4c2 第 3 章（12 条人名废卷）重跑废卷 = 0；多义率单独入账 |
| W4a | 数值定点键缺省由代码补 `DEFAULT_FIXED_POINT = 700`，可审计、可全局改 | `instr.apply_code_defaults` | 补键记 `defaulted_fixed_point` 账；错误类型（字符串/bool/float）仍丢弃，不洗坏料 |
| W4b | 删「数值键一律给 700」句 | `sampling/_probe_believes.py` 的 `v34_patch()` 已删；`instr.W4B_TOUCHED = True`；尺戳 bump v3.4 | tff 2026-10-14 裁定「删」。**位置史**：该句从未进生产提示词 `extract_prompt`，只在探针的 v3.4 草案补丁里——这正是 info.txt 说的"v3.4b 旁证，证据薄"。生产面本就不写默认值，故 v3.3→v3.4 提示词文本零变化；bump 记录的是"W4b 裁定 + W4a 代码兜底"共同构成新冻结面：v3.4 起 700 = 模型真判断，缺省 = 代码补 + `defaulted_fixed_point` 有账 |
| W5 | 温度 0 连跑两遍，逐章条目集合 Jaccard + BELIEVES/SUSPECTS 检出稳定性 | `instr_measure.double_run_report` / `instr_cli.report` | 预登记硬门槛见下 |
| W6 | 模型路由层：两条车道共用同一套分段/修复/别名/默认值，只有 client 不同 | `llm_extract.make_laned_channel` / `live.build_laned_source` | 2×2 对表 + 车道决策规则 |

`readout` 新增两个常设列：**废卷率**（章级，无账记 `-`，没测 ≠ 0）、**一致率**
（`<跑法>_fluctuation.json` 的 Jaccard 中位，同样没测记 `-`）。

## W5 预登记硬门槛与升级路径（"工程够不够"的答案机制）

```
废卷率 < 2%（30 章即 0 章）  ∧  Jaccard 中位 ≥ 0.85  ∧  探针集 BELIEVES 两跑一致
  └─ 全达标 → pass:open_v4d_baseline（才准开 v4d 基线）
  └─ 废卷达标但一致率/召回不达标 → ceiling_B:route_stronger_model_or_self_consistency_x3
       （天花板在 B 层，触发对冲：抽取路由到更强模型 或 自一致性 ×3 确定性合并）
  └─ 两者都救不回 → BELIEVES 类原语列为"本产品代不支持"，转商用规格裁剪，不再烧探针
  └─ 废卷率本身不达标 → instrument_fail:fix_A_first（A 层没修好，B/C 层花的钱都在买噪声）
```

## W6 预登记车道决策规则（含余量，tff 2026-10-14 裁定）

云端召回领先 **>10pp**（`LANE_RECALL_MARGIN = 0.10`）且一致率不低于本地 **−2pp**
（`LANE_JACCARD_TOLERANCE = 0.02`）⇒ 抽取默认切云端，本地留作降级档；
两者差不多 ⇒ 留本地（省 COGS、少一个外部依赖），云端只在本地废卷/漏检时按章兜底。

**为什么加余量**：原规则 `cr > lr` 是**噪声开关**——10~30 章样本里召回差 1~5pp 完全在
波动范围内，据此切默认车道等于拿抖动做产品决策。一致率那侧是「一致性铁律」的下行容差：
宁可少收 2pp 一致率，不可让默认车道更抖。边界含等号（0.71 vs 0.60 切，0.88 vs 0.90 切）。

**判据文本之争（v3.3 对 v3.4b）在 W5 云端数字落地前一律不再投入**——强抽取模型
很可能让那两行措辞的差异直接失去意义。

## 三条护栏（治理，不是代码）

1. **仪器戳要记下云的完整身份。** `instr.lane_identity_report` 产出
   `provider + model + version + base_url + temperature + max_tokens + extra_body`，
   写入 run.log 与台账。云端模型会被供应商静默换版 ⇒ **钉测探针集定期回放当金丝雀**，
   读数漂移即报警。这就是"度量仪器必须先被度量"，对象从本地模型换成外部服务。
2. **书稿出域是商业决策，需要拍板，不是工程默认。** 私有化部署客户不能把稿子送出去
   ⇒ 本地车道不是备胎，是一个产品档（云端标准档 / 本地部署档），差距由 W5 的 2×2
   量化并写进产品规格书。
3. **换车道 = 仪器版本变更。** 默认车道一旦切换，戳升档
   （`instr-v2-local` → `instr-v2-cloud`），v4d 基线在哪条车道上跑，跑之前一次说清。

## 怎么跑（零生成）

```bash
# 1) W1（可选）：分段拆分看一眼
python -c "from plot_engine.instr import split_draft_segments as s; \
print([ (g.index, g.para_start) for g in s(open('稿.txt',encoding='utf-8').read()) ])"

# 2) 用真实模型把冻结 v4c 全语料抽取两遍，proposal 骨架落 JSON（chapters/malformed/tokens/recall）
#    —— 这一步零生成，只做抽取回放；token 量为 v4d 预算零头。

# 3) W5 单车道双跑报告
python -m plot_engine.instr_cli l1.json l2.json --probes 2,3,9 --chapters 30 \
    --out docs/instr-w5-fluctuation.json

# 4) W6 2×2 对表（本地1 本地2 云端1 云端2）
python -m plot_engine.instr_cli l1.json l2.json c1.json c2.json --probes 2,3,9 \
    --chapters 30 --out docs/instr-w6-2x2.json

# 5) W2 验收：_junk.json 历史坏输出离线回放
python -m plot_engine.instr_measure replay-junk <run>/dump/_junk.json \
    --out docs/instr-w2-junk-replay.json
```

JSON 契约见 `plot_engine/instr_cli.py` docstring（只重放 proposal 骨架：
`type/actor/target/payload`，进集合一致率口径的是"抽到了什么"）。

## 时序与代价

- W1–W4 编码数日（本批次已完成），W5/W6 回放半天；
- 成本：**零生成**；抽取回放约 30 章 × 2 跑 + 修复回放，token 为 v4d 预算零头；
- 全部完成后才准开 v4d 基线。

## P1 连锁反应（先不定稿）

等 W5 云端数字：强模型单跑召回就达标 ⇒ "关键词提名 + 定向确认"可能整个不需要，
P1 缩水成"证据片段进 schema"一件事；强模型也救不回 BELIEVES ⇒ 才轮到确定性提名上场，
且届时它服务的是明确量化过的缺口。

## 云端车道实例：DeepSeek（2026-10-14 查证 api-docs.deepseek.com）

模板 `deepseek.router.json`（可提交，密钥只走 `api_key_env`）：

```json
{"extract": {
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-flash",
  "api_key_env": "ALEXANDRIA_CLOUD_API_KEY",
  "max_tokens": 2400, "temperature": 0, "timeout_s": 120,
  "usd_per_1k_tokens": 0.41,
  "extra_body": {"thinking": {"type": "disabled"}}}}
```

跑法：

```powershell
$env:ALEXANDRIA_CLOUD_API_KEY = "sk-..."        # 当前会话
python -m plot_engine.review --live --chapters 1 --lane cloud `
    --cloud-config @deepseek.router.json --state-dir run_c --dump-dir run_c
```

**三个坑（踩中任何一个都会毁读数，不是风格问题）：**

1. **模型名换代了**：`deepseek-chat` / `deepseek-reasoner` 已于 2026-07-24 弃用，
   现行名 `deepseek-flash`（V4.1-Flash，1M 上下文）与 `deepseek-v4-pro`。
   用旧名还能通，但踩在弃用倒计时上。
2. **默认是思考模式，而思考模式下 `temperature` 不起作用**（官方原话
   "Has no effect in thinking mode"）。W5 规格是「温度 0 连跑两遍」——
   不显式关思考，两跑一致率测的就不是同一个东西。所以模板必须带
   `thinking: {"type": "disabled"}`（等价写法 `reasoning_effort: "none"`）。
   顺带：非思考模式下 `top_p` 固定 1.0，传什么都不理。
3. **CoT 在 `reasoning_content` 里，不在 `reasoning`**。`llm.py` 原先只认 Ollama
   方言的 `reasoning`，云端思考型模型的 `reasoning_chars` 会恒为 0（仪器说谎）；
   现已两种方言都读，并把 `completion_tokens_details.reasoning_tokens` 记入
   `CallDiag`——思考 token 按输出计费，不入账等于少算钱。

**计费（每 1M token；峰时 = 01–04 与 06–10 UTC 周一至五，其余含周末一律谷时半价）：**

| | 输入(命中缓存) | 输入(未命中) | 输出 |
|---|---|---|---|
| deepseek-flash 峰 | $0.006 | $0.30 | $1.20 |
| deepseek-flash 谷 | $0.003 | $0.15 | $0.60 |
| deepseek-v4-pro 峰 | $0.044 | $1.32 | $3.96 |
| deepseek-v4-pro 谷 | $0.022 | $0.66 | $1.98 |

`usd_per_1k_tokens: 0.41` 是 flash **峰时混合估计**（按抽取负载输入:输出 ≈ 88:12 加权），
故意取峰时以免低估云端 COGS；真实账单会因缓存命中与谷时更低。
W5 全语料 30 章 × 2 跑 × ~4 段 ≈ 240 次调用，估算 **$0.05–0.10**——
任务单"抽取 token 只占整书成本零头"这条，实测前先用这张表兜底。

**JSON Output 没开，是刻意的**：DeepSeek 支持 `response_format:{"type":"json_object"}`
（保证合法 JSON，看着正好治 W2 的坏 JSON），但该模式要求输出是 JSON **对象**，
而本管线抽取约定的是 JSON **数组**。要开就得改输出形态——那是尺面/契约变更，
不在 P0"不动尺"的边界内，需拍板。W2 的修复环已能兜住段级坏料，暂不引入。

**两条车道的温度必须一致**：W6 2×2 要的是"只有模型不同"。云端模板钉 0，
本地车道跑对照时也要把 extract 的 temperature 设 0
（`--model-config '{"extract":{"temperature":0}}'`），否则两格不可比。
