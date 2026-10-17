# level3 C 旁路试点（一次性实验脚本，不进管线、不经 validator）。
# 口径：docs/level3-fn-calibration-pack.md §3.3 + 拍板记录「C 试点放行」——
# 13 OK + ch50 + 6 NH，Draft 取 sampling/wpe50ch 归档正文，本地 qwen2.5:32b 实调。
# 尺面戳：l3-presence-v0.3（R2 纪律：改措辞=改读数，本文件即逐字归档）。
# v0.1（单趟+严格行格式）冒烟在 ch50 三锚点全漏（NONE，2026-10-17 console 在案）；
# 两步式探针（先列在场时间线再对照）命中 ①②/③ 分模可见 ⇒ v0.2=两步式+尾行严格式（72b1f97 读数在案）。
# 乙批（tff「2选择乙」2026-10-17）⇒ v0.3=v0.2 基础上收紧引文配对：逐字引文+分族配对规定+输出前自查，
# 目标=把「配对粗糙」与「所指为真」分离出精确率；回归闸=ch50 三锚点仍须全中（掉锚=收紧过头，如实入册）。
# 行号区间批（tff 认可参照方案 2026-10-17）⇒ v0.4=模型只交行号区间（送检文本每行加 001 前缀），
# 引文由本脚本同进程对 _section_body 的同一份内存行列表回填——引用保真从模型义务改成程序义务。
# 行号基准：不二次读盘，无换行/编码漂移面；对照=quote_verify.py 跑 v0.4 log，
# 逐行回填应 verbatim、跨行 ⏎ 拍平应 normalized，出 stitched 及以上=回填管线 bug。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/level3_pilot.py [--v04] [章号...]
#       > sampling/level3-pilot-v04.console.log 2>&1
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.llm import LlmClient, LlmRouter                       # noqa: E402
from plot_engine.metrics import _section_body                           # noqa: E402

OK_CH = [1, 8, 12, 13, 21, 22, 23, 26, 35, 40, 42, 44, 48]
NH_CH = [2, 5, 6, 14, 15, 20]
BAD_CH = [50]

PROMPT_V02 = """下面是一章小说正文。
第一步：按行文顺序列出「在场时间线」——每个时点谁在什么地点做什么，每条一行。
第二步：对照时间线，找出三类「章内自相矛盾」：
A 进场无源：某角色首次在某地点出现并参与互动，但前文没有他到达该地点的叙述。
B 空间回卷：某角色明确离开某地点（或已出现在别处）之后，未经任何到达叙述，又在该原地点在场互动。
C 规则漂移：同一章内对同一静态事实（数量、归属、谁保管、谁值守等）的前后陈述互相矛盾——把每处数量/规则陈述两两对照。
只报确凿矛盾，每条引用两处原文短句；没有就不要硬凑，宁可漏报不可误报。
最后单独起一行输出 ==FINDINGS==，其后每条发现一行，格式 `A|短句1|短句2|一句话理由`（B、C 同理）；
若无任何发现，标记行后只输出 NONE。
正文开始：
"""

PROMPT = """下面是一章小说正文。
第一步：按行文顺序列出「在场时间线」——每个时点谁在什么地点做什么，每条一行。
第二步：对照时间线，找出三类「章内自相矛盾」：
A 进场无源：某角色首次在某地点出现并参与互动，但前文没有他到达该地点的叙述。
B 空间回卷：某角色明确离开某地点（或已出现在别处）之后，未经任何到达叙述，又在该原地点在场互动。
C 规则漂移：同一章内对同一静态事实（数量、归属、谁保管、谁值守等）的前后陈述互相矛盾。
　　C 做法：先把章内**每一处**关于数量/归属/钥匙/值守/在场人数的陈述逐条摘出，再两两对照，宁可多列一步不可跳。
配对硬规（每条发现必须满足，否则该条作废、不要输出）：
1. 两处引文都必须逐字摘自正文（各不超过 30 字），输出前逐条回正文核对，核对不上就删掉这条；
2. A 族：短句1=该角色在该地点首次出现并互动的句子，短句2=其前的时点中**别人**在该地点、或该角色在别处的最近一句（证明他进场无源）；
3. B 族：短句1=明确离开（或已到别处）的句子，短句2=之后又在原地点在场互动的句子；
4. C 族：短句1 与短句2 必须是对**同一件事**的两个互相矛盾陈述（数量不同、归属不同、在场人数不同等）。
只报确凿矛盾；没有就不要硬凑，宁可漏报不可误报。
最后单独起一行输出 ==FINDINGS==，其后每条发现一行，格式 `A|短句1|短句2|一句话理由`（B、C 同理）；
若无任何发现，标记行后只输出 NONE。
正文开始：
"""

PROMPT_V04 = """下面是一章小说正文，每行以三位数行号开头（如「012 正文……」）。
引用正文时必须且只能用行号区间，不得抄写任何原文句子。
第一步：按行文顺序列出「在场时间线」——每个时点谁在什么地点做什么，每条一行。
第二步：对照时间线，找出三类「章内自相矛盾」：
A 进场无源：某角色首次在某地点出现并参与互动，但前文没有他到达该地点的叙述。
B 空间回卷：某角色明确离开某地点（或已出现在别处）之后，未经任何到达叙述，又在该原地点在场互动。
C 规则漂移：同一章内对同一静态事实（数量、归属、谁保管、谁值守等）的前后陈述互相矛盾。
　　C 做法：先把章内**每一处**关于数量/归属/钥匙/值守/在场人数的陈述逐条摘出（记行号），再两两对照，宁可多列一步不可跳。
配对硬规（每条发现必须满足，否则该条作废、不要输出）：
1. 每条给两个**最小行号区间**，每个区间最多 2 行，单行区间也写成 12-12 这种形式；行号必须取自正文行首的三位数，不得杜撰；
2. A 族：区间一=该角色首次在该地点出现并互动的行，区间二=其前的时点中**别人**在该地点、或该角色在别处的最近一行（证明他进场无源）；
3. B 族：区间一=明确离开（或已到别处）的行，区间二=之后又在原地点在场互动的行；
4. C 族：两个区间必须是对**同一件事**的两个互相矛盾陈述（数量不同、归属不同、在场人数不同等）。
只报确凿矛盾；没有就不要硬凑，宁可漏报不可误报。
最后单独起一行输出 ==FINDINGS==，其后每条发现一行，格式 `A|区间一|区间二|一句话理由`（B、C 同理，区间形如 12-13）；
若无任何发现，标记行后只输出 NONE。
正文开始：
"""

router = LlmRouter.from_config({"l3": {
    "base_url": "http://127.0.0.1:11500/v1", "model": "qwen2.5:32b",
    "max_tokens": 2500, "temperature": 200, "timeout_s": 600,
    "extra_body": {"options": {"num_ctx": 12288}}}})          # 时间线+正文，12k 有余量
client = LlmClient(router)
dump = Path(__file__).resolve().parent / "wpe50ch"

V04 = "--v04" in sys.argv
targets = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(OK_CH + NH_CH + BAD_CH)


def _backfill(body, seg):
    """seg='12-13' → 正文原行（跨行用 ⏎ 拍平，quote_verify 去非字符后可核）。失败返回 None。"""
    m = re.fullmatch(r"\s*0*(\d+)\s*[-–—~至]\s*0*(\d+)\s*", seg)
    a, b = (int(m.group(1)), int(m.group(2))) if m else ((int(seg),) * 2 if seg.strip().isdigit() else (0, 0))
    if not (1 <= a <= b <= len(body)):
        return None
    return "⏎".join(body[a - 1:b])


for ch in targets:
    lines = (dump / f"ch{ch:02d}.md").read_text(encoding="utf-8", errors="replace").splitlines()
    body = _section_body(lines, "Draft")
    if V04:
        sent = PROMPT_V04 + "\n".join(f"{i:03d} {ln}" for i, ln in enumerate(body, 1))
    else:
        sent = PROMPT + "\n".join(body)
    text, usage = client.complete("l3", [{"role": "user", "content": sent}])
    tail = text.split("==FINDINGS==")[-1]
    raws = [ln.strip() for ln in tail.splitlines() if ln.strip()[:1] in "ABC" and ln.count("|") >= 3]
    finds, bad = [], 0
    for r in raws:
        p = r.split("|")
        if V04:
            q1, q2 = _backfill(body, p[1]), _backfill(body, p[2])
            if q1 is None or q2 is None:
                bad += 1
                print("    [区间失守]", r[:160])
                continue
            finds.append(f"{p[0]}|{q1}|{q2}|{p[3]}")
        else:
            finds.append(r)
    group = "OK" if ch in OK_CH else ("NH" if ch in NH_CH else "BAD")
    kinds = "".join(sorted({f[0] for f in finds}))
    print(f"ch{ch:02d} [{group}] findings={len(finds)} kinds={kinds or '-'}"
          + (f" 区间失守={bad}" if V04 else "")
          + f"（prompt_tokens={usage.prompt_tokens} 截断风险={'有' if usage.prompt_tokens >= 11000 else '无'}）")
    for f in finds:
        print("   ", f)
    sys.stdout.flush()

print(f"\n合计：调用 {len(client.calls)} 次 tokens={client.total_tokens} 成本=${client.total_cost_usd:.4f}（本地=0）")
print(client.render_call_diagnostics())
