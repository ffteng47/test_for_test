"""Commit 管道数据契约（07 §4.1 输入 / §11.1 追踪 / 结果）。

模型层只做 schema，四阶段编排在 `plot_engine.commit`。`scene_plan`（07 §4.1 ScenePlan）
自 Day 14–16 起落地为类型化字段；Phase 0 ScenePlan 由 Plot 层生成、pre-Writer 校验，
不进 Event Log，故 CommitRequest 仅承载、`CommitOrchestrator` 不强依赖。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from plot_engine.models.contract import ChapterContract
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.validator import ValidationResult

CommitStatus = Literal["OK", "FAIL", "CONFLICT", "DUPLICATE", "IO_ERROR",
                       "REPLAY_INCONSISTENT"]


class CommitRequest(BaseModel):
    """单次逐章 Commit 的输入（07 §4.1）。proposals 由 Stage 0 另行传入（deviation）。"""
    story_id: str
    chapter_no: int
    draft: str                              # 含 §4.4 markup 的整章文本
    contract: ChapterContract
    scene_plan: Optional[ScenePlan] = None    # Day 14–16 落地：规划产物，仅承载
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
    # Stage 2 不变量判定（{code, severity, detail}）。被拒章也要带出来：
    # 只有 `consistency_hard=n` 而无 code 的失败进不了 08 §6 任何桶，等于没被记录。
    consistency: List[Dict[str, Any]] = []
