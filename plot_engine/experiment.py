"""10 章实验驱动 + Phase-0 退出条件闸门（08_experiment_protocol.md §5/§8）。

网络无关：逐章产物由注入的 `chapter_source` 提供，Writer/抽取通道亦注入；真实模型与
Arc→Contract→ScenePlan 生成器不在 Phase 0（见 Day 20–22 计划偏离记录）。本模块只**编排**
既有管道（Writer→Stage-0→CommitOrchestrator）并按 §4 归类硬指标，绝不新增 HARD 判据（08 I2）。
Revision 循环（06）未落地 → `revision_*` 记未运行、E3 标 N/A；tokens/cost/计时恒 0。
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from plot_engine.classify import MetricCounts, classify_outcome, to_report_fields
from plot_engine.commit import CommitOrchestrator
from plot_engine.eventlog import EventLog
from plot_engine.extract import stage0_extract
from plot_engine.models.commit import CommitRequest
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig, ExperimentReport
from plot_engine.models.state import StoryState
from plot_engine.reduce import reduce_commit
from plot_engine.reducer import Reducer
from plot_engine.replay import verify_parity
from plot_engine.store import StateStore
from plot_engine.validator import Validator
from plot_engine.writer import SceneWriter, compose_chapter_draft

ChapterSource = Callable[[int, StoryState], ChapterArtifacts]


def run_experiment(config: ExperimentConfig, *, store: StateStore, log: EventLog,
                   chapter_source: ChapterSource, scene_writer: SceneWriter,
                   reducer: Optional[Reducer] = None,
                   validator: Optional[Validator] = None) -> ExperimentReport:
    reducer = reducer or Reducer()
    validator = validator or Validator()
    orch = CommitOrchestrator(store, log, reducer, validator)
    story = config.story_id

    total = MetricCounts()
    soft_map: Dict[str, int] = {}
    obs_map: Dict[str, int] = {}
    committed: list[int] = []
    unresolved: list[int] = []
    mismatch: list[int] = []
    generated = 0

    for ch in range(1, config.chapters + 1):
        env = store.load_latest(story)
        cur, cur_version = env.state, env.version
        art = chapter_source(ch, cur)
        draft = art.draft or compose_chapter_draft(art.scene_plan, art.contract, cur, scene_writer).draft
        props = stage0_extract(draft, art.scene_plan, art.contract, cur, chapter=ch,
                               rule_channel=art.rule_channel, llm_channel=art.llm_channel)

        req = CommitRequest(story_id=story, chapter_no=ch, draft=draft, contract=art.contract,
                            scene_plan=art.scene_plan, expected_version=cur_version,
                            trace_id=f"exp-{ch}")
        out = orch.commit(req, props, cur)
        generated += 1

        # 分类快照：只读再 reduce 取 consistency findings（I 码），不触发写入
        rb = reduce_commit(cur, props, art.contract, draft, cur.epoch, validator=validator)
        mc = classify_outcome(out, consistency=rb.consistency)
        for k, v in mc.by_rule.items():
            total.by_rule[k] = total.by_rule.get(k, 0) + v
        for m, v in mc.by_metric.items():
            total.by_metric[m] += v

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

    report = ExperimentReport(
        experiment_id=f"exp-{story}-{config.seed}", config=config,
        chapters_generated=generated, chapters_committed=len(committed),
        soft_warnings={k: soft_map[k] for k in sorted(soft_map)},
        observations={k: obs_map[k] for k in sorted(obs_map)},
        unresolved_chapters=sorted(unresolved),
        replay_consistency=(len(mismatch) == 0),
        replay_mismatch_chapters=sorted(set(mismatch)),
        **to_report_fields(total))
    return report


def evaluate_exit_conditions(report: ExperimentReport) -> Dict[str, Optional[bool]]:
    """08 §8 退出条件。E3'（Revision 后成功率）依赖 06，Phase 0 未落地 → N/A(None)。"""
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
    return {"E1": e1, "E2": e2, "E3": None, "E4": e4, "E5": e5, "E6": e6}
