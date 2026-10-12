#!/usr/bin/env bash
# 每个引擎一个独立 venv：CosyVoice/IndexTTS 的 torch 版本会和 alexandria/venv(2.7.0+cu128) 冲突。
# 串行安装，全部可重跑（已存在则跳过）。
set -uo pipefail
LAB=/home/tff/software/novel-audiobook/ttslab
IDX="-i https://pypi.tuna.tsinghua.edu.cn/simple"
mkdir -p "$LAB/venvs" "$LAB/logs"

mk() {  # mk <name> <requirements-file-or-"">
  local N=$1 RF=$2 V=$LAB/venvs/$1
  if [ -x "$V/bin/python" ]; then echo "[venv] $N exists"; else
    python3 -m venv "$V" || { echo "[FAIL venv] $N"; return; }
    "$V/bin/pip" install -q -U pip $IDX || { echo "[FAIL pip] $N"; return; }
  fi
  [ -n "$RF" ] && { "$V/bin/pip" install -r "$RF" $IDX && echo "[OK deps] $N" || echo "[FAIL deps] $N"; }
  "$V/bin/pip" install -q modelscope $IDX
}

mk cosyvoice "$LAB/repos/CosyVoice/requirements.txt"
mk indextts  "$LAB/repos/index-tts/requirements.txt"
mk funasr    ""
"$LAB/venvs/funasr/bin/pip" install -q funasr "json5>=0.9.6" torch torchaudio modelscope $IDX && echo "[OK deps] funasr"
echo "ENVS_DONE $(date)"
