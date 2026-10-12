"""Kokoro-82M sidecar：独立 venv（venvs/kokoro），只做「固定音色朗读」，不能克隆。

启动：venvs/kokoro/bin/uvicorn kokoro_server:app --host 127.0.0.1 --port 7863
用途：旁白兜底档 —— 角色没有可用克隆音色时用它出声，产出必须显式标注 engine=kokoro。
接口：POST /tts -> audio/wav（file 可省略；voice 传 models/Kokoro-82M/voices/*.pt 的裸名）
离线：KModel 与 voice pack 都用本地绝对路径加载，不走 huggingface_hub。
"""
import io
import os

import numpy as np
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

LAB = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(LAB, "models", "Kokoro-82M")
SR = 24000  # Kokoro v1.0 固定 24kHz
DEVICE = os.environ.get("KOKORO_DEVICE", "cpu")
DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "zf_xiaoxiao")
Voices: dict = {}
app = FastAPI(title="ttslab-kokoro")
_pipe = None


def _get():
    global _pipe
    if _pipe is None:
        from kokoro import KPipeline
        from kokoro.model import KModel
        kmodel = KModel(config=os.path.join(MODEL_DIR, "config.json"),
                        model=os.path.join(MODEL_DIR, "kokoro-v1_0.pth"))
        _pipe = KPipeline(lang_code='z', model=kmodel, device=DEVICE)
    return _pipe


def _voice_pack(name: str) -> torch.FloatTensor:
    key = (name or DEFAULT_VOICE).strip()
    if key not in Voices:
        path = os.path.join(MODEL_DIR, "voices", key + ".pt")
        if not os.path.isfile(path):
            raise HTTPException(status_code=400, detail=f"unknown kokoro voice '{key}'")
        Voices[key] = torch.load(path, map_location='cpu', weights_only=True)
    return Voices[key]


@app.post("/tts")
async def tts(text: str = Form(...), voice: str = Form(""), speed: float = Form(1.0),
              file: UploadFile = File(None)):
    if not text.strip():
        raise HTTPException(status_code=400, detail="text required")
    if speed <= 0:
        raise HTTPException(status_code=400, detail="speed must be > 0")
    pack = _voice_pack(voice)
    try:
        chunks = [r.output.audio.float().cpu().numpy().reshape(-1)
                  for r in _get()(text, voice=pack, speed=speed) if r.output is not None]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"kokoro failed: {exc}") from exc
    if not chunks:
        raise HTTPException(status_code=500, detail="model returned no audio")

    buf = io.BytesIO()
    import soundfile as sf
    sf.write(buf, np.concatenate(chunks), SR, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


@app.get("/health")
async def health():
    return {"ok": True, "device": DEVICE, "loaded": _pipe is not None, "sr": SR,
            "voice": DEFAULT_VOICE,
            "voices": sorted(f[:-3] for f in os.listdir(os.path.join(MODEL_DIR, "voices"))
                             if f.endswith(".pt"))}
