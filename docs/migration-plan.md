# 实施迁移计划

前置：本文档假设 source-audit.md / migration-matrix.md / target-architecture.md / dependency-conflicts.md 已读。
信息原则：所有指向"复制/修改"的条目均为审计确认存在的真实文件与函数；自研项显式标注。

## 第 0 步（开发机，现在就能做）

- 建仓库 novel-audiobook（backend/frontend/docs/deploy/models/data + tests），git init，保留 upstream/ 于 .gitignore（60MB+，且 SHA 已记录）。
- `deploy/bootstrap.sh`：Ubuntu 3090 机上建 venv-app/venv-gpu 并按 dependency-conflicts §3 落 pin；含 precheck 清单脚本。
- **待上机首验**：qwen_tts 版本裁定流程（pip 版 API 面核对 → 决定 git pin 与否）。这是整个计划唯一的外部不确定点，安排在任何 GPU 工作之前。

## 阶段 1：直接跑通 Alexandria 基线（Ubuntu 机，不写新代码）

目的：验证 3090 上全链真实可用 + 拿基线数据，而不是先改造。

1.1 克隆 alexandria@be6343d 独立运行，装 torch2.7/2.8-cu128 + qwen-tts==0.1.1 + requirements（14 pin）。
1.2 接 Ollama Qwen（改 config.json llm.base_url/model），灌 3–5 章中文小说（TXT），跑：标注→人物→声音设计→批量生成→MP3。
1.3 验收标准 = 基线记录：依赖版本清单、`nvidia-smi` 峰值显存、单 chunk(500字)生成秒数、批量模式(sub_batch)实测吞吐、标注归属错误率人工抽样 50 条、英文提示词在中文上的失效清单（引号/称谓/数字读法各记几例）。
1.4 顺手验证三件事：flash-attn 在 py312+torch2.8 是否有可用 wheel；compile_codec 在 NVIDIA 首次 autotune 耗时；M4B 导出在装好 ffmpeg 的 Ubuntu 上是否直接可用。
产出：docs/baseline.md。

**退出条件**：能产出一章可听的中文样书。若 LLM 标注中文质量不可接受，先停——问题定位到提示词，进阶段 2 时提示词重写优先级提到最高。

## 阶段 2：后端骨架 + 核心移植（开发机为主，~可并行）

2.1 database/：SQLAlchemy models + repositories，按 target-architecture §2 建表；migration 用 create_all + 手写 upgrade 脚本（个人项目不上 alembic）。
2.2 common/json_repair.py ← Alexandria 三函数（A 级复制，头部注释记 SHA）。
2.3 ebook/：convert.py + chapter.py + normalize.py + sentence.py + zh_tables.py + markers.py ← E2A 剥离（B 级改造：删 gradio 反射/session/show_alert；EPUB+TXT 先行，PDF 次之，mobi 挂起）。数据落 novel_chapters/novel_paragraphs（含原文定位映射）。
2.4 story/：annotator.py + reviewer.py ← generate_script/review 移植 + **中文提示词全文重写**（zh_cn_annotator/zh_cn_persona/zh_cn_reviewer.txt；规则含「」引号、"他说"句式、中文称谓）；speaker_resolver.py ← generate_personas 别名机制移植+中文化；persona.py 落 DB。
2.5 单测：json_repair、split_into_chunks(中文)、get_sentences(zho 预算打包)、ffmetadata 生成（fixture：3 章中文样例放 tests/fixtures/）。

验收：`POST /books`(epub) → chapters/paragraphs 入库 → annotate 任务 → script_segments 产出 → 人物/别名入库。纯 CPU 可全程开发，不碰 3090。

## 阶段 3：GPU worker + TTS Provider

3.1 tts/base.py + registry.py ← tool 的两层子类+Spec 目录模式（A 模式级）+ qwen3/provider.py ← snapshot_download/from_pretrained 加载、**subtalker 参数镜像**、公开三调用（A 复制 q3ab/alexandria 的公开 API 用法）。
3.2 voice_cache.py：克隆 prompt 缓存键 (realpath,transcript,mtime_ns,size)；.pt 嵌入持久化按阶段 0 结果决定。
3.3 voices/：voice_factory.py ← q3ab prepare_voice（ffmpeg 24k/mono/pcm_s16le + ffprobe，A 级）；VoiceDesign 试听→自动登记 clone voice（流程抄 generate_personas._save_generated_preview，落 DB）。
3.4 generation/：job_service（显式状态机含 phase2_pending）+ worker.py：轮询 SQLite、ABG 心跳/启动回收/stuck 判定（语义重写，非抄码）、段状态游标断点、tool 式文件命名幂等、E2A align_blocks 式重对齐复用。
3.5 批量路径：先串行单 worker 打通（ABG 形态），再并入 Alexandria generate_batch 分组/排序/限批逻辑（B 级）；续接策略按阶段 0 裁定（有 git pin 才做滚动 ICL）。
3.6 qc/：一期只建表+状态占位（qc_status），检测器二期。

验收：整本样书逐段 audio_segments 全部 done；kill -9 worker 后重启只补缺失段；改一句 instruct 重跑该段，旧版本仍在表里。

## 阶段 4：导出 + Vue 2 前端 + 端到端

4.1 export/：ffmpeg_runner(concat-list+progress 解析) + m4b(_generate_ffmpeg_metadata + _export_audio 剥离版 + mutagen 封面) + mp3；validator=ffprobe 实测时长对表，拒绝估算值。
4.2 frontend：Vue 2 + vue-router + axios。五视图按 target-architecture §5。ScriptEditor 是第一交互核心（逐句改 speaker/text/instruct、试听、确认锁、局部重生成按钮直连 jobs API）。轮询 2s + 后换 SSE。
4.3 端到端验收（= info.txt 阶段 4 的"完整生成一本中文小说"）：导入 20 章+ EPUB → 标注 → 人物修正 → 10 角色绑声 → 全量生成 → 抽 3 章人工听 + 逐句回链原文核对 → 导出整本 M4B（章节可在播放器跳转、时长与表一致）→ 中途断电重启续跑一次。

## 里程碑与顺序依赖

```
S0 上机 qwen_tts 裁定 ─┬─ S1 Alexandria 基线(拿数据) ─┐
                       └─ S2 骨架/移植(CPU, 并行做) ───┴─ S3 worker/TTS ─ S4 导出/前端/E2E
```

关键顺序律（info.txt 第八节原则,审计后确认正确）：先 S1 后改造——基线数据决定阈值/停顿表/是否 git pin；S2 与 S1 可在两台机并行。

## 必须自研清单（上游不存在、无现成可抄——工期主力）

1. **中文提示词三件套 + 中文归属规则**（影响全局质量）
2. **SQLite 数据层与状态机**（含 script/audio 分离、版本选择、幂等锁）
3. **context_manager + continuity_checker**（全书一致性；persona_refs 给了素材,聚合与检测逻辑没有）
4. **中文 speaker 别名体系**（姓/名/小称/亲属称谓归并规则）
5. 停顿/合并策略的中文语感调参
6. Vue 2 全部前端
7. （二期）中文 ASR QC 检测器：字级 CER + 片段重复 + 标记复核闭环（q3ab 架构复用、代码全换）

## 风险登记（审计发现，按优先级）

| 风险 | 证据 | 缓解 |
|---|---|---|
| 跨 chunk 韵律漂移（音色/情绪不接续） | alexandria 无续接;tool 续接需私有 API | 阶段0裁定 git pin;不行则 instruct 强化 + QC 复核 |
| qwen_tts 私有 API 随版本漂移 | tool pin 具体 commit;alexandria 也调私有路径 | requirements/gpu.lock 硬锁;升级走专项验证 |
| 中文标注错误率未知 | 英文提示词直用必差 | S1 基线量化 + S2 提示词重写 + 人工审校 UI 兜底 |
| Calibre/tesseract 二期引入面 | E2A 硬依赖 | 一期 EPUB/TXT/PDF/DOCX 不装 Calibre |
| flash-attn 编译失败 | tool/alexandria 均有降级探测路径 | 探测失败自动走 sdpa,仅损失速度 |
| 3090 显存争用(VoiceDesign/ASR/TTS) | 模型均 1.7B bf16 | worker 内串行状态机强制互斥 |
