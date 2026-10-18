# SillyTavern 深度审查：业务逻辑流与代码流（逐函数核实版）

- 代码基线：`refrence_projects/SillyTavern`（1010 文件）
- 审查方式：直接读源码，结论附 `文件:行号` 证据
- 形态：**互动角色扮演前端**（Node/Express 服务端 + 浏览器 SPA，Electron 壳可选）——列入参照系因为它是"单轮提示词组装 + 生态"的品类天花板；不是小说生产流水线

## 1. 架构总览

| 层 | 位置 | 内容（读码核实） |
|----|------|------------------|
| 多后端接入 | `src/endpoints/` | anthropic / openai / azure / google / novelai / horde / minimax / nanogpt / openrouter / caption / classify……**一家一个适配文件**，Express 路由 + 流式转发 |
| 向量层 | `src/vectors/` + `src/endpoints/vectors.js` | **21 个向量源**（SOURCES 数组）：transformers(本地) / ollama / llamacpp / vllm / extras / openai / cohere / google(palm/vertexai) / nomicai / togetherai / mistral / webllm / koboldcpp / openrouter / electronhub / chutes / nanogpt / siliconflow / workers_ai；本地索引用 `vectra`（磁盘 LocalIndex） |
| 角色卡 | `src/character-card-parser.js`、`charx.js`、`byaf.js`、`png/` | PNG tEXt chunk 内嵌 JSON（V1/V2/V3 卡规 ccv3），charx/byaf 容器格式 |
| 插件 | `src/plugin-loader.js` + `plugins/` | 服务端插件 |
| 前端核心 | `public/scripts/` | **world-info.js(5605行)** / PromptManager.js(92KB) / tokenizers.js(44KB) / power-user / authors-note / macros / slash-commands / extensions / templates |
| 数据 | `data/` + `default/` + backups | 用户数据目录与默认内容分离，备份内置 |

## 2. 业务逻辑流（单轮生成的提示词组装管线）

```
角色卡（描述/性格/首条/示例对话/系统提示覆盖）
 + 世界书 World Info（关键词触发注入，见 §3.1）
 + 作者注释 Author's Note（插入深度/频率）
 + 聊天历史（token 预算内截断，tokenizer 精确计数）
 + 指令模板（instruct/chat template，prompt-converters 按后端换算）
 → 宏展开（substituteParams）
 → 故事字符串组装（story string）
 → 多后端适配器 → SSE 流式生成
 → 事件总线（eventSource.emit）通知扩展
```

群聊（groups.js）：多角色轮次/次序策略；扩展在事件点挂钩可改写扫描状态、预算、已激活文本。

## 3. 代码流关键实现（逐函数证据）

### 3.1 世界书扫描主循环（`public/scripts/world-info.js:4709 checkWorldInfo`）

**这是"按需召回"最成熟的实现之一**，5605 行文件的核心。完整状态机：

```
checkWorldInfo(chat, maxContext, isDryRun, globalScanData)
 ├─ WorldInfoBuffer(chat, globalScanData)（:199）
 │    #depthBuffer（按消息深度索引）/ #recurseBuffer（递归扫描追加）/
 │    #injectBuffer（扩展注入且 scan=true 的提示）/ #globalScanData（persona/角色描述等聊天外扫描源）
 ├─ 预算：budget = round(world_info_budget% × maxContext)，world_info_budget_cap>0 时取 cap（:4733-4740）
 ├─ timedEffects = WorldInfoTimedEffects(chat, sortedEntries)：sticky/cooldown/delay 三种时态效果
 ├─ delayUntilRecursion 分级（true→1 级，数字→N 级），分级解锁
 └─ while (scanState) 扫描循环（scan_state: INITIAL → RECURSION / MIN_ACTIVATIONS → NONE）
```

**每个条目的激活判定链**（按代码顺序，任一不过即 continue）：

1. `entry.disable` / 已在 failedProbabilityChecks / 已激活 → 跳过
2. `triggers` 生成类型过滤器（当前触发方式不在列表→跳过）
3. `characterFilter`：按角色名/tags 白黑名单（isExclude 翻转）
4. 时态：`delay` 抑制、`cooldown` 抑制（sticky 优先）
5. 递归门禁：非递归轮 `delayUntilRecursion` 抑制；递归轮按 level 解锁；`excludeRecursion` 在递归轮抑制
6. 装饰器短路：`@@activate` 直接激活 / `@@dont_activate` 直接抑制 / 外部激活（externalActivations）
7. `constant: true` → 常驻激活；`sticky` 生效中 → 激活
8. **主关键词**：`buffer.matchKeys(textToScan, key, entry)`（大小写/全词匹配由全局设置控制）
9. **次关键词**（selective）：`selectiveLogic` 四态——AND_ANY / AND_ALL / NOT_ANY / NOT_ALL（:4930-4968，含 PR#1356 修复注释）
10. **概率触发**（:5041）：`Math.random()*100 <= entry.probability`；sticky 免重掷；失败入 failedProbabilityChecks（本轮不再考虑）
11. 宏展开 `substituteParams(entry.content)`
12. **预算闸**：`!entry.ignoreBudget && textToScanTokens + getTokenCountAsync(newContent) >= budget` → 记 `token_budget_overflowed`（可配 toastr 告警），**超预算即停**，已激活的不回吐

**递归与保底**：

- 本轮新激活条目的内容进入 recurseBuffer → `scan_state.RECURSION` 再扫（条目内容再触发新关键词）；`preventRecursion` 条目不喂递归；`world_info_max_recursion_steps` 封顶
- `world_info_min_activations > 0`：激活数不足则加深扫描深度（`min_activations_depth_max` 护栏），**保底召回**
- 组评分：`world_info_use_group_scoring` / inclusion group 内按权重掷签选一条（:5453 `Math.random()*totalWeight`）

**事件挂钩**（:5150-5180）：每轮结束 `eventSource.emit(WORLDINFO_SCAN_DONE, args)`——args 的 `state.next / activated.text / recursionDelay / budget` **可被监听器改写**，扩展能在扫描中途改状态机走向。

**注入定位**（:5186 起 BUILDING PROMPT）：激活条目按 insertion order 排序后（999→1 unshift），经 `getRegexedString`（正则后处理）按 `position` 分流——before/after（角色卡前后）/ EMTop / EMBottom（示例消息锚）/ ANTop / ANBottom（作者注释夹心）/ **atDepth**（按 depth+role 分组合并插入聊天历史指定深度）/ outlet（命名出口，供扩展定向消费）。

### 3.2 向量适配器矩阵（`src/endpoints/vectors.js`）

- `SOURCES` 数组 21 源；`getVector(source, settings, text, isQuery, directories)` **一个 switch 分发**（:53-100）
- OpenAI 兼容源复用同一实现：togetherai/mistral/electronhub/openrouter/chutes/nanogpt/siliconflow/workers_ai 全部 `getOpenAIVector(text, source, …)`（source 只决定 baseURL/key 读取）
- 本地源一等公民：`transformers`（server 内 transformers.js，feature-extraction pipeline，mean pooling+normalize）、`ollama`、`llamacpp`、`vllm`
- 批量：`getBatchVector` 固定 batchSize=10 分批；本地索引 `vectra`（磁盘 LocalIndex，per-user 目录）
- 新增源的步骤注释原话："Don't forget to add new sources to the SOURCES array"——**适配器注册是显式清单，无框架魔法**

### 3.3 tokenizer 精确计数（`public/scripts/tokenizers.js`）

- 按模型族选 tokenizer：GPT2 / OpenAI / LLAMA / MISTRAL / YI / LLAMA3 / GEMMA / JAMBA / **QWEN2** / COMMAND_R / COMMAND_A / NEMO / **DEEPSEEK**
- tokenizer JSON 远端下载（TOKENIZER_URLS）+ 本地缓存；不支持时降级估算并提示
- `getTokenCountAsync` 是全管线预算判断（WI 预算、历史截断、槽位分配）的统一量具——**token 预算工程的样本：先精确计数，再谈分配**

### 3.4 角色卡资产格式（`src/character-card-parser.js`）

PNG tEXt chunk 内嵌 JSON（ccv3/chara 字段）——**资产即文件、可分享**，催生了整片角色卡分享社区生态；charx/byaf 是容器格式变体。

### 3.5 多后端接入（`src/endpoints/*.js`）

一家一个文件：Express router + 鉴权头拼装 + SSE/流式转发 + 错误归一化。无抽象基类、无框架魔法——**"一层一文件"的最简参考形态**。

## 4. 针对我方当前问题/困境的解决方案对照

| 我方困境/在途事 | SillyTavern 方案 | 证据位置 | 可移植性 |
|-----------------|------------------|----------|----------|
| **llm.py 多供应商扩展** | 一家一文件的 endpoint 适配器，Express 路由+SSE 转发，无框架魔法 | `src/endpoints/` | 高——我方接多供应商时照此划，避免抽象过度 |
| **远期语义记忆（R8 之后）** | 双层召回：关键词触发（WI 全状态机）+ 向量检索（21 源矩阵，本地源优先）；预算制注入（%+cap、ignoreBudget、超支即停） | `world-info.js:4709` / `endpoints/vectors.js` | 中高——其"关键词+预算"层离线可复刻；向量层选型矩阵直接可用（ollama/llamacpp 本地优先） |
| **上下文预算工程** | 每槽位独立预算（WI 占 context 百分比+cap）；token 精确计数做统一量具；超支告警可配 | `world-info.js:4733` / `tokenizers.js` | 高——我方 contextPackage 预算分配可引入"槽位预算+精确计数+超支留痕"三件套 |
| **召回保底** | min_activations：激活不足自动加深扫描 | `world-info.js:5120` 区域 | 中——我方检索"零命中静默"问题的对照解 |
| **扩展性/事件钩子** | WORLDINFO_SCAN_DONE 的 args 可变——扩展能改状态机走向 | `world-info.js:5150` | 中——我方管线事件目前是只读通知 |
| **作品资产包（远期）** | PNG 内嵌 JSON：资产即文件、可分享 | `character-card-parser.js` | 低（远期），"单文件可移植资产包"的灵感 |
| **时态效果** | sticky（激活后保持 N 轮）/ cooldown（触发后冷却）/ delay（延迟生效） | `WorldInfoTimedEffects` | 中——伏笔/设定"召回节奏"的可借概念 |

## 5. 与我方架构的异同（诚实对照）

| 维度 | SillyTavern | 我方 plot_engine |
|------|-------------|------------------|
| 场景 | 单轮互动 RP（无状态会话哲学） | 长链连载生产（状态是主投入） |
| 一致性保障 | 无（靠用户维护世界书） | CAS/replay/台账/H1–H8 |
| 召回 | 关键词触发+预算注入+递归+时态 | 无（ContextPackage 静态组装） |
| 多后端 | 一层一文件适配器 | llm.py 单供应商 |
| 量具 | tokenizer 精确计数全管线统一 | 字数为纲（token 计数未入管线） |

**单轮最优 ≠ 长链一致**：其无状态哲学与连载生产目标不同，我方的状态层投入方向不变；它对我们的是**零件图鉴**价值，不是架构范本。

## 6. 一句话结论

SillyTavern 的证明题是"提示词组装与生态"：World Info 的"关键词触发 + 预算注入 + 递归 + 时态效果 + 概率"五件套是按需召回的最成熟实现，21 源向量适配器矩阵与一层一文件后端抽象是我方多供应商与语义记忆两件远期事的直接选型参考；其生态（角色卡/世界书分享社区）证明"资产格式可移植"本身就是护城河。