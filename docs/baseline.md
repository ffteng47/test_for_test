# 部署基线记录（2026-10-03）

## 端到端 Demo 验收（首次全链路走通）
《青石巷》835 字样例：**上传 → qwen3:8b 中文标注(16条) → VoiceDesign 四角色 → 16 段配音 → Play Sequence → Merge → MP3/M4B 导出**，全程约 40 分钟。

产物：`alexandria/cloned_audiobook.mp3`（64.4s）、`alexandria/audiobook.m4b`（64.4s，16 章节书签、中文元数据 title/artist/date 正确）。

关键教训（已写入设计约束）：
1. **英文提示词会把中文小说翻译成英文并丢内容** → 已换中文标注提示词（`prompts/zh_cn_annotator.txt`，占位符协议 `---SEPARATOR---`/`{context}`/`{chunk}` 不变，配置键 `app/config.json:prompts.system_prompt/user_prompt`）
2. **8B 模型仍有归属错误**（叙述误归角色、JSON 键幻觉出 `"错别字"`）→ 必须做 Review 二次审校 + 归属校验（对应自研 speaker_resolver/continuity_checker）
3. **Persona 描述必须显式声明性别+年龄**，否则 LIN WAN/LAO ZHOU 都会出男声；修复工具：`deploy/fix_speaker_voice.py`（参数化 SPEAKER/DESC/REF_TEXT，重造音色→改 ref_audio→删旧段）
4. **Ollama 新装必须手动解完整 `ollama-linux-amd64.tar.zst`**（自动脚本装的缺 llama-server；GitHub 直连 76KB/s，用 gh-proxy.com 或本机下载后 scp）
5. Audio Editor 的补生成是幂等的：删掉某角色的 mp3 后 "Generate audio for all unrendered chunks" 只重做缺失段，约 15 秒/段

## Review 流水线修复验证（同日第二轮）
- **缺陷**：`review_script.py:check_text_loss` 用空格分词计数，中文整句=1"词"，LLM 任何拆分/合并都被误判丢文本并整批回滚 → Review 恒显示 "No issues found"（假工作）。
- **补丁**：`deploy/patches/apply_cjk_textloss_patch.py`（CJK 字符逐字计单元，拉丁词不变；原文件 `.bak` 可回滚；子进程模型无需重启）。
- **验证**：qwen3:8b + 中文标注/审校提示词，20 处修复、6/6 归属变更全对（陈默↔林晚↔旁白↔老周均正确）。
- **残留缺陷**：标注随机丢字 6~25 汉字/237（Review 无原文输入，无法找回）→ 必须自研 continuity_checker（对照源文本做字符级完整性校验+定点重标注）。对白条目仍带外层引号（无害但应清理）。
- **结论**：8B+双中文提示词+补丁 Review 已达"可用"，阶段2 优先级：continuity_checker > speaker_resolver 别名表 > 14b 评估。

## 远程机器
- Ubuntu 24.04 / RTX 3090 24GB（driver 595.91.07）/ 64 核 / 251GB RAM / 346GB 磁盘
- 部署根：`/home/tff/software/novel-audiobook/`

## 组件状态
| 组件 | 状态 | 证据 |
|---|---|---|
| Alexandria (`alexandria/`, commit be6343d) | ✅ 服务运行 :4200 | `start_novelTTS.sh` → `NOVEL_TTS_UP`，HTTP 200 |
| Ollama systemd | ✅ active，qwen3:8b 已拉取（5.2GB） | `http://localhost:11434/v1` 就绪 |
| Qwen3-TTS 3 模型 | ✅ `MODELS_READY`，hf-cache 13G | CustomVoice / Base / VoiceDesign snapshots |
| GPU 推理 | ✅ VoiceDesign 加载并合成中文成功 | 31 行文本 8.4s（含加载），峰值显存 4.37GB |
| mineru 共存 | ✅ 未受扰动，常驻 6.8GB | nvidia-smi used=6857MiB |

## 显存预算（24GB）
mineru 6.8 + TTS 峰值 4.4 + ollama qwen3:8b ~5.5 ≈ 16.7GB → 余量 ~7GB，14b 需 `OLLAMA_KEEP_ALIVE` 短驻或错峰。

## 运维入口（mineru 同风格）
- 启动：`./start_novelTTS.sh`（venv/GPU/ffmpeg/显存≥8000MiB/磁盘/LLM 端点逐项检查，40×2s 健康轮询）
- 停止：`./stop_novelTTS.sh`（pidfile + pkill 兜底 + 残留扫描）
- 模型：`./download_models.sh`（hf-mirror，共享 HF_HOME=hf-cache）

## 前端
- `novel-audiobook/frontend/`：Vue 2.7 + Vite 5，5 视图（导入/剧本/角色声音/生成车间/母带导出）+ 传输条，mock 数据形状对齐 SQLite 契约。
- 构建产物 gzip：JS 47.5KB / CSS 4.4KB；Qoder Site 草稿 `novelaudio-studio-cnuaoea8udr.qoder.website`（未发布）。

## 待办
- qwen3:8b 中文剧本标注质量实测 → 决定是否上 14b
- 后端按 target-architecture.md 阶段 2-4 落地（annotator/speaker_resolver/worker/export）

## 联调版写路径（2026-10-04）
- 三层结构（可维护性优先）：`api/client.js` 只做传输；`api/actions.js` 唯一写入口（动作→track 轮询 /api/status→刷新数据切片）；`data/store.js` 拆为 loadSystem/loadChunks/loadVoices/loadJobs/loadExports/loadContinuity 细粒度 loader，组件零 fetch。
- 已接通动作：上传书稿(/api/upload multipart)、重新标注、复查、上下文复查、批量生成 pending 段、重试失败段、单段重生成、段编辑落库(text/instruct，PATCH 语义 exclude_unset)、音色设计 generate_personas、save_voice_config 透传原始 config（引擎无关：clone/design/custom/lora 均为后端 config 字段，前端不硬编码引擎）、cancel_audio、merge MP3、merge_m4b（元数据表单）、/api/audiobook HEAD→导出库、真实 HTML5 播放（段音频 /voicelines/*.mp3、成品 /api/audiobook、预览 /designed_voices，单例 `audio/player.js` 状态回写 store.transport）。
- UI：toast 浮层（成功/警告/错误）、按钮 busy 防重、Studio 队列行实时日志尾行、Export 校验面板改为字级一致率实算（无 continuity 时回退示意文案）、Import 上传后自动触发标注。
- 后端写路径冒烟：POST /api/chunks/0/generate → status/audio → chunk0 done，audio_path=voicelines/voiceline_0001_narrator.mp3。
- dev 代理：vite proxy /api、/voicelines 等 → VITE_API_TARGET（默认 3090:4200），npm run dev 即 LIVE。
- 模型库（HF_HOME=…/hf-cache，全部 [OK]，共 21G）：Qwen3-TTS 1.7B Base/CustomVoice/VoiceDesign + 新增 0.6B-CustomVoice、0.6B-Base（快速草稿档）+ Systran/faster-whisper-large-v3（ASR 质检用，已 pip 安装进 venv）。`deploy/download_extra_models.sh` 可重复续传。
- 未接（下一步）：ASR 质检任务（faster-whisper 跑转录一致性）、参考音频上传 UI、WAV/Audacity 导出、SQLite 多项目。

## 联调版（2026-10-04）
- continuity_checker：`deploy/continuity_check.py` → 远端 `alexandria/app/continuity_check.py`。归一化（CJK+alphanumeric，去标点）后 SequenceMatcher 字级对齐，逐 chunk 归因 missing/added，状态 ok/gap/drift。路由 patch `add_continuity_route.py`（GET /api/continuity，app.py 备份 .bak_pre_continuity）。demo 验证：237/237 sim=1.0；截断+加字回归 → 正确报 gap/drift。前端 hydrate 时拉取该报告，剧本工作台质检面板显示每段 ✓/⚠ 与全卷一致率。
- dev 模式 LIVE：vite.config.js 代理 /api、/voicelines 等 8 个前缀到 `VITE_API_TARGET`（默认 http://192.168.31.213:4200），`npm run dev` 直接进 live 模式。
- 后端 patch `deploy/patches/serve_studio_frontend.py`：`/` 托管 `alexandria/studio/`（Vue dist，hash 路由，assets 走 StaticFiles 挂载），旧 Alexandria UI 移到 `/legacy`；app.py 备份 `app.py.bak_pre_studio`，幂等。
- 前端新增 `src/api/client.js`（同源 fetch + 超时）与 `src/data/store.js`（reactive 深克隆 mock，`hydrate()` 探活 `/api/system/stats`，成功则映射 chunks/voices/status/stats/config/audiobook 到 mock 同形字段，`store.mode='live'`；失败静默回退 mock，Qoder Site 演示不受影响）。App.vue mounted 水合 + live 模式 15s 轮询，顶栏显示 LIVE/演示数据 徽标。
- speaker 归一化：`'CHEN MO'→chenmo`、`'LAO ZHOU'→oldzhou`（别名表）、`'NARRATOR'→narrator`，未知说话人按调色板分配颜色。
- StudioView 待生成/失败段计数改为从 store.segments 实算。
- 部署：`npm run build` → scp dist → `python3 /tmp/serve_studio_frontend.py` → stop/start_novelTTS.sh。入口 http://192.168.31.213:4200/（live），https://novelaudio-studio-cnuaoea8udr.qoder.website（mock 演示）。
- 已知边界：传输条播放仍为视觉 mock（未接 /api/audiobook 音频）；写路径（生成/编辑/合并按钮）尚未接通，属"联调版写路径"阶段。
- ⚠ 机器 10-04 01:20 重启过：ollama 自启正常，mineru 未自启（需用户手动拉起）。

## 后端产品层 v1：SQLite + 规则引擎 + ASR 质检 + 三层记忆（2026-10-04，alexandria/backend/）
- `noveldb.py`：stdlib sqlite3（WAL、FK CASCADE），表 projects(bible JSON)/characters/chapters/scenes/segments/audio_versions(chosen=1)/jobs；`Db.segments()` LEFT JOIN 出音频路径，读路径统一入口。DB 位于 `alexandria/novelaudio.db`。
- `domain.py`：前后端共享契约——KEY_ALIASES（与 frontend/store.js 同步）、speaker_key、is_dialogue、workspace_paths。
- `sync_state.py`：工作区 JSON→DB 幂等搬运（引擎仍写文件，本表为"以库为准"快照）；实测 259 段/11 人物全量同步。
- `rules.py`：确定性规则引擎，RULES 元组可插拔——unknown_speaker/quote_form/duplicate_adjacent/attribution_residue/emotion_jump/pause_sanity/missing_audio；`--write` 置 qc=retry，报告 `alexandria/rules_report.json`；自带 --selftest。抓到真实缺陷 #156 duplicate_text。
- `asr_qc.py`：faster-whisper large-v3 fp16 逐段回听，err=1−相似度，>8% 标 retry。两级去误报：pypinyin 拼音层比对（同音字 云雯/云文、繁简、标点归零）+ 阿拉伯数字↔中文数词逐位映射（三↔3）；待复核从 56→9。ffmpeg 解码绕 PyAV 坑；LD_LIBRARY_PATH 进程内 re-exec（不建系统 symlink，保护 mineru）。
- `context_manager.py`：三层记忆装配——第①层 Story Bible 摘要（人物卡：性别/性格/声线）+ 第②层章节状态写入 `script_context.json`；第③层相邻窗口复用引擎 previous_entries 不重复造。patch `add_script_context.py` 在 generate_script.py 锚点注入（幂等、备份 .bak_pre_ctx、无文件时零行为变化）。
- 工作区竞争注意：用户实时改 chunks.json（曾 259→41→259 往返），QC/同步前先看 mtime，跑批以启动瞬间快照为准。

## 后端产品层 v2：emotion 量化 + QC 数据链路（2026-10-04）
- `emotion_map.py`：instruct 自由文本 ⇄ 规范 (emotion, intensity) 双向量化。16 类情感（中英关键词，最长优先匹配 + 程度词微调），`infer`/`instruct_for` 幂等（selftest 全枚举验证）。识别不了返回 None（宁缺毋滥，舞台指示如"跺脚/抓头"不强行归类）。`--write` 回写 DB，`--push` 回写 chunks.json（备份 .bak_pre_emotion，引擎下次读取生效）。实测 196/259 可量化，分布 calm64/sarcasm21/cold19/rush15/whisper12…
- QC 数据链路：
  - `noveldb` 增 `qc_err REAL`（open_db 幂等 ALTER 迁移）；`set_segment_qc(id, qc, err=None)` 用 COALESCE——规则引擎改结论时不清掉已有 ASR 错误率。
  - `asr_qc.py --write` 现持久化逐段 err 到 DB（音频缺失段 err=1.0）。全库 259 段 err 已入库，终态 pass 253 / retry 6（6 段均真需人耳：妈呀→Maya Paul、你！→2、数字位值读法残差）。
  - patch `add_qc_route.py`：GET /api/qc 从 SQLite 出 `{segments:[{ord,qc,err}], totals, findings}`（app.py 备份 .bak_pre_qc，幂等，纯 stdlib 读库）。
- 前端消费 DB 侧 QC（权威覆盖文本 continuity）：`store.loadQc()` 读 /api/qc，逐段写 seg.qc/seg.qcErr，`store.system.qc` 存 totals；hydrate 顺序 continuity→qc。ScriptView 质检面板显示 `CER x%`；ExportView 校验面板加"音频回听质检：N 通过·M 待复核·K 未检"行。构建 JS 53.3KB / CSS 4.6KB。
- 部署：dist→studio，重启 novelTTS（start/stop 脚本在 `novel-audiobook/` 顶层，非 alexandria/）。入口 http://192.168.31.213:4200/。

## 已知边界与刻意推迟（ponytail）
- 多项目：DB schema 已全程按 project_id 关联、sync_state 支持 --title，具备多项目数据结构；但引擎（alexandria app.py）仍硬编码单工作区文件（ROOT/chunks.json 等），真正切换需引擎侧 per-project 目录手术。当前用户工作流为单书，多项目零近期收益 → 推迟到引擎支持工作区切换时再接线，届时 DB 层无需改动。
- emotion→音频：--push 改的是 instruct，历史音频仍按旧风格生成；QC 比对 text 非 instruct，故无正确性问题，用户按需重生成即享新量化风格。

## v3：多本书轮跑（项目工作区切换，2026-10-04）

- 机制：`backend/projects.py` 注册表 `projects.json{active, projects{slug:{title,created}}}`；
  每书一个目录 `alexandria/projects/<slug>/`，ROOT 的 `SWAP_ENTRIES`（state/chunks/script/voice_config/
  成品音频/报告/script_context/voicelines）换成软链指向当前书。引擎零改动。
- 切换 = 空闲守卫(8 类任务) → adopt 旧书实体 → 换链 → `stop+start_novelTTS.sh` 重启（StaticFiles 只在启动解析）
  → 健康轮询 → `sync_state(title)`。CLI：`projects.py list|current|adopt|add|switch`。
- HTTP：`GET /api/projects`（含每书段数）、`POST /api/projects/switch?slug=`（409=任务忙；
  派生 `python3 -u projects.py switch` 独立进程——**不能用 venv python，stop 脚本 pkill 会自杀**）。
  前端顶栏下拉切换，轮询 stats 恢复后整店 hydrate。
- 全局资产不随书切换：designed_voices/clone_voices/lora/app/uploads/app/config.json。
- GPU 门槛：启动脚本校验改为 `${ALEXANDRIA_MIN_FREE_MB:-8000}`。mineru(vllm ~12G) 在跑时
  可用显存只 ~6G：轮书模式需 `ALEXANDRIA_MIN_FREE_MB=4000` 起服务（可浏览/切换，生成会因显存失败），
  出音频前先停 mineru。
- 关键修复：`replace_segments` 现按 ord 且文本未变时继承 qc/qc_err/emotion/intensity
  （曾发生：切换后 sync 重建段落把 253/6 质检结果洗掉；已重跑 ASR QC 恢复并在真切换中验证保留）。
- 验证：demo2 最小书 adopt/add/switch/切回全回环（CLI+HTTP 两条路径）通过；QC 与 259 段完整。

### v3.1 播放/导出修复（同日）
- TransportBar 播放游标改为跟随工作台选中段（store.transport.segId 单一游标），
  不再写死第 4 段；play()/加载失败现会 toast 报原因，不再静默。
- 成品列表：本环境 FastAPI 对 HEAD /api/audiobook* 返回 405 → 改用 `Range: bytes=0-0`
  GET 探测（206 content-range 取大小），MP3/M4B 两行都列出，行内 播放/下载 直连各自端点。
- 导出按钮文案带格式（开始导出 MP3/M4B）；MP3 路径 = 选格式 MP3 后导出。
