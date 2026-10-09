# Writer 整章 Draft 组装 + Scene 重写缝（04 §8.4, 07 §4.4）
import re

from plot_engine.models.contract import ChapterContract, ChapterHook, ReaderSignal
from plot_engine.models.sceneplan import Beat, Scene, ScenePlan
from plot_engine.markup import parse_markup
from plot_engine.writer import compose_chapter_draft

EPOCH = "epoch_0"


def _beat(i: int) -> Beat:
    return Beat(beat_id=f"bt_{i:06d}", seq=i % 3, intent="x", beat_type="setup")


def _scene(n: int) -> Scene:
    return Scene(scene_id=f"scn_0047_{n:02d}", chapter_no=47, seq=n - 1,
                 location="loc_000012", characters=["char_000001"],
                 purpose="p", tension=500, beats=[_beat(3 * n + k) for k in range(3)])


def _plan(scene_ids: list[int]) -> ScenePlan:
    return ScenePlan(plan_id="sop_00000047", chapter_no=47, arc_id="arc_003",
                     contract_version=1, scenes=[_scene(i) for i in scene_ids],
                     epoch=EPOCH, created_at="2026-10-09T00:00:00Z")


def _contract(signals: list[tuple[str, str]]) -> ChapterContract:
    return ChapterContract(
        chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="g",
        story_goal_type="revelation",
        reader_signals=[ReaderSignal(fact_id=f, target_state=s) for f, s in signals],
        ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
        created_at="2026-10-09T00:00:00Z")


def _ok_writer(scene, contract, state) -> str:
    return f"{scene.scene_id} 的正文。\n\n第二段。"


def _flaky_writer(scene, contract, state) -> str:
    if scene.scene_id == "scn_0047_02":
        raise RuntimeError("boom")
    return _ok_writer(scene, contract, state)


def test_all_scenes_ok_produces_hook_and_readers():
    plan = _plan([1, 2, 3])
    contract = _contract([("fact_000003", "knows"), ("fact_000001", "hinted")])
    asm = compose_chapter_draft(plan, contract, None, _ok_writer)
    assert asm.scene_ok == ["scn_0047_01", "scn_0047_02", "scn_0047_03"]
    assert asm.scene_failed == []
    assert "scn_0047_01" in asm.draft and "scn_0047_03" in asm.draft


def test_failed_scene_isolated_others_committed():
    plan = _plan([1, 2, 3])
    contract = _contract([("fact_000003", "knows")])
    asm = compose_chapter_draft(plan, contract, None, _flaky_writer)
    assert asm.scene_failed == ["scn_0047_02"]
    assert asm.scene_ok == ["scn_0047_01", "scn_0047_03"]
    assert "scn_0047_02" not in asm.draft
    # 整章仍含合规 markup：恰好一条 hook、reader 命中
    mk = parse_markup(asm.draft)
    assert len(mk.hooks) == 1
    assert mk.hooks[0].kind == "cliffhanger" and mk.hooks[0].strength == 800
    assert {r.fact_id for r in mk.readers} == {"fact_000003"}


def test_hook_within_last_three_paragraphs():
    plan = _plan([1, 2, 3])
    contract = _contract([("fact_000001", "knows"), ("fact_000002", "deceived")])
    asm = compose_chapter_draft(plan, contract, None, _ok_writer)
    mk = parse_markup(asm.draft)
    assert mk.hooks[0].para_index >= mk.para_count - 3


def test_reader_kinds_mapped_and_unaware_skipped():
    plan = _plan([1, 2, 3])
    contract = _contract([("fact_000003", "knows"), ("fact_000001", "hinted"),
                          ("fact_000002", "deceived"), ("fact_000004", "unaware")])
    asm = compose_chapter_draft(plan, contract, None, _ok_writer)
    kinds = {(r.kind, r.fact_id) for r in parse_markup(asm.draft).readers}
    assert kinds == {("learns", "fact_000003"), ("hinted", "fact_000001"),
                     ("deceived", "fact_000002")}   # unaware 不产标注


def test_draft_roundtrips_parse_and_no_stray_comment():
    plan = _plan([1, 2, 3])
    contract = _contract([("fact_000003", "knows")])
    asm = compose_chapter_draft(plan, contract, None, _ok_writer)
    mk = parse_markup(asm.draft)
    assert mk.unknown == []                       # 只注入可解析的标注
    # reader 标注紧邻 hook 之前，二者都在末尾段
    assert re.search(r"<!--\s*reader_learns:\s*fact_000003\s*-->", asm.draft)
