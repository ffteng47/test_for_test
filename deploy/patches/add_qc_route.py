# Add GET /api/qc serving SQLite-side QC (rules + ASR) per segment + totals. Idempotent.
# Data source: backend/*.db (noveldb) + rules_report.json. Read-only, no workspace writes.
import py_compile
import shutil
import sys

APP = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
SRC = open(APP, encoding="utf-8").read()

if "/api/qc" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

shutil.copy(APP, APP + ".bak_pre_qc")

ANCHOR = '@app.get("/api/continuity")'
ROUTE = '''@app.get("/api/qc")
def qc_report():
    # backend/ 与 app/ 同级；懒导入避免污染主进程启动
    import os as _os, sys as _sys, json as _json
    _bk = _os.path.join(ROOT_DIR, "backend")
    if _bk not in _sys.path:
        _sys.path.insert(0, _bk)
    from domain import workspace_paths
    from noveldb import Db, open_db
    paths = workspace_paths()
    db = Db(open_db(paths["db"]))
    row = db.con.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()
    if not row:
        return {"segments": [], "totals": {"pass": 0, "retry": 0, "unchecked": 0}}
    segs = [{"ord": s["ord"], "qc": s["qc"], "err": s["qc_err"]} for s in db.segments(row["id"])]
    totals = {"pass": sum(1 for s in segs if s["qc"] == "pass"),
              "retry": sum(1 for s in segs if s["qc"] == "retry"),
              "unchecked": sum(1 for s in segs if not s["qc"])}
    findings = []
    rp = _os.path.join(ROOT_DIR, "rules_report.json")
    if _os.path.exists(rp):
        findings = _json.load(open(rp, encoding="utf-8"))
    return {"segments": segs, "totals": totals, "findings": findings}


''' + ANCHOR

if SRC.count(ANCHOR) != 1:
    print(f"ANCHOR_NOT_UNIQUE count={SRC.count(ANCHOR)}")
    sys.exit(1)

open(APP, "w", encoding="utf-8").write(SRC.replace(ANCHOR, ROUTE))
py_compile.compile(APP, doraise=True)
print("PATCH_OK")
