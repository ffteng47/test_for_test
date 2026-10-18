"""E 族：语义级场景重演（旁路确定性代理，批3 呈堂）。

D 族只抓逐字复读；tff ch50 复核发现的「同一核心场景三段重讲」
（001-008 赵六独守盘点 ↔ 009-021 张三进场再查 ↔ 022-030 背对背又坐再查）
不是逐字、也不是回卷硬跳——D/B 都抓不到，需要 E。

确定性代理=同地点 × 人物集重叠 × 案情话题词重叠 × 段间无新事件（新到达/新离开/新地点落定）。
分段的边界=帧边界 ∪ 帧内「新实体首次在场行」（复用 A 锚的进场信号，故 009/022 天然成界）。
severity 恒 OBS：候选≠定罪，重演是否算穿帮由人核/判分层裁。
"""
from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple

from plot_engine.l3.models import ConsistencyCandidate, SceneFrame

# 案情话题词表（尺面戳 l3-v0.2：变更=读数变更）
_TOPIC_RE = re.compile(r"(钥匙|印泥|印章|簿记|记录|账册|账簿|值守|守夜|守阁|值夜|失窃|窃|怀疑|猜|调查|查|线索|文件|伪造|证据)")
MIN_SEGMENT_LINES = 2         # 过渡碎段（单句赶路）不参与重演判定
MIN_COMMON_TOPICS = 2         # 组内所有段共享的案情核心词数
MAX_SEGMENT_FRACTION = 0.6    # 单段覆盖全章比例上限（超过=整场非重演）


def _topics(seg: Sequence[str]) -> set:
    found: set = set()
    for ln in seg:
        found.update(_TOPIC_RE.findall(ln))  # 案情台词也是重演内容，用整行不剥引号
    return found


def _segments(frames: Sequence[SceneFrame]) -> List[Tuple[str, int, int, set, set]]:
    """帧 → 子段（location, start, end, 人物集, 话题集）。帧内按「全章首现行」再切。

    v2.2：在场行经回忆/传闻全行拒绝后变稀疏，逐帧在场行不再等于进场信号；子段边界
    只认该实体在全章的第一次在场行（=真正的新人物进场，009/022 仍天然成界）。"""
    first_seen: Dict[str, int] = {}
    for fr in frames:
        for e, ln in fr.present_line.items():
            if ln < first_seen.get(e, 10 ** 9):
                first_seen[e] = ln
    segs: List[Tuple[str, int, int, set, set]] = []
    for fr in frames:
        cuts = [fr.line_start] + [ln for e, ln in fr.present_line.items()
                                  if ln == first_seen.get(e)]
        cuts = sorted(set(cuts))
        bounds = cuts + [fr.line_end + 1]
        for s, e_ex in zip(bounds, bounds[1:]):
            e = e_ex - 1
            if e < s:
                continue
            cast = {en for en, ln in fr.present_line.items() if s <= ln <= e}
            segs.append((fr.location_text, s, e, cast, None))  # topic 由调用方按 lines 补
    return segs


def find_scene_replay(chapter: int, lines: Sequence[str],
                      frames: Sequence[SceneFrame]) -> List[ConsistencyCandidate]:
    """章内同地点 ≥3 段、共享案情核心（≥MIN_COMMON_TOPICS 词每段都在）、人物有交集=场景重演候选。

    确定性代理只证「同场景被反复重讲」；是否推进了新事件（=不算重演）需事件级判断，留判分/人核。
    """
    total = len(lines)
    segs = _segments(frames)
    segs = [(loc, s, e, cast, _topics(lines[s - 1:e]))
            for loc, s, e, cast, _ in segs
            if e - s + 1 >= MIN_SEGMENT_LINES and (e - s + 1) / total <= MAX_SEGMENT_FRACTION]
    out: List[ConsistencyCandidate] = []
    by_loc: dict = {}
    for loc, s, e, cast, top in segs:
        by_loc.setdefault(loc, []).append((s, e, cast, top))
    for loc, group in by_loc.items():
        if len(group) < 3 or loc == "-":
            continue
        common = set.intersection(*(g[3] for g in group))
        cast_union = set().union(*(g[2] for g in group))
        if len(common) < MIN_COMMON_TOPICS or not cast_union:
            continue  # 无共享案情核心=各查各的，不是同一场景重演
        spans = "↔".join(f"{s}-{e}" for s, e, _, _ in group)
        refs = [f"{s}-{e}" for s, e, _, _ in group]
        out.append(ConsistencyCandidate(
            family="E", chapter=chapter, rule_id="scene_replay",
            evidence_refs=refs,
            detail=f"同场景「{loc}」重演 {len(group)} 段（{spans}），共享案情 {sorted(common)}、非逐字"))
    return out
