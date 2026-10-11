"""Phase 1 T1b：被路由给人工的单章重入（07 §5–§9 + 06 §6 步 7「交人工」的后半程）。

闭环长这样：dump 里的 `trace_status=NEEDS_HUMAN` 章 → 人改正文（或预编辑 Proposal）→
本函数一次 commit → 07 §7.5 的 replay 对账。**没有自动修订**：`RevisionLoop` 一步不跑，
人给的稿子就是最终稿，判据（Contract）也不重议——重议会把「人已经改过」这件事洗成
「契约又放宽了一次」。

只救援**链尾**：章一旦失败就不会有提交残留（07 §5.3 R1 无副作用失败），所以正常救援
不需要回滚；反过来，若它后面的章已经入库，回滚它等于整链重跑，那是实验的事不是这里的事。
⇒ 救援必须按章号顺序做，不满足就 raise，不做半吊子的历史重写。
"""
from __future__ import annotations

from typing import List, Optional

from plot_engine.commit import CommitOrchestrator
from plot_engine.eventlog import EventLog
from plot_engine.extract import RuleChannel, stage0_extract
from plot_engine.models.commit import CommitOutcome, CommitRequest
from plot_engine.models.contract import ChapterContract
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore
from plot_engine.validator import Validator


def rescue_chapter(store: StateStore, log: EventLog, story_id: str,
                   contract: ChapterContract, *, scene_plan: Optional[ScenePlan] = None,
                   draft: str = "", rule_channel: Optional[RuleChannel] = None,
                   llm_channel=None, proposals: Optional[List[EventProposal]] = None,
                   reducer: Optional[Reducer] = None,
                   validator: Optional[Validator] = None) -> CommitOutcome:
    """人工改后稿的一轮提交。`proposals` 给了就跳过 Stage-0（人已经预编辑并冻结）。"""
    env = store.load_latest(story_id)
    if env.state.chapter_no >= contract.chapter_no:
        raise ValueError(f"第 {contract.chapter_no} 章不是链尾（已提交到第 "
                         f"{env.state.chapter_no} 章）：救援按序做，链尾之后的重写属于整链重跑")
    props = (proposals if proposals is not None else stage0_extract(
        draft, scene_plan, contract, env.state, chapter=contract.chapter_no,
        rule_channel=rule_channel, llm_channel=llm_channel))
    orch = CommitOrchestrator(store, log, reducer or Reducer(), validator or Validator())
    return orch.commit(
        CommitRequest(story_id=story_id, chapter_no=contract.chapter_no, draft=draft,
                      contract=contract, scene_plan=scene_plan,
                      expected_version=env.version, trace_id=f"rescue-{contract.chapter_no}"),
        props, env.state)
