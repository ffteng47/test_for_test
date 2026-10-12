"""模型对照前的前置探针：这台端点上，每个候选模型**怎样**才肯直接给正文。

为什么先探：候选模型多半带思考链，而思考链落在哪儿各家不一样——有的落 `reasoning` 字段
（`content` 就干净），有的直接把思考散文写进 `content`。后者对 Writer 是致命的：
取料拿到的是「我现在要解决的问题是……」，不是小说正文，整条链的读数作废。

三条纪律，都是这一轮踩过才写下来的：
1. **开关必须按 `llm.py:112` 的线形发**——它是 `{**payload, **ep.extra_body}` 平铺，
   所以探针也必须平铺。嵌套成 `{"extra_body":{...}}` 时服务端把它当未知字段忽略，
   测出来的是「不开关」。
2. **`content` 非空不等于思考被关掉**。要同时看 `reasoning` 字段长度与 `finish_reason`：
   思考只是搬家（`content`→`reasoning`）时，它照旧吃 `max_tokens`，预算小就整段被截成空正文
   （qwen3:30b 的初筛十章空产出就是这么来的）。
3. **预算要给足**，否则把「预算截断」读成「开关生效/失效」。
"""
from __future__ import annotations

import json
import urllib.request

Q = "一个笼子里有鸡和兔，头共 35 个，脚共 94 只。问鸡和兔各几只？只给答案。"
# 平铺＝llm.py 的 `**ep.extra_body`，不是嵌套 extra_body 键
SWITCHES = (("不开关", {}),
            ("reasoning_effort=none", {"reasoning_effort": "none"}),
            ("think:false", {"think": False}))
BUDGET = 800


def _ask(base_url: str, model: str, extra: dict) -> dict:
    payload = {"model": model, "max_tokens": BUDGET,
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
                ch = d["choices"][0]
                content = (ch["message"].get("content") or "").strip()
                got[label] = (d.get("usage", {}).get("completion_tokens"), content, _clean(content),
                              len(ch["message"].get("reasoning") or ""),
                              str(ch.get("finish_reason") or ""))
            except Exception as e:                      # 端点离线/模型不在盘上，都要显式记
                got[label] = (None, f"报错 {type(e).__name__}: {e}", False, 0, "")
        rows.append({"model": m, "读数": got,
                     "生效开关": next((k for k, v in got.items() if v[2]), None)})
    return rows


def main() -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:11500/v1"
    models = sys.argv[2:] or ["qwen3:8b", "qwen3:14b", "qwen3.5:27b", "qwen3:30b",
                              "deepseek-r1:32b", "qwen2.5:14b"]
    print(f"端点 {base}｜预算 {BUDGET}")
    for row in probe(base, models):
        parts = []
        for k, (tok, content, clean, reason, finish) in row["读数"].items():
            tag = "✓" if clean and not reason else ("搬" if clean else "✗")
            parts.append(f"{k}: tok={tok} 思考={reason} {finish}「{content[:14] or '（空）'}」{tag}")
        flag = row["生效开关"]
        print(f"{row['model']:<16} " + " ｜ ".join(parts)
              + (f"\n{'':16} → 真关思考：{flag}" if flag else f"\n{'':16} → 无真开关"))
    print("图例：✓=content 干净且 reasoning 为空（真关掉）｜搬=content 干净但 reasoning 有货"
          "（只是搬家，仍占 max_tokens，Writer 预算小＝空正文）｜✗=散文仍进 content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
