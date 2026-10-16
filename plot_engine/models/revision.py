"""修订层数据契约（06 §3 RootCause、§5 RevisionPolicy、R6 过程记录）。

归因层级与回退动作都是**协议 verbatim**，本模块只做 schema，调度在 `plot_engine.revision`。
`confidence` 为定点整数 ×1000（05 §5.5），禁止 float。
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

RootCauseLevel = Literal["extraction", "writer", "contract", "arc",
                          "fact", "event", "validator", "state"]


class RootCause(BaseModel):
    """错误发生在哪一层（06 §2 R1：Revision 必须先分类 Root Cause）。"""
    level: RootCauseLevel
    evidence: str
    violated_rule_id: Optional[str] = None
    confidence: int = Field(default=1000, ge=0, le=1000)


class RevisionPolicy(BaseModel):
    """收敛策略（06 §5 verbatim 默认值）。"""
    max_rounds: int = 3
    # 06 §5 四级诚实阶梯（v0.12 裁定 2A：rewrite_scene 一级删除，writer 直接章级重写）；
    # v0.13 材料四：patch_write 插在重议之前——契约层第一动作是带清单的定向补写，
    # 宿主未注入该动作时阶梯自动跳过它（向后兼容，契约层直接走重议）。
    escalation: List[str] = Field(default_factory=lambda: [
        "rerun_extraction", "rewrite_chapter", "patch_write",
        "renegotiate_contract", "escalate_to_arc"])
    oscillation_detection: bool = True
    cost_ceiling_per_chapter_usd: float = 0.5
    human_escalation_threshold: int = 3


class RevisionStep(BaseModel):
    """单轮 Revision 的观测记录（06 R6 / 08 I3：所有 failure 必须记录）。"""
    round_no: int
    root_cause: RootCause
    action: str
    violations: List[str] = Field(default_factory=list)
    # 06 §9（v0.13 材料四裁定 3）：patch_write 行随轮记录缺失清单，dump 才能渲染
    # 「这一轮补写请求写了哪几条」。
    items: List[str] = Field(default_factory=list)
    committed: bool = False


class RevisionTrace(BaseModel):
    """一章的完整修订轨迹。`HALT` 走 06 §4.7（State 已不一致 → 停 pipeline）。"""
    story_id: str
    chapter_no: int
    steps: List[RevisionStep] = Field(default_factory=list)
    rounds: int = 0
    final_status: Literal["OK", "FAIL", "NEEDS_HUMAN", "HALT"] = "FAIL"
    needs_human: bool = False
    halt: bool = False
