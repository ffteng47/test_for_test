"""离线基线实测：把用户交付的 `ai_flavor_lint` 在本项目 canon 语料上跑一遍，出三张表。

纪律：
  - **观测面，不是判据**。不跑任何 LLM 采样、不改任何规则本体/阈值、不进 E1–E6/G1–G4、
    不引入退出码门控（交付说明 §「与原作的唯一差异」已把 --fail-on 移除，本脚本也不加）。
  - 正文唯一口径 = `plot_engine.reading.read_run`（E12/E19 的教训：自家解析器取段范围写窄
    会少算，这里一个字都不自己抠 markdown）。
  - 规则调用 = `plot_engine.ai_flavor_lint.scan_document`（import 调用，240 章不起 240 个进程），
    豁免机制按 `scan_file` 的语义走 `load_style_whitelist` + `mask_style_text`（本仓库当前没有
    任何 `.deslop-whitelist`，所以这一步实测是恒等变换，脚本仍按原语义调用）。
  - 唯一的例外：`required_events` 不在 read_run 的返回里，按 E15 的纪律**逐跑读 dump 的第 4 行**
    （`contract_version=… required_events=[…]`），只取这一个字段，不碰正文。

输出（stdout，markdown）：
  表 0  语料与家族底数（含被排除的跑）
  表 1  每条规则的命中分布（原始章次 + 每千字命中率，按家族）
  表 2  与判定面（bucket）的重叠四格 + 判死/首轮差值
  表 3  与 R1–R6 的映射与重合度量
  附表  被点名三条 B 类（解释链/比喻密度/公文腔）的专项复核
用法：
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m plot_engine.ai_flavor_baseline [--json-out PATH]
"""
from __future__ import annotations

import ast
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from plot_engine.reading import paragraphs, read_run
from plot_engine import ai_flavor_lint as lint

ROOT = Path(__file__).resolve().parent.parent
SAMPLING = ROOT / "sampling"

# --- 家族口径：模型/端点/夹具/尺，凭据在各基线文档与 run.log 首行 ---
# key -> label；成员见 RUN_FAMILY。家族标签不是从正文推的，是从 run.log + 基线文档推的。
FAMILY_LABEL = {
    "q25_11500_v2": "qwen2.5:14b @11500｜夹具 ladder-v2-f1-belief-arc｜v3.2 尺",
    "q25_11500_v1": "qwen2.5:14b @11500｜夹具 ladder-v1｜v3.2 尺",
    "q3_14b_11500": "qwen3:14b @11500｜夹具 ladder-v1｜v3.2 尺",
    "q3_8b_11500": "qwen3:8b @11500｜夹具 ladder-v1｜v3.2 尺",
    "q35_27b_11500": "qwen3.5:27b @11500｜夹具 ladder-v1｜v3.2 尺",
    "q3_30b_a4000": "qwen3:30b(a4000) @11500｜夹具 ladder-v1｜v3.2 尺",
    "r1_32b_11500_t8": "deepseek-r1:32b @11500（T8）｜夹具 ladder-v1｜旧尺",
    "q25_1434_t9": "qwen2.5:14b @11434（T9）｜夹具 ladder-v1｜旧尺",
    "q25_1434_v32": "qwen2.5:14b @11434（v3.2）｜夹具 ladder-v1｜v3.2 尺",
    "EXCLUDED": "bo_q3_30b｜十个 dump 正文全空（writer 预算吃光，E2 0%）⇒ 排除",
}
RUN_FAMILY = {
    "ladder2_r1": "q25_11500_v2", "ladder2_r2": "q25_11500_v2", "ladder2_r3": "q25_11500_v2",
    "q25_11500_r1": "q25_11500_v1", "q25_11500_r2": "q25_11500_v1", "q25_11500_r3": "q25_11500_v1",
    "bo_ctrl": "q25_11500_v1",
    "q3_14b_r1": "q3_14b_11500", "q3_14b_r2": "q3_14b_11500", "q3_14b_r3": "q3_14b_11500",
    "bo_q3_14b": "q3_14b_11500",
    "bo_q3_8b": "q3_8b_11500",
    "bo_q35_27b": "q35_27b_11500",
    "bo_q3_30b_a4000": "q3_30b_a4000",
    "t8r1": "r1_32b_11500_t8", "t8r2": "r1_32b_11500_t8", "t8r3": "r1_32b_11500_t8",
    "t9r1": "q25_1434_t9", "t9r2": "q25_1434_t9", "t9r3": "q25_1434_t9",
    "v32r1": "q25_1434_v32", "v32r2": "q25_1434_v32", "v32r3": "q25_1434_v32",
    "bo_q3_30b": "EXCLUDED",
}
FAMILY_ORDER = ["q25_11500_v2", "q25_11500_v1", "q3_14b_11500", "q3_8b_11500",
                "q35_27b_11500", "q3_30b_a4000", "r1_32b_11500_t8",
                "q25_1434_t9", "q25_1434_v32"]

BUCKET_CN = {"first_pass": "首", "rewrite_rescued": "救",
             "renegotiate_only": "继", "disposition": "处"}
PASS_BUCKETS = {"first_pass", "rewrite_rescued"}
DEAD_STATUS = "ARC_CONFLICT"

# 规则 → R1–R6 的映射是**分析判断**（写在表 3），本脚本只负责把可数的部分量出来。
# 密度型规则（换算成每千字才能跨家族比）：
DENSITY_RULES = {
    "micro-action-tic", "negation-pair-tic", "cliche-density-tic", "stock-reaction-tic",
    "action-list-tic", "abstract-summary-tic", "metaphor-density-tic", "reasoning-chain-tic",
    "system-notice-formality-tic", "overcompressed-prose-tic", "low-connective-density-tic",
    "quote-emphasis-tic", "formulaic-parallelism",
}
# 计数型规则：条数本身随章长线性增长（不是「密度门」，是「逐处命中」）
COUNT_RULES = {
    "not-is-comparison", "reverse-not-is", "voice-contrast", "negation-parade",
    "trailer-ending", "trailer-summary", "em-dash", "long-paragraph", "period-stutter",
}

_NOTICE_LINE = re.compile(r"^【[^】]+】$")
_STRUCT_LINE = re.compile(r"^\s*(#{1,6}\s|>\s?|[-*+]\s|\d+[.)]\s|\|)")


def required_events(dump_file: Path) -> List[str]:
    """只读 dump 第 4 行的 required_events（E15 纪律：逐跑读行首，不从终态反推）。"""
    for line in dump_file.read_text(encoding="utf-8").splitlines()[:6]:
        m = re.search(r"required_events=(\[.*\])", line)
        if m:
            return list(ast.literal_eval(m.group(1)))
    return []


def spearman(xs: List[float], ys: List[float]) -> float:
    """秩相关（自己实现，不引依赖）。用于「这条规则是不是只在读章长」。"""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else float("nan")


def stutter_max_run(text: str) -> int:
    """按交付物自己的碎句口径（只数引号外叙述句、可见字数 ≤ STUTTER_MAX_SENTENCE）
    量全库最长连续碎句串，用来解释「period-stutter 为什么全库 0 命中」。阈值不改。"""
    best = run = 0
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if lint.is_divider(trimmed) or lint.is_structural(trimmed):
            run = 0
            continue
        narrative = lint.strip_quoted(trimmed)
        if lint.visible_length(narrative) == 0:
            run = 0
            continue
        for sentence in lint.split_sentences(narrative):
            if lint.visible_length(sentence) <= lint.STUTTER_MAX_SENTENCE:
                run += 1
                best = max(best, run)
            else:
                run = 0
    return best


def collect() -> tuple[List[dict], Dict[int, List[str]]]:
    """一章一条记录：canon 正文 + 判定面字段 + 该章所有 finding。
    正文只在内存里过一遍（read_run 一次），行缓存另发给专项复核用。"""
    rows: List[dict] = []
    line_map: Dict[int, List[str]] = {}
    for run_dir in sorted(p for p in SAMPLING.iterdir() if (p / "dump").is_dir()):
        family = RUN_FAMILY.get(run_dir.name)
        if family is None:
            raise SystemExit(f"未登记的跑法 {run_dir.name}：先补 RUN_FAMILY，不要静默吞掉")
        r = read_run(run_dir)
        for c in r["chapters"]:
            text = c["text"]
            dump_file = run_dir / "dump" / f"ch{c['no']:02d}.md"
            whitelist = lint.load_style_whitelist(str(dump_file))
            findings = lint.scan_document(lint.mask_style_text(text, whitelist))
            paras = paragraphs(text)
            row = {
                "run": run_dir.name, "family": family, "chapter_no": c["no"],
                "status": c.get("status", ""), "bucket": c.get("bucket", ""),
                "chars": len(text), "vis_chars": lint.visible_length(text),
                "n_paras": len(paras),
                "max_para_chars": max((len(p) for p in paras), default=0),
                "notice_lines": sum(1 for p in paras if _NOTICE_LINE.match(p)),
                "struct_lines": sum(1 for _ in _STRUCT_LINE.finditer(text)),
                "required_events": required_events(dump_file),
                "stutter_max_run": stutter_max_run(text),
                "run_e2": r["e2"],
                "types": Counter(f["type"] for f in findings),
                "n_findings": len(findings),
                "is_dead": c.get("status", "") == DEAD_STATUS,
                "is_first": c.get("bucket") == "first_pass",
                "is_pass": c.get("bucket") in PASS_BUCKETS,
                "empty": text.strip() == "",
            }
            line_map[id(row)] = text.splitlines()
            rows.append(row)
    return rows, line_map


def density_proxy(row: dict, which: str) -> float | None:
    """用**交付物自己的** pattern 与「引号外叙述可见字数」口径算连续密度。
    不复制阈值、不改规则本体：只是把 0/1 命中摊成可比的连续量，供专项复核用。"""
    narrative_chars = 0
    hits = 0
    for line in row.get("lines", []):
        trimmed = line.strip()
        if not trimmed or lint.is_divider(trimmed) or lint.is_structural(trimmed):
            continue
        narrative = lint.strip_quoted(trimmed)
        narrative_chars += lint.visible_length(narrative)
        if which == "reasoning":
            hits += sum(len(s["pattern"].findall(narrative)) for s in lint.REASONING_CHAIN_PATTERNS)
        elif which == "metaphor":
            hits += len(lint.METAPHOR_MARKER_PATTERN.findall(narrative))
        elif which == "cliche":
            hits += sum(len(p.findall(narrative)) for p in lint.CLICHE_PATTERNS)
        elif which == "notice":
            if _NOTICE_LINE.match(trimmed):
                hits += sum(len(p.findall(trimmed)) for p in lint.NOTICE_FORMAL_PATTERNS)
    if not narrative_chars:
        return None
    return hits / narrative_chars * 1000.0


def md_table(header: List[str], rows: List[List[str]]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(x for x in r) + " |" for r in rows]
    return "\n".join(out)


def fmt(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}"


# ---------------------------------------------------------------------------
# 表 0：语料底数
# ---------------------------------------------------------------------------
def table0(rows: List[dict]) -> str:
    measured = [r for r in rows if not r["empty"]]
    live_n = len(measured)
    empty_runs = sorted({r['run'] for r in rows if r['empty']})
    lines = [f"跑法 {len({r['run'] for r in rows})} 个｜章次 {len(rows)}（canon 入口 read_run）｜"
             f"其中空正文 {len(rows) - live_n} 章 ⇒ 实测分母 N = {live_n}。",
             "空正文逐跑：" + ("、".join(
                 f"{run}={sum(1 for r in rows if r['run'] == run and r['empty'])} 章"
                 for run in empty_runs) if empty_runs else "无"), ""]
    fam_rows = []
    for fam in FAMILY_ORDER:
        fr = [r for r in rows if r["family"] == fam]
        live = [r for r in fr if not r["empty"]]
        if not live:
            fam_rows.append([FAMILY_LABEL[fam], f"0/{len(fr)}", "-", "-", "-", "-", "-",
                             "整族排除（无正文）"])
            continue
        ch = sorted(r["chars"] for r in live)
        buckets = Counter(r["bucket"] for r in live)
        fam_rows.append([
            FAMILY_LABEL[fam], f"{len(live)}/{len(fr)}", str(statistics.median(ch)),
            f"{sum(ch)}",
            str(statistics.median(r["n_paras"] for r in live)),
            f"{(buckets.get('first_pass', 0) + buckets.get('rewrite_rescued', 0)) / len(live):.0%}",
            " ".join(f"{BUCKET_CN[b]}={buckets.get(b, 0)}" for b in
                     ["first_pass", "rewrite_rescued", "renegotiate_only", "disposition"]),
            "判死(ARC)=" + str(sum(1 for r in live if r["status"] == DEAD_STATUS))])
    lines.append(md_table(["家族（模型@端点｜夹具｜尺）", "有正文章次/总", "章长中位",
                           "章长合计", "自然段中位", "E2(族内并池)", "首/救/继/处", "判死"],
                          fam_rows))
    lines.append("\n章长口径 = `len(text)`（canon `read_run` 的 Draft 正文，含换行）；"
                 "表 1/1B 的千字分母用「引号外可见字数」（`ai_flavor_lint.visible_length`），"
                 "与规则自己的密度口径一致，两者不要混引。"
                 "`E2(族内并池)` 是把家族内各跑的章次并池后的 (首+救)/生成，"
                 "**不等于**各跑 E2 的均值，只用来对照「密度型规则的家族分布与 E2 的家族分布是否同向」。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 表 1：命中分布
# ---------------------------------------------------------------------------
def within_family_rho(rows: List[dict], t: str) -> float:
    """族内秩相关：把「模型家族差」这个最大的混淆先扣掉，再看条数与章长还剩多少关系。"""
    parts = []
    for fam in FAMILY_ORDER:
        fr = [r for r in rows if r["family"] == fam and not r["empty"]]
        if len(fr) < 10 or len({r["vis_chars"] for r in fr}) < 5:
            continue
        rho = spearman([r["types"][t] for r in fr], [r["vis_chars"] for r in fr])
        if rho == rho:  # 非 nan
            parts.append((rho, len(fr)))
    if not parts:
        return float("nan")
    tot = sum(w for _, w in parts)
    return sum(r * w for r, w in parts) / tot


def stratified_gap(rows: List[dict], in_a, in_b, outcome, min_n: int = 3) -> tuple:
    """族内标准化差：只在同一家族里比 A 池与 B 池的 outcome 率，再按两边较小者加权。
    返回（差值 pp, 参与的家族数）。家族数=0 ⇒ 这个对比在本语料里没有可比样本。"""
    num = den = 0.0
    used = 0
    for fam in FAMILY_ORDER:
        fr = [r for r in rows if r["family"] == fam and not r["empty"]]
        ga = [r for r in fr if in_a(r)]
        gb = [r for r in fr if in_b(r)]
        if len(ga) < min_n or len(gb) < min_n:
            continue
        w = min(len(ga), len(gb))
        num += w * (sum(1 for r in ga if outcome(r)) / len(ga)
                    - sum(1 for r in gb if outcome(r)) / len(gb))
        den += w
        used += 1
    return (num / den * 100 if den else float("nan"), used)


def table1(rows: List[dict]) -> str:
    live = [r for r in rows if not r["empty"]]
    total_chars = sum(r["vis_chars"] for r in live)
    all_types = sorted(lint.SEVERITY)
    chars_v = [r["vis_chars"] for r in live]
    tbl = []
    for t in all_types:
        n_hit = sum(1 for r in live if r["types"][t])
        cnt = sum(r["types"][t] for r in live)
        per = [r["types"][t] for r in live]
        kilo = [c / max(1, ch) * 1000 for c, ch in zip(per, chars_v)]
        tbl.append([t, lint.SEVERITY[t], lint.REVIEW_CLASSES[t], lint.CALIBRATION[t],
                    str(n_hit), f"{n_hit / len(live):.1%}", f"{n_hit / 240:.1%}",
                    str(cnt), fmt(cnt / total_chars * 1000),
                    fmt(spearman(per, chars_v)), fmt(spearman(kilo, chars_v)),
                    fmt(within_family_rho(rows, t))])
    head = ["规则", "severity", "review", "calibration", "命中章次", f"命中率/{len(live)}",
            "命中率/240", "finding 条数", "条/千字(全库)", "ρ(条数,章长)", "ρ(条/千字,章长)",
            "族内ρ(条数,章长)"]
    n_density = sum(1 for t in all_types if t in DENSITY_RULES)
    n_count = sum(1 for t in all_types if t in COUNT_RULES)
    out = [f"分母：有正文 {len(live)} 章 / 全库 {len(rows)} 章次 / 任务口径 240；"
           f"有正文字符合计（引号外可见字数口径）= {total_chars}。\n",
           md_table(head, tbl),
           f"\n规则类型：密度/门控型 {n_density} 条（换算条/千字才能跨家族比），"
           f"计数型 {n_count} 条（条数随章长线性增长），其余 {len(all_types) - n_density - n_count} 条见 1B 类型列。"
           "\n`ρ(条数,章长)` 是全库秩相关（含家族间差），`族内ρ(条数,章长)` 只在同一家族内算再按章次加权——"
           "两者都高 ⇒ 这条主要在读章长；全库高而族内低 ⇒ 家族/排版差不是章长差。"]
    # 家族对比：密度/计数型统一换算成「条/千字」，原始命中章次作附注
    fam_lines = ["", "### 1B 家族对比（每格 = 条/千字 ｜ 命中章/该族有正文章次）", ""]
    fam_hdr = ["规则", "类型"] + list(FAMILY_ORDER)
    fam_rows_tbl = []
    for t in all_types:
        cells = [t, "密度" if t in DENSITY_RULES else "计数"]
        for fam in FAMILY_ORDER:
            fr = [r for r in rows if r["family"] == fam and not r["empty"]]
            if not fr:
                cells.append("—")
                continue
            c = sum(r["types"][t] for r in fr)
            ch = sum(r["vis_chars"] for r in fr)
            n = sum(1 for r in fr if r["types"][t])
            cells.append(f"{c / ch * 1000:.2f}｜{n}/{len(fr)}")
        fam_rows_tbl.append(cells)
    fam_lines.append(md_table(fam_hdr, fam_rows_tbl))
    fam_lines.append("\n家族简称见表 0（列序同表 0）；表 0 里标注整族排除的家族此处为 `—`。")
    return "\n".join(out) + "\n" + "\n".join(fam_lines)


# ---------------------------------------------------------------------------
# 表 2：与判定面的重叠
# ---------------------------------------------------------------------------
def table2(rows: List[dict]) -> str:
    live = [r for r in rows if not r["empty"]]
    dead = [r for r in live if r["status"] == DEAD_STATUS]
    first = [r for r in live if r["bucket"] == "first_pass"]
    rescue = [r for r in live if r["bucket"] == "rewrite_rescued"]
    renego = [r for r in live if r["bucket"] == "renegotiate_only"]
    disp = [r for r in live if r["bucket"] == "disposition"]
    passed = [r for r in live if r["bucket"] in PASS_BUCKETS]
    failed = [r for r in live if r["bucket"] not in PASS_BUCKETS]
    tbl = [["规则", f"首 n={len(first)}", f"救 n={len(rescue)}", f"继 n={len(renego)}",
            f"处 n={len(disp)}", f"过线 n={len(passed)}", f"未过线 n={len(failed)}",
            f"判死 n={len(dead)}", "判死−首轮(pp)", "族内判死−首轮(pp)", "族数",
            "判死 条/千字", "首轮 条/千字", "Δ条/千字",
            "命中章的过线率", "未命中章的过线率", "Δ(pp)", "族内Δ过线率(pp)"]]
    base_pass = len(passed) / len(live)

    def per_kilo(pool, t):
        c = sum(r["types"][t] for r in pool)
        ch = sum(r["vis_chars"] for r in pool)
        return c / ch * 1000 if ch else float("nan")

    for t in sorted(lint.SEVERITY):
        def rate(pool):
            return sum(1 for r in pool if r["types"][t]) / len(pool) if pool else float("nan")
        hit = [r for r in live if r["types"][t]]
        miss = [r for r in live if not r["types"][t]]
        hp = sum(1 for r in hit if r["bucket"] in PASS_BUCKETS) / len(hit) if hit else float("nan")
        mp = (sum(1 for r in miss if r["bucket"] in PASS_BUCKETS) / len(miss)) if miss else float("nan")
        kd, kf = per_kilo(dead, t), per_kilo(first, t)
        g_dead, n_fam1 = stratified_gap(
            rows, lambda r: r["is_dead"], lambda r: r["is_first"],
            lambda r, t=t: bool(r["types"][t]))
        g_pass, n_fam2 = stratified_gap(
            rows, lambda r: bool(r["types"][t]), lambda r: not r["types"][t],
            lambda r: r["is_pass"])
        tbl.append([t] + [f"{rate(p) * 100:.1f}%" for p in (first, rescue, renego, disp,
                                                            passed, failed, dead)]
                   + [f"{(rate(dead) - rate(first)) * 100:+.1f}",
                      "—" if n_fam1 == 0 else f"{g_dead:+.1f}", str(n_fam1),
                      fmt(kd), fmt(kf), f"{kd - kf:+.2f}",
                      "—" if not hit else f"{hp * 100:.1f}%",
                      f"{mp * 100:.1f}%",
                      "—" if not hit else f"{(hp - mp) * 100:+.1f}",
                      "—" if n_fam2 == 0 else f"{g_pass:+.1f}"])
    length_by_bucket = "\n".join(
        f"  {BUCKET_CN[b]}（{b}）n={len(g)}：章长中位 {statistics.median(r['chars'] for r in g):.0f} 字"
        f"（可见 {statistics.median(r['vis_chars'] for r in g):.0f}）"
        for b, g in [("first_pass", first), ("rewrite_rescued", rescue),
                     ("renegotiate_only", renego), ("disposition", disp)] if g)
    return (f"分母：有正文 {len(live)} 章｜过线（首+救）={len(passed)}（{base_pass:.1%}）｜"
            f"未过线（继+处）={len(failed)}｜其中判死 ARC_CONFLICT={len(dead)}｜首轮={len(first)}\n\n"
            f"章长本身对判定面的混淆（先把这条摊开，再看规则）：\n{length_by_bucket}\n\n"
            + md_table(tbl[0], tbl[1:])
            + "\n\n「族内」两列 = 只在同一模型家族内部比较、再按家族加权（扣掉「不同模型既写得长又写得不同」"
              "这个混淆）；`族数` 是该对比实际可用的家族数（每族要求判死池与首轮池各 ≥3 章），"
              "族数=0 ⇒ 本语料给不出这个对比的样本，不能读成「没有差」。")


# ---------------------------------------------------------------------------
# 表 3：与 R1–R6 的对齐（可数的部分）
# ---------------------------------------------------------------------------
R_MAP = {
    "not-is-comparison": "R1 复述/句式机械层",
    "reverse-not-is": "R1 复述/句式机械层",
    "negation-parade": "R1 复述/句式机械层",
    "voice-contrast": "R1 之外（套式修辞）",
    "trailer-ending": "R4 候选（章尾非叙事句）",
    "trailer-summary": "R4 候选（章尾非叙事句）",
    "em-dash": "R5 之外的排版项",
    "long-paragraph": "R5 段长与体量",
    "period-stutter": "R5 体量（句长反向）",
    "micro-action-tic": "R1 之外（删减过头指纹）",
    "negation-pair-tic": "R1 复述/句式机械层",
    "cliche-density-tic": "R1 之外（套词）",
    "stock-reaction-tic": "R1 之外（套式反应）",
    "action-list-tic": "R1 之外（无视角动作清单）",
    "abstract-summary-tic": "R4 候选（作者总结）",
    "metaphor-density-tic": "R1 之外（修辞密度）",
    "reasoning-chain-tic": "R1 之外（报告腔）",
    "system-notice-formality-tic": "R4 相邻（载体内公文腔）",
    "overcompressed-prose-tic": "R5 体量（反向：过短）",
    "low-connective-density-tic": "R5 体量（反向：过短）",
    "quote-emphasis-tic": "R4 候选（叙述层引号强调）",
    "formulaic-parallelism": "R1 复述/句式机械层",
}
# 规则簇重叠：同一章被几条 A 类同时命中的分布 + 两两共现（Jaccard）
A_CLASS = ["not-is-comparison", "reverse-not-is", "voice-contrast", "negation-parade",
           "trailer-ending", "trailer-summary", "em-dash"]


def verdicts(rows: List[dict]) -> str:
    """把可数的三件事（命中量级 / 是否被章长解释 / 是否与判定面重叠）摊成定位表。
    阈值写死在这里、可核：|族内判死−首轮| ≥5pp 且族数 ≥2 ⇒ 判为「与判定面重叠」；
    命中率 ≥60% ⇒ 判为「章级满盘」；命中 <5 章 ⇒ 判为「无定标样本」。"""
    live = [r for r in rows if not r["empty"]]
    body = []
    for t in sorted(lint.SEVERITY):
        n_hit = sum(1 for r in live if r["types"][t])
        rate = n_hit / len(live)
        rho_w = within_family_rho(rows, t)
        gap, nfam = stratified_gap(rows, lambda r: r["is_dead"], lambda r: r["is_first"],
                                   lambda r, t=t: bool(r["types"][t]))
        if n_hit == 0:
            v = "不可进：本语料零命中，没有一条定标样本"
        elif n_hit < 5:
            v = "只作观察列：命中 <5 章，任何率都是噪声"
        elif rate >= 0.60:
            v = "只作观察列：章级满盘（命中率 ≥60%），无区分度"
        elif nfam and gap == gap and abs(gap) >= 5.0 and nfam >= 2:
            v = "与判定面重叠：需先定标" + ("（同向于尺）" if gap > 0 else "（反向于尺）")
        else:
            v = "可进报告列（本语料显示它有独立信息）"
        body.append([t, lint.SEVERITY[t], str(n_hit), f"{rate:.1%}",
                     "—" if rho_w != rho_w else f"{rho_w:+.2f}",
                     "—" if nfam == 0 else f"{gap:+.1f}（{nfam} 族）", v])
    return md_table(["规则", "severity", "命中章", "命中率", "族内ρ(章长)",
                     "族内判死−首轮(pp)", "定位（阈值见表下注）"], body)


def table3(rows: List[dict]) -> str:
    live = [r for r in rows if not r["empty"]]
    # R5 的可数代理：自然段数与章长（rubric R5 的判法是 2–4 段 + 不超预算）
    over4 = [r for r in live if r["n_paras"] > 4]
    under2 = [r for r in live if r["n_paras"] < 2]
    lines = [f"R5 代理（canon 正文可数部分）：自然段 >4 段的章次 = {len(over4)}/{len(live)}"
             f"（{len(over4) / len(live):.1%}）；段数 <2 = {len(under2)}；"
             f"段数中位 = {statistics.median(r['n_paras'] for r in live):.0f}；"
             f"章长中位 = {statistics.median(r['chars'] for r in live):.0f} 字。"]
    for t, note in [("long-paragraph", "R5 段长项"), ("period-stutter", "R5 句长/体量项"),
                    ("overcompressed-prose-tic", "R5 体量反向"),
                    ("low-connective-density-tic", "R5 体量反向")]:
        hit = [r for r in live if r["types"][t]]
        both = sum(1 for r in hit if r["n_paras"] > 4)
        only_r = len(over4) - both
        lines.append(f"  {t}（{note}）：命中 {len(hit)} 章，其中与「段数>4」同时成立 {both} 章；"
                     f"「段数>4」单独成立 {only_r} 章（该规则没抓到）；"
                     f"该规则抓到但段数≤4 的 {len(hit) - both} 章。")
    dash_hit = [r for r in live if r["types"]["em-dash"]]
    dash_miss = [r for r in live if not r["types"]["em-dash"]]
    lines.append(
        f"  em-dash 不属于 R5 的段长项，它与体量的关系是：命中章章长中位 "
        f"{statistics.median(r['chars'] for r in dash_hit):.0f} 字 vs 未命中章 "
        f"{statistics.median(r['chars'] for r in dash_miss):.0f} 字（差 "
        f"{statistics.median(r['chars'] for r in dash_hit) - statistics.median(r['chars'] for r in dash_miss):+.0f} 字）。")
    notice_any = sum(1 for r in live if r["notice_lines"])
    struct_any = sum(1 for r in live if r["struct_lines"])
    lines.append(f"R4 代理（canon 正文里还剩多少非叙事文本）：含【…】规则行的章 = {notice_any}，"
                 f"含 markdown 结构行的章 = {struct_any}（read_run 已剥 HTML 注释与 Draft 段外内容）。")
    r4_rules = ["trailer-ending", "trailer-summary", "quote-emphasis-tic", "abstract-summary-tic"]
    lines.append("  R4 相邻规则与 R4 代理的重合：[" +
                 "，".join(f"{t} 命中 {sum(1 for r in live if r['types'][t])} 章，"
                           f"其中正文含非叙事文本的 "
                           f"{sum(1 for r in live if r['types'][t] and (r['notice_lines'] or r['struct_lines']))} 章"
                           for t in r4_rules) + "] ⇒ 这些规则抓的是**句式腔**，不是 R4 的标记泄漏。")
    lines.append(f"R1 代理：本层无可数代理（`docs/phase1-style-rubric-draft.md` §4 明确「不做复述度自动检测器」）。"
                 f"可数的是 A 类句式规则的**互相**重合度（下面的共现矩阵）——它们内部也不重叠，"
                 f"说明它们量的是四类不同形态，而不是同一个「复述」信号。")
    lines.append("R2（立场漂移）/R3（名物与数量自洽）/R6（单章可读）：全部是语义判定，"
                 "本交付物没有任何一条规则触及（无词面代理可数）⇒ 不替代、也不与人工抽检冲突。")
    # A 类内部共现
    lines.append("\n### A 类内部共现（同一章同时命中两条规则的章次数；对角线=该规则命中章数）\n")
    hdr = ["规则"] + A_CLASS
    body = []
    for a in A_CLASS:
        seta = {id(r) for r in live if r["types"][a]}
        cells = [a]
        for b in A_CLASS:
            setb = {id(r) for r in live if r["types"][b]}
            cells.append(str(len(seta & setb)))
        body.append(cells)
    lines.append(md_table(hdr, body))
    # 每条规则的 R 归属
    lines.append("\n### 规则 → rubric 归属（判断列，可数证据见上）\n")
    lines.append(md_table(["规则", "severity", "命中章", "R 归属（分析判断）"],
                          [[t, lint.SEVERITY[t], str(sum(1 for r in live if r["types"][t])),
                            R_MAP[t]] for t in sorted(lint.SEVERITY)]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 附表：被点名的三条 B 类专项复核
# ---------------------------------------------------------------------------
def special(rows: List[dict], line_map: Dict[int, List[str]]) -> str:
    live = [r for r in rows if not r["empty"]]
    infers = [r for r in live if "INFERS" in r["required_events"]]
    other = [r for r in live if "INFERS" not in r["required_events"]]
    out = [f"required_events 含 INFERS 的章次 = {len(infers)}/{len(live)}；按章号：" + " ".join(
        f"ch{no}={sum(1 for r in live if r['chapter_no'] == no and 'INFERS' in r['required_events'])}"
        for no in range(1, 11)), ""]
    body = []
    for t in ["reasoning-chain-tic", "metaphor-density-tic", "cliche-density-tic",
              "abstract-summary-tic", "system-notice-formality-tic"]:
        ri = sum(1 for r in infers if r["types"][t]) / len(infers) if infers else float("nan")
        ro = sum(1 for r in other if r["types"][t]) / len(other) if other else float("nan")
        body.append([f"{t} 命中章率", f"{ri * 100:.1f}%（n={len(infers)}）",
                     f"{ro * 100:.1f}%（n={len(other)}）", f"{(ri - ro) * 100:+.1f}pp"])
    out.append(md_table(["度量", "INFERS 必需章", "非 INFERS 章", "差"], body))

    # 连续密度代理（用交付物自己的 pattern 与自己的「引号外叙述可见字数」口径，不动阈值）
    thresholds = {"reasoning": lint.REASONING_CHAIN_PER_KILO,
                  "metaphor": lint.METAPHOR_DENSITY_PER_KILO,
                  "cliche": lint.CLICHE_DENSITY_PER_KILO}
    rule_name = {"reasoning": "reasoning-chain-tic", "metaphor": "metaphor-density-tic",
                 "cliche": "cliche-density-tic"}
    prox = {}
    for which in thresholds:
        prox[which] = (
            [v for v in (density_proxy({**r, "lines": line_map[id(r)]}, which) for r in infers)
             if v is not None],
            [v for v in (density_proxy({**r, "lines": line_map[id(r)]}, which) for r in other)
             if v is not None])
    out.append("\n### 密度代理（每千字命中数；阈值列 = 交付物自己的常量，未改）\n")
    body = []
    for which, (vi, vo) in prox.items():
        mi = statistics.mean(vi) if vi else float("nan")
        mo = statistics.mean(vo) if vo else float("nan")
        body.append([f"{rule_name[which]}（门 {thresholds[which]}/千字）",
                     f"n={len(vi)}｜中位 {statistics.median(vi):.1f}｜均值 {mi:.1f}"
                     f"｜max {max(vi):.1f}" if vi else "—",
                     f"n={len(vo)}｜中位 {statistics.median(vo):.1f}｜均值 {mo:.1f}"
                     f"｜max {max(vo):.1f}" if vo else "—",
                     f"{mi - mo:+.1f}" if vi and vo else "—"])
    out.append(md_table(["密度代理", "INFERS 必需章", "非 INFERS 章", "均值差"], body))

    out.append("\n### 按家族的密度代理（每千字，均值）\n")
    body = []
    for fam in FAMILY_ORDER:
        fr = [r for r in live if r["family"] == fam]
        if not fr:
            continue
        cells = [fam]
        for which in thresholds:
            vs = [v for v in (density_proxy({**r, "lines": line_map[id(r)]}, which) for r in fr)
                  if v is not None]
            cells.append(f"{statistics.mean(vs):.1f}" if vs else "—")
        cells.append(f"{statistics.median(r['vis_chars'] for r in fr):.0f}")
        body.append(cells)
    out.append(md_table(["家族", "解释链/千字", "比喻/千字", "套词/千字", "可见字数中位"], body))

    notice_hit = sum(1 for r in live if r["types"]["system-notice-formality-tic"])
    notice_cap = sum(1 for r in live if r["notice_lines"] >= lint.NOTICE_FORMAL_MIN_LINES)
    notice_any = sum(1 for r in live if r["notice_lines"] > 0)
    out.append(f"\n公文腔构造可达性：正文含 ≥1 行【…】的章 = {notice_any}/{len(live)}；"
               f"达到该规则最低行数门（≥{lint.NOTICE_FORMAL_MIN_LINES} 行）的章 = {notice_cap}；"
               f"该规则实际命中 = {notice_hit}。")

    runs = [r["stutter_max_run"] for r in live]
    out.append("\n### 碎句号门（连续 ≤{} 字叙述句 ≥{} 串）在本语料的可达性\n".format(
        lint.STUTTER_MAX_SENTENCE, lint.STUTTER_MIN_RUN))
    out.append(f"全库最长碎句串 = {max(runs)} 句（门 = {lint.STUTTER_MIN_RUN}）；"
               f"分布：" + " ".join(f"{k}串×{v}章" for k, v in sorted(Counter(runs).items()))
               + f"；达到门的章 = {sum(1 for v in runs if v >= lint.STUTTER_MIN_RUN)}。"
               "\n（用交付物自己的 `strip_quoted`/`split_sentences`/`visible_length` 与它自己的两个常量算的"
               "连续串长度，未改任何阈值。）")
    return "\n".join(out)


def main(argv: List[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    json_out = None
    if "--json-out" in argv:
        json_out = Path(argv[argv.index("--json-out") + 1])
    rows, line_map = collect()
    print("# 表 0｜语料底数\n\n" + table0(rows))
    print("\n\n# 表 1｜每条规则的命中分布\n\n" + table1(rows))
    print("\n\n# 表 2｜与判定面（bucket）的重叠\n\n" + table2(rows))
    print("\n\n# 表 3｜与 R1–R6 的对齐\n\n" + table3(rows))
    print("\n\n# 表 4｜逐条定位（可数部分，判据建议在此口径上写）\n\n" + verdicts(rows))
    print("\n\n# 附表｜被点名三条 B 类的专项复核\n\n" + special(rows, line_map))
    if json_out:
        dump = [{k: (dict(v) if isinstance(v, Counter) else v) for k, v in r.items()}
                for r in rows]
        json_out.write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n\n[逐章明细已写 {json_out}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
