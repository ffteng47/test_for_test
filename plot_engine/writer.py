"""Writer 整章 Draft 组装 + Scene 级重写缝（04 §8.4, 07 §4.4）。

Phase 0 网络无关：`scene_writer` 是注入式 `Callable[[Scene, ChapterContract, StoryState], str]`，
真实写手模型由调用方在实验期接入；本模块只负责**确定性组装**——
逐 scene 施加、异常隔离（仅失败 scene 重写，04 §8.4），末尾注入恰好一条 hook
与每条 reader_signal 的 reader 标注（07 §4.4），供 markup 通道回读。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from plot_engine.models.contract import ChapterContract
from plot_engine.models.sceneplan import Scene, ScenePlan
from plot_engine.models.state import StoryState

SceneWriter = Callable[[Scene, ChapterContract, Optional[StoryState]], str]

_PARA_SPLIT = re.compile(r"\n\s*\n")

# reader_signal.target_state → Draft markup 标注字面量；unaware 不产标注。
_SIGNAL_TO_MARKUP = {"knows": "reader_learns", "hinted": "reader_hinted",
                     "deceived": "reader_deceived"}


@dataclass
class DraftAssembly:
    draft: str
    scene_ok: List[str] = field(default_factory=list)
    scene_failed: List[str] = field(default_factory=list)


def _split_paras(fragment: str) -> List[str]:
    return [p.strip() for p in _PARA_SPLIT.split(fragment.strip()) if p.strip()]


def compose_chapter_draft(
    scene_plan: ScenePlan,
    contract: ChapterContract,
    state: Optional[StoryState],
    scene_writer: SceneWriter,
) -> DraftAssembly:
    """逐 scene 调 scene_writer；抛错仅记 failed 并跳过（不整章重写）。

    末尾先追加 reader 标注、再追加 hook，使 hook 落在最后一段（末 3 段内，07 §4.4）。
    """
    asm = DraftAssembly(draft="")
    paras: List[str] = []
    for scene in scene_plan.scenes:
        try:
            frag = scene_writer(scene, contract, state)
        except Exception:
            asm.scene_failed.append(scene.scene_id)
            continue
        asm.scene_ok.append(scene.scene_id)
        paras += _split_paras(frag)

    for rs in contract.reader_signals:
        kind = _SIGNAL_TO_MARKUP.get(rs.target_state)
        if kind is not None:
            paras.append(f"<!-- {kind}: {rs.fact_id} -->")
    paras.append(f"<!-- hook: {contract.ending.type} strength={contract.ending.strength} -->")

    asm.draft = "\n\n".join(paras)
    return asm
