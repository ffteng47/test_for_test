# Serve the built Studio frontend (alexandria/studio/) at "/" and keep legacy UI at "/legacy".
# Idempotent: backs up app.py once, refuses to double-patch.
import os
import py_compile
import shutil
import sys

APP = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
SRC = open(APP, encoding="utf-8").read()

if "read_legacy_index" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

shutil.copy(APP, APP + ".bak_pre_studio")

MOUNT_ANCHOR = 'app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")'
MOUNT_ADD = MOUNT_ANCHOR + '''

STUDIO_DIR = os.path.join(ROOT_DIR, "studio")
STUDIO_ASSETS = os.path.join(STUDIO_DIR, "assets")
if os.path.isdir(STUDIO_ASSETS):
    app.mount("/assets", StaticFiles(directory=STUDIO_ASSETS), name="studio_assets")'''

ROOT_OLD = '''@app.get("/")
async def read_index():
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )'''

ROOT_NEW = '''@app.get("/")
async def read_index():
    studio_index = os.path.join(STUDIO_DIR, "index.html")
    target = studio_index if os.path.exists(studio_index) else os.path.join(STATIC_DIR, "index.html")
    return FileResponse(target, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/legacy")
async def read_legacy_index():
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )'''

for old, new, label in ((MOUNT_ANCHOR, MOUNT_ADD, "mount"), (ROOT_OLD, ROOT_NEW, "root")):
    if SRC.count(old) != 1:
        print(f"ANCHOR_NOT_UNIQUE:{label} count={SRC.count(old)}")
        sys.exit(1)
    SRC = SRC.replace(old, new)

open(APP, "w", encoding="utf-8").write(SRC)
py_compile.compile(APP, doraise=True)
print("PATCH_OK")
