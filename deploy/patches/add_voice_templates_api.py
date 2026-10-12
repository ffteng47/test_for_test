# 跨书音色/情绪指令模板库：GET/POST /api/voice_templates（落 alexandria/voice_templates/）
# 用法（服务器上）：cd alexandria && venv/bin/python deploy_patches/add_voice_templates_api.py
# 幂等：voice_lab.py 里已含 voice_templates 则打印 TAG_ALREADY 退出。装完需重启 app.py 生效。
import os
import py_compile
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))          # deploy_patches/
APP = os.path.abspath(os.path.join(BASE, ".."))            # alexandria/
LAB = os.path.join(APP, "app", "voice_lab.py")

BLOCK = '''

# ---- voice_templates：跨书音色/情绪指令模板库（安装器 add_voice_templates_api.py）----
import glob as _tpl_glob
import re as _tpl_re

_TPL_ID = _tpl_re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _tpl_dir():
    d = os.path.join(os.path.dirname(_ctx["designed_dir"]), "voice_templates")
    os.makedirs(d, exist_ok=True)
    return d


class TemplateReq(BaseModel):
    id: str = ""           # 留空自动生成 lab-<ts>；带 id 则原地覆盖（改名=新 id）
    kind: str = "voice"    # voice | emotion
    name: str
    text: str


@router.get("/api/voice_templates")
async def voice_templates_list(kind: str = ""):
    out = []
    for p in sorted(_tpl_glob.glob(os.path.join(_tpl_dir(), "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                t = json.load(f)
        except (OSError, ValueError):
            continue
        if kind and t.get("kind") != kind:
            continue
        t["id"] = os.path.basename(p)[:-5]
        out.append(t)
    return out


@router.post("/api/voice_templates")
async def voice_templates_put(req: TemplateReq):
    if req.kind not in ("voice", "emotion"):
        raise HTTPException(status_code=400, detail="kind 只能是 voice/emotion")
    tid = req.id.strip().lower() or f"lab-{int(time.time() * 1000)}"
    if not _TPL_ID.match(tid):
        raise HTTPException(status_code=400, detail=f"id 非法: {tid}")
    text = req.text.strip()
    if not text or len(text) > 4000:
        raise HTTPException(status_code=400, detail="text 需为 1~4000 字")
    path = os.path.join(_tpl_dir(), f"{tid}.json")
    tmp = path + ".tmp"
    rec = {"kind": req.kind, "name": (req.name.strip() or tid)[:60], "text": text}
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return {"id": tid, **rec}
'''


def main():
    src = open(LAB, encoding="utf-8").read()
    if "voice_templates" in src:
        print("TAG_ALREADY")
        return
    shutil.copy(LAB, LAB + ".bak_pre_voice_templates")
    with open(LAB, "a", encoding="utf-8") as f:
        f.write(BLOCK)
    py_compile.compile(LAB, doraise=True)
    print("OK 已追加 /api/voice_templates 到 app/voice_lab.py（备份 .bak_pre_voice_templates），重启 app.py 生效")


if __name__ == "__main__":
    main()
