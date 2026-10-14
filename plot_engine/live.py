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

from plot_engine.instr import InstrFlags, instr_id_for_lane, lane_identity_report
from plot_engine.llm import LlmClient, LlmRouter
from plot_engine.llm_extract import make_laned_channel, make_llm_channel, make_segmented_llm_channel
from plot_engine.models.contract import ChapterContract
from plot_engine.models.experiment import ChapterArtifacts
from plot_engine.models.sceneplan import ScenePlan
from plot_engine.models.state import StoryState

PROBE_TIMEOUT_S = 10


def _get_json(url: str, timeout: int, headers: Optional[Dict[str, str]] = None) -> dict:
    req = urllib.request.Request(url, headers={**(headers or {}),
                                              "Accept": "application/json"})
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
    # 带上该角色的认证头：本地/自建端点没有 key 时行为不变，但云端车道若不带
    # Authorization 就会永远 401 —— 于是"云端通不通"这件事根本测不出来，
    # 而护栏 1 要求仪器（含其可用性）必须先被度量。
    headers = {"Authorization": f"Bearer {ep.api_key}"} if ep.api_key else {}
    try:
        data = _get_json(url, PROBE_TIMEOUT_S, headers)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"模型端点不可达：{url}（{e}）"
    ids = [str(m.get("id", "?")) for m in (data.get("data") or [])]
    return True, f"{url} 可用模型: {', '.join(ids[:12]) or '（列表为空）'}"


def build_live_source(client: LlmClient, *,
                      contracts: Callable[[int, StoryState], ChapterContract],
                      plans: Callable[[ChapterContract, StoryState], ScenePlan],
                      use_segmented: bool = False,
                      flags: Optional[InstrFlags] = None,
                      ) -> Callable[[int, StoryState], ChapterArtifacts]:
    """逐章产物：契约/场景由调用方给（对**当前** State 派生，不是 genesis），
    Draft 与抽取现场交给真实模型。

    `draft=""` 让 `run_experiment` 走 `compose_chapter_draft` + 注入的 LLM SceneWriter；
    只挂 `llm_channel`（规则通道尚未实现 → 单通道置信度 700，仍高于 H8.2 隔离线）。
    `use_segmented=True` 则挂 instr-v2 分段通道（W1–W4，默认全开，可经 flags 回滚）。
    """
    def source(ch: int, cur: StoryState) -> ChapterArtifacts:
        if use_segmented:
            channel = make_segmented_llm_channel(client, flags=flags)
        else:
            channel = make_llm_channel(client)
        source.channels.append(channel)
        contract = contracts(ch, cur)
        return ChapterArtifacts(contract=contract, scene_plan=plans(contract, cur),
                                draft="", llm_channel=channel)

    source.channels: list = []
    return source


def build_laned_source(local_client: LlmClient,
                       cloud_client: Optional[LlmClient] = None, *,
                       contracts: Callable[[int, StoryState], ChapterContract],
                       plans: Callable[[ChapterContract, StoryState], ScenePlan],
                       lane: str = "local",
                       flags: Optional[InstrFlags] = None,
                       ) -> Callable[[int, StoryState], ChapterArtifacts]:
    """W6 双车道 source：两条车道共用同一套分段/修复/别名/默认值管道，
    只有 client（模型）不同。`source.lane_identity` 记下所用车道的完整身份
    （护栏 1：provider+model+version+解码配置），`source.instr` 为仪器戳。
    """
    fl = flags or InstrFlags(lane=lane)
    fl.lane = lane

    def source(ch: int, cur: StoryState) -> ChapterArtifacts:
        channel = make_laned_channel(local_client, cloud_client, lane=fl.lane,
                                     flags=fl)
        source.channels.append(channel)
        contract = contracts(ch, cur)
        return ChapterArtifacts(contract=contract, scene_plan=plans(contract, cur),
                                draft="", llm_channel=channel)

    source.channels: list = []
    probe = cloud_client if (lane == "cloud" and cloud_client is not None) else local_client
    source.lane_identity = lane_identity_report(probe, fl.lane if not (
        lane == "cloud" and cloud_client is None) else "local")
    source.instr = instr_id_for_lane(source.lane_identity.get("lane", "local"))
    return source


def extraction_diagnostics(channels) -> Dict[str, object]:
    """逐章通道的抽取汇总：产出数 + 规则提升数 + 坏料归因。跑完不丢，否则 §6 抽取桶无从解释。

    instr-v2 通道另带仪器账本（repaired/deduped/alias_mapped/alias_ambiguous/
    defaulted/segments_run/missing_windows/instr/lane），有则并入，无则缺省 0
    （旧单跑通道无这些属性，读数口径不变）。
    """
    malformed: Dict[str, int] = {}
    proposals = promoted = 0
    instr: Dict[str, object] = {"repaired": 0, "deduped": 0, "alias_mapped": 0,
                                "alias_ambiguous": 0, "defaulted": 0,
                                "segments_run": 0, "missing_windows": [],
                                "instr": "instr-v1", "stamps": [], "lanes": []}
    for channel in channels:
        proposals += channel.produced
        promoted += getattr(channel, "promoted", 0)
        for bad in channel.malformed:
            malformed[bad["reason"]] = malformed.get(bad["reason"], 0) + 1
        for k in ("repaired", "deduped", "alias_mapped", "alias_ambiguous",
                  "defaulted", "segments_run"):
            instr[k] = int(instr[k]) + int(getattr(channel, k, 0) or 0)
        instr["missing_windows"] = list(instr["missing_windows"]) + list(
            getattr(channel, "missing_windows", None) or [])
        # stamps = 仪器戳（instr-v2-local/cloud），lanes = 车道名（local/cloud）。
        # 两者分列：混在一起会把 "local" 当成一枚戳拼进 instr。
        stamp = getattr(channel, "instr", None) or getattr(channel, "instr_version", None)
        if stamp and stamp not in instr["stamps"]:
            instr["stamps"] = [*instr["stamps"], stamp]
        lane = getattr(channel, "lane", None)
        if lane and lane not in instr["lanes"]:
            instr["lanes"] = [*instr["lanes"], lane]
    if instr["stamps"]:
        instr["instr"] = "+".join(sorted(set(instr["stamps"])))
    return {"proposals": proposals, "promoted": promoted,
            "malformed": malformed, "chapters": len(channels), "instr": instr}
