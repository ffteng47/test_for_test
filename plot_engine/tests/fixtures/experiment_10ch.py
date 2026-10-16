"""确定性 10 章实验 `chapter_source`（08 Day 20–22 测试夹具，网络无关）。

**契约与场景不再手写**：这里是 `docs/phase0-live-run-10ch.md` backlog #1 的修复处——
一份**有内容的 ArcContract**（逐章张力、三个 turning point、十二章知识闸门、
十章逐章意图），Chapter Contract 与 ScenePlan 由 `plot_engine.derive` 按 04 §4.3 / 附录 B 派生。
于是每一章的约束真的不一样，10 章实验才开始测试「跨章推进」而不是一条约束重复十遍。

**逐章知识阶梯（backlog #1 / A）**：`must_change` 的语义是 Δ（04 §4.2「每条必须被对应 Event
实现」+ §5.2 W1 + 10 §4.3 映射表），不是章末谓词。所以每一步只声明**本章真的发生的那一次
跃迁**，并由本章事件流里一条同 field 的实现事件兑现；`add` 仅出现在事实首次建立的那一章，
此后写成 rank 更新（suspected→known）。第 8 步的 `must_change` 故意为空——契约必须允许
「本章不推进」这个合法形态。三个 turning point 落在阶梯的第 1/5/9 步，其
`required_event_types` 直接取那一步钉死的强制事件类型，H5.1 因此不可能自相矛盾。

**ladder-v4（v4.1 批次，§3.1+§3.2 收尾）**：
- 规模：4 有名人物（张三/李四/王五/赵六，各有 belief 线）、12 fact、3 locations、2 items、
  2 relationships、1 faction；10 章的 (人物, field, fact) 三元组互不相同、不回环。
- 多线：每章 2~3 条并行线在**不同人物对**上展开（多数章 must_change ≥2，王五/李四/赵六
  各自的知识与信念进各自角色的 ledger——H5.3 按 actor 匹配，逼抽取器认对人）。
- §3.2 收尾：ch08 式「纯再锚钉」清零（本章不推进 ⇒ 强制集为空）；其余钉全是**叙事模态本身**
  （亲眼看见/读到/当面告知/内心确认），derive 04 §4.2 守卫要求的 field 覆盖由这些钉自己满足。
- 定标（tff 2026-10-11，「有效出场」可机检定义）：**本章内有台词、行动、或改变了至少一条
  事件状态**才算出场，仅被提及名字不算。夹具侧的保证是静态的：每章 cast 从 must_change 的
  actor 与强制事件的 actors_involved 里来（derive `_contract_cast`），进不了 cast 的人物
  本来就进不了契约；正文侧的 H 系列按同一文本判定（待尺面裁定后进 validator）。

闸门不给 reveal 限期：夹具 Writer 是确定性的，要求它写不出的东西只会让离线演练一路 FAIL，
那就变成在测夹具而不是测管道。`defects` 把指定章改成 "leak"（追加一条建立禁止知识
fact_000002 的 OBSERVES）或 "dead"（本章事件全换成死人出场）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from plot_engine.derive import derive_chapter_contract, derive_scene_plan
from plot_engine.models.contract import ArcContract, ChapterContract
from plot_engine.models.entity import Character, Faction, Item, Location, Relationship
from plot_engine.models.experiment import ChapterArtifacts, ExperimentConfig
from plot_engine.models.fact import Fact
from plot_engine.models.proposal import EventProposal
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState

EPOCH = "epoch_0"
NOW = "2026-10-09T00:00:00Z"
# 阶梯版本进 run.log 第 1 行（与抽取尺戳同处）：**改 `_STEPS` 任意一项必须同时 bump 这里**。
# 没有这一行，新旧基线并列时「这一跑跑在哪版夹具上」只能靠 commit 时间倒推（docs/measurement-errata.md §四）。
# 戳进日志之前（含 v32r1–3、bo_* 、q3_14b_r* 、q25_11500_r*）的所有跑法一律是 ladder-v1。
# ladder-v3：唯一一处改动＝ch09 的类型钉（§3.2 首笔，一次一个因）。
# ladder-v4：§3.1 规模（4 人物/12 fact/3 地/2 物/2 关系/1 门派）+ §3.2 收尾（ch08 式纯再锚钉
# 清零、每钉都是叙事模态）+ 逐章三元组唯一不回环。六臂 lv3 读数见 docs/phase1-rebaseline-v33.md §7。
# ladder-v5：码批 v3.9 夹具侧——ch06 补钉「赵六亲眼看见」（Δ 期望 known，IS_TOLD 上限 believed，
# D10 rank 守卫要求钉自己够得着）。
# ladder-v5b：ch10 解禁改钉 OBSERVES→IS_TOLD（hidden 身份不能「亲眼看见」——3A 拦截旧形态，
# 同批 3B），Δ 期望随降 believed。lv4 及更早读数与新尺分表。
LADDER_VERSION = "ladder-v5b-ch10istold"
_ACTOR = "char_000001"          # 张三（调查者）
_LI = "char_000002"             # 李四（嫌疑人，objective_truth=False 的 F2 本体）
_WANG = "char_000003"           # 王五（守阁人）
_ZHAO = "char_000004"           # 赵六（杂役，线人）
_DEAD_ACTOR = "char_000009"
_F1, _F2, _F3, _F4 = "fact_000001", "fact_000002", "fact_000003", "fact_000004"
_F5, _F6, _F7, _F8 = "fact_000005", "fact_000006", "fact_000007", "fact_000008"
_F9, _F10, _F11, _F12 = "fact_000009", "fact_000010", "fact_000011", "fact_000012"
# H5.5 把章尾 hook 与 contract.ending.type 对齐 ⇒ 逐章意图只能在兼容 cliffhanger
# 的目标类型里变（04 §4.4）。
_GOAL_TYPES = ["revelation", "escalation", "confrontation"]
_GOALS = ["张三在藏宝阁验出印章是伪造的。", "阁簿缺了三页，守阁人却笃定钥匙没少。",
          "赵六说他那夜值守，张三听完没全信。", "密信笔迹像王五，李四第一个说信是伪造的。",
          "李四被看见与外客会饮，矛头转向宗门内部。", "印泥的来源指向城外，赵六下山来报。",
          "库房簿记上少了一把专用刻刀。", "一次回避比一句谎话更像回答。",
          "张三把印泥、缺页与夜值串成同一条线。", "结论逼近——有人否认听说过叛徒。"]
_FIX = json.loads((Path(__file__).parent / "traitor_arc.json").read_text(encoding="utf-8"))


# ---- 阶梯的一步 = 本章真的发生的一次跃迁 + 兑现它的事件 ---------------------------
# 事件默认挂在 _ACTOR 名下；多线章用 actor= 把跃迁记到别的角色 ledger 上
# （H5.3 按 actor+fact+field 匹配实现事件，「谁看见」必须真的是谁）。

def _obs(fact: str, actor: str = _ACTOR, method: str = "sight") -> Dict[str, Any]:
    return {"event_type": "OBSERVES", "fact": fact, "actor": actor, "confidence": 1000,
            "payload": {"fact_id": fact, "method": method}}


def _reads(fact: str, actor: str = _ACTOR) -> Dict[str, Any]:
    return {"event_type": "READS", "fact": fact, "actor": actor, "confidence": 900,
            "payload": {"fact_id": fact, "method": "ledger"}}


def _told(fact: str, actor: str = _ACTOR, by: str = "") -> Dict[str, Any]:
    """IS_TOLD 的 actor 是**听的人**（知识进谁的 ledger）；by 只进 actors_involved 供场景成互动。"""
    return {"event_type": "IS_TOLD", "fact": fact, "actor": actor, "with": by,
            "confidence": 900,
            "payload": {"fact_id": fact, "trust_level": 900, "message_strength": 900}}


def _infers(conclusion: str, evidence: List[str], actor: str = _ACTOR) -> Dict[str, Any]:
    return {"event_type": "INFERS", "fact": conclusion, "actor": actor, "confidence": 700,
            "payload": {"conclusion_fact_id": conclusion, "evidence_fact_ids": evidence}}


def _belief(event_type: str, fact: str, strength: int,
            actor: str = _ACTOR) -> Dict[str, Any]:
    return {"event_type": event_type, "fact": fact, "actor": actor, "confidence": strength,
            "payload": {"fact_id": fact, "belief_strength": strength}}


def _knows(op: str, fact: str, expected: str, actor: str = _ACTOR) -> Dict[str, Any]:
    return {"character_id": actor, "field": "knowledge", "operation": op,
            "target": fact, "expected_value": expected}


def _holds(op: str, fact: str, expected: str, actor: str = _ACTOR) -> Dict[str, Any]:
    return {"character_id": actor, "field": "belief", "operation": op,
            "target": fact, "expected_value": expected}


# expected_value 不超过该事件类型的 reducer 上限（03 §4.3/§5.1）：
# OBSERVES/READS→known，IS_TOLD→believed，INFERS→suspected；
# BELIEVES→believes，SUSPECTS→suspects，DOUBTS→doubts。
# 十章互不回环：每章的 (人物, field, fact) 三元组全库唯一（test_experiment_e2e 静态钉死）。
_STEPS: List[Dict[str, Any]] = [
    {"events": [_obs(_F3), _infers(_F1, [_F3])],
     "mandatory": [_obs(_F3)],                     # 钉「亲眼验印」；INFERS 是派生线，不钉
     "must_change": [_knows("add", _F3, "known"), _knows("add", _F1, "suspected")]},
    {"events": [_reads(_F5), _belief("BELIEVES", _F8, 700, _WANG)],
     "must_change": [_knows("add", _F5, "known"),
                     _holds("add", _F8, "believes", _WANG)]},
    {"events": [_told(_F6, by=_ZHAO), _belief("SUSPECTS", _F6, 500)],
     "must_change": [_knows("add", _F6, "believed"), _holds("add", _F6, "suspects")]},
    {"events": [_reads(_F7, _WANG), _belief("DOUBTS", _F7, 500, _LI)],
     "must_change": [_knows("add", _F7, "known", _WANG),
                     _holds("add", _F7, "doubts", _LI)]},
    {"events": [_obs(_F9), _belief("SUSPECTS", _F1, 500)],
     "must_change": [_knows("add", _F9, "known"), _holds("add", _F1, "suspects")]},
    {"events": [_obs(_F10, _ZHAO), _told(_F10, by=_ZHAO)],
     # 两钉都进 Arc 强制项：赵六的 Δ 期望 known，IS_TOLD 上限只有 believed——
     # 钉「亲眼看见」才让 D10 rank 守卫（1A）看得到 reachable 的实现事件。
     "mandatory": [_told(_F10, by=_ZHAO), _obs(_F10, _ZHAO)],
     "must_change": [_knows("add", _F10, "known", _ZHAO), _knows("add", _F10, "believed")]},
    {"events": [_reads(_F11), _belief("BELIEVES", _F3, 600, _WANG)],
     "must_change": [_knows("add", _F11, "known"),
                     _holds("add", _F3, "believes", _WANG)]},
    {"events": [_obs(_F3)], "mandatory": [],       # 本章不推进：合法形态；再锚旧事实不再钉成 Arc 强制项
     "must_change": []},
    {"events": [_infers(_F4, [_F10, _F6]), _belief("BELIEVES", _F4, 600)],
     # 两钉都是本章的叙事模态：把线串起来＝INFERS，内心确认＝BELIEVES。
     # derive 04 §4.2 守卫要求的 belief 族覆盖由 BELIEVES 钉自己满足（同 lv3 裁定）。
     "must_change": [_knows("add", _F4, "suspected"), _holds("add", _F4, "believes")]},
    {"events": [_told(_F2, by=_LI), _belief("DOUBTS", _F1, 400, _LI)],
     # 第 10 步解禁 fact_000002——但解禁形态是**听当事人当面否认**（IS_TOLD，上限 believed）：
     # hidden 档身份事实钉成「亲眼看见」是越界钉（3A 拦截的就是这个旧形态，ch10 教训）。
     "must_change": [_knows("add", _F2, "believed"),
                     _holds("add", _F1, "doubts", _LI)],
     "must_not_change": []},
]
# turning point 挂在阶梯上真的有对应强制事件的第 1/5/9 步（事件类型由那一步的钉给出）。
_TURNS = {1: ("revelation", "印章是伪造的"), 5: ("escalation", "矛头指向内部"),
          9: ("crisis", "串成一条线")}
# 闸门：fact 解禁章号 = 该 fact 首次被本章约束引用之前；F4 中段开闸（ch5 起对读者暗示）、
# F2 第 10 章解禁。hidden 阶段不产 reader_signal（04 §4.3 D9）。
_GATES = [(_F1, 1, "hinted"), (_F2, 10, "hidden"), (_F3, 1, "confirmed"), (_F4, 5, "hinted"),
          (_F5, 2, "hinted"), (_F6, 3, "hinted"), (_F7, 4, "hinted"), (_F8, 2, "hidden"),
          (_F9, 5, "hinted"), (_F10, 6, "hinted"), (_F11, 7, "hinted"), (_F12, 8, "hinted")]


def _step(ch: int) -> Dict[str, Any]:
    return _STEPS[(ch - 1) % len(_STEPS)]


def _mandatory(ch: int) -> List[Dict[str, Any]]:
    """本章钉成 Arc 强制项的事件：默认＝整步事件流；步可带 `mandatory` 覆盖（§3.2）。
    `events` 仍整条进离线抽取道与正文，只是不钉 required_events ⇒ 重复锚定不再吃类型彩票。"""
    step = _step(ch)
    return step.get("mandatory", step["events"])


def _actors(e: Dict[str, Any]) -> List[str]:
    return [a for a in [e.get("actor", _ACTOR), e.get("with", "")] if a]


def build_arc(chapters: int = 10) -> ArcContract:
    """逐章意图 + 张力曲线 + turning_points + knowledge_gates：契约的合法来源（04 C2）。"""
    intents = [{"chapter_no": ch,
                "story_goal": f"{_GOALS[(ch - 1) % len(_GOALS)]}（第 {ch} 章）",
                "story_goal_type": _GOAL_TYPES[ch % len(_GOAL_TYPES)],
                "ending": {"type": "cliffhanger", "strength": 500 + 100 * (ch % 5),
                           "description": "章尾悬念"},
                "must_change": _step(ch)["must_change"],
                "must_not_change": _step(ch).get("must_not_change", [
                    {"character_id": _ACTOR, "field": "knowledge", "operation": "update",
                     "target": _F2}]),
                "required_events": [{"event_type": e["event_type"],
                                     "description": f"{e['event_type']} {e['fact']}",
                                     "actors_involved": _actors(e)}
                                    for e in _mandatory(ch)]}
               for ch in range(1, chapters + 1)]
    return ArcContract(
        arc_id="arc_003", epoch=EPOCH, chapter_range=(1, chapters),
        tension_curve=[min(1000, 300 + 60 * ch) for ch in range(1, chapters + 1)],
        turning_points=[{"chapter": c, "type": t, "description": d,
                         "required_event_types": sorted({e["event_type"] for e in _mandatory(c)})}
                        for c, (t, d) in _TURNS.items() if c <= chapters],
        knowledge_gates=[{"fact_id": f, "allowed_after_chapter": a, "reveal_stage_target": s}
                         for f, a, s in _GATES if a <= chapters],
        reader_beats=intents, created_at=NOW)


def contract_for(arc: ArcContract, ch: int, state: StoryState) -> ChapterContract:
    return derive_chapter_contract(arc, ch, state, created_at=NOW)


def plan_for(contract: ChapterContract, state: StoryState) -> ScenePlan:
    return derive_scene_plan(contract, state, created_at=NOW)


def _draft(contract: ChapterContract) -> str:
    """正文按契约的 reader_signals 生成标注：W8 要命中什么，本章就标什么（夹具不该自己漏）。"""
    marks = [f"<!-- reader_{_MARK_KIND[s.target_state]}: {s.fact_id} -->"
             for s in contract.reader_signals]
    hook = f"<!-- hook: {contract.ending.type} strength={contract.ending.strength} -->"
    return "第{ch}章：张三凝视印章。\n\n".format(ch=contract.chapter_no) + \
        "\n\n".join(marks + [hook])


_MARK_KIND = {"knows": "learns", "hinted": "hinted", "deceived": "deceived"}


def _proposals(ch: int, defect: Optional[str]) -> List[EventProposal]:
    out: List[EventProposal] = []
    events = list(_step(ch)["events"])
    if defect == "leak":
        events = events + [_obs(_F2)]                    # 建立本章仍禁止的知识 → H5.7
    if defect == "no_nail":
        # 本章钉成 Arc 强制项的事件整条没写出来 → H5.1 + 与之配对的 H5.3（must_change 失去实现事件）
        nails = {m["event_type"] for m in _mandatory(ch)}
        events = [e for e in events if e["event_type"] not in nails]
    for i, e in enumerate(events):
        actor = _DEAD_ACTOR if defect == "dead" else e.get("actor", _ACTOR)
        out.append(EventProposal(
            proposed_event_type=e["event_type"], actor=actor, target=e["fact"], chapter=ch,
            seq=i, preconditions=[f"evt_{ch:08d}_000"] if e["event_type"] == "INFERS" and i else [],
            payload=e["payload"], confidence=e["confidence"], source_ref=f"para:{i + 4}",
            extraction_method="rule", extraction_confidence=1000))
    return out


def _channels(ch: int, defect: Optional[str] = None):
    def rule(*_a):
        return _proposals(ch, defect)

    def llm(*_a):
        return [p.model_copy(update={"extraction_method": "llm"}) for p in rule()]
    return rule, llm


def build_source(defects: Optional[Dict[int, str]] = None,
                 arc: Optional[ArcContract] = None):
    defects = defects or {}

    def src(ch: int, cur: StoryState) -> ChapterArtifacts:
        contract = contract_for(arc or build_arc(), ch, cur)
        rule, llm = _channels(ch, defects.get(ch))
        return ChapterArtifacts(contract=contract, scene_plan=plan_for(contract, cur),
                                draft=_draft(contract), rule_channel=rule, llm_channel=llm)
    return src


# ---- v4 世界表（§3.1 规模门槛；traitor_arc.json 被 8 个 golden/单测共用，一字不动，
# 扩容全部在这里程序化追加）--------------------------------------------------------

def _char(cid: str, name: str) -> Character:
    return Character(character_id=cid, name=name, status="alive", faction_id="fac_00001",
                     current_location="loc_000012", introduced_at_chapter=1, epoch=EPOCH)


def _fact(fid: str, prop: str, canon: str, ftype: str = "existence",
          objective: str = "true", stage: str = "hinted") -> Fact:
    return Fact(fact_id=fid, fact_type=ftype, proposition=prop, canonical_form=canon,
                narrative_truth="unknown", objective_truth=objective, reveal_stage=stage,
                defined_at_chapter=1, epoch=EPOCH)


_NEW_CHARS = {_LI: _char(_LI, "李四"), _WANG: _char(_WANG, "王五"), _ZHAO: _char(_ZHAO, "赵六")}

_NEW_FACTS = {
    _F5: _fact(_F5, "藏宝阁簿记缺了三页", "ledger_missing_pages(pavilion_17)"),
    _F6: _fact(_F6, "赵六那夜在藏宝阁值守", "on_duty(zhao_liu, night_17)", "event"),
    _F7: _fact(_F7, "密信笔迹与王五手书同源", "handwriting_like(wang_wu, secret_letter)"),
    _F8: _fact(_F8, "藏宝阁钥匙一共有两把", "two_keys_exist(pavilion_17)"),
    _F9: _fact(_F9, "李四与外客在山下会饮", "drinks_with_outsider(li_si)", "event"),
    _F10: _fact(_F10, "印泥出自城外商号", "inkpad_from_shop_outside(city_gate)"),
    _F11: _fact(_F11, "伪造官印需要专用刻刀", "forgery_requires_knife(seal_17)"),
    _F12: _fact(_F12, "王五欠着外债", "debt_owed(wang_wu)"),
}

_NEW_LOCATIONS = {
    "loc_000013": Location(location_id="loc_000013", name="城外印泥铺",
                           introduced_at_chapter=1, epoch=EPOCH),
    "loc_000014": Location(location_id="loc_000014", name="山下酒肆",
                           introduced_at_chapter=1, epoch=EPOCH),
}

_NEW_ITEMS = {
    "item_000001": Item(item_id="item_000001", name="专用刻刀", item_type="equipment",
                        unique=True, stackable=False, introduced_at_chapter=1, epoch=EPOCH),
    "item_000002": Item(item_id="item_000002", name="藏宝阁钥匙", item_type="key",
                        unique=False, stackable=True, introduced_at_chapter=1, epoch=EPOCH),
}

_NEW_RELATIONSHIPS = [
    Relationship(relationship_id="rel_000001", from_character=_ACTOR, to_character=_LI,
                 type="master_disciple", strength=600, trust=600, symmetric=True,
                 established_at_chapter=1, epoch=EPOCH),
    Relationship(relationship_id="rel_000002", from_character=_WANG, to_character=_ACTOR,
                 type="colleague", strength=500, trust=400, symmetric=True,
                 established_at_chapter=1, epoch=EPOCH),
]

_NEW_FACTIONS = {
    "fac_00001": Faction(faction_id="fac_00001", name="青嶝宗",
                               members=[_ACTOR, _LI, _WANG, _ZHAO],
                               controlled_locations=["loc_000012"],
                               introduced_at_chapter=1, epoch=EPOCH),
}


def make_config(chapters: int = 10) -> ExperimentConfig:
    genesis = StoryState(**{**_FIX["genesis"], "state_hash": ""})
    genesis = genesis.model_copy(update={
        "characters": {**genesis.characters, **_NEW_CHARS,
                       _DEAD_ACTOR: Character(character_id=_DEAD_ACTOR, name="旧主",
                                              status="dead", death_chapter=1,
                                              introduced_at_chapter=1, epoch=EPOCH)},
        "facts": {**genesis.facts, _F4: _fact(
            _F4, "守阁的人碰过印泥", "touched_inkpad(pavilion_keeper)"), **_NEW_FACTS},
        "locations": {**genesis.locations, **_NEW_LOCATIONS},
        "items": _NEW_ITEMS,
        "relationships": list(_NEW_RELATIONSHIPS),
        "factions": _NEW_FACTIONS})
    return ExperimentConfig(story_id="s1", chapters=chapters, arc_contract=build_arc(chapters),
                            initial_state=genesis, seed=42, epoch=EPOCH)


def dummy_writer(scene, contract, state) -> str:
    return scene.scene_id
