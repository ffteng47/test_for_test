# 采样 dump 检视页：左导航=目录/章，右=渲染后的章节文档（一次性工具）。
# 用法: python sampling/make_dump_view.py v4d1 [v4d2 v4d3 ...]  -> sampling/dump_view.html
import html as H
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
dirs = sys.argv[1:] or ["v4d1"]

def render(md: str) -> str:
    out, li_open = [], False
    for line in md.splitlines():
        m = re.match(r"^(#{1,4}) (.*?)( —.*)?$", line)
        if m:
            if li_open: out.append("</ul>"); li_open = False
            lvl, txt = len(m.group(1)), H.escape(m.group(2) + (m.group(3) or ""))
            out.append(f"<h{lvl}>{txt}</h{lvl}>")
        elif line.startswith("- "):
            if not li_open: out.append("<ul class=props>"); li_open = True
            out.append(f"<li>{H.escape(line[2:])}</li>")
        elif line.strip() == "":
            if li_open: out.append("</ul>"); li_open = False
        else:
            if li_open: out.append("</ul>"); li_open = False
            out.append(f"<p>{H.escape(line)}</p>")
    if li_open: out.append("</ul>")
    return "\n".join(out)

pages, nav = {}, []
for d in dirs:
    dp = ROOT / d
    if not dp.is_dir(): continue
    for f in sorted(dp.glob("ch*.md")):
        key = f"{d}/{f.stem}"
        pages[key] = render(f.read_text(encoding="utf-8"))
        head = pages[key].split("</h1>")[0][3:]
        nav.append((key, head))
    jf = dp / "_junk.json"
    if jf.exists():
        junk = json.loads(jf.read_text(encoding="utf-8-sig"))
        rows = "".join(f"<tr><td>{b.get('chapter','')}</td><td>{H.escape(str(b.get('reason','')))}"
                       f"</td><td><code>{H.escape(json.dumps(b.get('gave'), ensure_ascii=False))}</code></td></tr>"
                       for b in junk)
        pages[f"{d}/_junk"] = f"<h1>{d} 坏料 {len(junk)} 条</h1><table><tr><th>章</th><th>reason</th><th>gave</th></tr>{rows}</table>"
        nav.append((f"{d}/_junk", f"[{d}] 坏料 {len(junk)}"))

page_json = json.dumps(pages, ensure_ascii=False)
nav_json = json.dumps([k for k, _ in nav], ensure_ascii=False)
html = f"""<!doctype html><meta charset="utf-8"><title>采样 dump 检视</title><style>
body{{margin:0;font:14px/1.7 system-ui;display:flex;height:100vh}}
nav{{width:230px;border-right:1px solid #ccc;padding:8px;overflow:auto;flex:none}}
nav a{{display:block;padding:3px 8px;cursor:pointer;border-radius:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
nav a.on{{background:#dde}}nav a:hover{{background:#eef}}
nav h4{{margin:10px 4px 2px;font-size:12px;color:#888}}
main{{flex:1;overflow:auto;padding:16px 28px;max-width:900px}}
h1{{font-size:20px}}h2{{font-size:17px;margin-top:22px;border-bottom:1px solid #eee}}
p{{margin:6px 0;text-indent:2em}}
ul.props{{background:#f7f7fb;padding:8px 8px 8px 24px;border-radius:6px}}
ul.props li{{font:12px ui-monospace;margin:2px 0}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:2px 8px}}
</style><nav id=nav></nav><main id=main></main><script>
const P={page_json},NAV={nav_json};
const nav=document.getElementById('nav'),main=document.getElementById('main');
let cur='',h='';for(const k of NAV){{const d=k.split('/')[0];if(d!==cur){{if(cur)h+='</div>';h+=`<div><h4>${{d}}</h4>`;cur=d;}}
  h+=`<a data-k="${{k}}">${{k.split('/')[1]}}</a>`}}nav.innerHTML=h+'</div>';
function show(k){{main.innerHTML=P[k];nav.querySelectorAll('a').forEach(a=>a.classList.toggle('on',a.dataset.k===k))}}
nav.querySelectorAll('a').forEach(a=>a.onclick=()=>show(a.dataset.k));
show(NAV[0]);
</script>"""
out = ROOT / "dump_view.html"
out.write_text(html, encoding="utf-8")
print(out)
