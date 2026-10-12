# POST /api/projects/add?title=... -> create empty workspace + auto-switch (spawned detached,
# same restart-safe pattern as /api/projects/switch). Idempotent.
import py_compile
import sys

APP = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
SRC = open(APP, encoding="utf-8").read()

if "/api/projects/add" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

ANCHOR = '@app.post("/api/projects/switch")'
ROUTE = '''@app.post("/api/projects/add")
def projects_add(title: str):
    # 新书=空工作区+自动切过去；切完在导入页上传 txt 即写入该书目录
    busy = [t for t in ("script", "review", "audio", "persona", "m4b_export",
                        "audacity_export", "lora_training", "dataset_gen")
            if process_state.get(t, {}).get("running")]
    if busy:
        raise HTTPException(status_code=409, detail="任务进行中，暂缓新建: " + ",".join(busy))
    import os as _os, sys as _sys, subprocess
    _bk = _os.path.join(ROOT_DIR, "backend")
    if _bk not in _sys.path:
        _sys.path.insert(0, _bk)
    from projects import create_project
    try:
        slug = create_project(title.strip())
    except SystemExit as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_dir = _os.path.join(ROOT_DIR, "logs")
    _os.makedirs(log_dir, exist_ok=True)
    log = open(_os.path.join(log_dir, "switch.log"), "a", encoding="utf-8")
    subprocess.Popen(["python3", "-u", "projects.py", "switch", slug], cwd=_bk,
                     stdout=log, stderr=log, start_new_session=True)
    return {"ok": True, "slug": slug, "switching": True}


''' + ANCHOR

if SRC.count(ANCHOR) != 1:
    print(f"ANCHOR_NOT_UNIQUE count={SRC.count(ANCHOR)}")
    sys.exit(1)

open(APP, "w", encoding="utf-8").write(SRC.replace(ANCHOR, ROUTE))
py_compile.compile(APP, doraise=True)
print("PATCH_OK")
