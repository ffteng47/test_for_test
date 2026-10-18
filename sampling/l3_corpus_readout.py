# L3 轻档语料读数（批1-2 验证出口，tff 2026-10-18 放行）：wpe50ch 50 章全量出数，零 LLM 纯派生。
# 出口纪律：候选不是定罪（severity 恒 OBS）；行号=剥注释后送检行号，宿主可回填原稿。
# 尺面戳 l3-v0.2.3（v2 四条：①台词提及不造在场帧 ②在场证据行=叙述互动行/A 章首豁免收窄
#   ③代称不抽数 ④陈述时点字段；v2.1 三笔：去找X目标不在场/值守问句不入predicate/白日词进时点表；
#   v2.2 两笔（tff 真人终审 92 卡呈规格）：①叙述内嵌回忆/传闻/揣测小句不算在场 ②night_watch 谓词退役；
#   v2.3 小批（tff 裁定=稽核 F1+F3+F4 先行，F2 挂中批）：F1 作用域扩到到达/离开（小句级：回忆小句里的
#   动作=被转述的动作 + 「并未离开」否定守卫）F3 到达词表补前来/赶来/过来 F4 转述指认「那就是/这便是」。
#   ）——读数较 v0.2.2 变更，v01/v02/v021/v022 归档不动。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/l3_corpus_readout.py [--twice]
#       > sampling/l3-corpus-v023.console.log 2>&1
# --twice=归档 replay 重算一致性验证（重跑比对 JSON 哈希，不一致=派生逻辑有非确定性 bug）。
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.metrics import _section_body                     # noqa: E402
from plot_engine.l3.scene_index import build_scene_index          # noqa: E402
from plot_engine.l3.triggers import needs_deep, run_light         # noqa: E402

dump = Path(__file__).resolve().parent / "wpe50ch"
BAD_CH = 50  # 回归闸章（pack §1.1 锚定义，现势=①②两锚）


def run_all():
    report = {}
    for md in sorted(dump.glob("ch*.md")):
        ch = int(md.stem[2:])
        body = _section_body(md.read_text(encoding="utf-8", errors="replace").splitlines(),
                             "Draft")
        cands = run_light(ch, body)
        frames = build_scene_index(ch, body)
        report[ch] = {
            "scenes": len(frames),
            "needs_deep": needs_deep(frames),
            "candidates": [c.model_dump() for c in cands],
        }
    return report


def digest(report) -> str:
    blob = json.dumps(report, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


rep = run_all()
if "--twice" in sys.argv:
    rep2 = run_all()
    print(f"重算一致性：{'一致' if digest(rep) == digest(rep2) else '不一致=BUG'} "
          f"（sha256[:16]={digest(rep)}）")

total = {"A": 0, "B": 0, "C": 0, "D": 0}
for ch in sorted(rep):
    r = rep[ch]
    kinds = {}
    for c in r["candidates"]:
        kinds[c["family"]] = kinds.get(c["family"], 0) + 1
        total[c["family"]] += 1
    ks = "/".join(f"{k}{v}" for k, v in sorted(kinds.items())) or "-"
    deep = " 深档信号" if r["needs_deep"] else ""
    tag = " [BAD回归闸]" if ch == BAD_CH else ""
    print(f"ch{ch:02d} 场景={r['scenes']} 候选={len(r['candidates'])} {ks}{deep}{tag}")
    for c in r["candidates"]:
        ev = ";".join(c["evidence_refs"])
        ep = f" [{c['epistemic_pair']}]" if c["epistemic_pair"] else ""
        print(f"    {c['family']}|{c['rule_id']}|{ev}|{c['detail']}{ep}")

anchor_fams = {c["family"] for c in rep.get(BAD_CH, {}).get("candidates", [])}
# 两锚制（tff 2026-10-18 亲拍，pack §1.1/§7.16）：锚③（003↔023 key_custody）容许多义可同真读法
# ⇒ 撤回判误、退出回归闸；闸按锚行号钉死，不只认族别出火。
A1 = any(c["family"] == "A" and c["evidence_refs"] == ["9-9"] for c in rep[BAD_CH]["candidates"])
B2 = any(c["family"] == "B" and c["evidence_refs"] == ["1-20", "22-30"] for c in rep[BAD_CH]["candidates"])
print(f"\nch50 回归闸（两锚制）：{sum((A1, B2))}/2 全中"
      if A1 and B2 else f"\nch50 回归闸（两锚制）：掉锚 锚①{A1} 锚②{B2} 候选族={sorted(anchor_fams)}")
print(f"合计：50 章 候选 A{total['A']} B{total['B']} C{total['C']} D{total['D']} "
      f"共 {sum(total.values())}（零 LLM 成本 $0）")

out = Path(__file__).resolve().parent / "l3-corpus-v023.json"
out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"JSON 出口：{out.name}（sha256[:16]={digest(rep)}）")
