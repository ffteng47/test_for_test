"""IndexTTS-2 sidecar：与生产 venv 隔离（本引擎要 torch2.8 + py3.11，生产 venv 是 3.12）。

启动：venvs/indextts311/bin/uvicorn indextts_server:app --host 127.0.0.1 --port 7862
设备：INDEX_DEVICE=cuda 走显卡（~6G 空闲显存），默认 cpu。
接口：POST /tts -> audio/wav 字节（契约同 cosy_server.py：text/instruct/seed + ref 音频）
情感：不吃模型私有格式，自由 instruct 先经 backend/emotion_map.py 折成规范
      (emotion, intensity)，再摊平为 IndexTTS-2 的 8 维 emo_vector。
"""
import os
import sys
import tempfile

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(LAB, "repos", "index-tts"))
# 词表唯一来源是 backend/emotion_map.py（ttslab 与 alexandria 的公共父目录下）
sys.path.insert(0, os.path.join(os.path.dirname(LAB), "alexandria", "backend"))
os.environ.setdefault("HF_HOME", "/home/tff/software/novel-audiobook/hf-cache")

MODEL_DIR = os.path.join(LAB, "models", "IndexTTS-2")
DEVICE = os.environ.get("INDEX_DEVICE", "cpu")
app = FastAPI(title="ttslab-indextts2")
_model = None

# emo_vector 顺序由上游固定：[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
EMO_INDEX = {
    "joy": 0, "surprise": 6, "rush": 6,
    "anger": 1, "roar": 1, "shout": 1,
    "sorrow": 2, "fear": 3,
    "sarcasm": 4, "smug": 4,
    "cold": 5, "daze": 5, "drawl": 5,
    "calm": 7, "serious": 7, "whisper": 7,
}
# 上游会再乘 emo_bias 并把总和压到 0.8，这里只给「未压 bias 前」的目标幅度
MAX_INTENSITY = 0.8


def _get():
    global _model
    if _model is None:
        from indextts.infer_v2 import IndexTTS2
        _model = IndexTTS2(cfg_path=os.path.join(MODEL_DIR, "config.yaml"),
                           model_dir=MODEL_DIR, use_fp16=DEVICE != "cpu",
                           device=DEVICE, use_qwen_emo=False)
    return _model


def emo_vector(emotion: str, intensity: float) -> list:
    vec = [0.0] * 8
    if emotion in EMO_INDEX:
        vec[EMO_INDEX[emotion]] = round(max(0.0, min(1.0, intensity)) * MAX_INTENSITY, 3)
    return vec


@app.post("/tts")
async def tts(text: str = Form(...), instruct: str = Form(""), seed: int = Form(-1),
              file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty ref_audio")
    if not text.strip():
        raise HTTPException(status_code=400, detail="text required")
    m = _get()
    if seed >= 0:
        import torch
        torch.manual_seed(seed)
    vec = None
    if instruct.strip():
        from emotion_map import infer
        got = infer(instruct)
        if got:
            vec = emo_vector(*got)
    suffix = os.path.splitext(file.filename or "ref.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        ref_path = tmp.name
    try:
        out = m.infer(spk_audio_prompt=ref_path, text=text, output_path=None, emo_vector=vec)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"indextts failed: {exc}") from exc
    finally:
        os.unlink(ref_path)

    if not out:
        raise HTTPException(status_code=500, detail="model returned no audio")
    sr, pcm = out  # (sampling_rate, int16 ndarray)
    audio = np.asarray(pcm).astype(np.float32).reshape(-1) / 32768.0
    return _wav_bytes(audio, int(sr))


def _wav_bytes(audio, sr):
    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


@app.get("/health")
async def health():
    return {"ok": True, "device": DEVICE, "loaded": _model is not None,
            "sr": 22050 if _model is not None else None}
