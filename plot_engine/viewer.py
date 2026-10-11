"""样章阅读器：一个自包含 HTML，左边章节、右边正文，判定收在可折叠面板里。

为什么要它：`sample.md` 是归档格式，人读 30 KB 中文长文需要**能跳章、能看出哪章没过线**。
零依赖、零构建、离线可开（正文与判定都内嵌在页面里，不 fetch），双击就是一次查看。
取料走 `plot_engine.reading`——和 `plot_engine.sample` 同一个「最终稿」定义。
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import List

from plot_engine.reading import STATUS_CN, paragraphs, read_run

# 这些正文出自合成夹具（`tests/fixtures/traitor_arc.json`），用来校尺，不是著作成品。
NOTE = "正文出自合成夹具《叛徒弧》：人名是占位符，story_goal 逐章喂给 Writer，故章首同质。" \
       "这是量具的读数，不是可发表的书稿。"

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>样章阅读器</title>
<style>
:root{--bg:#fbf9f5;--fg:#22221f;--mut:#8a8578;--line:#e4dfd3;
  --ok:#2f7d4f;--nh:#b8730a;--arc:#a8342a}
*{box-sizing:border-box}
body{margin:0;font:16px/1.95 "Source Han Serif SC","Songti SC","Noto Serif CJK SC",serif;
  background:var(--bg);color:var(--fg)}
#app{display:flex;min-height:100vh}
aside{width:236px;flex:none;border-right:1px solid var(--line);padding:16px 0;
  position:sticky;top:0;height:100vh;overflow:auto;background:#f4f0e6}
aside h1{font:400 13px/1 system-ui;margin:0 16px 12px;color:var(--mut);letter-spacing:.14em}
#runs{display:flex;gap:6px;padding:0 16px 14px;flex-wrap:wrap}
#runs button{font:12px system-ui;padding:5px 10px;border:1px solid var(--line);background:#fff;
  border-radius:99px;cursor:pointer}
#runs button.on{background:var(--fg);color:#fff;border-color:var(--fg)}
#toc a{display:flex;align-items:center;gap:8px;padding:9px 16px;font:14px system-ui;
  color:inherit;text-decoration:none;border-left:3px solid transparent}
#toc a:hover{background:#ece5d5}
#toc a.on{border-left-color:var(--fg);background:#ece5d5;font-weight:700}
#toc i{width:8px;height:8px;border-radius:99px;flex:none}
#toc s{margin-left:auto;color:var(--mut);text-decoration:none;font:11px system-ui}
main{flex:1;max-width:840px;padding:30px 48px 140px}
.sum{font:12px/1.8 system-ui;color:var(--mut);margin:0 0 28px}
h2{font-size:23px;margin:0 0 4px}
.badge{font:12px system-ui;padding:2px 9px;border-radius:99px;color:#fff;vertical-align:2px}
.wc{font:12px system-ui;color:var(--mut);margin-left:8px}
p{margin:0 0 1.05em;text-indent:2em}
details{margin:14px 0;font:13px/1.7 system-ui;background:#f1ece0;border:1px solid var(--line);
  border-radius:6px;padding:8px 13px;color:#45413a}
details p{font:13px/1.7 system-ui;text-indent:0;margin:.25em 0}
summary{cursor:pointer;color:var(--mut)}
.keys{font:12px system-ui;color:var(--mut);margin:26px 0 0}
@media(max-width:760px){
  aside{position:sticky;width:100%;height:auto;border-right:0;border-bottom:1px solid var(--line);
    padding:10px 0}
  #toc{display:flex;overflow:auto;padding:0 8px}#toc a{border-left:0;flex:none;padding:6px 9px}
  #toc s{display:none}main{padding:18px 20px 90px}}
</style></head><body><div id="app">
<aside><h1>样章</h1><div id="runs"></div><nav id="toc"></nav></aside>
<main id="body"></main>
</div>
<script>
const RUNS = __DATA__;
const C = {OK:'var(--ok)',NEEDS_HUMAN:'var(--nh)',ARC_CONFLICT:'var(--arc)',FAIL:'var(--arc)'};
let run = 0, idx = 0;
const esc = s => (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function render(){
  const r = RUNS[run], chs = r.chapters, c = chs[idx];
  document.getElementById('runs').innerHTML = RUNS.map((x,i)=>
    `<button class="${i===run?'on':''}" data-run="${i}">${esc(x.label)}</button>`).join('');
  document.getElementById('toc').innerHTML = chs.map((x,i)=>
    `<a href="#c${x.no}" data-ch="${i}" class="${i===idx?'on':''}">
       <i style="background:${C[x.status]||'#888'}"></i>第 ${x.no} 章
       <s>${x.bucket==='first_pass'?'首轮':x.bucket==='rewrite_rescued'?'救回':
            x.bucket==='renegotiate_only'?'仅重议':'处置'}</s></a>`).join('');
  const det = (t, items) => items.length
    ? `<details><summary>${t}（${items.length}）</summary>${items.map(x=>`<p>${esc(x)}</p>`).join('')}</details>`
    : '';
  const paras = (c.text ? paragraphs(c.text) : ['（本轮没有产出正文）']).map(p=>`<p>${esc(p)}</p>`).join('');
  document.getElementById('body').innerHTML =
    `<div class="sum">${esc(r.label)}｜抽取尺 <b>${esc(r.ruler)}</b>｜干净口径 E2 <b>${r.e2}</b>｜人工处置率 <b>${r.disp}</b>｜`
    + `共 ${chs.length} 章｜<span style="color:var(--ok)">绿=已提交</span> `
    + `<span style="color:var(--nh)">橙=待人工</span> <span style="color:var(--arc)">红=判死</span>`
    + `<br>${esc(r.note)}</div>
     <h2>第 ${c.no} 章
       <span class="badge" style="background:${C[c.status]||'#888'}">${esc(c.status_cn||c.status)}</span>
       <span class="wc">修订 ${c.rounds} 轮 · ${(c.text||'').length} 字</span></h2>
     ${det('判定（rule_id 原文）', c.findings)}${det('修稿指引', c.guide)}
     <div style="height:20px"></div>${paras}
     <p class="keys">快捷键：↑↓ 或 j/k 翻章｜←→ 换跑法｜判定面板点标题展开</p>`;
  window.scrollTo(0, 0);
}
function paragraphs(t){return t.split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean);}
document.addEventListener('click', e=>{
  const b = e.target.closest('#runs button'); if (b){ run = +b.dataset.run; idx = 0; render(); e.preventDefault(); }
  const a = e.target.closest('#toc a');    if (a){ idx = +a.dataset.ch; render(); e.preventDefault(); }
});
document.addEventListener('keydown', e=>{
  const n = RUNS[run].chapters.length;
  if (e.key==='ArrowDown'||e.key==='j'){ if(idx<n-1){idx++;render();} e.preventDefault(); }
  if (e.key==='ArrowUp'  ||e.key==='k'){ if(idx>0){idx--;render();}   e.preventDefault(); }
  if (e.key==='ArrowRight'){ run=(run+1)%RUNS.length; idx=0; render(); }
  if (e.key==='ArrowLeft' ){ run=(run+RUNS.length-1)%RUNS.length; idx=0; render(); }
});
render();
</script></body></html>
"""


def build_viewer(run_dirs: List[Path]) -> str:
    payload = [{"label": r["label"], "e2": r["e2"], "disp": r["disp"], "note": NOTE,
                "ruler": r["ruler"],
                "chapters": [dict(c, status_cn=STATUS_CN.get(c["status"], c["status"]))
                             for c in r["chapters"]]}
               for r in map(read_run, run_dirs)]
    return _TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))


def main(argv: None | List[str] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m plot_engine.viewer",
                                 description="把若干采样跑的逐章快照合成一个可翻阅的 HTML")
    ap.add_argument("runs", nargs="+", help="采样目录（含 dump/），可给多个做并排对照")
    ap.add_argument("-o", "--out", default="docs/samples/viewer.html")
    ns = ap.parse_args(argv)

    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_viewer([Path(r) for r in ns.runs]), encoding="utf-8")
    print(f"阅读器 → {out}（{out.stat().st_size / 1024:.0f} KB，离线双击即开）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
