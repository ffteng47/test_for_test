"""真实模型接线（08 §2 `model_router_config` / §3 成本字段）。

只做**接线**：不碰管道、不加 HARD 判据（08 §10 I1/I2）。
默认指向本机回环 Ollama；换 vLLM/其它端点是配置变更（`base_url`），不是代码变更。
`check_reachable` 只发一个轻量 GET `/v1/models`：先确认接线通，再决定要不要花 45 分钟跑 10 章。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional, Tuple

from plot_engine.llm import LlmClient, LlmRouter
from plot_engine.llm_extract import make_llm_channel
from plot_engine.models.contract import ChapterContract
from plot_engine.models.experiment import ChapterArtifacts
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState

PROBE_TIMEOUT_S = 10


def _get_json(url: str, timeout: int) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:      # noqa: S310（本机/自建端点）
        return json.loads(resp.read().decode("utf-8"))


def build_client(config: Optional[Dict[str, Dict]] = None) -> LlmClient:
    """`config` 为空 → 本地默认三角色；否则 `{role: {字段覆盖}}`。"""
    router = LlmRouter.from_config(config) if config else LlmRouter.default()
    return LlmClient(router)


def check_reachable(client: LlmClient) -> Tuple[bool, str]:
    ep = next(iter(client.router.endpoints.values()), None)
    if ep is None:
        return False, "没有配置任何模型角色（model_router_config 为空）"
    url = f"{ep.base_url.rstrip('/')}/models"
    try:
        data = _get_json(url, PROBE_TIMEOUT_S)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"模型端点不可达：{url}（{e}）"
    ids = [str(m.get("id", "?")) for m in (data.get("data") or [])]
    return True, f"{url} 可用模型: {', '.join(ids[:12]) or '（列表为空）'}"


def build_live_source(client: LlmClient, *,
                      contracts: Callable[[int], ChapterContract],
                      plans: Callable[[int], ScenePlan]
                      ) -> Callable[[int, StoryState], ChapterArtifacts]:
    """逐章产物：契约/场景由调用方给，Draft 与抽取现场交给真实模型。

    `draft=""` 让 `run_experiment` 走 `compose_chapter_draft` + 注入的 LLM SceneWriter；
    只挂 `llm_channel`（规则通道尚未实现 → 单通道置信度 700，仍高于 H8.2 隔离线）。
    """
    def source(ch: int, cur: StoryState) -> ChapterArtifacts:
        return ChapterArtifacts(contract=contracts(ch), scene_plan=plans(ch), draft="",
                                llm_channel=make_llm_channel(client))
    return source
