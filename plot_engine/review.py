"""Day 23-25 Architecture Review 决策单（08 §6 失败分类 / §7 架构冻结闸 / §8 退出条件）。

**只读**：把 `ExperimentReport` 整理成人类 Review 所需的分类 + 闸口判定，
绝不因样本失败而自动改协议/改 HARD/改架构（08 §7 冻结要求，I6）。
是否进 Phase 1 的最终决定权始终在人。§6 分类是**启发式归因辅助**，非自动裁决。
`python -m plot_engine.review` 是离线演练入口：临时目录里跑确定性夹具，同样不写仓库状态。
"""
from __future__ import annotations

from typing import Dict, List, Optional

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
            "revision_chapters_needed": sum(1 for v in report.revision_rounds.values() if v),
            "revision_max_rounds": max(report.revision_rounds.values(), default=0),
            "revision_success_rate": report.revision_success_rate,
            "revision_ran": len(report.revision_rounds) == report.chapters_generated
            and report.chapters_generated > 0,
        },
        "failure_classes": classes,
        "freeze_gate": gate,
        "exit_conditions": evaluate_exit_conditions(report),
    }


def render_review_text(sheet: dict) -> str:
    """把决策单渲染成人类可读文本（Review 会上直接用）。"""
    s = sheet["summary"]
    if s["revision_ran"]:
        rev = (f"需修 {s['revision_chapters_needed']} 章 / 最多 {s['revision_max_rounds']} 轮"
               f" / 修复率 {s['revision_success_rate']:.2f}")
    else:
        rev = "未运行（E3 不可判）"
    lines = [f"# Architecture Review — {sheet['experiment_id']}",
             f"生成 {s['generated']} / 提交 {s['committed']} / 未决 {s['unresolved_chapters']}"
             f" / replay一致 {s['replay_consistency']}",
             f"Revision：{rev}",
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


def _offline_dry_run(chapters: int, defects: Dict[int, str]) -> ExperimentReport:
    """离线演练：用确定性夹具源充当 Writer/抽取模型，走完整管道产出 Report（网络无关）。

    夹具在 `plot_engine/tests/fixtures/`（测试与开发命令共用同一份 arc 定义，避免二套假数据）。
    store/log 落在临时目录，不污染仓库。
    带上 06 Revision 循环，但夹具 Writer 是确定性的 → 重写只会得到同一份 Draft，
    因此本演练只证明「阶梯/预算/振荡/trace」机制在跑；真实收敛率与 E3' 需接真实 Writer。
    """
    import dataclasses
    import sys
    import tempfile
    from pathlib import Path

    from plot_engine.eventlog import EventLog
    from plot_engine.experiment import run_experiment
    from plot_engine.revision import RevisionLoop
    from plot_engine.store import StateStore
    from plot_engine.writer import compose_chapter_draft

    fixtures = Path(__file__).parent / "tests" / "fixtures"
    sys.path.insert(0, str(fixtures))
    import experiment_10ch as fx

    cfg = fx.make_config(chapters)
    tmp = Path(tempfile.mkdtemp(prefix="phase0-"))
    store = StateStore(str(tmp / "state.db"))
    log = EventLog(str(tmp / "event.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)

    def rewrite(ctx):
        asm = compose_chapter_draft(ctx.scene_plan, ctx.contract,
                                    store.load_latest(cfg.story_id).state, fx.dummy_writer)
        return dataclasses.replace(ctx, draft=asm.draft)

    loop = RevisionLoop(actions={"rerun_extraction": lambda ctx: ctx,
                                 "rewrite_scene": rewrite, "rewrite_chapter": rewrite})
    return run_experiment(cfg, store=store, log=log,
                          chapter_source=fx.build_source(defects),
                          scene_writer=fx.dummy_writer, revision_loop=loop)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m plot_engine.review",
        description="Phase-0 离线实验 → 08 §6 失败分类 / §7 冻结闸 / §8 退出条件决策单（只读）")
    ap.add_argument("--chapters", type=int, default=10)
    ap.add_argument("--defect", action="append", default=[], metavar="CH:KIND",
                    help="注入缺陷章，KIND ∈ {leak, dead}；可重复。用于验证分类归因是否落对桶")
    args = ap.parse_args(argv)

    import sys
    if hasattr(sys.stdout, "reconfigure"):        # Windows GBK 控制台下中文不乱码
        sys.stdout.reconfigure(encoding="utf-8")

    defects: Dict[int, str] = {}
    for spec in args.defect:
        ch, _, kind = spec.partition(":")
        if kind not in ("leak", "dead"):
            ap.error(f"--defect {spec!r}: KIND 必须是 leak|dead")
        try:
            defects[int(ch)] = kind
        except ValueError:
            ap.error(f"--defect {spec!r}: CH 必须是整数")

    print(render_review_text(architecture_review(_offline_dry_run(args.chapters, defects))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
