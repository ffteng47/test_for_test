# L3 批3 判分对照试点（W2 归因实验本体，一次性旁路脚本，不进管线、不经 validator）。
# 口径：docs/l3-batch3-handoff-brief.md W2——喂**同一候选集**（sampling/l3-corpus-v01.json，
# 批1-2 宿主确定性配对的 290 候选）给判分端点，模型**只判不找**：真|误报|存疑 + 一句话理由 + 行号区间。
# 归因读数：精确率对照 v0.4.2 基线（裸 44.8%/宿主压制 54.5%）——跳升=配对瓶颈实锤（模型无辜），
# 仍塌=模型语义判断实锤。终裁权在 tff。
# 两条 W1 预警兑现：①epistemic_pair 只作宿主先验展示，禁写模型可执行禁令（防自我撤回 ch50 C 锚）；
# ②撤回收纳过滤：理由含「撤回/按规不得报」或判定非法词 → 该候选记 存疑 并打 RETRACT 标。
# 送检面（§3.3 检索增强形态）：C 族=证据帧（区间宿主回填，零全章）；A/B 族=全章编号正文
# （无到达/无回卷是全称否定判断，帧内不可判——如实分开计量）。
# 尺面戳：l3-judge-v1.0（判定提示词逐字归档在本文件）。
# 行号基准（冒烟实证坑，风险①同型）：evidence_refs=Draft body 剥注释/空行（l3 strip_comments 输出）后
# 1 基——对未剥基准回填=系统性引到空行；空引文按 [区间失守] 计。冒烟另修：误报口径须逐字贴 §7.9
# 台账（「台词/推测对立」写宽一圈=宿主亲手压死 ch50 锚所在 dialogue/speculation 类，违反 W3 锚安全闸）。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/l3_judge_pilot.py [章号...] > sampling/l3-judge-v10.console.log 2>&1
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.llm import LlmClient, LlmRouter                       # noqa: E402
from plot_engine.l3.scene_index import strip_comments                  # noqa: E402
from plot_engine.metrics import _section_body                           # noqa: E402

OK_CH = [1, 8, 12, 13, 21, 22, 23, 26, 35, 40, 42, 44, 48]
NH_CH = [2, 5, 6, 14, 15, 20]
BAD_CH = [50]
DUMP = Path(__file__).resolve().parent / "wpe50ch"
CORPUS = json.loads((Path(__file__).resolve().parent / "l3-corpus-v01.json")
                    .read_text(encoding="utf-8"))

JUDGE_HEADER = """你是穿帮候选的**判分器**。候选由宿主程序确定性配对产出，你只判定每一条候选是否成立，
不要自行寻找新矛盾。判定口径（依据 v0.2-v0.4.2 全量人核台账）：
- 真：两处/一处证据之间存在**作者层面**的自相矛盾（同一事实两种说法且不可同真；在场但前文无到达且非章首开场；离开后无到达又回原地）。
- 误报：可同真（如「都在」与「各保管一把」）；人物说辞与物证/旁白陈述对立（侦探文悬念设计——说的和事实不一致，是人物在骗，不是作者在矛盾）；引文本身含到达或离开叙述、与候选主张相悖；章首段落的开场在场；单处陈述、无冲突方。
- 存疑：证据不足以裁定。
注意两条：①不同人物各自的推测互不一致不是矛盾，但**叙述层**对同一事实的两种说法不可同真仍是真；②候选若已被叙事自觉摆上台面（角色自己指出规则前后不一），仍可判真。标注仅供参考，不是禁令，一切以证据文本为准。
输出纪律：每条候选一行，格式 `序号|真|误报|存疑三选一|一句话理由（必须针对该候选的证据文本，不得照抄口径条目）|依据行号区间(如12-13)`；
不要输出判定行以外的内容。
"""

AB_RULES = {"A": "A 进场无源：该角色首次在场互动前无到达叙述", "B": "B 空间回卷：明确离开后无到达叙述又在原地"}


def _backfill(body, ref):
    m = re.fullmatch(r"(\d+)-(\d+)", ref)
    a, b = (int(m.group(1)), int(m.group(2))) if m else (int(ref), int(ref))
    if not (1 <= a <= b <= len(body)):
        return None
    text = "⏎".join(body[a - 1:b])
    return text if text.strip() else None                    # 空引文=基准错位，按失守计


def _c_lines(cands, body):
    out, kept = [], []
    for c in cands:
        quotes = [_backfill(body, r) for r in c["evidence_refs"]]
        if any(q is None for q in quotes):
            print(f"   [区间失守] {c['detail'][:80]} refs={c['evidence_refs']}")
            continue
        kept.append(c)
        tag = f"（标注: {c['epistemic_pair']}）" if c["epistemic_pair"] else ""
        out.append(f"序号{len(kept)}{tag} {c['detail']}\n"
                   + "\n".join(f"  行{r}: {q}" for r, q in zip(c["evidence_refs"], quotes)))
    return "\n".join(out), kept


def _ab_lines(cands):
    lines = []
    for i, c in enumerate(cands, 1):
        refs = "、".join(c["evidence_refs"])
        lines.append(f"序号{i} [{AB_RULES[c['family']]}] {c['detail']}（证据行 {refs}）")
    return "\n".join(lines), list(cands)


def _parse(text, cands, verdicts, family_of):
    n_bad = n_hit = 0
    for ln in text.splitlines():
        parts = [p.strip() for p in ln.split("|")]
        m = re.fullmatch(r"(?:序号)?\s*(\d+)", parts[0]) if parts else None
        if not m or not (1 <= int(m.group(1)) <= len(cands)):
            continue
        n_hit += 1
        v = parts[1] if len(parts) > 1 else ""
        reason = "|".join(p.strip() for p in parts[2:5])
        if v not in ("真", "误报", "存疑") or re.search(r"撤回|按规不得报", reason):
            if v not in ("真", "误报", "存疑"):
                n_bad += 1
            v = "存疑"
            reason = f"[RETRACT/非法] {reason}"[:120]
        verdicts.append((family_of(cands[int(m.group(1)) - 1]), cands[int(m.group(1)) - 1], v, reason))
    if n_hit == 0:
        print(f"   [解析失守回显] {text[:600]}")
    elif n_hit < len(cands):
        print(f"   [漏判] 候选 {len(cands)} 判定 {n_hit}（截断或格式漂移，如实入册）")
    return n_bad


base_url = os.environ.get("L3_BASE_URL", "http://127.0.0.1:11500/v1")
model = os.environ.get("L3_MODEL", "qwen2.5:32b")
cfg = {"base_url": base_url, "model": model, "max_tokens": 2500, "temperature": 0,
       "timeout_s": 600, "extra_body": {"options": {"num_ctx": 16384}}}
if os.environ.get("L3_API_KEY_ENV"):
    cfg["api_key_env"] = os.environ["L3_API_KEY_ENV"]
if os.environ.get("L3_USD_PER_1K"):
    cfg["usd_per_1k_tokens"] = float(os.environ["L3_USD_PER_1K"])
client = LlmClient(LlmRouter.from_config({"l3": cfg}))

targets = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(int(k) for k in CORPUS)
verdicts = []
frame_tokens = full_tokens = 0
n_bad = 0
for ch in targets:
    chapter = CORPUS.get(str(ch))
    if not chapter or not chapter["candidates"]:
        continue
    body = strip_comments(_section_body(
        (DUMP / f"ch{ch:02d}.md").read_text(encoding="utf-8", errors="replace").splitlines(), "Draft"))[0]
    group = "OK" if ch in OK_CH else ("NH" if ch in NH_CH else "BAD")
    cs = chapter["candidates"]
    ab = [c for c in cs if c["family"] in ("A", "B")]
    cc = sorted((c for c in cs if c["family"] == "C"),
                key=lambda c: (c["detail"].split(":")[0], c["evidence_refs"]))
    printed = []
    start = len(verdicts)

    def _tally(n):
        vs = [v for _, _, v, _ in verdicts[-n:]]
        return f"{vs.count('真')}真/{vs.count('误报')}误/{vs.count('存疑')}疑"

    if cc:
        ctext, kept = _c_lines(cc, body)
        if kept:
            msg = [{"role": "user", "content": JUDGE_HEADER
                    + f"\n本章（ch{ch:02d}）C 族候选 {len(kept)} 条，逐条判定：\n{ctext}\n"}]
            text, usage = client.complete("l3", msg)
            frame_tokens += usage.prompt_tokens
            n_bad += _parse(text, kept, verdicts, lambda c: "C")
            printed.append(f"C({len(kept)}):{_tally(len(kept))}")
    if ab:
        atext, kept = _ab_lines(ab)
        numbered = "\n".join(f"{i:03d} {ln}" for i, ln in enumerate(body, 1))
        msg = [{"role": "user", "content": JUDGE_HEADER
                 + f"\n编号正文（ch{ch:02d}）：\n{numbered}\n\nA/B 族候选 {len(kept)} 条，逐条判定：\n{atext}\n"}]
        text, usage = client.complete("l3", msg)
        full_tokens += usage.prompt_tokens
        n_bad += _parse(text, kept, verdicts, lambda c: c["family"])
        printed.append(f"AB({len(kept)}):{_tally(len(kept))}")

    print(f"ch{ch:02d} [{group}] candidates={len(cs)} -> {' | '.join(printed)}"
          f"（累计prompt_tokens 帧={frame_tokens} 全章={full_tokens}）")
    for fam, c, v, r in verdicts[start:]:
        print(f"   {fam}|{v}|{c['detail'][:90]}|{r[:90]}")
    sys.stdout.flush()

print(f"\n合计：候选判定 {len(verdicts)} 条（区间失守丢弃见上方 [区间失守]，非法/撤回改判 {n_bad}）")
print(f"送检面：C 证据帧 tokens={frame_tokens}｜A/B 全章 tokens={full_tokens}"
      f"｜对照=全章硬塞形态（v0.4.2 均值 2677/章×有候选章数）")
print(f"调用 {len(client.calls)} 次 tokens={client.total_tokens} 成本=${client.total_cost_usd:.4f}（本地=0）")

# 出口自证：判定台账 JSON（人核/秤量用，沿五态对照组先例——构造性不靠肉眼）
Path(__file__).with_name("l3-judge-v10.verdicts.json").write_text(
    json.dumps([{"family": f, "chapter": c["chapter"], "detail": c["detail"],
                 "refs": c["evidence_refs"], "pair": c["epistemic_pair"], "verdict": v, "reason": r}
                for f, c, v, r in verdicts], ensure_ascii=False, indent=1), encoding="utf-8")
