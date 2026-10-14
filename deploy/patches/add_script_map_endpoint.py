# 安装器（幂等）：新增只读端点 GET /api/script_map —— 分集映射。
# E-books 导入产出的 script_map.json（episodes 列表 + 每段 chunk 的 episode 号）此前
# 只有导入脚本自己看得见，前端拿不到，剧本工作台只能挂死一段假文案。
# 锚点：app/app.py 的 @app.get("/api/chunks")。备份 .bak_pre_script_map；py_compile 自检；
# 重启主服务生效（§4.3 预检：确认无任务在跑再重启）。
import py_compile
import sys

PY = "/home/tff/software/novel-audiobook/alexandria/app/app.py"
A1 = '''@app.get("/api/chunks")
async def get_chunks():
    chunks = project_manager.load_chunks()
    return chunks
'''
B1 = A1 + '''

@app.get("/api/script_map")
async def get_script_map():
    """分集映射：episodes + 每段所属集号（E-books 导入的 script_map.json）。"""
    d = os.path.dirname(os.path.realpath(project_manager.script_path))
    p = os.path.join(d, "script_map.json")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="script_map.json not found")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"script_map.json unreadable: {e}")
'''


def main():
    src = open(PY, encoding="utf-8").read()
    if '"/api/script_map"' in src:
        print("TAG_ALREADY")
        return
    if A1 not in src:
        sys.exit("ANCHOR_NOT_FOUND")
    open(PY + ".bak_pre_script_map", "w", encoding="utf-8").write(src)
    open(PY, "w", encoding="utf-8").write(src.replace(A1, B1, 1))
    try:
        py_compile.compile(PY, doraise=True)
    except py_compile.PyCompileError as e:
        import shutil
        shutil.move(PY + ".bak_pre_script_map", PY)
        sys.exit(f"COMPILE_FAIL, rolled back: {e}")
    print("PATCHED")


if __name__ == "__main__":
    main()
