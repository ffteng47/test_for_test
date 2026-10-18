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
    """A：实体在非开场首行首次在场（叙述行口径），且此前无到达记录。

    v2 修复②：章首豁免收窄到「场景0 首行在场=开场设定」，实体在场景0 内后段凭空
    出现（ch50 锚①赵六独守→第9行张三在场）照算 A；在场取首次叙述行号=证据行。"""
    out: List[ConsistencyCandidate] = []
    seen: set = set()
    arrived_before: Dict[str, int] = {}
    for fr in frames:
        for e in fr.arrived:
            arrived_before.setdefault(e, fr.scene_seq)
        for e, pline in sorted(fr.present_line.items(), key=lambda kv: kv[1]):
            if e in seen:
                continue
            seen.add(e)
            if fr.scene_seq == 0 and pline == fr.line_start:
                continue  # 章首豁免：开场首行在场=场景设定
            if e not in arrived_before:
                out.append(ConsistencyCandidate(
                    family="A", chapter=fr.chapter, rule_id="entry_without_source",
                    evidence_refs=[f"{pline}-{pline}"],
                    detail=f"{e} 在场景{fr.scene_seq}（{fr.location_text}）第{pline}行"
                           f"首次在场，此前无到达叙述"))
    return out


def find_skydrop_arrivals(frames: Sequence[SceneFrame]) -> List[ConsistencyCandidate]:
    """B-空降（v0.3 中批后续，pack §7.18 tff 亲裁 ch08-B=真穿帮「位移蒸发」）：

    主体被**位移叙述明确落到**某地（prev 帧 arrived_move），随后一帧只在门窗口出现
    （arrived 但不在 arrived_move）=位移蒸发。门窗口支由「全消解」降为「条件消解」——
    推开的门只证明门动了，不证明人怎么到的这里。
    落定锚取 prev 帧强到达（非「prev 帧在场」）：这是 §7.16 的判据入码——同为门+推开，
    ch08-B 判真（前一行「来到了山下的一家小酒馆」把人落到别处）、ch14/21/22/26/35/42/48-B
    判误（前一行只写开门/移动意图，人从未被落到另一地点）。"""
    out: List[ConsistencyCandidate] = []
    landed: Dict[str, SceneFrame] = {}   # 实体 → 最近一次「被位移叙述落到」的帧
    for fr in frames:
        weak = [e for e in fr.arrived if e not in fr.arrived_move]
        for e in fr.arrived_move:
            landed[e] = fr               # 落定锚刷新（含本帧，之后失效）
        for e in weak:
            prev = landed.get(e)
            if prev is not None and prev.location_text != fr.location_text:
                out.append(ConsistencyCandidate(
                    family="B", chapter=fr.chapter, rule_id="skydrop_arrival",
                    evidence_refs=[f"{prev.line_start}-{prev.line_end}",
                                   f"{fr.line_start}-{fr.line_end}"],
                    detail=f"{e} 场景{prev.scene_seq}由位移叙述落到{prev.location_text}，场景{fr.scene_seq}"
                           f"仅有门窗口到达入{fr.location_text}，中间无位移叙述 [工件标注:空降到达]"))
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
