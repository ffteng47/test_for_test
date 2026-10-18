"""选择性触发（轻档=每章默认，纯确定性零 LLM 成本）。

轻档=区间重叠冲突+在场/时序硬检查+陈述对照+重复块，全确定性。
深档（高风险章：多线交汇/身份揭露/关键道具转移/时间跳跃）留批3 旁路判分器送检，
高风险信号用确定性代理（场景切换数超阈），不用 LLM 判断要不要用 LLM。
"""
from __future__ import annotations

from typing import List, Sequence

from plot_engine.l3.fact_intervals import extract_statements
from plot_engine.l3.interval_conflicts import find_statement_conflicts
from plot_engine.l3.models import ConsistencyCandidate
from plot_engine.l3.scene_index import (DEFAULT_ENTITIES, DEFAULT_LOCATIONS,
                                        build_scene_index, strip_comments)
from plot_engine.l3.temporal_checks import (find_entry_without_source,
                                            find_space_rewind)
from plot_engine.l3.duplication import find_dup_runs

DEEP_SCENE_SWITCH_THRESHOLD = 6  # 深档确定性代理：章内场景切换数超阈（尺面戳 l3-v0.2）


def run_light(chapter: int, body: Sequence[str],
              entities: Sequence[str] = DEFAULT_ENTITIES,
              locations: Sequence[str] = DEFAULT_LOCATIONS) -> List[ConsistencyCandidate]:
    """单章轻档全量候选（行号=剥注释后送检行号，宿主可回填原稿）。"""
    frames = build_scene_index(chapter, body, entities, locations)
    statements = extract_statements(chapter, body, entities)
    lines, _map = strip_comments(body)
    out: List[ConsistencyCandidate] = []
    out += find_entry_without_source(frames)
    out += find_space_rewind(frames)
    out += find_statement_conflicts(statements)
    out += find_dup_runs(lines, chapter)
    return out


def needs_deep(frames: Sequence) -> bool:
    """深档触发信号（确定性代理）：场景切换数超阈。"""
    return len(frames) > DEEP_SCENE_SWITCH_THRESHOLD
