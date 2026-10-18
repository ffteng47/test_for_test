"""位置/时序硬检查（第二层，确定性）：A 进场无源 + B 空间回卷。

丁批校准口径入码：
- 章首场景（scene_seq=0）=开场设定，A 族豁免（误报 5 中 3 的教训）；
- 硬离开才计 departed，「准备离开」意图不计（ch20 #22 误报教训）；
- 有到达叙述即消解（ch06/14/21 误报面：到达叙述被误引为无到达证据）；
- 离开→同场景再现之间无任何到达=B 候选（最早可达检查的最小实现，不做全 TCSP）。
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from plot_engine.l3.models import ConsistencyCandidate, SceneFrame


def find_entry_without_source(frames: Sequence[SceneFrame]) -> List[ConsistencyCandidate]:
    """A：实体在非章首场景首次在场，且此前无到达记录、此前各场景均未在场。"""
    out: List[ConsistencyCandidate] = []
    seen: Dict[str, int] = {}
    arrived_before: Dict[str, int] = {}
    for fr in frames:
        for e in fr.arrived:
            arrived_before.setdefault(e, fr.scene_seq)
        for e in fr.present:
            if fr.scene_seq == 0:
                seen.setdefault(e, fr.scene_seq)  # 章首豁免：开场在场=场景设定
                continue
            if e not in seen and e not in arrived_before:
                out.append(ConsistencyCandidate(
                    family="A", chapter=fr.chapter, rule_id="entry_without_source",
                    evidence_refs=[f"{fr.line_start}-{fr.line_end}"],
                    detail=f"{e} 在场景{fr.scene_seq}（{fr.location_text}）首次在场，"
                           f"此前无到达叙述"))
            seen.setdefault(e, fr.scene_seq)
    return out


def find_space_rewind(frames: Sequence[SceneFrame]) -> List[ConsistencyCandidate]:
    """B：实体硬离开后又在同地点在场，中间无到达叙述。"""
    out: List[ConsistencyCandidate] = []
    open_dep: Dict[str, SceneFrame] = {}
    for fr in frames:
        for e in fr.arrived:
            open_dep.pop(e, None)  # 到达消解
        for e in fr.present:
            prev = open_dep.get(e)
            if prev is not None and fr.location_text == prev.location_text:
                out.append(ConsistencyCandidate(
                    family="B", chapter=fr.chapter, rule_id="space_rewind",
                    evidence_refs=[f"{prev.line_start}-{prev.line_end}",
                                   f"{fr.line_start}-{fr.line_end}"],
                    detail=f"{e} 场景{prev.scene_seq}离开{prev.location_text}，"
                           f"场景{fr.scene_seq}又在原地互动，中间无到达"))
                open_dep.pop(e, None)
        for e in fr.departed:
            open_dep[e] = fr
    return out
