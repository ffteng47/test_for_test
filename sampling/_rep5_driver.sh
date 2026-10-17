# ③ 云端复现驱动（tff 授权 2026-10-17「3B」，预算 ≤$0.25）：串行 r4→r5，同 S 批冻结面。
# 一次性运行器，跑完可删；进度行落 _rep5_progress.log（DONE 行=每批出口码+时刻）。
cd "$(dirname "$0")/.." || exit 1
export PYTHONIOENCODING=utf-8
for r in r4 r5; do
  d="sampling/ep1v39pv2c-$r"
  if [ -d "$d" ]; then
    echo "SKIP $r already exists"
    continue
  fi
  .venv/Scripts/python.exe -m plot_engine.review --live --chapters 10 \
    --model-config @router_q25_14b.json --lane cloud --cloud-config @deepseek.router.json \
    --gate-project 1 --dump-dir "$d" > "$d.console.log" 2>&1
  echo "DONE $r exit=$? $(date +%H:%M:%S)"
done
