# v3 三臂 golden test（`docs/phase0-final-report-and-v3-config-ab.md` §10.3）——常驻 CI，替代一次性人工核验。
# 任一条断言失效 ⇒ 「v2 六次与 v3 九次同面可比」作废，采样读数全部作废重跑。
import hashlib

from plot_engine.llm_writer import prompt_version, scene_prompt
from plot_engine.models.contract import CharacterChange, RequiredEvent
from plot_engine.models.event import EventType
from plot_engine.models.sceneplan import Beat
from plot_engine.tests.test_llm_writer import _contract, _scene, _state

# ch02 形状：节拍意图内嵌答案键（类型名 + fact ID），告知块给裸 ID 跃迁目标
CONTRACT = _contract(
    must_change=[CharacterChange(character_id="char_000001", field="knowledge",
                                 operation="update", target="fact_000001",
                                 expected_value="known")],
    required_events=[RequiredEvent(event_type="OBSERVES", description="张三看见印泥")])
SCENE = _scene(beats=[
    Beat(beat_id="bt_000000", seq=0, intent="建立读者对 fact_000001 的认知", beat_type="setup"),
    Beat(beat_id="bt_000001", seq=1, intent="OBSERVES fact_000001", beat_type="setup"),
    Beat(beat_id="bt_000002", seq=2, intent="过渡", beat_type="setup")])

# 冻结于 `dcf771f`（即产出 t1–t3 的 told 渲染路径）；改动该路径必须连带重跑并换哈希
TELL_GOLDEN_SHA256 = "571d02f30f523c0eb2035b53b560c3cbf7c16e615fa1206f3f496d234c11032f"


def _joined(arm: str) -> str:
    return "\n".join(m["content"] for m in scene_prompt(SCENE, CONTRACT, _state(), arm=arm))


def _beat_line(arm: str) -> str:
    return next(l for l in _joined(arm).split("\n") if l.startswith("节拍意图:"))


def _lines(text: str) -> list:
    return text.split("\n")


def test_arm_labels_are_the_four_versions():
    assert prompt_version("beats") == "v0-beats"
    assert prompt_version("stripped") == "v2-stripped"
    assert prompt_version("told") == "v1-told"
    assert prompt_version("persona") == "v1-told+persona"


def test_arm_a_differs_from_baseline_only_in_the_beat_line():
    """断言 1：臂 A（stripped）与 v0-beats 只差 `节拍意图` 一行，其余逐字节一致。"""
    a, base = _lines(_joined("stripped")), _lines(_joined("beats"))
    diff = [l for l in a if l not in base] + [l for l in base if l not in a]
    assert len(diff) == 2 and all(l.startswith("节拍意图:") for l in diff)


def test_arm_b_adds_only_the_two_summary_lines():
    """断言 2：v0-beats + 汇总两行 = 臂 B；系统提示逐字节不动。"""
    base, told = _joined("beats"), _joined("told")
    assert told.startswith(base)
    assert _lines(told)[len(_lines(base)):] == [
        "必须发生的跃迁: char_000001.knowledge update fact_000001 → known",
        "必须出现的事件类型: OBSERVES"]


def test_arm_c_adds_only_the_persona_rule():
    """断言 3：臂 C 与臂 B 的用户消息逐字节一致，系统消息只多 persona 一行。"""
    b = scene_prompt(SCENE, CONTRACT, _state(), arm="told")
    c = scene_prompt(SCENE, CONTRACT, _state(), arm="persona")
    assert c[1]["content"] == b[1]["content"]
    added = set(c[0]["content"].split("\n")) - set(b[0]["content"].split("\n"))
    assert len(added) == 1 and not any(tok in next(iter(added)) for tok in
                                       ("fact_", "char_", "OBSERVES"))


def test_arm_b_render_is_byte_identical_to_the_frozen_template():
    """断言 3b：臂 B ≡ t1–t3 模板（除版本标签）⇒ v3-B 可与 t1–t3 合并为 n=6。"""
    assert hashlib.sha256(_joined("told").encode("utf-8")).hexdigest() == TELL_GOLDEN_SHA256


def test_arm_a_beat_line_carries_no_event_type_and_no_id():
    """断言 4：臂 A 的节拍行不含 26 个事件类型 token 与任何 fact_/char_ ID——第一次真正的盲写。"""
    line = _beat_line("stripped")
    assert line != _beat_line("beats")
    for token in EventType.__args__:
        assert token not in line
    assert "fact_" not in line and "char_" not in line
