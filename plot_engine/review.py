"""Day 23-25 Architecture Review 决策单（08 §6 失败分类 / §7 架构冻结闸 / §8 退出条件）。

**只读**：把 `ExperimentReport` 整理成人类 Review 所需的分类 + 闸口判定，
绝不因样本失败而自动改协议/改 HARD/改架构（08 §7 冻结要求，I6）。
是否进 Phase 1 的最终决定权始终在人。§6 分类是**启发式归因辅助**，非自动裁决。
`python -m plot_engine.review` 是离线演练入口：临时目录里跑确定性夹具，同样不写仓库状态。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from plot_engine.experiment import evaluate_exit_conditions
from plot_engine.llm_writer import ARMS
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


# 指引文本的刻度号（与 `EXTRACTION_RULER` 同族）：FIX_GUIDE 也是尺面文本——它喂给修订环/写手，
# 改任何一条措辞都可能改变读数。g2 = 补上 SUSPECTS 写法判据（E18：漏讲导致 ch07 按指引改不出）。
# 历史 run.log 没有这一栏 ⇒ 无指引戳的跑法一律算 g1（H5.1 缺 SUSPECTS 的那版）。
GUIDE_VERSION = "g2-suspects-added"
FIX_GUIDE: Dict[str, str] = {
    "H1.1": "死人不能行动：把这条行动换成在场活人来做，或先写清楚他其实还没死",
    "I7": "同 H1.1（可见性一致性）：已死角色不能是事件 actor",
    "H2.2": "该角色本章没拿到这条知识：补一场他亲眼看到 / 读到 / 被告知该事实的戏",
    "H5.1": "缺一个必需类型的事件，把它写成看得见的动作——INFERS=由已知证据推出结论；"
            "READS=读到写着的文字；IS_TOLD=有人当面告知；OBSERVES=在场亲眼注意到；"
            "BELIEVES=内心确认某事；SUSPECTS=起疑并把嫌疑指向某人/某事（介于怀疑与确认之间的中间态）；"
            "DOUBTS=明确起疑",
    "H5.3": "must_change 没实现：让那个字段真被对应动作改掉——"
            "belief→Believes/Suspects/Doubts，knowledge→Observes/Reads/Is_told/Infers",
    "H5.4": "must_not_change 被动了：本章别让那个字段发生任何变化",
    "H5.6": "这条允许的知识还没建立：要让读者知道就补一个来源场景（不强制）",
    "H5.7": "禁止知识被整批揭示：删掉这段揭示，或改成角色尚不知情",
    # 首次救援实跑（t8r3 ch09）踩到的：前三轮机器写手都自动带上尾部标注，人给的稿子没有 ⇒ H5.5 落空。
    "H5.5": "章尾补一行机器标注 `<!-- hook: 类型 strength=0-1000 -->`，类型取上一行括号里"
            "「期望 ending.type=」的那个值（机器写手会自动带，人改稿最容易漏这条）",
}
_EXTRACT_BLIND = ("INFERS", "BELIEVES")   # T8 铲 1 认定的跨模型漏抽类型


def _fix_guide_lines(final_status: str, validation) -> List[str]:
    """路由给人的章要附「改哪里」，只给 rule_id 的那半程是人替机器读协议。

    抽取洞（T8 铲 1：`INFERS`/`BELIEVES` 跨模型漏抽）修好之前，照指引改完仍可能被打回，
    所以那条 caveat 一起给——否则人会把尺的毛病当自己稿子的问题。
    每条都带上判定原文：`H5.5` 要的类型、`H5.1` 缺的事件都写在那行里，人不必回头翻协议。
    """
    if final_status != "NEEDS_HUMAN" or validation is None or not validation.hard_violations:
        return []
    hard = validation.hard_violations
    lines = ["", "## 修稿指引"]
    lines += [f"- {f.rule_id}｜{f.message} ⇒ {FIX_GUIDE[f.rule_id]}"
              for f in hard if f.rule_id in FIX_GUIDE]
    if len(lines) == 2:
        return []
    if any(t in f.message for f in hard for t in _EXTRACT_BLIND):
        lines.append("- 注意：本尺对 INFERS/BELIEVES 有已知漏抽（docs/phase1-t8-variant-r1-32b.md §6），"
                     "照上面改完仍可能判未满足，那不是稿子的错")
    return lines


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
    # 人工终态只存在于 trace 上：`status=` 是 outcome 的 07 §4.1 枚举（没有 NEEDS_HUMAN），
    # 从它数「要不要人接」会把已路由的章读成 0 次（Phase 0 的读错）。
    # trace 缺席只有两种：中途判死的 Arc 章（没有终态可言，退回 status 本身）
    # 和调用方没传 trace 的离线核对。
    final_status = getattr(trace, "final_status", None) or status
    lines = [f"# Chapter {ch} — status={status}",
             f"trace_status={final_status}",
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
    lines += _fix_guide_lines(final_status, validation)
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
              arm: str = "beats", state_dir: Optional[str] = None,
              fail_stop: bool = False):
    """真实模型实验：Writer/抽取换成本地端点，其余管道与离线演练完全一致。

    返回 `(report|None, 端点说明, 抽取诊断)`：端点不可达时不烧预算，实验中途端点失效时
    报告作废并给出一句原因——两种情况都是 `report=None`，绝不半成品出数。
    `client` 可注入，供测试保持零网络。
    `arm` 选 Writer 提示词配置（`docs/phase0-final-report-and-v3-config-ab.md` §10.2）：
    `stripped`=臂 A（节拍行抹掉类型名与 ID，第一次真盲写）、`told`=臂 B（裸 ID 汇总两行，
    渲染与 t1–t3 逐字节一致）、`persona`=臂 C（臂 B + 角色一致性规则）；基线 `beats` 留作金丝雀。
    提示词是产品配置不是协议，只有臂 A/B/C 的渲染过滤器不动尺，版本随端点说明落进 run.log。
    `state_dir` 给定时 State/EventLog 落在那儿（默认临时目录、跑完即弃）——
    **跨进程救援（`--rescue`）要求链还在盘上**，所以采样跑法恒带这个参数。
    救援本身不在这里跑：`main()` 拒绝 `--live --rescue` 同命令，人工重入是测量之后的独立一步。
    """
    import dataclasses
    import tempfile

    from pathlib import Path

    from plot_engine.eventlog import EventLog
    from plot_engine.experiment import run_experiment
    from plot_engine.live import (build_client, build_live_source, check_reachable,
                                  extraction_diagnostics)
    from plot_engine.llm import LlmUnavailable
    from plot_engine.llm_extract import EXTRACTION_RULER
    from plot_engine.llm_writer import WRITER_SURFACE, make_scene_writer, prompt_version
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
    tmp = Path(state_dir) if state_dir else Path(tempfile.mkdtemp(prefix="phase0-live-"))
    tmp.mkdir(parents=True, exist_ok=True)
    if (tmp / "state.db").exists():
        # 已有链上再跑一批 = 章号重复、CAS 从链尾起算，两份读数会混进同一条账。
        return None, f"--state-dir {tmp} 里已经有一条链：换目录或先清掉，两批实验不并成一条账", None
    store = StateStore(str(tmp / "state.db"))
    log = EventLog(str(tmp / "event.db"))
    store.init_genesis(cfg.story_id, cfg.initial_state)

    writer = make_scene_writer(client, arm=arm)

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
                                on_chapter=on_chapter, stop_on_unresolved=fail_stop)
    except LlmUnavailable as e:
        # `check_reachable` 只保证开工那一刻通；跑一半挂了（服务器端 llama-server 缺失
        # 就是这样）不能把 traceback 撒在半小时输出后面，也不能假装还有报告。
        where = f"已落盘的逐章快照：{dump_dir}" if dump_dir else "（未传 --dump-dir，逐章快照没落盘）"
        return None, f"模型在实验中途不可用，本报告作废。{where}\n原因：{e}", None
    note = (f"{msg}｜prompt={prompt_version(arm)}｜抽取尺={EXTRACTION_RULER}"
            f"｜指引={GUIDE_VERSION}｜夹具={fx.LADDER_VERSION}｜Writer面={WRITER_SURFACE}")
    cap = getattr(client, "router", None)
    if cap is not None and "extract" in cap.endpoints:
        note += f"｜抽取上限={cap.endpoints['extract'].max_tokens}"
    if fail_stop and report.unresolved_chapters:
        note += f"｜停在第 {report.unresolved_chapters[-1]} 章（P2 语义，分母 = 停前生成章数）"
    if dump_dir is not None:
        note += "｜终态 " + " ".join(f"{k}={v}" for k, v in sorted(count_dispositions(dump_dir).items()))
    diag = extraction_diagnostics(source.channels)
    diag["calls"] = getattr(client, "render_call_diagnostics", lambda: "")()
    return report, note, diag


def count_dispositions(dump_dir) -> Dict[str, int]:
    """从逐章快照数**终态分布**——人工处置率的唯一可数来源。
    `status=` 是 outcome 的 CommitStatus（07 §4.1 没有 NEEDS_HUMAN 这个值），
    只有第二行的 `trace_status=` 分得出「烧完预算判死」和「已路由给人」；
    报告（08 §3 逐字表）不许加字段，所以这一列只能从落盘的快照读回来。
    契约开工前就判死的章一步没跑 ⇒ 没有 trace，退回首行的 `status=ARC_CONFLICT`。"""
    import re
    from pathlib import Path

    out: Dict[str, int] = {}
    for p in sorted(Path(dump_dir).glob("ch*.md")):
        lines = p.read_text(encoding="utf-8").splitlines()
        value = next((ln.split("=", 1)[1] for ln in lines[:3]
                      if ln.startswith("trace_status=")), None)
        if value is None:
            value = (re.search(r"status=(\w+)", lines[0]).group(1) if lines else "—")
        out[value] = out.get(value, 0) + 1
    return out


def _rescue_batch(store, log, cfg, client, specs: List[str]) -> List[str]:
    """逐章走 T1b 闭环（`rescue_chapter`）：一次提交、不跑修订、判据不重议。
    抽取仍走真模型——人改的是正文，不是替模型抽事件。
    链尾守卫在 `rescue_chapter` 里 raise，这里逐条兜住：一条坏 spec 不带走其余。
    """
    from pathlib import Path

    from plot_engine.llm_extract import EXTRACTION_RULER, make_llm_channel
    from plot_engine.rescue import rescue_chapter
    from plot_engine.tests.fixtures import experiment_10ch as fx

    lines = []
    for spec in specs:
        ch_s, _, path = spec.partition(":")
        try:
            ch = int(ch_s)
            draft = Path(path).read_text(encoding="utf-8")
        except (ValueError, OSError) as e:
            lines.append(f"--rescue {spec!r} 读不进：{e}")
            continue
        cur = store.load_latest(cfg.story_id).state
        try:
            contract = fx.contract_for(cfg.arc_contract, ch, cur)
            res = rescue_chapter(store, log, cfg.story_id, contract,
                                 scene_plan=fx.plan_for(contract, cur), draft=draft,
                                 llm_channel=make_llm_channel(client))
        except ValueError as e:
            lines.append(f"第 {ch} 章 rescue=SKIP｜{e}")
            continue
        lines.append(f"第 {ch} 章 rescue={res.status} version={res.new_version}"
                     + ("" if res.status == "OK" else f"｜{res.message}"))
    return lines


def _rescue_run(state_dir: str, model_config: dict, specs: List[str], *, client=None) -> List[str]:
    """`--rescue` 的独立入口：不跑实验，只对盘上那条链做人工重入（要求 --state-dir）。"""
    from pathlib import Path

    from plot_engine.eventlog import EventLog
    from plot_engine.live import build_client, check_reachable
    from plot_engine.store import StateStore
    from plot_engine.tests.fixtures import experiment_10ch as fx

    client = client or build_client(model_config)
    ok, msg = check_reachable(client)
    if not ok:
        return [msg]
    cfg = fx.make_config(10)
    return _rescue_batch(StateStore(str(Path(state_dir) / "state.db")),
                         EventLog(str(Path(state_dir) / "event.db")), cfg, client, specs)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m plot_engine.review",
        description="Phase-0 实验 → 08 §6 失败分类 / §7 冻结闸 / §8 退出条件决策单（只读）")
    ap.add_argument("--chapters", type=int, default=10)
    ap.add_argument("--defect", action="append", default=[], metavar="CH:KIND",
                    help="注入缺陷章，KIND ∈ {leak, dead, no_nail}；可重复。用于验证分类归因是否落对桶")
    ap.add_argument("--live", action="store_true",
                    help="用真实模型（默认本机 Ollama）跑实验；换 vLLM 只改 --model-config")
    ap.add_argument("--model-config", metavar="JSON", default=None,
                    help='模型路由 JSON 或 @文件路径，例：{"writer":{"base_url":"http://<host>:8000/v1","model":"qwen2.5-14b"}}')
    ap.add_argument("--dump-dir", metavar="DIR", default=None,
                    help="逐章落盘 正文/抽取产物/判定，供失败归因（08 §10 I3）；仅 --live 生效")
    ap.add_argument("--state-dir", metavar="DIR", default=None,
                    help="State/EventLog 落盘目录（不给则临时目录、跑完即弃）；"
                         "采样跑法恒给，否则事后没有可救援的链")
    ap.add_argument("--rescue", action="append", default=[], metavar="CH:FILE",
                    help="人工改后稿重入（Phase 1 T1b）：FILE 是改后正文，CH 必须是链尾章。"
                         "只提交一次、不跑修订、不重议判据；要求 --state-dir")
    ap.add_argument("--fail-stop", action="store_true",
                    help="产品语义（裁定 P2）：任一章判死/待人工就停整条链，后面的章不再生成。"
                         "默认关＝测量语义（十章分布）。两者 E2 分母不同，不可同表并列")
    ap.add_argument("--prompt", choices=ARMS, default="beats",
                    help="Writer 提示词臂（docs/phase0-final-report-and-v3-config-ab.md §10.2）："
                         "beats=v0-beats 基线金丝雀；stripped=臂 A 节拍行抹掉类型名与 ID；"
                         "told=臂 B 追加 must_change 目标与必需事件类型（裸 ID，不给禁条）；"
                         "persona=臂 C = 臂 B + 角色一致性规则；仅 --live 生效")
    args = ap.parse_args(argv)

    import sys
    if hasattr(sys.stdout, "reconfigure"):        # Windows GBK 控制台下中文不乱码
        sys.stdout.reconfigure(encoding="utf-8")

    defects: Dict[int, str] = {}
    for spec in args.defect:
        ch, _, kind = spec.partition(":")
        if kind not in ("leak", "dead", "no_nail"):
            ap.error(f"--defect {spec!r}: KIND 必须是 leak|dead|no_nail")
        try:
            defects[int(ch)] = kind
        except ValueError:
            ap.error(f"--defect {spec!r}: CH 必须是整数")

    if args.rescue:
        if not args.state_dir:
            ap.error("--rescue 要求 --state-dir：链不在盘上就没有可救援的账")
        if args.live:
            # §7.3 修正案 (a) 由码来守，不靠约定：同一份命令里跑实验又提交人工稿，
            # 这份读数的机器唯一性就没了——而 T9 的全部价值只在「机器可复现」这一件事上。
            ap.error("--rescue 不与 --live 同一条命令：测量跑必须机器唯一。"
                     "先跑测量，再单独用 --rescue 对盘上那条链做人工重入")
        for line in _rescue_run(args.state_dir, _read_model_config(args.model_config),
                                args.rescue):
            print(line)
        return 0

    if args.live:
        report, msg, diag = _live_run(args.chapters, _read_model_config(args.model_config),
                                      dump_dir=args.dump_dir, arm=args.prompt,
                                      state_dir=args.state_dir, fail_stop=args.fail_stop)
        print(msg)
        if report is None:
            return 2
        print(f"tokens={report.total_tokens} cost=${report.total_cost_usd:.4f} "
              f"用时={report.total_duration_ms / 1000:.0f}s｜"
              f"抽取产出 {diag['proposals']} 条（规则提升 {diag['promoted']}）"
              f" / 坏料 {diag['malformed'] or '无'}")
        if diag.get("calls"):
            print(f"接线：{diag['calls']}")
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
