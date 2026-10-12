#!/bin/bash
# Alexandria Audiobook 基线服务停止脚本（与 start_novelTTS.sh 配对）
set -u
BASE=/home/tff/software/novel-audiobook
LOGD=$BASE/logs

PID=$(cat "$LOGD/alexandria.pid" 2>/dev/null || true)
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID" && echo "[OK] alexandria (pid $PID) 已停止"
else
  pkill -f "$BASE/alexandria/venv/bin/python app.py" && echo "[OK] alexandria 已停止 (按命令行匹配)" || echo "alexandria 未运行"
fi

sleep 2
LEFT=$(pgrep -af "$BASE/alexandria/venv/bin/python" || true)
if [ -n "$LEFT" ]; then
  echo "[warn] 残留进程（LLM/TTS 子任务），强制清理:"; echo "$LEFT"
  pkill -f "$BASE/alexandria/venv/bin/python"
fi
rm -f "$LOGD/alexandria.pid"
echo "NOVEL_TTS_DOWN"
