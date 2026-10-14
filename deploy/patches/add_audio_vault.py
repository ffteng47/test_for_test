# 音频仓库安装器（幂等）：量化标签词表 + 音频仓库 API + Voice Lab 记录的标注/改/删/分页。
#
# 1) 写 app/tag_vocab.py —— 标签维度的唯一真源；一维 = 一行，枚举只增不删不改序
# 2) 写 app/audio_vault.py —— 仓库：入库即实测（时长/字每秒/基频）→ 归一化标签，支持筛选与 LLM 挑选
# 3) backend/noveldb.py: SCHEMA 增加 voice_samples 表（open_db 每次 executescript，自动建表）
# 4) app/app.py: 挂载 vault 路由
# 5) app/voice_lab.py: history 分页；record/update 标注与修改；record/delete 删记录（可选删文件）
#
# 顺序要求：在 add_voice_lab.py / add_engine_backends.py 之后跑（本安装器的 old 锚点取原始文本）。
import os
import py_compile

BASE = "/home/tff/software/novel-audiobook/alexandria/app"
BACKEND = os.path.join(os.path.dirname(BASE), "backend")
APP = os.path.join(BASE, "app.py")
VOC = os.path.join(BASE, "tag_vocab.py")
VAU = os.path.join(BASE, "audio_vault.py")
NDB = os.path.join(BACKEND, "noveldb.py")
LAB = os.path.join(BASE, "voice_lab.py")

VOC_SRC = r'''"""标签词表：音频仓库与声音实验室标注的唯一真源（安装器 deploy/patches/add_audio_vault.py）。

可扩展性全押在一条约定上：
- 新增一维 = FACETS 里加一行；枚举值**只增不删、不改顺序**。
- 向量布局由 FACETS 声明顺序生成（layout() 会吐出列名），删改历史样本的向量就作废。
- 情绪值不在这里重定义：直接取 backend/emotion_map.py 的规范情感，__main__ 自检断言同源。

量化：num/int 本身就是数；enum 展开成 one-hot / 多选位；note 给人看，不进向量。
所以同一个标签集既能喂 LLM（as_prompt 出一句中文），也能喂embedding/最近邻（to_vector 出定长向量）。
"""
import os
import sys

_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def emotion_keys():
    from emotion_map import EMOTIONS
    return list(EMOTIONS.keys())


def emotion_labels():
    """情绪 key → 一个中文名，给前端下拉框用；词表仍然只有 emotion_map 一处。"""
    from emotion_map import EMOTIONS
    return {k: (v["keys"][0] if v.get("keys") else k) for k, v in EMOTIONS.items()}


# 情绪的量化坐标 (valence 效价, arousal 唤醒度)，各 [-1,1]。标定表不是真理：
# 觉得标定偏了就改这几个数，别改结构。
EMOTION_VA = {
    "joy": (0.8, 0.6), "smug": (0.5, 0.3), "sarcasm": (-0.3, 0.2),
    "calm": (0.1, -0.5), "cold": (-0.3, -0.4), "drawl": (-0.1, -0.6),
    "shout": (0.0, 0.8), "roar": (-0.5, 0.9), "surprise": (0.1, 0.7),
    "whisper": (-0.1, -0.5), "anger": (-0.6, 0.9), "sorrow": (-0.7, -0.4),
    "fear": (-0.7, 0.7), "serious": (-0.1, -0.2), "rush": (0.0, 0.8),
    "daze": (-0.2, -0.3),
}

# 实测值 → 0..1 的归一化旋钮。换语言/换书先调这两个区间，不改代码。
PACE_BOUNDS = (2.0, 7.5)      # 字/秒
PITCH_BOUNDS = (70.0, 330.0)  # 基频 Hz

FACETS = {
    "emotion":   {"label": "情绪", "kind": "enum", "values": None},
    "intensity": {"label": "情绪强度", "kind": "num", "min": 0.0, "max": 1.0, "step": 0.05},
    "bond":      {"label": "感情对象", "kind": "enum", "values":
                  ["无", "亲情", "爱情", "友情", "敌意", "怜悯", "愧疚", "敬畏", "思念"]},
    "warmth":    {"label": "冷热", "kind": "num", "min": -1.0, "max": 1.0, "step": 0.05},
    "scene":     {"label": "情节", "kind": "enum", "multi": True, "values":
                  ["旁白铺陈", "日常对话", "内心独白", "争执冲突", "紧张追逐", "危险对峙",
                   "悬疑铺垫", "温柔安慰", "悲伤告别", "搞笑调侃", "宣告决策"]},
    "timbre":    {"label": "音色质感", "kind": "enum", "multi": True, "values":
                  ["清亮", "低沉", "沙哑", "气声", "颤抖", "圆润", "尖细", "干冷", "厚实"]},
    "pace":      {"label": "语速", "kind": "num", "min": 0.0, "max": 1.0, "step": 0.05, "measured": True},
    "pitch":     {"label": "音高", "kind": "num", "min": 0.0, "max": 1.0, "step": 0.05, "measured": True},
    "rating":    {"label": "人工评级", "kind": "int", "min": 0, "max": 5, "step": 1},
    "note":      {"label": "备注", "kind": "text", "max_len": 200},
}


def _values(key):
    vals = FACETS[key]["values"]
    return emotion_keys() if vals is None else vals


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def scale_pace(cps):
    lo, hi = PACE_BOUNDS
    return _clamp((cps - lo) / (hi - lo), 0.0, 1.0)


def scale_pitch(hz):
    lo, hi = PITCH_BOUNDS
    return _clamp((hz - lo) / (hi - lo), 0.0, 1.0)


def _dims():
    """向量列定义：(维度, 类型, 取值)。layout() 与 to_vector() 共用，永不脱节。"""
    dims = []
    for key, fac in FACETS.items():
        if fac["kind"] == "enum":
            dims += [(key, "onehot", v) for v in _values(key)]
            if key == "emotion":
                dims += [(key, "va", "valence"), (key, "va", "arousal")]
        elif fac["kind"] in ("num", "int"):
            dims.append((key, fac["kind"], None))
    return dims


_DIMS = _dims()


def _dim_name(dim):
    key, kind, val = dim
    if kind == "onehot":
        return f"{key}={val}"
    if kind == "va":
        return f"{key}:{val}"
    return key


def layout():
    return [_dim_name(d) for d in _DIMS]


def validate(tags):
    """未知维度 / 非规范枚举值直接报错：标签写歪一条，下游 LLM 就挑错一次。"""
    out = {}
    for key, val in (tags or {}).items():
        if key not in FACETS:
            raise ValueError(f"未知标签维度：{key}")
        fac = FACETS[key]
        if val is None or val == "" or (isinstance(val, list) and not val):
            continue
        if fac["kind"] == "enum":
            allowed = _values(key)
            items = val if isinstance(val, list) else [val]
            bad = [x for x in items if x not in allowed]
            if bad:
                raise ValueError(f"{key} 不是规范值：{bad}（可用：{allowed}）")
            out[key] = items if fac.get("multi") else items[-1]
        elif fac["kind"] == "int":
            out[key] = int(_clamp(round(float(val)), fac["min"], fac["max"]))
        elif fac["kind"] == "num":
            out[key] = round(_clamp(float(val), fac["min"], fac["max"]), 3)
        else:
            out[key] = str(val)[:fac["max_len"]]
    return out


def to_vector(tags):
    tags = tags or {}
    vec = []
    for key, kind, val in _DIMS:
        if kind == "onehot":
            cur = tags.get(key)
            held = set(cur if isinstance(cur, list) else ([cur] if cur else []))
            vec.append(1.0 if val in held else 0.0)
        elif kind == "va":
            va = EMOTION_VA.get(tags.get("emotion") or "")
            vec.append(float(va[0 if val == "valence" else 1]) if va else 0.0)
        elif kind == "int":
            vec.append(float(tags.get(key, 0)) / FACETS[key]["max"])
        else:
            vec.append(float(tags[key]) if key in tags else 0.0)
    return vec


def schema():
    """前端标签面板与 LLM 的同一份说明书：不在 Vue 里另抄一套维度。"""
    rows = []
    for key, fac in FACETS.items():
        row = {"key": key, "label": fac["label"], "kind": fac["kind"],
               "multi": bool(fac.get("multi")), "measured": bool(fac.get("measured"))}
        if fac["kind"] == "enum":
            row["values"] = _values(key)
            if FACETS[key]["values"] is None:
                row["value_labels"] = emotion_labels()
        elif fac["kind"] in ("num", "int"):
            row.update({"min": fac["min"], "max": fac["max"], "step": fac["step"]})
        else:
            row["max_len"] = fac["max_len"]
        rows.append(row)
    return rows


def as_prompt(tags):
    """标签集 → 一句中文，直接塞进 LLM 提示词。"""
    parts = []
    for key, val in (tags or {}).items():
        if val in (None, "", []):
            continue
        label = FACETS[key]["label"] if key in FACETS else key
        if key == "emotion" and val in EMOTION_VA:
            v, a = EMOTION_VA[val]
            parts.append(f"{label}={val}(效价{v:+.1f}/唤醒{a:+.1f})")
        elif isinstance(val, list):
            parts.append(f"{label}={'/'.join(str(x) for x in val)}")
        else:
            parts.append(f"{label}={val}")
    return "，".join(parts)


if __name__ == "__main__":
    keys = emotion_keys()
    assert set(EMOTION_VA) == set(keys), "情绪标定表与 emotion_map 不同源"
    assert set(emotion_labels()) == set(keys), "情绪中文名与 emotion_map 不同源"
    assert schema()[0].get("value_labels"), "情绪下拉框必须拿到中文名"
    assert len(layout()) == len(to_vector({})), "layout 与向量长度脱节"
    assert layout().count("emotion") == 0
    t = validate({"emotion": "anger", "scene": ["争执冲突"], "pace": 0.42,
                  "rating": 4, "note": " x" * 999})
    assert t["emotion"] == "anger" and t["scene"] == ["争执冲突"]
    assert t["rating"] == 4 and len(t["note"]) == 200
    assert len(to_vector(t)) == len(layout())
    assert to_vector(t)[layout().index("emotion=anger")] == 1.0
    assert to_vector(t)[layout().index("emotion=joy")] == 0.0
    assert abs(to_vector(t)[layout().index("emotion:valence")] - (-0.6)) < 1e-9
    try:
        validate({"emotion": "furious"})
        raise AssertionError("非规范情绪必须被拒")
    except ValueError:
        pass
    try:
        validate({"size": 1})
        raise AssertionError("未知维度必须被拒")
    except ValueError:
        pass
    assert scale_pace(PACE_BOUNDS[0]) == 0.0 and scale_pace(PACE_BOUNDS[1]) == 1.0
    assert scale_pitch(-100) == 0.0 and scale_pitch(9999) == 1.0
    assert "情绪=anger" in as_prompt(t)
    print("TAG_VOCAB_OK", len(layout()), "dims", len(keys), "emotions")
'''

VAU_SRC = r'''"""音频仓库：确认过的好声音 + 量化标签（安装器 deploy/patches/add_audio_vault.py）。

三类来源：lab（声音实验室记录 id）/ chunk（台词段序号，取已生成的音频）/ file（root 下的相对路径）。
入库即实测：时长、字每秒、中位基频 → 归一化写进 tags 的 pace/pitch（人工传值则以人工为准）。
标签一律过 tag_vocab.validate，词表不在这里也不在前端，只在 tag_vocab.py。

# ponytail: 筛选是全表扫 + Python 过滤，几千条够用；上万条改 json_extract 生成列 + 索引。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

import tag_vocab
router = APIRouter()
_ctx = {}
_NOISE = re.compile(r"\s+")


def init(**kwargs):
    _ctx.update(kwargs)


def _root():
    return _ctx["root_dir"]


def _abs(rel):
    return os.path.normpath(os.path.join(_root(), rel))


def _within_root(path):
    """只允许当前工作区内的文件：仓库的写入方是本机 UI，越界路径一律拒。"""
    real = os.path.realpath(path)
    return real == os.path.realpath(_root()) or real.startswith(os.path.realpath(_root()) + os.sep)


def _url(rel):
    return "/" + rel.replace(os.sep, "/")


def _db():
    bk = os.path.join(os.path.dirname(_root()), "backend")
    if bk not in sys.path:
        sys.path.insert(0, bk)
    from domain import active_project_id, workspace_paths
    from noveldb import Db, open_db
    db = Db(open_db(workspace_paths()["db"]))
    pid = active_project_id(db.con)
    if pid is None:
        raise HTTPException(status_code=400, detail="当前书未入库 noveldb：先去「导入拆解」跑一次标注")
    return db, pid


# ---- 实测：时长 / 语速 / 基频 ----

def _load_mono(path):
    import soundfile as sf
    try:
        data, sr = sf.read(path)
    except Exception:
        if os.path.splitext(path)[1].lower() == ".wav":
            raise
        tmp = os.path.join(tempfile.gettempdir(), f"vault_{int(time.time()*1000)}.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path,
                        "-ac", "1", "-ar", "16000", tmp], check=True)
        try:
            data, sr = sf.read(tmp)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    return np.asarray(data, dtype=np.float32), sr


def _median_f0(audio, sr):
    """自相关基频：40ms 帧、20ms 步进，取 80–400Hz 内最强相关峰的中位数。够用且零依赖。

    自相关是 O(帧长²)：整段 5 分钟音频要跑几十秒，所以最多抽 400 帧（均匀铺开），
    中位数对抽样不敏感，长音频也一样。
    """
    frame, hop = int(sr * 0.04), int(sr * 0.02)
    lo, hi = max(2, int(sr / 400.0)), min(frame - 2, int(sr / 80.0))
    starts = list(range(0, max(1, len(audio) - frame), hop))
    stride = max(1, len(starts) // 400)
    cands = []
    for start in starts[::stride]:
        seg = audio[start:start + frame]
        seg = seg - float(seg.mean())
        energy = float(np.dot(seg, seg))
        if energy <= 1e-6:
            continue
        corr = np.correlate(seg, seg, mode="full")
        corr = corr[frame - 1:]
        if corr[0] <= 0:
            continue
        win = corr[lo:hi + 1]
        peak = int(np.argmax(win))
        if win[peak] < 0.3 * corr[0]:
            continue
        cands.append(sr / float(lo + peak))
    return float(np.median(cands)) if len(cands) >= 3 else None


def measure(path, text):
    audio, sr = _load_mono(path)
    dur = len(audio) / float(sr)
    cps = (len(_NOISE.sub("", text or "")) / dur) if dur > 0 else 0.0
    hz = _median_f0(audio, sr)
    derived = {"duration_s": round(dur, 2), "cps": round(cps, 2),
               "f0_hz": round(hz, 1) if hz else None}
    tags = {"pace": round(tag_vocab.scale_pace(cps), 3)}
    if hz:
        tags["pitch"] = round(tag_vocab.scale_pitch(hz), 3)
    return derived, tags


# ---- 来源解析 ----

def _lab_record(rec_id):
    path = os.path.join(_ctx["designed_dir"], "voice_lab_manifest.json")
    try:
        with open(path, encoding="utf-8") as f:
            recs = json.load(f)
    except (OSError, ValueError):
        recs = []
    rec = next((r for r in recs if r.get("id") == rec_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail=f"实验室记录不存在：{rec_id}")
    rel = os.path.relpath(os.path.join(_ctx["designed_dir"], "previews",
                                      os.path.basename(rec.get("audio_url") or "")), _root())
    if not os.path.exists(_abs(rel)):
        raise HTTPException(status_code=404, detail="记录对应的音频文件已不在 previews 里")
    return {"rel": rel, "text": rec.get("sample_text") or "",
            "role": rec.get("speaker") or "", "src_id": rec_id}


def _chunk_record(index):
    with open(os.path.join(_root(), "chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)
    rows = chunks if isinstance(chunks, list) else chunks.get("chunks", [])
    try:
        row = rows[int(index)]
    except (IndexError, TypeError, ValueError):
        raise HTTPException(status_code=404, detail=f"段序号不存在：{index}")
    rel = row.get("audio_path") or ""
    if not rel or not os.path.exists(_abs(rel)):
        raise HTTPException(status_code=400, detail="该段还没有生成音频，先进生成车间跑出来")
    return {"rel": rel, "text": row.get("text") or "",
            "role": row.get("speaker") or "", "src_id": str(int(index))}


def _file_record(rel):
    if not os.path.exists(_abs(rel)) or not _within_root(_abs(rel)):
        raise HTTPException(status_code=400, detail=f"路径不可用或越出工作区：{rel}")
    return {"rel": rel, "text": "", "role": "", "src_id": rel}


class AddReq(BaseModel):
    kind: str = "lab"          # lab | chunk | file
    src: str = ""              # 记录 id / 段序号 / root 下相对路径
    role: str = ""
    text: str = ""
    tags: dict = Field(default_factory=dict)


class UpdateReq(BaseModel):
    id: int
    role: Optional[str] = None
    text: Optional[str] = None
    tags: Optional[dict] = None



def _row(r, with_vector=False):
    tags = json.loads(r["tags"] or "{}")
    derived = json.loads(r["derived"] or "{}")
    out = {"id": r["id"], "kind": r["kind"], "src_id": r["src_id"], "role": r["role"],
           "text": r["text"], "tags": tags, "derived": derived,
           "rating": int(tags.get("rating", 0)), "note": tags.get("note", ""),
           "audio_url": _url(r["path"]), "missing": not os.path.exists(_abs(r["path"])),
           "created_at": r["created_at"], "tag_prompt": tag_vocab.as_prompt(tags)}
    if with_vector:
        out["vector"] = tag_vocab.to_vector(tags)
    return out


@router.get("/api/vault/schema")
async def vault_schema():
    return {"facets": tag_vocab.schema(), "layout": tag_vocab.layout(),
            "emotions": tag_vocab.emotion_keys(),
            "bounds": {"pace_cps": list(tag_vocab.PACE_BOUNDS),
                       "pitch_hz": list(tag_vocab.PITCH_BOUNDS)}}


@router.post("/api/vault/add")
async def vault_add(req: AddReq):
    if req.kind == "lab":
        src = _lab_record(req.src)
    elif req.kind == "chunk":
        src = _chunk_record(req.src)
    elif req.kind == "file":
        src = _file_record(req.src)
    else:
        raise HTTPException(status_code=400, detail=f"未知来源类型：{req.kind}")

    try:
        tags = tag_vocab.validate(req.tags)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    text = req.text or src["text"]
    try:
        derived, measured = measure(_abs(src["rel"]), text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"音频测量失败：{exc}")
    # 人工标的 pace/pitch 优先：机器量出来的是基线，人耳才是终判
    for key, val in measured.items():
        tags.setdefault(key, val)

    db, pid = _db()
    sql = ("INSERT INTO voice_samples(project_id, kind, src_id, path, role, text, tags, derived) "
           "VALUES(?,?,?,?,?,?,?,?) "
           "ON CONFLICT(project_id, kind, src_id, path) DO UPDATE SET "
           "role=excluded.role, text=excluded.text, tags=excluded.tags, derived=excluded.derived "
           "RETURNING id")
    cur = db.con.execute(
        sql,
        (pid, req.kind, src["src_id"], src["rel"], req.role or src["role"], text,
         json.dumps(tags, ensure_ascii=False), json.dumps(derived, ensure_ascii=False)))
    sid = cur.fetchone()[0]   # RETURNING 的游标必须先取空，否则 commit 报 statements in progress
    cur.close()
    db.con.commit()
    row = db.con.execute('SELECT * FROM voice_samples WHERE id=?', (sid,)).fetchone()
    return _row(row)


def _match(row, f):
    tags = json.loads(row["tags"] or "{}")
    if f["role"] and row["role"] != f["role"]:
        return False
    if f["emotion"] and tags.get("emotion") != f["emotion"]:
        return False
    if f["bond"] and tags.get("bond") != f["bond"]:
        return False
    for key in ("scene", "timbre"):
        want = [x for x in (f[key] or "").split(",") if x]
        if want and not set(want) & set(tags.get(key) or []):
            return False
    if f["min_rating"] and int(tags.get("rating", 0)) < f["min_rating"]:
        return False
    for key in ("pace", "pitch"):
        for bound, val in ((f[key + "_min"], "min"), (f[key + "_max"], "max")):
            if bound is None:
                continue
            got = tags.get(key)
            if got is None or (val == "min" and got < bound) or (val == "max" and got > bound):
                return False
    if f["q"] and f["q"] not in (row["text"] or "") and f["q"] not in tags.get("note", ""):
        return False
    return True


def _filters(role, emotion, bond, scene, timbre, q, min_rating, pace_min, pace_max, pitch_min, pitch_max):
    return {"role": role, "emotion": emotion, "bond": bond, "scene": scene, "timbre": timbre,
            "q": q, "min_rating": min_rating,
            "pace_min": pace_min, "pace_max": pace_max,
            "pitch_min": pitch_min, "pitch_max": pitch_max}


@router.get("/api/vault/list")
async def vault_list(role: str = "", emotion: str = "", bond: str = "", scene: str = "",
                     timbre: str = "", q: str = "", min_rating: int = 0,
                     pace_min: float = None, pace_max: float = None,
                     pitch_min: float = None, pitch_max: float = None,
                     limit: int = 20, offset: int = 0):
    db, pid = _db()
    f = _filters(role, emotion, bond, scene, timbre, q, min_rating,
                 pace_min, pace_max, pitch_min, pitch_max)
    rows = [r for r in db.con.execute(
        'SELECT * FROM voice_samples WHERE project_id=? ORDER BY id DESC', (pid,)).fetchall()
        if _match(r, f)]
    return {"rows": [_row(r) for r in rows[offset:offset + limit]],
            "total": len(rows), "limit": limit, "offset": offset}


@router.get("/api/vault/pick")
async def vault_pick(role: str = "", emotion: str = "", bond: str = "", scene: str = "",
                     timbre: str = "", min_rating: int = 0,
                     pace_min: float = None, pace_max: float = None,
                     pitch_min: float = None, pitch_max: float = None,
                     limit: int = 3):
    """给 LLM 的出口：按角色 + 情节/情绪/语速区间挑最合适的现成声音，带回向量与说明串。"""
    db, pid = _db()
    f = _filters(role, emotion, bond, scene, timbre, "", min_rating,
                 pace_min, pace_max, pitch_min, pitch_max)
    rows = [r for r in db.con.execute(
        'SELECT * FROM voice_samples WHERE project_id=? ORDER BY id DESC', (pid,)).fetchall()
        if _match(r, f)]
    rows.sort(key=lambda r: (int(json.loads(r["tags"] or "{}").get("rating", 0)),
                             r["created_at"] or ""), reverse=True)
    return {"candidates": [_row(r, with_vector=True) for r in rows[:limit]],
            "total": len(rows), "layout": tag_vocab.layout()}


@router.post("/api/vault/update")
async def vault_update(req: UpdateReq):
    """tags 是全量快照：没传的维度即清掉。pace/pitch 属实测，本次没显式给就按 derived 重算。"""
    db, pid = _db()
    row = db.con.execute('SELECT * FROM voice_samples WHERE id=? AND project_id=?',
                         (req.id, pid)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"仓库条目不存在：{req.id}")
    text = row["text"] if req.text is None else req.text
    role = row["role"] if req.role is None else req.role
    derived = json.loads(row["derived"] or "{}")
    remeasured = req.text is not None and req.text != row["text"]
    if remeasured:
        derived, _ = measure(_abs(row["path"]), text)
    tags = json.loads(row["tags"] or "{}")
    if req.tags:
        try:
            tags = tag_vocab.validate(req.tags)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    for key, raw, scale in (("pace", derived.get("cps"), tag_vocab.scale_pace),
                            ("pitch", derived.get("f0_hz"), tag_vocab.scale_pitch)):
        if raw and (remeasured or key not in tags):
            tags[key] = round(scale(raw), 3)
    db.con.execute('UPDATE voice_samples SET role=?, text=?, tags=?, derived=? WHERE id=?',
                   (role, text, json.dumps(tags, ensure_ascii=False),
                    json.dumps(derived, ensure_ascii=False), req.id))
    db.con.commit()
    return _row(db.con.execute('SELECT * FROM voice_samples WHERE id=?', (req.id,)).fetchone())


@router.delete("/api/vault/{sample_id}")
async def vault_delete(sample_id: int, purge: bool = False):
    """删条目默认只摘标签；purge=true 才删文件，且只允许 designed_voices/clone_voices 下的产物。"""
    db, pid = _db()
    row = db.con.execute('SELECT * FROM voice_samples WHERE id=? AND project_id=?',
                         (sample_id, pid)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"仓库条目不存在：{sample_id}")
    removed = None
    if purge:
        real = os.path.realpath(_abs(row["path"]))
        guarded = [os.path.realpath(_ctx["designed_dir"]), os.path.realpath(_ctx["clone_dir"])]
        if not any(real.startswith(d + os.sep) for d in guarded):
            raise HTTPException(status_code=400, detail="该路径不是仓库自有产物，只删条目不删文件")
        if os.path.exists(real):
            os.remove(real)
            removed = row["path"]
    db.con.execute('DELETE FROM voice_samples WHERE id=?', (sample_id,))
    db.con.commit()
    return {"status": "deleted", "id": sample_id, "purged_file": removed}


if __name__ == "__main__":
    # 离机自检：造一个 120Hz 正弦 wav，验证路径围栏、语速与基频实测。
    import tempfile
    root = tempfile.mkdtemp(prefix="vault_selftest_")
    _ctx.update({"root_dir": root, "designed_dir": os.path.join(root, "designed_voices"),
                 "clone_dir": os.path.join(root, "clone_voices")})
    assert _within_root(os.path.join(root, "voicelines", "a.wav"))
    assert not _within_root(os.path.join(root, "..", "escape.wav"))
    assert not _within_root("/etc/passwd")

    import soundfile as sf
    sr = 16000
    os.makedirs(_abs("voicelines"), exist_ok=True)
    t = np.arange(sr) / float(sr)
    sf.write(_abs("voicelines/sine.wav"), (0.3 * np.sin(2 * np.pi * 120.0 * t)).astype("float32"), sr)
    derived, measured = measure(_abs("voicelines/sine.wav"), "一二三四五六七八")
    assert abs(derived["f0_hz"] - 120.0) <= 12.0, derived
    assert abs(derived["cps"] - 8.0) <= 0.1, derived
    assert derived["duration_s"] == 1.0 and measured["pace"] == 1.0, (derived, measured)
    print("AUDIO_VAULT_SELFTEST_OK", derived, measured)
'''

APP_MOUNT_ANCHOR = "app.include_router(voice_lab_router)"

VAULT_MOUNT = '''app.include_router(voice_lab_router)

import audio_vault
audio_vault.init(project_manager=project_manager, root_dir=ROOT_DIR,
                 designed_dir=DESIGNED_VOICES_DIR, clone_dir=CLONE_VOICES_DIR)
app.include_router(audio_vault.router)'''

NDB_ANCHOR = "CREATE TABLE IF NOT EXISTS jobs("

NDB_TABLE = '''CREATE TABLE IF NOT EXISTS voice_samples(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                       -- lab | chunk | file
  src_id TEXT DEFAULT '',                   -- 来源标识：实验室记录 id / 段序号 / 相对路径
  path TEXT NOT NULL,                       -- 相对 ROOT_DIR 的音频路径
  role TEXT DEFAULT '',                     -- 人物 key：不是标签维度，单列才好筛
  text TEXT DEFAULT '',
  tags TEXT DEFAULT '{}',                   -- tag_vocab 校验后的标签（含 pace/pitch 归一值）
  derived TEXT DEFAULT '{}',                -- 实测原始值：时长/字每秒/基频
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(project_id, kind, src_id, path));  -- 同源重复入库即覆盖，不产生重复行

CREATE TABLE IF NOT EXISTS jobs('''

LAB_HISTORY_ANCHOR = '''@router.get("/api/voice_lab/history")
async def voice_lab_history(limit: int = 60):
    path = os.path.join(_ctx["designed_dir"], "voice_lab_manifest.json")
    try:
        with open(path, encoding="utf-8") as f:
            recs = json.load(f)
    except (OSError, ValueError):
        recs = []
    return {"records": list(reversed(recs))[:limit]}'''

LAB_RECORDS = '''def _lab_path():
    return os.path.join(_ctx["designed_dir"], "voice_lab_manifest.json")


def _lab_records():
    """清单的唯一读口：列表/改/删都走这里，不各处各读各写。"""
    try:
        with open(_lab_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _lab_write(records):
    path = _lab_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records[-1000:], f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


@router.get("/api/voice_lab/history")
async def voice_lab_history(limit: int = 20, offset: int = 0,
                            speaker: str = "", model_key: str = "", q: str = ""):
    """倒序分页：page = offset/limit。清单是千级量，过滤直接在 Python 侧做。"""
    recs = list(reversed(_lab_records()))
    if speaker:
        recs = [r for r in recs if r.get("speaker") == speaker]
    if model_key:
        recs = [r for r in recs if r.get("model_key") == model_key]
    if q:
        recs = [r for r in recs
                if q in (r.get("sample_text") or "") or q in ((r.get("tags") or {}).get("note") or "")]
    return {"records": recs[offset:offset + limit], "total": len(recs),
            "limit": limit, "offset": offset}


class RecordUpdate(BaseModel):
    id: str
    tags: dict = {}
    text: str = None
    speaker: str = None


class RecordDelete(BaseModel):
    id: str
    purge: bool = False


@router.post("/api/voice_lab/record/update")
async def voice_lab_record_update(req: RecordUpdate):
    """标注/修改：tags 是这条记录的**全量快照**（传子集会删掉没传的维度），一律过 tag_vocab 校验。"""
    import tag_vocab
    recs = _lab_records()
    hit = next((r for r in recs if r.get("id") == req.id), None)
    if not hit:
        raise HTTPException(status_code=404, detail="记录不存在")
    if req.tags:
        try:
            hit["tags"] = tag_vocab.validate(req.tags)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if req.text is not None:
        hit["sample_text"] = req.text
    if req.speaker is not None:
        hit["speaker"] = req.speaker
    _lab_write(recs)
    return hit


@router.post("/api/voice_lab/record/delete")
async def voice_lab_record_delete(req: RecordDelete):
    """删记录默认不动音频文件：那条 wav 可能正被当参考样本用。purge=true 才删 previews 下的文件。"""
    recs = _lab_records()
    hit = next((r for r in recs if r.get("id") == req.id), None)
    if not hit:
        raise HTTPException(status_code=404, detail="记录不存在")
    rest = [r for r in recs if r.get("id") != req.id]
    _lab_write(rest)
    purged = None
    if req.purge:
        preview_dir = os.path.realpath(os.path.join(_ctx["designed_dir"], "previews"))
        target = os.path.realpath(os.path.join(preview_dir, os.path.basename(hit.get("audio_url") or "")))
        if target.startswith(preview_dir + os.sep) and os.path.exists(target):
            os.remove(target)
            purged = os.path.basename(target)
    return {"status": "deleted", "id": req.id, "purged_file": purged}'''

LAB_WRITE_ANCHOR = '''    mpath = os.path.join(_ctx["designed_dir"], "voice_lab_manifest.json")
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
    return rec'''


def patch(path, pairs, tag):
    """pairs: (old, new, marker[, optional])。marker 已存在则跳过该条。
    optional=True 的条目是给老部署做的升级迁移：锚点不在 = 本机从没装过旧版，跳过即可，
    不能让它的 assert 把同文件其他必需补丁一起带崩（patch() 是全建成功才落盘）。"""
    src = open(path, encoding="utf-8").read()
    changed = False
    for entry in pairs:
        old, new, marker = entry[:3]
        optional = entry[3] if len(entry) > 3 else False
        if marker in src:
            continue
        if optional and old not in src:
            print(f"{tag}: skip optional -> {old[:60]!r}")
            continue
        assert old in src, f"{tag}: anchor missing -> {old[:80]!r}"
        src = src.replace(old, new, 1)
        changed = True
    if not changed:
        print(f"{tag}: ALREADY")
        return
    open(path, "w", encoding="utf-8").write(src)
    print(f"{tag}: PATCHED")


os.makedirs(BASE, exist_ok=True)
open(VOC, "w", encoding="utf-8").write(VOC_SRC)
open(VAU, "w", encoding="utf-8").write(VAU_SRC)
print("VAULT_MODULES_WRITTEN")

# ---- 1) noveldb 建表 ----
patch(NDB, [(NDB_ANCHOR, NDB_TABLE, "voice_samples")], "NDB")

# ---- 2) app.py 挂路由 ----
patch(APP, [(APP_MOUNT_ANCHOR, VAULT_MOUNT, "include_router(audio_vault.router)")], "APP_MOUNT")

# ---- 3) Voice Lab：分页历史 + 记录标注/改/删，写入收敛到 _lab_write ----
patch(LAB, [
    (LAB_HISTORY_ANCHOR, LAB_RECORDS, "voice_lab/record/delete"),
    (LAB_WRITE_ANCHOR, "    recs = _lab_records()\n    recs.append(rec)\n    _lab_write(recs)\n    return rec",
     "_lab_write(recs)"),
    # 早期版本是 merge 语义（清掉一个标签删不掉），原地升级成 replace
    ('''            clean = tag_vocab.validate(req.tags)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        merged = dict(hit.get("tags") or {})
        merged.update(clean)
        hit["tags"] = merged''',
     '''            hit["tags"] = tag_vocab.validate(req.tags)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))''',
     'hit["tags"] = tag_vocab.validate(req.tags)', True),
], "LAB_RECORDS")

for f in (VOC, VAU, NDB, APP, LAB):
    py_compile.compile(f, doraise=True)
print("AUDIO_VAULT_OK")
