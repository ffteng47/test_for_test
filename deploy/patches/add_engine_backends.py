# 多引擎批量生产安装器：让 voice_config.engine 决定走哪个 TTS（幂等）。
#
# 1) 写 app/engines.py —— 生产侧唯一的 sidecar 引擎注册表 + 兜底规则
# 2) app.py: VoiceConfigItem 增加 engine 字段（否则 save_voice_config 会把它丢掉）
# 3) app/voice_lab.py: _cosy_call → _sidecar_call（复用 engines），新增 IndexTTS-2 / Kokoro 行
# 4) app/tts.py: 单段 generate_voice 与批量 generate_batch 都按 engine 分发；
#    角色没有可用音色时旁白回落 Kokoro（不再静默用 Ryan）
# 5) app/project.py: 每段写回 voice_engine / voice_fallback，Kokoro 兜底必须显式留痕
import os
import py_compile

BASE = "/home/tff/software/novel-audiobook/alexandria/app"
APP = os.path.join(BASE, "app.py")
ENG = os.path.join(BASE, "engines.py")
LAB = os.path.join(BASE, "voice_lab.py")
TTS = os.path.join(BASE, "tts.py")
PRJ = os.path.join(BASE, "project.py")

ENG_SRC = '''\
"""sidecar 引擎注册表：Voice Lab 与批量生产共用（安装器 deploy/patches/add_engine_backends.py）。

voice_config[speaker]["engine"] 决定走哪个引擎；"" / "qwen" = 进程内 Qwen3-TTS。
其余一律本机 HTTP sidecar（见 ttslab/），第二套 torch 绝不装进生产 venv。
兜底：角色没有可用音色时旁白回落 Kokoro，但调用方必须把 voice_engine 写回 chunk，
禁止静默冒充主音色（Kokoro 不能克隆，出来的音色不是该角色的）。
"""
import os

ENGINES = {
    "cosy": {
        "label": "CosyVoice2", "ref": True, "emo": "instruct2",
        "url": os.environ.get("COSY_TTS_URL", "http://127.0.0.1:7861/tts"),
        "hint": "cd ~/software/novel-audiobook/ttslab && venvs/cosyvoice/bin/uvicorn cosy_server:app --port 7861",
    },
    "index": {
        "label": "IndexTTS-2", "ref": True, "emo": "emo_vector",
        "url": os.environ.get("INDEX_TTS_URL", "http://127.0.0.1:7862/tts"),
        "hint": "cd ~/software/novel-audiobook/ttslab && venvs/indextts311/bin/uvicorn indextts_server:app --port 7862",
    },
    "kokoro": {
        "label": "Kokoro 兜底", "ref": False, "emo": "none", "voice": os.environ.get("KOKORO_VOICE", "zf_xiaoxiao"),
        "url": os.environ.get("KOKORO_TTS_URL", "http://127.0.0.1:7863/tts"),
        "hint": "cd ~/software/novel-audiobook/ttslab && venvs/kokoro/bin/uvicorn kokoro_server:app --port 7863",
    },
}
FALLBACK = "kokoro"

# 段级情感（emotion_map 的规范中文句）送进各引擎的载体：
#   verbatim   = 原句直接当 instruct 用（Qwen3-TTS 三家）
#   instruct2  = 包成 CosyVoice2 自己的中文句式，且要音色行显式选 instruct 通道
#   emo_vector = 由 sidecar 自己 emotion_map.infer() 折成 8 维幅度（IndexTTS-2）
#   none       = 没有情感通道，指令一律丢弃（Kokoro 兜底）
EMO_VEHICLES = ("verbatim", "instruct2", "emo_vector", "none")


def instruct2_style(text):
    """段级 instruct → CosyVoice2 instruct2 的句式。非中文直接返回空：宁可没情绪，不要乱音。"""
    t = (text or "").strip()
    if not t or not any(0x4E00 <= ord(c) <= 0x9FFF for c in t):
        return ""
    return t if t[0] in "用以请" else f"用{t}的语气说话"


def usable(voice_data):
    """该角色的音色配置能不能真出声。"""
    vtype = voice_data.get("type")
    if not vtype:
        return False
    if vtype == "clone":
        return bool(voice_data.get("ref_audio")) and bool(voice_data.get("ref_text"))
    if vtype == "design":
        return bool(voice_data.get("description") or voice_data.get("ref_audio"))
    if vtype in ("lora", "builtin_lora"):
        return bool(voice_data.get("adapter_path") or voice_data.get("adapter_id"))
    return True


def resolve(voice_data):
    """→ (engine_key, 是否兜底)。engine_key 为空串表示走进程内 Qwen。"""
    voice_data = voice_data or {}
    engine = voice_data.get("engine") or ""
    if engine in ENGINES:
        return engine, False
    if engine == "qwen":
        return "", False
    return ("", False) if usable(voice_data) else (FALLBACK, True)


def provenance(voice_data):
    """写回 chunk 的溯源字段：前端据此标注实际出声引擎。"""
    engine, fallback = resolve(voice_data)
    return {"voice_engine": engine or "qwen", "voice_fallback": fallback}


def label(engine_key):
    return ENGINES[engine_key]["label"] if engine_key in ENGINES else "Qwen3-TTS"


def ref_path(voice_data):
    """ref_audio 相对项目根（app/ 的上一级）解析，规则同 _get_clone_prompt。"""
    path = voice_data.get("ref_audio") or ""
    if path and not os.path.isabs(path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, path)
    return path


def call(engine_key, text, voice_data=None, instruct="", seed=-1):
    """统一 POST /tts（契约同 ttslab/cosy_server.py）→ (float32 mono, sr)。"""
    import requests
    import numpy as np

    cfg = ENGINES[engine_key]
    voice_data = voice_data or {}
    # 通道由音色行显式声明（Voice Lab 选用时写入 mode），不由「这句有没有 instruct」决定：
    # 剧本每段的 instruct 是给 Qwen 写的语气词，直接喂 CosyVoice2 的 instruct2 会出乱音。
    mode = voice_data.get("mode") or "zero_shot"
    vehicle = cfg.get("emo", "verbatim")
    if vehicle == "instruct2":
        instruct = instruct2_style(instruct) if mode == "instruct" else ""
        if not instruct:
            mode = "zero_shot"
    elif vehicle == "none":
        instruct = ""
    elif mode == "instruct" and not (instruct or "").strip():
        mode = "zero_shot"
    data = {"text": text, "instruct": instruct or "", "seed": str(seed), "mode": mode}
    files = None
    if cfg.get("ref", True):
        path = ref_path(voice_data)
        if not path or not os.path.exists(path):
            raise RuntimeError(
                f"{cfg['label']} 需要参考音频，但 ref_audio 不存在：{voice_data.get('ref_audio') or '未设置'}")
        data["ref_text"] = voice_data.get("ref_text") or ""
        if vehicle == "instruct2" and data["mode"] == "zero_shot" and not data["ref_text"]:
            raise RuntimeError(
                f"{cfg['label']} 纯克隆要 ref_text（参考音频里说的原话）才能出声："
                f"去「角色与声音」补上，或在 Voice Lab 用「CosyVoice2 情感指令」重新选用")
        with open(path, "rb") as f:
            files = {"file": (os.path.basename(path), f.read())}
    else:
        data["voice"] = voice_data.get("voice") or cfg.get("voice", "")

    try:
        resp = requests.post(cfg["url"], data=data, files=files, timeout=1800)
    except requests.RequestException as exc:
        raise RuntimeError(f"{cfg['label']} sidecar 未响应，先启动：{cfg['hint']}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"{cfg['label']} 生成失败：{resp.text[:200]}")

    import io

    import soundfile as sf
    audio, sr = sf.read(io.BytesIO(resp.content), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return np.asarray(audio), int(sr)


if __name__ == "__main__":
    assert resolve({}) == ("kokoro", True)                       # 没配置 → 兜底，且留痕
    assert resolve({"type": "custom", "voice": "Ryan"}) == ("", False)
    assert resolve({"type": "clone"}) == ("kokoro", True)        # 缺 ref_text 的克隆配置不算可用
    assert resolve({"type": "clone", "ref_audio": "a.wav", "ref_text": "阿"}) == ("", False)
    assert resolve({"engine": "index", "type": "custom"}) == ("index", False)
    assert resolve({"engine": "qwen", "type": "clone"}) == ("", False)
    assert provenance({}) == {"voice_engine": "kokoro", "voice_fallback": True}
    assert usable({"type": "clone", "ref_audio": "a.wav"}) is False
    assert all(v.get("emo") in EMO_VEHICLES for v in ENGINES.values())   # 每个引擎必须声明情感载体
    assert instruct2_style("平稳叙述，克制") == "用平稳叙述，克制的语气说话"
    assert instruct2_style("recap, warm and easy") == ""       # 英文语气词一律不进 instruct2
    assert instruct2_style("") == ""
    print("SELFTEST OK")
'''

TTS_SIDE = '''    def _sidecar_generate(self, engine_key, text, instruct_text, voice_data, output_path):
        """走本机 sidecar 出一段音频；异常按各分支既有约定返回 False。"""
        try:
            seed = int(voice_data.get("seed", -1))
        except (TypeError, ValueError):
            seed = -1
        # character_style 是给 Qwen 写的长描述（常为英文），对三个 sidecar 都是噪声：
        # cosy 有自己的通道、index 只认规范情感句、kokoro 没有情感通道。段级 instruct 才是信号。
        instruct = (instruct_text or "").strip()
        try:
            audio, sr = engines.call(engine_key, text, voice_data, instruct=instruct, seed=seed)
        except Exception as exc:
            print(f"TTS [{engine_key}] failed: {exc}")
            return False
        self._save_wav(audio, sr, output_path)
        print(f"TTS [{engine_key}] ok → {output_path}")
        return True

'''

LAB_SIDE = '''def _sidecar_call(key, req):
    """跨引擎试听：统一走 engines.call，返回 (audio_list, sr) 与 qwen 分支同形状。"""
    import engines

    try:
        seed = int(req.seed)
    except (TypeError, ValueError):
        seed = -1
    try:
        audio, sr = engines.call(
            MODELS[key]["backend"], req.sample_text,
            {"ref_audio": os.path.join(_ctx["clone_dir"], os.path.basename(req.ref_audio)),
             "ref_text": req.ref_text, "mode": MODELS[key].get("mode"), "voice": req.voice},
            instruct=req.description or req.instruct, seed=seed)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return [audio], sr
'''

APP_ANCHOR = '    source_model: Optional[str] = ""  # Voice Lab provenance'

EMO_ROUTE = '''@router.get("/api/emotions")
async def list_emotions():
    """规范情感词表（五层架构第②层出口）：风格下拉框的唯一来源，不在 Vue 里另抄一套。"""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
    from emotion_map import EMOTIONS, instruct_for
    return [{"emotion": k, "instruct": instruct_for(k, v["intensity"])} for k, v in EMOTIONS.items()]


'''



ENG_LIST_ROUTE = '''@router.get("/api/engines")
async def list_engines():
    """出声引擎清单：前端下拉框的唯一来源，不在 Vue 里写第二套。"""
    import engines
    return [{"key": k, "label": v["label"], "ref": v.get("ref", True), "emo": v.get("emo", "verbatim"),
             "fallback": k == engines.FALLBACK} for k, v in engines.ENGINES.items()]


'''


def patch(path, pairs, tag):
    """pairs: (old, new, marker)。marker 已存在则跳过该条；首条 old 缺失且 marker 缺失 → 已打过补丁。"""
    src = open(path, encoding="utf-8").read()
    changed = False
    for old, new, marker in pairs:
        if marker in src:
            continue
        assert old in src, f"{tag}: anchor missing -> {old[:80]!r}"
        src = src.replace(old, new, 1)
        changed = True
    if not changed:
        print(f"{tag}: ALREADY")
        return
    open(path, "w", encoding="utf-8").write(src)
    print(f"{tag}: PATCHED")


open(ENG, "w", encoding="utf-8").write(ENG_SRC)
print("ENGINES_WRITTEN")

# ---- 1) VoiceConfigItem 必须认识 engine，否则前端写了也存不下 ----
patch(APP, [(
    "from typing import List, Optional, Dict",
    "from typing import List, Optional, Dict, Union",
    "List, Optional, Dict, Union",
), (
    '    seed: Optional[str] = "-1"',
    '    seed: Optional[Union[str, int]] = "-1"  # 前端按 int 传，pydantic v2 不做 int→str 强转',
    'seed: Optional[Union[str, int]]',
), (
    APP_ANCHOR,
    APP_ANCHOR + '\n    engine: Optional[str] = ""  # 批量生产走哪个 TTS：""|qwen|cosy|index|kokoro',
    '    engine: Optional[str] = ""',
), (
    '    alias_of: Optional[str] = None  # 别名归并；不声明就会被 pydantic 静默丢掉，保存一次即断链',
    '    alias_of: Optional[str] = None  # 别名归并；不声明就会被 pydantic 静默丢掉，保存一次即断链\n'
    '    mode: Optional[str] = ""  # 出声通道：""|zero_shot=纯克隆；instruct=CosyVoice2 情感指令（仅显式选用该音色行才写）',
    'mode: Optional[str] = ""',
)], "APP")

# ---- 2) Voice Lab：注册 IndexTTS-2 / Kokoro，sidecar 调用收敛到 engines ----
patch(LAB, [(
    '''                      "url": os.environ.get("COSY_TTS_URL", "http://127.0.0.1:7861/tts")},''',
    '''                      "url": os.environ.get("COSY_TTS_URL", "http://127.0.0.1:7861/tts")},
    "index_clone": {"backend": "index", "model_id": "IndexTTS-2", "label": "IndexTTS-2 克隆",
                    "method": "clone",
                    "url": os.environ.get("INDEX_TTS_URL", "http://127.0.0.1:7862/tts")},
    "koko_narr":   {"backend": "kokoro", "model_id": "Kokoro-82M", "label": "Kokoro 旁白兜底",
                    "method": "custom",
                    "url": os.environ.get("KOKORO_TTS_URL", "http://127.0.0.1:7863/tts")},''',
    '"index_clone"',
), (
    '''        if MODELS[key].get("backend") == "cosy":
            wavs, sr = _cosy_call(key, req)''',
    '''        if MODELS[key].get("backend"):
            wavs, sr = _sidecar_call(key, req)''',
    '_sidecar_call(key, req)',
), (
    '''           "voice": req.voice, "instruct": req.instruct, "seed": req.seed,''',
    '''           "voice": MODELS[key].get("voice") or req.voice, "instruct": req.instruct, "seed": req.seed,
           "engine": MODELS[key].get("backend") or "qwen",''',
    '"engine": MODELS[key].get("backend")',
), (
    '''           "engine": MODELS[key].get("backend") or "qwen",''',
    '''           "engine": MODELS[key].get("backend") or "qwen",
           "mode": MODELS[key].get("mode") or "zero_shot",''',
    '"mode": MODELS[key].get("mode") or "zero_shot"',
)], "LAB")

# ---- 2b) 前端要按引擎出下拉框，清单必须来自 engines.ENGINES ----
patch(LAB, [(
    '@router.get("/api/voice_lab/models")',
    ENG_LIST_ROUTE + '@router.get("/api/voice_lab/models")',
    '"/api/engines"',
)], "LAB_ENGINES")

# ---- 2b2) 已装机器：/api/engines 要把情感载体一起吐给前端 ----
patch(LAB, [(
    '''    return [{"key": k, "label": v["label"], "ref": v.get("ref", True),
             "fallback": k == engines.FALLBACK} for k, v in engines.ENGINES.items()]''',
    '''    return [{"key": k, "label": v["label"], "ref": v.get("ref", True), "emo": v.get("emo", "verbatim"),
             "fallback": k == engines.FALLBACK} for k, v in engines.ENGINES.items()]''',
    '"emo": v.get("emo"',
)], "LAB_ENGINE_EMO")

# ---- 2c) 风格下拉框读规范词表，杜绝前端第二套文案 ----
patch(LAB, [(
    '@router.get("/api/engines")',
    EMO_ROUTE + '@router.get("/api/engines")',
    '"/api/emotions"',
)], "LAB_EMOTIONS")

src = open(LAB, encoding="utf-8").read()
if "def _sidecar_call" in src and "def _cosy_call" not in src:
    print("LAB_SIDE_CAR: ALREADY")
else:
    head = src.split("def _cosy_call")[0] if "def _cosy_call" in src else src.rstrip() + "\n\n"
    open(LAB, "w", encoding="utf-8").write(head + LAB_SIDE)
    print("LAB_SIDE_CAR: REWRITTEN")

# ---- 3) 生产引擎：单段与批量都按 engine 分发 ----
patch(TTS, [(
    "def sanitize_filename(name):",
    "import engines\n\n\ndef sanitize_filename(name):",
    "import engines",
), (
    '''        voice_data = voice_config.get(speaker)
        if not voice_data:
            print(f"Warning: No voice configuration for '{speaker}'. Skipping.")
            return False

        voice_type = voice_data.get("type", "custom")
''',
    '''        # 没有可用音色 → engines 会给出兜底引擎（Kokoro），不再静默跳过或冒充 Ryan
        voice_data = voice_config.get(speaker) or {}
        engine_key, is_fallback = engines.resolve(voice_data)
        if is_fallback:
            print(f"TTS fallback: '{speaker}' 无可用音色 → {engines.label(engine_key)}")
        if engine_key:
            return self._sidecar_generate(engine_key, text, instruct_text, voice_data, output_path)

        voice_type = voice_data.get("type", "custom")
''',
    "engines.resolve(voice_data)",
), (
    '''        lora_chunks = []
        design_chunks = []
''',
    '''        lora_chunks = []
        design_chunks = []
        sidecar_chunks = []
''',
    "sidecar_chunks = []",
), (
    '''        for chunk in chunks:
            speaker = chunk.get("speaker")
            voice_data = voice_config.get(speaker, {})
            voice_type = voice_data.get("type", "custom")
''',
    '''        for chunk in chunks:
            speaker = chunk.get("speaker")
            voice_data = voice_config.get(speaker, {})
            engine_key, _ = engines.resolve(voice_data)
            if engine_key:
                sidecar_chunks.append((chunk, engine_key))
                continue
            voice_type = voice_data.get("type", "custom")
''',
    "sidecar_chunks.append((chunk, engine_key))",
)], "TTS")

src = open(TTS, encoding="utf-8").read()
if "def _sidecar_generate" in src:
    print("TTS_SIDE: ALREADY")
else:
    anchor = '''                except Exception as e:
                    results["failed"].append((idx, str(e)))

        return results

    # ── Connection test ─'''
    assert anchor in src, "TTS_SIDE: anchor missing"
    src = src.replace(anchor, '''                except Exception as e:
                    results["failed"].append((idx, str(e)))

        # sidecar 引擎逐段串行（每引擎一个独立进程，不参与 qwen 批处理）
        for chunk, engine_key in sidecar_chunks:
            idx = chunk["index"]
            output_path = os.path.join(output_dir, f"temp_batch_{idx}.wav")
            voice_data = voice_config.get(chunk.get("speaker"), {})
            if self._sidecar_generate(engine_key, chunk["text"], chunk.get("instruct", ""),
                                      voice_data, output_path):
                results["completed"].append(idx)
            else:
                results["failed"].append((idx, f"{engines.label(engine_key)} 生成失败"))

        return results

''' + TTS_SIDE + '''    # ── Connection test ─''', 1)
    open(TTS, "w", encoding="utf-8").write(src)
    print("TTS_SIDE: PATCHED")

# ---- 3b) 已装机器：摘掉老 _sidecar_generate 里的 character_style 拼接（对新装是空操作）----
patch(TTS, [(
    '''        style = (voice_data.get("character_style") or "").strip()
        instruct = f"{(instruct_text or '').strip()} {style}".strip()''',
    '''        # character_style 是给 Qwen 写的长描述（常为英文），对三个 sidecar 都是噪声：
        # cosy 有自己的通道、index 只认规范情感句、kokoro 没有情感通道。段级 instruct 才是信号。
        instruct = (instruct_text or "").strip()''',
    '段级 instruct 才是信号',
)], "TTS_STYLE")

# ---- 3c) type=design 的绑定要能吃 voice_config 里的 seed（原来调用时丢了，配置写了也无效）----
patch(TTS, [(
    '''        wav_path, sr = self.generate_voice_design(description=description, sample_text=text)''',
    '''        try:
            dseed = int(voice_data.get("seed", -1))
        except (TypeError, ValueError):
            dseed = -1
        wav_path, sr = self.generate_voice_design(description=description, sample_text=text, seed=dseed)''',
    'sample_text=text, seed=dseed',
)], "TTS_DESIGN_SEED")

# ---- 3d) Voice Lab：seed=-1 要把随机数落地，结果行才显示得出可复现的 seed ----
patch(LAB, [(
    '''    import torch
    if req.seed >= 0:
        torch.manual_seed(req.seed)''',
    '''    import torch
    # 随机也要留痕：不落地就只记到 seed=-1，满意的那条再也抽不回来。
    # 上界取 2**31-1，与各 sidecar 的 int(seed) 解析保持一致。
    if req.seed < 0:
        req.seed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())
    torch.manual_seed(req.seed)''',
    'int(torch.randint(0, 2 ** 31 - 1, (1,)).item())',
)], "LAB_SEED")

# ---- 4) 溯源：每段记下真正出声的引擎 ----
patch(PRJ, [(
    "def get_speaker(entry):",
    "import engines\n\n\ndef get_speaker(entry):",
    "import engines",
), (
    '''                self._update_chunk_fields(index, status="done", audio_path=audio_path)''',
    '''                self._update_chunk_fields(index, status="done", audio_path=audio_path,
                                          **engines.provenance(voice_config.get(speaker_to_use, {})))''',
    "engines.provenance(voice_config.get(speaker_to_use",
), (
    '''                    chunks[idx]["status"] = "done"
                    results["completed"].append(idx)''',
    '''                    chunks[idx]["status"] = "done"
                    chunks[idx].update(engines.provenance(
                        voice_config.get(self._resolve_alias(speaker, voice_config), {})))
                    results["completed"].append(idx)''',
    "chunks[idx].update(engines.provenance",
)], "PRJ")

for f in (ENG, APP, LAB, TTS, PRJ):
    py_compile.compile(f, doraise=True)
print("ENGINE_BACKENDS_OK")
