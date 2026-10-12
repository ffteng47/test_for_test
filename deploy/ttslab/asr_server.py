"""ASR sidecar：SenseVoice 转写，跑在 ttslab/venvs/funasr（funasr 拉的 torch 与生产 venv 不兼容，故独立进程）。

启动：venvs/funasr/bin/uvicorn asr_server:app --port 7870
用途：给克隆参考音频自动产出 ref_text，并把情感/事件标签折算成该段的量化 instruct 建议
      （词表与 backend/emotion_map.py 同源，不在这里重复定义）。
"""
import os
import re
import sys
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from funasr import AutoModel

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(LAB), "alexandria", "backend"))
from emotion_map import asr_map, instruct_for  # noqa: E402

MODEL_DIR = os.path.join(LAB, "models", "SenseVoiceSmall")
DEVICE = os.environ.get("ASR_DEVICE", "cpu")
TAGS = re.compile(r"^((?:<\|[^|]*\|>)+)", re.IGNORECASE)

app = FastAPI(title="ttslab-asr")
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = AutoModel(model=MODEL_DIR, device=DEVICE, disable_update=True,
                           trust_remote_code=True)
    return _model


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = "zh"):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty upload")
    suffix = os.path.splitext(file.filename or "audio")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        path = tmp.name
    try:
        res = _get_model().generate(input=path, cache={}, language=language, use_itn=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"asr failed: {exc}") from exc
    finally:
        os.unlink(path)

    out = res[0] if res else {}
    text = out.get("text", "")
    match = TAGS.match(text)
    tags = [t.strip("<|").strip() for t in re.findall(r"<\|([^|>]*)\|>", match.group(1))] if match else []
    known = {"zh", "en", "ja", "ko", "yue"}
    emo = next((t for t in tags if t.isupper() and t not in known and t not in {"withitn", "noreturn", "speech", "event"}), "")
    got = asr_map(tags)
    return {
        "text": text[match.end():].strip() if match else text.strip(),
        "language": next((t for t in tags if t in known), language),
        "emotion": emo,
        "tags": tags,
        # 该段 instruct 建议：只在识别到规范情感时给出，前端填进可编辑框，不覆盖人工值
        "emotion_norm": got[0] if got else "",
        "instruct": instruct_for(*got) if got else "",
    }


@app.get("/health")
async def health():
    return {"ok": True, "device": DEVICE, "loaded": _model is not None}
