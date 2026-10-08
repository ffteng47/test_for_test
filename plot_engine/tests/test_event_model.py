"""Event 模型测试：合法构造回读 + 非法输入拒绝（01 §4）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from plot_engine.models.event import Event


def _mk(**kw):
    base = dict(event_id="evt_00000047_003", epoch="epoch_0",
                event_type="OBSERVES", chapter=47, seq=2,
                payload={"fact_id": "fact_000003", "method": "sight"})
    base.update(kw)
    return Event(**base)


def test_valid_event_reads_back_fields():
    e = _mk()
    assert e.schema_version == 2 and e.confidence == 1000


@pytest.mark.parametrize("bad", [
    {"event_id": "evt_47_3"},                 # 错误的 id 正则
    {"event_type": "NOT_A_TYPE"},             # Taxonomy 之外的类型
    {"chapter": 0},                           # chapter 必须 >= 1
    {"confidence": 1001},                     # 超出定点 0~1000
])
def test_malformed_event_rejected(bad):
    with pytest.raises(ValidationError):
        _mk(**bad)
