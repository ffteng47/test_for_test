# 导入自动绑音：按音色模板（voice_templates/<slug>__<ROLE>.json）的中文/英文描述，
# 在 designed_voices/*_meta.json 与既有 projects/*/voice_config.json 里找"描述全等"的现成声音，
# 命中即写 clone 绑定（type/ref_audio/ref_text/description），未造的列入 pending。
# 用法（服务器）：cd alexandria && venv/bin/python deploy_patches/voice_bind.py --slug shuxue [--apply]
#                venv/bin/python deploy_patches/voice_bind.py --demo
import argparse
import glob
import json
import os
import re
import shutil
import time

ALEX = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def build_index():
    """norm(描述) -> {ref_audio, ref_text, source}；meta 先入，任一成书 voice_config 覆盖（实绑过的优先）。"""
    idx = {}
    metas = []
    for p in glob.glob(os.path.join(ALEX, "designed_voices", "*_meta.json")):
        m = _load(p, {})
        ts = os.path.getmtime(p)
        if m.get("description") and m.get("preview"):
            metas.append((ts, norm(m["description"]),
                          {"ref_audio": m["preview"], "ref_text": m.get("ref_text", ""), "source": os.path.basename(p)}))
    for _, k, v in sorted(metas):
        idx[k] = v
    for p in glob.glob(os.path.join(ALEX, "projects", "*", "voice_config.json")):
        for role, c in (_load(p, {}) or {}).items():
            if isinstance(c, dict) and c.get("type") == "clone" and c.get("ref_audio") and c.get("description"):
                idx[norm(c["description"])] = {"ref_audio": c["ref_audio"], "ref_text": c.get("ref_text", ""),
                                               "source": f"proven:{os.path.basename(os.path.dirname(p))}/{role}"}
    return idx


def templates_for(slug):
    """{ROLE: 描述文本}，来自 voice_templates/<slug>__<ROLE>.json（kind=voice）。"""
    out = {}
    for p in glob.glob(os.path.join(ALEX, "voice_templates", f"{slug}__*.json")):
        t = _load(p, {})
        if t.get("kind", "voice") == "voice":
            out[os.path.basename(p)[:-5][len(slug) + 2:]] = t.get("text", "")
    return out


def bind(speakers, config, tpl, idx):
    """返回 (新增绑定 dict, pending 列表)。纯函数，--demo 直接喂夹具。"""
    add, pending = {}, []
    for s in sorted(speakers):
        if s in config:
            continue
        desc = tpl.get(s)
        if not desc:
            pending.append({"speaker": s, "reason": "无音色模板（voices/ 未提供描述）"})
            continue
        hit = idx.get(norm(desc))
        if not hit:
            pending.append({"speaker": s, "reason": "有模板但库里没有该描述的声音，需先在实验室造声"})
            continue
        add[s] = {"type": "clone", "ref_audio": hit["ref_audio"],
                  "ref_text": hit["ref_text"], "description": desc}
    return add, pending


def demo():
    tpl = {"A": "warm female voice", "B": "old raspy male", "C": "never designed"}
    idx = {norm("warm female voice"): {"ref_audio": "designed_voices/a.wav", "ref_text": "x", "source": "m"},
           norm("old raspy male"): {"ref_audio": "designed_voices/b.wav", "ref_text": "y", "source": "m"}}
    cfg = {"B": {"type": "clone"}}  # B 已绑 → 不重复动
    add, pending = bind({"A", "B", "C", "D"}, cfg, tpl, idx)
    assert add == {"A": {"type": "clone", "ref_audio": "designed_voices/a.wav", "ref_text": "x",
                         "description": "warm female voice"}}, add
    reasons = {p["speaker"]: p["reason"] for p in pending}
    assert reasons == {"C": "有模板但库里没有该描述的声音，需先在实验室造声",
                       "D": "无音色模板（voices/ 未提供描述）"}, reasons
    print("DEMO_OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--apply", action="store_true", help="写 voice_config.json（默认 dry-run）")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        demo()
        return
    book = os.path.join(ALEX, "projects", a.slug)
    script = _load(os.path.join(book, "annotated_script.json"), [])
    if not script:
        raise SystemExit(f"{book}/annotated_script.json 缺失或为空")
    speakers = {e.get("speaker") for e in script}
    cfg = _load(os.path.join(book, "voice_config.json"), {}) or {}
    add, pending = bind(speakers, cfg, templates_for(a.slug), build_index())
    if add and a.apply:
        vc = os.path.join(book, "voice_config.json")
        if os.path.exists(vc):
            shutil.copy(vc, vc + f".bak_{time.strftime('%y%m%d_%H%M%S')}")
        cfg.update(add)
        tmp = os.path.join(book, "voice_config.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(book, "voice_config.json"))
    print(json.dumps({"bound": sorted(add), "pending": pending, "applied": bool(add and a.apply)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
