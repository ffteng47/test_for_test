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


def build_paired(run_dirs: List[Path], seed: int = 0) -> List[dict]:
    """配对出题：把**同一段剧情的多次渲染**收进同一组，组内比优劣，不跨组比。

    为什么换出题法（E23）：这个语料只有一个局面，绝对分（「愿意付费读」）测的是夹具的单调；
    而同一原章的 N 次渲染内容逐字配平，组内名次是**配对**读数——同样的人时，信息量比 90 份
    绝对分高，且「读起来像重复」从折磨变成了题设。组内变体顺序独立洗牌，所以「变体 A」
    在不同组里不是同一个臂，反推不出谁是谁。
    """
    items = pool(run_dirs)
    failures = sum(1 for x in items if x["status"] != "OK")
    if len(items) < MIN_CHAPTERS:
        raise ValueError(f"只有 {len(items)} 章可评，下限 {MIN_CHAPTERS} 章：给的跑法不够")
    if failures < MIN_FAILURES:
        raise ValueError(f"失败类只有 {failures} 章，下限 {MIN_FAILURES}：这张表全是过线的章，"
                         f"量不出「判死的章是不是真难看」那一格")
    groups: dict = {}
    for x in items:
        groups.setdefault(x["chapter"], []).append(x)
    too_few = [k for k, v in groups.items() if len(v) < 2]
    if too_few:
        raise ValueError(f"第 {too_few} 段剧情只有 1 个渲染，配不成对：这些章出不了配对题")
    rng = random.Random(seed)
    out: List[dict] = []
    for chapter in sorted(groups):
        g = groups[chapter]
        rng.shuffle(g)
        out += [dict(x, group=chapter, variant=chr(ord("A") + j))
                for j, x in enumerate(g)]
    return [dict(x, blind_id=i + 1) for i, x in enumerate(out)]


def render_worksheet(items: List[dict]) -> str:
    paired = "group" in items[0] if items else False
    head = ("# 盲评工作表\n\n"
            + ("读法：同一组是同一段剧情的不同写法，**先把一组读完再排名**（组内 1–N 不重号），"
               "六条 rubric 逐条打，最后补一句为什么。\n"
               "**这里没有出处、没有判定状态**——那是答案键里的事，评分收齐前不要打开它。\n\n"
               if paired else
               "读法：每章只读不查，读完立刻打「愿意付费读」这一列（是/否），再补一句为什么。\n"
               "**这里没有出处、没有判定状态**——那是答案键里的事，评分收齐前不要打开它。\n\n"))
    def title(x):
        return (f"## {x['blind_id']:02d}｜第 {x['group']} 段 · 变体 {x['variant']}\n"
                if paired else f"## {x['blind_id']:02d}\n")
    return head + "\n".join(title(x) + "\n" + x["text"] + "\n" for x in items)


def render_key(items: List[dict]) -> str:
    paired = "group" in items[0] if items else False
    rows = "\n".join(
        (f"| {x['blind_id']:02d} | {x['group']} | {x['variant']} | {x['run']} | {x['chapter']} | {x['status']} |"
         if paired else
         f"| {x['blind_id']:02d} | {x['run']} | {x['chapter']} | {x['status']} |")
        for x in items)
    table = ("| 盲评号 | 组 | 变体 | 跑法 | 原章号 | 判定终态 |\n|---|---|---|---|---|---|"
             if paired else
             "| 盲评号 | 跑法 | 原章号 | 判定终态 |\n|---|---|---|---|")
    return "# 答案键（评分收齐前勿开）\n\n" + table + "\n" + rows + "\n"


_RUBRIC = [("R1", "不复述", "同一批信息没有被近似重写 2–3 遍"),
           ("R2", "立场不漂移", "主角身份/阵营全章一致"),
           ("R3", "名物与数量自洽", "同一物/同一数只有一个指称与一个值"),
           ("R4", "不泄元数据", "没有标记、注释、标题、「本章悬念」一类非叙事文本"),
           ("R5", "段长与体量合规", "2–4 个自然段、成文、没有被截断"),
           ("R6", "单章可读", "不了解 State/契约也能说出谁在查什么、这章新发生了什么")]

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>盲评打分表 · __N__ 章</title>
<style>
:root{--bg:#fbf9f5;--fg:#22221f;--mut:#8a8578;--line:#e4dfd3;--ok:#2f7d4f;--todo:#c9b98a}
*{box-sizing:border-box}
body{margin:0;font:16px/1.95 "Source Han Serif SC","Songti SC","Noto Serif CJK SC",serif;
  background:var(--bg);color:var(--fg)}
#app{display:flex;min-height:100vh}
aside{width:236px;flex:none;border-right:1px solid var(--line);padding:16px 0;
  position:sticky;top:0;height:100vh;overflow:auto;background:#f4f0e6}
aside h1{font:400 13px/1 system-ui;margin:0 16px 6px;color:var(--mut);letter-spacing:.14em}
#prog{font:12px system-ui;color:var(--mut);margin:0 16px 12px}
#toc a{display:flex;align-items:center;gap:8px;padding:8px 16px;font:14px system-ui;
  color:inherit;text-decoration:none;border-left:3px solid transparent}
#toc a:hover{background:#ece5d5}
#toc a.on{border-left-color:var(--fg);background:#ece5d5;font-weight:700}
#toc i{width:8px;height:8px;border-radius:99px;flex:none;background:var(--todo)}
#toc i.ok{background:var(--ok)}
main{flex:1;max-width:880px;padding:30px 48px 120px}
h2{font-size:23px;margin:0 0 2px}
.hint{font:12px/1.8 system-ui;color:var(--mut);margin:0 0 20px}
p{margin:0 0 1.05em;text-indent:2em}
form{margin:26px 0 0;border-top:1px solid var(--line);padding-top:16px;
  font:14px/1.7 system-ui;background:#f1ece0;border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.rrow{display:flex;align-items:baseline;gap:10px;padding:7px 0;border-bottom:1px dotted #ddd6c6}
.rrow:last-of-type{border-bottom:0}
.rrow b{font:600 14px system-ui;min-width:132px}
.rrow small{color:var(--mut);font:12px system-ui;flex:1}
.rrow .opt{display:flex;gap:6px}
.rrow label{font:13px system-ui;border:1px solid var(--line);background:#fff;border-radius:99px;
  padding:3px 12px;cursor:pointer;white-space:nowrap}
.rrow label:has(input:checked){background:var(--fg);color:#fff;border-color:var(--fg)}
textarea{width:100%;box-sizing:border-box;min-height:3em;margin-top:10px;
  font:14px/1.6 system-ui;border:1px solid var(--line);border-radius:6px;padding:8px 10px;background:#fff}
.btn{font:13px system-ui;padding:6px 14px;border:1px solid var(--line);background:#fff;
  border-radius:99px;cursor:pointer;margin:12px 6px 0 0}
#out{width:100%;height:18em;font:12px/1.5 ui-monospace,Consolas,monospace;white-space:pre;
  border:1px solid var(--line);border-radius:6px;padding:10px;background:#fff;margin-top:10px}
details{margin-top:14px;font:13px/1.7 system-ui}
.keys{font:12px system-ui;color:var(--mut);margin:26px 0 0}
@media(max-width:760px){
  aside{position:sticky;width:100%;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:10px 0}
  #toc{display:flex;overflow:auto;padding:0 8px}#toc a{border-left:0;flex:none;padding:6px 9px}
  main{padding:18px 20px 90px}}
</style></head><body><div id="app">
<aside><h1>盲评（无出处）</h1><div id="prog"></div><nav id="toc"></nav></aside>
<main id="body"></main>
</div>
<script>
const CH=__DATA__, R=__R__, K="blind-__MODE__-__SEED__", N=__N__;
let S={}; try{S=JSON.parse(localStorage.getItem(K)||"{}")}catch(e){S={}}
let idx=0;
const V={"1":"过","0":"不过"};
const GRP=!!CH[0].g;
var NG={}; CH.forEach(function(c){if(c.g)NG[c.g]=(NG[c.g]||0)+1;});
function done(o){return !!o && o.pay!=="" && (!GRP||o.rank!=="")
  && R.every(function(r){return o[r[0]]!==""});}
function toc(){
  var k=CH.filter(function(c){return done(S[c.i]);}).length;
  document.getElementById("prog").textContent="已完成 "+k+" / "+N;
  document.getElementById("toc").innerHTML=CH.map(function(c,i){
    return '<a data-i="'+i+'" class="'+(i===idx?"on":"")+'"><i class="'
      +(done(S[c.i])?"ok":"")+'"></i>'+(GRP?("第 "+c.g+" 段 · 变体 "+c.v):("第 "+c.i+" 章"))+'</a>';}).join("");}
function field(name,opts){
  var w=document.createElement("span");w.className="opt";
  opts.forEach(function(o){
    var l=document.createElement("label"),i=document.createElement("input");
    i.type="radio";i.name=name;i.value=o[0];l.appendChild(i);
    l.appendChild(document.createTextNode(o[1]));w.appendChild(l);});
  return w;}
function body(){
  var c=CH[idx], o=S[c.i]||{}, m=document.getElementById("body");
  m.innerHTML="";
  var h=document.createElement("h2");
  h.textContent=GRP?("第 "+c.g+" 段剧情 · 变体 "+c.v+"（本组共 "+NG[c.g]+" 个写法）"):("第 "+c.i+" 章");
  m.appendChild(h);
  var p=document.createElement("div");p.className="hint";
  p.textContent=GRP
    ?"同组是**同一段剧情的不同写法**（内容配平了，读起来像重复是题设不是缺陷）：先把一组读完再给组内名次，名次不许重号。"
    :"读完再判，别回头改；六条全过才算这章过；判不出就留空（留空算证据缺失，不算过）。";
  m.appendChild(p);
  (c.t||"（本轮没有产出正文）").split(/\n\s*\n/).forEach(function(s){
    var q=document.createElement("p");q.textContent=s.trim();m.appendChild(q);});
  var f=document.createElement("form");
  R.forEach(function(r){
    var row=document.createElement("div");row.className="rrow";
    var b=document.createElement("b");b.textContent=r[0]+" "+r[1];
    var sm=document.createElement("small");sm.textContent=r[2];
    row.appendChild(b);row.appendChild(sm);row.appendChild(field(r[0]+"_"+c.i,[[1,"过"],[0,"不过"]]));
    f.appendChild(row);});
  if(GRP){
    var rr=document.createElement("div");rr.className="rrow";
    var rb=document.createElement("b");rb.textContent="组内名次";rr.appendChild(rb);
    var rs=document.createElement("small");rs.textContent="1 = 这组里最好读；只在本组内比较";rr.appendChild(rs);
    var sel=document.createElement("select");sel.id="rank_"+c.i;sel.className="btn";
    var zero=document.createElement("option");zero.value="";zero.textContent="未评";sel.appendChild(zero);
    for(var z=1;z<=NG[c.g];z++){var op=document.createElement("option");
      op.value=z;op.textContent=z;sel.appendChild(op);}
    sel.value=o.rank||"";rr.appendChild(sel);f.appendChild(rr);}
  [["pay","愿意付费读",[[1,"是"],[0,"否"]]],
   ["len","长度影响判断",[[1,"是"],[0,"否"],["n","没注意"]]]].forEach(function(x){
    var row=document.createElement("div");row.className="rrow";
    var b=document.createElement("b");b.textContent=x[1];row.appendChild(b);
    row.appendChild(document.createElement("small"));
    row.appendChild(field(x[0]+"_"+c.i,x[2]));f.appendChild(row);});
  var t=document.createElement("textarea");t.id="why_"+c.i;t.placeholder="一句为什么";
  t.value=o.why||"";f.appendChild(t);
  var be=document.createElement("button");be.type="button";be.className="btn";be.textContent="导出评分";
  var bc=document.createElement("button");bc.type="button";bc.className="btn";bc.textContent="复制到剪贴板";
  be.onclick=fill; bc.onclick=function(){fill();var a=document.getElementById("out");
    a.select();try{document.execCommand("copy")}catch(e){}};
  f.appendChild(be);f.appendChild(bc);
  var d=document.createElement("details");d.innerHTML="<summary>导出预览（粘回仓库落盘；页面不联网，分数只在这台机器上）</summary>";
  var a=document.createElement("textarea");a.id="out";a.readOnly=true;d.appendChild(a);f.appendChild(d);
  m.appendChild(f);
  R.forEach(function(r){if(o[r[0]]!==undefined&&o[r[0]]!=="")
    set(r[0]+"_"+c.i,o[r[0]]);});
  if(o.pay)set("pay_"+c.i,o.pay); if(o.len)set("len_"+c.i,o.len);
  var kp=document.createElement("p");kp.className="keys";
  kp.textContent="快捷键：↑↓ 或 j/k 翻章｜1–6 给 R1–R6 打「过」，按 Shift+1–6 打「不过」｜Ctrl+S 导出";
  m.appendChild(kp);}
function set(n,v){var e=document.querySelector('[name="'+n+'"][value="'+v+'"]');if(e)e.checked=true;}
function rec(){
  var c=CH[idx], o={};
  R.forEach(function(r){var e=document.querySelector('[name="'+r[0]+"_"+c.i+'"]:checked');o[r[0]]=e?e.value:"";});
  var pe=document.querySelector('[name="pay_'+c.i+'"]:checked');o.pay=pe?pe.value:"";
  var le=document.querySelector('[name="len_'+c.i+'"]:checked');o.len=le?le.value:"";
  var rk=document.getElementById("rank_"+c.i);o.rank=rk?rk.value:"";
  o.why=(document.getElementById("why_"+c.i).value||"").trim();
  if(o.pay===""&&o.len===""&&o.why===""&&(!GRP||o.rank==="")
     &&R.every(function(r){return o[r[0]]==="";}))delete S[c.i];
  else S[c.i]=o;
  localStorage.setItem(K,JSON.stringify(S));}
function table(){
  var H=(GRP?["组","变体","名次"]:["章"]).concat(
    ["R1","R2","R3","R4","R5","R6","六条全过","愿意付费读","长度影响","理由"]);
  var rows=CH.map(function(c){
    var o=S[c.i]||{};
    var vs=R.map(function(r){return o[r[0]]?V[o[r[0]]]:"";});
    var all=vs.length===6&&vs.every(function(v){return v==="过";});
    return "| "+(GRP?[c.g,c.v,o.rank||""]:[c.i]).concat(vs).concat([all?"过":"不过",
      o.pay?((o.pay==="1")?"是":"否"):"",
      o.len?((o.len==="n")?"没注意":((o.len==="1")?"是":"否")):"",
      (o.why||"").replace(/[|\r\n]/g," ")]).join(" | ")+" |";});
  var dn=CH.filter(function(c){return done(S[c.i]);}).length;
  var np=CH.filter(function(c){var o=S[c.i]||{};
    return R.every(function(r){return o[r[0]]==="1";});}).length;
  var py=CH.filter(function(c){return (S[c.i]||{}).pay==="1";}).length;
  var tail=["","完成 "+dn+"/"+N+"｜六条全过 "+np+" 章（"+(N?Math.round(np/N*100):0)+"%）"+
            "｜愿意付费读 "+py+" 章（"+(N?Math.round(py/N*100):0)+"%）",
            "留空 "+(N-dn)+" 章（证据缺失，不算过）｜种子 __SEED__"];
  if(GRP){
    var bad=[];
    Object.keys(NG).forEach(function(g){
      var rs=CH.filter(function(c){return c.g==g;}).map(function(c){return (S[c.i]||{}).rank||"";});
      var got=rs.filter(function(v){return v!=="";});
      var dup=got.filter(function(v,i){return got.indexOf(v)!==i;});
      var miss=NG[g]-got.length;
      if(miss||dup.length)bad.push("第 "+g+" 段：缺 "+miss+" 个名次"+
        (dup.length?"、重号 "+Array.from(new Set(dup)).join("/"):""));});
    tail.push(bad.length?("组内名次未收齐 ⇒ 该组的配对读数不能算：" + bad.join("；"))
                       :"各组名次全部收齐、无重号 ⇒ 配对读数可用");}
  return ["| "+H.join(" | ")+" |","|"+H.map(function(){return "---";}).join("|")+"|"].concat(rows)
    .concat(tail).join("\n");}
function fill(){var a=document.getElementById("out");if(a)a.value=table();}
function go(i){rec();idx=Math.max(0,Math.min(N-1,i));toc();body();window.scrollTo(0,0);}
document.addEventListener("click",function(e){
  var a=e.target.closest("#toc a");if(a){go(+a.dataset.i);e.preventDefault();}});
document.addEventListener("change",function(e){
  if(e.target.closest("form")){rec();toc();}});
document.addEventListener("input",function(e){
  if(e.target.tagName==="TEXTAREA"&&e.target.id!=="out")rec();});
document.addEventListener("keydown",function(e){
  var typing=e.target.tagName==="TEXTAREA";
  if(!typing&&(e.key==="ArrowDown"||e.key==="j")){go(idx+1);e.preventDefault();}
  if(!typing&&(e.key==="ArrowUp"||e.key==="k")){go(idx-1);e.preventDefault();}
  if(e.ctrlKey&&e.key.toLowerCase()==="s"){fill();e.preventDefault();return;}
  if(!typing&&e.key>="1"&&e.key<="6"){set(R[+e.key-1][0]+"_"+CH[idx].i,e.shiftKey?"0":"1");rec();toc();}
  });
toc();body();
</script></body></html>
"""


def render_html(items: List[dict], seed: int) -> str:
    """逐章翻阅的打分页：复用 `viewer.py` 的左章节右正文壳，判定收在正文下方。

    刻意**不含出处、不含判定状态、不联网**——页面上任何字节都不该让人反推出是哪一臂，
    否则盲评退化成带答案键的复核（模块 docstring 立的就是这条解耦）。90 章排成一张长墙
    等于没出题：评分人翻不动就会开始跳章，跳章的表不能再当普查读。
    """
    paired = "group" in items[0] if items else False
    data = [{"i": x["blind_id"], "t": (x["text"] or "").strip(),
             "g": x.get("group"), "v": x.get("variant")} for x in items]
    out = _HTML.replace("__DATA__", _js(data)).replace("__R__", _js(_RUBRIC))
    out = out.replace("__N__", str(len(items))).replace("__SEED__", str(seed))
    return out.replace("__MODE__", "paired" if paired else "census")


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
    ap.add_argument("--paired", action="store_true",
                    help="配对出题：同一段剧情的多次渲染收进一组、组内排名次（语料只有一个局面时用，E23）")
    ns = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    build_fn = build_paired if ns.paired else build
    items = build_fn([Path(r) for r in ns.runs], ns.seed)
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
