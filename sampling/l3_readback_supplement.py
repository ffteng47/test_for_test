# 补裁补充呈堂页（§7.22 遗留 25 项=页外新火 11 + A 族行号位移 12 + 空降 2）。
# 腿一只覆盖 20 章，这些章任何双腿页都没有正文可读，故单出一页；只渲染、零 LLM、不动尺面。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/l3_readback_supplement.py \
#       > sampling/l3-readback-supplement.console.log 2>&1
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from plot_engine.l3.temporal_checks import find_skydrop_arrivals  # noqa: E402
from plot_engine.l3.scene_index import build_scene_index, strip_comments  # noqa: E402
from plot_engine.metrics import _section_body  # noqa: E402

OLD = json.loads((HERE / "l3-corpus-v023.json").read_text(encoding="utf-8"))
NEW = json.loads((HERE / "l3-corpus-v030.json").read_text(encoding="utf-8"))
PAGE_CH = {2, 8, 12, 13, 14, 20, 21, 22, 23, 26, 35, 40, 42, 44, 48, 50}  # v045 呈堂页实有卡章


def body(ch):
    return strip_comments(_section_body(
        (HERE / "wpe50ch" / f"ch{ch:02d}.md").read_text(encoding="utf-8", errors="replace")
        .splitlines(), "Draft"))[0]


def a_cards(ch, ent=None):
    out = []
    for c in NEW[str(ch)]["candidates"]:
        if c["family"] != "A":
            continue
        e = c["detail"].split(" 在")[0]
        if ent and e not in ent:
            continue
        out.append((e, c["evidence_refs"][0]))
    return out


def old_ref(ch, ent):
    for c in OLD[str(ch)]["candidates"]:
        if c["family"] == "A" and c["detail"].split(" 在")[0] == ent:
            return c["evidence_refs"][0]
    return "?"


items = {}  # 章 → [(标题, 高亮行号集合)]

# 1+2) 腿一未覆盖章的全部 A 族卡：v0.2.3 同实体有卡=行号位移（新旧两行都标），无卡=新火
for ch in sorted(set(int(k) for k in NEW) - PAGE_CH):
    for ent, ref in a_cards(ch):
        o = old_ref(ch, ent)
        if o not in ("?", ref):
            items.setdefault(ch, []).append(
                (f"位移 A｜{ent} {o}→{ref}（旧行+新行都标）",
                 {int(o.split('-')[0]), int(ref.split('-')[0])}))
        else:
            items.setdefault(ch, []).append(
                (f"新火 A｜{ent} 第{ref}行首次在场、此前无到达叙述",
                 {int(ref.split('-')[0])}))

# 3) 空降到达（旁路规则，未接 run_light，任何页都不出现）
for ch in range(1, 51):
    for c in find_skydrop_arrivals(build_scene_index(ch, body(ch))):
        rows = {int(r.split('-')[0]) for r in c.evidence_refs}
        items.setdefault(ch, []).append(
            (f"空降 B｜{c.detail}", rows | {int(r.split('-')[1]) for r in c.evidence_refs}))

CSS = ("body{font:14px/1.7 serif;background:#111;color:#ddd;margin:0;padding:24px}"
       "h2{color:#7fd;margin-top:32px;border-bottom:1px solid #333}"
       ".hd{color:#fc6;margin:14px 0 4px;font-weight:700}"
       "pre{background:#181818;padding:10px;white-space:pre-wrap;word-break:break-all}"
       "mark{background:#3a2d00;color:#ffd76e;padding:0 2px;display:block}"
       ".ln{color:#556;margin-right:6px}")

out = ["<!doctype html><meta charset=utf-8><title>L3 补裁补充呈堂页 · §7.22 遗留 25 项</title>",
       f"<style>{CSS}</style><h1 style='color:#7fd'>L3 补裁补充呈堂页</h1>",
       "<p>内容=腿一未覆盖章的 A 族新火/行号位移 + 空降到达旁路卡。<b>只呈正文，不判决</b>"
       "；候选≠定罪，severity 恒 OBS，画线权 tff。生成：sampling/l3_readback_supplement.py。</p>"]
for ch in sorted(items):
    bs = body(ch)
    out.append(f"<h2 id='ch{ch}'>ch{ch:02d}</h2>")
    for title, rows in items[ch]:
        out.append(f"<div class=hd>{html.escape(title)}</div><pre>")
        for i, ln in enumerate(bs, 1):
            t = f"<span class=ln>{i:03d}</span>{html.escape(ln)}"
            out.append(f"<mark>{t}</mark>" if i in rows else t)
        out.append("</pre>")

dst = HERE.parent / "docs" / "samples" / "l3-audit-readback.html"
dst.write_text("\n".join(out) + "\n", encoding="utf-8")
n = sum(len(v) for v in items.values())
print(f"卡 {n} 张｜章 {len(items)} 个：{sorted(items)}")
print("HTML 呈堂：docs/samples/l3-audit-readback.html")
