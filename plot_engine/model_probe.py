"""模型对照前的前置探针：这台端点上，每个候选模型吃不吃 `reasoning_effort: none`。

为什么先探：实测五个模型在**不带**该参数时都把 200 token 预算花在思考上、`content` 为空
（`qwen3:8b/14b/30b、qwen3.5:27b、deepseek-r1:32b` 全中）。空正文进 Writer 就是 `WriterError`，
整条链当场停；更糟的是「带参数的那组」和「不带参数的对照组」比出来的不是模型差异，是开关差异。
所以对照实验开始前，每个模型都要单独确认：关掉思考之后**能给出答案**，且 token 数明显掉下来。
"""
from __future__ import annotations

import json
import urllib.request

Q = "一个笼子里有鸡和兔，头共 35 个，脚共 94 只。问鸡和兔各几只？只给答案。"


def _ask(base_url: str, model: str, extra: dict) -> dict:
    payload = {"model": model, "max_tokens": 200,
               "messages": [{"role": "user", "content": Q}], **extra}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def probe(base_url: str, models) -> list:
    rows = []
    for m in models:
        got = {}
        for label, extra in (("默认", {}), ("关思考", {"reasoning_effort": "none"})):
            try:
                d = _ask(base_url, m, extra)
                msg = d["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                got[label] = (d.get("usage", {}).get("completion_tokens"), content[:24] or "（空）")
            except Exception as e:                      # 端点离线/模型不在盘上，都要显式记
                got[label] = (None, f"报错 {type(e).__name__}: {e}")
        on, off = got["默认"], got["关思考"]
        rows.append({"model": m, "默认": on, "关思考": off,
                     "可用": bool(off[1]) and not off[1].startswith("报错")
                             and (off[0] or 0) < (on[0] or 10 ** 6)})
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
        flag = "✓ 可进对照" if row["可用"] else "✗ 不许进对照（开关没生效或答不出）"
        print(f"{row['model']:<16} 默认 tok={row['默认'][0]} 答「{row['默认'][1]}」｜"
              f"关思考 tok={row['关思考'][0]} 答「{row['关思考'][1]}」 {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
