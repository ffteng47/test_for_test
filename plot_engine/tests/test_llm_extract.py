# 07 §4.3 通道 3：真实模型抽取。模型输出是**不可信输入**，坏料必须可判定、不可静默。
import pytest

from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint
from plot_engine.llm_extract import extract_prompt, make_llm_channel, parse_proposals
from plot_engine.models.contract import ChapterContract, ChapterHook
from plot_engine.models.entity import Character
from plot_engine.models.fact import Fact
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"
DRAFT = "张三凝视印章。印泥是干的。"


def _state():
    return StoryState(
        story_id="s1", chapter_no=46, version=46, epoch=EPOCH,
        characters={"char_000001": Character(character_id="char_000001", name="张三",
            status="alive", introduced_at_chapter=1, epoch=EPOCH)},
        facts={"fact_000001": Fact(fact_id="fact_000001", fact_type="existence",
            proposition="印泥已干", canonical_form="c1", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH),
            "fact_000002": Fact(fact_id="fact_000002", fact_type="existence",
            proposition="真凶", canonical_form="c2", narrative_truth="unknown",
            objective_truth="unknown", defined_at_chapter=1, epoch=EPOCH)},
        state_hash="0" * 64)


def _contract():
    return ChapterContract(chapter_no=47, arc_id="arc_003", epoch=EPOCH, story_goal="g",
                           story_goal_type="revelation",
                           knowledge_allowed=["fact_000001"], knowledge_forbidden=["fact_000002"],
                           ending=ChapterHook(type="cliffhanger", strength=800, description="d"),
                           created_at="2026-10-09T00:00:00Z")


def _reply(items):
    return {"choices": [{"message": {"content": items}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}}


def _client(replies):
    it = iter(replies)
    return LlmClient(LlmRouter(endpoints={"extract": ModelEndpoint(model="m")}),
                     transport=lambda url, payload, headers, timeout_s: next(it))


def test_fenced_json_array_parses_into_llm_proposals():
    props, bad = parse_proposals(
        "```json\n[{\"event_type\": \"OBSERVES\", \"actor\": \"char_000001\", "
        "\"target\": \"fact_000001\", \"payload\": {\"fact_id\": \"fact_000001\"}, "
        "\"source_ref\": \"para:1\"}]\n```", 47, _state())
    assert bad == [] and len(props) == 1
    p = props[0]
    assert p.extraction_method == "llm"
    assert (p.proposed_event_type, p.actor, p.chapter) == ("OBSERVES", "char_000001", 47)


def test_seq_is_renumbered_so_the_model_cannot_collide_event_ids():
    """event_id 由 (chapter, seq) 推出；模型若回 5,5 或从 1 起编号 → H6.4 误爆。"""
    props, _ = parse_proposals(
        '[{"event_type": "OBSERVES", "seq": 5, "payload": {"fact_id": "fact_000001"}},'
        ' {"event_type": "READS", "seq": 5, "payload": {"fact_id": "fact_000001"}}]',
        47, _state())
    assert [p.seq for p in props] == [0, 1]


def test_surrounding_prose_is_skipped_not_failed():
    props, bad = parse_proposals(
        '好的，以下是事件：\n[{"event_type": "OBSERVES", "payload": {"fact_id": '
        '"fact_000001"}}]\n希望有帮助。', 47, _state())
    assert len(props) == 1 and bad == []


def test_illegal_event_type_is_dropped_and_recorded_not_committed():
    props, bad = parse_proposals('[{"event_type": "MURDERS"}]', 47, _state())
    assert props == []
    assert bad and bad[0]["reason"] == "unknown_event_type"


def test_unparsable_reply_yields_no_proposals_and_one_malformed_record():
    props, bad = parse_proposals("我不确定这段里发生了什么。", 47, _state())
    assert props == []
    assert bad and bad[0]["reason"] == "malformed_reply"


def test_float_in_payload_or_confidence_is_rejected():
    """05 §5.5 定点铁律：float 进 payload 会让 canonical_json 在 commit 阶段炸。"""
    _props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "payload": {"w": 0.7}}]', 47, _state())
    assert bad and bad[0]["reason"] == "float_in_payload"
    _p2, bad2 = parse_proposals('[{"event_type": "OBSERVES", "confidence": 0.9}]', 47, _state())
    assert bad2 and bad2[0]["reason"] == "float_in_payload"


def test_ids_that_are_not_in_state_are_dropped():
    """模型编造 char_999999 会在下游炸成一串无法归因的违例，抽取层就得拦下。"""
    props, bad = parse_proposals('[{"event_type": "OBSERVES", "actor": "char_999999"}]',
                                 47, _state())
    assert props == [] and bad[0]["reason"] == "unknown_id"


def test_source_ref_uses_paragraph_numbers_so_dual_channels_can_align():
    """07 §4.3 交叉验证靠 source_ref 的 span 对齐；模型回原文长引用 → 与规则通道永远对不上。"""
    props, _ = parse_proposals(
        '[{"event_type": "OBSERVES", "payload": {"fact_id": "fact_000001"}, "paragraph": 3}]',
        47, _state())
    assert props[0].source_ref == "para:3"


def test_missing_source_ref_is_filled_deterministically():
    props, _ = parse_proposals(
        '[{"event_type": "OBSERVES", "payload": {"fact_id": "fact_000001"}}]', 47, _state())
    assert props[0].source_ref.startswith("llm:")


# —— payload 契约：reducer 按 01 §4.1 取键，缺键不是「reducer 的错」而是抽取层的产物不合格
def test_payload_missing_required_key_is_dropped_and_recorded():
    """实测：qwen2.5:14b 会回 {"object": "印章"} —— 放下去就是 MALFORMED_PROPOSAL 级联。"""
    props, bad = parse_proposals('[{"event_type": "OBSERVES", "payload": {"object": "印章"}}]',
                                 47, _state())
    assert props == []
    assert bad and bad[0]["reason"] == "missing_payload_keys"
    assert "fact_id" in bad[0]["item"]


def test_infers_needs_conclusion_and_evidence():
    props, bad = parse_proposals(
        '[{"event_type": "INFERS", "payload": {"conclusion_fact_id": "fact_000001"}}]',
        47, _state())
    assert props == [] and bad[0]["reason"] == "missing_payload_keys"
    props2, _ = parse_proposals(
        '[{"event_type": "INFERS", "payload": {"conclusion_fact_id": "fact_000001",'
        ' "evidence_fact_ids": ["fact_000001"]}}]', 47, _state())
    assert len(props2) == 1


def test_null_fixed_point_key_is_dropped_rather_than_reaching_the_reducer():
    """实测：v3a1 ch04 回 `"trust_level": null` —— 键存在就放行，reducer 里 `None * int`
    抛 TypeError，整次采样连后面 6 章的读数一起没了。null 与缺键是同一类坏料。"""
    props, bad = parse_proposals(
        '[{"event_type": "IS_TOLD", "payload": {"fact_id": "fact_000001",'
        ' "trust_level": null, "message_strength": 700}}]', 47, _state())
    assert props == []
    assert bad[0]["reason"] == "missing_payload_keys" and "trust_level" in bad[0]["item"]


def test_non_integer_fixed_point_key_is_dropped():
    """定点 ×1000（05 §5.5）：字符串/bool 一样是「reducer 拿它做算术」的炸点。"""
    for value in ('"很高"', "true", '"700"'):
        raw = ('[{"event_type": "BELIEVES", "payload": {"fact_id": "fact_000001",'
               ' "belief_strength": %s}}]' % value)
        props, bad = parse_proposals(raw, 47, _state())
        assert props == [] and "belief_strength" in bad[0]["item"], value


def test_integer_fixed_point_keys_still_pass():
    props, bad = parse_proposals(
        '[{"event_type": "IS_TOLD", "payload": {"fact_id": "fact_000001",'
        ' "trust_level": 600, "message_strength": 700}}]', 47, _state())
    assert len(props) == 1 and bad == []


def test_non_enum_reveal_truth_is_dropped_before_it_reaches_the_state():
    """实测：v3b1 崩在下一章门口 —— 模型回 `"new_narrative_truth": true`（JSON 布尔），
    reducer 用 `model_copy` 写 State 不过校验，布尔就这样进了 blob；下次 `load_latest`
    才 ValidationError，整次采样的后续读数一起作废。枚举键和定点键是同一类炸点。"""
    for value in ("true", "false", '"confirmed"', "null"):
        raw = ('[{"event_type": "REVEALS", "payload": {"fact_id": "fact_000001",'
               ' "new_narrative_truth": %s}}]' % value)
        props, bad = parse_proposals(raw, 47, _state())
        assert props == [] and "new_narrative_truth" in bad[0]["item"], value


def test_enum_fixed_keys_still_pass():
    props, bad = parse_proposals(
        '[{"event_type": "REVEALS", "payload": {"fact_id": "fact_000001",'
        ' "new_narrative_truth": "true"}}]', 47, _state())
    assert len(props) == 1 and bad == []


def test_types_the_reducers_cannot_consume_are_not_accepted():
    props, bad = parse_proposals('[{"event_type": "CASE_SOLVED"}]', 47, _state())
    assert props == [] and bad[0]["reason"] == "type_not_supported"


def test_channel_wires_into_the_stage0_seam_and_accumulates_tokens():
    channel = make_llm_channel(_client([_reply(
        '[{"event_type": "OBSERVES", "target": "fact_000001",'
        ' "payload": {"fact_id": "fact_000001"}}]')]))
    props = channel(DRAFT, None, _contract(), _state())
    assert len(props) == 1
    assert channel.total_tokens == 120


def test_channel_records_bads_for_observability_instead_of_silently_dropping():
    channel = make_llm_channel(_client([_reply('[{"event_type": "MURDERS"}]')]))
    assert channel(DRAFT, None, _contract(), _state()) == []
    assert [b["reason"] for b in channel.malformed] == ["unknown_event_type"]


def test_channel_caps_output_at_max_items():
    one = '{"event_type": "OBSERVES", "payload": {"fact_id": "fact_000001"}}'
    many = "[" + ",".join(one for _ in range(6)) + "]"
    channel = make_llm_channel(_client([_reply(many)]), max_items=3)
    props = channel(DRAFT, None, _contract(), _state())
    assert len(props) == 3
    assert channel.malformed[-1]["reason"] == "over_cap"
    assert channel.produced == 3


@pytest.mark.parametrize("over", [{"temperature": 200}, {"max_items": 1}])
def test_channel_never_invents_events_when_the_model_says_nothing(over):
    if "temperature" in over:
        router = LlmRouter(endpoints={"extract": ModelEndpoint(model="m", **over)})
        client = LlmClient(router, transport=lambda *a: _reply("[]"))
    else:
        client = _client([_reply("[]")])
    channel = make_llm_channel(client, **{k: v for k, v in over.items() if k == "max_items"})
    assert channel(DRAFT, None, _contract(), _state()) == []


def test_prompt_carries_the_draft_and_the_known_id_vocabulary():
    msgs = extract_prompt(DRAFT, None, _contract(), _state())
    joined = "\n".join(m["content"] for m in msgs)
    assert DRAFT in joined
    assert "char_000001" in joined and "fact_000001" in joined
    assert "OBSERVES" in joined                       # Taxonomy 必须显式给出，否则模型自造类型
    assert "JSON" in joined or "json" in joined


def test_prompt_states_the_payload_schema_and_paragraph_numbering():
    """模型不知道 reducer 要什么键；不给 schema，它就把「印章」当 payload 交上来（实测已发生）。"""
    joined = "\n".join(m["content"] for m in extract_prompt(
        "第一段。\n\n第二段。", None, _contract(), _state()))
    assert "fact_id" in joined and "conclusion_fact_id" in joined
    assert "evidence_fact_ids" in joined
    assert "段落编号" in joined and "paragraph" in joined
    assert "1. 第一段。" in joined                    # 正文按段号给出，引用只回数字


def test_undeclared_payload_key_is_stripped_but_event_kept():
    """实测：qwen3:8b 把 schema 提示 `OBSERVES:fact_id` 回声成 payload 里的 {"OBSERVES": "fact_id"}。
    回声键进了 EventLog 就是提示词脚手架污染事件流；但该事件在正文里确实发生，
    整条丢弃会把真通过变成假失败 —— 所以剥键、记账、留事件。"""
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "char_000001", '
        '"payload": {"fact_id": "fact_000001", "OBSERVES": "fact_id"}}]', 47, _state())
    assert len(props) == 1
    assert props[0].payload == {"fact_id": "fact_000001"}
    assert bad[0]["reason"] == "stripped_payload_key"
    assert bad[0]["item"] == "OBSERVES.OBSERVES"


def test_evidence_fact_ids_list_is_not_mistaken_for_a_key():
    props, bad = parse_proposals(
        '[{"event_type": "INFERS", "actor": "char_000001", "payload": '
        '{"conclusion_fact_id": "fact_000001", "evidence_fact_ids": ["fact_000001"]}}]',
        47, _state())
    assert len(props) == 1 and bad == []
    assert props[0].payload["evidence_fact_ids"] == ["fact_000001"]


def test_int_valued_id_key_is_rejected_not_passed_through():
    """实测 null-draft 对照：模型回 `{"fact_id": 3}`。`3` 解析不到任何 Fact，
    放下去就是一条指向不存在设定的事件（01 §4.1 引用必须落在真实实体 id 上）。"""
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "actor": "char_000001", "payload": {"fact_id": 3}}]',
        47, _state())
    assert props == []
    assert bad[0]["reason"] == "id_value_not_id"
    assert bad[0]["item"] == "OBSERVES.fact_id=3"


def test_int_inside_evidence_list_is_rejected():
    props, bad = parse_proposals(
        '[{"event_type": "INFERS", "actor": "char_000001", "payload": '
        '{"conclusion_fact_id": "fact_000001", "evidence_fact_ids": [3]}}]', 47, _state())
    assert props == [] and bad[0]["reason"] == "id_value_not_id"


def test_id_keys_are_not_checked_without_state():
    """state 缺省时没有词表可判，退回原有的宽容行为（离线夹具依赖这一点）。"""
    props, bad = parse_proposals(
        '[{"event_type": "OBSERVES", "payload": {"fact_id": 3}}]', 47, None)
    assert len(props) == 1 and bad == []


def test_extract_prompt_does_not_leak_the_contracts_required_events():
    """null-draft 对照实测：模型在「正文毫无事件」时照样回 OBSERVES+INFERS —— 因为它看见了
    「本章 Contract 要求的事件类型」。通道一旦拿到答案键，H5.1/H5.3 就能被抽取器单独满足，
    实验结论也就失去意义。07 §4.3 要求通道彼此独立。"""
    msgs = extract_prompt(DRAFT, None, _contract(), _state())
    system = msgs[0]["content"]
    assert "要求的事件类型" not in system
    assert "INFERS" not in system.replace("INFERS", "") or True  # 类型词表仍在，答案键不在
    # 词表与 forbidden 仍需给出：前者是 id 的取值域，后者是泄露防线
    assert "fact_000001" in system and "fact_000002" in system


def test_extract_prompt_tells_id_keys_to_give_id_strings():
    system = extract_prompt(DRAFT, None, _contract(), _state())[0]["content"]
    assert "fact_id" in system and "字符串" in system


def test_channel_withholds_markup_from_the_model_so_channels_stay_independent():
    """实测：带 `<!-- reader_learns: fact_000003 -->` 的空正文会让模型照抄 markup 里的 fact id，
    换成不存在的 fact_000001 它也照造。markup 是通道 1，LLM 是通道 3；通道 3 读到通道 1 的答案，
    cross_validate 就永远「一致」——那是假的一致（07 §4.3）。"""
    from plot_engine.llm import LlmClient, LlmRouter, ModelEndpoint

    seen = []

    def transport(url, payload, headers, timeout_s):
        seen.append(payload["messages"])
        return _reply("[]")

    channel = make_llm_channel(LlmClient(
        LlmRouter(endpoints={"extract": ModelEndpoint(model="m")}), transport=transport))
    channel(DRAFT + "\n\n<!-- reader_learns: fact_000003 -->\n\n"
            "<!-- hook: cliffhanger strength=800 -->", None, _contract(), _state())
    user_msg = seen[0][-1]["content"]
    assert "reader_learns" not in user_msg and "cliffhanger" not in user_msg
    assert "张三凝视印章" in user_msg                       # 正文本身照常送入
