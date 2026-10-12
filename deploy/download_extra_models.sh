#!/usr/bin/env bash
# 追加下载：轻量 0.6B TTS（快速草稿模式）+ faster-whisper large-v3（ASR 质检）
# 已存在的模型 snapshot_download 自动跳过；断线重跑即可
set -uo pipefail
BASE=/home/tff/software/novel-audiobook
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=${HF_HOME:-$BASE/hf-cache}
PY=$BASE/alexandria/venv/bin/python
mkdir -p "$BASE/logs"
echo "[..] start $(date) HF_HOME=$HF_HOME"
for REPO in \
  "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice" \
  "Qwen/Qwen3-TTS-12Hz-0.6B-Base" \
  "Systran/faster-whisper-large-v3"
do
  echo "[..] $REPO"
  $PY - "$REPO" <<'EOF'
import sys
from huggingface_hub import snapshot_download
p = snapshot_download(sys.argv[1])
print("[OK]", sys.argv[1], "->", p)
EOF
  [ $? -eq 0 ] || echo "[FAIL] $REPO (继续下一个，重跑本脚本可续传)"
done
echo "[..] pip install faster-whisper"
$BASE/alexandria/venv/bin/pip install --quiet faster-whisper && echo "[OK] faster-whisper installed" || echo "[FAIL] pip faster-whisper"
echo "EXTRA_MODELS_DONE $(date)"
