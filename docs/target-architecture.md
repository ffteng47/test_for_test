# 目标架构（novel-audiobook）

裁定前提（用户已确认）：运行机 = Ubuntu 24.04 + RTX 3090 24GB + 256GB RAM；本机 Windows 仅开发/审计；**SQLite + 单 Worker，不引入 MySQL/Redis**；LLM 走本地 Qwen（Ollama/OpenAI 兼容端点，config 化）；前端 Vue 2。

## 1. 进程拓扑与 GPU 所有权

单卡 3090 上"API、LLM、TTS、ASR 不同时加载多个大模型"是第一约束。采用 **3 进程 + 显存让渡协议**，直接沿用审计确认存在的三个上游机制：

```
┌─────────────────────────────────────────────────────────┐
│ api (uvicorn, 端口 4200)                                 │
│   FastAPI：全部业务路由；不碰 GPU（除 nvidia-smi 读数）      │
│   └─ 写 SQLite jobs 表 = 唯一任务提交方式                  │
├─────────────────────────────────────────────────────────┤
│ annotator 子进程（按需，CPU/网络）                         │
│   generate_script/review/personas 的移植体（openai SDK →  │
│   本地 Qwen 端点）。上游模式:启动前 api 置 engine=None+gc   │
│   (alexandria app.py:890) —— LLM 阶段不占卡，TTS 阶段才加载│
├─────────────────────────────────────────────────────────┤
│ worker 子进程（常驻，GPU 唯一持有者）                       │
│   持有 tts.qwen3 provider（≤3 个 1.7B 模型 + LoRA 热切换） │
│   ASR 以"任务级加载/用完卸载"入同一进程（串行于 TTS 批次间）  │
│   协议：stdin JSON / stdout JSON 行（q3ab 防注入模式 A）    │
│   段文件命名/幂等：tool 的 [idx][hash][model][voice][fail] │
└─────────────────────────────────────────────────────────┘
```

- TTS 模型生命周期照抄 tool：`snapshot_download` → `from_pretrained(local_dir, bf16, flash_attn 探测)`；subtalker 参数必带。
- ASR（Qwen3-ASR-1.7B bf16 约需 3.5GB）与 TTS 1.7B bf16 约 3.4GB×N 可共存于 24GB，但**默认串行**：TTS 批量结束后在 worker 内加载 ASR 跑 QC，跑完 unload（alexandria `unload_models` 模式）。VoiceDesign 试听同样走 worker 排队，绝不并发。
- 环境隔离：worker 独立 venv（tool 的多 venv 思想收敛为"每 GPU 角色一个 venv"）；api/annotator 一个轻量 venv。二期若加别的 TTS 引擎，按 tool 的 module-probe 选 venv 机制扩展，不改主进程。

## 2. 数据层：SQLite schema（WAL 模式，表名沿用 info.txt 设计）

状态全在 DB，音频/文本在文件系统，两侧以路径+哈希相连。蓝本 = E2A `blocks/sentences/stamp` WAL schema（core.py:609-846）+ Alexandria `chunk status` 字段（project.py:156-160）+ ABG 两阶段语义（重述为自有实现）。

```sql
-- 项目与原文
novel_projects(id, title, author, lang DEFAULT 'zh', created_at)
novel_chapters(id, project_id→, index, title_raw, title_norm,
               source_path, source_locator,          -- 原始文件+定位(E2A spine doc 级)
               status)                               -- parsed/annotated/generated…
novel_paragraphs(id, chapter_id→, order, raw_text, clean_text,
                 char_start, char_end)               -- 原文↔清理文本映射，回链音频
-- 人物与声音
novel_characters(id, project_id→, canonical_name, profile_json) -- persona_refs 结构入库
character_aliases(id, character_id→, alias, kind)               -- 含"晚晚/林小姐"字级别名
voice_profiles(id, name, provider DEFAULT 'qwen3', model, mode, -- design/clone/custom/lora/
               ref_audio_path, ref_text, language, version, locked, created_at)
character_voice_bindings(id, character_id→, voice_id→, bound_at, note)
                                                                  -- 换声不动剧本
-- 脚本与音频（分离是硬要求：同段可多版本、可选定旧版）
script_segments(id, chapter_id→, order, kind,          -- narration|dialogue|heading
                character_id→ NULL, text, instruct, marker_json,
                source_paragraph_ids_json,             -- 回链原文，可追溯
                confirmed INT DEFAULT 0)
audio_segments(id, script_segment_id→, job_id→, version,
               audio_path, duration_ms, sr, status,    -- pending/generating/done/error/review
               qc_status, qc_detail_json, created_at)
generation_jobs(id, project_id→, chapter_id NULL, kind, -- annotate|review|persona|tts|qc|export
                phase, status,                          -- phase: 1|2 (ABG 两阶段显式化)
                progress, progress_msg, error,
                last_heartbeat, retry_count, max_retries DEFAULT 3,
                created_at, started_at, completed_at)
audio_exports(id, project_id→, job_id→, format, path, metadata_json, created_at)
```

要点：
- `script_segments` 与 `audio_segments` 分表（info.txt 强调，上游均无）。用户"选定第 2 次生成" = `audio_segments.status='chosen'` 参与导出，`confirmed` 段落拒绝被自动重生成覆盖（幂等，tool 文件哈希命名兜底）。
- 恢复：worker 启动即执行 ABG 语义——`status='running'` 的行按 `last_heartbeat` 超时(建议 120s)回收为 `pending/retry`，超过 max_retries 置 `failed`；job 内断点用 E2A `block_resume/sentence_resume` 式游标 + align_blocks 文本哈希做增量重跑。
- 进度：api 对前端提供 SSE 或 2s 轮询（ABG 模式）；`progress` 沿用 Alexandria 的阶段百分比带，但真实数据源是 audio_segments 计数。

## 3. 后端代码结构（backend/，FastAPI，Python 3.12）

```
backend/
├── api/          books chapters characters voices scripts generation exports jobs
├── story/        annotator reviewer persona speaker_resolver(移植+中文化)
│                 context_manager continuity_checker(自研) prompts/zh_cn_*.txt
├── ebook/        convert(Calibre/PyMuPDF) chapter(blocks) normalize filter_blocks
│                 sentence(jieba+中文标点) markers(SML) zh_tables
├── tts/          base.py registry.py model_manager.py
│                 qwen3/{provider,voice_cache,continuation}.py audio/{normalize,silence,concat}
├── voices/       voice_factory prepare(q3ab A级) voice_manager voice_binding
├── generation/   job_service worker segment_scheduler pause_policy realign retry_policy
│                 progress_service
├── qc/           asr(Qwen3-ASR) zh_check(字级CER/片段重复) quality(复核状态机)
├── export/       ffmpeg_runner concat m4b(ffmetadata+封面) mp3 probe validator
├── database/     models.py repositories.py migrations.py(轻量自研,不用alembic也可)
├── common/       json_repair atomic_write(→sqlite 化后可删)
└── main.py
```

## 4. API 契约（一期）

REST，前缀 `/api`；形状糅合 Alexandria 路由表 + ABG confirm 流。

| 路由 | 用途 |
|---|---|
| POST /books（multipart epub/txt/docx/pdf）→ GET /books/{id}/chapters | 导入+解析预览（章节树、可勾选跳过） |
| POST /jobs {kind:annotate|review, chapter_ids} | 标注/审校任务 |
| GET /scripts/{chapter_id} · PATCH /segments/{id} · POST /segments/{id}/confirm | 逐句编辑+锁定 |
| GET /characters · POST /characters/resolve(重跑别名) · PATCH 改名/合并 | 人物管理 |
| GET/POST /voices · POST /voices/{id}/preview · POST /voices/clone(样本上传→prepare) | 声音工作室 |
| POST /bindings {character_id, voice_id} | 角色↔声音 |
| POST /jobs {kind:tts, chapter_id, segment_ids?} · POST /jobs/{id}/cancel | 生成/局部重生成 |
| GET /jobs/{id} · GET /jobs/{id}/stream | 进度 |
| POST /jobs/{id}/review-characters · POST /jobs/{id}/confirm | ABG 两阶段人物审校 |
| POST /jobs {kind:export, format:mp3|m4b, chapter_scope} · GET /exports/{id}/download | 导出 |
| GET /system/stats（nvidia-smi/磁盘） | 沿用 alexandria /api/system/stats |

## 5. 前端（Vue 2 + 现有构建栈）

五个视图对应流水线：BookImporter(章节树预览) → ScriptEditor(逐句:说话人/文本/instruct/确认锁/试听) → CharacterManager(别名合并、绑定声音) → VoiceStudio(样本上传→prepare→clone 试听→版本列表) → GenerationBoard(任务队列、进度条、段落级重生成、QC 复核队列) + AudiobookPlayer(章节时间轴播放,M4B 侧车 JSON 章节表)。
交互蓝本 = alexandria index.html 的 Editor/Voices tab + ABG 的 character review modal。

## 6. MVP 边界（对齐 info.txt 最终建议，砍掉一期不做的）

**一期**：EPUB/TXT 导入→章节/段落入库→中文标注(重写提示词)→人物+别名→声音 design/clone+绑定→逐句编辑确认→Qwen3-TTS 批量(带 subtalker 参数与幂等命名)→章节 MP3 + 整本 M4B(ffmetadata 实测时长)→断点续跑+心跳回收。
**二期**：ASR 质检闭环、context_manager/continuity_checker 全书一致性、DOCX/PDF/Calibre 全格式、Audacity 工程导出、LoRA 声线训练、VTT 同步阅读。
**不做**：多用户/权限、分布式队列、其他 TTS 引擎（registry 只留接口）、在线 ASR 回退。
