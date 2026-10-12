# 让 start_novelTTS.sh 顺带拉起两个 sidecar（ASR ref_text / CosyVoice2），端口已监听则跳过。
import shutil, sys
SH = "/home/tff/software/novel-audiobook/start_novelTTS.sh"
SRC = open(SH, encoding="utf-8").read()
if "start_sidecar" in SRC:
    print("ALREADY_PATCHED"); sys.exit(0)
shutil.copy(SH, SH + ".bak_pre_sidecar")

ANCHOR = 'mkdir -p "$LOGD"\n'
BLOCK = ANCHOR + '''
# ---- sidecar：ASR(7870) 与 CosyVoice2(7861)，各自独立 venv，与主服务同生命周期 ----
LAB=$BASE/ttslab
start_sidecar(){ # start_sidecar <port> <venv-python> <module> <logfile>
  if ss -ltn 2>/dev/null | grep -q ":$1 "; then echo "[ok] sidecar :$1 已在运行"; return; fi
  [ -x "$2" ] || { echo "[warn] sidecar venv 缺失: $2"; return; }
  ( cd "$LAB" && setsid "$2" -m uvicorn "$3" --host 127.0.0.1 --port "$1" \
      >> "$LAB/logs/$4" 2>&1 < /dev/null & )
  echo "[..] sidecar :$1 启动中（日志 ttslab/logs/$4）"
}
start_sidecar 7870 "$LAB/venvs/funasr/bin/python"    asr_server:app  asr.log
start_sidecar 7861 "$LAB/venvs/cosyvoice/bin/python" cosy_server:app cosy_server.log
'''
if SRC.count(ANCHOR) != 1:
    sys.exit(f"ANCHOR count={SRC.count(ANCHOR)}")
open(SH, "w", encoding="utf-8").write(SRC.replace(ANCHOR, BLOCK))
print("PATCHED", SH)
