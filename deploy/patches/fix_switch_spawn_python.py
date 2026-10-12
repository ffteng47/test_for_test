# Fix: /api/projects/switch spawned projects.py with sys.executable (venv python), which
# stop_novelTTS.sh pkills -> the switch process killed itself mid-restart. Use system python3 -u.
import py_compile

APP = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
SRC = open(APP, encoding="utf-8").read()
OLD = 'subprocess.Popen([sys.executable, "projects.py", "switch", slug], cwd=_bk,'
NEW = 'subprocess.Popen(["python3", "-u", "projects.py", "switch", slug], cwd=_bk,'

if NEW in SRC:
    print("ALREADY_PATCHED")
    raise SystemExit(0)
assert SRC.count(OLD) == 1, f"anchor count={SRC.count(OLD)}"
open(APP, "w", encoding="utf-8").write(SRC.replace(OLD, NEW))
py_compile.compile(APP, doraise=True)
print("PATCH_OK")
