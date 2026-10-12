"""CosyVoice2 sidecar：与生产 venv 隔离（本引擎锁 torch 2.3.1+cu121，qwen-tts 用 2.7.0+cu128）。

启动：venvs/cosyvoice/bin/uvicorn cosy_server:app --host 127.0.0.1 --port 7861
设备：COSY_DEVICE=cuda 走显卡（需 ~5G 空闲显存），默认 cpu。
接口：POST /tts  -> audio/wav 字节
"""
import os
import sys
import tempfile

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(LAB, "repos", "CosyVoice"))
sys.path.append(os.path.join(LAB, "repos", "CosyVoice", "third_party", "Matcha-TTS"))
os.environ.setdefault("COSY_DEVICE", os.environ.get("COSY_DEVICE", "cpu"))

MODEL_DIR = os.path.join(LAB, "models", "CosyVoice2-0.5B")
app = FastAPI(title="ttslab-cosyvoice2")
_model = None


def _get():
    global _model
    if _model is None:
        from cosyvoice.cli.cosyvoice import CosyVoice2
        _model = CosyVoice2(MODEL_DIR, load_vllm=False,
                            fp16=os.environ["COSY_DEVICE"] != "cpu")
    return _model


@app.post("/tts")
async def tts(text: str = Form(...), ref_text: str = Form(""), instruct: str = Form(""),
              mode: str = Form("zero_shot"), file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty ref_audio")
    m = _get()
    suffix = os.path.splitext(file.filename or "ref.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        ref_path = tmp.name
    try:
        if mode == "instruct":
            if not instruct.strip():
                raise HTTPException(status_code=400, detail="instruct required for mode=instruct")
            gen = m.inference_instruct2(text, instruct, ref_path, stream=False)
        else:
            if not ref_text.strip():
                raise HTTPException(status_code=400, detail="ref_text required for zero_shot")
            gen = m.inference_zero_shot(text, ref_text, ref_path, stream=False)
        chunks = [(out.get("tts_speech") if out.get("tts_speech") is not None else out["tts_audio"]).float().cpu().numpy().reshape(-1)
                  for out in gen]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"cosyvoice failed: {exc}") from exc
    finally:
        os.unlink(ref_path)

    if not chunks:
        raise HTTPException(status_code=500, detail="model returned no audio")
    return _wav_bytes(np.concatenate(chunks), m.sample_rate)


def _wav_bytes(audio, sr):
    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


@app.get("/health")
async def health():
    return {"ok": True, "device": os.environ["COSY_DEVICE"], "loaded": _model is not None,
            "sr": getattr(_model, "sample_rate", None)}
