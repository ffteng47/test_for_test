"""硬指标分类器：把 Commit/consistency/replay 产物映射到 08 §4 九项桶。

只做**计数与归类**，不改判据（08 I2：实验期不得修改 HARD 规则）。
未知 rule_id 兜底归 CANON，但仍单记 `by_rule`，绝不静默丢弃（05 §9 I6）。
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional

from plot_engine.models.commit import CommitOutcome
from plot_engine.models.experiment import RULE_TO_METRIC, HardMetric


@dataclasses.dataclass
class MetricCounts:
    by_metric: Dict[HardMetric, int] = dataclasses.field(
        default_factory=lambda: {m: 0 for m in HardMetric})
    by_rule: Dict[str, int] = dataclasses.field(default_factory=dict)


def classify_outcome(outcome: CommitOutcome, *, consistency: Optional[List[dict]] = None,
                     replay_ok: Optional[bool] = None) -> MetricCounts:
    mc = MetricCounts()

    def add(rule_id: str) -> None:
        mc.by_rule[rule_id] = mc.by_rule.get(rule_id, 0) + 1
        bucket = RULE_TO_METRIC.get(rule_id)
        if bucket is None and rule_id.startswith("H8."):
            # 08 §4 那九项是**故事状态**的账，没有一项量「抽取可信度」⇒ H8.x 只记 by_rule。
            # 兜底进 CANON 会让 §8 E6 与 G4 因为一次漏抽而判成状态不一致（backlog #3）。
            # 抽取失败照样在 06 §4.0 的 Extraction 类里可见，桶外不等于不可见。
            return
        mc.by_metric[bucket or HardMetric.CANON] += 1

    if outcome.validation is not None:
        for f in outcome.validation.hard_violations:
            add(f.rule_id)

    for c in consistency or []:
        if c.get("severity") == "hard":
            add(c["code"])

    if outcome.status == "REPLAY_INCONSISTENT":
        mc.by_metric[HardMetric.REPLAY] += 1
        mc.by_rule["REPLAY_INCONSISTENT"] = mc.by_rule.get("REPLAY_INCONSISTENT", 0) + 1
    if replay_ok is False:
        mc.by_metric[HardMetric.REPLAY] += 1
        mc.by_rule["REPLAY_INCONSISTENT"] = mc.by_rule.get("REPLAY_INCONSISTENT", 0) + 1

    return mc


def to_report_fields(mc: MetricCounts) -> dict:
    """映射到 ExperimentReport 命名字段；`hard_violations` 按 rule_id 确定性排序。"""
    return {
        "canon_contradictions": mc.by_metric[HardMetric.CANON],
        "knowledge_contradictions": mc.by_metric[HardMetric.KNOWLEDGE],
        "timeline_contradictions": mc.by_metric[HardMetric.TIMELINE],
        "hard_violations": {k: mc.by_rule[k] for k in sorted(mc.by_rule)},
    }


def consistency_counts(findings: List[dict]) -> Dict[str, int]:
    """committed 状态的设定/知识/时序矛盾计数（08 §4 三项命名指标）。

    只统计 `assert_consistent` 的 HARD finding；被拒章的沙盒不一致不在此列——
    它们的失败信号已由 `validate` 的 rule_id 计入 `hard_violations`，不该反向拉低 §8 E6。
    """
    acc = {"canon": 0, "knowledge": 0, "timeline": 0}
    bucket_to_key = {HardMetric.CANON: "canon", HardMetric.KNOWLEDGE: "knowledge",
                     HardMetric.TIMELINE: "timeline"}
    for f in findings:
        if f.get("severity") != "hard":
            continue
        # 未映射 code 兜底 CANON，与 classify_outcome 同口径：I2/I6 这类不进九项的硬矛盾
        # 一旦被丢掉，§8 E6 会因为「看不见」而判过。
        key = bucket_to_key.get(RULE_TO_METRIC.get(f["code"], HardMetric.CANON))
        if key:
            acc[key] += 1
    return acc
