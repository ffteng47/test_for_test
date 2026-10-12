#!/usr/bin/env bash
# 停掉 ttslab sidecars（按启动时记录的 pid，兜底用端口）。
set -u
LAB="$(cd "$(dirname "$0")" && pwd)"
cd "$LAB" || exit 1
for f in logs/*.pid; do
  [ -e "$f" ] || continue
  N=$(basename "$f" .pid)
  kill "$(cat "$f")" 2>/dev/null && echo "[kill] $N $(cat "$f")"
  rm -f "$f"
done
for P in 7861 7862 7863 7870; do
  fuser -k "$P"/tcp 2>/dev/null && echo "[kill] :$P"
done
echo "SIDECARS_DOWN"
