# 小说有声书流水线 · 使用 Wiki

覆盖到 2026-10-08 的完整功能。服务地址 `http://192.168.31.213:4200`（后端直接托管前端 dist，改前端只需覆盖 `alexandria/studio/`，不用重启；改后端必须重启）。

---

## 0. 三十秒心智模型

一本书从原文到成品走五步，页面顶部就是这五步：

```
01 导入拆解 → 02 剧本工作台 → 03 角色与声音 → 04 生成车间 → 05 母带导出
                        ↑
                   ✚ 声音实验室（造声/试听工作台）
```

每一段台词由**三个互相独立的维度**决定，混淆这三者是 90% 的「声音不对」的根因：

| 维度 | 决定什么 | 在哪里设 |
|---|---|---|
| **音色来源 type** | 这个人的「嗓子」从哪来 | voice_config：`design` / `clone` / `custom` |
| **出声引擎 engine** | 用哪个模型发音 | 「角色与声音」→ 出声引擎 |
| **段级情感 instruct** | 这一句怎么说 | 「剧本工作台」每段的 instruct |

---

## 1. 三个维度的对应关系（核心表）

### 1.1 type = 嗓子从哪来

| type | 含义 | 批量生产的真实行为 | 绑定处提示颜色 |
|---|---|---|---|
| `clone` | 参考音频克隆 | 每段都用**同一个** ref_audio 出声 → 音色稳定 = 试听那个声音 | 🟢 绿 |
| `custom` | 模型自带具名说话人 | 每段一致，音色由模型内置（如 Ryan），ref_audio 不参与 | 🟢 绿 |
| `design` | 只有一段**文字描述** | **每句重新抽一次音色**，30 句出 30 个不太一样的「他」 | 🔴 红 |
| 其它/未知 | —— | 无法保证与试听一致 | 🔴 红 |

> `design` 是「造一个嗓子」的工序，不是「用这个嗓子念全书」的工序。
> 后端 `generate_personas.py` 的成功路径就是这样收口的：VoiceDesign 抽一条预览 → 把预览当 ref_audio → **写成 `type: clone`**。只有预览合成失败时才会退回留下 `type: design`（只带描述、没有样本）。
> 所以看到红色 `design` 提示 = 上一次造声没落地，去声音实验室重跑一条并点「选用」。

### 1.2 engine + 情感载体 emo

情感词表只有一份：`app/emotion_map.py`，16 个规范中文句，前端通过 `GET /api/emotions` 读，不允许第二套文案。

| 引擎 | key | 需要参考音频 | 情感载体 emo | 段级 instruct 怎么被消化 |
|---|---|---|---|---|
| Qwen3-TTS（进程内） | `qwen`/空 | 视 type | `verbatim` | 原样送进模型 |
| CosyVoice2 :7861 | `cosy` | ✅ | `instruct2` | 包成「用…的语气说话」；**非中文直接丢弃**；通道为「纯克隆」时不读情感 |
| IndexTTS-2 :7862 | `index` | ✅ | `emo_vector` | sidecar 自己折成 8 维向量 `[happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]` |
| Kokoro :7863 | `kokoro` | ❌ | `none` | **没有情感通道，instruct 一律忽略**（兜底朗读） |

新增一个引擎 = 一个 sidecar + `alexandria/app/engines.py` 的 `ENGINES` 里一行（必须声明合法 `emo`，自检会断言）。前端模型/引擎下拉全部来自接口，零改动。

### 1.3 mode = CosyVoice2 的出声通道

voice_config 里的 `mode` 字段只有两个值：`zero_shot`（纯克隆）/ `instruct`（情感指令）。
**它只由显式选择决定**（在「角色与声音」的「出声通道」下拉，或在声音实验室选用时由服务端回传），不再由「这句有没有 instruct」自动翻转——那曾是「30 字念出 20 秒乱音」的直接原因。

---

## 2. 逐页功能说明

### 01 导入拆解 `/import`

- `＋ 上传书稿`：接受 `.txt` / `.epub`（DOCX 未接通）。上传成功后**自动触发**整本标注，不用手点。
- `⟳ 标注剧本` → `/api/generate_script`：LLM 把原文切成段、判说话人、给每段写 instruct。busy 时禁用。
- `✓ 复查` → `/api/review_script`：字级比对原文与标注稿，产出 一致率 / 漏字 / 增字（左侧连续性条）。
- 章节树里的「已生成 / 已标注 / 待处理」是阶段标记；「原文回链」的段落号当前是展示值，不要当准。

### 02 剧本工作台 `/script`

统计条：段 / 已生成 / 失败 / 待生成 / **兜底** / 已锁定。

- `◐ N 兜底`：这 N 段没有可用角色音色，由 Kokoro 顶班，**不是角色本身的声音**。点开看会标「Kokoro 兜底 · 非角色音色」。
- 展开某段：`instruct` 输入框决定这句的语气。提示语「TTS 每句独立合成——上下文要写全」。
- 右侧检查器：说话人 / 类型 / **出声引擎** / instruct / 台词 / 音频版本。
  - `⌾ 保存修改` → `/api/chunks/{index}`
  - `▷ 试听本句`：只播**已生成的文件**，没有音频时按钮禁用
  - `↻ 重生成` → `/api/chunks/{index}/generate`
  - `▶ 批量生成` → `/api/generate_batch`（2026-10-12 改）：点击**先弹确认**（列出未完成段数 = pending+error），勾「以后不再弹出此确认」记在 localStorage `novel.skipGenConfirm`，此后直接启动。**运行中按钮变「⏹ 停止生成」** → `POST /api/cancel_audio`：任务在跑就置 cancel 标志（当前段出完才停，已生成音频保留，再点批量只补未做的）；空闲时该端点把卡在 `generating` 的段复位成 `pending`。
  - **刷新页面后仍能停（2026-10-13）**：`busy` 原本是纯前端内存态，批量生成跑一半刷新一下按钮就变回「▶ 批量生成」，看着像没法中止。现在进入工作台会跑 `resyncRunning()`（`frontend/src/api/actions.js`）：逐个查后端 `/api/status/{audio,persona,script,review}`，凡是 `running:true` 的任务自动恢复进度轮询，按钮重新变「⏹ 停止生成」。状态以**后端**为准，前端只是显示器。
- 章节切换按钮当前是装饰（无 handler）。
- QC 框：`音频回听一致 CER x%`（ASR 回听 vs 台词）、`原文无损`（字级）、`转录一致/疑似漏字`。

### 03 角色与声音 `/cast`

左列人物表 → 中列绑定 → 右列 Voice Profile 库。

- `导入参考音频`：上传 → **SenseVoice ASR 自动转写**出 ref_text 并弹出确认框（可改），情感建议一并带出。取消则只入库不绑定。
- `⚡ 批量自动设计` → `/api/generate_personas`：跑 `generate_personas.py` 子进程（会先卸载 TTS 引擎腾显存），逐个人物 LLM 写描述 → VoiceDesign 抽预览 → 固化成 `clone` 参考并写进 voice_config。进度在生成车间的「音色」任务里看（任务队列里的「音色设计」就是这个按钮，同一个 persona 任务，不是两个功能）。
  - **点击先弹二层窗口选范围**（2026-10-12）：`仅设计未绑定角色（安全）` = 后端 `new_only:true` → 脚本 `--new-only`，只补 voice_config 里没有的角色；`全部人物重新设计` = 全量，**会覆盖所有已绑定音色**；或取消。有定稿音色的书（如第1册）只走「仅未绑定」或干脆别点——补新角色一律走实验室造声 + `选用`，或造完重跑 `ebook_import.py --templates-only` 自动绑。
  - **⚠ 模糊别名归并（实测代码）**：`_resolve_to_canonical` 先做归一化全等，再做**子串包含**（`xiaoman` 是 `xiaoman2` 的子串 → 必被 alias），最后才是 Jaccard≥阈值。刻意拉开的两个近似名（如 `XIAOMAN`/`XIAOMAN2`）**会被合并成同一个声音**，0.8 阈值拦不住子串这步。全量模式风险最大，仅未绑定模式同样会归并新角色。
- **声音绑定**：下拉选音色行，下方彩色提示（本次新增）说明「保存后每句实际会发出什么声音」：
  - 🟢 绿 = 与试听一致（clone/custom，说明音色锁在哪、情绪从哪来）
  - 🔴 红 = 会跑偏（design 逐句重抽 / Kokoro 兜底 / clone 缺参考音频 / 未知类型）
- **出声引擎**：`自动（有可用音色→Qwen3-TTS，缺音色→Kokoro 兜底）` 或显式选 cosy/index/kokoro。选 cosy/index 时出现：
  - **出声通道**：纯克隆（音色语气全照参考音频，不读段级情感）/ 情感指令（照参考音频的音色 + 每段 instruct）
  - **ref_text** 输入框：纯克隆必填，逐字照抄参考音频里说的那句。留空 → 🔴 警告（批量会直接失败）
  - 情感载体说明（例如 cosy = 自动包成「用…的语气说话」；kokoro = ⚠ 无情感通道）
- `试听当前绑定`：播参考样本（本次新增：声音实验室也能直接播上传的参考音频）。
- `保存绑定`：只写配置，**已生成的音频不会自动变**。
- `↻ 重生成该角色台词（N 段）`：让新声音真正作用到已有段落。
- 换声不必重标全书：别名归并表让「他 / 少爷 / 晚晚」解析到同一 voice_id。

### ✚ 声音实验室 `/voice-lab`

造声与试听工作台，三种方法（页签）：

| 方法 | 需要什么 | 产出 |
|---|---|---|
| **描述造声 design** | 一段音色描述（预置 7 模板 + 服务器模板库，如「老者 · 沙哑」） | 一次性抽嗓子。**性别/年龄不由描述保证**：同描述换 seed 实测基频 115Hz（老年男）↔ 214Hz（近女/童声） |
| **参考克隆 clone** | 参考音频（可上传，自动 ASR 转写 ref_text） | 音色**完全**由录音决定。想要老人声就得有老人录音，写指令改不了年龄。**Qwen3-TTS 也能克隆**：`Qwen3-TTS Base 1.7B/0.6B 克隆`（`base17`/`base06`，零样本），生产 8 个声线走的就是「VoiceDesign 造嗓 → preview 当 ref_audio → Base 克隆」两段式 |
| **固定音色 custom** | 模型自带说话人 + instruct | 稳定但不可扮角 |

- 多模型连刷：勾选多个模型，一次请求逐个生成，左侧进度 `doneCount/总数`，冷加载最坏约 3 分钟（超时按 300s 设）。
- **引擎下拉框里没有 Qwen 不是不能克隆**：`/api/engines` 只列 sidecar（cosy/index/kokoro 三个常驻服务），Qwen3-TTS 是主进程内加载，只出现在「模型」列表里。早期模型名只写「Base 1.7B 克隆」看不出归属，2026-10-11 统一改名带 `Qwen3-TTS` 前缀（安装器 `deploy/patches/relabel_qwen_models.py`，幂等，改 `app/voice_lab.py` 的 label，需重启生效）。
- **情绪指令 / instruct 字段只在对应载体生效**：CosyVoice2 的「情感指令」模型才会读，且改成「改语气，不改年龄音色」。
- **音色/情绪模板库**（2026-10-12）：描述与指令都可 `＋ 存为模板`（POST /api/voice_templates，落服务器 `alexandria/voice_templates/*.json`，跨书共享）；下拉里「📚」组即库内条目，电子书导入时 `voices/` 里的角色音色说明会自动入库。当前描述可直接改了再生成，库文件改名/直删要上服务器动。
- 结果行显示：**标题**（默认 = 模型名，可 ✎ 改成自定义名，见下）、生成耗时/音频时长、**seed**（随机也会显示真实数字，见 §3）、目标角色、试听音频、`选用`。
- **✎ 改标题（2026-10-13）**：结果行/历史行的模型名旁有 ✎ 按钮，`window.prompt` 输入自定义标题（如把「Qwen3-TTS VoiceDesign 1.7B」改成「冒险岛-小满」），存进记录的 `name` 字段（≤60 字，超长 400），留空则恢复显示模型名。后端字段由幂等安装器 `deploy/patches/add_lab_record_name.py` 补（改 `app/voice_lab.py` 的 `RecordUpdate` + update 处理器，**需重启生效**），走的是现成接口 `POST /api/voice_lab/record/update`。
- `选用`：把这条结果写成**当前下拉框选中角色**的 voice_config —— 早期版本会优先用记录上那个「生成时」的角色标签，导致点完 `选用` 别的角色被改、看着的角色没动（已修，按钮文案 `选用 → X` 现在就是实际写入对象）。注意它会**固化成 `type: clone`**（描述造声则把预览音频当 ref_audio），并带上服务端回传的实际引擎与通道。绑定后旧音频仍需去「角色与声音」重生成。
  - **已占用红锁（2026-10-12）**：某条试听结果一旦被某角色选用，它的按钮变**红底**并回显「已选用 → 角色名」；此后切换目标角色不会改变该显示，红色期间点它只会**解除占用标记**（红→白，弹提示，原角色绑定不动），不会被悄悄选给别的角色；解除后再点才按当前目标角色写入，绑定成功立即重新变红。判定依据是 voice_config 的 `ref_audio` 路径与该条结果一致（design 看预览文件、clone 看参考样本、custom 看说话人名）。注意红锁只覆盖「实验室台账记录 ∧ 被角色绑定」的声音：design 类型角色和从 `clone_voices/` 导入的绑定不在台账里，永远显白。
  - **串绑确认（2026-10-13）**：一条记录生成时带着当时的目标角色（`speaker`）。若你切换到的当前角色 ≠ 记录上的 `speaker`，点 `选用` 会先弹确认「这条声音是给『××』造的，确定绑给『××』？」，取消即不动。防的就是历史那类事故：给 LANDLADY/CROWD 造的声音被顺手绑进 PIKE/XIAOMAN。
- 历史区：倒序分页（每页 20，可翻页 + 按角色筛），清单在 `designed_voices/voice_lab_manifest.json`。每条可直接：
  - `标注`：按音频仓库的词表打标（情绪/强度/感情/情节/音色质感/语速/音高/评级/备注，见 §2◆），写进记录的 `tags`；
  - 改文本：直接编辑那段试听文本（`record/update`）；
  - `存仓库`：把这条送进音频仓库（入库即实测时长/字每秒/基频）。仓库条目的 `role` 取这条记录的 `speaker`，记录是空的就用你当前选中的目标角色兜底；
  - `删除`：默认只删记录、保留 wav（它可能正被当参考样本用），勾上「删除时连音频」才删 `previews/` 下的文件。**仓库与实验室共享文件（引用式，不是拷贝）**：purge 删掉文件后，仓库里引用它的行不会消失，但会标 `missing`、再也取不出声；不勾 purge 则记录、文件、仓库行都互不相干。「选用/取消」只写 voice_config，不动文件也不动仓库。

### ◆ 音频仓库 `/vault`

「确认过的好声音」+ 量化标签，让后续 LLM 不用重新造声，直接按标签拣现成声音。

| 维度 | 类型 | 取值 | 怎么来的 |
|---|---|---|---|
| 人物 `role` | 单列（非标签） | voice_config 的 key，如 `NARRATOR` | 入库来源或手填 |
| 情绪 `emotion` | 枚举 | `emotion_map.py` 的 16 个规范值 | 人工；前端显示中文名 |
| 情绪强度 `intensity` | 0..1 | — | 人工 |
| 感情对象 `bond` | 枚举 | 无/亲情/爱情/友情/敌意/怜悯/愧疚/敬畏/思念 | 人工 |
| 冷热 `warmth` | -1..1 | — | 人工 |
| 情节 `scene` | 多选枚举 | 旁白铺陈/日常对话/内心独白/争执冲突/紧张追逐/危险对峙/悬疑铺垫/温柔安慰/悲伤告别/搞笑调侃/宣告决策 | 人工 |
| 音色质感 `timbre` | 多选枚举 | 清亮/低沉/沙哑/气声/颤抖/圆润/尖细/干冷/厚实 | 人工 |
| 语速 `pace` | 0..1 | 字每秒按 **2.0–7.5** 归一化 | **入库实测**，可人工覆盖 |
| 音高 `pitch` | 0..1 | 中位基频按 **70–330Hz** 归一化 | **入库实测**，可人工覆盖 |
| 人工评级 `rating` | 0..5 整数 | 拣选时第一排序键 | 人工 |
| 备注 `note` | ≤200 字 | 不进向量 | 人工 |

- **量化双出口**（同一份标签，两个消费者）：`to_vector()` → **52 维定长向量**（枚举 one-hot、情绪另加效价/唤醒两维、数值维原样），适合 embedding / 最近邻 / 打分模型；`as_prompt()` → 一句中文（`情绪=anger(效价-0.6/唤醒+0.9)，情节=争执冲突，语速=0.82`），适合直接塞进 LLM 提示词。
- 接口：`/api/vault/schema`（词表说明书，前端标签面板就是它渲染的）、`/api/vault/add`、`/api/vault/list`（分页 + role/emotion/bond/scene/timbre/评级/语速音高区间/全文筛）、`/api/vault/pick`（给 LLM 的出口：按标签拣 + 带回向量与 layout）、`/api/vault/update`、`DELETE /api/vault/{id}?purge=`。页面上的 `按当前筛选试拣` 就是 `/pick` 的实盘预览。
- 三种入库来源：`lab`（实验室记录）、`chunk`（台词段序号，取已生成的那段音频）、`file`（工作区内相对路径）。**仓库只记路径，不复制文件**，所以外部素材要先合法地放进工作区（例如 `clone_voices/`），再按 `file` 入库 —— 版权素材不提供下载或抓取。
- `tags` 是**全量快照**语义：update 时没传的维度即视为清掉（前端标签面板本来就带全量）。`purge` 删文件只允许 `designed_voices/`、`clone_voices/` 内的产物，越界路径直接拒绝。
- 数据落 `novelaudio.db` 的 `voice_samples` 表（按 `project_id` 分书），`UNIQUE(project_id, kind, src_id, path)` 让同源重复入库即覆盖，不产生重复行。
- 加一维 = 在 `app/tag_vocab.py` 的 `FACETS` 里加一行；枚举值**只增不删、不改顺序**（改了历史向量就作废）。跑 `../venv/bin/python tag_vocab.py` 自检。

**role（人物）这件事**

- role 存的是 **voice_config 的 key**（本书是 `NARRATOR / XIAOMAN / TONGSHU / XIAOMAN2 / MAMA / CROWD / YUNWEN / GIRL` 这种大写拼音），**不是中文名**。页面上「旁白」「小满」是前端把 key 翻译出来的显示名（`speakerKey('NARRATOR') → 'narrator' → SPEAKERS.narrator.name`），仓库查的是库里的原始值 —— 所以在筛选框输「旁白」永远 0 条，要输 `NARRATOR`。入库卡片下面那行 `NARRATOR=旁白 · XIAOMAN=小满 …` 就是这张对照表，行内「人物」框也带同一份补全。
- role 的三个来源：`lab` 取实验室记录的 `speaker`（= 生成时下拉框选的目标角色；记录没带就用当前选中的角色兜底）；`chunk` 取 `chunks.json` 该段的 `speaker`（LLM 标注结果）；`file` 只能手填。入库后行内改 → `POST /api/vault/update` 全量覆盖这一列。
- **role 不需要「创建」**：它在两处自然产生 —— ①标注阶段给段落写出 `speaker`（01/02 页）；②「角色与声音」给这个 speaker 绑音色，写进 `voice_config.json`，此后它才可筛可绑。想加新角色就走这两步；`绑定到 X` 只接受已存在的 key，填了陌生 key 会明确报错并列出可用值（免得写出没人引用的幽灵音色）。
- **两个「人物」框不是一回事**：页顶那个是**查询条件**，行内每条目自己那个才是这条 `voice_samples.role`。`绑定 → X` 按钮上写的 X 取的是**本行**的值（早期版本取的是筛选框，所以会出现「我把筛选改成 NARRATOR，按钮还写着 CROWD」）；若本行为空而筛选框有值，绑定会先把这个 role 落库再绑，不留不一致的条目。
- **写操作一律过一层最短 600ms 的蒙版**（入库实测 / 保存 / 绑定 / 删除）：接口往返只有十几毫秒，中间态和成功提示人眼根本看不见，所以给了转圈 + 一句具体在干什么，收起后才弹成功 toast。

**风格字段各管什么（`tts.py` 的分工，别再混用）**

一个角色的「声音」由 4 个字段决定，不同出声路径读的不是同一个：

| 字段 | 谁读它 | 语义 |
|---|---|---|
| `ref_audio` + `ref_text` | type=clone 的全部路径 | **音色本体**。像不像这口声音，100% 由它决定，文字描述改不了年龄/音质 |
| `character_style` | 进程内 Qwen 的 clone（`tts.py:1185/1200`）与 lora（`:917`）；批量 custom/lora | **角色级长描述**，和段级 instruct 拼一句后进 `instruct_ids`，只影响语气/腔调。sidecar（cosy/index/kokoro）**故意不读**（`:1104`） |
| `default_style` | 进程内 Qwen 的 custom（`:1131`）；lora 的兜底 | 同上，但**段级 instruct 非空时整条被忽略** |
| `description` | type=design（`:812`） | 造声提示词，只决定新生成的音色长什么样，不进入 clone 路径 |

- 规矩：**仓库的量化标签不进角色配置**。绑定一条仓库音频 = 只写 `ref_audio`/`ref_text`（+ 出处），`character_style` 留空。标签要发挥作用，走段级 `instruct`（由 `as_prompt()` 出那句中文），一句一句地给，不要塞成角色永久风格。
- 已知缺口：`_local_batch_clone`（`tts.py:1443`）调 `generate_voice_clone` 时只送 `text` 和 `voice_clone_prompt`，**段级 `instruct` 和 `character_style` 都没进 `instruct_ids`** —— 所以「标了情绪、批量重跑听不出来」，而单段重生成（`generate_voice`）会生效。两条路径行为不一致，属于后端缺陷，要动 `tts.py` 得走安装器。

**数值标签能不能当调音旋钮用？不能**

`pace` / `pitch` 是**对已有音频的实测归一化**（`tag_vocab.py:72/77`：字每秒按 2.0–7.5、中位基频按 70–330Hz 线性压到 0..1），方向只有「音频 → 数字」。手改这两个数只改标签（而且再保存还会被重新实测覆盖），不会让任何音频变快变高。想真的调语速/音高只有三条路：① 换/重录 `ref_audio`（音色与语速基线在参考音频里）；② 段级 `instruct` 用自然语言写「语速放慢、音调压低」（模型自由发挥，只能大致带）；③ 后期变速变调（ffmpeg `atempo`/`asetrate` 或 rubberband）—— **本工程的后期管线目前只有导出环节的响度归一（见 §05），没有变速变调**，要精确控制得再在导出环节加一条。


### 04 生成车间 `/studio`

- 队列卡片：GPU 显存 / 当前任务 / 待生成段 / 失败段（自动重试 ≤3 次后转人工）。
- 任务行：类型（TTS/标注/质检/音色/导出）、进度、ETA、状态、`取消`（仅 running 时出现）。
- `⏸ 暂停队列`：**前端状态**，实现是调 `/api/cancel_audio`；服务端没有真正的 pause，恢复即重新起批。
- `重试全部失败段` → 对 `status==='error'` 的段跑 `/api/generate_batch`。
- 章节矩阵行操作：已标注→`生成`；已生成→`复审`（跳回剧本台）；否则`待标注`。
- 断点续跑靠幂等命名 `[index][hash][model][voice][fail]`，重启会回收 stale 任务。
- 溯源：每段记录真正出声的引擎（`voice_engine`），Kokoro 兜底必须显式留痕，禁止静默冒充角色音色。

### 05 母带导出 `/export`

- 格式：M4B（章节跳转）/ MP3（单文件）/ WAV（**后端未接通，点了只提示**）。
- 码率 64k/96k/128k/192k、封面自动/不嵌入、章节多选 —— 但**这三项目前不传给后端**，后端按默认处理；只有「哪些章节」的勾选在 UI 上限制为「音频已生成」的章节。
- `合并 MP3` → `/api/merge`；`导出 M4B` → `/api/merge_m4b`。**M4B 要带章节就传 `per_chunk_chapters: true`**（默认 `false` 走标题检测分组，导出不带章节标记）。
- **导出时会自动裁段首死气**（`app/tts.py` 的 `trim_leading_silence`，安装器 `deploy/patches/add_leading_silence_trim.py`）：每段开头那截 TTS 自带的随机静音（实测中位 437 ms）收窄到 `LEAD_SILENCE_KEEP_MS = 80`。**同一本书成片因此比不裁短约 7%**，段间停顿从 ≈1.0 s 回到 ≈0.67 s。裁剪点在 `combine_audio_with_pauses` 与 `compute_timeline` 两处（章节偏移累加的是裁剪后的长度，所以章节轴跟着一起缩，不会漂）。不想裁：常量改 `None` + 重启。
- **两个出口现在都会自动做母带后期**（两遍 loudnorm + 真峰值限制，−16 LUFS ±1.0 / ≤ −1.5 dBTP）。阈值与判定唯一真源：`backend/master_audio.py`；接入方式：安装器 `deploy/patches/add_export_loudnorm.py`（幂等，`PATCHED` 后需重启主服务才生效）。
- **每次导出落一份 `delivery_report.json`**（写在**成品自己的真实目录** `projects/<slug>/`，与 M4B/MP3 同级，换书不覆盖；`书` 字段就是 slug）：全项实测 LUFS / dBTP / RMS / 时长 / 章节数 / 体积 / 首尾静默 + 逐项 PASS/FAIL + `通过`。**判定看的是最终成品**——归一那步只能量中间 WAV，所以导出末尾还有一次 `成品机检`（日志打 `成品机检 OK：… LUFS / … dBTP / … 章`，或 `!! 成品机检不通过（不要交付）`）。**归一失败、机检跑不起来都会写成 `通过=false`，所以听不到警告不等于合格，交付前看这个 json。**
- **机检闸门（M1）**：`GET /api/delivery_report` 把上面那份 json 交给前端；`/export` 的 LIBRARY 顶上一栏显示实测数与逐项判定，`通过=false` 时栏内红字、成品行红字、**下载按钮禁用**（仍可试听）。判据只有两层，都写在 `backend/master_audio.py`：`gate()` 客户口径（响度、真峰值）能拦交付，`channel_gate()` 渠道口径（RMS / 峰值 / 体积）只报数不拦。命令行单验：`backend/master_audio.py --inspect 成品.m4b`（不合格非 0 退出）。安装器 `deploy/patches/add_delivery_gate.py`（幂等，备份 `app.py.bak_pre_gate`），改了 `app.py`，**需重启主服务生效**。
- **`root_dir` 是软链根，不是书目录**：`alexandria/` 下的 `audiobook.m4b`、`cloned_audiobook.mp3` 等是指向 `projects/<slug>/` 的软链，换书＝重指这些链接（`switch` 打的是「换链 N 项」）。凡是往「书自己的文件」里写东西的代码，都要对**成品路径**取 `os.path.realpath()`，直接拼 `root_dir` 会落到共享根上。
- 导出前检查条（有数据才显示）：原文字级一致率（≥0.999 打勾）、QC pass/retry/unchecked 计数、N 段尚无音频将跳过、N 段待复核。
- 成品列表探测服务器真实存在的整书产物：`播放`（播时按钮变 `■ 停止`，按 `store.transport.url` 逐行判定）/ `下载`（`/api/audiobook`）/ `删除`（仅本地列表）。

### 底栏播放器 TransportBar

跟随选中段：播放/停止、说话人、位置、可点波形、`◎ 审听`、`重生成本句`。未生成的段在 live 模式会改播成品整书。（原先右边那个 `✓ 确认锁定` 已删：它只写前端一个 `seg.confirmed`，没有后端落点，`loadChunks()` 每 15 s 又按 `status==='done'` 重算覆盖，等于没作用；人工闸门统一走 `◎ 审听` 的四类判定，落 `projects/<slug>/prooflisten.jsonl`。）

`◎ 审听` = **M3 审听工位的唯一入口**（详见 §7）：开启后波形让位给四类判定键 `1 ✓对 / 2 ✗错读 / 3 ♪音色不对 / 4 ↻需重生成`，并显示 `已审/总段`；`空格` 重听本段、`n`/`b` 前后跳段、判定后自动连播下一段有音频的、`Esc` 退出。审听状态只活在这个组件里（它全程只挂载一次），换路由不丢。

### 多书切换（顶栏）

`＋ 新书` / 下拉切换 → `/api/projects/add`、`/api/projects/switch?slug=`。**会重启后端**（symlink 切工作区），前端轮询 `/api/system/stats` 最长 180s；失败提示通常是显存不足，查 `logs/switch.log`。

**本地书稿的标准存放与导入**（2026-10-12 裁决）：所有电子书放 `E-books/<书名>/<册名>/`，格式规范 = `docs/ebooks-standard.md`；一册一条命令导入 = `python deploy/ebook_import.py E-books/测试书/第1册`（meta.json 给 slug，校验后直投 `annotated_script.json`、备份旧脚本、删 chunks.json 触发重建、对照 voice_config 打印未绑音色、缺 rights.json 自动出模板）。**已人工标注的剧本（`【说话人·标记】台词` 转换而来）禁止走 `/import` 的 LLM 整本标注**——那是给无标注小说的，对剧本是破坏性重猜。第 1 册 10 集 864 段已按此升级进 `shuxue`（旧 5 集 259 段成品备份为 `annotated_script.json.bak_261012_054551`，voicelines 未动）；6 个新角色 CAPTAIN/KEEPER/LANDLADY/LUJIU/PIKE/VENDOR 未绑音色，绑前不生成其段落——提示词见 `E-books/测试书/第1册/docs/新角色音色提示词_v2_中英双语.md`。

---

## 3. seed 工作流（怎么把满意的声音留住）

1. `-1` = 随机。**现在随机也会落地真实数字**：服务端在 `-1` 时抽一个 `0 ~ 2^31-1` 的 seed，用它 `torch.manual_seed` 并下发给 sidecar，结果行和历史行显示的就是这个数。
2. 挑嗓子：固定描述、`seed` 填 `-1` 连刷 3–5 条 → 听到满意的那条**记下它显示的 seed**。
3. 复现：把 seed 填进输入框再生成一次 → 同一条嗓子。跨模型对比也用同一个固定 seed。
4. 落地：点 `选用` 把这条固化成该角色的绑定（`type: clone` + 参考样本），比只记 seed 更稳。

`voice_config` 里的 `seed` 现在**真的会被生产路径读**：描述造声（design）绑定过去是把配置里的 seed 丢了（已修），现在 `_local_generate_*` 三条路径（design / clone / custom）都吃 `voice_data["seed"]`。

---

## 4. 运维

### 4.1 启动 / 停止

```bash
cd /home/tff/software/novel-audiobook
bash deploy/start_novelTTS.sh          # 主服务（含 sidecar 拉起）
bash ttslab/start_sidecars.sh          # 只起 sidecar（已在跑则跳过，可反复执行）
bash ttslab/stop_sidecars.sh           # 按 pid 文件停，兜底 fuser -k 端口
```

`start_novelTTS.sh` 的预检：venv 存在 → `nvidia-smi` → ffmpeg/ffprobe → **空闲显存 ≥ `ALEXANDRIA_MIN_FREE_MB`（默认 8000）** → 磁盘 ≥20GB → LLM endpoint 探活（不通只禁用标注，不禁 TTS）。已在跑则拒绝二次启动；轮询 `/` 最长 240s。端口 `ALEXANDRIA_PORT`，默认 **4200**。

| 端口 | sidecar | 设备旋钮 |
|---|---|---|
| 7870 | SenseVoice ASR → ref_text + 情感标签 | `ASR_DEVICE`（默认 cpu）|
| 7861 | CosyVoice2 → 克隆 / 情感指令 | `COSY_DEVICE=cuda` 需 ~5G 空闲显存 |
| 7862 | IndexTTS-2 → 克隆 + 8 维 emo_vector | `INDEX_DEVICE=cuda` 需 ~6G |
| 7863 | Kokoro → 固定音色朗读（不能克隆，旁白兜底）| `KOKORO_DEVICE` |

sidecar 只监听 `127.0.0.1`，各自独立 venv（funasr 的 torch 与生产 venv 冲突）。

### 4.2 部署映射（本机 → 服务器）

```
deploy/patches/*.py     → alexandria/deploy_patches/*.py   用 alexandria/venv/bin/python 跑
deploy/ttslab/*         → ttslab/
backend/*.py            → alexandria/backend/*.py          （noveldb/domain 这类入库层文件本机为准）
frontend/dist/*         → tar 覆盖进 alexandria/studio/     （静态，免重启）
```

仓库端到端自检（需服务在跑，边跑边看它生成的临时记录会不会被自己删掉）：`alexandria/venv/bin/python` 之外用系统 `python3 deploy/test_audio_vault_e2e.py` 即可；模块级自检 `cd alexandria/app && ../venv/bin/python tag_vocab.py && ../venv/bin/python audio_vault.py`。

前端发布（静态，免重启）：

```bash
cd frontend && npm run build && cd dist \
  && tar cf - index.html assets/ | ssh tff@192.168.31.213 \
       'cd /home/tff/software/novel-audiobook/alexandria/studio && tar xf - && grep -o "assets/index[^\"]*" index.html'
```

`index.html` 带 `no-store`，服务器每次都回最新 hash；但**标签页里已经加载的旧 JS 不会自己换**，改完必须强刷。`studio/assets/` 只增不减，历史 hash 文件可按需清理。

后端改动**全部走安装器**（幂等：`patch(path, [(old, new, marker)])`，marker 已存在就跳过），不手改服务器文件。跑完会 `py_compile` 五个文件并打印 `ENGINE_BACKENDS_OK`。

安装器的输出含义：
- `ALREADY` = 这处改动已在盘上（正常，可反复执行）
- `PATCHED` = 本次写入
- 之后**必须重启主服务**才生效（sidecar 不受影响，不必动 CosyVoice2 常驻进程）

自检：`cd alexandria/app && ../venv/bin/python engines.py` → `SELFTEST OK`。

### 4.3 重启纪律（硬性）

**生成任务在跑时绝不重启。** 重启前先确认：

```bash
# unfinished_chunks 必须为 0，且 GPU 利用率 < 20%，否则不重启
curl -s localhost:4200/api/system/stats
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
```

pid 记在 `logs/alexandria.pid`；日志 `logs/alexandria.log`。重启需带上 `LANG=C.UTF-8`、`HF_ENDPOINT=https://hf-mirror.com`、`HF_HOME=…/hf-cache`，并在 `alexandria/app` 目录内起 `app.py`。永不动 vLLM 和其他 GPU 进程；测试写入前先备份 `voice_config.json` / `chunks.json`。

### 4.4 nvidia-smi 突然 `Failed to initialize NVML: Driver/library version mismatch`

**这不是本项目的问题，是 apt 自动升级把驱动切成两半。** 机制（192.168.31.213 上实测）：

- `apt-daily-upgrade.timer` 的 `Persistent=true` 意味着**错过的时间点会在下次开机补跑**，所以日志时间常常是 06:4x / 11:2x 这种飘值。
- unattended-upgrade 只按 Allowed-Origins 放行安全类更新。内核和 nvidia 包**同时存在于 `noble-updates` 和 `noble-security` 两个 pocket**（`apt-cache policy linux-image-*` 可见两条 500），所以它是从「安全更新」这条被放开的通道进来的 —— 关掉「自动装普通软件更新」拦不住它。
- 它升了用户态（`libnvidia-compute-595` / `nvidia-utils-595` / `nvidia-driver-595-open` 一起 595.91.07 → **595.99.02**），但**内存里加载的内核模块还是 595.91.07**：

  | 位置 | 本机版本 | 取值命令 |
  |---|---|---|
  | 内核里正在跑的模块 | 595.91.07 | `cat /sys/module/nvidia/version` |
  | 磁盘上给当前内核的预编译模块 | 595.99.02 | `modinfo -F version nvidia` |
  | 用户态库 / nvidia-smi | 595.99.02 | `dpkg-query -W -f='${Version}\n' 'nvidia-driver-595-open'` |

  NVML 要求用户态与内核模块严格同版本，对不上就直接拒绝初始化 —— `nvidia-smi` 连一行数字都吐不出来。
- **已经在跑的 GPU 进程不受影响**（它们的旧库还映射在内存里），所以症状是「服务活着，但任何新起的 CUDA 进程和 `nvidia-smi` 全废」。`start_novelTTS.sh` 的预检已改成：拿不到纯数字就打印上面三个版本对照和处置办法，不再把报错文本当数字比大小（旧版会吐 `[: …: integer expression expected`）。

**修 = 让模块和库重新同版本**，两条路：

```bash
# A) 不重启：先把占用 GPU 的进程全停掉（vLLM / sidecar / 本服务），确认无人占用后重载
sudo fuser -v /dev/nvidia*                       # 必须为空才能继续
sudo rmmod nvidia_uvm nvidia_modeset nvidia && sudo modprobe nvidia
# B) 重启（最省事）。前提：GRUB 第 0 项那个内核有配套的 nvidia 模块包，否则重启后 GPU 直接没了
ls -1 /lib/modules | sort -V                     # 确认将启动的内核
dpkg -l "linux-modules-nvidia-595-open-$(uname -r)" | grep ^ii   # 有 ii 且与用户态同版本才安全
```

重启前照 §4.3 预检；`rmmod` 在有进程占用时只会失败，别拿它当"顺手重载"。

**防复发（钉住内核与驱动）**

> **状态：待查，未执行。** 2026-10-10 复核时 `apt-mark showhold | wc -l` = **0**，这台机器仍处在"每次 `apt-daily-upgrade` 都可能再切一次"的状态。下面的名字是 213 实测筛出来的，换一台必须重跑第 1 步，不要照抄。脚本形态见 `deploy/fix_gpu_driver.sh --hold`（同样**未执行，等审查**）。
>
> 待查清单：
> - 钉完之后 `unattended-upgrades` 是否会因为 held 包卡在 `E: … held broken packages`（139 机型的现象），需要在 213 上观察一次 `apt-daily-upgrade` 跑完的日志。
> - `linux-firmware-amd-graphics` 目前 pending（来自 `noble-updates`，非自动安装通道），与本次冻结无关，但别把它误读成"漏钉"。
> - 长期解法到底是 hold 还是换 `nvidia-dkms-595`：这台用的是**预编译**模块（`linux-modules-nvidia-595-open-<kver>-generic`），`nvidia-dkms-595` 是 `un`（未装）。dkms 解决的是"新内核没有配套模块"，**不解决本次事故**（已加载的模块照样要重载/重启才换版本），而且换过去要面对 Secure Boot / MOK。所以 hold 是当前唯一确定有效的拦法，dkms 只是备选。
> - 人工升级的窗口：hold 期间内核与驱动不再拿安全补丁，要成套升（`unhold` → `apt-get upgrade` → 立刻重启），不能只升一边。

`Allowed-Origins` 是口袋级开关，改它等于把安全更新一起关掉；要拦就按包名 `apt-mark hold`。**但包名必须按机器实际筛，不能照抄别处的**：这台是 HWE 内核，`linux-generic` / `linux-image-generic` / `linux-headers-generic` 这类包名**不存在**，`apt-mark hold` 碰到不存在的名字会静默跳过，你以为钉住了其实只钉了一半。所以先用版本号把成套包筛出来，再校验名字，最后才钉：

```bash
# 1) 只读校验：按已装版本号筛出 nvidia 成套包 + 内核/模块元包，逐个确认包名存在
NV=$(dpkg-query -W -f='${Package} ${Version}\n' | awk '$2 ~ /^595\.99\.02/ {print $1}')
KER="linux-generic-hwe-24.04 linux-image-generic-hwe-24.04 linux-headers-generic-hwe-24.04 \
     linux-modules-nvidia-595-open-generic-hwe-24.04"
for p in $NV $KER; do dpkg-query -W "$p" >/dev/null 2>&1 || echo "✗ 包名不存在: $p"; done
echo "拟钉住 $(echo $NV $KER | wc -w) 个"          # 213 实测 = 15 个 nvidia + 4 个内核/模块

# 2) 名字全对，才执行（需要 sudo）
sudo apt-mark hold $NV $KER
apt-mark showhold | wc -l                          # 必须等于上一步的数字

# 3) 撤销
sudo apt-mark unhold $NV $KER
```

关键一条别漏：`libnvidia-compute-595`（NVML/libcuda 的宿主）必须在名单里，只钉 `nvidia-driver-595-open` 元包拦不住用户态库被单独升级。驱动与内核要**一起钉** —— 只钉驱动、内核继续自动升，下一次就会变成"新内核 + 无配套 GPU 模块"，那是比这次更难发现的坑。代价：内核与驱动不再自动拿安全补丁，需人工成套升级，且 `apt-get upgrade` 会一直显示这批被 kept back。

---

## 5. 故障排查（都是真踩过的）

| 症状 | 根因 | 处理 |
|---|---|---|
| 导出的整书比人声轻一截、峰值还超标 | 原 `merge_audio` / `merge_m4b` 只做 concat + 转码，**没有任何响度处理**（实测旧成品 −23.25 LUFS / −1.18 dBTP，两项都不合格） | 两个出口现在自动过 `backend/master_audio.py` 的后期，落 `delivery_report.json`；由 `deploy/patches/add_export_loudnorm.py` 接入，**装完必须重启主服务才生效**（§4.3）。校验：`backend/master_audio.py --inspect 成品.m4b（不合格非 0 退出；`--check` 是模块自检，不带路径）` |
| 旁白/台词变成乱音，30 字念出 ~20s | 生产自动抓了 CosyVoice2 的 `instruct2` 通道，喂进去的是给 Qwen 写的长描述（分布外文本） | 通道改为显式 `mode`；`instruct2_style()` 只收中文、包成「用…的语气说话」，非中文返回空并退回纯克隆。同句实测：乱指令 14.4s / 规范句 12.6s / 纯克隆 7.7s（修复后成品 7.8s） |
| 克隆出来不像参考音频（例如要老人声却是少年） | 克隆音色 100% 来自 ref_audio；年龄描述写在 `character_style` 里，sidecar 根本不读 | 「角色与声音」重传/重选参考音频；要老人就录老人。段级 instruct 只改语气不改年龄 |
| 同一角色每句音色都在飘 | voice_config 里 `type: design`（描述造声）被拿去量产 | 绑定处现在会给🔴红字警告；去声音实验室 `选用` 一条固化成 clone 参考 |
| 批量生成跑一半，刷新页面后按钮变回「▶ 批量生成」、看着停不掉 | `store.busy` 是纯前端内存态，刷新即丢，后端任务其实还在跑 | 已修（2026-10-13）：进工作台时 `resyncRunning()` 查后端 `/api/status`，running 的任务自动恢复跟踪、按钮回到「⏹ 停止生成」；强刷浏览器缓存的旧 bundle 会没有这行为，见 §4.2 部署映射 |
| 给 A 角色造的声音绑到了 B 角色（串绑） | 记录带生成时的 `speaker`，选用却按当时下拉框的角色写入，两边不一致时无提示 | 已加防护（2026-10-13）：`选用` 时 记录 speaker ≠ 当前角色 会弹二次确认；历史行也回显「目标 ××」。既成串绑（如根 voice_config 里 PIKE←LANDLADY 的样本）仍需手工重绑修复 |
| 批量生成直接报错不发声 | cosy/index + `zero_shot` + **空 ref_text** | 补 ref_text（ASR 可自动转写），或把通道切到「情感指令」 |
| 批量生成**全量秒失败**（进度 0 done, N failed） | CUDA OOM：24G 卡被 **ollama llama-server（实测 14.4GiB，keep_alive 常驻）+ mineru VLLM（~6.7GiB）+ app.py 自身 2.5GiB** 挤满（2026-10-12 实录） | 生成前卸载 ollama 模型（`ollama stop <model>` 或配 `OLLAMA_KEEP_ALIVE=0`）、或停 mineru；确认法：`nvidia-smi` 看占用 PID，`ps -p <pid> -o args` 认进程 |
| 每段 instruct 没效果 | 引擎是 Kokoro（`emo: none`），或 CosyVoice2 走纯克隆通道 | 看绑定区的情感载体说明；换引擎或换通道 |
| 试听不到参考音频 | 全站原先没有 `<audio>` 元素 | 声音实验室已加参考音频试听条；「角色与声音」有 `试听当前绑定` |
| 结果行显示 `seed -1`，复现不了 | 随机 seed 没落地 | 安装器 `LAB_SEED` 组已修：随机也抽真数并回显 |
| 前端改了没生效 | 浏览器缓存了旧的带 hash 资源 | 强刷；`studio/assets/` 里会留历史 hash 文件，可按需清理 |
| 改完后端行为没变 | 忘了重启（`PATCHED` ≠ 已加载） | §4.3 预检后重启 |
| 段「已绑定但听不到角色声」 | 段落显示的是旧音频 | 换绑定不会重生成，必须点 `↻ 重生成该角色台词` |
| Voice Lab 点了 `选用`，目标角色引擎却没变（旁白还是 CosyVoice2） | 旧版 `apply()` 优先用记录上「生成时」的角色标签，写进了别的角色 | 已修：只认当前下拉框选中的角色；重听那条再点一次 `选用` 即可 |
| 标签清不掉 / 少了一个维度 | `tags` 是全量快照，但早期实现是 merge | 已改为 replace；前端标签面板每次都送全量 |
| 仓库里筛不到「旁白」 | `role` 存的是 key（`NARRATOR`），中文只是显示名 | 筛 `NARRATOR`；入库卡片下方有 `NARRATOR=旁白 …` 对照行 |
| 行内改成 NARRATOR，按钮还写「绑定 → CROWD」 | 改的是页顶**筛选框**（查询条件），按钮读的是**本行**的 role；#6 库里存的就是 CROWD（那条误绑记录带出来的） | 改本行那个框；没改完就点绑定会先把 role 落库再绑。包更新后要强刷（`assets/index-*.js` 换 hash） |
| 入库报 `cannot commit transaction - SQL statements in progress` | `INSERT … RETURNING` 的游标没取空就 commit | 已修：先 `fetchone()`+`close()` 再 commit |
| 点 `存入仓库`/`保存`/`绑定到角色` 没反应也没提示 | 三处静默路径：①任一请求在跑时整排按钮被全局 `saving` 禁用，点击被吞 ②`存入仓库` 在来源为空时是 disabled，不说为什么 ③`绑定` 读的是**页顶筛选框**的人物，行内那个框它不看 | 已修：禁用与「处理中…」文案改为逐行（`saving === r.id`），空来源/未知角色都会弹出指名原因；`绑定` 改读**本行**人物，非本书角色直接点名可用 key。后端三个写接口实测 200 / <20ms，不是服务问题 |
| 角色风格里冒出「语速=0.453，音高=0.079」这种数字串，念出来怪 | 早期 `绑定` 把仓库条目的 `tag_prompt`（量化标签文本）写进了 `character_style`，而 Qwen 的 clone 路径会把该字段拼进 instruct 当语气指令念 | 已修：绑定不再写 `character_style`（留空），标签只走段级 `instruct`。线上 CROWD 的脏值已清空（改前备份 `voice_config.json.bak-*`）。这些数字是**对旧音频的实测**，改它们不会改变任何音频 |

### 重装环境的坑（照抄）

- `grpcio==1.57.0` 无 cp312 wheel → 放开 `>=1.62`
- 无 nvcc 机器上 `deepspeed` 会让 transformers 导入即炸 → 推理用可卸载
- `openai-whisper` sdist 需 `pkg_resources`，setuptools≥81 已移除 → `pip install "setuptools<81"` 后 `--no-build-isolation`
- `matcha` 模块在 `repos/CosyVoice/third_party/Matcha-TTS`，需手动进 `sys.path`
- CosyVoice2 非流式输出键是 `tts_speech`
- index-tts 要求 python<3.12 → `uv venv --python 3.11`
- IndexTTS-2 缺辅助权重：`w2v-bert-2.0`（conformer_shaw.pt + model.safetensors，各 2.2G）必须预置到 `models/IndexTTS-2/hf_cache/w2v-bert-2.0/`，否则加载时去 ModelScope 拉 → 404
- indextts/kokoro 的 venv 要补 `fastapi uvicorn python-multipart soundfile`

---

## 6. 数据与文件位置

```
alexandria/
  app/app.py                    FastAPI 主程序（约 90 个路由）
  app/engines.py                引擎注册表（唯一真源，含 __main__ 自检）
  app/voice_lab.py              声音实验室（MODELS 注册 + 缓存 + 结果清单）
  app/tag_vocab.py              标签词表唯一真源（FACETS → validate / to_vector / as_prompt，含 __main__ 自检）
  app/audio_vault.py            音频仓库（入库实测、筛选、/pick LLM 出口，含 __main__ 自检）
  app/tts.py                    生产 TTS 分发：qwen 进程内 / sidecar
  app/emotion_map.py            16 个规范情感句 + infer() + ASR 标签桥
  app/generate_personas.py      批量自动设计（描述 → 预览 → 固化为 clone）
  backend/master_audio.py       母带后期（两遍 loudnorm + 真峰值限制）+ 段边界机检 boundary_flags + 成品复判 finalize/gate——阈值与判定唯一真源，单验一个文件用 `--inspect 成品`
  deploy_patches/add_export_loudnorm.py  幂等安装器：把后期挂进 merge_audio / merge_m4b（新装跑这份）
  deploy_patches/add_delivery_gate.py   幂等安装器：M1 机检闸门——GET /api/delivery_report、归一崩溃也写不合格报告、导出末尾对真成品复判
  deploy_patches/add_prooflisten.py   幂等安装器：M3 审听工位——POST/GET /api/prooflisten，判定落 projects/<slug>/prooflisten.jsonl
  deploy_patches/fix_master_report_dir.py 幂等修正器：已打过接线的机器改验收报告落点（旧机器跑这份）
  chunks.json                   每段台词 + 状态 + 溯源（voice_engine）
  voice_config.json             每个角色的音色绑定
  annotated_script.json         LLM 标注稿
  delivery_report.json          每次导出的实测验收（LUFS / dBTP / 通过与否 / 章节数 / 时长）——交付前看它，不靠耳朵
  designed_voices/              Voice Lab 预览与清单
  clone_voices/                 上传的参考音频
  studio/                       前端 dist
ttslab/                         四个 sidecar + 启停脚本 + README
logs/                           主服务/任务/sidecar 日志与 pid
```

多本书时 `projects/<slug>/` 下各有一份同名数据，根目录文件是指向当前工作区的 symlink；切书即重启服务。

---

## 7. 最近三天做了什么（变更摘要）

- **音频仓库（`/vault` + `audio_vault.py` + `tag_vocab.py`）**：好声音带量化标签入库（人物 × 情节 × 情绪 × 感情 × 语速 × 音高 × 评级），入库即实测时长/字每秒/中位基频；同一份标签两个出口（52 维向量 + 一句中文），`/api/vault/pick` 是给 LLM 的拣选入口。安装器 `deploy/patches/add_audio_vault.py`。
- **Voice Lab 记录可管理**：历史倒序分页（每页 20，按角色筛）、行内标注（走同一词表校验）、改试听文本、删记录（可选连音频文件）。清单读写收敛到 `_lab_records()/_lab_write()` 一处。
- **修：`选用` 绑错角色**：Voice Lab 的绑定原先偏向记录上生成时的角色标签，界面上选的是旁白、写进去的可能是 CROWD；现在只认当前选中角色。
- **修：`INSERT … RETURNING` 后 commit 失败**；**改：标签为全量快照语义**（清得掉）。
- **修：仓库绑定污染角色风格**：`绑定` 曾把条目的 `tag_prompt`（`语速=0.453，音高=0.079` 这类实测标签）写进 `voice_config.character_style`，Qwen clone 路径会把它当语气指令拼进 instruct。现在绑定只写 `ref_audio`/`ref_text`，`character_style` 留空；线上 CROWD 的脏值已清空并留备份。同时把「四个风格字段各被谁读、数值标签不是调音旋钮」写进 §2◆ 音频仓库末尾的「风格字段各管什么」。
- 外部角色素材不提供下载/抓取（《神探迈克狐》这类是付费成品）：把自有的合法素材放进工作区，用仓库的 `file` 来源入库即可。
- **清掉前端「点了没反应也没提示」**：三个写接口在服务端实测 200 / <20ms，问题全在 UI 静默路径 —— ①任一请求在飞时全局 `saving` 把整排按钮禁用、点击被吞（改成逐行 `saving === r.id` + 「保存中/绑定中/入库中…」）；②`存入仓库` 来源为空时只是 disabled（改成可点并说明缺什么）；③仓库 `绑定` 读的是页顶筛选框的人物，行内那个框它不看（改成读本行 `role`，陌生 key 明确报错并列出可用值）；④`add` 失败只写行内小字（补 toast）。顺带修了一个会写串数据的 bug：`保存` 不分情形都送 `editTags`，A 行的标签会被写进 B 行，现在只在标注面板为本行展开时才提交。
- **role 语义落文档**：仓库的 `role` 是 voice_config 的 **key**（`NARRATOR`），中文（旁白）只是前端显示名，所以按「旁白」筛必然 0 条；入库卡片新增 `NARRATOR=旁白 · …` 对照行，行内「人物」框接上同一份补全。

- **跨引擎接入**：CosyVoice2 / IndexTTS-2 / Kokoro 以 sidecar 形式并入，`engines.py` 成为唯一注册表；Voice Lab 与批量生产都读它。
- **情感载体重构**：每个引擎声明 `emo`（verbatim / instruct2 / emo_vector / none），段级情感按载体自动换算，UI 通过 `/api/engines` 如实播报；情感词表收敛到 `emotion_map.py` 一份。
- **通道显式化**：voice_config 新增 `mode`，CosyVoice2 走纯克隆还是情感指令由用户显式选，杜绝自动翻转导致的乱音。
- **参考音频链路**：上传即 ASR 自动转写 ref_text + 情感建议，可修正；新增参考音频试听；ref_text 缺失在绑定处直接红字警告。
- **seed 贯通**：Voice Lab 随机 seed 落地并回显；design/clone/custom 三条生产路径都尊重配置里的 seed。
- **绑定后果提示**：「角色与声音」按 type + 引擎 + 通道给出🟢/🔴彩色说明，明确「生成出来的就是不是你试听挑的那个声音」。
- **溯源与兜底留痕**：每段写入真正出声引擎 `voice_engine`，Kokoro 顶班显式标注，禁止静默冒充角色音色。
- **母带后期接入导出（2026-10-10）**：`merge_audio` / `merge_m4b` 原先只做 concat + 转码，**没有任何响度处理**——旧整书实测 −23.25 LUFS / −1.18 dBTP，轻 7 dB 且峰值超标。现在两个出口自动过 `backend/master_audio.py`（两遍 loudnorm `linear=true` + `alimiter level=0`，阈值与判定唯一真源），实测 −16.45 LUFS / −2.16 dBTP、章节 259→259、时长零漂移；每次导出落 `delivery_report.json`。安装器 `deploy/patches/add_export_loudnorm.py`（幂等，备份 `project.py.bak_pre_loudnorm`），**需重启主服务生效**。两个坑留此备查：本 build 的 `alimiter` 默认 `level=true` 会自带补偿增益；`alimiter` 限采样峰值而验收读帧间真峰值，故留 1 dB 余量。
- **段首死气裁剪上线（2026-10-11）**：372 段实测段首静音中位 437 ms / 最大 1273 ms、段尾中位 90 ms —— 段间静音是代码里的固定值，随机的那截在段头。`app/tts.py` 加 `trim_leading_silence`（`combine_audio_with_pauses` 与 `compute_timeline` 两处共用，只改一处章节轴会漂），收窄到 80 ms 后：**同一本书 1508.62 → 1399.75 s（−7.2%）**，段首跳变最大 −40.38 dB（阈 −12，超阈 0 段，没切进语音），259 章末章 END 正落在文件尾。干跑踩到的坑：pydub 的 `detect_leading_silence` 是**绝对 dBFS**，`head_tail_jump_db` 的静默起点是**相对段峰**，两个数不能直接对照。安装器 `deploy/patches/add_leading_silence_trim.py`，备份 `tts.py.bak_pre_lead_trim`，关掉改 `LEAD_SILENCE_KEEP_MS = None`。
- **M1 机检闸门上线（2026-10-11）**：`backend/master_audio.py` 补 `inspect()` 全项实测（LUFS / RMS / 真峰值 / 时长 / 章节数 / 体积 / 文件首尾静默）、`gate()` 客户口径与 `channel_gate()` 渠道口径分两层（只有前者能拦交付）、`finalize()` 对**真成品**复判并就地改写 `delivery_report.json`；CLI 加 `--inspect 成品`（不合格非 0 退出），`--check` 里加**削顶反例**（`volume=24dB` 的 220 Hz 正弦 → −1.95 LUFS / +0.04 dBTP，两项全 FAIL）。接线：`GET /api/delivery_report` + 前端 `/export` 的 LIBRARY 机检栏，`通过=false` 时红字并禁用下载（试听仍可）。安装器 `deploy/patches/add_delivery_gate.py`（备份 `app.py.bak_pre_gate`），改了 `app.py`，需重启主服务。
  两个踩到的坑留此备查：① **ffmpeg `lavfi` 的 `sine` 源不是满幅**，实测峰 −18.06 dBFS——不加增益就当一个「顶满样本」，闸门会因为响度过轻而 FAIL，看起来测过了，其实没测削顶。② **机检一度量错了文件**：归一那步只能看中间 WAV，于是报告里 `章节数: 0→0`、体积 117.7 MB（成品 m4b 实际 20.4 MB），「章节标记没丢」这条判据从来没生效过；所以导出末尾补了 `finalize()` 这一道。
- **M3 审听工位上线（2026-10-11）**：`deploy/patches/add_prooflisten.py` → `POST/GET /api/prooflisten`，判定追加进 `projects/<slug>/prooflisten.jsonl`（四类 `ok/misread/timbre/regen` + 每段墙钟秒），`/export` 的 pre-flight 多一行「人工审听 x/259 · 未审 n」。**工位入口在底部播放条右侧的 `◎ 审听`**（不是剧本工作台右栏——第一版放右栏实测看不到判定键、还把「质检」块顶出可视区）：开审听后波形让位给 `1 ✓对 / 2 ✗错读 / 3 ♪音色不对 / 4 ↻需重生成` 四个键 + `已审/总段` + 快捷键提示；`空格` 重听本段、`n`/`b` 前后跳、判定后自动连播下一段有音频的、`Esc` 退出。剧本工作台只留进度角标和每段判定标记。母带导出 LIBRARY 的「播放」在播时变 `■ 停止`。踩到的坑四个：① **书目录不能靠 `realpath(CHUNKS_PATH)` 反查**——`chunks.json` 虽在 `SWAP_ENTRIES` 里，实测服务器上它是 `alexandria/` 根目录的真文件，反查会把判定写进多本书共用的软链根（串书）；改成走 `projects.json` 的 `active`。② **Vue 2 里 computed 与 method 同名会把整个 SPA 打死**：给审听统计起的 computed `listen` 撞上原有的方法 `listen()`（试听本句），`vite build` 和模板编译都不报错，运行时才炸 `Invalid handler for event "click": got undefined`，组件树渲染中断——hash 路由下所有点击监听一起没了，症状是「左侧导航全点不动」。③ **模板引用了 `data()` 里没有的键，同一死法**：判定块搬进播放条时漏注册 `VERDICT` → `Cannot read properties of undefined (reading 'ok')`，症状是「点了开关、状态变了、界面不动」。④ **`reactive()` 之后才挂上去的键不被追踪，读它的 computed 永远缓存初值**：`store.js` 先 `reactive(structuredClone(mockStore))` 再 `store.mode = 'mock'`（`busy/toast/projects/engines` 同），而 mock 里没有 `mode` 键 → `TransportBar` 的 `live()` 卡在 `false`，`onPlay()` 一直走演示分支，症状是「播放按钮点了根本没有任何反应」；模板里内联 `store.mode === 'live'` 看着正常，只有 computed 是死的，所以最难发现。修法是所有键在进 `reactive()` 之前就在对象里（mock 的 `system` 补 `qc/delivery/listen: null`，`loadChunks()` 的段字面量补 `listen: null`）。CDP 复验 `vm.live === true` 且点 `▶` 后 `store.transport.url` 指向本段；但后台标签页 `navigator.userActivation.hasBeenActive === false`，连 `Input.dispatchMouseEvent` 都不算用户激活，`audio.play()` 一律 `NotAllowedError` —— 验的是驱动限制，不是按钮坏。
- **前端改完的验收方法（别再靠 md5 比对）**：起 dev server（`npm run dev`，已代理到 `:4200`），用无头 Chrome 逐路由抓控制台：`chrome.exe --headless=new --enable-logging=stderr --virtual-time-budget=25000 --dump-dom http://localhost:5173/#/script`，`grep -i "vue warn|TypeError|Error in"` 必须为空，再看 `--dump-dom` 出来的 DOM 里有没有真数据。上面那个 computed 撞名就是这么抓到的；上线后再对生产 URL 跑一遍同样命令。**但这条只覆盖「路由打开就渲染」的东西：只在点击后才出现的块（如审听判定键）全绿也能是死的**——那部分要么 dev server 下人工点一下，要么走 CDP 驱动页面（见下）。出事时**不必回滚文件**——`studio/assets/` 只增不减，改 `index.html` 里的 hash 指回上一版即可（本次回滚用的就是 `index-D817FasR.js`）。
- **CDP 驱动真页面复验（用户开 `--remote-debugging-port=9222` 时）**：`curl http://127.0.0.1:9222/json` 拿 `webSocketDebuggerUrl`，Node 全局 `WebSocket` 直连，`Runtime.evaluate`（`awaitPromise` + `returnByValue`）读 DOM/组件状态、`Input.dispatchKeyEvent` 发键、`Page.captureScreenshot` 看图；组件实例从 `document.querySelector('.transport').__vue__` 拿。两个**假象**别当真 bug：① 后台标签页 rAF 冻结 → `<transition mode="out-in">` 永远停在 `fade-leave-active`，看着像「切路由后白屏/列表空」，标签页一亮就自己好了；② `element.click()` 不算用户激活 → `audio.play()` 被 autoplay 挡，播不出声不等于按钮没接上——**连 `Input.dispatchMouseEvent` 发的「真实」鼠标事件在后台标签页也不算**（实测 `navigator.userActivation.hasBeenActive` 始终 `false`，新建一个静音 `new Audio()` 照样 `NotAllowedError`），所以「按钮接上了没有」看 `store.transport.url` 有没有落到本段路径，不看有没有声音。另两条驱动口径：`Page.navigate` 换 hash 是**同文档导航、不重载**，验新 bundle 必须换 path 或加 `?v=`（否则你以为在测新版，其实进程还是旧的）；组件实例只在 `.transport` 这类真实节点上取（本页 `#app` 取不到）。
- **M5④ 权利台账落地（2026-10-11）**：`deploy/check_rights.py`（部署在 `alexandria/deploy_patches/`，只读检查、不改后端、不需要重启）+ `docs/rights-ledger.md`。台账一本书一份写 `alexandria/projects/<slug>/rights.json`，认书走 `projects.json` 的 `active`（同 M3 那条：`chunks.json` 在共享根上是真文件，不能 `realpath` 反查）。三条判据缺任一条退出码 1 = 不开工：文本三权利 + 书面担保 + 侵权自担 + 合同凭证 / 每个 `type=clone` 角色的声线来源 / AI 朗读声明文本。跑法：`cd alexandria/deploy_patches && ../venv/bin/python check_rights.py`（`--slug` 指书、`--init` 写空模板、`--demo` 自检）。**实测声线**：这本书 8 个角色全 `type=clone`，但参考音频一律是 persona 造的 `designed_voices/*_preview.wav`，不是真人声纹——所以 `来源=自研音色` 合法，检查器用路径认这件事，参考音频落在 `designed_voices/` 之外还按自研填的直接拦。当前这本书没填台账，检查器判「缺 `rights.json` → 不开工」是对的。**留着的垃圾**：`alexandria/delivery_report.json`（02:13、`书=alexandria`、`输出=temp_master_norm.wav`）是修目录那次的过期产物，现行的是 `projects/shuxue/delivery_report.json`（04:15），`/api/delivery_report` 实测读的是后者，闸门没读错；删它不可逆，等单独批准。
- **验收口径实测（2026-10-11，服务重启后真跑两条导出链路）**：MP3 与 M4B 都验到 `−16.0 LUFS / −2.48 dBTP / 时长 1508.6 s / 259 章`，`通过: true`。踩到并修掉的接线缺陷：报告原先写在 `root_dir`（共享软链根）上——换书即被覆盖、`书` 字段恒为 `"alexandria"`；改成写在成品的真实目录（安装器 `deploy_patches/fix_master_report_dir.py`，旧机器专用，因为 `add_export_loudnorm.py` 见已接线就跳过）。**重新导出 M4B 要带 `per_chunk_chapters=true`**，默认 `false` 走标题检测分组、导出不带章节标记（现成母带的 259 章是 2026-10-04 带该参数导出的）。顺带：我方母带的 LUFS−RMS 差值只有 **+0.65**（不是商用样本的 +3.55），渠道 RMS 窗口的判定因此改写，见 `channel-master-checklist.md` §2.2。
