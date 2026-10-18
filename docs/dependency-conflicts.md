# 依赖冲突与 CUDA 兼容分析

全部版本取自五个仓库的真实依赖文件（见 source-audit.md 各节），非推测。

## 1. 五仓依赖矩阵（关键项）

| 项 | Alexandria | Audiobook-Generator | tts-audiobook-tool | ebook2audiobook | qwen3-tts-audiobook |
|---|---|---|---|---|---|
| Python | 未 pin（flash-attn wheel 为 **cp310**） | 3.11（Docker） | **3.11**（base）/3.12（qwen3 文件头） | **>3.9,<3.13** | 未 pin |
| torch | **2.7.0**（torch.js, cu128 index；Docker 基座 2.8.0-cuda12.8） | >=2.0.0 | **==2.8.0** + torchaudio==2.8.0 | coqui-tts 0.27.5 间接锁 | >=2.0.0（Makefile cu121） |
| transformers | **==4.57.3**（显式 pin） | >=4.30 | 未列（qwen_tts 传递） | 未列 | 未列 |
| peft | ==0.18.1 | — | — | — | — |
| qwen_tts | **==0.1.1**（pip） | >=0.0.5（pip） | **git pin @022e286b98fb** | — | >=0.1.0（pip） |
| qwen_asr | — | — | — | — | >=0.1.0 |
| 音频 | pydub/librosa/soundfile | pydub | ffmpeg 流式 + pyloudnorm + librosa | ffmpeg + pydub + mutagen | pydub + soundfile |
| CUDA 假设 | **cu128**（驱动 550+） | 无 | 无 pin（用户 venv 自装） | 无 | **cu121** |
| 外部二进制 | ffmpeg | ffmpeg | ffmpeg | **Calibre ebook-convert**, ffmpeg, tesseract, espeak-ng | ffmpeg |

## 2. 冲突判定

1. **torch 2.7.0 vs 2.8.0**：Alexandria 固定 2.7/cu128，tool 固定 2.8/cu128 兼容域。对我们**无实际冲突**——两仓的 Qwen3 路径最终都只经由 `qwen_tts` 这一个包，选一个 torch 即可（见裁定）。flash-attn 必须与所选 torch 同 ABI 重编译，cp310 wheel 不可直接用。
2. **qwen_tts 三个版本口径（真冲突点）**：`0.1.1(pip)` 与 `git@022e286` 内部 API 有差——tool 直接调用了**私有 API**（`model._build_assistant_text`、`_tokenize_texts`、`model.model.generate(...)`、`speech_tokenizer.decode`、`_merge_generate_kwargs`）来捕获 codec codes 实现滚动续接；这些在 0.1.1 上**不保证存在**。q3ab/md_to_audio 只用公开 API（`generate_voice_clone/generate_voice_design/generate_custom_voice`）。
3. **transformers==4.57.3（Alexandria）vs qwen_tts 传递依赖**：qwen_tts 0.1.1 与 4.57.x 是否互相兼容需在 Ubuntu 实测 `pip check`；若装 git 版 qwen_tts，其 transformers 需求可能更高。
4. **peft==0.18.1**：只有做 LoRA 声线（二期）才需要，一期可移出主环境减冲突面。
5. **E2A 的 coqui-tts/piper/phonemizer/espeak-ng 全家桶**：我们只取其解析与导出代码，**全部不装**。jieba 单独拿走。
6. **Calibre**：唯一无法 pip 化的硬依赖（mobi/fb2/rtf 转换）。一期只支持 EPUB/TXT 可完全不装；PDF/DOCX 走自带 PyMuPDF/python-docx 路径（E2A 本就不经 Calibre）；mobi 等二期再引。
7. **ABG 依赖不 pin** → 不装，冲突面上零贡献。

## 3. 裁定：两个 venv，一台 Ubuntu

目标机：Ubuntu 24.04，NVIDIA 驱动 ≥550，CUDA 12.8 runtime（cu128 wheel，兼容 cu121 编译物的前提是不向下混装——统一 cu128 即可，无需 cu121）。

```
venv-app/     # api + annotator + ebook 解析：轻装，无 torch
  fastapi==0.128.0 uvicorn==0.40.0 pydantic==2.12.5 openai==2.16.0
  ebooklib pymupdf python-docx beautifulsoup4 jieba chardet
  sqlalchemy==2.x aiosqlite PyMuPDF…（python 3.12）

venv-gpu/     # worker：唯一 GPU 环境
  torch==2.8.0 torchaudio==2.8.0（cu128）
  transformers==4.57.3（若 pip check 通过则锁;否则以 qwen_tts 要求为准）
  qwen_tts=<裁定见下>  qwen_asr>=0.1.0 soundfile numpy librosa pyloudnorm
  flash-attn=<torch2.8+cu128+py312 自编译>（可选,不存在则代码路径自动跳过——tool 已示范探测法）
  二期追加: peft==0.18.1
```

**qwen_tts 版本裁定流程（首步上机即做）**：
1. 先装 pip 版 `qwen-tts`，`python -c "import qwen_tts; print(version, dir(Qwen3TTSModel))"` 核对公开 API 是否含 `create_voice_clone_prompt / generate_voice_clone / generate_custom_voice / generate_voice_design`。
2. 若需滚动续接（跨段韵律）→ 必须 git pin `QwenLM/Qwen3-TTS@022e286`（tool 实证组合）；同时把 Alexandria 私有 API 适配层（batch、lora）逐函数在该 commit 上重新验证，`_model_lock/ThreadPool` 批量路径降级为公开 API 串行。
3. 两条都不通则一期砍滚动续接，保公开 API。

## 4. 模型资产清单（磁盘/显存预算，RTX 3090 24GB）

| 模型 | 用途 | 显存(bf16) | 一期常驻? |
|---|---|---|---|
| Qwen3-TTS-12Hz-1.7B-CustomVoice | 内置音色+情绪 instruct | ~3.5GB | 常驻（旁白可先全用内置音色） |
| Qwen3-TTS-12Hz-1.7B-Base | 克隆/LoRA 合成 | ~3.5GB | 常驻（主力） |
| Qwen3-TTS-12Hz-1.7B-VoiceDesign | 文本描述造音色 | ~3.5GB | 按需加载→用完 unload（生成试听时） |
| Qwen3-ASR-1.7B | QC 转录 | ~3.5GB | 按需，串行于 TTS 批次间 |
| Qwen3-ForcedAligner-0.6B | 词级时间戳（二期） | ~1.5GB | 否 |
| 本地 Qwen LLM | 标注/审校 | **在 Ollama/别处，本卡零占用**（annotator 走 HTTP） | n/a |

峰值核算：常驻 2×3.5 + 批量 KV/codec（tool `_estimate_max_batch_size` 会主动限批）+ 临时 ASR 3.5 < 24GB，成立。规则：**VoiceDesign 与 ASR 永不同时在场**（worker 内串行状态机强制）。
磁盘：TTS 三模型 ~11GB、ASR ~3.5GB 一次性下载进 `models/`（HF cache 重定向，tool snapshot_download 模式）。

## 5. 外部二进制与环境检查表（Ubuntu 机 deploy/precheck.sh）

- [ ] ffmpeg + ffprobe（导出链核心；验证含 libmp3lame——Alexandria 记录过 conda ffmpeg 缺 lame 产出 428 字节文件的坑）
- [ ] NVIDIA 驱动 ≥550；`nvidia-smi` 可被 api 进程调用
- [ ] （二期）Calibre ebook-convert + tesseract + 中文 tessdata
- [ ] Ollama/vLLM 端点连通 + 目标 Qwen 模型已拉取（annotator 默认 localhost:11434/v1，config 化）
- [ ] Python 3.12 + 两个 venv 各自 `pip check` 零冲突

## 6. 上游已知的卫生问题（继承代码时规避）

- E2A conf.py 硬编码 Fernet key + `kill_previous_instances()` 杀同名进程——剥离时必删。
- ABG `verify=False` 健康检查、全 `>=` 依赖——不继承。
- q3ab `venv_qwen3/bin/python`、`cuda:0` 硬编码——全部 config 化。
- Alexandria requirements 无 torch/qwen_tts（装在外）——我们 venv-gpu 显式 pin 并写 lock 文件（pip freeze → requirements/gpu.lock）。
