# 代码迁移矩阵

复用等级：**A** 复制即可运行 / **B** 少量修改 / **C** 只复用算法或业务逻辑 / **D** 只参考设计 / **E** 不使用。
所有"源文件:行号"均来自真实源码（见 source-audit.md）。无法确认的标注"待审计"。

## 一、剧本与人物（backend/story/）

| 源仓库 | 源文件:行 | 类/函数 | 功能 | 依赖 | 等级 | 目标文件 | 修改事项 | 风险 |
|---|---|---|---|---|---|---|---|---|
| alexandria | app/generate_script.py:13,88,158 | clean_json_string / repair_json_array / salvage_json_entries | LLM 脏输出 JSON 修复 | 无 | **A** | backend/common/json_repair.py | 无 | 低 |
| alexandria | app/generate_script.py:179 | fix_mojibake | CP1252 乱码修复 | 无 | **B** | backend/common/json_repair.py | 中文文本确认不适用后仅在导入 latin 文件时启用 | 低 |
| alexandria | app/generate_script.py:197 | split_into_chunks(max_size=3000) | LLM 输入切块 | 无 | **C** | backend/story/annotator.py | 句子边界 ` [.!?]` → 中文 `。！？；`、按段落优先 | 中文切错边界→标注质量下降 |
| alexandria | app/generate_script.py:233 | process_chunk(…, previous_entries) | 单块 LLM 标注调用 | openai SDK | **B** | backend/story/annotator.py | 中文化回看窗口(3条)与人物名册注入格式；换中文提示词 | 提示词不过关则归属错误率高 |
| alexandria | app/generate_script.py:370 | run_single_speaker | 单说话人模式(散文/独白) | openai | **B** | backend/story/annotator.py | 500字符切分→中文句段切分 | 低 |
| alexandria | app/review_script.py:23 | merge_consecutive_narrators(max_merged_length=800) | 相邻旁白合并 | 无 | **B** | backend/story/reviewer.py | 长度阈值改按中文字数 | 低 |
| alexandria | app/review_script.py:76 | review_batch(…, source_context) | 批量审校 LLM 调用 | openai | **B** | backend/story/reviewer.py | 中文对话归属/连续性规则重写提示词 | 同提示词风险 |
| alexandria | app/review_script.py:195 | check_text_loss(threshold=0.95) | 防 LLM 丢字安全闸 | 无 | **C** | backend/story/reviewer.py | 词计数→字符/句计数（中文无空格） | 不改造则闸失效 |
| alexandria | app/review_script.py:250 | main(–context-window 模式) | 上下文窗口式逐条审校 | openai | **B** | backend/story/reviewer.py | 并入 DB 驱动流程 | 低 |
| alexandria | app/generate_personas.py:53-117 | normalize_speaker_name / _token_jaccard / _resolve_to_canonical(0.4) | 说话人名归一/相似度合并 | 无 | **B** | backend/story/speaker_resolver.py | 中文人名/称谓切分（姓+名、晚晚、林小姐）；jaccard 改字级 | **高**：中文别名体系需重新设计 |
| alexandria | app/generate_personas.py:161 | _resolve_aliases_batch | 一次性 LLM 别名分组 | openai | **B** | backend/story/speaker_resolver.py | 中文提示词 | 中 |
| alexandria | app/generate_personas.py:307-349 | _load/_append_character_ref (persona_refs/*.json) | 人物档案累积 | 无 | **B** | DB 表 character_refs | 文件→SQLite；字段沿用(aliases/features/personality/voice_clues/relationships/sample_lines) | 低 |
| alexandria | app/generate_personas.py:445 | _save_generated_preview | VoiceDesign 试听+自动登记 clone 声音 | tts.TTSEngine | **C** | backend/voices/voice_factory.py | 改走统一 Provider；写 DB 而非 voice_config.json | 中 |
| alexandria | app/app.py:600-695 | _HTMLTextExtractor / extract_epub_text | 简易 EPUB→文本 | 无 | **E** | —（弃用） | 被 ebook2audiobook 链替代 | — |
| 自研 | — | context_manager（章节摘要/人物关系/近期事件） | 跨章节一致性 | LLM | 新增 | backend/story/context_manager.py | 全新实现，数据源=character_refs+章节摘要表 | 工作量被 info.txt 低估 |
| 自研 | — | continuity_checker | 换声/归属冲突检测 | — | 新增 | backend/story/continuity_checker.py | 基于 DB 校验,非 LLM 优先 | 中 |

提示词文件：`default_prompts.txt`(57行)/`review_prompts.txt`(83行)/`persona_prompts.txt`(23行) 均 **C** 级——结构、规则分类、占位符（{context}/{chunk}/{batch}/{speaker}/{sample_lines}/{character_ref}）照搬，文本全文重写为中文（引号「」『』、,"他说"句式、去掉英文数字读法规则）。

## 二、任务与生成（backend/generation/）

| 源 | 源文件:行 | 类/函数 | 功能 | 等级 | 目标 | 修改事项 | 风险 |
|---|---|---|---|---|---|---|---|
| alexandria | app/project.py:22-134 | group_into_chunks / MAX_CHUNK_CHARS=500 / _is_structural | 同 speaker+instruct 合并→500字 TTS 块 | **B** | backend/generation/chunker.py | 阈值按中文语速调；结构判定接中文标题表 | 低 |
| alexandria | app/project.py:136-175 | load_chunks/_resolve_alias(环检测) | 块加载/别名解引用 | **C** | repositories.py | 文件→DB 查询 | 低 |
| alexandria | app/project.py:715 | generate_chunks_parallel(ThreadPool) | 标准并发生成 | **B** | backend/generation/worker.py | 并入单 worker 状态机 | 低 |
| alexandria | app/project.py:834 | generate_chunks_batch(按 voice 类型分桶) | 快速批量生成 | **B** | worker.py | 同上；保留分桶思路 | 低 |
| alexandria | app/project.py:156-160 | chunk status 字段(pending/generating/done/error)+audio_path+pause_after | 块级断点 | **A** | audio_segments 表 | 即 DB 列 | 低 |
| ABG | worker_with_progress.py:267-313,513-723 | 两阶段 job(awaiting_review→confirm) | 人物表人工审校中断点 | **C**（无 license,只借语义） | job_service.py | 用显式状态 phase2_pending 替代"pending+characters非空"约定 | 低 |
| ABG | worker_with_progress.py:82-111,974-1042 + job_queue.py:437,494 | 心跳线程/_recover_stale_jobs/get_stuck_jobs/reset_job_for_retry | 崩溃恢复三件套 | **C**(同上) | worker.py | 移植语义;真正实现 job_timeout(上游是死代码) | 低 |
| ABG | tts_synthesizer.py:251-310 | load_voice_prompt(.pt 嵌入缓存) | 免重复提取说话人嵌入 | **C**(设计) | tts/qwen3/voice_cache.py | 缓存键学 tool:(path,transcript,mtime,size);存 .pt 需 qwen_tts 版本兼容验证——**待审计** | 中 |
| E2A | core.py:3794-3798 | 交互式 skip/resume input | 断点选择 | **E** | — | 改 job 策略字段 | — |
| E2A | core.py:2626-2777 | align_blocks/realign_blocks/text_hash/block_hash | 编辑后增量重解析+音频复用 | **A−** | generation/realign.py | 剥 session 全局 | 低 |
| tool | sound_segment_util.py:31-40,111 | 段文件名编码 [index][hash][model][voice][failcount] | 幂等/多版本可追溯 | **A** | 文件命名规范 | 直接采纳;解决 info.txt"不覆盖已确认音频" | 低 |
| tool | generation 事件/validator | 生成事件流/校验 | 进度 | **D** | progress_service.py | 自建 SSE/WebSocket | 低 |

## 三、TTS Provider 层（backend/tts/）

| 源 | 源文件:行 | 内容 | 等级 | 目标 | 修改事项 | 风险 |
|---|---|---|---|---|---|---|
| tool | tts_models/tts_base_model.py:22-167 | TtsBaseModel 两层子类契约(base 无重 import/model 才加载库)、generate 统一签名、错误返回字符串 | **A(模式)** | tts/base.py | 签名按我们 dataclass 请求/结果重写 | 低 |
| tool | tts_models/tts_model_type.py:26-77,85+ | TtsModelSpec 元数据目录(采样率/批量能力/替换表/requirements 引用) | **A** | tts/registry.py | 只留 qwen3 条目起步 | 低 |
| tool | tts.py:892-914 | _MODEL_REGISTRY 懒工厂注册 | **A(模式)** | registry.py | — | 低 |
| tool | tts_base_model.py:68-112 | 克隆 prompt 缓存键 (realpath,transcript,mtime_ns,size)、失败不污染缓存 | **A** | tts/qwen3/voice_cache.py | — | 低 |
| tool | qwen3_model.py:47-77 | snapshot_download→from_pretrained(dir, device_map, bf16, flash_attn 探测) | **A** | tts/qwen3/provider.py | 模型目录走我们 config | 低 |
| tool | qwen3_model.py:490-534 | **subtalker_temperature/top_k/top_p 镜像** + 默认 0.9/50/1.0/rep1.05 | **A** | provider.py | 无 | **不加 subtalker 参数=音质明显劣化**,最易踩的坑 |
| tool | qwen3_model.py:362-423 | generate_base_with_codes(自实现克隆推理以捕获 codec codes,按比例裁 ref 段) | **B** | provider.py 续接路径 | 与 qwen-tts 版本强耦合——升级需重验 | 中(版本锁) |
| tool | qwen3_base_model.py:37,130-144 | 滚动续接 ICL(≤3项/段落清空/仅 base+batch1) | **B** | provider.py | 中文段落边界判定 | 续接质量退化快 |
| tool | tts_model_type.py:659-682 | qwen3 spec: 24kHz 输出、language 'zh'→'chinese'、un_all_caps | **A** | provider.py | — | 低 |
| alexandria | app/tts.py:941-1100 | generate_batch 按类型分组/长度排序/sub-batch 显存估算(_estimate_max_batch_size KV 数学)/组间 empty_cache | **B** | provider.py 批量路径 | 剥 ROCm hack;3090 上验证 compile_codec | 中(编译路径 NVIDIA 未验证) |
| alexandria | app/tts.py:721-800 | 四类 voice 路由 custom/clone/lora/design + alias | **B** | provider.py | 路由配置从 DB 读 | 低 |
| alexandria | app/tts.py:285,424,629 | 设备解析 cuda→mps→cpu / torch.compile(max-autotune,dynamic) / unload_models | **B** | model_manager.py | 保留 GPU 让渡(Alexandria app.py:890 模式) | 低 |
| q3ab | scripts/voice_factory.py:171-216 | **stdin-JSON 传不可信文本给模型子进程**(防注入,有历史事故注释) | **A** | worker 进程协议 | 采纳为跨进程调用规范 | 低 |
| ABG/q3ab | 各自 worker | 单 daemon 线程轮询串行合成 | **D** | worker.py | 即我们单 worker 形态 | — |

## 四、电子书解析与导出（backend/ebook/ export/）

| 源 | 源文件:行 | 内容 | 等级 | 目标 | 修改事项 | 风险 |
|---|---|---|---|---|---|---|
| E2A | core.py:888-953 | normalize_epub_zip | **A** | ebook/zip_norm.py | 剥 session 调用(:940) | 低 |
| E2A | core.py:955-1263 | convert2epub(含 **Calibre 净化环境调用 :1189-1237**、PyMuPDF 拍平 :990-1039、txt 预处理 :983-989) | **B** | ebook/convert.py | 剥 show_alert/依赖检查 | 需装 Calibre(外部二进制) |
| E2A | core.py:515-607 | ocr2xhtml(tesseract+tessdata 自动下载+标题启发) | **B** | ebook/ocr.py(可选) | isupper/istitle 中文失效→改启发式或砍 | 中文扫描书另专项 |
| E2A | core.py:1314-1430 | get_blocks(spine 顺序=章,不靠 TOC) | **A−** | ebook/chapter.py | 剥 stanza | 低 |
| E2A | core.py:1432-1741 | filter_blocks._tuple_row(epub:type 跳列表/表格线性化/标题→pause) | **B** | ebook/normalize.py | SML 标记→我们的 marker 集 | 中(300 行精读移植) |
| E2A | core.py:2498-2559 + conf_models.py:26-47 | SML 标签 U+E000 转义/还原 | **A** | ebook/markers.py | — | 低 |
| E2A | conf_lang.py:103-135,633-640,901 | **中文标点硬/软集、章节词表(章/节/卷/回…)、zho max_chars=82** | **A** | ebook/zh_tables.py | 直接抄表(Apache-2.0 保留声明) | 低 |
| E2A | core.py:1743-2088 | get_sentences(jieba 分词+预算打包+孤儿合并 :1800-1849,2026-2057) | **B**(zh 路径) | ebook/sentence.py | 剥 SML 耦合与 GUI 进度 | 低 |
| E2A | core.py:609-846 | SQLite blocks/sentences/stamp WAL schema | **A−(蓝本)** | database/models.py | 并入我们的章/段/句三级表 | 低 |
| E2A | core.py:3396-3464 + 2986-3028 | concat-list ffmpeg 拼接 + -progress pipe:2 | **A** | export/ffmpeg_runner.py | 剥 gradio 反射 | 低 |
| E2A | core.py:3037-3110 | **_generate_ffmpeg_metadata(ffmetadata [CHAPTER] TIMEBASE=1/1000, ffprobe 实测时长)** | **A** | export/m4b.py | 标题清洗保留 | 低 |
| E2A | core.py:3112-3274 | _export_audio(ffprobe 探测→编码/流拷贝→mutagen 封面) | **B** | export/m4b.py | 剥 session/进度 | 低 |
| E2A | tts_engines/common/audio.py | get_audio_duration/get_audiolist_duration | **A−** | export/probe.py | — | 低 |
| E2A | lib/classes/subprocess_pipe.py:1-147 | ffmpeg 进度解析 | **B** | export/ffmpeg_runner.py | — | 低 |
| tool | sound_pipeline.py:102-134 + concat_util.py:234+,700-755 | 段后处理链(trim→peak norm→gap limit→流式 s16le PCM concat) | **B** | tts/audio/*.py | pySBD Reason→我们 marker 类型 | 低 |
| tool | loudness_normalization_util.py:60-131,195-215 | 两遍 EBU R128 loudnorm(I/LRA/TP 测量→套用) | **A** | tts/audio/normalize.py | 目标 LUFS 定 -16 | 低 |
| tool | reason_pauses.py:44-68 | 停顿时长表(按边界类型 0.5/0.9/1.2/2.0/2.5s) | **B** | generation/pause_policy.py | 中文小说节奏重调 | 低 |
| tool | m4b_chapter_util.py:12-51 | chapter 文件→ffmpeg | **A(与 E2A 二选一)** | — | **裁定用 E2A 版**(与导出链一体) | — |
| alexandria | project.py:541,650 | merge_m4b + 英文标题正则 | **D** | — | 被 E2A 链替代;标题正则换中文表 | — |

## 五、声音管理与质检（backend/voices/ qc/）

| 源 | 源文件:行 | 内容 | 等级 | 目标 | 修改事项 | 风险 |
|---|---|---|---|---|---|---|
| q3ab | voice_factory.py:49-125 | prepare_voice: ffmpeg mono/24k/pcm_s16le+trim+ffprobe | **A** | voices/voice_factory.py | venv_qwen3/cuda 硬编码→config | 低 |
| q3ab | voice_factory.py:127-320 | test_voice/clone_voice ICL↔x_vector_only 切换 | **B** | 同上 | 走统一 Provider 而非子进程内嵌脚本 | 低 |
| q3ab | voices/ 命名约定(<name>.wav+<name>.txt) | 转录存在性=模式开关 | **C** | voice_profiles 表 | **升级为真 manifest(DB 行)**:语言/性别/模型/版本/来源——上游本就没有,勿假装有 | 低 |
| q3ab | map_emotions_to_voices.py:18-65 | EMOTION_MAP 情绪→声音变体文件名 | **C** | character_voice_bindings | 情绪变体建模为独立 voice 版本+绑定表 | 低 |
| q3ab | transcribe.py:49-126 | Qwen3-ASR-1.7B 封装(bf16/cuda/batch32)+ForcedAligner 加载 | **B** | qc/asr.py | Groq 云回退改本地或删;显存调度按任务级 | 中(ASR+TTS 共卡) |
| q3ab | validate_audio.py:77-267 + md_to_audio.py:409-443 | QC 流程架构(转录→检测→比对→带模型切换的重试) | **A(设计)** | qc/*.py | — | 低 |
| q3ab | 同上检测器 | Jaccard 词集/词重复正则/stutter 正则/gibberish | **E**(中文全失效) | qc/zh_check.py | **重写**:字级 CER(difflib/编辑距离)、连续字重复 `了了了`、n-gram 片段重复、中文标点边界 | 不重写=QC 形同虚设 |
| q3ab | md_to_audio.py:332-337 | QC 异常 fail-open 放行 | **E** | qc/quality.py | 改"标记复核"状态,不静默通过 | 低 |
| alexandria | app.py:242 + tts.py:730 | VoiceConfigItem 五型路由字段 | **B** | voice_profiles 表 | JSON→DB;design/clone/custom/lora 语义保留 | 低 |
| alexandria | 内联 get_voices(app.py:833) | 从脚本提取说话人清单 | **B** | voices/voice_import.py | info.txt 的 parse_voices.py 不存在,从 app.py 剥 | 低 |

## 六、前端（frontend/，Vue 2 重建）

| 源 | 内容 | 等级 | 说明 |
|---|---|---|---|
| alexandria app/static/index.html(4097行) | 5 tab 流水线(Setup/Script/Voices/Editor/Result)+逐块编辑表+试听队列+声音卡片+别名下拉 | **C(交互蓝本)** | vanilla+Bootstrap;交互流程、字段布局、轮询节奏(状态轮询)是完整参考;代码不搬 |
| ABG frontend | 单页 vanilla;人物审校 modal + 2s 轮询 | **C** | awaiting_review 的人物表编辑 UI 是 confirm 流程的最佳参考 |
| tool browser_player | 同步阅读器/播放列表/睡眠定时 | **D** | 阅读器同步需要 E2A build_vtt_file 式字幕侧车才成立,一期不做 |
| E2A gradio.py(3068行) | 块编辑器/进度条 | **D** | 只借"块级勾选重生成"交互概念 |

## 七、明确不使用（E 级）清单

- ABG 全部源码文件（无许可证文本;仅其**状态机语义与提示词工程**以自有实现重述）——database/models/job_queue/tts_synthesizer 的表结构与循环逻辑 Alexandria+自研已覆盖。
- tool 的 Textual UI、conversation/chat、SGL-Omni 服务器变体、enhance 对齐工具链（一期）。
- E2A 的 gradio.py、device_installer.py(2001行 uv 安装器)、argos 翻译、tts_engines/*(8 个引擎适配)、conf.py 的 Fernet/HF token 机制。
- q3ab 的 tts_ui.py、Makefile、examples(英文样例)。
- Alexandria 的 pinokio/install.js 启动器(目标为 Ubuntu 手动部署)、builtin_lora 预置(英文音色)。
