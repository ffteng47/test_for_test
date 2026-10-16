# -*- coding: utf-8 -*-
"""取证裁决（重放机检，§11 落盘脚本）：event.db 重放 pre-state → dump 头部重建终轮契约 +
`## Proposals` 重建提案 → 复跑 Validator._review，按 applied 事件的 类型/actor/rank 定死
每一类失败；复现 rule 集与 dump 不符的章才回流。判决口径（Δ 面，章次级）：
① 正文没写钉；② 戏在正文、抽取没给/型漂移；③ 抽到了但判钉不认（actor 翻转 / 族内弱
动词撞 rank 上限——H5.3 实现表与 H2.2 rank 互斥面）；④ 泄漏族（H5.7，另按终稿有无文本
依据分 Writer 真漏 / 抽取误报）；伴生=H5.6；漏驱动=H5.4（被禁知识动了账）。
运行：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/_forensics/adjudicate.py
"""
import sys, sqlite3, json, ast, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plot_engine.review import _load_fx
from plot_engine.replay import apply_events
from plot_engine.reducer import Reducer
from plot_engine.models.event import Event
from plot_engine.models.proposal import EventProposal
from plot_engine.validator import Validator, _referenced_fact

FX = {"full": _load_fx("experiment_10ch"), "half": _load_fx("experiment_10ch_half")}
PENDING = {
    ("ep1v38-r1", "full"): [2, 4, 5, 6, 7, 9, 10],
    ("ep1v38-r2", "full"): [1, 2, 4, 5, 6, 7, 9, 10],
    ("ep1v38-r3", "full"): [2, 4, 5, 6, 7, 9, 10],
    ("ep1v38-l1", "full"): [2, 3, 4, 6, 7, 9, 10],
    ("attr_m32b_r1", "full"): [1, 2, 4, 6, 7, 9, 10],
    ("attr_half_r1", "half"): [2, 3, 4, 7, 8, 9, 10],
}
KCAP = {"OBSERVES": 3, "READS": 3, "IS_TOLD": 2, "INFERS": 1}
KRANK = {"unknown": 0, "suspected": 1, "believed": 2, "known": 3, "confirmed": 4}
IMPL = {"knowledge": {"OBSERVES", "READS", "IS_TOLD", "INFERS"},
        "belief": {"BELIEVES", "SUSPECTS", "DOUBTS"}}
FACT_KW = {
    "fact_000001": ["叛徒"], "fact_000002": ["叛徒"], "fact_000003": ["伪造", "赝品", "假印", "仿"],
    "fact_000004": ["碰过印泥", "摸过印泥", "动过印泥"], "fact_000005": ["三页", "缺页"],
    "fact_000006": ["值守", "守夜", "值夜", "轮值"], "fact_000007": ["笔迹", "密信"],
    "fact_000008": ["两把", "两枚钥匙"], "fact_000009": ["会饮", "外客", "酒"],
    "fact_000010": ["印泥", "商号"], "fact_000011": ["刻刀"], "fact_000012": ["欠", "债"],
}
ACT_KW = {
    "READS": ["读", "翻阅", "翻看", "翻开", "记载", "写着", "簿记"],
    "OBSERVES": ["看", "瞥", "注意", "见", "发现", "盯"],
    "IS_TOLD": ["告诉", "告知", "回答", "说道", "开口", "报告", "听说"],
    "INFERS": ["意味着", "推断", "断定", "意识到", "串", "证明"],
    "BELIEVES": ["相信", "确信", "认定", "笃定"], "SUSPECTS": ["怀疑", "嫌疑", "起疑", "可疑"],
    "DOUBTS": ["不信", "存疑", "质疑", "未必"],
}
NAME = {"char_000001": "张三", "char_000002": "李四", "char_000003": "王五", "char_000004": "赵六"}
ORDER = {"⚠": 0, "③": 1, "②": 2, "①?": 3, "?": 4, "other": 5, "伴生": 6, "④": 7, "漏驱动": 7}


def sections(raw):
    out, cur = {}, None
    for line in raw.splitlines():
        m = re.match(r"^## (.+?)\s*$", line)
        if m:
            cur = m.group(1); out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def props_of(sec_text, ch):
    out = []
    for i, line in enumerate(sec_text.splitlines()):
        m = re.match(r"^- (\w+) actor=(\S+) target=(\S+) payload=(\{.*\})", line.strip())
        if not m:
            continue
        t, a, tg, pj = m.groups()
        payload = ast.literal_eval(pj.replace("None", "'None'"))
        out.append(EventProposal(proposed_event_type=t, actor=a,
                                 target=None if tg == "None" else tg, chapter=ch, seq=i,
                                 payload=payload, confidence=700, source_ref=f"para:{i + 4}",
                                 extraction_method="llm", extraction_confidence=700))
    return out


def scene(draft, fact, etypes):
    verbs = [v for et in ([etypes] if isinstance(etypes, str) else etypes) for v in ACT_KW.get(et, [])]
    for s in re.split(r"[。！？\n]", draft):
        s = s.strip()
        if s and any(k in s for k in FACT_KW.get(fact, [])) and any(k in s for k in verbs):
            return s[:48]
    return ""


def judge(d, fx_key, ch):
    fx = FX[fx_key]
    arc = fx.build_arc(10)
    cfg = fx.make_config(10)
    con = sqlite3.connect(str(ROOT / "sampling" / d / "state" / "event.db"))
    rows = con.execute("select payload_json from events where chapter<? order by chapter,seq", (ch,)).fetchall()
    evs = [Event(**json.loads(r[0])) for r in rows]
    pre = apply_events(cfg.initial_state, evs, Reducer())
    raw = (ROOT / "sampling" / d / f"ch{ch:02d}.md").read_text(encoding="utf-8")
    head = raw.splitlines()[3]
    cv = int(re.search(r"contract_version=(\d+)", head).group(1))
    types = ast.literal_eval(re.search(r"required_events=\[.*\]", head).group(0)[len("required_events="):])
    derived = fx.contract_for(arc, ch, pre)
    kept = [e for e in derived.required_events if e.event_type in types]
    contract = derived.model_copy(update={"version": cv, "required_events": kept})
    sec = sections(raw)
    props = props_of(sec.get("Proposals", ""), ch)
    res, sim = Validator()._review(sec.get("Draft", "").strip(), props, contract, pre)
    dump_rules = sorted(re.findall(r"(H\d+\.\d+)", sec.get("Findings", "")))
    repro_rules = sorted({f.rule_id for f in res.hard_violations})
    applied = sim.applied if sim else []
    failed = sim.failed if sim else []

    def why(act, fld, tgt, expected):
        ref = lambda ev: _referenced_fact(ev)
        ap_ah = [e for e in applied if ref(e) == tgt and e.actor == act]
        if fld == "belief":
            good = [e for e in ap_ah if e.event_type in IMPL["belief"]]
            if good:
                return "⚠", f"{NAME[act]} belief{tgt[-2:]}已实现仍FAIL"
            pr_ah = [p for p in props if p.actor == act and (p.payload.get("fact_id") or p.payload.get("conclusion_fact_id")) == tgt]
            if pr_ah:
                return "②", f"{NAME[act]} belief{tgt[-2:]}提案类型{pr_ah[0].proposed_event_type}∉belief表"
            pf = [p for p in props if (p.payload.get("fact_id") or p.payload.get("conclusion_fact_id")) == tgt]
            if pf:
                return "③", f"{NAME[act]} belief{tgt[-2:]}actor翻转→{pf[0].actor[-2:]}"
            # 信念筛查须同查 SUSPECTS 与 BELIEVES 动词（只查怀疑漏掉「笃定/相信」句，
            # l1ch2/r1ch5 曾因此被误留 ①?）。
            ev = scene(sec.get("Draft", ""), tgt, ("SUSPECTS", "BELIEVES"))
            return ("②", f"正文有戏无提案:{ev}") if ev else ("①?", f"{NAME[act]} belief{tgt[-2:]}正文未见锚")
        exp = KRANK.get(str(expected), 3)
        good = [e for e in ap_ah if e.event_type in IMPL["knowledge"]]
        if good:
            mx = max(KCAP.get(e.event_type, 0) for e in good)
            if mx >= exp:
                return "⚠", f"{NAME[act]} kno{tgt[-2:]}已达成仍FAIL"
            t0 = max(good, key=lambda e: KCAP.get(e.event_type, 0)).event_type
            return "③", f"{NAME[act]} kno{tgt[-2:]}族内弱动词{t0}(cap{mx})<期望{expected}"
        pr_ah = [p for p in props if p.actor == act and (p.payload.get("fact_id") or p.payload.get("conclusion_fact_id")) == tgt]
        if pr_ah:
            strong = [p for p in pr_ah if p.proposed_event_type in IMPL[fld if fld in IMPL else "knowledge"]]
            if not strong:
                return "②", f"{NAME[act]} {fld[:3]}{tgt[-2:]}actor对提案类型{pr_ah[0].proposed_event_type}∉实现表"
            f0 = failed[0][1] if failed else "未入账且无failed记录"
            return "⚠", f"{NAME[act]} kno{tgt[-2:]}提案全对未入账({f0})"
        pf = [p for p in props if (p.payload.get("fact_id") or p.payload.get("conclusion_fact_id")) == tgt]
        if pf:
            p0 = pf[0]
            return "③", f"{NAME[act]} kno{tgt[-2:]}actor翻转(提案在{p0.actor[-2:]}名下{p0.proposed_event_type})"
        ev = scene(sec.get("Draft", ""), tgt, "OBSERVES")
        return ("②", f"正文有戏无提案:{ev}") if ev else ("①?", f"{NAME[act]} kno{tgt[-2:]}正文未见锚")

    def why_nail(ntype):
        if any(e.event_type == ntype for e in applied):
            return "⚠", f"H5.1 {ntype}已入账仍报缺"
        pr = [p for p in props if p.proposed_event_type == ntype]
        if pr:
            return "⚠", f"H5.1 {ntype}提案在但未入账({failed[0][1] if failed else '?'})"
        fact = None
        for e in derived.required_events:
            if e.event_type == ntype and fact is None:
                fact = next((f for f in FACT_KW if f in (e.description or "")), None)
        if fact:
            d1 = [p for p in props if (p.payload.get("fact_id") or p.payload.get("conclusion_fact_id")) == fact]
            if d1:
                return "②", f"钉{ntype}:{fact[-2:]}型漂移→{d1[0].proposed_event_type}"
            ev = scene(sec.get("Draft", ""), fact, ntype)
            return ("②", f"钉{ntype}:{fact[-2:]}正文有戏:{ev}") if ev else ("①?", f"钉{ntype}:{fact[-2:]}正文未见锚")
        return "①?", f"钉{ntype}无fact无法定位"

    items = []
    seen = set()
    for f in res.hard_violations:
        key = (f.rule_id, f.message[:40])
        if key in seen:
            continue
        seen.add(key)
        if f.rule_id == "H2.2":
            m = re.search(r"(\w+) 未取得知识 (fact_\d+)（期望 (\S+?)）", f.message)
            if m:
                items.append(why(m.group(1), "knowledge", m.group(2), m.group(3)) + ("H2.2",))
            else:
                items.append(("other", "H2.2消息未解析:" + f.message[:40], "H2.2"))
        elif f.rule_id == "H5.3":
            m = re.search(r"must_change (\w+)\.(\w+)", f.message)
            act, fld = m.groups()
            subs = [why(act, fld, c_.target, c_.expected_value)
                    for c_ in contract.must_change
                    if c_.character_id == act and c_.field == fld]
            fails = [s for s in subs if s[0] != "⚠"]
            pick = min(fails or subs, key=lambda s: ORDER[s[0]])
            items.append(pick + ("H5.3",))
        elif f.rule_id == "H5.1":
            m = re.search(r"必需事件 (\w+)", f.message)
            items.append(why_nail(m.group(1)) + ("H5.1",))
        elif f.rule_id == "H5.7":
            items.append(("④", "禁止知识泄漏", "H5.7"))
        elif f.rule_id == "H5.6":
            items.append(("伴生", "H5.6", "H5.6"))
        elif f.rule_id == "H5.4":
            items.append(("漏驱动", "H5.4=被禁知识动了账", "H5.4"))
        else:
            items.append(("other", f.rule_id + ":" + f.message[:36], f.rule_id))
    return items, dump_rules, repro_rules


LEAKY = {"④", "漏驱动"}
tally, manual = {}, []
for (d, fx_key), chs in sorted(PENDING.items()):
    for ch in chs:
        items, dr, rr = judge(d, fx_key, ch)
        core = [i for i in items if i[0] != "伴生"]
        if not core:
            verdict = "?" if not dr else "other"
        elif all(i[0] in LEAKY for i in core):
            verdict = "④"
        else:
            core = [i for i in core if i[0] not in LEAKY] or core
            verdict = min((i[0] for i in core), key=lambda v: ORDER[v])
        tally[verdict] = tally.get(verdict, 0) + 1
        flag = "" if set(dr) == set(rr) else f" [复现差 dump={dr} repro={rr}]"
        if verdict in ("①?", "⚠") or flag:
            manual.append((d, ch, verdict, flag))
        print(f"{d:13s}{ch:>3d}  {verdict:4s}{flag} {' ; '.join(i[2]+':'+i[1] for i in items)[:150]}")
print("\n合计:", dict(sorted(tally.items(), key=lambda kv: ORDER[kv[0]])))
print("需回流/人工:", manual)
