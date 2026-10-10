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
    # 派生阶段就判死的章（04 §4.3 ArcConflict）：没跑校验器，只能自己占一个 code。
    "ARC_CONFLICT": FAILURE_CONTRACT_ARC,
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
            # 逐章 `章号:轮数`：聚合值（需修几章 / 最多几轮）盖住了「哪几章」，
            # 而修订烧在哪一章正是 Review 会上要指着说的东西。预格式化字符串保证 sheet 可 JSON 化。
            "revision_rounds_list": " ".join(f"{c}:{v}" for c, v in sorted(report.revision_rounds.items())),
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
        lines = [f"Revision：{rev}", f"逐章轮数：{s['revision_rounds_list']}"]
    else:
        lines = ["Revision：未运行（E3 不可判）"]
    lines = [f"# Architecture Review — {sheet['experiment_id']}",
             f"生成 {s['generated']} / 提交 {s['committed']} / 未决 {s['unresolved_chapters']}"
             f" / replay一致 {s['replay_consistency']}",
             *lines,
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
    from plot_engine.revision_actions import renegotiate_contract
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
                                 "rewrite_scene": rewrite, "rewrite_chapter": rewrite,
                                 "renegotiate_contract": renegotiate_contract(
                                     cfg.arc_contract, created_at=fx.NOW)})
    return run_experiment(cfg, store=store, log=log,
                          chapter_source=fx.build_source(defects, cfg.arc_contract),
                          scene_writer=fx.dummy_writer, revision_loop=loop)


def _proposal_lines(props) -> List[str]:
    return [f"- {p.proposed_event_type} actor={p.actor} target={p.target} "
            f"payload={p.payload}" for p in props] or ["- （无）"]


def _write_chapter_dump(dump_dir, ch: int, rounds, out, trace) -> None:
    """逐章落盘 正文 + 抽取产物 + 判定（08 §10 I3：所有 failure 必须记录）。

    失败章不进 State，事后无从复现；这份快照是唯一能区分
    「Writer 没写出必需事件」与「抽取漏掉了必需事件」的证据。
    `rounds` 是每一轮进 commit 前的 (ctx, 抽取产物)，下标 0 = 第 0 轮。修订会换掉 Draft，
    所以主段渲染**最终**那一轮，第 0 轮另起一段保留——只留最终稿就看不出失败是修订前还是修订后的。
    `contract_version` 一起落盘：重议契约（06 §4.2）是否真的发生过，只能从这里看出来
    ——`ExperimentReport` 的字段是 08 §3 逐字表，不能往里加。
    """
    from pathlib import Path

    d = Path(dump_dir)
    d.mkdir(parents=True, exist_ok=True)
    if not rounds:
        # 契约在本章开工前就判死（04 §4.3）：管道一步没跑，`out` 槽位放的是异常消息。
        (d / f"ch{ch:02d}.md").write_text(
            f"# Chapter {ch} — status=ARC_CONFLICT\nmessage={out}\n", encoding="utf-8")
        return
    ctx, props = rounds[-1]
    if isinstance(out, str):
        # 中途判死的 Arc 章：`out` 槽位同样是异常消息，判定与一致性这一栏还没产出。
        status, message, validation, consistency = "ARC_CONFLICT", out, None, []
    else:
        status, message = out.status, out.message
        validation, consistency = out.validation, out.consistency
    lines = [f"# Chapter {ch} — status={status}",
             f"message={message}",
             f"contract_version={ctx.contract.version} rounds={len(rounds) - 1} "
             f"required_events={sorted(e.event_type for e in ctx.contract.required_events)}",
             ""]
    if trace is not None and trace.steps:
        lines.append("## Revision")
        lines += [f"- round {s.round_no} level={s.root_cause.level} "
                  f"rules={','.join(s.violations) or '—'} action={s.action} "
                  f"committed={s.committed}" for s in trace.steps]
        lines.append("")
    if validation is not None:
        lines.append("## Findings")
        for f in validation.hard_violations:
            lines.append(f"- HARD {f.rule_id}: {f.message}")
        for f in validation.soft_warnings:
            lines.append(f"- SOFT {f.rule_id}: {f.message}")
        for f in validation.observations:
            lines.append(f"- OBS {f.rule_id}: {f.message} | {f.evidence or ''}")
    if consistency:
        lines.append("## Consistency")
        for f in consistency:
            lines.append(f"- {f['severity'].upper()} {f['code']}: {f['detail']}")
    lines.append("")
    lines += ["## Draft", ctx.draft.strip(), "", "## Proposals"]
    lines += _proposal_lines(props)
    if len(rounds) > 1:
        first, first_props = rounds[0]
        lines += ["", f"## Round 0（contract_version={first.contract.version}）",
                  first.draft.strip(), "", "## Round 0 Proposals"]
        lines += _proposal_lines(first_props)
    lines.append("")
    (d / f"ch{ch:02d}.md").write_text("\n".join(lines), encoding="utf-8")


def _live_run(chapters: int, model_config: dict, *, client=None, dump_dir=None,
              told: bool = False):
    """真实模型实验：Writer/抽取换成本地端点，其余管道与离线演练完全一致。

    返回 `(report|None, 端点说明, 抽取诊断)`：端点不可达时不烧预算，实验中途端点失效时
    报告作废并给出一句原因——两种情况都是 `report=None`，绝不半成品出数。
    `client` 可注入，供测试保持零网络。
    `told` 选 Writer 提示词配置（`v1-told` 告知型 / `v0-beats` 基线；基线**不叫盲写**，
    `节拍意图` 会带出事件类型与 fact ID），版本随端点说明落进 run.log
    ——提示词是产品配置不是协议，读数的血缘靠这个标签（`docs/phase0-writer-prompt-ab.md` §2）。
    """
    import dataclasses
    import tempfile
    from pathlib import Path

    from plot_engine.eventlog import EventLog
    from plot_engine.experiment import run_experiment
    from plot_engine.live import (build_client, build_live_source, check_reachable,
                                  extraction_diagnostics)
    from plot_engine.llm import LlmUnavailable
    from plot_engine.llm_writer import make_scene_writer, prompt_version
    from plot_engine.revision import RevisionLoop
    from plot_engine.revision_actions import renegotiate_contract
    from plot_engine.store import StateStore
    from plot_engine.writer import compose_chapter_draft
    from plot_engine.tests.fixtures import experiment_10ch as fx

    client = client or build_client(model_config)
    ok, msg = check_reachable(client)
    if not ok:
        return None, msg, None

    cfg = fx.make_config(chapters)
    tmp = Path(tempfile.mkdtemp(prefix="phase0-live-"))
    store = StateStore(str(tmp / "state.db"))
    log = EventLog(str(tmp / "event.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)

    writer = make_scene_writer(client, told=told)

    def rewrite(ctx):
        asm = compose_chapter_draft(ctx.scene_plan, ctx.contract,
                                    store.load_latest(cfg.story_id).state, writer)
        return dataclasses.replace(ctx, draft=asm.draft)

    loop = RevisionLoop(actions={"rerun_extraction": lambda ctx: ctx,
                                 "rewrite_scene": rewrite, "rewrite_chapter": rewrite,
                                 "renegotiate_contract": renegotiate_contract(
                                     cfg.arc_contract, created_at=fx.NOW)})
    # 逐章契约/场景对**当前** State 派生：Arc 只有一份，约束必须一章一个样（backlog #1）。
    source = build_live_source(client,
                               contracts=lambda ch, cur: fx.contract_for(cfg.arc_contract,
                                                                         ch, cur),
                               plans=fx.plan_for)
    on_chapter = None
    if dump_dir is not None:
        on_chapter = lambda ch, rounds, out, trace: _write_chapter_dump(
            dump_dir, ch, rounds, out, trace)
    report = None
    try:
        report = run_experiment(cfg, store=store, log=log, chapter_source=source,
                                scene_writer=writer, revision_loop=loop, llm_client=client,
                                on_chapter=on_chapter)
    except LlmUnavailable as e:
        # `check_reachable` 只保证开工那一刻通；跑一半挂了（服务器端 llama-server 缺失
        # 就是这样）不能把 traceback 撒在半小时输出后面，也不能假装还有报告。
        where = f"已落盘的逐章快照：{dump_dir}" if dump_dir else "（未传 --dump-dir，逐章快照没落盘）"
        return None, f"模型在实验中途不可用，本报告作废。{where}\n原因：{e}", None
    return report, f"{msg}｜prompt={prompt_version(told)}", extraction_diagnostics(source.channels)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m plot_engine.review",
        description="Phase-0 实验 → 08 §6 失败分类 / §7 冻结闸 / §8 退出条件决策单（只读）")
    ap.add_argument("--chapters", type=int, default=10)
    ap.add_argument("--defect", action="append", default=[], metavar="CH:KIND",
                    help="注入缺陷章，KIND ∈ {leak, dead, no_obs}；可重复。用于验证分类归因是否落对桶")
    ap.add_argument("--live", action="store_true",
                    help="用真实模型（默认本机 Ollama）跑实验；换 vLLM 只改 --model-config")
    ap.add_argument("--model-config", metavar="JSON", default=None,
                    help='模型路由 JSON 或 @文件路径，例：{"writer":{"base_url":"http://<host>:8000/v1","model":"qwen2.5-14b"}}')
    ap.add_argument("--dump-dir", metavar="DIR", default=None,
                    help="逐章落盘 正文/抽取产物/判定，供失败归因（08 §10 I3）；仅 --live 生效")
    ap.add_argument("--prompt", choices=("beats", "told"), default="beats",
                    help="Writer 提示词配置：beats=v0-beats 基线（无汇总行，但 节拍意图 仍带类型与 fact ID），"
                         "told=v1-told 追加本章 must_change 目标与必需事件类型（不给禁条，"
                         "docs/phase0-writer-prompt-ab.md §3）；仅 --live 生效")
    args = ap.parse_args(argv)

    import sys
    if hasattr(sys.stdout, "reconfigure"):        # Windows GBK 控制台下中文不乱码
        sys.stdout.reconfigure(encoding="utf-8")

    defects: Dict[int, str] = {}
    for spec in args.defect:
        ch, _, kind = spec.partition(":")
        if kind not in ("leak", "dead", "no_obs"):
            ap.error(f"--defect {spec!r}: KIND 必须是 leak|dead|no_obs")
        try:
            defects[int(ch)] = kind
        except ValueError:
            ap.error(f"--defect {spec!r}: CH 必须是整数")

    if args.live:
        report, msg, diag = _live_run(args.chapters, _read_model_config(args.model_config),
                                      dump_dir=args.dump_dir, told=args.prompt == "told")
        print(msg)
        if report is None:
            return 2
        print(f"tokens={report.total_tokens} cost=${report.total_cost_usd:.4f} "
              f"用时={report.total_duration_ms / 1000:.0f}s｜"
              f"抽取产出 {diag['proposals']} 条 / 坏料 {diag['malformed'] or '无'}")
        print(render_review_text(architecture_review(report)))
        return 0

    print(render_review_text(architecture_review(_offline_dry_run(args.chapters, defects))))
    return 0


def _read_model_config(spec: Optional[str]) -> dict:
    """`--model-config` 接受内联 JSON 或 @path.json；空 → 本地默认路由。"""
    import json
    from pathlib import Path

    if not spec:
        return {}
    raw = Path(spec[1:]).read_text(encoding="utf-8") if spec.startswith("@") else spec
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("--model-config 必须是 {role: {字段覆盖}} 的 JSON 对象")
    return loaded


if __name__ == "__main__":
    raise SystemExit(main())
