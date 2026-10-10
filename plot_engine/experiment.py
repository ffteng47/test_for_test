"""10 章实验驱动 + Phase-0 退出条件闸门（08_experiment_protocol.md §5/§8）。

网络无关：逐章产物由注入的 `chapter_source` 提供，Writer/抽取通道亦注入；Arc→Contract→
ScenePlan 由 `plot_engine.derive` 确定性派生（04 §4.3），ChapterContext 带上本章开工时的
State 供契约层回退（06 §4.2）使用。本模块只**编排**既有管道
（Writer→Stage-0→CommitOrchestrator）并按 §4 归类硬指标，绝不新增 HARD 判据（08 I2）。
Revision 循环（06）由调用方注入；不注入时 `revision_*` 记未运行、E3 标 N/A。
"""
from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

from plot_engine.classify import MetricCounts, classify_outcome, consistency_counts
from plot_engine.commit import CommitOrchestrator
from plot_engine.consistency import assert_consistent
from plot_engine.derive import ArcConflict, NoChapterIntent
from plot_engine.eventlog import EventLog
from plot_engine.extract import stage0_extract
from plot_engine.llm import LlmClient
from plot_engine.models.commit import CommitOutcome, CommitRequest
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig, ExperimentReport
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.reducer import Reducer
from plot_engine.replay import verify_parity
from plot_engine.revision import ChapterContext, Recommit, RevisionLoop
from plot_engine.store import StateStore
from plot_engine.validator import Validator
from plot_engine.writer import SceneWriter, compose_chapter_draft

ChapterSource = Callable[[int, StoryState], ChapterArtifacts]


def run_experiment(config: ExperimentConfig, *, store: StateStore, log: EventLog,
                   chapter_source: ChapterSource, scene_writer: SceneWriter,
                   reducer: Optional[Reducer] = None,
                   validator: Optional[Validator] = None,
                   revision_loop: Optional[RevisionLoop] = None,
                   llm_client: Optional[LlmClient] = None,
                   on_chapter: Optional[Callable[[int, Optional[ChapterContext],
                                                  List[EventProposal], "CommitOutcome | str"],
                                                 None]] = None,
                   ) -> ExperimentReport:
    reducer = reducer or Reducer()
    validator = validator or Validator()
    orch = CommitOrchestrator(store, log, reducer, validator)
    story = config.story_id
    started = time.perf_counter()

    total = MetricCounts()
    soft_map: Dict[str, int] = {}
    obs_map: Dict[str, int] = {}
    committed: list[int] = []
    unresolved: list[int] = []
    mismatch: list[int] = []
    rounds_by_chapter: Dict[int, int] = {}
    fixed_by_revision = 0
    needed_revision = 0
    generated = 0

    def quarantine(ch: int, exc: BaseException, ctx: Optional[ChapterContext] = None,
                   props: Optional[List[EventProposal]] = None) -> None:
        """Arc 层输入缺陷只作废本章：留痕进 §6 的 Contract/Arc 桶（08 §10 I3），实验继续。
        让整场实验换成 traceback，等于把一份报告换成一个错误。

        `ctx` 为空 = 本章开工前就判死（管道一步没跑）；非空 = 中途判死，正文与抽取产物
        照样交给快照——「Arc 要的事件模型没写」正是最需要区分 Writer/抽取的那一类。
        """
        unresolved.append(ch)
        total.by_rule["ARC_CONFLICT"] = total.by_rule.get("ARC_CONFLICT", 0) + 1
        if on_chapter is not None:
            on_chapter(ch, ctx, list(props or []), str(exc))

    for ch in range(1, config.chapters + 1):
        env = store.load_latest(story)
        cur, cur_version = env.state, env.version
        try:
            art = chapter_source(ch, cur)
        except (ArcConflict, NoChapterIntent) as exc:
            # 契约在本章开工前就判死（04 §4.3 / 06 §4.3 Arc Error）：管道一步没跑，
            # 不算 generated、不花 token。
            quarantine(ch, exc)
            continue
        draft = art.draft or compose_chapter_draft(art.scene_plan, art.contract, cur, scene_writer).draft
        captured: Dict[str, list] = {"props": []}

        def recommit(ctx: ChapterContext) -> "CommitOutcome":
            props = stage0_extract(ctx.draft, ctx.scene_plan, ctx.contract, cur, chapter=ch,
                                   rule_channel=art.rule_channel, llm_channel=art.llm_channel)
            captured["props"] = props
            req = CommitRequest(story_id=story, chapter_no=ch, draft=ctx.draft,
                                contract=ctx.contract, scene_plan=ctx.scene_plan,
                                expected_version=cur_version, trace_id=f"exp-{ch}")
            return orch.commit(req, props, cur)

        ctx = ChapterContext(contract=art.contract, scene_plan=art.scene_plan,
                             draft=draft, state=cur)
        if revision_loop is None:
            out = recommit(ctx)
        else:
            try:
                trace, out = revision_loop.run_chapter(story, ch, ctx, recommit)
            except (ArcConflict, NoChapterIntent) as exc:
                # 契约层重议撞开 Arc Error（06 §4.3）：管道已经跑过、token 已花 ⇒ 算 generated，
                # 但它不是模型失败，同样只作废本章，并把本章已跑出的产物交给快照。
                generated += 1
                quarantine(ch, exc, ctx, captured["props"])
                continue
            rounds_by_chapter[ch] = trace.rounds
            if trace.rounds:
                needed_revision += 1
                fixed_by_revision += int(out.status == "OK")
        if on_chapter is not None:
            on_chapter(ch, ctx, list(captured["props"]), out)
        generated += 1

        # §4/§6：validation 层硬规则按 rule_id 计入 hard_violations（含被拒章，作失败分类信号）。
        # Stage 2 的不变量矛盾同样带 code：只在 message 里出现数字的失败无法归桶。
        mc = classify_outcome(out, consistency=out.consistency)
        for k, v in mc.by_rule.items():
            total.by_rule[k] = total.by_rule.get(k, 0) + v

        val = out.validation
        if val is not None:
            for f in val.soft_warnings:
                soft_map[f.rule_id] = soft_map.get(f.rule_id, 0) + 1
            for f in val.observations:
                obs_map[f.rule_id] = obs_map.get(f.rule_id, 0) + 1

        if out.status == "OK":
            committed.append(ch)
        else:
            unresolved.append(ch)
        if out.status == "REPLAY_INCONSISTENT":
            mismatch.append(ch)

    # 整链 Replay 对账：verify_parity 只对「最新已提交章」有效（比对 load_latest）。
    # 逐章增量校验已由 orchestrator 在每次 commit 内完成，此处复核全链末章一致。
    if committed:
        last = max(committed)
        if not verify_parity(store, log, reducer, story, last) and last not in mismatch:
            mismatch.append(last)

    # committed 状态的设定/知识/时序矛盾：只对真正入库的故事负责（08 §4 三项命名指标）。
    final_env = store.load_latest(story)
    committed_events = log.read_story(story) if committed else []
    named = consistency_counts(assert_consistent(final_env.state, committed_events))

    report = ExperimentReport(
        experiment_id=f"exp-{story}-{config.seed}", config=config,
        chapters_generated=generated, chapters_committed=len(committed),
        hard_violations={k: total.by_rule[k] for k in sorted(total.by_rule)},
        soft_warnings={k: soft_map[k] for k in sorted(soft_map)},
        observations={k: obs_map[k] for k in sorted(obs_map)},
        canon_contradictions=named["canon"],
        knowledge_contradictions=named["knowledge"],
        timeline_contradictions=named["timeline"],
        unresolved_chapters=sorted(unresolved),
        replay_consistency=(len(mismatch) == 0),
        replay_mismatch_chapters=sorted(set(mismatch)),
        revision_rounds={k: rounds_by_chapter[k] for k in sorted(rounds_by_chapter)},
        revision_success_rate=(fixed_by_revision / needed_revision) if needed_revision
        else (1.0 if rounds_by_chapter else 0.0),
        # 08 §3 成本字段：只有真实模型运行才记账（离线夹具恒 0，保持 Day 20–25 结果可比）
        total_tokens=llm_client.total_tokens if llm_client else 0,
        total_cost_usd=llm_client.total_cost_usd if llm_client else 0.0,
        total_duration_ms=int((time.perf_counter() - started) * 1000) if llm_client else 0)
    return report


_MAX_REVISION_ROUNDS = 3      # 08 §8 E3' 的字面上限


def evaluate_exit_conditions(report: ExperimentReport) -> Dict[str, Optional[bool]]:
    """08 §8 退出条件。E3' 需 06 Revision 循环实际运行（逐章轮数有记录）才可判。"""
    gen = report.chapters_generated
    e1 = gen == report.config.chapters
    commit_rate = (report.chapters_committed / gen) if gen else 0.0
    e2 = commit_rate >= 0.70
    hv = report.hard_violations
    tot = sum(hv.values())
    e4 = True if tot == 0 else (max(hv.values()) / tot) <= 0.40
    mism = len(report.replay_mismatch_chapters)
    e5 = ((gen - mism) / gen) >= 0.90 if gen else False
    e6 = (report.replay_consistency and report.canon_contradictions == 0
          and report.knowledge_contradictions == 0 and report.timeline_contradictions == 0)
    rounds = report.revision_rounds
    e3: Optional[bool] = None
    if len(rounds) == gen and gen:            # 每章都有轮数记录 = Revision 确实跑过
        e3 = commit_rate >= 0.90 and max(rounds.values()) <= _MAX_REVISION_ROUNDS
    return {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6}
