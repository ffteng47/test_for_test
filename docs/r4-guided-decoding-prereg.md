# R4 后期补充预注册：前置 schema（grammar-constrained / guided decoding）

> 2026-10-15，问题助手调研 + 主线收编。roadmap L4 第 4 条（temp0 失稳正解登记）的**技术底与预注册靶**；
> 不进当前测量靶批，基线定谳后另起一批（一因一批 + 尺戳 bump + 新旧分表）。

## 1. 可行性结论：技术前置已齐

- 现场端点两机实测（只读探活）：@213 Ollama **0.40.2**、本地 **0.40.3**——远超最低要求
  （llama.cpp 侧 PR [#12168](https://github.com/ggml-org/llama.cpp/pull/12168) b4853+ 起
  `response_format.json_schema` 可用；Ollama [v0.5 结构化输出](https://ollama.com/blog/structured-outputs)）。
- Ollama 现行管线直接架在 llama-server 上（PR [#16031](https://github.com/ollama/ollama/pull/16031)），
  `/v1` 的 `response_format` 官方映射代码级确认（openai/openai.go ≈776–804）。
- **最小接入 = 零码**：`plot_engine/llm.py:44` `ModelEndpoint.extra_body` 在 `llm.py:127–129` 直合请求体
  ⇒ router JSON 的 `extract` 角色加 `response_format:{"type":"json_schema",...}` 即生效；
  或服务器侧 `llama-server -j <schema>` 全局约束先行验证。
- schema 单一来源：由 `llm_extract.py:52–66 PAYLOAD_SCHEMA` + `:23 _VALID_TYPES` + `:47 _ID_RE` 派生，禁双源漂移。
- 既有 `constrained_decode` 钩子（`llm_extract.py:479–501`，当前 skip）届时退役/改道。

## 2. 预期管理：grammar 治什么、不治什么

治（语法层确定性，与温度无关）：键名/型别面翻转、enum 外取值、非法 payload 键、语法畸形
——正是 §19–§20/§24 病理中的存在性/键名抖动面。

**不治（社区物证，预注册必须写明）**：
- string 值内复读：[ollama#15502](https://github.com/ollama/ollama/issues/15502)（open）schema 约束下
  自由文本值内循环至预算烧穿、JSON 永不闭合，repeat_penalty 1.5 压不住；grammar 反为环流提供合法跑道。
- 数组级复读：[llama.cpp#29462](https://github.com/ggml-org/llama.cpp/issues/29462)——转换器不设重复上界，
  **schema 必须写死 `maxItems`**（应用侧 `max_items=24` 截断不进 grammar）。
- 残余退化：[coles.codes 实测](https://coles.codes/posts/grammar-constrained-repetition-trap/)、
  [SqueezeBits guided-decoding 报告](https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang)。
- pattern 可能被转换层静默放宽（[llama.cpp#26939](https://github.com/ggml-org/llama.cpp/pull/26939)）
  ⇒ **后置校验三铁律（`llm_extract.py:6–14`）不可因前置 schema 撤除**。

## 3. 预注册靶（instr-v3 批）

grammar on/off 同谱系对照，读数指标：`MALFORMED_PROPOSAL` 率、`finish=length` 率、
段内复读率（`truncated_segment`/keyset 差分，仪器已在 `instr_measure.py`）。
同模型、同夹具戳、双遍闸照旧；尺戳本批 v3.6 → 升档另议。

风险登记：约束增量吞吐成本；`json_schema` 与请求内 `grammar` 互斥（server-common.cpp ≈1302）；
WP-B（llm.py 写集）撞车矩阵 roadmap:147——若走显式字段而非 extra_body 需并批裁定。
