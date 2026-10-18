# 一次性页面生成器（W2 真人复核查：把争议候选+判定+原文证据高亮合成单文件 HTML，零生产接触）。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/make_judge_review.py
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from plot_engine.metrics import _section_body                    # noqa: E402
from plot_engine.l3.scene_index import strip_comments            # noqa: E402

V = json.loads((HERE / "l3-judge-v10.verdicts.json").read_text(encoding="utf-8"))

# 人核结论（2026-10-18，口径沿 pack §7.9+勘误，逐条回原文读证据行）：键=(章, refs 元组)
AUDIT = {
    (2, ("4-4", "22-22")): ("误报", "行4 是问句「你这里不是只有一把钥匙吗」，行22 长老纠正为两把=问答结构，非作者矛盾"),
    (9, ("4-4", "13-13")): ("真", "第二把钥匙保管人「赵六独自掌握」(行4) vs「李四保管」(行13)，记忆/叙述层互斥无解释"),
    (9, ("13-13", "14-14")): ("同源枚举", "行14 是行13 推测的自延伸，不另立矛盾源"),
    (9, ("14-14", "19-19")): ("同源枚举", "同上，矛盾源=行4↔行13"),
    (9, ("4-4", "14-14")): ("同源枚举", "同上"),
    (13, ("3-3", "17-17")): ("真", "保管口径三方互斥（赵六+长老 / 守夜人+保管人+长老 / 宗主+赵六+守阁人）——同一矛盾源枚举膨胀注"),
    (13, ("3-3", "8-8")): ("真", "同上（矛盾源=行3/8/17 三方口径，条目三条）"),
    (13, ("8-8", "17-17")): ("真", "同上"),
    (13, ("3-3", "4-4")): ("待定", "行4 变体口径是否同族互斥，请连读原文裁"),
    (13, ("4-4", "11-11")): ("待定", "同族变体，未单独定罪"),
    (13, ("4-4", "17-17")): ("待定", "同族变体，未单独定罪"),
    (13, ("4-4", "8-8")): ("待定", "同族变体，未单独定罪"),
    (17, ("12-12", "13-13")): ("误报", "行12「墙上几把钥匙」=房内杂钥所指域，与行13「（藏宝阁）这里钥匙只有两把」不同域，可同真"),
    (20, ("5-5", "29-29")): ("误报", "行29「还有另一把钥匙的事呢」被抽成「1把」=宿主抽取工件；两处可同真（一把在赵六+另一把）"),
    (23, ("1-1", "28-28")): ("误报", "行28「李四大晚上出去会外客」≠值守在场人数主张，配对指域漂移（机判对，理由含糊）"),
    (23, ("3-3", "24-24")): ("真", "翻案：赵六发誓「钥匙只有一把」+行4 叙述层背书 vs 行24「钥匙有两把，李四和赵六各持一把」=同静态事实互斥（台账 ch23-C 真域，判分器以「悬念设计」顶回）"),
    (23, ("4-4", "24-24")): ("真", "同上矛盾源的第二配对（枚举膨胀注）"),
    (25, ("31-31", "32-32")): ("误报", "行31「一共两把，另一把在哪里」与行32「另一把在宗主那里」相容可同真；「1把」=抽取工件"),
    (30, ("17-17", "29-29")): ("误报", "行17 两把口径+行29「失踪了一把」=情节演进非口径矛盾（失踪≠总数说法互斥）"),
    (32, ("2-2", "10-10")): ("真", "行2 王五记忆「钥匙只有一把」vs 行10 王五本人台词「只有两把」+行13 叙述「有两把」=同一矛盾源（条目两条，枚举注）"),
    (32, ("2-2", "13-13")): ("真", "同上矛盾源"),
    (32, ("8-8", "10-10")): ("待定", "行8 变体口径是否同族，连读裁"),
    (32, ("8-8", "13-13")): ("待定", "同族变体，未单独定罪"),
    (36, ("12-12", "15-15")): ("误报", "行12 张三怀中备用钥匙与行15「一把李四一把张三」相容（备用=张三那把），可同真"),
    (36, ("2-2", "12-12")): ("真", "行2 赵六视角「两把：掌门+他本人」vs 行12 张三怀中取出藏宝阁备用钥匙=保管归属互斥无解释（ch50 锚③同型）"),
    (46, ("1-9", "14-22")): ("误报", "refs 内行19「赵六急匆匆地走进藏宝阁」=到达叙述，B 主张不成立——判分器与宿主到达消解双层同漏（判分器判真是错判）"),
    (50, ("25-29",)): ("真", "锚①：李四山下在场无到达（§1.1 锚定义在册；机判「对话提及」豁免顶回=翻案）"),
    (50, ("1-20", "22-24")): ("真", "锚②：赵六离开后原地互动（机判「视角转换」豁免顶回=翻案）"),
    (50, ("3-3", "23-23")): ("真", "锚③：钥匙保管口径，「有人改了规则」叙事自觉在册仍按锚定义判真（机判「不同理解可同真」顶回=翻案）"),
    (12, ("6-6", "21-21")): ("误报", "行6 是张三的「应该谨慎保管」期望句非陈述，与行21 守阁人口径可同真（机判结论对）；注：台账 ch12-C 备用钥匙真域未被本候选集指认=宿主配对覆盖缺口"),
    (12, ("11-11", "17-17")): ("误报", "洪峰样例：询问/交谈台词被抽成在场人数陈述=批1-2 抽取层时态语用混淆（机判否决正确）"),
}
CH50_NIGHT = "误报", "宿主配对硬伤实证：行10/12「赵六，昨晚你值守…」是事后询问台词，被抽成在场人数陈述——机判误报是对的（理由含糊但结论对）"

CHS = sorted({v["chapter"] for v in V} & {2, 8, 9, 12, 13, 17, 20, 23, 25, 30, 32, 36, 46, 50})


def predicate(c):
    return c["detail"].split(":")[0].strip() if c["family"] == "C" else ""


def in_page(v):
    key = (v["chapter"], tuple(v["refs"]))
    if key in AUDIT:
        return True
    if v["verdict"] == "真":
        return True
    if v["chapter"] == 50 and predicate(v) == "night_watch":
        return True
    if v["chapter"] == 8 and v["family"] == "A":
        return True
    return False


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
.card.t{border-left-color:var(--red)}.card.f{border-left-color:#c9c2b2}.card.p{border-left-color:var(--blue)}.card.r{border-left-color:var(--org)}
.card b{display:inline-block;min-width:64px}.card .q{color:var(--mut)}
.tag{font:11px system-ui;padding:1px 8px;border-radius:99px;color:#fff;margin-right:6px}
.tag.t{background:var(--red)}.tag.f{background:#8a8578}.tag.p{background:var(--blue)}.tag.r{background:var(--org)}
pre.body{font:14px/2 inherit;white-space:pre-wrap;background:#fff;border:1px solid var(--line);border-radius:6px;padding:18px 20px}
mark{padding:0 2px;border-radius:3px}
mark.t{background:#f7d5cf}mark.r{background:#f5e3c3}mark.p{background:#d5e2f7}mark.f{background:#eae6db}
.ln{color:#c6bfae;font:11px monospace;margin-right:8px}
"""

cards_by_ch, marks_by_ch = {}, {}
for v in V:
    if not in_page(v):
        continue
    key = (v["chapter"], tuple(v["refs"]))
    if v["chapter"] == 50 and predicate(v) == "night_watch":
        hu, note = CH50_NIGHT
    else:
        hu, note = AUDIT.get(key, ("待定", "未单独人核，请连读原文裁"))
    cls = {"真": "t", "误报": "f", "待定": "p", "同源枚举": "r"}.get(hu, "p")
    if hu == "真" and v["verdict"] == "误报":
        cls = "r"                                   # 翻案
    cards_by_ch.setdefault(v["chapter"], []).append(
        f'<div class="card {cls}"><span class="tag {cls}">{v["verdict"]}</span>'
        f'<span class="tag t">人核:{hu}</span><b>{v["family"]}|{v["refs"][0]}</b> {v["detail"]}'
        f'<div class="q">机判理由：{v["reason"][:110]}</div>'
        f'<div>人核注：{note}</div></div>')
    for r in v["refs"]:
        a, b = (int(x) for x in r.split("-"))
        for i in range(a, b + 1):
            cur = marks_by_ch.setdefault(v["chapter"], {})
            if cls == "t" or i not in cur:
                cur[i] = cls                          # 同色冲突取最重

parts, toc = [], []
for ch in CHS:
    if ch not in cards_by_ch:
        continue
    body = strip_comments(_section_body(
        (HERE / "wpe50ch" / f"ch{ch:02d}.md").read_text(encoding="utf-8", errors="replace").splitlines(),
        "Draft"))[0]
    mk = marks_by_ch.get(ch, {})
    html = "".join(
        f'<mark class="{mk[i]}"><span class="ln">{i:03d}</span>{ln}</mark>\n' if i in mk
        else f'<span class="ln">{i:03d}</span>{ln}\n' for i, ln in enumerate(body, 1))
    n_t = sum(1 for c in cards_by_ch[ch] if "人核:真" in c)
    parts.append(f'<h2 id="ch{ch}">ch{ch:02d}（人核真 {n_t} / 争议 {len(cards_by_ch[ch])}）</h2>'
                 + "\n".join(cards_by_ch[ch]) + f"<pre class=body>{html}</pre>")
    toc.append(f'<a href="#ch{ch}"><i></i>ch{ch:02d}<s>{len(cards_by_ch[ch])} 条</s></a>')

Path(HERE.parent / "docs" / "samples" / "l3-judge-review.html").write_text(
    f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>L3 判分争议页 · 批3 W2（l3-judge-v1.0）</title>
<style>{STYLE}</style></head><body><div id="app">
<aside><h1>争议条目导航</h1>
<p>机判=32b@temp0 判分器（只判不找）；人核=本会话按 §7.9 口径回读证据行结论；<b>请 tff 真人裁</b>。
红=人核真 橙=翻案(机判误报但锚/台账真 或同源枚举) 蓝=待裁 灰=人核误报。原文行号=strip_comments 基准。</p>
<nav id="toc">{''.join(toc)}</nav></aside>
<main><h2 style="margin-top:0">L3 批3 W2 判分争议 · 真人复核页</h2>
<p class=legend>数据源 sampling/l3-judge-v10.verdicts.json（290 条全量）+ sampling/wpe50ch 归档正文。
判定口径 pack §7.9+勘误；ch50 锚定义 §1.1（本页未改锚定义，仅呈堂）。</p>
{''.join(parts)}</main></div></body></html>""", encoding="utf-8")
print("written docs/samples/l3-judge-review.html，入页章：", CHS)
