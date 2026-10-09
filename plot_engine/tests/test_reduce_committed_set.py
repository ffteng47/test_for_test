# 一致性闸的事件集必须是「已提交事件集」，不是「本批事件集」（07 §6 R4/R5）
#
# 真实模型 10 章实验里被拒章的失败信息全是 `consistency_hard=n`、一个 HARD rule_id 都没有：
# 上一章的 INFERS/DOUBTS 在 belief/knowledge ledger 里留下的 source 指针，
# 从下一章起永远指向「本批之外」的事件 → 整条故事被 I9 判死，且模型再好也救不回来。
# `experiment.py` 与 `verify_parity` 都用全量事件集调 `assert_consistent`，
# 只有增量 reduce 用了 `applied`：两条本该零漂移的路径不一致，而 ledger 记录不会自己消失。
from plot_engine.classify import classify_outcome
from plot_engine.commit import CommitOrchestrator
from plot_engine.eventlog import EventLog
from plot_engine.models.commit import CommitRequest
from plot_engine.models.contract import ChapterContract
from plot_engine.models.experiment import HardMetric
from plot_engine.models.ledger import BeliefEntry
from plot_engine.models.proposal import EventProposal, proposal_event_id
from plot_engine.reduce import reduce_commit
from plot_engine.reducer import Reducer
from plot_engine.store import StateStore
from plot_engine.tests.test_commit_orchestrator import (
    _DRAFT, _contract, _genesis_state, _proposals, _request)
from plot_engine.tests.test_reduce_commit import _state

EPOCH = "epoch_0"
CH46, CH47 = 46, 47
_OLD_SOURCE = f"evt_{CH46:08d}_001"   # 上一章已提交、本章不再触碰的事件

_CH46_DRAFT = "张三把那封信用火苗燎了一角。\n\n<!-- hook: cliffhanger strength=800 -->"


def _doubts_contract():
    """第 46 章只留一条「对 fact_000002 起疑」的信念：第 47 章的批次不会重写它。"""
    fields = _contract().model_dump()
    fields.update(chapter_no=CH46, must_change=[], must_not_change=[],
                  required_events=[{"event_type": "DOUBTS", "description": "起疑"}],
                  forbidden_events=[], knowledge_allowed=["fact_000002"],
                  knowledge_forbidden=[], reader_signals=[],
                  created_at="2026-10-08T09:00:00Z")
    return ChapterContract(**fields)


def _doubts_proposals():
    return [EventProposal(proposed_event_type="DOUBTS", actor="char_000001",
                          target="fact_000002", chapter=46, seq=1,
                          payload={"fact_id": "fact_000002"},
                          source_ref="para:1", extraction_method="llm")]


def _old_belief_entry():
    return BeliefEntry(character_id="char_000001", fact_id="fact_000001",
                       belief_state="believes", strength=600,
                       source_event_id=_OLD_SOURCE, acquired_at_chapter=46,
                       last_updated_chapter=46, epoch=EPOCH)


def test_earlier_chapter_ledger_source_is_not_a_violation():
    """本章没重写这条 belief，不代表它的 source 不是已提交事件。"""
    st = _state().model_copy(update={"belief_ledger": [_old_belief_entry()]})
    rb = reduce_commit(st, _proposals(), _contract(), _DRAFT, EPOCH,
                       committed_event_ids=frozenset({_OLD_SOURCE}))
    assert [f for f in rb.consistency if f["code"] == "I9"] == []
    assert rb.committable() is True


def test_orchestrator_knows_the_committed_events_from_the_log(tmp_path):
    """连续两章真实提交：调用方没传 committed_event_ids，日志就是已提交事件集。"""
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis("s1", _genesis_state())
    orch = CommitOrchestrator(store, log, Reducer())

    first = orch.commit(
        CommitRequest(story_id="s1", chapter_no=46, draft=_CH46_DRAFT,
                      contract=_doubts_contract(), expected_version=0, trace_id="t-46"),
        _doubts_proposals(), store.load_latest("s1").state)
    assert first.status == "OK", first.message

    out = orch.commit(_request(1), _proposals(), store.load_latest("s1").state)
    assert out.status == "OK", out.message
    # 这条 belief 的 source 仍指向第 46 章：它已提交，但不在这批 applied 事件里。
    assert _OLD_SOURCE in {e.source_event_id for e in store.load_latest("s1").state.belief_ledger}
    assert _OLD_SOURCE not in {proposal_event_id(p) for p in _proposals()}


def test_dangling_ledger_source_is_still_hard_and_carries_its_code(tmp_path):
    """反向半闸：source 真悬空时必须照拦，且被拒章的矛盾要带 code 交出去。

    只修事件集不修可见性 = 失败仍然落不进 08 §6 任何一个桶，等于没发生（backlog #3）。
    """
    store = StateStore(str(tmp_path / "s.db"))
    log = EventLog(str(tmp_path / "e.db"))
    store.init_genesis("s1", _genesis_state().model_copy(
        update={"belief_ledger": [_old_belief_entry()]}))   # 日志里没有这条事件
    out = CommitOrchestrator(store, log, Reducer()).commit(
        _request(), _proposals(), store.load_latest("s1").state)
    assert out.status == "FAIL" and "consistency_hard=1" in out.message
    assert [f["code"] for f in out.consistency if f["severity"] == "hard"] == ["I9"]
    assert (classify_outcome(out, consistency=out.consistency)
            .by_metric[HardMetric.KNOWLEDGE] == 1)
