#!/bin/bash
# GPU 驱动 NVML mismatch 的取证 + 冻结 + 重启 + 复核脚本。在 Ubuntu 机上跑：sudo bash fix_gpu_driver.sh
# 无参数 = 只读体检（不写任何东西）。--hold 钉包；--reboot 重启；--verify 重启后复核并拉起服务。
# 背景与判读见 docs/usage-wiki.md §4.4
set -u
BASE=/home/tff/software/novel-audiobook
PORT=${ALEXANDRIA_PORT:-4200}
MODE=${1:-check}

die(){ echo "[停止] $1"; exit 1; }
step(){ echo; echo "===== $1 ====="; }

[ "$(id -u)" = 0 ] || [ "$MODE" = "check" ] || die "需要 root：sudo bash $0 ${MODE#--}"

# ---- 三个版本，必须完全一致才对得上 ----
LOADED=$(cat /sys/module/nvidia/version 2>/dev/null || echo 无)
DISK=$(modinfo -F version nvidia 2>/dev/null || echo 无)
USER=$(dpkg-query -W -f='${Version}' nvidia-kernel-common-595 2>/dev/null | cut -d- -f1)
USER=${USER:-无}
step "版本对照（内核模块 vs 用户态）"
echo "  内存里加载的模块 : $LOADED"
echo "  磁盘上给当前内核 : $DISK      (当前内核 $(uname -r))"
echo "  用户态驱动包     : $USER"
if [ "$LOADED" = "$USER" ] && [ "$DISK" = "$USER" ]; then
  echo "  → 三者一致，GPU 驱动没裂。若 nvidia-smi 仍报错，另有原因，别重启。"
  ALIGNED=1
else
  echo "  → 不一致：用户态与内核模块必须同版本，NVML 才肯工作。只能重载模块或重启。"
  ALIGNED=0
fi

# ---- 重启会启动哪个内核，它有没有配套 GPU 模块 ----
step "重启后的 GPU 可用性（GRUB_DEFAULT=0 → 选最新内核）"
BOOTK=$(ls -1 /lib/modules | grep generic | sort -V | tail -1)
[ -n "$BOOTK" ] || die "/lib/modules 读不到内核列表"
KO=$(find "/lib/modules/$BOOTK" -name 'nvidia.ko*' 2>/dev/null | head -1)
KOV=${KO:+$(modinfo -F version "$KO" 2>/dev/null)}
echo "  将启动的内核 : $BOOTK   (GRUB 默认: $(grep -E '^GRUB_DEFAULT' /etc/default/grub || echo '?'))"
echo "  它的 GPU 模块: ${KOV:-★ 没有 nvidia.ko ★}"
[ -d /sys/firmware/efi ] && echo "  引导方式     : UEFI（换 dkms 路线需先确认 Secure Boot / MOK，本脚本不碰）" || echo "  引导方式     : Legacy BIOS"
BOOTK_OK=0
[ -n "$KOV" ] && [ "$KOV" = "$USER" ] && BOOTK_OK=1
echo "  → 重启后驱动判定: $([ $BOOTK_OK = 1 ] && echo 安全（模块与用户态同为 $KOV）|| echo '★ 有风险，见下面处置')"

step "待升级的内核/驱动（有新版等着，就更要把住重启时机）"
apt-cache policy linux-generic-hwe-24.04 linux-image-generic-hwe-24.04 \
  linux-modules-nvidia-595-open-generic-hwe-24.04 nvidia-kernel-common-595 2>/dev/null \
  | awk '/^[a-z]/{p=$1} /^  Installed|^  Candidate/{printf "  %-56s %s\n", p, $0}' | sed 's/  Installed:/已装/'
apt list --upgradable 2>/dev/null | grep -iE "^linux-|^nvidia-|^libnvidia-" | sed 's/^/  待升: /' || echo "  无（内核/驱动都无待升级）"

step "谁在占 GPU（重启会让它们消失，其中非本项目进程动了要你确认）"
# 谁真的开着 /dev/nvidia* —— /proc 是唯一不会说谎的来源（API 里没有"未完成任务"这个字段）
HOLDERS=""
for p in $(ls /proc | grep -E '^[0-9]+$'); do
  ls -l /proc/$p/fd 2>/dev/null | grep -q "/dev/nvidia" || continue
  CMD=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | cut -c1-90)
  echo "  PID $p -> $CMD"
  HOLDERS="$HOLDERS$p,"
done
HOLDERS=${HOLDERS%,}
echo "  占用者 PID: ${HOLDERS:-无}"

step "本项目服务（4200）与生成任务"
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "localhost:$PORT/api/system/stats" 2>/dev/null || echo 000)
echo "  /api/system/stats HTTP=$CODE $([ "$CODE" = 000 ] && echo '(服务未运行)' || echo '(服务在跑)')"
# 生成中 = 本项目的 python 正握着 /dev/nvidia*。NVML 裂了的时候握不住，这条自然放行。
BUSY=""
if [ -n "$HOLDERS" ]; then
  for p in ${HOLDERS//,/ }; do
    grep -q "alexandria/venv" /proc/$p/cmdline 2>/dev/null || continue
    grep -qE "generate|batch|tts" /proc/$p/cmdline 2>/dev/null && BUSY="$BUSY $p"
    echo "  本项目进程 PID $p: $(tr '\0' ' ' < /proc/$p/cmdline | cut -c1-90)"
  done
fi
[ -z "$BUSY" ] || die "PID$BUSY 正在用 GPU 跑生成，按 §4.3 不许重启"

[ "$MODE" = "check" ] && { echo; echo "只读体检完成。下一步：sudo bash $0 --hold（钉住），再 sudo bash $0 --reboot。"; exit 0; }

if [ "$MODE" = "--hold" ]; then
  step "钉住内核与驱动（包名按已装版本号筛出来，不手敲）"
  [ "$USER" != "无" ] || die "读不到 nvidia 用户态版本，无法按版本筛包"
  NV=$(dpkg-query -W -f='${Package} ${Version}\n' | awk -v v="$USER" 'index($2, v"")==1 {print $1}')
  KER="linux-generic-hwe-24.04 linux-image-generic-hwe-24.04 linux-headers-generic-hwe-24.04 linux-modules-nvidia-595-open-generic-hwe-24.04"
  ALL="$NV $KER"
  echo "  nvidia 成套 $(echo $NV | wc -w) 个 + 内核/模块 $(echo $KER | wc -w) 个"
  echo "$ALL" | tr ' ' '\n' | sed 's/^/    /'
  BAD=0
  for p in $ALL; do dpkg-query -W "$p" >/dev/null 2>&1 || { echo "  ✗ 包名不存在: $p"; BAD=1; }; done
  [ "$BAD" = 0 ] || die "有包名不存在，apt-mark 会静默跳过它们 → 钉一半等于没钉。先修正名单。"
  echo "  关键包自检（缺一个就不许钉）："
  for need in libnvidia-compute-595 nvidia-kernel-common-595 nvidia-firmware-595-$USER; do
    case " $ALL " in *" $need "*) echo "    ✓ $need";; *) echo "    ✗ 少了 $need"; BAD=1;; esac
  done
  [ "$BAD" = 0 ] || die "名单不完整"
  apt-mark hold $ALL
  N=$(apt-mark showhold | wc -l)
  [ "$N" -ge "$(echo $ALL | wc -w)" ] || die "钉住后 showhold 只有 $N 条，与预期 $(echo $ALL | wc -w) 不符"
  echo "  已钉住 $N 条。代价：这批包不再自动拿安全补丁；apt-get upgrade 会长期显示它们 kept back。"
  echo "  要人工升级：sudo apt-mark unhold $ALL 之后成套 apt-get upgrade && 立刻重启。"
  exit 0
fi

if [ "$MODE" = "--reboot" ]; then
  step "重启前最后一道闸"
  [ "$ALIGNED" = 0 ] || die "驱动本来就一致，不需要重启（先把别的原因查清楚）"
  [ "$BOOTK_OK" = 1 ] || die "将启动的 $BOOTK 没有与用户态($USER)同版的 GPU 模块，重启后 GPU 直接没了。
  先补配套包再重启：apt-get install -y linux-modules-nvidia-595-open-${BOOTK%-generic}
  （装不上就说明源里已无此组合，必须先把用户态驱动升到与之匹配的那一版，再重启）"
  echo "  判定：重启进 $BOOTK，加载 ${KOV}，与用户态 ${USER} 一致 → 可恢复。"
  echo "  占用 GPU 的进程（含 vLLM/mineru/ComfyUI 等非本项目进程）会一并消失，确认无误后 5 秒内 Ctrl-C 取消。"
  sleep 5
  reboot
  exit 0
fi

if [ "$MODE" = "--verify" ]; then
  step "重启后复核"
  echo "  内存模块=$(cat /sys/module/nvidia/version 2>/dev/null || echo 无)  磁盘=$(modinfo -F version nvidia 2>/dev/null || echo 无)  用户态=$(dpkg-query -W -f='${Version}' nvidia-kernel-common-595 2>/dev/null | cut -d- -f1)"
  nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv || die "nvidia-smi 仍失败：NVML 没恢复，先别起服务"
  echo "  钉住的包数: $(apt-mark showhold | wc -l)"
  step "拉起本项目服务（sidecar 由 start_novelTTS.sh 自己带）"
  su tff -c "cd $BASE && ./start_novelTTS.sh"
  sleep 20
  curl -s -o /dev/null -w "  4200 首页 HTTP=%{http_code}\n" --max-time 10 "localhost:$PORT/"
  exit 0
fi

die "未知参数 $MODE（可用：无参数 / --hold / --reboot / --verify）"
