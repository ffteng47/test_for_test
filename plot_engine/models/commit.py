"""Commit 管道数据契约（07 §4.1 输入 / §11.1 追踪 / 结果）。

模型层只做 schema，四阶段编排在 `plot_engine.commit`。`scene_plan` 本应必填
（07 §4.1 ScenePlan），Phase 0 的 ScenePlan 生成在 Day 14–16 才落地，故此处
可选并留 `Any`（documented deviation，见 Day 12-13 计划 Global Constraints）。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel

from plot_engine.models.contract import ChapterContract
from plot_engine.validator import ValidationResult

CommitStatus = Literal["OK", "FAIL", "CONFLICT", "DUPLICATE", "IO_ERROR",
                       "REPLAY_INCONSISTENT"]


class CommitRequest(BaseModel):
    """单次逐章 Commit 的输入（07 §4.1）。proposals 由 Stage 0 另行传入（deviation）。"""
    story_id: str
    chapter_no: int
    draft: str                              # 含 §4.4 markup 的整章文本
    contract: ChapterContract
    scene_plan: Optional[Any] = None        # Day 14–16 落地，暂缺省
    expected_version: int                   # CAS 用
    trace_id: str


class CommitTrace(BaseModel):
    """每次 Commit 必落的观测记录（07 §11.1）。Phase 0 计时字段填 0。"""
    trace_id: str
    story_id: str
    chapter_no: int

    stage_0_ms: int = 0
    stage_1_ms: int = 0
    stage_2_ms: int = 0
    stage_3_ms: int = 0
    replay_check_ms: int = 0

    result: CommitStatus
    hard_violations: int
    soft_warnings: int
    observations: int
    quarantined_proposals: int

    version_before: int
    version_after: Optional[int]

    epoch: str
    schema_version: int = 2
    timestamp: str = ""


class CommitOutcome(BaseModel):
    """Commit 返回：状态 + 版本指针 + 可观测 trace + Stage 1 判定（07 §5）。"""
    status: CommitStatus
    new_version: Optional[int] = None
    current_version: Optional[int] = None
    message: str = ""
    trace: CommitTrace
    validation: Optional[ValidationResult] = None
