"""Draft markup 解析通道（07 §4.4）：HTML 注释 → 结构化标注。

解析器只负责分类（hooks / readers / unknown），不判定数量与位置约束
（恰好一条 hook、末尾 3 段内等由 validator 的 M1/M5 规则裁决）。
不认识的注释一律进 unknown 桶，绝不静默丢弃（05 §9 I6）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_HOOK_RE = re.compile(r"<!--\s*hook:\s*(\w+)\s+strength=(\d+)\s*-->")
_READER_RE = re.compile(r"<!--\s*reader_(learns|hinted|deceived):\s*(\S+)\s*-->")


@dataclass
class HookAnno:
    kind: Optional[str]        # cliffhanger/reveal/callback/none/...（值域校验归 validator）
    strength: Optional[int]    # 定点 int，0..1000 由 validator 判定
    para_index: int            # 所在段（0 起）
    raw: str


@dataclass
class ReaderAnno:
    kind: str                  # "learns" | "hinted" | "deceived"
    fact_id: Optional[str]
    para_index: int
    raw: str


@dataclass
class DraftMarkup:
    hooks: List[HookAnno] = field(default_factory=list)
    readers: List[ReaderAnno] = field(default_factory=list)
    para_count: int = 0
    unknown: List[str] = field(default_factory=list)


def _split_paragraphs(draft: str) -> List[str]:
    stripped = draft.strip()
    if not stripped:
        return []
    return [p for p in re.split(r"\n\s*\n", stripped) if p.strip()]


def parse_markup(draft: str) -> DraftMarkup:
    """按空行分段，逐段扫描 HTML 注释并分类。"""
    result = DraftMarkup()
    paragraphs = _split_paragraphs(draft)
    result.para_count = len(paragraphs)
    for idx, para in enumerate(paragraphs):
        for comment in _COMMENT_RE.findall(para):
            hook = _HOOK_RE.fullmatch(comment)
            reader = _READER_RE.fullmatch(comment)
            if hook:
                result.hooks.append(HookAnno(kind=hook.group(1),
                                             strength=int(hook.group(2)),
                                             para_index=idx, raw=comment))
            elif reader:
                result.readers.append(ReaderAnno(kind=reader.group(1),
                                                 fact_id=reader.group(2),
                                                 para_index=idx, raw=comment))
            else:
                result.unknown.append(comment)
    return result
