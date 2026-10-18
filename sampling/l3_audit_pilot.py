# L3 双腿审计试点（l3-audit-v2.3，同对账逻辑吃 v0.3.0 底料复跑，tff 2026-10-19「确认启动中批」=稽核 F2 根治面）。
# 腿一=inkos 式整章自报（qwen2.5:32b@temp0，level3-pilot-v044=宿主标注换成 v0.2.3 候选后的复跑，编号行+引文行号+空结果合法）；
# 腿二=oh-story 式宿主确定性直出（run_light 候选=l3-corpus-v030.json，零 LLM）。
# 审判=宿主侧零 LLM 对账：同章同族、证据行集合有交集=双证；只腿一有=LLM独报（新域候选/幻觉待核）；
#   只腿二有=宿主独报（工件或模型漏检待核）。候选≠定罪 severity 恒 OBS，终审=HTML 呈 tff 真人裁。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/l3_audit_pilot.py
#       > sampling/l3-audit-v23.console.log 2>&1
# v2.0 归档（v043 腿一 + v021 腿二 + l3-audit-v20.trial.json + l3-audit-review.html）不动，tff 终审在 pack §7.16。
import html as htmlmod
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from plot_engine.metrics import _section_body                    # noqa: E402
from plot_engine.l3.scene_index import strip_comments            # noqa: E402

LOG = (HERE / "level3-pilot-v044.console.log").read_text(encoding="utf-8")
HOST = json.loads((HERE / "l3-corpus-v030.json").read_text(encoding="utf-8"))
CHS = sorted({int(m.group(1)) for m in re.finditer(r"^ch(\d+) \[", LOG, re.M)})


def body_lines(ch):
    return strip_comments(_section_body(
        (HERE / "wpe50ch" / f"ch{ch:02d}.md").read_text(encoding="utf-8", errors="replace").splitlines(),
        "Draft"))[0]


def line_set(qtext, lines):
    """引文（⏎ 连接=原行序）→ 送检行号集合（逐行 verbatim 包含反查，短于 6 字不据）。"""
    hit = set()
    for qseg in qtext.split("⏎"):
        q = qseg.strip()
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if len(s) >= 6 and s in q:
                hit.add(i)
    return hit


# ---- 腿一：解析 v043 finding 台账 ----
llm = {}
for ch in CHS:
    llm[ch] = []
cur = None
for ln in LOG.splitlines():
    m = re.match(r"^ch(\d+) \[", ln)
    if m:
        cur = int(m.group(1))
        continue
    m = re.match(r"^    ([ABC])\|(.*)$", ln)
    if m and cur:
        p = m.group(2).split("|")
        q = line_set(p[0] + "⏎" + p[1], body_lines(cur))
        llm[cur].append({"fam": m.group(1), "refs": [p[0], p[1]],
                         "desc": "|".join(p[2:3])[:120], "lines": sorted(q)})

# ---- 腿二：宿主候选行号集合 ----
host = {}
for ch in CHS:
    host[ch] = []
    for c in HOST.get(str(ch), {}).get("candidates", []):
        s = set()
        for r in c["evidence_refs"]:
            a, b = (int(x) for x in r.split("-"))
            s.update(range(a, b + 1))
        host[ch].append({"fam": c["family"], "refs": c["evidence_refs"],
                        "detail": c["detail"], "lines": sorted(s)})

# ---- 审判：同章同族贪心一对一（证据行交集≥1=双证）----
trial = []
for ch in CHS:
    for fam in "ABC":
        hs = list(host[ch] and [h for h in host[ch] if h["fam"] == fam])
        ls = [l for l in llm[ch] if l["fam"] == fam]
        used = set()
        for l in ls:
            match = next((i for i, h in enumerate(hs)
                          if i not in used and set(l["lines"]) & set(h["lines"])), None)
            if match is None:
                trial.append({"ch": ch, "fam": fam, "class": "LLM独报", "llm": l})
            else:
                used.add(match)
                trial.append({"ch": ch, "fam": fam, "class": "双证", "llm": l, "host": hs[match]})
        trial += [{"ch": ch, "fam": fam, "class": "宿主独报", "host": h}
                  for i, h in enumerate(hs) if i not in used]

from collections import Counter
cls_cnt = Counter(t["class"] for t in trial)
fam_cnt = Counter((t["fam"], t["class"]) for t in trial)  # Counter=缺组合读 0（v2.2 面 B 宿主独报归零暴露旧写法 KeyError）
print(f"腿一=32b@temp0 整章自报（v044 复跑 {sum(len(v) for v in llm.values())} 条，$0）"
      f"｜腿二=宿主 v0.3.0 候选｜审判=行集合交集对账（零 LLM；腿一 v044 底料仍为 v0.2.3 标注=滞后一版）")
for fam in "ABC":
    print(f"  {fam}: " + " ".join(f"{c}{fam_cnt[(fam, c)]}" for c in ("双证", "LLM独报", "宿主独报")
                                  if fam_cnt[(fam, c)]))
print(f"合计: 双证={cls_cnt['双证']} LLM独报={cls_cnt['LLM独报']} 宿主独报={cls_cnt['宿主独报']}")
ch50 = [t for t in trial if t["ch"] == 50]
print(f"ch50 锚闸对照：双证 {sum(1 for t in ch50 if t['class'] == '双证')}/{len(ch50)} 条入审")
for t in trial:
    tag = {"双证": "✓", "LLM独报": "L", "宿主独报": "H"}[t["class"]]
    d = (t.get("llm", {}).get("desc") or t.get("host", {}).get("detail", ""))[:88]
    refs = ((t.get("llm", {}).get("lines") or []) + [str(r) for r in t.get("host", {}).get("refs", [])])
    print(f"  {tag}|{t['ch']:02d}|{t['fam']}|{d}|{refs[:6]}")

Path(HERE / "l3-audit-v23.trial.json").write_text(
    json.dumps(trial, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- HTML 呈堂（版式沿 l3-judge-review.html 先例）----
STYLE = """
:root{--bg:#fbf9f5;--fg:#22221f;--mut:#8a8578;--line:#e4dfd3;--red:#a8342a;--blue:#2a5aa8;--org:#b8730a}
*{box-sizing:border-box}body{margin:0;font:16px/1.95 "Source Han Serif SC","Songti SC","Noto Serif CJK SC",serif;background:var(--bg);color:var(--fg)}
#app{display:flex;min-height:100vh}
aside{width:250px;flex:none;border-right:1px solid var(--line);padding:16px 0;position:sticky;top:0;height:100vh;overflow:auto;background:#f4f0e6}
aside h1{font:400 13px/1 system-ui;margin:0 16px 6px;color:var(--mut);letter-spacing:.14em}
aside p{font:11px/1.6 system-ui;color:var(--mut);margin:0 16px 12px}
#toc a{display:flex;align-items:center;gap:8px;padding:8px 16px;font:14px system-ui;color:inherit;text-decoration:none;border-left:3px solid transparent}
#toc a:hover{background:#ece5d5}
#toc i{width:8px;height:8px;border-radius:99px;flex:none;background:var(--red)}
#toc s{margin-left:auto;color:var(--mut);text-decoration:none;font:11px system-ui}
main{flex:1;max-width:900px;padding:30px 46px 140px}
h2{font:700 22px/1.4 system-ui;margin:46px 0 6px;border-bottom:2px solid var(--line);padding-bottom:6px}
.legend,.note{font:12px/1.8 system-ui;color:var(--mut);margin:0 0 18px}
.card{font:13px/1.8 system-ui;background:#fff;border:1px solid var(--line);border-left:5px solid var(--mut);border-radius:6px;padding:10px 14px;margin:10px 0}
.card.t{border-left-color:var(--red)}.card.p{border-left-color:var(--blue)}.card.r{border-left-color:var(--org)}
.card .q{color:var(--mut)}
.tag{font:11px system-ui;padding:1px 8px;border-radius:99px;color:#fff;margin-right:6px}
.tag.t{background:var(--red)}.tag.p{background:var(--blue)}.tag.r{background:var(--org)}
pre.body{font:14px/2 inherit;white-space:pre-wrap;background:#fff;border:1px solid var(--line);border-radius:6px;padding:18px 20px}
mark{padding:0 2px;border-radius:3px}
mark.t{background:#f7d5cf}mark.r{background:#f5e3c3}mark.p{background:#d5e2f7}
.ln{color:#c6bfae;font:11px monospace;margin-right:8px}
"""
CLS = {"双证": ("t", "双证"), "LLM独报": ("p", "LLM独报"), "宿主独报": ("r", "宿主独报")}
cards, marks = {}, {}
for t in trial:
    cls, lab = CLS[t["class"]]
    l, h = t.get("llm", {}), t.get("host", {})
    body_html = (f'<div class="card {cls}"><span class="tag {cls}">{lab}</span><b>{t["fam"]}</b> '
                 + (f'腿一：{l.get("desc", "")}<br>' if l else "")
                 + (f'<div class="q">引证行：{"、".join(map(str, l.get("lines", [])))}</div>' if l else "")
                 + (f'<div>腿二：{h.get("detail", "")}</div>' if h else "") + "</div>")
    cards.setdefault(t["ch"], []).append(body_html)
    for i in set(l.get("lines", [])) | set(h.get("lines", [])):
        cur = marks.setdefault(t["ch"], {})
        if cls == "t" or i not in cur:
            cur[i] = cls
parts, toc = [], []
for ch in sorted(cards):
    lines = body_lines(ch)
    mk = marks.get(ch, {})
    page = "".join(f'<mark class="{mk[i]}"><span class="ln">{i:03d}</span>{htmlmod.escape(ln)}</mark>\n'
                   if i in mk else f'<span class="ln">{i:03d}</span>{htmlmod.escape(ln)}\n'
                   for i, ln in enumerate(lines, 1))
    n = Counter(t["class"] for t in trial if t["ch"] == ch)
    parts.append(f'<h2 id="ch{ch}">ch{ch:02d}（{len(cards[ch])} 条：'
                 f'双证 {n["双证"]} / LLM独 {n["LLM独报"]} / 宿主独 {n["宿主独报"]}）</h2>'
                 + "\n".join(cards[ch]) + f"<pre class=body>{page}</pre>")
    toc.append(f'<a href="#ch{ch}"><i></i>ch{ch:02d}<s>{len(cards[ch])} 条</s></a>')
Path(HERE.parent / "docs" / "samples" / "l3-audit-review-v23.html").write_text(
    f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>L3 双腿审计审判页 · l3-audit-v2.3</title>
<style>{STYLE}</style></head><body><div id="app">
<aside><h1>条目导航</h1>
<p>腿一=整章自报（32b@temp0，inkos 式，v044 复跑）；腿二=宿主确定性候选（l3-v0.2.3）；审判=证据行交集对账（零 LLM）。
<b>红=双证（两条腿同指） 蓝=LLM独报 橙=宿主独报</b>。候选≠定罪，请 tff 真人裁。行号=strip_comments 基准。</p>
<nav id="toc">{''.join(toc)}</nav></aside>
<main><h2 style="margin-top:0">L3 双腿审计 · 同输入交叉审判呈堂页（l3-audit-v2.3，v0.3.0 底料复跑）</h2>
<p class=legend>数据源 sampling/level3-pilot-v044.console.log（腿一）+ sampling/l3-corpus-v030.json（腿二）
+ l3-audit-v23.trial.json（审判台账）。口径 pack §7.9+勘误；<b>判据现势=§7.16 tff 亲拍（含「文本容许多义可同真读法→不算穿帮」条款）；
ch50 锚=①②两锚制</b>。前页 v2.0/v2.1（tff 已终审）保留不动，本页为其 v2.3 底料对照复跑。</p>
{''.join(parts)}</main></div></body></html>""", encoding="utf-8")
print("HTML 呈堂：docs/samples/l3-audit-review-v23.html")
