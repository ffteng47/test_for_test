# W5 回放数据的检视页（一次性工具）：左导航=章桶，右=两跑提案对照。
# 键口径与 instr 一致：type|actor|target；命中=两跑都有，单边=波动条目。
import json, sys
from pathlib import Path

here = Path(__file__).resolve().parent
passes = []
for name in ("pass1.json", "pass2.json"):
    p = here / name
    if p.exists():
        passes.append((name, json.loads(p.read_text(encoding="utf-8"))))

def key(it):
    return "|".join(str(it.get(k, "")) for k in ("type", "actor", "target"))

chapters = sorted({int(c) for _, d in passes for c in d["chapters"]})
data = {}
for ch in chapters:
    bucket = {}
    for i, (name, d) in enumerate(passes):
        items = d["chapters"].get(str(ch), d["chapters"].get(ch, []))
        for it in items:
            e = bucket.setdefault(key(it), {"it": it, "p": [False, False]})
            e["p"][i] = True
    data[ch] = sorted(bucket.values(), key=lambda e: (not (e["p"][0] and e["p"][1]), e["p"], str(e["it"]["type"])))

meta = [{"name": n, "instr": d["instr"], "ruler": d["ruler"], "lane": d.get("lane", ""),
         "tokens": d["tokens"], "malformed": len(d["malformed"])} for n, d in passes]

html = """<!doctype html><meta charset="utf-8"><title>W5 回放检视</title>
<style>
body{margin:0;font:14px/1.5 system-ui;display:flex;height:100vh}
nav{width:180px;border-right:1px solid #ccc;padding:8px;overflow:auto;flex:none}
nav a{display:block;padding:4px 8px;cursor:pointer;border-radius:4px}
nav a.on,nav a:hover{background:#eef}
main{flex:1;overflow:auto;padding:12px 24px}
table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid #ddd;padding:3px 8px;text-align:left;vertical-align:top}
tr.both{background:#f2fbf2}tr.only{background:#fdf2f2}
.badge{font-size:12px;color:#666}.meta{color:#666;font-size:12px;margin:4px 0 12px}
pre{white-space:pre-wrap;margin:0;font:12px ui-monospace}
</style><nav id=nav></nav><div><div class=meta id=meta></div><main id=main></main></div>
<script>
const DATA=%DATA%,META=%META%;
const nav=document.getElementById('nav');
document.getElementById('meta').innerHTML=META.map(m=>`${m.name}｜${m.instr}｜尺 ${m.ruler}｜车道 ${m.lane}｜tokens ${m.tokens}｜坏料 ${m.malformed}`).join('<br>')+(DATA.length&&2>META.length?'<br>（Pass 2 未落盘，单边=全量待比）':'');
function show(ch){
  document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.dataset.c==ch));
  const rows=DATA.find(d=>d.ch==ch).items.map(e=>{
    const it=e.it,both=e.p[0]&&e.p[1];
    return `<tr class=${both?'both':'only'}><td>${it.type}</td><td>${it.actor??''}</td><td>${it.target??''}</td><td><pre>${JSON.stringify(it.payload)}</pre></td><td class=badge>${it.source_ref??''}</td><td class=badge>${e.p.map(p=>p?'✓':'–').join(' ')}</td></tr>`}).join('');
  main.innerHTML=`<h3>ch${String(ch).padStart(2,'0')}</h3><table><tr><th>type</th><th>actor</th><th>target</th><th>payload</th><th>source_ref</th><th>P1 P2</th></tr>${rows}</table>`;
}
DATA.forEach(d=>{const a=document.createElement('a');a.textContent='ch'+String(d.ch).padStart(2,'0');a.dataset.c=d.ch;a.onclick=()=>show(d.ch);nav.append(a)});
show(DATA[0].ch);
</script>"""
html = html.replace("%DATA%", json.dumps(
    [{"ch": ch, "items": data[ch]} for ch in chapters], ensure_ascii=False))
html = html.replace("%META%", json.dumps(meta, ensure_ascii=False))
out = here / "view.html"
out.write_text(html, encoding="utf-8")
print(out)
