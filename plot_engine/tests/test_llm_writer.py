# 07 §4.4 Writer 缝：真实模型写正文。markup 归组装器，Writer 只产文本。
import pytest

from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint
from plot_engine.llm_writer import WriterError, make_scene_writer, scene_prompt
from plot_engine.models.contract import ChapterContract, ChapterHook
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.sceneplan import Beat, Scene
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", introduced_at_chapter=1, epoch=EPOCH),
            "char_000002": Character(character_id="char_000002", name="李四", aliases=[],
            gender=None, status="alive", death_chapter=None, seal_chapter=None, realm=None,
            abilities=[], attributes={}, current_location=None, faction_id=None,
            introduced_at_chapter=1, last_seen_at_chapter=1, epoch=EPOCH)},
        facts={"fact_000001": Fact(fact_id="fact_000001", fact_type="existence",
            proposition="印泥已干", canonical_form="c1", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH),
            "fact_000002": Fact(fact_id="fact_000002", fact_type="existence",
            proposition="真凶是李四", canonical_form="c2", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)},
        state_hash="0" * 64)


def _contract(**over):
    base = dict(chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="张三发现印泥是干的",
                story_goal_type="revelation",
                knowledge_allowed=["fact_000001"], knowledge_forbidden=["fact_000002"],
                tension_target=720,
                ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
                created_at="2026-10-09T00:00:00Z")
    return ChapterContract(**{**base, **over})


def _scene(**over):
    base = dict(scene_id="scn_0047_01", chapter_no=47, seq=0, location="loc_000012",
                characters=["char_000001", "char_000002"], purpose="张三查验印章",
                tension=600,
                beats=[Beat(beat_id=f"bt_{i:06d}", seq=i % 3, intent="铺垫",
                            beat_type="setup") for i in range(3)])
    return Scene(**{**base, **over})


def _client(replies):
    it = iter(replies)

    def transport(url, payload, headers, timeout_s):
        return {"choices": [{"message": {"content": next(it)}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}}
    return LlmClient(LlmRouter(endpoints={"writer": ModelEndpoint(model="m")}),
                     transport=transport)


def test_writer_returns_blank_line_separated_prose():
    w = make_scene_writer(_client(["第一段。\n\n第二段。"]))
    out = w(_scene(), _contract(), _state())
    assert [p.strip() for p in out.split("\n\n")] == ["第一段。", "第二段。"]


def test_writer_strips_markup_so_only_the_composer_owns_it():
    """模型若自带 hook，`compose_chapter_draft` 会再加一条 → 07 §4.4「恰好一条 hook」破功。"""
    w = make_scene_writer(_client(
        ["正文。\n\n<!-- hook: cliffhanger strength=900 -->\n\n<!-- reader_learns: fact_000001 -->"]))
    out = w(_scene(), _contract(), _state())
    assert "<!--" not in out and "正文。" in out


def test_empty_reply_is_a_scene_failure_not_a_silent_short_chapter():
    """抛错 → compose_chapter_draft 记 scene_failed，06 §4.1 以 Scene 为最小重写单位。"""
    w = make_scene_writer(_client(["   "]))
    with pytest.raises(WriterError):
        w(_scene(), _contract(), _state())


def test_writer_error_names_the_scene_for_revision_triage():
    w = make_scene_writer(_client([""]))
    with pytest.raises(WriterError) as e:
        w(_scene(), _contract(), _state())
    assert "scn_0047_01" in str(e.value)


def test_prompt_never_hands_the_model_a_forbidden_fact():
    """泄露禁止知识 → 必然 H5.7；把禁条喂进 prompt 是我们自己制造失败。"""
    joined = "\n".join(m["content"] for m in scene_prompt(_scene(), _contract(), _state()))
    assert "fact_000002" not in joined and "真凶是李四" not in joined
    assert "fact_000001" in joined                      # 允许的fact要给，否则模型无法写对
    assert "张三" in joined and "张三查验印章" in joined


def test_unknown_ids_in_scene_degrade_to_raw_id_instead_of_crashing():
    w = make_scene_writer(_client(["正文。"]))
    assert w(_scene(characters=["char_999999"], location="loc_999999"), _contract(), _state())
    joined = "\n".join(m["content"] for m in scene_prompt(
        _scene(characters=["char_999999"], location="loc_999999"), _contract(), None))
    assert "char_999999" in joined


def test_writer_accumulates_tokens_on_the_client():
    client = _client(["甲。", "乙。"])
    w = make_scene_writer(client)
    w(_scene(), _contract(), _state())
    w(_scene(), _contract(), _state())
    assert client.total_tokens == 120                   # (50+10) × 2 scene


def test_scene_writer_plugs_into_compose_chapter_draft():
    from plot_engine.writer import compose_chapter_draft
    from plot_engine.models.sceneplan import ScenePlan
    plan = ScenePlan(plan_id="sop_00000047", chapter_no=47, arc_id="arc_003",
                     contract_version=1,
                     scenes=[_scene(), _scene(scene_id="scn_0047_02", seq=1),
                             _scene(scene_id="scn_0047_03", seq=2)],
                     epoch=EPOCH, created_at="2026-10-09T00:00:00Z")
    client = _client(["好场景。", "   ", "第三个场景。"])   # 第二个 scene 失败
    asm = compose_chapter_draft(plan, _contract(), _state(), make_scene_writer(client))
    assert asm.scene_ok == ["scn_0047_01", "scn_0047_03"]
    assert asm.scene_failed == ["scn_0047_02"]
    assert "好场景。" in asm.draft and "   " not in asm.draft.split("\n\n")
    assert asm.draft.count("<!-- hook:") == 1           # 恰好一条，落在末尾


def test_blind_prompt_does_not_name_the_required_transition():
    """基线配置（v0-blind）：契约要求只当尺子，不进提示词。"""
    from plot_engine.llm_writer import prompt_version
    contract = _contract(must_change=[], required_events=[])
    joined = "\n".join(m["content"] for m in scene_prompt(_scene(), contract, _state()))
    assert prompt_version(False) == "v0-blind"
    assert "必须发生的跃迁" not in joined and "必须出现的事件类型" not in joined


def test_told_prompt_names_transitions_but_never_the_forbidden_fact():
    """告知型配置（v1-told）的红线（phase0-writer-prompt-ab §3）：
    给的是作者大纲（跃迁目标 + 必需事件类型），禁条连 id 带命题一起抹。"""
    from plot_engine.llm_writer import prompt_version
    from plot_engine.models.contract import CharacterChange, RequiredEvent
    contract = _contract(
        must_change=[CharacterChange(character_id="char_000001", field="knowledge",
                                     operation="update", target="fact_000001",
                                     expected_value="known"),
                     CharacterChange(character_id="char_000001", field="belief",
                                     operation="add", target="fact_000002",
                                     expected_value="believes")],
        required_events=[RequiredEvent(event_type="OBSERVES", description="张三看见印泥"),
                         RequiredEvent(event_type="INFERS", description="推出真凶")])
    joined = "\n".join(m["content"] for m in scene_prompt(_scene(), contract, _state(),
                                                         told=True))
    assert prompt_version(True) == "v1-told"
    assert "char_000001.knowledge update fact_000001 → known" in joined
    assert "INFERS、OBSERVES" in joined
    # 禁条目标：条目不渲染，且 description 里的 id 也被兜底抹掉
    assert "belief" not in joined.split("必须发生的跃迁")[1]
    assert "fact_000002" not in joined and "真凶是李四" not in joined
