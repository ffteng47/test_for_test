# Voice Lab 安装器：多模型音色试听工作台后端。幂等。
# 1) 写 app/voice_lab.py（模型白名单 + generate/history 端点，结果带模型来源元数据）
# 2) patch app.py：挂 router、VoiceConfigItem 增加 source_model 字段
import os
import py_compile
import shutil
import sys

BASE = "/home/tff/software/novel-audiobook/alexandria/app"
APP = os.path.join(BASE, "app.py")
LAB = os.path.join(BASE, "voice_lab.py")

LAB_SRC = '''\
# Voice Lab：单模型一次请求的音色试听工作台（安装器 deploy/patches/add_voice_lab.py）
# 结果全部落 designed_voices/voice_lab_manifest.json，含 model/method/seed 来源信息。
import json
import os
import threading
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

MODELS = {
    "vd17":   {"model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "label": "Qwen3-TTS VoiceDesign 1.7B", "method": "design"},
    "base17": {"model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",        "label": "Qwen3-TTS Base 1.7B 克隆",     "method": "clone"},
    "base06": {"model_id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",        "label": "Qwen3-TTS Base 0.6B 克隆",     "method": "clone"},
    "cv17":   {"model_id": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "label": "Qwen3-TTS CustomVoice 1.7B", "method": "custom"},
    "cv06":   {"model_id": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", "label": "Qwen3-TTS CustomVoice 0.6B", "method": "custom"},
}

router = APIRouter()
_ctx = {}
_lock = threading.Lock()
_cache = {}  # key -> model；3090 显存只养得起两个实验模型，超了就逐出


class GenerateRequest(BaseModel):
    model: str
    method: str            # design | clone | custom
    sample_text: str
    description: str = ""  # design: 音色描述
    ref_audio: str = ""    # clone: clone_voices/ 下的文件名
    ref_text: str = ""     # clone: 参考音频对应文本
    voice: str = "Ryan"    # custom: 内置说话人名
    instruct: str = ""     # custom: 风格指令
    seed: int = -1
    speaker: str = ""      # 目标角色，仅作标注


def init(**kwargs):
    _ctx.update(kwargs)


def _engine():
    engine = _ctx["project_manager"].get_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="TTS engine not initialized")
    return engine


def _get_model(key):
    if key in _cache:
        return _cache[key]
    with _lock:
        if key in _cache:
            return _cache[key]
        engine = _engine()
        import torch
        from qwen_tts import Qwen3TTSModel
        from tts import TTSEngine
        device = engine._resolve_device()
        dtype = torch.bfloat16 if "cuda" in device else torch.float32
        load_kwargs = {"dtype": dtype}
        if device != "cpu":
            load_kwargs["device_map"] = device
        t0 = time.time()
        print(f"VoiceLab: loading {MODELS[key]['model_id']} ...", flush=True)
        model = TTSEngine._load_model(Qwen3TTSModel, MODELS[key]["model_id"], load_kwargs)
        print(f"VoiceLab: {key} loaded in {time.time()-t0:.0f}s", flush=True)
        while len(_cache) >= 2:
            old_key = next(iter(_cache))
            del _cache[old_key]
            engine._clear_gpu_cache()
        _cache[key] = model
        return model


def _available(key):
    from tts import TTSEngine
    return TTSEngine._resolve_local_model_path(MODELS[key]["model_id"]) is not None


@router.get("/api/voice_lab/models")
async def voice_lab_models():
    return [{"key": k, "label": v["label"], "model_id": v["model_id"],
             "method": v["method"], "loaded": k in _cache, "available": _available(k)}
            for k, v in MODELS.items()]


@router.get("/api/voice_lab/history")
async def voice_lab_history(limit: int = 60):
    path = os.path.join(_ctx["designed_dir"], "voice_lab_manifest.json")
    try:
        with open(path, encoding="utf-8") as f:
            recs = json.load(f)
    except (OSError, ValueError):
        recs = []
    return {"records": list(reversed(recs))[:limit]}


@router.post("/api/voice_lab/generate")
async def voice_lab_generate(req: GenerateRequest):
    key = req.model
    if key not in MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model '{key}'")
    if not req.sample_text.strip():
        raise HTTPException(status_code=400, detail="sample_text required")
    method = MODELS[key]["method"]
    engine = _engine()
    model = _get_model(key)
    if not _available(key):
        raise HTTPException(status_code=400, detail=f"Model {key} not in local HF cache")

    import torch
    if req.seed >= 0:
        torch.manual_seed(req.seed)

    lang = engine._language
    t0 = time.time()
    try:
        if method == "design":
            if not req.description.strip():
                raise HTTPException(status_code=400, detail="description required for design")
            wavs, sr = model.generate_voice_design(
                text=req.sample_text, instruct=req.description, language=lang,
                non_streaming_mode=True, max_new_tokens=2048)
        elif method == "clone":
            import soundfile as sf
            fname = os.path.basename(req.ref_audio)
            ref_path = os.path.join(_ctx["clone_dir"], fname)
            if not fname or not os.path.exists(ref_path):
                raise HTTPException(status_code=400, detail="ref_audio missing (upload to clone_voices first)")
            if not req.ref_text.strip():
                raise HTTPException(status_code=400, detail="ref_text required for clone")
            audio_array, ref_sr = sf.read(ref_path)
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)
            prompt = model.create_voice_clone_prompt(ref_audio=(audio_array, ref_sr), ref_text=req.ref_text)
            gen_extra = {}
            instruct = req.description.strip()
            if instruct:
                tok = model._tokenize_texts([model._build_instruct_text(instruct)])[0]
                gen_extra["instruct_ids"] = [tok]
            wavs, sr = model.generate_voice_clone(
                text=req.sample_text, voice_clone_prompt=prompt,
                non_streaming_mode=True, max_new_tokens=2048, **gen_extra)
        else:
            wavs, sr = model.generate_custom_voice(
                text=req.sample_text, language=lang, speaker=req.voice,
                instruct=(req.instruct or req.description or "neutral"),
                non_streaming_mode=True, max_new_tokens=2048)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate failed: {e}")

    if not wavs:
        raise HTTPException(status_code=500, detail="model returned no audio")
    import numpy as np
    audio = np.concatenate(wavs) if len(wavs) > 1 else wavs[0]

    previews_dir = os.path.join(_ctx["designed_dir"], "previews")
    os.makedirs(previews_dir, exist_ok=True)
    fname = f"voice_lab_{key}_{int(time.time()*1000)}.wav"
    wav_path = os.path.join(previews_dir, fname)
    engine._save_wav(audio, sr, wav_path)

    rec = {"id": fname[:-4], "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "model_key": key, "model_label": MODELS[key]["label"], "model_id": MODELS[key]["model_id"],
           "method": method, "speaker": req.speaker, "sample_text": req.sample_text,
           "description": req.description, "ref_text": req.ref_text, "ref_audio": os.path.basename(req.ref_audio),
           "voice": req.voice, "instruct": req.instruct, "seed": req.seed,
           "duration_s": round(len(audio) / sr, 2), "gen_time_s": round(time.time() - t0, 1),
           "audio_url": f"/designed_voices/previews/{fname}"}

    mpath = os.path.join(_ctx["designed_dir"], "voice_lab_manifest.json")
    try:
        with open(mpath, encoding="utf-8") as f:
            recs = json.load(f)
    except (OSError, ValueError):
        recs = []
    recs.append(rec)
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(recs[-500:], f, ensure_ascii=False, indent=1)
    os.replace(tmp, mpath)
    return rec
'''

src = open(APP, encoding="utf-8").read()
if "voice_lab" in src:
    print("APP_ALREADY_PATCHED")
else:
    shutil.copy(APP, APP + ".bak_pre_voice_lab")
    anchor = 'project_manager = ProjectManager(ROOT_DIR)'
    assert anchor in src, "anchor missing"
    src = src.replace(
        anchor,
        anchor + '''
from voice_lab import router as voice_lab_router
from voice_lab import init as _voice_lab_init
_voice_lab_init(project_manager=project_manager,
                clone_dir=CLONE_VOICES_DIR, designed_dir=DESIGNED_VOICES_DIR)
app.include_router(voice_lab_router)''', 1)
    vc_anchor = '    description: Optional[str] = ""  # voice description (for design type)'
    assert vc_anchor in src, "VoiceConfigItem anchor missing"
    src = src.replace(vc_anchor, vc_anchor + '\n    source_model: Optional[str] = ""  # Voice Lab provenance', 1)
    open(APP, "w", encoding="utf-8").write(src)
    print("APP_PATCHED")

open(LAB, "w", encoding="utf-8").write(LAB_SRC)
py_compile.compile(LAB, doraise=True)
py_compile.compile(APP, doraise=True)
print("VOICE_LAB_OK")
