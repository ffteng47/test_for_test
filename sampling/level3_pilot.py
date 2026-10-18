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
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/level3_pilot.py [--v04|--v041] [章号...]
#       > sampling/level3-pilot-v04.console.log 2>&1
# 丁批（tff「确认拍丁」2026-10-18）⇒ v0.4.2=三规则修复+D 族章内重复检测：
# ①A 章首豁免=宿主标注（章首 3 行内在场=开场场景设定）；②B 回查失守=提示词撤回指令+宿主到达模式标注
# （inkos REVIEW_SOURCE_MISMATCH 同款）；③C 说辞-物证=提示词认识论分层（台词 vs 事实/物证=悬念不判矛盾）；
# ④D=章内逐字重复块（宿主直出零 LLM，参照 check-degeneration.js 逐行复读指纹；v1 只逐字，微改写留 v2）。
# 宿主纪律=只标注不删除（防误杀真 finding，压制面交第二读数人核）；回归闸=ch50 三锚，掉锚如实入册。
# 甲′批（tff「确认甲」2026-10-17）⇒ v0.4.1=区间形态不变、B 族补「逐条摘出再回查」做法（C 族同款，
# v0.4 掉 B 锚 0/3 的对症加码）；回归闸=ch50 B 锚双拍须回，回不来退并集形态。
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

PROMPT_V041 = """下面是一章小说正文，每行以三位数行号开头（如「012 正文……」）。
引用正文时必须且只能用行号区间，不得抄写任何原文句子。
第一步：按行文顺序列出「在场时间线」——每个时点谁在什么地点做什么，每条一行。
第二步：对照时间线，找出三类「章内自相矛盾」：
A 进场无源：某角色首次在某地点出现并参与互动，但前文没有他到达该地点的叙述。
B 空间回卷：某角色明确离开某地点（或已出现在别处）之后，未经任何到达叙述，又在该原地点在场互动。
　　B 做法：先把章内**每一处**写到某角色「离开/动身/前往别处/到达某地」的行逐条摘出（记行号，注明谁、从哪、到哪），
　　再逐条回查：该时点之后是否还有他在**原地点**在场互动的行、且中间没有任何到达叙述——宁可多列一步不可跳。
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

PROMPT_V042 = """下面是一章小说正文，每行以三位数行号开头（如「012 正文……」）。
引用正文时必须且只能用行号区间，不得抄写任何原文句子。
第一步：按行文顺序列出「在场时间线」——每个时点谁在什么地点做什么，每条一行。
第二步：对照时间线，找出三类「章内自相矛盾」：
A 进场无源：某角色首次在某地点出现并参与互动，但前文没有他到达该地点的叙述。
B 空间回卷：某角色明确离开某地点（或已出现在别处）之后，未经任何到达叙述，又在该原地点在场互动。
　　B 做法：先把章内**每一处**写到某角色「离开/动身/前往别处/到达某地」的行逐条摘出（记行号，注明谁、从哪、到哪），
　　再逐条回查：该时点之后是否还有他在**原地点**在场互动的行、且中间没有任何到达叙述——宁可多列一步不可跳。
C 规则漂移：同一章内对同一静态事实（数量、归属、谁保管、谁值守等）的前后陈述互相矛盾。
　　C 做法：先把章内**每一处**关于数量/归属/钥匙/值守/在场人数的陈述逐条摘出（记行号），再两两对照，宁可多列一步不可跳。
配对硬规（每条发现必须满足，否则该条作废、不要输出）：
1. 每条给两个**最小行号区间**，每个区间最多 2 行，单行区间也写成 12-13 这种形式；行号必须取自正文行首的三位数，不得杜撰；
2. A 族：区间一=该角色首次在该地点出现并互动的行，区间二=其前的时点中**别人**在该地点、或该角色在别处的最近一行（证明他进场无源）；
3. B 族：区间一=明确离开（或已到别处）的行，区间二=之后又在原地点在场互动的行；
4. C 族：两个区间必须是对**同一件事**的两个互相矛盾陈述（数量不同、归属不同、在场人数不同等）。
裁量规（丁批新增，逐条适用，违则该条作废）：
5. A 族章首豁免：正文前 3 行内角色已在场属于开场场景设定，不算进场无源，不得报告；
6. B 族证据自洽：输出前逐条回查区间二原文——若该行本身就含到达叙述（门被推开/打开/敲响、走进/进来/踏入/出现在门口/破门而入等），说明到达已被叙述，该条必须撤回不得输出；
7. C 族认识论分层：先把每条陈述标为【叙述者事实】/【角色台词】/【角色猜测】；只有【叙述者事实】与【叙述者事实】、或同一角色前后两处【台词】互相矛盾才可报；角色台词与叙述者事实/物证对立属于悬念设计（角色可能在说谎或记错），不得报为矛盾。
只报确凿矛盾；没有就不要硬凑，宁可漏报不可误报。
最后单独起一行输出 ==FINDINGS==，其后每条发现一行，格式 `A|区间一|区间二|一句话理由`（B、C 同理，区间形如 12-13）；
若无任何发现，标记行后只输出 NONE。
正文开始：
"""

V042 = "--v042" in sys.argv
V041 = "--v041" in sys.argv
PROMPT_V04 = PROMPT_V042 if V042 else (PROMPT_V041 if V041 else PROMPT_V04)

# 端点/模型可用环境变量覆盖（默认=尺面归档口径 32b@11500；并行臂如 14b@11434 本地 3090）。
# 换模型=换读数，归档日志章头带 model@host 戳，跨臂比较资格见 calibration-pack §7.10。
# 云端臂（v0.5-cloud，tff 2026-10-18「已经提供环境变量；按照建议执行」）：
# L3_API_KEY_ENV=key 的环境变量名（llm.py api_key_env 机制，key 不落盘）；
# L3_TEMPERATURE=温度覆盖（deepseek 拒超界值；云端配置源 deepseek.router.json=0 贪心，
# 顺带消解丁批归因混淆①采样漂移）；L3_USD_PER_1K=成本单价（源同文件 0.00041）。
import os
L3_BASE_URL = os.environ.get("L3_BASE_URL", "http://127.0.0.1:11500/v1")
L3_MODEL = os.environ.get("L3_MODEL", "qwen2.5:32b")
L3_API_KEY_ENV = os.environ.get("L3_API_KEY_ENV")
L3_TEMPERATURE = os.environ.get("L3_TEMPERATURE")
L3_USD_PER_1K = os.environ.get("L3_USD_PER_1K")
_l3_cfg = {
    "base_url": L3_BASE_URL, "model": L3_MODEL,
    "max_tokens": 2500,
    "temperature": float(L3_TEMPERATURE) if L3_TEMPERATURE else 200,
    "timeout_s": 600,
    "extra_body": {"options": {"num_ctx": 12288}}}
if L3_API_KEY_ENV:
    _l3_cfg["api_key_env"] = L3_API_KEY_ENV
if L3_USD_PER_1K:
    _l3_cfg["usd_per_1k_tokens"] = float(L3_USD_PER_1K)
router = LlmRouter.from_config({"l3": _l3_cfg})               # 时间线+正文，12k 有余量
client = LlmClient(router)
dump = Path(__file__).resolve().parent / "wpe50ch"

V04 = "--v04" in sys.argv or V041 or V042
targets = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(OK_CH + NH_CH + BAD_CH)


def _backfill(body, seg):
    """seg='12-13' → 正文原行（跨行用 ⏎ 拍平，quote_verify 去非字符后可核）。失败返回 None。"""
    m = re.fullmatch(r"\s*0*(\d+)\s*[-–—~至]\s*0*(\d+)\s*", seg)
    a, b = (int(m.group(1)), int(m.group(2))) if m else ((int(seg),) * 2 if seg.strip().isdigit() else (0, 0))
    if not (1 <= a <= b <= len(body)):
        return None
    return "⏎".join(body[a - 1:b])


# ---- 丁批宿主层（v0.4.2，只标注不删除） ----
CHAPTER_HEAD_N = 3  # A 族章首豁免窗口（行）
# wpe50 样本具名主线角色（试点口径；泛化留批1-2 实体层）——smoke 实证：模型区间一常避开
# 章首行选后续互动行（ch20-A），故豁免判定改查「区间一中的角色是否已在章首建立」。
CAST_RE = re.compile("张三|王五|李四|赵六")
# 到达叙述模式：门语境的推开/打开/敲响 + 进入类动词（inkos REVIEW_SOURCE_MISMATCH 的宿主核验面）
ARRIVAL_RE = re.compile(
    r"(门[^。]{0,8}(推开|打开|敲响|开了))|((推开|打开|敲响)[^。]{0,8}门)"
    r"|(走了?进来|进来的是|踏入|迈进|推门|破门|闯入|出现在门口|步入)")
_WS_RE = re.compile(r"[\s　，。、；：？！…—·「」『』“”‘’（）()《》〈〉,.!?;:'\"\-]")


def _seg_start(seg):
    m = re.match(r"\s*0*(\d+)", seg or "")
    return int(m.group(1)) if m else 0


def _dup_runs(body, min_run=3, min_len=20):
    """章内逐字重复块：去空白标点后整行相等且双序列同步步进的连续块（≥min_run 行）。
    ch15/20 实证形态=整段逐字重排；v1 只逐字，微改写近重复留 v2（shingle）。"""
    seen, pairs = {}, []
    for i, ln in enumerate(body):
        n = _WS_RE.sub("", ln)
        if len(n) < min_len:
            continue
        if n in seen:
            pairs.append((seen[n], i))
        else:
            seen.setdefault(n, i)
    runs = []
    for a, b in pairs:
        if runs and a == runs[-1][0] + runs[-1][2] and b == runs[-1][1] + runs[-1][2]:
            runs[-1][2] += 1
        else:
            runs.append([a, b, 1])
    return [(a, a + l - 1, b, b + l - 1, l) for a, b, l in runs if l >= min_run]


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
            ann = ""
            if V042:
                if p[0] == "A":
                    head = "\n".join(body[:CHAPTER_HEAD_N])
                    if _seg_start(p[1]) <= CHAPTER_HEAD_N:
                        ann += " [宿主豁免候选:区间1在章首%d行内]" % CHAPTER_HEAD_N
                    else:
                        # 主体=理由句中首个具名角色（中文主语先行惯例）——smoke2 实证：
                        # 用 q1 全名集合会把 ch50 A 锚误判（q1 含章首合法在场的赵六）。
                        msub = CAST_RE.search(p[3] or "")
                        if msub and msub.group(0) in CAST_RE.findall(head):
                            ann += " [宿主豁免候选:主体已在章首建立]"
                if p[0] == "B" and ARRIVAL_RE.search(q2 or ""):
                    ann += " [宿主撤回候选:区间2含到达模式]"
            finds.append(f"{p[0]}|{q1}|{q2}|{p[3]}{ann}")
        else:
            finds.append(r)
    if V042:  # D 族宿主直出（零 LLM）：逐字重复块，引文取块首 ≤2 行代表
        for a1, a2, b1, b2, ln_ in _dup_runs(body):
            q1 = _backfill(body, f"{a1}-{min(a1 + 1, a2)}")
            q2 = _backfill(body, f"{b1}-{min(b1 + 1, b2)}")
            finds.append(f"D|{q1}|{q2}|章内逐字重复块 {a1}-{a2}行 ↔ {b1}-{b2}行（共{ln_}行）[宿主直出]")
    group = "OK" if ch in OK_CH else ("NH" if ch in NH_CH else "BAD")
    kinds = "".join(sorted({f[0] for f in finds}))
    print(f"ch{ch:02d} [{group}] ({L3_MODEL}@{L3_BASE_URL.split(chr(47))[2]}) findings={len(finds)} kinds={kinds or '-'}"
          + (f" 区间失守={bad}" if V04 else "")
          + f"（prompt_tokens={usage.prompt_tokens} 截断风险={'有' if usage.prompt_tokens >= 11000 else '无'}）")
    for f in finds:
        print("   ", f)
    sys.stdout.flush()

print(f"\n合计：调用 {len(client.calls)} 次 tokens={client.total_tokens} 成本=${client.total_cost_usd:.4f}（本地=0）")
print(client.render_call_diagnostics())
