#!/usr/bin/env bash
# 多引擎评测环境下载：TTS 权重(CosyVoice2 / IndexTTS-2 / Kokoro) + STT(SenseVoiceSmall) + 推理代码仓库
# 幂等：已存在的 snapshot 自动跳过；断线重跑续传。不写入 alexandria/venv。
set -uo pipefail
BASE=/home/tff/software/novel-audiobook
LAB=$BASE/ttslab
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=${HF_HOME:-$BASE/hf-cache}
mkdir -p "$LAB/models" "$LAB/repos" "$LAB/logs"

if [ ! -x "$LAB/dl-venv/bin/python" ]; then
  echo "[..] creating dl-venv"
  python3 -m venv "$LAB/dl-venv"
  "$LAB/dl-venv/bin/pip" install -q -U pip modelscope "huggingface_hub[cli]"
fi
PY=$LAB/dl-venv/bin/python

ms_dl() { echo "[ms] $1"; $PY -c "from modelscope import snapshot_download as d; print(d('$1', local_dir='$LAB/models/$2'))" || echo "[FAIL ms] $1"; }
hf_dl() { echo "[hf] $1"; $PY -c "from huggingface_hub import snapshot_download as d; print(d('$1', local_dir='$LAB/models/$2'))" || echo "[FAIL hf] $1"; }

ms_dl iic/SenseVoiceSmall SenseVoiceSmall
ms_dl FunAudioLLM/CosyVoice2-0.5B CosyVoice2-0.5B
hf_dl hexgrad/Kokoro-82M Kokoro-82M
hf_dl IndexTeam/IndexTTS-2 IndexTTS-2

# 推理代码：github 直连不通，走 ghproxy 只读镜像（用前请自行比对上游 commit）
GIt="git -c url.https://ghproxy.net/https://github.com/.insteadOf=https://github.com/"
for R in "FunAudioLLM/CosyVoice" "index-tts/index-tts" "hexgrad/kokoro"; do
  N=$(basename "$R")
  if [ -d "$LAB/repos/$N/.git" ]; then echo "[git] $N exists"; continue; fi
  echo "[git] $N"
  eval "$GIt clone --depth 1 --recurse-submodules https://github.com/$R $LAB/repos/$N" || echo "[FAIL git] $R"
done
echo "TTS_LAB_DL_DONE $(date)"
