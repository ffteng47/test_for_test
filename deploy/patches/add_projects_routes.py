# Multi-project workspace switching over HTTP (task #14). Idempotent; combines two edits:
#  1) v2 of /api/qc: resolve project via domain.active_project_id (registry-aware), not first row.
#  2) New GET /api/projects + POST /api/projects/switch?slug=... (busy-guarded, detached spawn,
#     because a switch restarts this very service).
# Anchor: the existing '@app.get("/api/qc")' route.
import py_compile
import shutil
import sys

APP = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
SRC = open(APP, encoding="utf-8").read()

if "/api/projects" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

OLD_QC_PID = '    row = db.con.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()'
NEW_QC_PID = ('    from domain import active_project_id\n'
              '    _pid = active_project_id(db.con)')
OLD_QC_USE = 'db.segments(row["id"])'
NEW_QC_USE = "db.segments(_pid)"
OLD_QC_NONE = "    if not row:"
NEW_QC_NONE = "    if _pid is None:"

if SRC.count(OLD_QC_PID) == 1 and SRC.count(OLD_QC_USE) == 1 and SRC.count(OLD_QC_NONE) == 1:
    SRC = (SRC.replace(OLD_QC_PID, NEW_QC_PID)
              .replace(OLD_QC_USE, NEW_QC_USE)
              .replace(OLD_QC_NONE, NEW_QC_NONE))
else:
    print("QC_V2_ANCHOR_NOT_FOUND")
    sys.exit(1)

shutil.copy(APP, APP + ".bak_pre_projects")

ANCHOR = '@app.get("/api/qc")'
ROUTE = '''@app.get("/api/projects")
def projects_list():
    # 多书工作区：注册表(projects.json) + 每书段数(按 title 关联 DB 项目)
    import os as _os, sys as _sys, json as _json
    _bk = _os.path.join(ROOT_DIR, "backend")
    if _bk not in _sys.path:
        _sys.path.insert(0, _bk)
    from domain import registry, workspace_paths
    from noveldb import Db, open_db
    reg = registry()
    active = reg.get("active")
    projects = []
    try:
        db = Db(open_db(workspace_paths()["db"]))
        counts = {r["title"]: r["n"] for r in db.con.execute(
            "SELECT p.title, (SELECT COUNT(*) FROM segments s WHERE s.project_id=p.id) n "
            "FROM projects p")}
    except Exception:
        counts = {}
    for slug, meta in sorted((reg.get("projects") or {}).items()):
        projects.append({"slug": slug, "title": meta.get("title"),
                         "active": slug == active,
                         "segments": counts.get(meta.get("title"), 0)})
    return {"active": active, "projects": projects}


@app.post("/api/projects/switch")
def projects_switch(slug: str):
    # 切换会重启本服务，只能派生独立进程异步执行；前端轮询健康后刷新。
    busy = [t for t in ("script", "review", "audio", "persona", "m4b_export",
                        "audacity_export", "lora_training", "dataset_gen")
            if process_state.get(t, {}).get("running")]
    if busy:
        raise HTTPException(status_code=409, detail="任务进行中，暂缓切换: " + ",".join(busy))
    import os as _os, subprocess
    reg_path = _os.path.join(ROOT_DIR, "projects.json")
    if not _os.path.exists(reg_path):
        raise HTTPException(status_code=409, detail="尚无项目注册（后端先 projects.py adopt）")
    import json as _json
    reg = _json.load(open(reg_path, encoding="utf-8"))
    if slug not in (reg.get("projects") or {}):
        raise HTTPException(status_code=404, detail="未知项目 " + slug)
    _bk = _os.path.join(ROOT_DIR, "backend")
    log_dir = _os.path.join(ROOT_DIR, "logs")
    _os.makedirs(log_dir, exist_ok=True)
    log = open(_os.path.join(log_dir, "switch.log"), "a", encoding="utf-8")
    # 必须用系统 python3：stop 脚本会 pkill venv/bin/python，用 venv 起就是自杀。
    subprocess.Popen(['python3', '-u', 'projects.py', 'switch', slug], cwd=_bk,
                     stdout=log, stderr=log, start_new_session=True)
    return {"ok": True, "switching": slug}


''' + ANCHOR

if SRC.count(ANCHOR) != 1:
    print(f"ANCHOR_NOT_UNIQUE count={SRC.count(ANCHOR)}")
    sys.exit(1)

open(APP, "w", encoding="utf-8").write(SRC.replace(ANCHOR, ROUTE))
py_compile.compile(APP, doraise=True)
print("PATCH_OK")
