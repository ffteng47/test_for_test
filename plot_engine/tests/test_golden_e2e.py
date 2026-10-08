import json
from pathlib import Path

from plot_engine.store import StateStore
from plot_engine.eventlog import EventLog
from plot_engine.models.state import StoryState
from plot_engine.models.event import Event
from plot_engine.reducer import Reducer
from plot_engine.consistency import assert_consistent
from plot_engine.replay import apply_events, verify_parity

FIX = Path(__file__).parent / "fixtures" / "traitor_arc.json"


def test_golden_traitor_arc(tmp_path):
    data = json.loads(FIX.read_text(encoding="utf-8"))
    store, log, red = StateStore(str(tmp_path / "s.db")), EventLog(str(tmp_path / "e.db")), Reducer()
    genesis = StoryState(**{**data["genesis"], "state_hash": ""})
    store.init_genesis("s1", genesis)
    events = [Event(**e) for e in data["chapter47_events"]]
    state = apply_events(genesis, events, red)   # 与 replay 同一条驱动路径

    hard = [f for f in assert_consistent(state, events) if f["severity"] == "hard"]
    assert hard == []

    # 期望 Ledger 值（03 §9；OBSERVES 按 §4.3 R1 下限 900，INFERS 派生 630）
    kn = {k.fact_id: (k.knowledge_state, k.strength) for k in state.knowledge_ledger}
    assert kn["fact_000003"][0] == "known" and kn["fact_000003"][1] >= 900
    assert kn["fact_000001"] == ("suspected", 630)
    rn = {r.fact_id: (r.reader_state, r.reader_strength) for r in state.reader_ledger}
    assert rn["fact_000003"] == ("knows", 900)
    assert state.belief_ledger == []             # 张三未被告知、未确认
    # fact_000002（李四是叛徒）在所有 Ledger 中均无记录
    assert "fact_000002" not in kn and "fact_000002" not in rn

    # 提交最终 reduce 结果 + 证明 replay 对账一致
    res = store.persist("s1", state, 0, proposal_set_hash="golden47", event_log=log, events=events)
    assert res.status == "OK"
    assert verify_parity(store, log, red, "s1", 47) is True

    # 幂等重放同一提交：同 proposal_set_hash → DUPLICATE，不再写
    again = store.persist("s1", state, 0, proposal_set_hash="golden47", event_log=log, events=events)
    assert again.status == "DUPLICATE"
