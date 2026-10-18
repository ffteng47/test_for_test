"""L3 语义一致性层（穿帮检测）——纯派生子包。

设计依据：`docs/l3-consistency-three-layer-design.md` v0.1（批1-2，tff 2026-10-18「确认放行」）。

三条边界纪律（违反=回滚）：
1. 本层全部是纯派生投影：零尺零契约零门禁、不回写上游、replay 不可得记「-」；
2. 判分器（NLI/LLM）不进内核，留 sampling/ 旁路车道带戳试点；
3. 候选不是定罪：severity 恒 OBS，L3 永不产 HARD。

与既有 `consistency.py`（L0 账面自洽）划界：本层管"账与文的一致性"，不管"账内部自洽"。
尺面戳：l3-v0.2.3（predicate 白名单/实体白名单/地点名词表/触发词表变更=读数变更，须带戳）。
"""
from plot_engine.l3.models import (ConsistencyCandidate, IntervalFact, SceneFrame,  # noqa: F401
                                   Statement)
