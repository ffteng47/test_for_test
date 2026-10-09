"""Day 23-25 Architecture Review 决策单（08 §6 失败分类 / §7 架构冻结闸 / §8 退出条件）。

**只读**：把 `ExperimentReport` 整理成人类 Review 所需的分类 + 闸口判定，
绝不因样本失败而自动改协议/改 HARD/改架构（08 §7 冻结要求，I6）。
是否进 Phase 1 的最终决定权始终在人。§6 分类是**启发式归因辅助**，非自动裁决。
"""
from __future__ import annotations

from typing import Dict, List

from plot_engine.experiment import evaluate_exit_conditions
from plot_engine.models.experiment import ExperimentReport

# 08 §6 结论类
FAILURE_EXTRACTION = "Extraction 问题（06 §4.0）"
FAILURE_WRITER_VALIDATOR = "Writer / Validator 问题"
FAILURE_FACT_ONTOLOGY = "Fact Ontology 问题"
FAILURE_CONTRACT_ARC = "Contract / Arc 问题"
FAILURE_NOT_PHASE0 = "不属于 Phase 0（剧情质量 / LLM 怪句）"
FAILURE_ARCH_BLOCKER = "架构阻断问题（Event 无法 replay）"

_ALL_CLASSES = [FAILURE_EXTRACTION, FAILURE_WRITER_VALIDATOR, FAILURE_FACT_ONTOLOGY,
                FAILURE_CONTRACT_ARC, FAILURE_NOT_PHASE0, FAILURE_ARCH_BLOCKER]

# HARD rule_id → §6 结论类。未在表内的 rule 归 WRITER_VALIDATOR（校验器拦下的产出问题）。
_RULE_CLASS: Dict[str, str] = {
    "H8.1": FAILURE_EXTRACTION, "H8.2": FAILURE_EXTRACTION, "H6.1": FAILURE_EXTRACTION,
    "H6.2": FAILURE_EXTRACTION, "H6.4": FAILURE_EXTRACTION, "H6.5": FAILURE_EXTRACTION,
    "MALFORMED_PROPOSAL": FAILURE_EXTRACTION,
    "H5.1": FAILURE_CONTRACT_ARC, "H5.2": FAILURE_CONTRACT_ARC, "H5.3": FAILURE_CONTRACT_ARC,
    "H5.4": FAILURE_CONTRACT_ARC, "H5.5": FAILURE_CONTRACT_ARC, "H5.6": FAILURE_CONTRACT_ARC,
    "I1": FAILURE_FACT_ONTOLOGY, "R7": FAILURE_FACT_ONTOLOGY,
    "REPLAY_INCONSISTENT": FAILURE_ARCH_BLOCKER,
}


def _class_for_rule(rule_id: str) -> str:
    if rule_id.startswith("H7."):
        return FAILURE_CONTRACT_ARC
    return _RULE_CLASS.get(rule_id, FAILURE_WRITER_VALIDATOR)


def architecture_review(report: ExperimentReport) -> dict:
    """整理 §6 分类计数 + §7 冻结闸 + §8 退出条件为一份可序列化决策单。"""
    classes: Dict[str, dict] = {c: {"count": 0, "rule_ids": []} for c in _ALL_CLASSES}

    def add(cls: str, rule_id: str, n: int) -> None:
        classes[cls]["count"] += n
        if rule_id not in classes[cls]["rule_ids"]:
            classes[cls]["rule_ids"].append(rule_id)

    for rule_id, n in report.hard_violations.items():
        add(_class_for_rule(rule_id), rule_id, n)
    for ch in report.replay_mismatch_chapters:
        add(FAILURE_ARCH_BLOCKER, "REPLAY_INCONSISTENT", 1)

    counts = {c: classes[c]["count"] for c in _ALL_CLASSES}

    # §7 架构冻结闸：任一 G 命中才「允许」讨论改架构（非自动改）。
    g1 = any(v >= 3 for v in counts.values())
    g2 = classes[FAILURE_ARCH_BLOCKER]["count"] >= 1 or report.replay_consistency is False
    g3 = len(report.unresolved_chapters) >= 2
    g4 = (report.canon_contradictions + report.knowledge_contradictions
          + report.timeline_contradictions) > 0
    gate = {
        "G1_same_class_ge_3": g1, "G2_architecture_blocker": g2,
        "G3_ge_2_chapters_uncommitted": g3, "G4_state_inconsistent": g4,
        "may_change_architecture": any([g1, g2, g3, g4]),
    }

    return {
        "experiment_id": report.experiment_id,
        "summary": {
            "generated": report.chapters_generated,
            "committed": report.chapters_committed,
            "unresolved_chapters": report.unresolved_chapters,
            "replay_consistency": report.replay_consistency,
        },
        "failure_classes": classes,
        "freeze_gate": gate,
        "exit_conditions": evaluate_exit_conditions(report),
    }


def render_review_text(sheet: dict) -> str:
    """把决策单渲染成人类可读文本（Review 会上直接用）。"""
    s = sheet["summary"]
    lines = [f"# Architecture Review — {sheet['experiment_id']}",
             f"生成 {s['generated']} / 提交 {s['committed']} / 未决 {s['unresolved_chapters']}"
             f" / replay一致 {s['replay_consistency']}",
             "", "## §6 失败分类"]
    for cls, info in sheet["failure_classes"].items():
        if info["count"]:
            lines.append(f"- {cls}: {info['count']}  ({', '.join(info['rule_ids'])})")
    if not any(i["count"] for i in sheet["failure_classes"].values()):
        lines.append("- （无失败）")
    lines += ["", "## §7 架构冻结闸"]
    g = sheet["freeze_gate"]
    for k in ("G1_same_class_ge_3", "G2_architecture_blocker",
              "G3_ge_2_chapters_uncommitted", "G4_state_inconsistent"):
        lines.append(f"- {k}: {g[k]}")
    lines.append(f"- 可讨论改架构: {g['may_change_architecture']}")
    lines += ["", "## §8 退出条件（Phase 0 → Phase 1）"]
    for k, v in sheet["exit_conditions"].items():
        label = "N/A（06 Revision 未落地）" if v is None else v
        lines.append(f"- {k}: {label}")
    return "\n".join(lines)
