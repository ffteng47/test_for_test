"""盲评工作表（`docs/style-acceptance-v1.1.md` §3）：把若干跑法的章打散、去掉出处，发给人读。

为什么单独做这一步：判定读数知道「哪章过了线」，人读的是**另一件事**——这章好不好看。
两个读数必须解耦，否则人会被 provenance 带着打分（看到 `bo_q3_14b` 就默认它比 `8b` 好读）。
所以这里刻意产出**两份文件**：工作表只给编号与正文，答案键单独一份、评分收齐前不许打开。

取章用普查不用抽样：手上全部章数就是分母，任何「挑几章来评」都是在替被评者选题。
两条下限（≥30 章、失败类 ≥15）不满足时直接拒绝出题，出一张不够格的表比不出表更坏。
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import List

MIN_CHAPTERS = 30
MIN_FAILURES = 15


def pool(run_dirs: List[Path]) -> List[dict]:
    from plot_engine.reading import read_run

    out: List[dict] = []
    for d in run_dirs:
        r = read_run(Path(d))
        out += [{"run": r["label"], "chapter": c["no"], "status": c["status"],
                 "text": c["text"]}
                for c in r["chapters"] if c.get("text")]
    return out


def build(run_dirs: List[Path], seed: int = 0) -> List[dict]:
    items = pool(run_dirs)
    failures = sum(1 for x in items if x["status"] != "OK")
    if len(items) < MIN_CHAPTERS:
        raise ValueError(f"只有 {len(items)} 章可评，盲评下限 {MIN_CHAPTERS} 章：给的跑法不够")
    if failures < MIN_FAILURES:
        raise ValueError(f"失败类只有 {failures} 章，下限 {MIN_FAILURES}：这张表全是过线的章，"
                         f"量不出「判死的章是不是真难看」那一格")
    random.Random(seed).shuffle(items)
    return [dict(x, blind_id=i + 1) for i, x in enumerate(items)]


def render_worksheet(items: List[dict]) -> str:
    head = ("# 盲评工作表\n\n"
            "读法：每章只读不查，读完立刻打「愿意付费读」这一列（是/否），再补一句为什么。\n"
            "**这里没有出处、没有判定状态**——那是答案键里的事，评分收齐前不要打开它。\n\n")
    return head + "\n".join(f"## {x['blind_id']:02d}\n\n{x['text']}\n" for x in items)


def render_key(items: List[dict]) -> str:
    rows = "\n".join(f"| {x['blind_id']:02d} | {x['run']} | {x['chapter']} | {x['status']} |"
                     for x in items)
    return ("# 答案键（评分收齐前勿开）\n\n| 盲评号 | 跑法 | 原章号 | 判定终态 |\n"
            "|---|---|---|---|\n" + rows + "\n")


_RUBRIC = [("R1", "不复述", "同一批信息没有被近似重写 2–3 遍"),
           ("R2", "立场不漂移", "主角身份/阵营全章一致"),
           ("R3", "名物与数量自洽", "同一物/同一数只有一个指称与一个值"),
           ("R4", "不泄元数据", "没有标记、注释、标题、「本章悬念」一类非叙事文本"),
           ("R5", "段长与体量合规", "2–4 个自然段、成文、没有被截断"),
           ("R6", "单章可读", "不了解 State/契约也能说出谁在查什么、这章新发生了什么")]

_HTML = r"""<!DOCTYPE html>
<html lang="zh"><meta charset="utf-8"><title>盲评打分表 __N__ 章</title>
<style>
 body{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:0 auto;max-width:52em;padding:1em 1.5em 6em;
      line-height:1.8;color:#20252b;background:#fbfbf9}
 header{position:sticky;top:0;background:#fbfbf9;border-bottom:2px solid #444;padding:.5em 0;margin-bottom:1em;z-index:9}
 #bar{display:flex;gap:1em;align-items:center;flex-wrap:wrap;font-size:.95rem}
 progress{width:12em;height:.8em}
 button{padding:.35em .9em;font-size:.95rem;cursor:pointer}
 .ch{border-top:1px solid #ccc;padding:1.2em 0 1.6em}
 .ch h2{font-size:1rem;margin:0 0 .4em;color:#666}
 .txt{background:#fff;border:1px solid #e2e2dc;padding:1em 1.2em;white-space:pre-wrap;margin:.4em 0 .9em}
 label{margin-right:.9em;font-size:.93rem}
 .rrow{display:grid;grid-template-columns:max-content 1fr auto auto;gap:.15em .8em;
       align-items:baseline;margin-bottom:.35em}
 .rrow b{font-weight:600} .rrow small{color:#777;font-weight:400}
 textarea{width:100%;box-sizing:border-box;min-height:2.4em;font:inherit;font-size:.9rem}
 .done h2::after{content:" ✓";color:#1a7f37}
 #out{width:100%;height:16em;box-sizing:border-box;font:12px/1.5 monospace;white-space:pre}
 .warn{color:#b3261e;font-size:.85rem;margin-left:1em}
</style>
<header><div id="bar">
 <b>盲评打分表</b>
 <span>已完成 <span id="n">0</span>/__N__</span><progress id="p" max="__N__" value="0"></progress>
 <button onclick="dump()">导出评分</button><button onclick="copy()">复制</button>
 <span class="warn">这里没有出处、没有判定状态——评分收齐前不要打开答案键</span>
</div>
<div style="font-size:.85rem;color:#666;margin-top:.3em">
 每章：六条逐条判<b>过/不过</b>（<b>全过才算这章过</b>），再打「愿意付费读」，最后补一句为什么。
 读完再判，别回头改；判不出就留空（留空计入「证据缺失」，不算过）。</div></header>
<main id="m"></main>
<section style="border-top:2px solid #444;padding-top:1em">
 <h2>评分导出（先复制，再粘回仓库落盘；页面不联网，分数只存在这台机器的浏览器里）</h2>
 <textarea id="out" readonly></textarea></section>
<script>
const CH=__DATA__, R=__R__, K="blind-__SEED__", N=__N__;
let S={}; try{S=JSON.parse(localStorage.getItem(K)||"{}")}catch(e){S={}}
const V={1:"过",0:"不过"};
R.forEach(function(r){
  var row=document.createElement("div");row.className="rrow";
  var lab=document.createElement("b");lab.textContent=r[0]+" "+r[1];
  var hint=document.createElement("small");hint.textContent=r[2];
  row.appendChild(lab);row.appendChild(hint);
  [1,0].forEach(function(v){
    var l=document.createElement("label");
    var i=document.createElement("input");
    i.type="radio";i.name=r[0];i.value=v;l.appendChild(i);
    l.appendChild(document.createTextNode(v?"过":"不过"));row.appendChild(l);});
  window["mk_"+r[0]]=row;});
function payRow(c){
  var row=document.createElement("div");row.className="rrow";
  var lab=document.createElement("b");lab.textContent="愿意付费读";row.appendChild(lab);
  [[1,"是"],[0,"否"]].forEach(function(o){
    var l=document.createElement("label");var i=document.createElement("input");
    i.type="radio";i.name="pay_"+c;i.value=o[0];l.appendChild(i);
    l.appendChild(document.createTextNode(o[1]));row.appendChild(l);});
  return row;}
function lenRow(c){
  var row=document.createElement("div");row.className="rrow";
  var lab=document.createElement("b");lab.textContent="长度是否影响你的判断";row.appendChild(lab);
  [[1,"是"],[0,"否"],["n","没注意"]].forEach(function(o){
    var l=document.createElement("label");var i=document.createElement("input");
    i.type="radio";i.name="len_"+c;i.value=o[0];l.appendChild(i);
    l.appendChild(document.createTextNode(o[1]));row.appendChild(l);});
  return row;}
var m=document.getElementById("m");
CH.forEach(function(c){
  var sec=document.createElement("section");sec.className="ch";sec.id="c"+c.i;
  var h=document.createElement("h2");h.textContent="第 "+c.i+" 章";sec.appendChild(h);
  var p=document.createElement("div");p.className="txt";p.textContent=c.t;sec.appendChild(p);
  R.forEach(function(r){var n=window["mk_"+r[0]].cloneNode(true);
    n.querySelectorAll("input").forEach(function(i){i.name=r[0]+"_"+c.i;});sec.appendChild(n);});
  sec.appendChild(payRow(c.i));sec.appendChild(lenRow(c.i));
  var w=document.createElement("div");w.innerHTML="<small>一句为什么</small>";
  var t=document.createElement("textarea");t.id="why_"+c.i;w.appendChild(t);sec.appendChild(w);
  m.appendChild(sec);});
function get(n){var e=document.querySelector('[name="'+n+'"]:checked');return e?e.value:"";}
function set(n,v){if(v===""||v==null)return;
  var e=document.querySelector('[name="'+n+'"][value="'+v+'"]');if(e)e.checked=true;}
function rec(c){var o={};R.forEach(function(r){o[r[0]]=get(r[0]+"_"+c);});
  o.pay=get("pay_"+c);o.len=get("len_"+c);
  o.why=(document.getElementById("why_"+c).value||"").trim();return o;}
function done(o){return !!o && o.pay!=="" && R.every(function(r){return o[r[0]]!=="";});}
function refresh(){
  var s={},k=0;
  CH.forEach(function(c){var o=rec(c.i);s[c.i]=o;if(done(o))k++;});
  localStorage.setItem(K,JSON.stringify(s));
  document.getElementById("n").textContent=k;
  document.getElementById("p").value=k;
  document.querySelectorAll(".ch").forEach(function(e){
    e.classList.toggle("done",done(s[e.id.slice(1)]));});
  dump(s);}
function table(s){
  var H=["章","R1","R2","R3","R4","R5","R6","六条全过","愿意付费读","长度影响","理由"];
  var rows=CH.map(function(c){
    var o=s[c.i]||{};
    var vs=R.map(function(r){return o[r[0]]===""?"":V[o[r[0]]];});
    while(vs.length<6)vs.push("");
    var pass=vs.every(function(v){return v==="过";});
    var pay=o.pay===""?"":(o.pay==="1"?"是":"否");
    var len=o.len===""?"":(o.len==="n"?"没注意":(o.len==="1"?"是":"否"));
    return "| "+[c.i].concat(vs).concat([pass?"过":"不过",pay,len,
      (o.why||"").replace(/[|\r\n]/g," ")]).join(" | ")+" |";});
  var doneN=CH.filter(function(c){return done(s[c.i]);}).length;
  var np=CH.filter(function(c){var o=s[c.i]||{};
    return R.every(function(r){return o[r[0]]==="1";});}).length;
  var py=CH.filter(function(c){return (s[c.i]||{}).pay==="1";}).length;
  return ["| "+H.join(" | ")+" |","|"+H.map(function(){return "---";}).join("|")+"|"]
    .concat(rows).concat(["",
      "完成 "+doneN+"/"+N+"｜六条全过 "+np+" 章（"+(N?Math.round(np/N*100):0)+"%）"+
      "｜愿意付费读 "+py+" 章（"+(N?Math.round(py/N*100):0)+"%）",
      "留空 "+(N-doneN)+" 章（计入证据缺失，不算过）｜种子 __SEED__"]).join("\n");}
function dump(s){s=s||JSON.parse(localStorage.getItem(K)||"{}");
  document.getElementById("out").value=table(s);}
function copy(){var t=document.getElementById("out");t.select();
  try{document.execCommand("copy")}catch(e){}}
document.addEventListener("change",refresh);
document.addEventListener("input",refresh);
CH.forEach(function(c){var o=S[c.i]||{};
  R.forEach(function(r){set(r[0]+"_"+c.i,o[r[0]]);});
  set("pay_"+c.i,o.pay);set("len_"+c.i,o.len);
  if(o.why)document.getElementById("why_"+c.i).value=o.why;});
refresh();
</script>
"""


def render_html(items: List[dict], seed: int) -> str:
    """离线打分页：六条 rubric + 愿意付费读 + 长度影响，localStorage 暂存、纯前端导出。

    刻意**不含出处、不含判定状态、不联网**——页面上任何字节都不该让人反推出是哪一臂，
    否则盲评就退化成带答案键的复核（模块 docstring 立的就是这条解耦）。
    """
    import html
    import json

    data = [{"i": x["blind_id"], "t": html.escape((x["text"] or "").strip())} for x in items]
    out = _HTML.replace("__DATA__", _js(data)).replace("__R__", _js(_RUBRIC))
    out = out.replace("__N__", str(len(items))).replace("__SEED__", str(seed))
    return out


def _js(obj) -> str:
    """JSON 塞进 <script> 里：`</` 会提前关掉脚本标签，必须转义。"""
    import json

    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def main(argv: None | List[str] = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m plot_engine.blind_review",
                                 description="把若干采样跑的章打散成一份无出处盲评表")
    ap.add_argument("runs", nargs="+", help="采样目录（含 dump/）")
    ap.add_argument("-o", "--out", default="docs/samples/blind-worksheet.md")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--html", action="store_true", help="同时产出一份离线可打开的打分页（同名 .html）")
    ns = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    items = build([Path(r) for r in ns.runs], ns.seed)
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    key = out.with_name(out.stem + "-key.md")
    out.write_text(render_worksheet(items), encoding="utf-8")
    key.write_text(render_key(items), encoding="utf-8")
    extra = ""
    if ns.html:
        page = out.with_name(out.stem + ".html")
        page.write_text(render_html(items, ns.seed), encoding="utf-8")
        extra = f"｜打分页 → {page}（浏览器直接打开，本地暂存、不联网）"
    print(f"盲评表 → {out}（{len(items)} 章，"
          f"失败类 {sum(1 for x in items if x['status'] != 'OK')} 章）｜答案键 → {key}{extra}"
          f"｜种子 {ns.seed}（换种子=换一份题，读数不可与旧种子并列）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
