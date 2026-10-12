#!/usr/bin/env bash
# 启动 ttslab sidecars（CosyVoice2 / IndexTTS-2 / Kokoro / SenseVoice-ASR），已在跑则跳过。
# 每个引擎独立 venv，只监听 127.0.0.1；生产 alexandria 经 HTTP 调用。
set -u
LAB="$(cd "$(dirname "$0")" && pwd)"
cd "$LAB" || exit 1
mkdir -p logs
export HF_HOME=${HF_HOME:-/home/tff/software/novel-audiobook/hf-cache}

up() {  # up <name> <port> <venv-python> <app> [env...]
  local N=$1 P=$2 PY=$3 APP=$4; shift 4
  if curl -s -m 2 "http://127.0.0.1:$P/health" >/dev/null 2>&1; then
    echo "[skip] $N :$P 已在跑"; return
  fi
  [ -x "$PY" ] || { echo "[FAIL] $N venv 缺失: $PY"; return 1; }
  local CMD=("$PY" -m uvicorn "$APP" --host 127.0.0.1 --port "$P")
  [ $# -gt 0 ] && CMD=(env "$@" "${CMD[@]}")
  nohup "${CMD[@]}" >> "logs/$N.log" 2>&1 &
  echo $! > "logs/$N.pid"
  for _ in $(seq 1 30); do
    curl -s -m 2 "http://127.0.0.1:$P/health" >/dev/null 2>&1 && { echo "[OK] $N :$P"; return; }
    sleep 2
  done
  echo "[warn] $N :$P 60s 内未就绪，看 logs/$N.log"
}

up asr        7870 venvs/funasr/bin/python     asr_server:app
up cosy       7861 venvs/cosyvoice/bin/python  cosy_server:app      COSY_DEVICE="${COSY_DEVICE:-cpu}"
up indextts   7862 venvs/indextts311/bin/python indextts_server:app INDEX_DEVICE="${INDEX_DEVICE:-cpu}"
up kokoro     7863 venvs/kokoro/bin/python      kokoro_server:app    KOKORO_DEVICE="${KOKORO_DEVICE:-cpu}"
echo "SIDECARS_DONE"
