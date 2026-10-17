# 一次性探针（乙批收口用）：核 v0.2/v0.3 两代 console 里 finding 引文的逐字命中率。
# 引文须逐字出自 Draft 正文才算「配对兑现」；打印截断行（≥160 字符）不参与。
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.metrics import _section_body  # noqa: E402

DUMP = Path(__file__).resolve().parent / "wpe50ch"


def hits(log):
    hit = miss = skip = 0
    cur = None
    for ln in Path(log).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^ch(\d+) \[", ln)
        if m:
            cur = int(m.group(1))
            continue
        m = re.match(r"^\s+[ABC]\|", ln)
        if not m or cur is None:
            continue
        s = ln.strip()
        parts = s.split("|")
        if len(s) >= 160 or len(parts) < 3:
            skip += 1
            continue
        lines = (DUMP / f"ch{cur:02d}.md").read_text(encoding="utf-8", errors="replace").splitlines()
        draft = "".join(_section_body(lines, "Draft"))
        if parts[1].strip() in draft and parts[2].strip() in draft:
            hit += 1
        else:
            miss += 1
    return hit, miss, skip


base = Path(__file__).resolve().parent
for log in (base / "level3-pilot.console.log", base / "level3-pilot-v03.console.log"):
    h, m_, s = hits(log)
    rate = f"{h / (h + m_):.0%}" if h + m_ else "-"
    print(f"{log.name}: 逐字命中 {h}/{h + m_}（可核行）= {rate}，截断跳过 {s}")
