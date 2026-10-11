# 06 §5/§6/§7 修订循环：分层回退、轮次预算、振荡早停、人工闸、State 停机
from plot_engine.models.commit import CommitOutcome, CommitTrace
from plot_engine.models.revision import RevisionPolicy
from plot_engine.revision import ChapterContext, RevisionLoop
from plot_engine.validator import Finding, ValidationResult


def _trace(ch: int) -> CommitTrace:
    return CommitTrace(trace_id=f"t{ch}", story_id="s1", chapter_no=ch, result="FAIL",
                       hard_violations=0, soft_warnings=0, observations=0,
                       quarantined_proposals=0, version_before=0, version_after=None,
                       epoch="epoch_0")


def _fail(ch: int, *rules: str, status: str = "FAIL") -> CommitOutcome:
    val = ValidationResult(hard_violations=[
        Finding(rule_id=r, severity="hard", message=f"{r} 命中") for r in rules])
    return CommitOutcome(status=status, trace=_trace(ch), validation=val)


def _ok(ch: int) -> CommitOutcome:
    return CommitOutcome(status="OK", new_version=ch, trace=_trace(ch),
                         validation=ValidationResult())


def _ctx(draft: str = "张三凝视印章。") -> ChapterContext:
    return ChapterContext(contract=None, scene_plan=None, draft=draft)      # type: ignore[arg-type]


def test_first_round_success_needs_no_revision():
    trace, out = RevisionLoop(actions={}).run_chapter("s1", 1, _ctx(), lambda c: _ok(1))
    assert trace.final_status == "OK" and trace.rounds == 0 and trace.steps == []
    assert out.status == "OK"


def test_extraction_failure_reruns_extraction_only():
    calls = []

    def rerun(c):
        calls.append("rerun_extraction")
        return c

    loop = RevisionLoop(actions={"rerun_extraction": rerun})
    trace, out = loop.run_chapter("s1", 1, _ctx(),
                                  _seq(_fail(1, "H8.1"), _ok(1)))
    assert trace.final_status == "OK" and trace.rounds == 1 and calls == ["rerun_extraction"]
    assert out.status == "OK"
    assert trace.steps[0].action == "rerun_extraction" and trace.steps[0].committed is True


def _seq(*outcomes: CommitOutcome):
    """按调用次序返回 outcomes 的 fake recommit（第 0 个是首轮）。"""
    it = iter(outcomes)

    def recommit(ctx):
        return next(it)
    return recommit


def test_contract_layer_never_rewrites_prose():
    """06 R5：Contract 错误不得用重写正文弥补。"""
    called = []
    loop = RevisionLoop(actions={"rewrite_scene": lambda c: called.append("scene") or c})
    trace, _ = loop.run_chapter("s1", 1, _ctx(), _seq(_fail(1, "H7.4")))
    assert called == []                                   # 绝不调用正文重写动作
    assert trace.needs_human is True and trace.final_status == "NEEDS_HUMAN"


def test_missing_action_escalates_to_human():
    trace, _ = RevisionLoop(actions={}).run_chapter("s1", 1, _ctx(), _seq(_fail(1, "H1.1")))
    assert trace.needs_human is True and trace.rounds == 0


def test_oscillation_jumps_to_next_ladder_level():
    """06 §7：两轮 violation 集合相同 → 立即升级，不烧完预算。"""
    loop = RevisionLoop(actions={"rewrite_scene": lambda c: c,
                                 "rewrite_chapter": lambda c: c})
    trace, out = loop.run_chapter("s1", 1, _ctx(),
                                  _seq(_fail(1, "H1.1"), _fail(1, "H1.1"), _ok(1)))
    assert [s.action for s in trace.steps] == ["rewrite_scene", "rewrite_chapter"]
    assert trace.final_status == "OK" and trace.rounds == 2 and out.status == "OK"


def test_round_budget_stops_and_escalates_to_human():
    calls = []

    def rewrite_scene(c):
        calls.append(len(calls))
        return c

    def recommit(ctx):                        # 每轮换 rule，不触发振荡
        return _fail(1, f"H1.{len(calls) + 2}")

    loop = RevisionLoop(actions={"rewrite_scene": rewrite_scene})
    trace, _ = loop.run_chapter("s1", 1, _ctx(), recommit)
    assert len(calls) == RevisionPolicy().max_rounds      # R3/R4：预算触顶即停
    # 触顶 = 把人接进 loop，终态写 NEEDS_HUMAN；outcome 侧 CommitStatus 一字未动（07 §4.1 无此枚举）
    assert trace.needs_human is True and trace.final_status == "NEEDS_HUMAN" and trace.rounds == 3


def test_state_layer_halts_without_retry():
    calls = []
    loop = RevisionLoop(actions={"rerun_extraction": lambda c: calls.append(1) or c})
    trace, _ = loop.run_chapter("s1", 2, _ctx(),
                                _seq(_fail(2, "H1.1", status="REPLAY_INCONSISTENT")))
    assert trace.halt is True and trace.final_status == "HALT" and trace.rounds == 0
    assert calls == []


def test_fact_and_event_layers_go_straight_to_human():
    # 06 §4.4/§4.5 需 epoch 升级，不是重写文本能解决的
    for rule in ("I1", "H6.1"):
        loop = RevisionLoop(actions={"rewrite_scene": lambda c: c})
        trace, _ = loop.run_chapter("s1", 1, _ctx(), _seq(_fail(1, rule)))
        assert trace.needs_human is True and trace.rounds == 0, rule
