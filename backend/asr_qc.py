"""asr_qc — 音频回听质检（第⑤层）：faster-whisper 转录逐段音频，与剧本文本对齐算错误率。

原则：这是“确定性”质检数据源，替代示意徽标。err = 1 - 字级相似度。
模型：Systran/faster-whisper-large-v3（HF 缓存已有 snapshot），GPU float16。

用法（3090 venv）：
    HF_HOME=/home/tff/software/novel-audiobook/hf-cache \
    python3 asr_qc.py [--limit N] [--write]     # --write 回写 DB segments.qc
"""
from __future__ import annotations

import argparse
import difflib
import glob
import os
import re
import subprocess
import sys

import numpy as np

from domain import active_project_id, workspace_paths
from noveldb import Db, open_db

ERR_THRESHOLD = 0.08  # 经验值：中文 TTS 回听 CER 通常 <5%，>8% 基本是吞字/重复

_KEEP = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uf900-\ufaffa-zA-Z0-9]')

# 拼音级比对：同音字（云雯/云文）、繁简（你問我）、标点差异全部归零，
# 只留真吞字/多字。不装 pypinyin 则退回字级比对。
try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None


# Whisper 恒把数字转写为阿拉伯数字（三→3），逐位映射成拼音使两侧对齐。
# 位值读法仍有残差（三百零一 vs 301 → sanlingyi vs sanbailingyi），短促计数句留给人耳终检。
_DIGITS = {ord(c): w for c, w in zip('0123456789',
                                     'ling yi er san si wu liu qi ba jiu'.split())}


def normalize(text: str) -> str:
    n = ''.join(_KEEP.findall(text))
    if lazy_pinyin:
        return ''.join(lazy_pinyin(n)).translate(_DIGITS)
    return n


def err_rate(expected: str, heard: str) -> float:
    a, b = normalize(expected), normalize(heard)
    if not a:
        return 0.0 if not b else 1.0
    return round(1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 4)


def _find_model() -> str:
    hub = os.path.join(os.environ.get('HF_HOME', ''), 'hub')
    hits = sorted(glob.glob(os.path.join(hub, 'models--Systran--faster-whisper-large-v3', 'snapshots', '*')))
    if not hits:
        raise SystemExit('faster-whisper-large-v3 snapshot 不在 HF_HOME 缓存，先跑 download_extra_models.sh')
    return hits[-1]


def _ensure_cuda_libs():
    """venv 的 nvidia/cublas 等 wheel 库不在链接器路径里，re-exec 自己注入 LD_LIBRARY_PATH。
    系统级 symlink 会波及 mineru 等共享 GPU 服务，故只作用于本进程。"""
    if os.environ.get('NOVELQC_CUDA'):
        return
    import sysconfig
    sp = sysconfig.get_paths()['purelib']
    libs = ':'.join(sorted(glob.glob(os.path.join(sp, 'nvidia', '*', 'lib'))))
    if not libs:
        return
    env = dict(os.environ,
               LD_LIBRARY_PATH=(libs + ':' + os.environ.get('LD_LIBRARY_PATH', '')).rstrip(':'),
               NOVELQC_CUDA='1')
    os.execve(sys.executable, [sys.executable] + sys.argv, env)


def _load16k(path: str) -> 'np.ndarray':
    """绕开 faster-whisper/PyAV 兼容坑：ffmpeg 解码为 16k 单声道 float32。"""
    raw = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def run(limit: int | None = None, write: bool = False) -> list[dict]:
    from faster_whisper import WhisperModel
    paths = workspace_paths()
    db = Db(open_db(paths['db']))
    pid = active_project_id(db.con)
    segs = [dict(r) for r in db.segments(pid) if r['status'] == 'done' and r['audio_path']]
    if limit:
        segs = segs[:limit]

    root = os.path.dirname(paths['db'])
    model = WhisperModel(_find_model(), device='cuda', compute_type='float16')
    results = []
    for s in segs:
        wav = os.path.join(root, s['audio_path'])
        if not os.path.exists(wav):
            results.append({'ord': s['ord'], 'err': 1.0, 'qc': 'retry', 'detail': '音频文件缺失'})
            print(f"#{s['ord']:>3} err=1.000 retry 音频文件缺失: {wav}")
            if write:
                db.set_segment_qc(s['id'], 'retry', 1.0)
            continue
        heard_segs, _info = model.transcribe(_load16k(wav), language='zh', beam_size=1)
        text = ' '.join(s.text for s in heard_segs)
        e = err_rate(s['text'], text)
        qc = 'pass' if e <= ERR_THRESHOLD else 'retry'
        results.append({'ord': s['ord'], 'err': e, 'qc': qc, 'heard': text[:60]})
        print(f"#{s['ord']:>3} err={e:.3f} {qc}  {s['text'][:24]}… | 听到: {text[:24]}…")
        if write:
            db.set_segment_qc(s['id'], qc, e)
    return results


if __name__ == '__main__':
    _ensure_cuda_libs()
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    rs = run(args.limit, args.write)
    bad = [r for r in rs if r.get('qc') == 'retry' or r['err'] > ERR_THRESHOLD]
    print(f"ASR_QC: {len(rs)} 段, {len(bad)} 段待复核")

    # selftest：对齐逻辑本身不依赖 GPU
    assert err_rate('雨下到第三天的时候。', '雨下到第三天的时候') == 0.0
    assert err_rate('少爷，老爷请您回去。', '老爷请您回去') > 0.0
    if lazy_pinyin:  # 同音/繁简/数字转写不再是错误
        assert err_rate('云雯！这边！', '云文 这边') == 0.0
        assert err_rate('你问我为什么来到这里？', '你問我為什麼來到這裡') == 0.0
        assert err_rate('三。', '3') == 0.0
    print('SELFTEST OK')
