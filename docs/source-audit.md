# 上游仓库源码审计报告

审计日期：2026-10-03。全部结论基于对实际源码的逐文件阅读，非 README 推测。
审计执行环境为本 Windows 开发机；目标运行环境为另一台 Ubuntu 24.04 + RTX 3090 机器。

## 仓库与 commit 记录

| 仓库 | commit SHA | commit 日期 | 许可证 | 克隆大小 |
|---|---|---|---|---|
| alexandria-audiobook | `be6343d95d94db5f88973aa25575a390f3ce46aa` | 2026-08-02 | **MIT** | 853K |
| Audiobook-Generator | `98c7fd7f961debd4a9fbac54a1d57d478e3ed208` | 2026-02-15 | **无 LICENSE 文件**（README 声称 MIT 但未附文本） | 452K |
| tts-audiobook-tool | `b8486ddc8f8aee630ef578d441e8aab68fc34e8c` | 2026-09-29 | **MIT** | 11M |
| ebook2audiobook | `d3ff5bc9272bab0f392fb847d186648c7fab998b` (v26.9.27) | 2026-10-02 | **Apache-2.0**（文本完整；pyproject 误标 MIT） | 60M |
| qwen3-tts-audiobook | `26ffedf7ea7d56d3ac17d0957495f674458fd6f9` | 2026-06-01 | **MIT** | 463K |

⚠️ 迁移纪律：每个复制进本项目的文件顶部保留 `源仓库 + 路径 + commit SHA` 注释。Audiobook-Generator 无许可证文本，**只提取设计思想与提示词写法，禁止逐文件复制其源码**。

---

## 1. Alexandria（主框架）— 审计结论：比 info.txt 预期更强，但需大改中文层

### 实际结构（app/ 全部文件，行数）

```
app/app.py                2569  FastAPI 全部路由 + Pydantic 配置模型 + 子进程调度
app/tts.py                1758  TTSEngine：本地 Qwen3-TTS(3模型) + 外部 Gradio 后端
app/project.py            1014  ProjectManager：chunk 生成、批量、合并、导出
app/generate_personas.py   879  LLM 人物分析 + VoiceDesign 试听生成
app/generate_script.py     500  LLM 剧本标注（子进程）
app/review_script.py       537  LLM 剧本二审（子进程）
app/train_lora.py          592  LoRA 微调子进程
app/hf_utils.py            110  builtin LoRA 下载
app/default_prompts.py      45  ┐
app/persona_prompts.py      31  ├ 提示词加载器（根目录 3 个 .txt，"---SEPARATOR---" 分隔）
app/review_prompts.py       30  ┘
app/utils.py                38  仅 atomic_json_write()
app/static/index.html     4097  单文件 vanilla JS + Bootstrap 5.3（非 Vue）
```

### 与 info.txt 假设不符的事实（重要）

1. **`app/parse_voices.py` 不存在**。README 与迁移表都引用了它，实际声音提取是 `app.py:833` 的内联 `get_voices()`。`backend/voices/voice_import.py  # Alexandria` 这一行迁移表作废，改为从 `app.py` 提取。
2. **人物别名解析已存在**：`generate_personas.py:53-117` 有 `normalize_speaker_name / _token_jaccard / _resolve_to_canonical(threshold=0.4)` 和一次性 LLM 别名分组 `_resolve_aliases_batch()`；人物档案文件 `persona_refs/<speaker>.json`（aliases/features/personality/voice_clues/relationships/sample_lines）。info.txt 把 `speaker_resolver.py` 标为"全新增"是低估——应改为**移植+中文化**，不是从零写。
3. **没有任何数据库**。全部状态是仓库根目录下的平铺 JSON（`annotated_script.json` / `chunks.json` / `voice_config.json` / `config.json` / `state.json`），用 `atomic_json_write` 写入。"SQLite 数据层"是从零新建，不是改造。
4. **脚本条目格式极简**：`{"speaker": "ELENA", "text": "...", "instruct": "..."}`，无段落 ID、无原文定位、无章节维度。info.txt 要求的"原始段落顺序/来源定位映射"在上游不存在，必须自己建。
5. **TTS 无跨 chunk 韵律上下文**：每段音频独立合成，LLM 提示词明确要求 instruct 自带全部语境。长小说跨段音色/语气漂移是已知缺陷（tts-audiobook-tool 的"滚动续接 ICL"机制可部分弥补，见 §3）。
6. **全英文中心**：3 个提示词文件、章节标题正则 `project.py:650`（只认 chapter/part/prologue…）、`train_lora.py --language english` 默认值。中文小说 = 重写全部提示词 + 中文标题匹配 + `--language chinese`。
7. 端口 4200；LLM 默认 `http://localhost:11434/v1`（Ollama 风格），默认模型 `richardyoung/qwen3-14b-abliterated:Q8_0`——接入本地 Qwen 时改 config.json 即可，走 openai SDK，兼容 vLLM。
8. `test_api.py` 是打活服务器的集成脚本不是 pytest；无 CI 测试可依仗。

### 核心机制细节（迁移必需）

- **进程模型**：脚本标注/审校/人物生成/LoRA 训练全部是 `sys.executable -u xxx.py` 子进程（日志进内存 `process_state`，无持久化）；音频 chunk 生成在进程内 `BackgroundTasks + ThreadPoolExecutor`。persona 子进程启动前会 `engine=None; gc.collect()` 释放显存——**这是上游已有的 GPU 单实例让渡模式，保留**。
- **三种 TTS 模型**（`qwen_tts` 包，pin `qwen-tts==0.1.1`）：
  - `Qwen3-TTS-12Hz-1.7B-CustomVoice` → `generate_custom_voice(text, language, speaker, instruct, non_streaming_mode, max_new_tokens)`，9 个内置音色
  - `-Base` → `create_voice_clone_prompt(ref_audio, ref_text, x_vector_only_mode)` + `generate_voice_clone`；LoRA 走 PEFT 包装 `model.model.talker = PeftModel.from_pretrained(...)`
  - `-VoiceDesign` → `generate_voice_design(text, instruct=描述, language)`
  - voice_config 类型路由：`custom | clone | lora | builtin_lora | design`；`alias_of` 带环检测。
- **批量推理**：`generate_batch` 按 voice 类型分组 → 按长度排序 → sub-batch（`_estimate_max_batch_size` 按 KV-cache 估算显存）→ 组间 `empty_cache()`。`torch.compile(max-autotune)` 可选加速 codec 解码 3-4×。
- **chunking 两层**：LLM 输入侧 3000 字符/段 + 前 3 条样式回看 + 全书人物名册注入；TTS 音频侧 `group_into_chunks` 同 speaker+instruct 合并到 500 字符上限，`pause_after` 毫秒级可覆盖（默认跨说话人 500ms、同人 250ms）。
- **导出**：MP3 合并（校验 428 字节 libmp3lame 失败→WAV 回退）；M4B = ffmpeg FFMETADATA 章节标记（`project.py:541`）；Audacity 多轨工程导出。
- **GPU 生命周期**：模型懒加载 + `threading.Lock` + 实例缓存；bf16 on CUDA；`unload_models()` 全清。大量 ROCm/RDNA hack（3090 无关但增面积）。README 基准测试是在 AMD RX 7900 XTX 上做的，NVIDIA 侧 compile 路径需自测。

### 依赖（app/requirements.txt，14 行全 pin）

fastapi==0.128.0, uvicorn==0.40.0, pydantic==2.12.5, pydub==0.25.1, requests==2.33.0, openai==2.16.0, gradio_client==2.0.3, soundfile==0.13.1, numpy==2.2.6, librosa==0.11.0, **transformers==4.57.3**, peft==0.18.1, python-multipart, aiofiles。
另装：`torch==2.7.0`（cu128 index，torch.js）+ `qwen-tts==0.1.1`。flash-attn wheel 是 cp310（Python 3.10）；Docker 基座 pytorch:2.8.0-cuda12.8。

---

## 2. Audiobook-Generator — 审计结论：只借设计，不抄代码（无证可依）

- **Job 模型**：SQLite（SQLAlchemy 同步）单表 `audiobook_jobs`，完整模式见 migration-matrix。要点：`status ∈ pending/processing/awaiting_review/completed/failed/cancelled`、`job_metadata/detected_characters` 为 JSON Text 列、`parent_job_id + is_batch` 做章节子任务、`retry_count/max_retries`、`last_heartbeat`。全书文本内联存在 `input_text` 列（反模式，不学）。
- **两阶段生命周期（最有价值的设计）**：phase1 文本处理+说话人检测 → `awaiting_review`(progress=50) → 用户在 UI 里改人物表/传克隆样本 → `POST /jobs/{id}/confirm` → 回到 pending 且 `detected_characters IS NOT NULL` 即视为 phase2。**续跑判定用状态约定而非显式状态**（脆弱，移植时改成显式 `phase2_pending`）。
- **恢复机制三件套**：启动时 `_recover_stale_jobs`（PROCESSING→重试或失败）；每任务 30s 心跳线程；`_check_and_handle_stuck_jobs` 每 30s 扫心跳超 120s 的任务。但 `job_timeout=1800` 只打日志从未生效（死代码）；`_run_with_timeout` 同样死代码。
- **说话人检测**：纯 LLM。首 50k 字符单次调用出人物表（含旁白必要性判断规则）；全书用迭代式增量检测（每批带上已知说话人列表，只找新人）；分段 = 对全书一次 LLM 调用返回 `{text, speaker_id, segment_index}`——**单次 8000 token 上限决定它撑不过一章**，它靠"一章一个子任务"绕开。JSON 修复用截断补全 hack。
- **TTS**：只用 `qwen_tts`，VoiceDesign 生成参考音 → Base 克隆合成；`<id>.pt` 预提取说话人嵌入文件（`load_voice_prompt` 重建 VoiceClonePromptItem，避免每任务重提取——**值得移植的机制**）。**串行单 worker**（daemon 线程 5s 轮询 DB），逐段合成。
- **已发现的真实 bug**（不要继承）：`worker_with_progress.py:919` 批量完成时 `TypeError`（传了不存在的 kwarg）；`/voices/generate` 端点 import 错误直接不可用；`CANCELLED` 无人设置；进度列 `progress_details` 从未被填。
- **API 面**：29 个路由；API.md 严重过期（只写 8 个）。人物表 CRUD + confirm 的 REST 形状可借鉴契约，不抄实现。
- **依赖**：requirements.txt 全 `>=` 不 pin；python 3.11；qwen-tts>=0.0.5。
- **无 ASR/质检**。

---

## 3. tts-audiobook-tool — 审计结论：Qwen3-TTS 调用规范的权威来源 + Provider 抽象样板

- **环境隔离机制（launch.py）**：每个 TTS 模型一个独立 venv；启动时在各 venv 内跑 `python -c` 探测 `importlib.util.find_spec` / `importlib.metadata.version`，恰好匹配一个模型才算有效 venv，然后用该 venv 的 python `os.execv`/`Popen` 重启 `-m tts_audiobook_tool`。**运行期一个进程只挂一个引擎**；推理再套一层 `multiprocessing` 子 worker（command/event 队列协议、20s 启动超时、faulthandler）。
- **引擎抽象**：`TtsBaseModel` ABC + `TtsModelSpec` NamedTuple 元数据目录（22 个成员：14 本地引擎 + 7 服务器变体），两层子类约定：`XxxBaseModel` 禁止 import 模型库（UI 层可安全全量导入）、`XxxModel` 才碰库。注册表 `Tts._MODEL_REGISTRY: type -> (base, factory, attr)`。**这就是我们 backend/tts/base.py + registry.py 的成熟范本。**
- **Qwen3-TTS 调用细节（全部值得照抄的规范）**：
  - 装法：`git+https://github.com/QwenLM/Qwen3-TTS.git@022e286b98...`（pin 到 commit，非 pip 版本号）
  - 加载：先 `snapshot_download`（离线友好）再 `from_pretrained(本地目录, device_map="cuda:0", dtype=bf16, attn_implementation="flash_attention_2" 若可导入)`
  - **采样参数必须镜像到 subtalker**：`subtalker_temperature/top_k/top_p`（talker=语义 token、subtalker=code_predictor，后者对音质影响更大）。默认 temp 0.9 / top_k 50 / top_p 1.0 / rep_pen 1.05。
  - 克隆：`create_voice_clone_prompt(ref_audio=path, ref_text=transcript, x_vector_only_mode=False)` → `VoiceClonePromptItem(ref_code, ref_spk_embedding, icl_mode, ref_text)`；prompt 缓存在 CPU；缓存键 = (realpath, transcript, mtime_ns, size)。
  - **滚动续接（仅 Base 模型、batch=1）**：把已生成 codes + 前文拼回 ICL prompt，上限 ~3 项，段落边界清空——**这是唯一能缓解跨段韵律漂移的现成机制**，Alexandria 没有。
  - `language="chinese"`（英文单词不是 ISO 码）；输出 24kHz float32；custom_voice/voice_design 用库级批量 API，base 模式自实现 `generate()` 以捕获 codec codes。
- **文本预处理**：pySBD 分句（引号感知、边界 offset 保留）→ phrase → `Reason` 枚举分类（SENTENCE/PARAGRAPH/SPACE_BREAK…）→ 每类映射到停顿时长表；对白自动检测（引号跨度）分配第二 voice index。全英文假设（引号字符、attribution 动词白名单）。
- **音频后链（成熟度最高）**：段内去静音+峰值归一(headroom 1dB) → 按 Reason 加停顿 → `limit_silence_gaps` 压段内长静音（librosa，且做时间戳重映射）→ **流式 ffmpeg stdin s16le PCM** concat → 两遍 EBU R128 loudnorm（第一遍解析 stderr JSON）→ M4B 章节化。段文件命名编码 index/内容哈希/模型tag/voice tag/失败次数（天然幂等+可追溯——正是 info.txt 要的"已确认音频不覆盖"的现成答案）。
- **依赖**：torch==2.8.0 / torchaudio==2.8.0（全仓库统一），base 含 faster-whisper、pysbd、librosa、mutagen 等；qwen3tts requirements 额外钉上面那个 git commit；无 transformers 显式 pin（走传递依赖）。

---

## 4. ebook2audiobook — 审计结论：电子书解析与 M4B 导出是两座金矿；核心 4390 行需大剥离

- **解析链**：一切先归一为 EPUB。txt 直接预处理；pdf 用 PyMuPDF 逐页 `get_text('xhtml')`、扫描页走 tesseract OCR（自动下 tessdata_best）；docx 用 python-docx、无文字时取内嵌图 OCR；mobi/fb2/rtf 等交给 **Calibre `ebook-convert` 子进程**（关键参数 `--chapter-mark=pagebreak --page-breaks-before "//*[name()='h1'..'h5']" --flow-size=0`；调用前净化 PYTHON*/conda 环境变量——**这个 Calibre 环境隔离技巧必须带走**）。
- **章节=EPUB spine 文档**（`get_blocks`，不依赖 TOC），`filter_blocks` 用 BeautifulSoup 把 h1-h4→标题+`[pause]`、表格线性化 `header: cell — ...`、跳过 `epub:type∈{frontmatter,backmatter,toc,...}`。
- **SML 标记体系**：`[pause]/[break]` 等标签 escape 到 U+E000 私用区字符再跑清理正则（防止被误伤）——小巧自包含，评级 A。
- **切句**：无 nltk；手写字符预算打包器，`language_mapping["zho"].max_chars=82`，硬/软标点集**已含中文 。！？，、**；中日韩泰走 jieba/nagisa 等分词后 `_join_ideogramms` 重打包。**中文分句在这里是现成的**（其他四仓全不支持）。
- **增量重解析**：`align_blocks/realign_blocks` 用 text_hash + difflib 把编辑后的 block 对齐回旧音频——断点续跑/编辑后重导出的正解，评级 A−。
- **状态存储**：三份（proxy + JSON×2 + SQLite blocks_current，WAL 模式，stamp/blocks/sentences 表）——SQLite schema 本身可直接当我们 `novel_chapters/paragraphs` 的蓝本。
- **音频装配**：句子→FLAC(24k) → ffmpeg concat demuxer 拼章 → `_generate_ffmpeg_metadata`（标准 ffmetadata `[CHAPTER] TIMEBASE=1/1000 START/END ms`，时长用 ffprobe 实测而非估算——info.txt 的担忧上游已解决）→ `_export_audio`（ffprobe 探测→编码或流拷贝快路径→mutagen 嵌封面）。无 Bookcorder。
- **冲突点**：`core.py` 顶部 `import gradio`；进度条从 `sys.modules['lib.gradio']` 反射取；`convert_ebook` 里有交互式 `input()`；Manager 全局 session 状态；CWD 相对路径 + 改 `tempfile.tempdir`；conf.py 里硬编码 Fernet key。→ 全部要剥离，只取算法层。
- **许可证**：Apache-2.0 文本（pyproject 误标 MIT；版权行是未填写的模板占位符——上游卫生问题，不构成使用限制）。再分发需带许可副本+变更说明。

---

## 5. qwen3-tts-audiobook — 审计结论：voice 准备流程 A 级、QC 架构可借、QC 代码对中文 D 级

- **voice_factory.prepare_voice**：ffmpeg 转 **mono/24kHz/pcm_s16le WAV** + 可选 trim + ffprobe 测时长；可选同名 `.txt` 转录文件存在与否决定 ICL/x-vector 模式。即插即用于我们 `backend/voices/`。
- **安全模式（评级 A）**：把不可信文本经 **stdin JSON** 传给子进程里的模型代码，而不是 f-string 拼进源码——注释记载了历史注入事故。我们跨进程传提示词时必须沿用。
- **克隆 API 实证**：`generate_voice_clone(text, language, ref_audio, ref_text)`（ICL）/ `x_vector_only_mode=True`（无转录）；md_to_audio 默认 x-vector（注释称去口音残留）、ICL 需显式开关。
- **多角色格式**：`[speaker]` / `[speaker;instruction]` 行首标签 + `[pause 1.5s]` + `#` 注释；speaker 名 = 声音文件名。**`;instruction` 在生成时被忽略（死代码）**；"情绪多角色书"实为预录情绪变体声音 + `EMOTION_MAP` 标签→文件名重写。
- **QC（validate_audio.py + transcribe.py）**：Qwen3-ASR `Qwen/Qwen3-ASR-1.7B`（支持中文、bfloat16/cuda）→ 词集 Jaccard 相似度 <0.5 判低质、词重复/音节 stutter/长词/辅音串 = 全部**基于空格分词的拉丁正则**；重试 5 次、前 3 次本地 ASR 后 2 次换云端 Groq Whisper"第二意见"；**任何 ASR 异常 = fail-open 放行**。ForcedAligner(0.6B) 只在 CLI timestamps 模式，未接入 QC。→ 架构照搬，检测器全部重写为字级 CER/编辑距离 + 中文标点逻辑；fail-open 策略要改成"标记复核"。
- **硬伤**：`venv_qwen3/bin/python` 与 `cuda:0` 到处硬编码（Linux only、无 CPU 回退）；tests/ 与 voices/ 只有 README 占位，**无任何测试**；md_to_audio 与 multi_speaker 整条 validate/retry/combine 栈代码重复；LUFS 注释 -16 实际 -14。
- 依赖：torch>=2.0（不 pin）、qwen-tts>=0.1.0、qwen-asr>=0.1.0，CUDA 走 cu121 index——与 Alexandria(cu128/transformers 4.57.3) 与 tool(torch 2.8.0) 三者互不兼容，见 dependency-conflicts.md。

---

## 交叉结论（五仓合并的唯一主实现裁定）

| 功能域 | 唯一主实现 | 来源 | 其余仓库该功能 |
|---|---|---|---|
| 剧本标注/审校 | Alexandria generate_script/review_script（提示词重写为中文） | Alexandria | ABG 的 speaker_detector 只借"迭代增量检测"提示词思路；E2A 无 LLM 标注 |
| 别名/人物档案 | Alexandria generate_personas（persona_refs + 别名解析，中文化） | Alexandria | 不引入 ABG detected_characters 双轨 |
| TTS Provider 抽象 | tool 的 TtsBaseModel/TtsModelSpec/registry 模式 + Qwen3 调用规范 | tts-audiobook-tool | 其余引擎只留接口 |
| Qwen3-TTS 实际调用 | qwen_tts 包（版本仲裁见 dependency-conflicts）；subtalker 参数、ICL 缓存、滚动续接 | tool + Alexandria 批量层 | ABG/q3ab 的实现不进入代码 |
| 切句/分段（中文） | E2A get_sentences 的 zho 分支（jieba + 中文标点集） | ebook2audiobook | 其余四仓的 `[.!?]\s+` 全部弃用 |
| 电子书解析 | E2A convert2epub/get_blocks/filter_blocks（剥 GUI） | ebook2audiobook | Alexandria 自带 extract_epub_text 太薄，弃 |
| 任务/进度/恢复 | 自建 SQLite 状态机；借 ABG 心跳+stuck 回收+两阶段 review 语义、E2A block/sentence 级断点、Alexandria chunk status | 自研为主 | — |
| 音频装配/响度/导出 | tool 的流式 ffmpeg + 两遍 loudnorm 链 为内部工序；E2A ffmetadata/M4B/封面嵌入 为成品导出 | tool + E2A | pydub 全链弃用（ABG/q3ab） |
| 声音工厂/voice profile | q3ab prepare_voice 流程 + Alexandria voice_config 四类路由 + 真 DB manifest | 三者合成 | tool 的项目内嵌样本管理不搬 |
| ASR 质检 | Qwen3-ASR 接入（q3ab 架构）+ 自写中文检测器 | q3ab 思路 | 检测代码不复制 |
