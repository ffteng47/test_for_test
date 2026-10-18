"""确定性候选检测（第二层）：穿帮从语义判断降维成集合运算。

C 族候选=同 predicate 取值冲突的陈述对。丁批校准口径入码：
- narrator∧narrator、同章同 predicate 不同取值 → 候选（ch12/13/23 钥匙域全真形态）；
- narrator∧dialogue → 仍出候选但打 narrator_dialogue 标签（ch50 锚③定义要求可检出；
  丁批 C 族教训=「台词 vs 物证」多为悬念，**压制权在判分层不在本层**——本层只全量打标）；
- speculation 参与的对 → 打标签出候选（角色猜测不构成矛盾证据，判分层默认降权）。
候选不是定罪：severity 恒 OBS。
"""
from __future__ import annotations

from typing import List, Sequence

from plot_engine.l3.models import ConsistencyCandidate, IntervalFact, Statement


def _pair_tag(a: Statement, b: Statement) -> str:
    pair = sorted([a.epistemic, b.epistemic])
    return f"{pair[0]}_{pair[1]}"


def find_statement_conflicts(statements: Sequence[Statement]) -> List[ConsistencyCandidate]:
    """章内同 predicate 取值两两对照（丁批 C 做法的代码化：逐条摘出再两两对照）。"""
    out: List[ConsistencyCandidate] = []
    by_ch: dict = {}
    for s in statements:
        by_ch.setdefault(s.chapter, []).append(s)
    for ch, ss in by_ch.items():
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)):
                a, b = ss[i], ss[j]
                if a.predicate != b.predicate or a.value == b.value:
                    continue
                # v2 修复②：值守=时点受限 predicate，当晚在场与事后/回忆追述分属不同参照夜，
                # 不可同真冲突（询问/回忆句只作辅证）；narrator 域锚（custody/count）不受此闸。
                if a.predicate == "night_watch" and a.tense != b.tense:
                    continue
                out.append(ConsistencyCandidate(
                    family="C", chapter=ch, rule_id="statement_value_conflict",
                    evidence_refs=[f"{a.line_start}-{a.line_end}", f"{b.line_start}-{b.line_end}"],
                    detail=f"{a.predicate}: 「{a.value}」({a.epistemic}) ↔ 「{b.value}」({b.epistemic})",
                    epistemic_pair=_pair_tag(a, b)))
    return out


def find_interval_conflicts(intervals: Sequence[IntervalFact]) -> List[ConsistencyCandidate]:
    """跨章区间重叠冲突（FactTrack 式）：同 subject+predicate 区间重叠且取值不同。"""
    out: List[ConsistencyCandidate] = []
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            a, b = intervals[i], intervals[j]
            if (a.subject, a.predicate) != (b.subject, b.predicate) or a.object == b.object:
                continue
            a_end = a.valid_until if a.valid_until is not None else 10 ** 9
            b_end = b.valid_until if b.valid_until is not None else 10 ** 9
            if a.valid_from <= b_end and b.valid_from <= a_end:
                out.append(ConsistencyCandidate(
                    family="C", chapter=b.source_chapter, rule_id="interval_overlap_conflict",
                    evidence_refs=[a.evidence_ref, b.evidence_ref],
                    detail=f"{a.predicate}: 「{a.object}」(ch{a.valid_from}起) 与 "
                           f"「{b.object}」(ch{b.valid_from}起) 区间重叠",
                    epistemic_pair="narrator_narrator"))
    return out
