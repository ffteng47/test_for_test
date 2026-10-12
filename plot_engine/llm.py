"""可配置 LLM 接入层（08 §2 `model_router_config`）。

设计约束：
- **本地优先**：默认 base_url 是 `127.0.0.1`（Ollama 的 OpenAI 兼容端点），换 vLLM/云端只改配置，
  不改代码；不写死任何供应商。
- **按角色路由**：writer / extract / plan 各自一份 `ModelEndpoint`，可不同模型、不同温度。
- **可注入 transport**：测试与离线 CI 绝不发网络请求（Auto-Mode #6）。
- **温度定点 ×1000**：`temperature` 以整数存，线上再还原 float，避免浮点抖动改变采样（05 §5.5 精神）。
- **密钥只进 Header**：绝不进请求体——请求体会被写进 trace/报告。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from pydantic import BaseModel, Field

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"

# (url, payload, headers, timeout_s) -> 解析后的 JSON dict
Transport = Callable[[str, dict, Mapping[str, str], int], dict]


class LlmUnavailable(RuntimeError):
    """端点不可达/超时/非 2xx。与「模型答得不好」区分开：后者是内容问题，前者是接线问题。"""


class ModelEndpoint(BaseModel):
    """一个角色的模型配置。`api_key` 由 `api_key_env` 从环境解析，绝不写进配置文件。"""
    base_url: str = DEFAULT_LOCAL_BASE_URL
    model: str = "qwen2.5:14b"
    max_tokens: int = 1200
    temperature: int = Field(default=800, ge=0, le=2000)     # 定点 ×1000（0.8）
    usd_per_1k_tokens: float = 0.0                            # 本地模型 = 0（零边际成本）
    timeout_s: int = 300
    api_key_env: Optional[str] = None
    api_key: Optional[str] = None
    extra_body: Dict[str, Any] = Field(default_factory=dict)   # 供应商私有字段透传（如 think:false）


class LlmRouter(BaseModel):
    """角色 → 端点。实验配置里的 `model_router_config` 就是它的 `to_config()`。"""
    endpoints: Dict[str, ModelEndpoint] = Field(default_factory=dict)

    @classmethod
    def default(cls) -> "LlmRouter":
        return cls(endpoints={
            "writer": ModelEndpoint(),
            "extract": ModelEndpoint(max_tokens=800, temperature=200),
            "plan": ModelEndpoint(max_tokens=1500, temperature=500)})

    @classmethod
    def from_config(cls, config: Mapping[str, Mapping]) -> "LlmRouter":
        """`{role: {字段覆盖}}`。未写的字段取默认；`api_key_env` 在此处解析成 `api_key`。"""
        endpoints: Dict[str, ModelEndpoint] = {}
        for role, fields in config.items():
            ep = ModelEndpoint(**{k: v for k, v in dict(fields).items() if k != "api_key"})
            if ep.api_key_env:
                ep.api_key = os.environ.get(ep.api_key_env) or None
            endpoints[role] = ep
        return cls(endpoints=endpoints)

    def to_config(self) -> Dict[str, dict]:
        """可安全落盘/进报告的形态：只留变量名，绝不留密钥。"""
        return {role: ep.model_dump(exclude={"api_key"}) for role, ep in self.endpoints.items()}

    def roles(self) -> List[str]:
        return sorted(self.endpoints)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _urllib_transport(url: str, payload: dict, headers: Mapping[str, str],
                      timeout_s: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                headers={**dict(headers), "Content-Type": "application/json"},
                                method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:   # noqa: S310（本地/自建端点）
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        raise LlmUnavailable(f"{url} → HTTP {e.code}: {body}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LlmUnavailable(f"{url} 不可达（{e}）；本地模型需先加载，冷启动约 65s") from e


@dataclass
class CallDiag:
    """一次调用的接线读数：正文为空时它是唯一的证据（30b 初筛十章空产出，run.log 里一个字没有）。"""
    role: str
    model: str
    finish: str
    content_chars: int
    reasoning_chars: int
    max_tokens: int
    raw: str = ""          # 仅正文为空时留档的响应截断


class LlmClient:
    """OpenAI 兼容 `/chat/completions` 客户端 + token/成本累计（08 §3 成本字段的数据源）。"""

    def __init__(self, router: LlmRouter, *, transport: Optional[Transport] = None) -> None:
        self.router = router
        self._transport = transport or _urllib_transport
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.calls: List[CallDiag] = []

    def complete(self, role: str, messages: List[dict]) -> Tuple[str, Usage]:
        ep = self.router.endpoints[role]                    # 未配置角色 = 配置错误，直接抛
        payload = {"model": ep.model, "messages": messages,
                   "temperature": ep.temperature / 1000.0, "max_tokens": ep.max_tokens,
                   **ep.extra_body}
        headers = {"Authorization": f"Bearer {ep.api_key}"} if ep.api_key else {}
        resp = self._transport(f"{ep.base_url.rstrip('/')}/chat/completions",
                               payload, headers, ep.timeout_s)
        try:
            choice = resp["choices"][0]
            msg = choice["message"]
            text = msg["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LlmUnavailable(f"{ep.model} 响应缺少 choices：{str(resp)[:200]}") from e
        reasoning = msg.get("reasoning") or ""
        self.calls.append(CallDiag(role=role, model=ep.model,
                                   finish=str(choice.get("finish_reason") or ""),
                                   content_chars=len(text or ""),
                                   reasoning_chars=len(reasoning),
                                   max_tokens=ep.max_tokens,
                                   raw="" if text else str(resp)[:300]))
        u = resp.get("usage") or {}
        usage = Usage(int(u.get("prompt_tokens", 0) or 0), int(u.get("completion_tokens", 0) or 0))
        self.total_tokens += usage.total
        self.total_cost_usd += usage.total / 1000.0 * ep.usd_per_1k_tokens
        return text, usage

    def render_call_diagnostics(self) -> str:
        """接线摘要一行；只点名被截断或空正文的调用。全正常 ⇒ 只给计数。"""
        bad = [c for c in self.calls if not c.content_chars or c.finish == "length"]
        head = f"调用 {len(self.calls)} 次"
        if not bad:
            return head + "｜接线正常（无空正文、无截断）"
        return head + f"｜可疑 {len(bad)} 次：" + " ".join(
            f"[{c.role} {c.model} finish={c.finish} 正文={c.content_chars} "
            f"思考={c.reasoning_chars} 上限={c.max_tokens}]" for c in bad[:8])
