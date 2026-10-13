# 安装器（幂等）：让上传的参考音频把 ASR 出的 ref_text 一并落盘。
# 现状：/api/clone_voices/upload 只在 manifest.json 记 {id,name,filename}，ASR 文本只活在
# 前端内存里，换个下拉样本就得重新转写。改两处 + 加一个回写端点：
#   1) upload 接 ref_text 表单字段并写进 manifest 条目
#   2) 新增 POST /api/clone_voices/ref_text：上传后 ASR 结果回写（list 直接读 manifest，自动带回）
# 锚点：app/app.py 的 clone_voices 路由块。备份 .bak_pre_clone_ref_text；py_compile 自检；重启主服务生效。
import py_compile
import shutil
import sys

PY = "/home/tff/software/novel-audiobook/alexandria/app/app.py"

A1 = '''@app.post("/api/clone_voices/upload")
async def clone_voices_upload(file: UploadFile = File(...)):
'''
B1 = '''@app.post("/api/clone_voices/upload")
async def clone_voices_upload(file: UploadFile = File(...), ref_text: str = Form("")):
'''

A2 = '''    manifest.append({
        "id": voice_id,
        "name": base_name,
        "filename": dest_filename,
    })
'''
B2 = '''    manifest.append({
        "id": voice_id,
        "name": base_name,
        "filename": dest_filename,
        "ref_text": ref_text,
    })
'''

A3 = '''    logger.info(f"Clone voice deleted: {voice_id}")
    return {"status": "deleted", "voice_id": voice_id}
'''
B3 = A3 + '''
class CloneRefText(BaseModel):
    id: str
    ref_text: str = ""

@app.post("/api/clone_voices/ref_text")
async def clone_voices_set_ref_text(req: CloneRefText):
    """回写参考音频的 ASR 转写：上传时转写还没跑，先落文件，转写完再补这条。"""
    manifest = _load_manifest(CLONE_VOICES_MANIFEST)
    entry = next((v for v in manifest if v["id"] == req.id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Clone voice not found")
    entry["ref_text"] = req.ref_text
    _save_manifest(CLONE_VOICES_MANIFEST, manifest)
    logger.info(f"Clone voice ref_text saved: {req.id}")
    return {"status": "saved", "id": req.id, "ref_text": req.ref_text}
'''

MARKER = '@app.post("/api/clone_voices/ref_text")'


def main():
    src = open(PY, encoding="utf-8").read()
    if MARKER in src:
        print("CLONE_REF_TEXT_ALREADY")
        return
    missing = [a for a in (A1, A2, A3) if a not in src]
    if missing:
        sys.exit(f"ANCHOR_NOT_FOUND: {missing}")
    assert "from fastapi import" in src and "Form" in src, "app.py 未导入 Form，需先补 from fastapi import Form"
    open(PY + ".bak_pre_clone_ref_text", "w", encoding="utf-8").write(src)
    patched = src.replace(A1, B1, 1).replace(A2, B2, 1).replace(A3, B3, 1)
    open(PY, "w", encoding="utf-8").write(patched)
    try:
        py_compile.compile(PY, doraise=True)
    except py_compile.PyCompileError as e:
        shutil.move(PY + ".bak_pre_clone_ref_text", PY)
        sys.exit(f"COMPILE_FAIL, rolled back: {e}")
    print("PATCHED")


if __name__ == "__main__":
    main()
