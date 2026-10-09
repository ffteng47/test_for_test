"""10 章实验协议数据契约（08_experiment_protocol.md §2 配置 / §3 报告 / §4 硬指标）。

Phase 0 网络无关：真实 LLM Writer/抽取与 Arc→Contract→ScenePlan 生成器均不在本协议范围，
实验链路以注入的确定性 `ChapterArtifacts` 充当非确定模型，验证管道接线（见 Day 20–22 计划偏离记录）。
Revision 循环（06）未落地，报告 `revision_*` 记为未运行、E3 标 N/A。数值一律定点整数×1000。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from plot_engine.models.contract import ArcContract, ChapterContract
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState


class HardMetric(str, Enum):
    """08 §4 九项硬指标桶（Phase 0 唯一 KPI，目标恒为 0）。"""
    CANON = "canon_contradiction"
    KNOWLEDGE = "knowledge_contradiction"
    TIMELINE = "timeline_contradiction"
    IMPOSSIBLE_ACTION = "character_impossible_action"
    DEAD_REAPPEAR = "dead_character_reappears"
    ITEM_UNAVAILABLE = "unavailable_item_used"
    FORBIDDEN_LEAK = "forbidden_knowledge_leak"
    REQUIRED_EVENT_MISSING = "required_plot_event_missing"
    REPLAY = "replay_inconsistency"


# HARD rule_id → 硬指标桶（08 §4/§6）。未列入的 rule 由分类器兜底归 CANON 并单记 by_rule。
RULE_TO_METRIC: Dict[str, HardMetric] = {
    # dead / unborn 出场（validator L1 + consistency I7）
    "H1.1": HardMetric.DEAD_REAPPEAR, "I7": HardMetric.DEAD_REAPPEAR,
    # 地点/境界/能力/解锁 → 角色做了不可能的动作
    "H1.3": HardMetric.IMPOSSIBLE_ACTION, "H1.4": HardMetric.IMPOSSIBLE_ACTION,
    "H2.4": HardMetric.IMPOSSIBLE_ACTION, "H4.3": HardMetric.IMPOSSIBLE_ACTION,
    # 库存超额/负数 → 使用了不可用物品
    "H1.2": HardMetric.ITEM_UNAVAILABLE, "H4.1": HardMetric.ITEM_UNAVAILABLE,
    "H4.2": HardMetric.ITEM_UNAVAILABLE,
    # 时序：倒流/未来引用/同批顺序/同时两地
    "H3.1": HardMetric.TIMELINE, "H3.2": HardMetric.TIMELINE,
    "H3.3": HardMetric.TIMELINE, "H3.4": HardMetric.TIMELINE,
    # 禁止知识外泄（角色已持有 / 整批建立）
    "H2.1": HardMetric.FORBIDDEN_LEAK, "H5.7": HardMetric.FORBIDDEN_LEAK,
    # 知识账本不一致（引用未定义事实 / source 不在提交集）
    "I9": HardMetric.KNOWLEDGE, "H2.2": HardMetric.KNOWLEDGE, "H5.6": HardMetric.KNOWLEDGE,
    # 必需事件缺失 / must_change 无实现
    "H5.1": HardMetric.REQUIRED_EVENT_MISSING, "H5.3": HardMetric.REQUIRED_EVENT_MISSING,
    # Replay 不一致（由 commit status 命中，此处为代表来源，保证桶非空）
    "REPLAY_INCONSISTENT": HardMetric.REPLAY,
    # 设定/正典矛盾（双层真相不一致 / ID 冲突）
    "R7": HardMetric.CANON, "I1": HardMetric.CANON,
}


@dataclass
class ChapterArtifacts:
    """注入式逐章产物：Commit 链路所需的一切（draft 与 channels 可缺，Writer/抽取现场生成）。"""
    contract: ChapterContract
    scene_plan: Optional[ScenePlan] = None
    draft: str = ""
    rule_channel: Optional[Callable[..., List[EventProposal]]] = None
    llm_channel: Optional[Callable[..., List[EventProposal]]] = None


class ExperimentConfig(BaseModel):
    """实验输入（08 §2）。"""
    story_id: str
    chapters: int = 10
    arc_contract: ArcContract
    initial_state: StoryState
    seed: int
    epoch: str
    model_router_config: dict = Field(default_factory=dict)


class ExperimentReport(BaseModel):
    """实验输出（08 §3 verbatim 字段）。"""
    experiment_id: str
    config: ExperimentConfig

    chapters_generated: int = 0
    chapters_committed: int = 0

    hard_violations: Dict[str, int] = Field(default_factory=dict)   # 按 rule_id
    soft_warnings: Dict[str, int] = Field(default_factory=dict)
    observations: Dict[str, int] = Field(default_factory=dict)

    canon_contradictions: int = 0
    knowledge_contradictions: int = 0
    timeline_contradictions: int = 0

    replay_consistency: bool = True
    replay_mismatch_chapters: List[int] = Field(default_factory=list)

    revision_rounds: Dict[int, int] = Field(default_factory=dict)   # 每章 revision 轮数
    revision_success_rate: float = 0.0
    unresolved_chapters: List[int] = Field(default_factory=list)

    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0

    timestamp: str = ""
