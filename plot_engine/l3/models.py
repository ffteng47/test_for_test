"""L3 共享模型（派生物，不入账、不改 PAYLOAD_SCHEMA）。

出处指针统一行号区间制（v0.4 同源）：`"26-27"` 表示送检正文第 26–27 行（1-based，
宿主回填原文，模型不可见本层）。
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class SceneFrame(BaseModel):
    """章内场景帧（派生物）。场景边界=地点名词跳变或时间标记词。"""

    chapter: int
    scene_seq: int               # 章内场景序号（0=章首场景=开场设定，A 族豁免）
    location_text: str           # 命中的地点名词（正文原话；无命中="-"）
    line_start: int
    line_end: int
    present: List[str] = []      # 本场景行内提及的白名单实体
    arrived: List[str] = []      # 本场景有到达叙述的实体
    departed: List[str] = []     # 本场景有硬离开叙述的实体（意图词不算）
    # 抽取层 v2 修复①②：present/到达/离开=叙述行口径；present_line=实体首次在场的叙述行号
    present_line: Dict[str, int] = {}


class Statement(BaseModel):
    """静态事实陈述（C 族域：数量/保管/值守），带认识论分层标签。"""

    chapter: int
    predicate: str               # key_count / key_custody / night_watch（白名单=尺面）
    value: str                   # 规范化取值（如 "2把" / "赵六+长老"）
    raw: str                     # 原文片段（出处）
    line_start: int
    line_end: int
    epistemic: Literal["narrator", "dialogue", "speculation"]
    tense: Literal["on_scene", "aftermath"] = "on_scene"  # v2 修复④：事后/回忆=aftermath


class IntervalFact(BaseModel):
    """有效区间投影（InkOS state-reducer 互证形态：expire 不删行）。

    只有 narrator 陈述建权威区间；dialogue/speculation 是 claim，不顶替权威事实。
    """

    subject: str
    predicate: str
    object: str
    valid_from: int
    valid_until: Optional[int] = None
    source_chapter: int
    evidence_ref: str


class ConsistencyCandidate(BaseModel):
    """一致性候选。候选不是定罪——severity 恒 OBS，判分在旁路车道。"""

    family: Literal["A", "B", "C", "D", "E"]
    chapter: int
    rule_id: str                 # 触发规则（如 "entry_without_source"）
    evidence_refs: List[str]     # 行号区间，宿主可回填
    detail: str
    epistemic_pair: str = ""     # C 族：narrator_narrator / narrator_dialogue / ...
    severity: Literal["OBS"] = "OBS"
