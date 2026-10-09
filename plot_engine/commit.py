"""CommitOrchestrator：07 §5–§9 四阶段管道 + §7.5 parity 回滚。

Stage 1 Validate / Stage 2 Reduce 合并在 `reduce_commit`（同一 reduce 路径，零漂移）；
Stage 3 Persist 复用 `StateStore.persist`（WAL+CAS+幂等）；提交成功后自动增量 Replay 对账，
hash 不符则回滚本次 version、事件标 orphan、落 REPLAY_INCONSISTENT 并停 pipeline（07 §7.5 R6）。
Phase 0：无副作用失败（HARD / 空批）不写任何 version 或 event；IO_ERROR 由底层 sqlite 异常归一。
"""
from __future__ import annotations

import sqlite3
from typing import FrozenSet, List, Optional

from plot_engine.canonical import proposal_set_hash
from plot_engine.eventlog import EventLog
from plot_engine.models.commit import CommitOutcome, CommitRequest, CommitStatus, CommitTrace
from plot_engine.models.proposal import EventProposal
from plot_engine.models.state import StoryState
from plot_engine.reduce import reduce_commit
from plot_engine.replay import verify_parity
from plot_engine.store import StateStore
from plot_engine.validator import Validator


class CommitOrchestrator:
    def __init__(self, store: StateStore, log: EventLog, reducer,
                 validator: Optional[Validator] = None) -> None:
        self._store = store
        self._log = log
        self._reducer = reducer
        self._validator = validator

    def commit(self, request: CommitRequest, proposals: List[EventProposal],
               arc_state: StoryState,
               *, committed_event_ids: FrozenSet[str] = frozenset()) -> CommitOutcome:
        epoch = arc_state.epoch
        chapter_no = request.chapter_no
        version_before = request.expected_version

        def trace(result: CommitStatus, *, hard=0, soft=0, obs=0, quar=0,
                  after: Optional[int] = None) -> CommitTrace:
            return CommitTrace(trace_id=request.trace_id, story_id=request.story_id,
                               chapter_no=chapter_no, result=result,
                               hard_violations=hard, soft_warnings=soft,
                               observations=obs, quarantined_proposals=quar,
                               version_before=version_before, version_after=after,
                               epoch=epoch)

        # Stage 1 + 2：判定 + 单条 reduce（无副作用）
        rb = reduce_commit(arc_state, proposals, request.contract, request.draft, epoch,
                           committed_event_ids=committed_event_ids, validator=self._validator)
        counts = dict(hard=len(rb.validation.hard_violations),
                      soft=len(rb.validation.soft_warnings),
                      obs=len(rb.validation.observations),
                      quar=rb.quarantined)

        # HARD 非空 / 空批 → FAIL，不进入 Stage 3，不写任何东西（07 §5.3 R1 / Review Focus #4）
        if not rb.committable() or not rb.applied:
            reasons = []
            if rb.new_state is None:
                reasons.append("H8.1 整批短路")
            if not rb.validation.can_commit():
                reasons.append(f"HARD={len(rb.validation.hard_violations)}")
            cons = sum(1 for f in rb.consistency if f["severity"] == "hard")
            if cons:
                reasons.append(f"consistency_hard={cons}")
            if not rb.applied:
                reasons.append("empty batch")
            if not reasons:
                reasons.append("unspecified")
            return CommitOutcome(status="FAIL", trace=trace("FAIL", **counts),
                                 validation=rb.validation,
                                 message="not committable: " + "+".join(reasons))

        psh = proposal_set_hash([e.model_dump(mode="json") for e in rb.applied])

        # Stage 3：WAL + CAS + 幂等（07 §7/§8）
        try:
            res = self._store.persist(request.story_id, rb.new_state, version_before,
                                      proposal_set_hash=psh, event_log=self._log,
                                      events=rb.applied)
        except sqlite3.Error as exc:                       # 07 §7.4 F1/F3/F5
            return CommitOutcome(status="IO_ERROR", trace=trace("IO_ERROR", **counts),
                                 validation=rb.validation, message=f"persist error: {exc}")

        if res.status == "CONFLICT":
            return CommitOutcome(status="CONFLICT", current_version=res.current_version,
                                 trace=trace("CONFLICT", **counts), validation=rb.validation,
                                 message=res.message)
        if res.status == "DUPLICATE":
            return CommitOutcome(status="DUPLICATE", new_version=res.new_version,
                                 trace=trace("DUPLICATE", **counts, after=res.new_version),
                                 validation=rb.validation, message=res.message)

        # §7.5：提交成功后增量 Replay 对账，不一致则回滚本次 Commit
        if not verify_parity(self._store, self._log, self._reducer, request.story_id, chapter_no):
            self._store.revert_commit(request.story_id, res.new_version, chapter_no, psh, self._log)
            return CommitOutcome(status="REPLAY_INCONSISTENT", trace=trace("REPLAY_INCONSISTENT",
                                                                            **counts),
                                 validation=rb.validation,
                                 message="replay state_hash mismatch (07 §7.5 R6)")

        return CommitOutcome(status="OK", new_version=res.new_version,
                             trace=trace("OK", **counts, after=res.new_version),
                             validation=rb.validation)
