# 一次性复核（不入库、不改尺面）：pack §7.19 那次「§7.18 空降到达闸证伪」读数的重建（tff 2026-10-19 裁定=需要）。
# 账面描述逐字复原两种历史闸形，跑在当前 v0.3.0 帧面上，外加本批落码的紧版做对照：
#   闸形A=同地点回入 + 上一帧硬离开 + 本帧无位移词到达（历史读数=仅 ch50 锚② 1 条，ch08 零命中）
#   闸形B=A 改为要求地点跳变（历史读数=9 条落 ch06/07/10/40/42/49，ch08 零命中）
#   紧版=find_skydrop_arrivals（落定锚=上一帧由位移叙述把人落到别处）
# 复核目的=验证「两形抓不到 ch08」的根因确为 F2（整行拒绝把 ch08 L015/L016 双杀），而非闸形本身无解。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/_skydrop_spike.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.metrics import _section_body                          # noqa: E402
from plot_engine.l3.scene_index import build_scene_index               # noqa: E402
from plot_engine.l3.temporal_checks import (find_skydrop_arrivals,     # noqa: E402
                                            find_space_rewind)

DUMP = Path(__file__).resolve().parent / "wpe50ch"


def gate_a(frames):
    """闸形A：实体硬离开→同地点再现，中间只有门窗口到达（无位移支到达）=候选。"""
    out = []
    open_dep = {}
    for fr in frames:
        for e in fr.arrived:
            open_dep.pop(e, None)
        for e in fr.present:
            prev = open_dep.get(e)
            if prev is not None and fr.location_text == prev.location_text:
                weak_only = e in fr.arrived and e not in fr.arrived_move
                out.append((fr.chapter, e, prev.scene_seq, fr.scene_seq, weak_only,
                            f"{prev.line_start}-{prev.line_end};{fr.line_start}-{fr.line_end}"))
        for e in fr.departed:
            open_dep[e] = fr
    return out


def gate_b(frames):
    """闸形B：A 判据里的「同地点回入」换成「地点跳变」（离开后在另一地点再现，中间无位移到达）。"""
    out = []
    open_dep = {}
    for fr in frames:
        for e in fr.arrived:
            open_dep.pop(e, None)
        for e in fr.present:
            prev = open_dep.get(e)
            if prev is not None and fr.location_text != prev.location_text:
                weak_only = e in fr.arrived and e not in fr.arrived_move
                out.append((fr.chapter, e, prev.scene_seq, fr.scene_seq, weak_only,
                            f"{prev.line_start}-{prev.line_end};{fr.line_start}-{fr.line_end}"))
        for e in fr.departed:
            open_dep[e] = fr
    return out


def run(fn, label):
    rows = []
    for md in sorted(DUMP.glob("ch*.md")):
        ch = int(md.stem[2:])
        body = _section_body(md.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
        rows += [(ch,) + r[1:] for r in fn(build_scene_index(ch, body))]
    hit8 = [r for r in rows if r[0] == 8]
    print(f"\n[{label}] 总数={len(rows)} ch08 命中={len(hit8)}")
    for r in rows:
        print(f"   ch{r[0]:02d} {r[1]} 场景{r[2]}→{r[3]} 门窗支独证={r[4]} {r[5]}")
    return rows


run(gate_a, "闸形A 同地点回入")
run(gate_b, "闸形B 地点跳变")
tight = []
for md in sorted(DUMP.glob("ch*.md")):
    ch = int(md.stem[2:])
    body = _section_body(md.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
    for c in find_skydrop_arrivals(build_scene_index(ch, body)):
        tight.append((ch, c.evidence_refs, c.detail[:60]))
print(f"\n[紧版 find_skydrop_arrivals] 总数={len(tight)}")
for t in tight:
    print("   ch%02d" % t[0], t[1], t[2])

# 根因对照：同一帧面下 B 主判据（space_rewind）须仍=1 条（ch50 锚②），证明 F2 修复没动 B 面。
b = []
for md in sorted(DUMP.glob("ch*.md")):
    ch = int(md.stem[2:])
    body = _section_body(md.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
    b += [(ch, c.evidence_refs) for c in find_space_rewind(build_scene_index(ch, body))]
print("\n[B 主判据 space_rewind] 总数=", len(b), b)
