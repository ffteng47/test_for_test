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
from typing import List, Optional

from plot_engine.llm import LlmClient
from plot_engine.models.contract import ChapterContract
from plot_engine.models.sceneplan import Scene
from plot_engine.models.state import StoryState
from plot_engine.writer import SceneWriter

_MARKUP_RE = re.compile(r"<!--.*?-->", re.S)
_PARAS = re.compile(r"\n\s*\n")


class WriterError(RuntimeError):
    """本 Scene 没有可用文本（模型空回/全被剥掉/超长后为空）。"""


def _name(obj, raw_id: str) -> str:
    got = getattr(obj, "name", None)
    return f"{got}（{raw_id}）" if got else raw_id


def _vocab(scene: Scene, contract: ChapterContract, state: Optional[StoryState]) -> str:
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
    beats = " / ".join(f"{b.intent}" for b in scene.beats)
    lines = [f"场景: {scene.scene_id}｜地点: {loc}｜人物: {', '.join(people) or '（无）'}",
             f"本场景目的: {scene.purpose}", f"节拍意图: {beats or '（无）'}",
             f"本章目标: {contract.story_goal}｜目标张力 {scene.tension / 1000:.2f}"]
    if facts:
        lines.append("可以使用的事实: " + "；".join(facts))
    return "\n".join(lines)


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


def prompt_version(told: bool) -> str:
    return "v1-told" if told else "v0-blind"


def scene_prompt(scene: Scene, contract: ChapterContract,
                 state: Optional[StoryState] = None, *, max_chars: int = 1200,
                 told: bool = False) -> List[dict]:
    forbidden = set(contract.knowledge_forbidden)
    rules = [
        "你是悬疑长篇正文写手。只写本 Scene 的叙事文本。",
        "写 2~4 个自然段，段与段之间空一行；总长不超过 "
        f"{max_chars} 字。",
        "不要输出任何 HTML 注释、标记、标题、小标题或元数据（如“本章悬念”）。",
        "不要提前揭露尚未到揭示时机的事实，也不要解释你写了什么。",
        "中文，第三人称，与既有世界设定保持一致。",
    ]
    body = _vocab(scene, contract, state)
    if told:
        lines = _told_lines(contract)
        if lines:
            body += "\n" + "\n".join(lines)
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


def make_scene_writer(client: LlmClient, *, max_chars: int = 1200,
                      role: str = "writer", told: bool = False) -> SceneWriter:
    def write_scene(scene: Scene, contract: ChapterContract,
                    state: Optional[StoryState] = None) -> str:
        text, _usage = client.complete(role, scene_prompt(scene, contract, state,
                                                          max_chars=max_chars, told=told))
        draft = _clean(text or "", max_chars)
        if not draft:
            raise WriterError(f"scene {scene.scene_id} 无可用正文（模型返回空或被剥空）")
        return draft
    return write_scene
