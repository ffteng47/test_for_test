# SillyTavern — 架构 / 商业 / 业务流 / 代码流

- 代码基线：`refrence_projects/SillyTavern`（1010 文件）
- License：AGPL-3.0
- 定位：**互动角色扮演前端**，不是小说生产流水线——列入参照系是因为它在"单轮提示词工程 + 生态"上是品类天花板

## 1. 架构

Node.js/Express 服务端（`src/`）+ 浏览器单页前端（`public/`），桌面 Electron 壳可选。

| 层 | 位置 | 职责 |
|----|------|------|
| 多后端接入 | `src/endpoints/` | anthropic / openai(+azure) / google / novelai / horde / minimax / nanogpt …每家一个适配文件 |
| RAG 向量层 | `src/vectors/` | **8 个向量源适配器**：openai / cohere / google / ollama / llamacpp / vllm / nomicai / extras + `embedding.js` 统一抽象 |
| 角色卡 | `src/character-card-parser.js`、`png/`、`charx.js`、`byaf.js` | PNG 内嵌 JSON（V1/V2/V3 卡规）、charx/byaf 容器格式解析 |
| 插件 | `src/plugin-loader.js` + `plugins/` | 服务端插件 |
| 前端核心 | `public/scripts/` | world-info.js（**世界书**）、authors-note.js、macros/、slash-commands/、extensions/、templates/、tokenizers |
| 数据 | `data/` + `default/` | 用户数据目录与默认内容分离，备份内置（backups/） |

## 2. 业务流（单轮生成的提示词组装管线）

```
角色卡（描述/性格/首条/示例对话/系统提示覆盖）
 + 世界书 World Info（关键词触发注入：primary/secondary key、深度、位置、概率、递归扫描）
 + 作者注释 Author's Note（插入深度/频率/角色级）
 + 聊天历史（token 预算内截断，tokenizer 精确计数）
 + 指令模板（instruct template / chat template / prompt-converters 按后端换算）
 → 宏展开（macros）→ 故事字符串组装（story string）
 → 多后端适配器 → 流式生成 → 后处理 → 事件总线（events.js）通知扩展
```

群聊（groups.js）：多角色轮次/次序策略；扩展（extensions）在事件点挂钩改写 prompt 或 UI。

## 3. 代码流关键点

- **后端抽象**：每供应商一个 endpoint 文件，统一 Express 路由 + SSE/流式转发——我方 `plot_engine/llm.py` 若要接多供应商，这是最简参考形态（一层一文件，无框架魔法）
- **向量抽象**：`vectors/embedding.js` 统一接口，8 实现可插拔——R8 远期若做语义记忆，适配器矩阵照此划（本地 ollama/llamacpp 优先，云端可选）
- **World Info 注入算法**（`public/scripts/world-info.js`）：关键词匹配 → 预算内按优先级/位置注入，支持递归（条目内容再触发新关键词）与概率触发——"按需召回"的最成熟实现之一，比全文塞上下文省 token
- **角色卡 V2 规范**：PNG tEXt chunk 内嵌 JSON（ccv3/chara 字段）——资产即文件、可分享，催生了整片角色卡分享社区生态
- **token 预算**：tokenizer 精确计数 + 各槽位（卡/世界书/注释/历史）预算分配——上下文预算工程的经典样本

## 4. 商业

- **无商业化**：纯社区项目，靠维护者与贡献者；变现为零，但**生态即影响力**——角色卡/世界书/扩展的分享社区是品类事实标准
- 与我方关系：价值在技术参照：
  1. 多后端 LLM 抽象（一层一文件）
  2. RAG 向量适配器矩阵（8 源统一接口）
  3. World Info 式"关键词触发 + 预算注入"的按需召回算法
  4. 卡式资产规范（PNG 内嵌）启发我方"作品资产包"的可移植格式设计（远期）
- 场景差异提示：互动 RP 场景与网文连载场景差异大——其"单轮最优"不等于"长链一致"，其无状态会话哲学与连载生产的目标不同；我方状态层（CAS/replay/台账）是面向长链生产的正确投入

## 5. 一句话结论

SillyTavern 是"提示词组装与生态"的教科书：把它当**零件图鉴**（后端抽象、向量适配、World Info、token 预算），不当架构范本。