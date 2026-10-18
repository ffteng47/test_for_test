# 一次性标注器（a 候选离线兑现，2026-10-17）：把 v0.2/v0.3 console 的每条 finding 按引文可核度分五态。
# verbatim=逐字原样在正文；normalized=去标点后在；stitched=拆开的片段各自在（语义摘述拼出来的）；
# paraphrase=单字级微改写（difflib 匹配率≥0.7，锚点为真、字面走样）；unverifiable=对不上（疑编造）。
# finding 取两处引文的较差态。零重跑、零 GPU、不写任何账。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/quote_verify.py
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.metrics import _section_body                          # noqa: E402

DUMP = Path(__file__).resolve().parent / "wpe50ch"
_RANK = ["verbatim", "normalized", "stitched", "paraphrase", "unverifiable"]
_clean = lambda s: re.sub(r"[^\w]", "", s)


def _ratio(qc, dc):
    if not qc:
        return 0.0
    return sum(b.size for b in SequenceMatcher(None, qc, dc, autojunk=False).get_matching_blocks()) / len(qc)


def classify(q, raw, clean):
    if q in raw:
        return "verbatim"
    qc = _clean(q)
    if qc in clean:
        return "normalized"
    parts = [p for p in re.split(r"[。，！？；：、]", q) if len(p) >= 6]
    if parts and all(_clean(p) in clean for p in parts):
        return "stitched"
    return "paraphrase" if _ratio(qc, clean) >= 0.7 else "unverifiable"


def verify(log):
    agg = {}
    cur = None
    for ln in Path(log).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^ch(\d+) \[(\w+)\]", ln)
        if m:
            cur = (int(m.group(1)), m.group(2))
            continue
        s = ln.strip()
        m = re.match(r"^[ABC]\|", s)
        if not m or cur is None or len(s) == 160:      # ==160=旧 pilot f[:160] 截断伪影；>160 的完整长行（v0.4 回填）保留
            continue
        parts = s.split("|")
        if len(parts) < 3:
            continue
        raw = "\n".join(_section_body((DUMP / f"ch{cur[0]:02d}.md")
                                      .read_text(encoding="utf-8", errors="replace").splitlines(), "Draft"))
        clean = _clean(raw)
        worst = max((classify(x.strip(), raw, clean) for x in parts[1:3]),
                    key=_RANK.index)
        agg.setdefault(cur[1], {}).setdefault(worst, 0)
        agg[cur[1]][worst] += 1
    return agg


for log in (Path(__file__).parent / "level3-pilot.console.log",
            Path(__file__).parent / "level3-pilot-v03.console.log",
            Path(__file__).parent / "level3-pilot-v04.console.log",
            Path(__file__).parent / "level3-pilot-v041.console.log",
Path(__file__).parent / "level3-pilot-v042.console.log",
Path(__file__).parent / "level3-pilot-v042-qwen14b.console.log"):
    print(f"\n== {log.name} ==")
    try:
        agg = verify(log)
    except (UnicodeDecodeError, FileNotFoundError) as exc:
        print(f"  [跳过] 日志不可读（在写/编码异常）：{exc.__class__.__name__}")
        continue
    tot = {}
    for grp in ("BAD", "NH", "OK"):
        if grp not in agg:
            continue
        row = agg[grp]
        n = sum(row.values())
        for k, v in row.items():
            tot[k] = tot.get(k, 0) + v
        print(f"  {grp}（{n} 条）：" + " ".join(f"{k}={row.get(k, 0)}" for k in _RANK))
    n = sum(tot.values()) or 1
    keep = tot.get("verbatim", 0) + tot.get("normalized", 0)
    print(f"  合计 {sum(tot.values())} 条｜逐字可核={keep}（{keep / n:.0%}）"
          f"｜微改写={tot.get('paraphrase', 0)}｜拼接={tot.get('stitched', 0)}"
          f"｜疑编造={tot.get('unverifiable', 0)}")
