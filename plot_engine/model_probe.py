"""模型对照前的前置探针：这台端点上，每个候选模型**怎样**才肯直接给正文。

为什么先探：候选模型多半带思考链，而思考链落在哪儿各家不一样——有的落 `reasoning_content`
（`content` 就干净），有的直接把思考散文写进 `content`。后者对 Writer 是致命的：
取料拿到的是「我现在要解决的问题是……」，不是小说正文，整条链的读数作废。
所以每个模型、每种开关都要单独问一遍鸡兔同笼（只要求 15 字内答案的题），
判据是**内容短且直接给数**——这才说明开关真的把散文从 content 里清出去了。
"""
from __future__ import annotations

import json
import urllib.request

Q = "一个笼子里有鸡和兔，头共 35 个，脚共 94 只。问鸡和兔各几只？只给答案。"
SWITCHES = (("不开关", {}),
            ("reasoning_effort=none", {"reasoning_effort": "none"}),
            ("think:false", {"extra_body": {"think": False}}))


def _ask(base_url: str, model: str, extra: dict) -> dict:
    payload = {"model": model, "max_tokens": 800,
               "messages": [{"role": "user", "content": Q}], **extra}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def _clean(text: str) -> bool:
    t = text.strip()
    return len(t) <= 40 and any(c.isdigit() for c in t) \
        and not any(k in t[:14] for k in ("问题", "设", "要解", "根据", "首先"))


def probe(base_url: str, models) -> list:
    rows = []
    for m in models:
        got = {}
        for label, extra in SWITCHES:
            try:
                d = _ask(base_url, m, extra)
                content = (d["choices"][0]["message"].get("content") or "").strip()
                got[label] = (d.get("usage", {}).get("completion_tokens"), content, _clean(content))
            except Exception as e:                      # 端点离线/模型不在盘上，都要显式记
                got[label] = (None, f"报错 {type(e).__name__}: {e}", False)
        rows.append({"model": m, "读数": got,
                     "生效开关": next((k for k, v in got.items() if v[2]), None)})
    return rows


def main() -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:11500/v1"
    models = sys.argv[2:] or ["qwen3:8b", "qwen3:14b", "qwen3.5:27b", "qwen3:30b",
                              "deepseek-r1:32b"]
    print(f"端点 {base}")
    for row in probe(base, models):
        line = "｜".join(f"{k} tok={v[0]}「{v[1][:20] or '（空）'}」{'' if v[2] else '✗'}"
                         for k, v in row["读数"].items())
        flag = f"✓ 用 {row['生效开关']}" if row["生效开关"] else "✗ 无生效开关（不进对照）"
        print(f"{row['model']:<16} {line} {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
