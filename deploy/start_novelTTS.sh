#!/bin/bash
# Alexandria Audiobook 基线服务启动脚本（/home/tff/software/novel-audiobook/alexandria）
# 启动前逐项检查：venv / GPU 驱动与空闲显存 / ffmpeg / 磁盘 / LLM 端点 / HF 镜像；
# Web UI 与 API 固定 0.0.0.0:4200（供局域网开发机访问），模型经 hf-mirror 下载缓存。
set -u
export LANG=C.UTF-8
export HF_ENDPOINT=https://hf-mirror.com          # huggingface.co 直连不通，必须走镜像
export HF_HOME=${HF_HOME:-/home/tff/software/novel-audiobook/hf-cache}  # 与 download_models.sh 一致
BASE=/home/tff/software/novel-audiobook
APP=$BASE/alexandria
PY=$APP/venv/bin/python
LOGD=$BASE/logs
PORT=${ALEXANDRIA_PORT:-4200}
mkdir -p "$LOGD"

# ---- sidecar TTS/ASR 引擎：唯一清单在 ttslab/start_sidecars.sh，本脚本只做生命周期挂钩 ----
LAB=$BASE/ttslab; mkdir -p "$LAB/logs"
[ -x "$LAB/venvs/funasr/bin/python" ] && ( cd "$LAB" && bash start_sidecars.sh >> "$LAB/logs/sidecars.log" 2>&1 < /dev/null & )

fail(){ echo "[FAIL] $1"; exit 1; }
ok(){ echo "[OK] $1"; }

# ---- 检查 ----
[ -x "$PY" ] || fail "venv 缺失: $APP/venv（先跑 $BASE/install_deps.sh 或查看 $BASE/install.log）"
command -v nvidia-smi >/dev/null 2>&1 || fail "nvidia-smi 不存在，NVIDIA 驱动未就绪"
command -v ffmpeg >/dev/null 2>&1 || command -v ffprobe >/dev/null 2>&1 || fail "ffmpeg/ffprobe 缺失 (sudo apt install ffmpeg)"
SMI_OUT=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>&1 | head -1)
# 不是纯数字 = nvidia-smi 本身失败了（最常见是 apt 自动升级驱动后，内核里的模块与用户态库版本不一致）
case "$SMI_OUT" in
  ''|*[!0-9]*)
    fail "nvidia-smi 取不到显存数字，GPU 当前不可用：${SMI_OUT:-空输出}
  内核里加载的驱动模块: $(cat /sys/module/nvidia/version 2>/dev/null || echo '?')
  磁盘上给当前内核的模块: $(modinfo -F version nvidia 2>/dev/null || echo '?')   (内核 $(uname -r))
  用户态驱动包: $(dpkg-query -W -f='${Version}  ' 'nvidia-driver-*open' 2>/dev/null | head -1)
  三者必须一致。最常见原因是 apt 自动升级只换了用户态库和磁盘上的 .ko，内存里那个模块还是旧的：
  先停掉占用 GPU 的进程（vLLM / sidecar / 本服务），再 sudo rmmod nvidia_uvm nvidia_modeset nvidia && sudo modprobe nvidia；
  做不到（有进程在占，rmmod 必失败）就重启机器。重启前先确认 $(uname -r) 有配套模块包，否则重启后 GPU 直接没了。
  详见 docs/usage-wiki.md §4.4" ;;
esac
FREE_MB=$SMI_OUT
# TTS 三模型常驻约需 8GB；mineru 占用时剩余仍应 >= 8000MiB
[ "$FREE_MB" -ge "${ALEXANDRIA_MIN_FREE_MB:-8000}" ] || fail "GPU 可用显存不足 ${ALEXANDRIA_MIN_FREE_MB:-8000}MiB (free=${FREE_MB}MiB，mineru 是否占用过高?)"
AVAIL_GB=$(df --output=avail -BG /home/tff/software 2>/dev/null | tail -1 | tr -d ' G')
[ -n "$AVAIL_GB" ] && [ "$AVAIL_GB" -ge 20 ] || fail "~/software 剩余磁盘不足 20GB (${AVAIL_GB:-?}G)"
# LLM（剧本标注/人物生成用；纯 TTS 冒烟测试不需要，仅提醒）
LLM_URL=$(python3 - "$APP/app/config.json" <<'EOF' 2>/dev/null
import json,sys
try: print(json.load(open(sys.argv[1])).get("llm",{}).get("base_url",""))
except Exception: print("")
EOF
)
LLM_URL=${LLM_URL:-http://localhost:11434/v1}
LLM=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$LLM_URL/models" 2>/dev/null || echo 000)
[ "$LLM" = "200" ] && ok "LLM 端点就绪: $LLM_URL" || echo "[warn] LLM 端点不可达: $LLM_URL（剧本标注不可用，TTS 不受影响）"
ok "环境检查通过 (GPU free=${FREE_MB}MiB, disk=${AVAIL_GB}G)"

# ---- 已在运行? ----
if pgrep -f "$APP/venv/bin/python app.py" >/dev/null; then
  echo "[warn] alexandria 已在运行 (pid $(cat "$LOGD/alexandria.pid" 2>/dev/null || pgrep -f "$APP/venv/bin/python app.py" | head -1))"
  exit 0
fi

# ---- 启动 ----
cd "$APP/app" || fail "目录缺失: $APP/app"
ALEXANDRIA_HOST=0.0.0.0 ALEXANDRIA_PORT=$PORT nohup "$PY" app.py >> "$LOGD/alexandria.log" 2>&1 &
echo $! > "$LOGD/alexandria.pid"

HEALTH=000
for i in $(seq 1 40); do
  HEALTH=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/" 2>/dev/null || echo 000)
  [ "$HEALTH" = "200" ] && break
  sleep 2
done
[ "$HEALTH" = "200" ] || fail "服务 240s 内未就绪（启动日志看 $LOGD/alexandria.log）"
ok "Web UI/API http://0.0.0.0:$PORT 就绪"
echo "NOVEL_TTS_UP ui=http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PORT  internal=127.0.0.1:$PORT"
