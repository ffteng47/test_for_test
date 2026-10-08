"""markup → EventProposal 通道 1（07 §4.3）。

reader_* 标注逐条转为 READER_* Proposal：extraction_method="markup"、
extraction_confidence=1000（标注即事实）。hook 标注不是事件，不产 Proposal；
unknown 桶由 validator 的 M2 配对规则处理，不在此静默生成。
"""
from __future__ import annotations

from typing import List

from .markup import DraftMarkup
from .models.proposal import EventProposal

_KIND_TO_EVENT = {
    "learns": "READER_LEARNS",
    "hinted": "READER_HINTED",
    "deceived": "READER_DECEIVED",
}


def markup_to_proposals(markup: DraftMarkup, chapter: int,
                        start_seq: int) -> List[EventProposal]:
    """按标注出现顺序生成 Proposal，seq 自 start_seq 连续递增。"""
    proposals: List[EventProposal] = []
    seq = start_seq
    for anno in markup.readers:
        if anno.fact_id is None:
            continue  # 缺 fact 的标注不产 Proposal（M2 由 validator 配对裁决）
        proposals.append(EventProposal(
            proposed_event_type=_KIND_TO_EVENT[anno.kind],
            actor=None,
            target=anno.fact_id,
            chapter=chapter,
            seq=seq,
            payload={"fact_id": anno.fact_id},
            confidence=1000,
            source_ref=f"markup:reader_{anno.kind}#{seq}",
            extraction_method="markup",
            extraction_confidence=1000,
        ))
        seq += 1
    return proposals
