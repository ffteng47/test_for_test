# Add GET /api/continuity serving the continuity checker report. Idempotent.
import py_compile
import sys

APP = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
SRC = open(APP, encoding="utf-8").read()

if "/api/continuity" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

import shutil
shutil.copy(APP, APP + ".bak_pre_continuity")

ANCHOR = '@app.get("/favicon.ico")'
ROUTE = '''@app.get("/api/continuity")
async def get_continuity():
    import continuity_check
    return continuity_check.check()

''' + ANCHOR

if SRC.count(ANCHOR) != 1:
    print(f"ANCHOR_NOT_UNIQUE count={SRC.count(ANCHOR)}")
    sys.exit(1)

open(APP, "w", encoding="utf-8").write(SRC.replace(ANCHOR, ROUTE))
py_compile.compile(APP, doraise=True)
print("PATCH_OK")
