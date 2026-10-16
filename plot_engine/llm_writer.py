"""07 §4.4 Writer 缝：真实模型逐 Scene 写正文。

职责边界：Writer **只产叙事文本**，markup（hook / reader 标注）一律由
`compose_chapter_draft` 追加 —— 模型自带的 markup 会被剥掉，否则「恰好一条 hook」变成两条。
提示词**绝不把 `knowledge_forbidden` 的事实喂给模型**：禁令只写在系统提示的规则里，
禁条本身连 id 带命题一起从提示中抹除，免得我们自己造出 H5.7。
空产出一律抛 `WriterError`：让 `compose_chapter_draft` 记 `scene_failed`，
06 §4.1 才能以 Scene 为最小重写单位，而不是静默交出一章薄纸。
"""
from __future__ import annotations

import re
from typing import List, Optional, get_args

from plot_engine.llm import LlmClient
from plot_engine.models.contract import ChapterContract
from plot_engine.models.event import EventType
from plot_engine.models.sceneplan import Scene
from plot_engine.models.state import StoryState
from plot_engine.writer import SceneWriter

_MARKUP_RE = re.compile(r"<!--.*?-->", re.S)
_PARAS = re.compile(r"\n\s*\n")
# 臂 A 渲染层过滤器：`节拍意图` 是场景规划器写下的答案键（类型名 + 实体 ID），只在此抹掉，
# 不动 planner 文本 ⇒ plan 仍带 id，validator / 抽取通道输入不变，尺一字不动。
_EVENT_RE = re.compile("|".join(sorted(get_args(EventType), key=len, reverse=True)))
_ID_RE = re.compile(r"(?:fact|char|loc|item)_\d+")
_SPACES_RE = re.compile(r"\s+")


def _scrub_beat(intent: str) -> str:
    return _SPACES_RE.sub(" ", _ID_RE.sub("", _EVENT_RE.sub("", intent))).strip()


_PERSONA_RULE = ("同一角色的身份与立场全章保持一致：已设定为调查者或旁观者的角色不得被写成作案者本人，"
                 "阵营与人物关系不得无理由反转。")


class WriterError(RuntimeError):
    """本 Scene 没有可用文本（模型空回/全被剥掉/超长后为空）。"""


def _name(obj, raw_id: str) -> str:
    got = getattr(obj, "name", None)
    return f"{got}（{raw_id}）" if got else raw_id


def _vocab(scene: Scene, contract: ChapterContract, state: Optional[StoryState],
           *, scrub: bool = False) -> str:
    forbidden = set(contract.knowledge_forbidden)
    if state is None:
        people, facts = list(scene.characters), []
    else:
        people = [_name(state.characters.get(cid), cid) for cid in scene.characters]
        allowed = [f for f in state.facts.values()
                   if f.fact_id not in forbidden
                   and (not contract.knowledge_allowed
                        or f.fact_id in contract.knowledge_allowed)]
        facts = [f"{f.fact_id}: {f.proposition[:60]}" for f in allowed]
    loc = _name(state.locations.get(scene.location), scene.location) if state else scene.location
    intents = [b.intent for b in scene.beats]
    if scrub:
        intents = [s for s in (_scrub_beat(i) for i in intents) if s]
    beats = " / ".join(intents)
    lines = [f"场景: {scene.scene_id}｜地点: {loc}｜人物: {', '.join(people) or '（无）'}",
             f"本场景目的: {scene.purpose}", f"节拍意图: {beats or '（无）'}",
             f"本章目标: {contract.story_goal}｜目标张力 {scene.tension / 1000:.2f}"]
    if facts:
        lines.append("可以使用的事实: " + "；".join(facts))
    if state is not None:
        ledger = _established_ledger(state, forbidden)
        if ledger:
            lines.append(ledger)
    return "\n".join(lines)


def _established_ledger(state: StoryState, forbidden: set) -> str:
    """§3.4b（E25 台账注入）：列出各人物**已建立**的认知（fact→状态/强度），逼 Writer
    写新推进而不是重锚旧事实。ch09 六臂 0/6 首轮、抽到的 BELIEVES 全锚 F1——病相是无意识
    重锚上一章已建立的 fact，台账把「已经知道/相信到什么程度」显式交给模型。forbidden fact 不进。"""
    by_char: dict = {}
    for e in state.knowledge_ledger:
        if e.fact_id not in forbidden:
            by_char.setdefault(e.character_id, []).append(f"{e.fact_id}={e.knowledge_state}({e.strength})")
    for e in state.belief_ledger:
        if e.fact_id not in forbidden:
            by_char.setdefault(e.character_id, []).append(f"{e.fact_id}~{e.belief_state}({e.strength})")
    if not by_char:
        return ""
    seg = [f"{cid}：" + "、".join(v) for cid, v in sorted(by_char.items()) if v]
    return "已建立认知（勿重复锚定，写新的推进）: " + "；".join(seg)


def _told_lines(contract: ChapterContract) -> List[str]:
    """告知型配置（`v1-told`）：只给「作者大纲」，不给「答题卡」。

    红线（`docs/phase0-writer-prompt-ab.md` §3）：`knowledge_forbidden` 里的目标连条目一起抹掉，
    `expected_value` 之外的状态秘密不进提示。事件类型只给类型名，不给 description/payload。
    """
    forbidden = set(contract.knowledge_forbidden)
    lines = [f"必须发生的跃迁: {c.character_id}.{c.field} {c.operation} {c.target}"
             + (f" → {c.expected_value}" if c.expected_value is not None else "")
             for c in contract.must_change if c.target not in forbidden]
    types = sorted({e.event_type for e in contract.required_events})
    if types:
        lines.append("必须出现的事件类型: " + "、".join(types))
    return lines


ARMS = ("beats", "stripped", "told", "persona")

# Writer 输入面版本（§3.3 场级 700–1000 字规格 + §3.4b 已建立认知台账）：尺面戳，进 run.log 首行。
# 旧语料（无此戳 = Writer面 v0）不得与新语料同表比较。
WRITER_SURFACE = "w4-scene700-1000+ledger"

# §3.3（v4 定标：章长 2000–3000，夹具派生 3 场/章 ⇒ 场级 700–1000）。段数死规格已删——
# 无人判定的名义规格留着只会被违反。这是尺面：换规格 = 换尺，戳进 run.log 首行 `章长规格=`。
WRITER_SPEC = "w4-scene-700-1000"


def prompt_version(arm: str) -> str:
    """基线不叫 blind：`_vocab` 的 节拍意图 无条件带出事件类型与 fact ID（08 采样期实测）。"""
    return {"beats": "v0-beats", "stripped": "v2-stripped",
            "told": "v1-told", "persona": "v1-told+persona"}[arm]


def scene_prompt(scene: Scene, contract: ChapterContract,
                 state: Optional[StoryState] = None, *, min_chars: int = 700,
                 max_chars: int = 1000, arm: str = "beats",
                 directive: str = "") -> List[dict]:
    forbidden = set(contract.knowledge_forbidden)
    rules = [
        "你是悬疑长篇正文写手。只写本 Scene 的叙事文本。",
        # §3.3：段数死规格删掉（无人判定段数，留着只会被违反），改成字数区间硬要求。
        # 夹具每章 3 场 ⇒ 场级 700~1000 字 ≈ 章 2100~3000 字（docs/phase1-fixture-v4-design.md §1 定标）。
        f"写满 {min_chars}~{max_chars} 字（不含空行），宁长勿短；段与段之间空一行。",
        "不要输出任何 HTML 注释、标记、标题、小标题或元数据（如“本章悬念”）。",
        "不要提前揭露尚未到揭示时机的事实，也不要解释你写了什么。",
        "中文，第三人称，与既有世界设定保持一致。",
    ]
    if arm == "persona":
        rules.append(_PERSONA_RULE)
    body = _vocab(scene, contract, state, scrub=(arm == "stripped"))
    if arm in ("told", "persona"):
        lines = _told_lines(contract)
        if lines:
            body += "\n" + "\n".join(lines)
    if directive:
        # 06 §4.2 patch_write：缺失清单随补写轮下发（只在补写请求里出现，常规轮提示词一字不动）。
        body += "\n\n" + directive
    # 兜底：任何禁条 id 都不该出现在提示里（命题已被上面过滤，这里连 id 一起抹）
    for fid in forbidden:
        rules = [r.replace(fid, "（封锁）") for r in rules]
        body = body.replace(fid, "（封锁）")
    return [{"role": "system", "content": "\n".join(rules)},
            {"role": "user", "content": body}]


def _clean(raw: str, max_chars: int) -> str:
    text = _MARKUP_RE.sub("", raw)
    paras = [p.strip() for p in _PARAS.split(text.strip()) if p.strip()]
    kept: List[str] = []
    used = 0
    for p in paras:
        if kept and used + len(p) > max_chars:
            break
        kept.append(p)
        used += len(p)
    return "\n\n".join(kept)


def make_scene_writer(client: LlmClient, *, min_chars: int = 700, max_chars: int = 1000,
                      role: str = "writer", arm: str = "beats",
                      directive: str = "") -> SceneWriter:
    def write_scene(scene: Scene, contract: ChapterContract,
                    state: Optional[StoryState] = None) -> str:
        text, _usage = client.complete(role, scene_prompt(scene, contract, state,
                                                          min_chars=min_chars,
                                                          max_chars=max_chars, arm=arm,
                                                          directive=directive))
        draft = _clean(text or "", max_chars)
        if not draft:
            raise WriterError(f"scene {scene.scene_id} 无可用正文（模型返回空或被剥空）")
        return draft
    return write_scene
