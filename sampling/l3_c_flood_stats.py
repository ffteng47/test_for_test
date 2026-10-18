# W3（批3 前置，零 LLM）：C249 候选的 epistemic_pair 洪峰分流统计。
# 目的=给 W2 判定提示词定压制参数：speculation/dialogue/narrator 各配对类占多少、
# 按类移出后候选量削减曲线，并对 ch50 三锚候选做「压制是否吞锚」安全闸反查。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/l3_c_flood_stats.py
#       > sampling/l3-c-flood-v01.console.log 2>&1
import json
from collections import Counter
from pathlib import Path

cands = [c for ch in json.loads(
    (Path(__file__).parent / "l3-corpus-v01.json").read_text(encoding="utf-8")).values()
    for c in ch["candidates"]]
cfam = [c for c in cands if c["family"] == "C"]
print(f"候选总量={len(cands)}｜C 族={len(cfam)}")

dist = Counter(c["epistemic_pair"] or "(空)" for c in cfam)
print("\n== C 族 epistemic_pair 分布 ==")
for k, v in dist.most_common():
    print(f"  {k:32s} {v:4d}（{v / len(cfam):.0%}）")

# 削减曲线：宿主侧按配对类移出（模拟序=占比降序的累进压制）
print("\n== 压制曲线（移出类→剩余 C 候选）==")
remaining = len(cfam)
for k, v in dist.most_common():
    remaining -= v
    print(f"  移出 {k:32s} → 剩 {remaining:4d}（削 {1 - remaining / len(cfam):.0%}）")

# 锚安全闸：ch50 候选按配对类归属，吞锚=该类不可整类压制
print("\n== ch50 锚候选的配对类（安全闸反查）==")
for c in json.loads((Path(__file__).parent / "l3-corpus-v01.json")
                    .read_text(encoding="utf-8"))["50"]["candidates"]:
    print(f"  {c['family']}|{c['rule_id']}|{';'.join(c['evidence_refs'])}"
          f"|pair={c['epistemic_pair'] or '(空)'}")

# predicate 分布（C 族矛盾域集中度，喂 W2 分域参数）
print("\n== C 族 predicate 分布 top ==")
pred = Counter(c["detail"].split(":")[0].split("|")[0].strip() for c in cfam)
for k, v in pred.most_common(12):
    print(f"  {k:28s} {v}")
