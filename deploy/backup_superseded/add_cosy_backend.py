# Voice Lab 接入第二个引擎（CosyVoice2 sidecar）：MODELS 增加 backend 字段，跨引擎调用走本机 HTTP。
# 为什么 sidecar：CosyVoice 锁 torch 2.3.1+cu121，生产 venv 是 2.7.0+cu128，同环境装不下。
# 幂等；前端无需改动，模型列表来自 /api/voice_lab/models。
import py_compile
import shutil
import sys

VL = "/home/tff/software/novel-audiobook/alexandria/app/voice_lab.py"
SRC = open(VL, encoding="utf-8").read()
if "cosy_clone" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

shutil.copy(VL, VL + ".bak_pre_cosy")

A1 = '''    "cv06":   {"model_id": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", "label": "CustomVoice 0.6B", "method": "custom"},
'''
ADD1 = A1 + '''
    # 跨引擎：本机 sidecar（ttslab/cosy_server.py :7861），method=clone 使其出现在“参考克隆”页签下
    "cosy_clone":    {"backend": "cosy", "model_id": "CosyVoice2-0.5B", "label": "CosyVoice2 克隆",
                      "method": "clone", "mode": "zero_shot",
                      "url": os.environ.get("COSY_TTS_URL", "http://127.0.0.1:7861/tts")},
    "cosy_instruct": {"backend": "cosy", "model_id": "CosyVoice2-0.5B", "label": "CosyVoice2 情感指令",
                      "method": "clone", "mode": "instruct",
                      "url": os.environ.get("COSY_TTS_URL", "http://127.0.0.1:7861/tts")},
'''

A2 = '''def _available(key):
    from tts import TTSEngine
    return TTSEngine._resolve_local_model_path(MODELS[key]["model_id"]) is not None
'''
ADD2 = '''def _available(key):
    cfg = MODELS[key]
    if cfg.get("backend"):
        lab = os.environ.get("TTS_LAB_MODELS", "/home/tff/software/novel-audiobook/ttslab/models")
        return os.path.isdir(os.path.join(lab, cfg["model_id"]))
    from tts import TTSEngine
    return TTSEngine._resolve_local_model_path(cfg["model_id"]) is not None
'''

A3 = "    model = _get_model(key)\n"
ADD3 = '    model = None if MODELS[key].get("backend") else _get_model(key)\n'

A4 = '        if method == "design":\n'
ADD4 = '''        if MODELS[key].get("backend") == "cosy":
            wavs, sr = _cosy_call(key, req)
        elif method == "design":
'''

HELPER = '''

def _cosy_call(key, req):
    """跨引擎调用 CosyVoice2 sidecar，返回 (audio_list, sr)，与 qwen 分支同形状。"""
    import requests

    cfg = MODELS[key]
    fname = os.path.basename(req.ref_audio)
    ref_path = os.path.join(_ctx["clone_dir"], fname)
    if not fname or not os.path.exists(ref_path):
        raise HTTPException(status_code=400, detail="ref_audio missing (upload to clone_voices first)")
    if cfg["mode"] == "zero_shot" and not req.ref_text.strip():
        raise HTTPException(status_code=400, detail="ref_text required for clone")
    if cfg["mode"] == "instruct" and not req.description.strip():
        raise HTTPException(status_code=400, detail="请填写附加风格指令（CosyVoice2 走 instruct2）")

    with open(ref_path, "rb") as f:
        raw = f.read()
    try:
        resp = requests.post(
            cfg["url"],
            data={"text": req.sample_text, "ref_text": req.ref_text,
                  "instruct": req.description, "mode": cfg["mode"]},
            files={"file": (fname, raw)}, timeout=900)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=(
            "CosyVoice2 sidecar 未启动：cd ~/software/novel-audiobook/ttslab && "
            "venvs/cosyvoice/bin/uvicorn cosy_server:app --port 7861")) from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])

    import io

    import soundfile as sf

    audio, sr = sf.read(io.BytesIO(resp.content), dtype="float32")
    return [audio], int(sr)
'''

out = SRC
for anchor, repl in ((A1, ADD1), (A2, ADD2), (A3, ADD3), (A4, ADD4)):
    if out.count(anchor) != 1:
        sys.exit(f"ANCHOR NOT UNIQUE: {anchor!r} count={out.count(anchor)}")
    out = out.replace(anchor, repl)
out = out.rstrip("\n") + HELPER

open(VL, "w", encoding="utf-8").write(out)
py_compile.compile(VL, doraise=True)
print("PATCHED", VL)
