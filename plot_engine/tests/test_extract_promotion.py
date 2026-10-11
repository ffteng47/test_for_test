# §7.3-1 确定性提升规则的 golden test：同一段推理文稿，补出的 INFERS 与 fact_id 归属逐字可复现。
from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint
from plot_engine.llm_extract import make_llm_channel
from plot_engine.models.contract import ChapterContract, ChapterHook
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"
# 结论措辞在正文里；模型只给 OBSERVES + FACT_CONTRADICTED，漏了 INFERS（§7.1 脸一的原样形态）
DRAFT = "张三凝视印章，纹路对不上。印泥是干的。\n\n他敲了三次，声音是空的——他确定了：这枚是伪造的。"

_INFER = ("[{\"event_type\": \"OBSERVES\", \"actor\": \"char_000001\", "
          "\"payload\": {\"fact_id\": \"fact_000001\"}},"
          " {\"event_type\": \"FACT_CONTRADICTED\", \"actor\": \"char_000001\", "
          "\"payload\": {\"fact_id\": \"fact_000002\"}}]")
_WITH_INFERS = _INFER[:-1] + (", {\"event_type\": \"INFERS\", \"actor\": \"char_000001\", "
                              "\"payload\": {\"conclusion_fact_id\": \"fact_000002\", "
                              "\"evidence_fact_ids\": [\"fact_000001\"]}}]")


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", introduced_at_chapter=1, epoch=EPOCH)},
        facts={"fact_000001": Fact(fact_id="fact_000001", fact_type="existence",
            proposition="印泥已干", canonical_form="c1", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH),
            "fact_000002": Fact(fact_id="fact_000002", fact_type="existence",
            proposition="印章17为伪造品", canonical_form="c2", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)},
        state_hash="0" * 64)


def _contract(chapter_no=47):
    return ChapterContract(chapter_no=chapter_no, arc_id="arc_003", epoch=EPOCH,
                           story_goal="g", story_goal_type="revelation",
                           knowledge_allowed=["fact_000001", "fact_000002"],
                           knowledge_forbidden=[],
                           ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
                           created_at="2026-10-09T00:00:00Z")


def _channel(reply):
    client = LlmClient(LlmRouter(endpoints={"extract": ModelEndpoint(model="m")}),
                       transport=lambda url, payload, headers, timeout_s:
                       {"choices": [{"message": {"content": reply}}],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    return make_llm_channel(client)


def _run(reply, draft=DRAFT):
    ch = _channel(reply)
    return ch(draft, None, _contract(), _state()), ch


def test_golden_conclusion_language_upgrades_the_near_miss_to_infers():
    props, ch = _run(_INFER)
    assert [(p.proposed_event_type, p.actor, p.seq) for p in props] == [
        ("OBSERVES", "char_000001", 0),
        ("FACT_CONTRADICTED", "char_000001", 1),
        ("INFERS", "char_000001", 2)]
    promoted = props[-1]
    assert promoted.payload == {"conclusion_fact_id": "fact_000002",
                                "evidence_fact_ids": ["fact_000001"]}
    assert (promoted.source_ref, promoted.extraction_method, promoted.confidence) == \
        ("promote:fact_000002", "hybrid", 700)      # 置信度沿用点名那条事件的，不虚报
    assert ch.promoted == 1 and ch.produced == 3      # 提升不静默：读数上单独记账


def test_model_that_already_named_infers_is_left_alone():
    props, ch = _run(_WITH_INFERS)
    assert [p.proposed_event_type for p in props] == ["OBSERVES", "FACT_CONTRADICTED", "INFERS"]
    assert ch.promoted == 0


def test_no_conclusion_language_no_promotion():
    props, ch = _run(_INFER, draft="张三凝视印章，纹路对不上。印泥是干的。")
    assert [p.proposed_event_type for p in props] == ["OBSERVES", "FACT_CONTRADICTED"]
    assert ch.promoted == 0


def test_negated_conclusion_marker_does_not_fire():
    props, ch = _run(_INFER, draft="张三凝视印章。\n\n他无法确定这枚是伪造的。")
    assert ch.promoted == 0 and len(props) == 2


def test_inference_without_an_actor_is_not_fabricated():
    """INFERS 的账落在 actor 名下；无主提升会在 reducer 里造出 character_id=None 的条目。"""
    props, ch = _run(_INFER.replace('"char_000001"', 'null'))
    assert ch.promoted == 0 and len(props) == 2


def test_conclusion_must_differ_from_the_evidence():
    """模型只给 OBSERVES(f1) + FACT_CONTRADICTED(f1)：同一条事实既当据又当结论 ⇒ 不提升。"""
    props, ch = _run("[{\"event_type\": \"OBSERVES\", \"actor\": \"char_000001\", "
                     "\"payload\": {\"fact_id\": \"fact_000001\"}},"
                     " {\"event_type\": \"FACT_CONTRADICTED\", \"actor\": \"char_000001\", "
                     "\"payload\": {\"fact_id\": \"fact_000001\"}}]")
    assert ch.promoted == 0 and len(props) == 2
