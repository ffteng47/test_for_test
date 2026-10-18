# L3 批3 测试工作交接包（其他助手用）

- 版本：v1.0（2026-10-18 10:10，主会话产出；tff「接下来的测试工作我分配给其他助手」）
- 状态基线：roadmap v0.43 / 链验 **605 passed** / 语料 `sampling/wpe50ch/`（50 章归档正文）
- 读者：接手 L3 判分测试的助手。**先读本文+主设计文档 §5 批次表再动手。**

## 0. 一句话现状

批1-2（`plot_engine/l3/` 纯派生层）已收口：穿帮"找对子"已由宿主确定性代码完成
（50 章 290 候选在档，`sampling/l3-corpus-v01.json`）；**批3=判分对照测试**——把同一候选集
喂给不同判分端点（本地 32b / 云端 deepseek / NLI），验证归因：精确率跳升=配对瓶颈实锤，
仍塌=模型语义判断实锤（tff 预拍的问题，由本批数据回答）。

## 1. 必读设计方案（按序）

| 文档 | 版本 | 读什么 |
|------|------|--------|
| `docs/l3-consistency-three-layer-design.md` | v0.1 | §2 模块边界、§3 三层结构、§5 施工批次表（批3 定义） |
| `docs/level3-fn-calibration-pack.md` | 活档 | §1.1 **ch50 三锚定义**（回归闸判据）、§7.9+勘误（人核口径与台账）、§7.10（丁批判决+归因三混淆）、§7.11（批1-2 收口读数） |
| `docs/l3-cloud-fallback-eval.md` | v0.1 | 云端混合路由设计、触发条件、成本、探针批 v0.5-cloud 定义 |
| `docs/project-roadmap.md` | v0.43 | v0.38→v0.43 拍板链（画线权全在 tff，任何越权代画=回滚） |
| `docs/commercial/refrence/deep-dive/inkos.md` | - | 审稿降级/引文宿主核验/结算保正典（判分器设计参照） |

## 2. 已就绪的零件（不要重造）

| 零件 | 位置 | 说明 |
|------|------|------|
| 候选生成（零 LLM） | `plot_engine/l3/` 七模块 | 单测 15 例绿；ch50 三锚候选 3/3 |
| 候选集数据 | `sampling/l3-corpus-v01.json` | 50 章 290 候选（A28/B13/C249/D0），带 evidence_refs 行号区间+epistemic_pair 标签 |
| 读数出口 | `sampling/l3_corpus_readout.py` | `--twice`=重算一致性验证；改派生逻辑后必跑 |
| 判分试点（单趟式，四代戳） | `sampling/level3_pilot.py --v042` | 端点覆盖：`L3_BASE_URL/L3_MODEL/L3_API_KEY_ENV/L3_TEMPERATURE/L3_USD_PER_1K` |
| 引文五态核验 | `sampling/quote_verify.py` | 日志清单硬编码，新日志要补进 for 循环 |
| 人核台账（52→39 条判定） | pack §7.9 | 判分读数的 ground truth 对照底本；判定口径§7.9 先读再判 |
| 云端 key | User 级环境变量 `ALEXANDRIA_CLOUD_API_KEY` | tff 已 setx 持久化；进程内取用：`$env:ALEXANDRIA_CLOUD_API_KEY=[System.Environment]::GetEnvironmentVariable('ALEXANDRIA_CLOUD_API_KEY','User')` |

## 3. 工作项（按序执行，W1 是 W2 前置）

### W1 v0.5-cloud 探针（立即，≈$0.01）

**当前故障**：首跑失败 `WinError 10061 目标计算机积极拒绝`——**这是执行环境网络拦截**
（沙箱禁网），不是 deepseek 拒连。处理：在无网络限制的环境跑，或确认代理设置；
`level3-pilot-v05cloud.console.log` 现内容=失败 traceback，成功跑直接覆盖。

命令（PowerShell，逐条）：
```powershell
$env:ALEXANDRIA_CLOUD_API_KEY=[System.Environment]::GetEnvironmentVariable('ALEXANDRIA_CLOUD_API_KEY','User')
$env:PYTHONIOENCODING='utf-8'
$env:L3_BASE_URL='https://api.deepseek.com'; $env:L3_MODEL='deepseek-chat'
$env:L3_API_KEY_ENV='ALEXANDRIA_CLOUD_API_KEY'; $env:L3_TEMPERATURE='0'; $env:L3_USD_PER_1K='0.00041'
.venv\Scripts\python.exe sampling/level3_pilot.py --v042 50 8 12 22 > sampling/level3-pilot-v05cloud.console.log 2>&1
```
- 章节=ch50（回归闸仲裁）+ch08/12/22（32b 失守真域：#09 A/#13 C/#27 B，台账见 pack §7.9）
- 若 `deepseek-chat` 报模型不存在：改 `deepseek-reasoner` 再试（`deepseek.router.json` 里的
  `deepseek-flash` 疑为陈旧名，勿用；型号变更记入戳注）
- 跑完：①把 `level3-pilot-v05cloud.console.log` 补进 `quote_verify.py` 清单跑五态；
  ②日志若是 UTF-16（PowerShell `>` 重定向的坑）先转 UTF-8 无 BOM 再核验；
  ③对照台账判读：锚命中/失守域回补/误报形态，产出对照表（云端 vs 32b vs 14b）

### W2 批3 判分对照试点（主体，归因鉴别实验）

喂**同一候选集**（`l3-corpus-v01.json`）给判分端点，**只判不找**（这是与 W1 单趟式的本质区别）：
- 判定提示词设计：每条候选给 evidence_refs 行号区间（宿主回填原文后送检）+family+detail，
  模型输出三态 `真|误报|存疑` + 一句话理由 + 行号区间引用（区间制=构造性逐字，沿用 v0.4 形态）；
  C 族候选附 epistemic_pair，指示模型「narrator_dialogue=台词 vs 事实多为悬念，降权不定罪」
  （丁批校准口径，pack §7.9 ①②③）
- 三臂对照：本地 32b@11500（$0）/ 云端 deepseek（W1 通了之后）/ NLI 平价对照（可选，
  中文 paraphrase 弱项在册，先跑分布再谈上岗）
- ground truth：OK 章 14 真域+NH/锚台账（§7.9）；新 finding 形态变=回原文人核，口径不变
- 产出：精确率/召回/成本/送检面（候选相关场景帧 vs 全章硬塞）四读数，落 pack §7.12

### W3 C 洪峰分流（零 LLM 可先跑）

C249 候选的 epistemic_pair 分布统计（纯 Python 读 JSON），离线模拟压制规则
（speculation 参与对降权/narrator_dialogue 降权）对候选量的削减曲线——给 W2 判定提示词定参数。

### W4（可选）v0.4.3 混淆清洗

`L3_TEMPERATURE=0` + A/B/C 分族单跑（本地 32b，$0），验证丁批归因混淆①（采样漂移）占比。

## 4. 纪律红线（违反=回滚）

1. 判分器**留 sampling/ 旁路**，不进内核、不接 `validator.py:830`（接线=批5 另案，WP-0 申报）
2. 候选不是定罪：severity 恒 OBS，L3 永不产 HARD
3. 尺面戳纪律：提示词/模型/词表（实体/地点/predicate/触发词）变更=读数变更，必须带戳归档
4. **ch50 锚定义改动须 tff 亲拍**（锚③「叙事自觉」裁量空间在册，pack §7.9 注记）
5. roadmap 单写者纪律：主会话持有，其他会话改动须先批注声明
6. 文档不写任何许可/合规类内容；证据附 `文件:行号`
7. 禁区：`docs/samples/blind-v2paired-key.md` 禁读；`.qoder/`、`frontend/` 他人工作面勿碰

## 5. 验收口径（批3 收口判据）

- ch50 三锚候选经判分后仍为真（锚闸）
- 判分精确率读数对照 v0.4.2 基线（裸 44.8%/宿主压制 54.5%）：**跳升→配对瓶颈实锤
  （模型无辜，架构路线正确）；仍塌→模型语义判断实锤（报 tff 定下步）**
- 送检面下降量级（候选场景帧 tokens vs 全章 2677 均值）
- 链验 605 基线不降；新代码配新测试同步入链
