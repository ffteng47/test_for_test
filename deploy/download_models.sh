#!/bin/bash
# 预下载 Qwen3-TTS 三模型（经 hf-mirror，Alexandria 运行时也从 HF_HOME 缓存读取）
set -u
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=${HF_HOME:-/home/tff/software/novel-audiobook/hf-cache}
BASE=/home/tff/software/novel-audiobook
mkdir -p "$HF_HOME" "$BASE/logs"
[ -d "$BASE/alexandria/venv" ] || { echo "[FAIL] venv 不存在，先完成安装"; exit 1; }
echo "[..] 下载模型到 $HF_HOME（约 3x3.5GB，已存在的自动跳过）"
"$BASE/alexandria/venv/bin/python" - <<'EOF'
from huggingface_hub import snapshot_download
for repo in ("Qwen/Qwen3-TTS-12Hz-1.7B-Base",
             "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
             "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"):
    print("[..]", repo, flush=True)
    p = snapshot_download(repo)
    print("[OK]", repo, "->", p, flush=True)
EOF
echo "MODELS_READY"
