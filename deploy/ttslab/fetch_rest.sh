#!/usr/bin/env bash
# CosyVoice2 权重走 hf-mirror；推理代码仓库在多个 github 只读代理里试通的第一个。
set -uo pipefail
LAB=/home/tff/software/novel-audiobook/ttslab
export HF_ENDPOINT=https://hf-mirror.com
PY=$LAB/dl-venv/bin/python

$PY -c "from huggingface_hub import snapshot_download as d; print(d('FunAudioLLM/CosyVoice2-0.5B', local_dir='$LAB/models/CosyVoice2-0.5B'))" \
  || $PY -c "from modelscope import snapshot_download as d; print(d('iic/CosyVoice2-0.5B', local_dir='$LAB/models/CosyVoice2-0.5B'))" \
  || echo "[FAIL] CosyVoice2"

for P in "https://ghfast.top/" "https://gh-proxy.com/" "https://github.moeyy.xyz/" "https://ghproxy.net/"; do
  if curl -o /dev/null -sw "" --max-time 10 "${P}https://github.com/FunAudioLLM/CosyVoice"; then PROXY=$P; break; fi
done
echo "[proxy] ${PROXY:-none}"
[ -n "${PROXY:-}" ] || exit 0
for R in "FunAudioLLM/CosyVoice" "index-tts/index-tts" "hexgrad/kokoro" "modelscope/FunASR"; do
  N=$(basename "$R")
  [ -d "$LAB/repos/$N/.git" ] && { echo "[git] $N exists"; continue; }
  git -c url."${PROXY}https://github.com/".insteadOf=https://github.com/ \
      clone --depth 1 --recurse-submodules --shallow-submodules "https://github.com/$R" "$LAB/repos/$N" \
    || echo "[FAIL git] $R"
done
echo "REST_DONE $(date)"
