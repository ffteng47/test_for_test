# 安装器（幂等）：voice_lab 记录更新接口加 name 字段 —— 实验室/仓库音频可手动重命名。
# 锚点：app/voice_lab.py 的 RecordUpdate 模型与 voice_lab_record_update 处理函数。
# 备份 .bak_pre_lab_record_name；py_compile 自检；重启主服务生效（§4.3 预检）。
import py_compile
import sys

PY = "/home/tff/software/novel-audiobook/alexandria/app/voice_lab.py"
A1 = '''class RecordUpdate(BaseModel):
    id: str
    tags: dict = {}
    text: str = None
    speaker: str = None
'''
B1 = A1 + "    name: str = None\n"
A2 = '''    if req.speaker is not None:
        hit["speaker"] = req.speaker
'''
B2 = A2 + '''    if req.name is not None:
        nm = req.name.strip()
        if len(nm) > 60:
            raise HTTPException(status_code=400, detail="name too long (max 60)")
        hit["name"] = nm
'''


def main():
    src = open(PY, encoding="utf-8").read()
    if 'if req.name is not None:' in src:
        print("TAG_ALREADY")
        return
    missing = [a for a in (A1, A2) if a not in src]
    if missing:
        sys.exit(f"ANCHOR_NOT_FOUND: {missing}")
    open(PY + ".bak_pre_lab_record_name", "w", encoding="utf-8").write(src)
    open(PY, "w", encoding="utf-8").write(src.replace(A1, B1, 1).replace(A2, B2, 1))
    try:
        py_compile.compile(PY, doraise=True)
    except py_compile.PyCompileError as e:
        import shutil
        shutil.move(PY + ".bak_pre_lab_record_name", PY)
        sys.exit(f"COMPILE_FAIL, rolled back: {e}")
    print("PATCHED")


if __name__ == "__main__":
    main()
