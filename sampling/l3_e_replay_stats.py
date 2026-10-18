# E 族立项读数（批3，零 LLM $0）：语义级场景重演确定性代理的语料命中面。
# 复现：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/l3_e_replay_stats.py > sampling/l3-e-replay-v02.console.log 2>&1
# 出口纪律：E=候选不是定罪（severity OBS）；本批尺面 v0.2 不把 E 接进 run_light（同场景模板语料
# 会让纯话题重叠判别力不足——须加「段间无新事件」事件级闸，留 tff 拍板后再进生产候选流）。
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_engine.metrics import _section_body                    # noqa: E402
from plot_engine.l3.scene_index import build_scene_index, strip_comments  # noqa: E402
from plot_engine.l3.scene_replay import find_scene_replay        # noqa: E402

dump = Path(__file__).resolve().parent / "wpe50ch"
hits, by_ch = [], {}
for md in sorted(dump.glob("ch*.md")):
    ch = int(md.stem[2:])
    body = _section_body(md.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
    lines, _ = strip_comments(body)
    es = find_scene_replay(ch, lines, build_scene_index(ch, body))
    by_ch[ch] = es
    for c in es:
        hits.append(ch)
        print(f"ch{ch:02d} E|{c.evidence_refs}|{c.detail}")

print(f"\nE 命中：{len(hits)}/50 段次，{len(set(hits))} 章 {sorted(set(hits))}")
calib = any(c.evidence_refs == ["1-8", "9-20", "22-30"] for c in by_ch.get(50, []))
print(f"ch50 三段校准（001-008/009-021/022-030）：{'命中' if calib else '未命中'}")
print("判读：语料=同场景（藏宝阁失窃调查）模板，纯话题重叠在多章触发=判别力不足；"
      "E 进生产候选流需补「段间无新事件」事件级闸，读数已呈堂待 tff 裁。")
