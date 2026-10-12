# ttslab — 多引擎 TTS/STT 评测区

与生产环境 `alexandria/venv`（qwen-tts, torch 2.7.0+cu128）完全隔离：每个引擎独立 venv，
跨引擎调用一律走本机 sidecar HTTP，不在生产 venv 里 pip install。

## 权重 models/
| 目录 | 引擎 | 许可（商用） |
|---|---|---|
| CosyVoice2-0.5B | 阿里 FunAudioLLM | Apache-2.0 ✅ |
| IndexTTS-2 | B 站 | 代码 Apache-2.0；权重商用需 bilibili 登记（小团队免费）⚠️ |
| Kokoro-82M | hexgrad | Apache-2.0 ✅ |
| SenseVoiceSmall | 阿里 FunASR | Apache-2.0 ✅（STT + 情感标签）|
| (已有) Qwen3-TTS 1.7B/0.6B ×3 | alexandria/hf-cache | Apache-2.0 ✅ |
| (已有) faster-whisper-large-v3 | alexandria/hf-cache | MIT ✅（作 QC 回听）|

已排除：F5-TTS、Fish Speech/OpenAudio —— 权重 CC-BY-NC，不能用于商业有声书。

## venvs/ repos/
cosyvoice / indextts / funasr 各一个；repos 经 gh-proxy 只读镜像克隆，
上线前需与上游 commit 比对（`git -C repos/CosyVoice log -1`）。

## 冒烟测试
CosyVoice2 克隆：
引擎权重能不能起来，直接问 sidecar，不要在 venv 里手搓上游 API：
```
bash start_sidecars.sh                                  # 起齐并跳过已在跑的
for p in 7861 7862 7863 7870; do curl -s 127.0.0.1:$p/health; echo; done
curl -s -X POST 127.0.0.1:7870/transcribe -F "file=@某个已上传的参考音频.wav"   # 看 ref_text + 情感
```
端到端（含生产分发）走 Voice Lab：`POST :4200/api/voice_lab/generate`，结果的 `engine` 字段即来源。

## Sidecar（Voice Lab 与批量生产共用）
一条命令起齐（已在跑则跳过，可反复执行）：`bash start_sidecars.sh`；停止：`bash stop_sidecars.sh`。

| 端口 | 进程 | 设备旋钮 |
|---|---|---|
| 7870 | SenseVoice ASR → ref_text + 情感标签 | `ASR_DEVICE`（默认 cpu）|
| 7861 | CosyVoice2 → 克隆 / 情感指令 | `COSY_DEVICE=cuda` 需 ~5G 空闲显存 |
| 7862 | IndexTTS-2 → 克隆 + 8 维 emo_vector | `INDEX_DEVICE=cuda` 需 ~6G |
| 7863 | Kokoro → 固定音色朗读（不能克隆，旁白兜底）| `KOKORO_DEVICE` |

生产侧唯一引擎注册表是 `alexandria/app/engines.py`（含 `__main__` 自检），Voice Lab 的
`MODELS[...]["backend"]` 行和批量生产的 `voice_config[speaker]["engine"]` 都读它：
每条结果写回 `voice_engine` / `voice_fallback`，Kokoro 兜底必须显式留痕，禁止静默冒充角色音色。
新增一个引擎 = 一个 sidecar + `ENGINES` 里一行，前端零改动（模型列表来自接口）。
`start_novelTTS.sh` 只挂钩 `start_sidecars.sh`，引擎清单不在两处维护。

**情感载体**（`ENGINES[key]["emo"]`）声明每个引擎怎么吃段级情感，翻译只在引擎边界做，词表仍只有
`emotion_map` 一份：`verbatim`=原句直给（Qwen 三家）/ `instruct2`=包成 CosyVoice2 句式 /
`emo_vector`=sidecar 自己 `infer()` 折成 8 维（IndexTTS-2）/ `none`=没有情感通道（Kokoro）。
`engines.py` 自检会断言每行都声明了合法载体，新引擎漏声明当场炸。剧本和 Vue 都不需要知道格式差异。

**通道**（7861 的 `mode`）由音色绑定里的 `mode` 字段决定，不由「这句有没有 instruct」决定：
`zero_shot`=纯克隆（必填 `ref_text`），`instruct`=CosyVoice2 情感指令。剧本每段的 instruct 是给
Qwen 写的语气词，直接塞进 instruct2 会让模型胡说话（30 字念出 20s）；`engines.cosy_style()`
负责把它翻成「用…的语气说话」，非中文一律丢弃退回纯克隆。情感词表唯一来源是
`backend/emotion_map.py`，经 `GET /api/emotions` 出给前端，别在 Vue 里再抄一套。

## 环境搭建踩过的坑（重装时照抄）
- `grpcio==1.57.0` 无 cp312 wheel → 放开 `>=1.62`
- `deepspeed` 在无 nvcc 机器上让 transformers 导入即炸 → 推理用可卸载
- `openai-whisper` sdist 需 `pkg_resources`，setuptools≥81 已移除 → `pip install "setuptools<81"` 后 `--no-build-isolation`
- `matcha` 模块在 `repos/CosyVoice/third_party/Matcha-TTS`，需手动进 sys.path
- CosyVoice2 非流式输出键是 `tts_speech`
- index-tts 要求 python<3.12 → `uv venv --python 3.11`（`UV_PYTHON_INSTALL_MIRROR=https://gh-proxy.com/...`）
- IndexTTS-2 快照缺辅助权重：`w2v-bert-2.0`（conformer_shaw.pt + model.safetensors，各 2.2G）必须预置到
  `models/IndexTTS-2/hf_cache/w2v-bert-2.0/`，否则加载时去 ModelScope 拉 → 404
- indextts/kokoro 的 venv 要补 `fastapi uvicorn python-multipart soundfile`（上游 requirements 不含服务侧依赖）
- 杀进程用 `pkill -f "cosy_serve[r]"`，否则 ssh 自身命令行会被匹配杀掉
