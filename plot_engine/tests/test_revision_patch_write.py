# 06 §4.2/§4.3（v0.13 材料四）契约层分诊：第一动作 = 带缺失清单的定向补写；
# 同条 must_change 补写后再失败 = needs_arc_replan（抛 ArcConflict，交 experiment 的
# Arc 通道作废本章）；H5.1 补写后再失败 = 振荡升级到重议。每型一正一反。
import pytest

from plot_engine.derive import ArcConflict
from plot_engine.models.commit import CommitOutcome, CommitTrace
from plot_engine.models.contract import ChapterContract
from plot_engine.models.revision import RevisionPolicy
from plot_engine.revision import ChapterContext, RevisionLoop
from plot_engine.validator import Finding, ValidationResult

EPOCH = "epoch_0"
KEY53 = "char_000001|knowledge|fact_000001|known"


def _contract():
    return ChapterContract(chapter_no=47, arc_id="arc_003", epoch=EPOCH,
                           story_goal="g", story_goal_type="revelation",
                           ending={"type": "cliffhanger", "strength": 800,
                                   "description": "d"},
                           created_at="2026-10-16T00:00:00Z")


def _ctx():
    return ChapterContext(contract=_contract(), draft="正文。")


def _finding(rule_id, evidence):
    return Finding(rule_id=rule_id, severity="hard", message=rule_id,
                   location=None, evidence=evidence, suggestion=None)


def _outcome(status, hard=()):
    trace = CommitTrace(trace_id="t", story_id="s1", chapter_no=47, result=status,
                        hard_violations=len(hard), soft_warnings=0, observations=0,
                        quarantined_proposals=0, version_before=0,
                        version_after=1 if status == "OK" else None, epoch=EPOCH)
    val = ValidationResult(hard_violations=list(hard)) if hard else None
    return CommitOutcome(status=status, new_version=1 if status == "OK" else None,
                         current_version=0, message=status, trace=trace,
                         validation=val)


def _loop(**actions):
    return RevisionLoop(policy=RevisionPolicy(), actions=dict(actions))


def test_h53_first_fall_gets_a_directed_patch_with_the_item_list():
    """正例：H5.3 的第一轮回退是 patch_write，条目全键随 ctx.missing_requirements 下发；
    补写后提交过 ⇒ 修订数落在 patch 轮上。"""
    bad = _outcome("FAIL", hard=[_finding("H5.3", KEY53)])
    ok = _outcome("OK")
    seen = []

    def patch(ctx):
        seen.append(list(ctx.missing_requirements))
        return ctx

    outs = iter([bad, ok])
    trace, out = _loop(patch_write=patch,
                       renegotiate_contract=lambda c: c).run_chapter(
        "s1", 47, _ctx(), lambda ctx: next(outs))
    assert seen == [[f"H5.3|{KEY53}"]]
    assert out.status == "OK" and trace.rounds == 1
    assert trace.steps[0].action == "patch_write"
    assert trace.steps[0].items == [f"H5.3|{KEY53}"]      # 06 §9 仪表：dump 能渲染清单


def test_same_h53_refail_after_patch_raises_needs_arc_replan():
    """反例：补写一轮后**同一条** must_change 仍未实现 ⇒ 正文写不出这个 Δ，
    是作者输入错误——抛 ArcConflict（needs_arc_replan），不再烧重议/人工预算。"""
    bad = _outcome("FAIL", hard=[_finding("H5.3", KEY53)])
    with pytest.raises(ArcConflict, match="needs_arc_replan"):
        _loop(patch_write=lambda c: c,
              renegotiate_contract=lambda c: c).run_chapter(
            "s1", 47, _ctx(), lambda ctx: bad)


def test_needs_arc_replan_carries_the_rounds_it_burned():
    """#98 仪表微修（§13 入册）：判死异常必须带着已跑轮次的 trace——patch-v1 时代
    quarantine 只收 message，dump 里没有 `## Revision` 段，「补写确实开过火」
    （S 批条件①）只能靠消息文本间接证。"""
    bad = _outcome("FAIL", hard=[_finding("H5.3", KEY53)])
    with pytest.raises(ArcConflict) as ei:
        _loop(patch_write=lambda c: c,
              renegotiate_contract=lambda c: c).run_chapter(
            "s1", 47, _ctx(), lambda ctx: bad)
    assert [s.action for s in ei.value.trace.steps] == ["patch_write"]


def test_writer_level_after_patch_rewrites_not_an_empty_list_patch():
    """反例（r1 ch05 round 2 实弹）：契约层补写后失败升到 Writer 层——清单必空，
    patch_write 不许空挂开火（功能≈rewrite_chapter 却遮蔽真实动作），
    必须落回该层默认动作。"""
    bad53 = _outcome("FAIL", hard=[_finding("H5.3", KEY53)])
    bad57 = _outcome("FAIL", hard=[_finding("H5.7", None)])
    ok = _outcome("OK")
    outs = iter([bad53, bad57, ok])
    seen_items = []

    def rewrite(ctx):
        seen_items.append(list(ctx.missing_requirements))
        return ctx

    trace, out = _loop(patch_write=lambda c: c, rewrite_chapter=rewrite,
                       renegotiate_contract=lambda c: c).run_chapter(
        "s1", 47, _ctx(), lambda ctx: next(outs))
    assert [s.action for s in trace.steps] == ["patch_write", "rewrite_chapter"]
    assert seen_items == [[]]                                   # 补写载荷只带真清单


def test_h51_refail_after_patch_escalates_to_renegotiate_not_second_patch():
    """H5.1 补写后再失败：不是作者债（事件类型可放宽），按 §7 振荡升级到重议——
    重议在 patch_write 之后的阶梯位上，同轮清单不再触发第二次补写。"""
    bad = _outcome("FAIL", hard=[_finding("H5.1", "INFERS")])
    calls = []
    outs = iter([bad, bad, bad])
    trace, out = _loop(
        patch_write=lambda c: calls.append("patch") or c,
        renegotiate_contract=lambda c: calls.append("reneg") or c,
    ).run_chapter("s1", 47, _ctx(), lambda ctx: next(outs))
    assert calls[:2] == ["patch", "reneg"]
    assert [s.action for s in trace.steps] == ["patch_write", "renegotiate_contract"]
    assert trace.final_status == "NEEDS_HUMAN"           # 预算触顶交人，语义不变


def test_loop_without_patch_write_keeps_the_old_route():
    """反例（向后兼容）：宿主未注入 patch_write ⇒ 契约层直接走重议，
    分诊机整个隐身——存量接线（离线夹具外的旧调用）读数不受影响。"""
    bad = _outcome("FAIL", hard=[_finding("H5.3", KEY53)])
    ok = _outcome("OK")
    outs = iter([bad, ok])
    trace, out = _loop(renegotiate_contract=lambda c: c).run_chapter(
        "s1", 47, _ctx(), lambda ctx: next(outs))
    assert out.status == "OK"
    assert trace.steps[0].action == "renegotiate_contract"
