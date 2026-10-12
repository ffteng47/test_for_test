set -u
for n in ctrl q3_8b q3_14b q35_27b q3_30b; do
  case $n in
    ctrl) cfg=router_q25_14b.json;;
    *) cfg=router_$n.json;;
  esac
  d=sampling/bo_$n
  mkdir -p $d
  .venv/Scripts/python.exe -X utf8 -m plot_engine.review --live --chapters 10 --prompt persona \
    --model-config @$cfg --dump-dir $d/dump --state-dir $d/state > $d/run.log 2>&1
  echo "bo_$n exit=$?" >> sampling/bo_all.log
done
