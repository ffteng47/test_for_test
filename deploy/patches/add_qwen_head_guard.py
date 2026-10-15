# Qwen 段首伪影守卫（幂等安装器）：生成出口一刀切。
#
# 根因（2026-10-15 诊断）：Qwen3-TTS 原始输出 13.8%（119/864）段首带病——
#   (a) 首样本不归零（s0≈−0.05）硬跳变 → 爆音；
#   (b) 头 100–220ms 低电平准谐波噪声（rms≈−29dBFS），-45dB 能量静音裁剪够不着。
# 确定性、与 seed 无关 → 重生成治不了，必须在 _save_wav 落盘前拦。
#
# 1) 写 app/head_guard.py —— 唯一实现（新生成守卫与存量修复脚本共用）
# 2) tts.py: import head_guard；_save_wav 落盘前 audio_array = head_guard.clean(...)
#    —— _save_wav 是全文件唯一 sf.write，所有引擎/实验室预览共用此咽喉点。
#
# 生效需重启后端（tts.py 是常驻模块）。存量 mp3 用 repair_qwen_heads.py 离线刷。
import os
import py_compile
import shutil

BASE = "/home/tff/software/novel-audiobook/alexandria/app"
HG = os.path.join(BASE, "head_guard.py")
TTS = os.path.join(BASE, "tts.py")

HG_SRC = r'''"""qwen 段首伪影守卫（安装器 deploy/patches/add_qwen_head_guard.py）。

两条独立动作：
1. 去爆音：首样本 |a0|>0.005 时前 5ms 线性淡入。任何引擎无害。
2. 裁孤立头噪：只有「头部有能量(>=-40dBFS) ∧ 头部整体比正文低(<=body-8dB)
   ∧ 头与正文间存在接近静音的间隙(<=-45dBFS) ∧ 正文起点在 600ms 内」同时成立才裁。
   连续起音（气声、擦音直接进正文）没有间隙 → 不动，防误伤合法轻起。
ponytail: 判定是包络级启发式；若出现「合法叹息被裁」，升级为谱特征（500-2kHz 准谐波线）判定。
"""
import numpy as np

FRAME_S = 0.01
HEAD_WIN_S = 0.6          # 正文起点只在前 600ms 内找
BURST_FLOOR_DB = -40.0    # 头部“有能量”下限
GAP_DB = -45.0            # 头/正文间的静音间隙上限
ONSET_SUSTAIN = 3         # 连续 3 帧达标才算正文开始
PRE_ROLL_S = 0.003        # 裁到正文起点前 3ms（原 20ms 会把噪底尾巴留在头上→可听"匝"）
FADE_S = 0.005


def _frames_db(a, sr, win):
    n = len(a) // win
    if n == 0:
        return np.zeros(0), 0
    rms = np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(axis=1)) + 1e-9
    return 20 * np.log10(rms), n


def clean(arr, sr):
    a = np.asarray(arr, dtype=np.float32)
    if a.ndim != 1 or len(a) < int(sr * 0.3):
        return a
    win = max(1, int(sr * FRAME_S))
    db, n = _frames_db(a, sr, win)
    if n > 40:
        body = db[int(0.4 * sr / win):]
        body = body[body > -60.0]
        if len(body):
            bm = float(np.median(body))
            thr = bm - 6.0
            loud = db >= thr
            maxo = min(n - ONSET_SUSTAIN, int(HEAD_WIN_S * sr / win))
            onset = -1
            for i in range(1, maxo):
                if loud[i] and loud[i + 1] and loud[i + 2]:
                    onset = i
                    break
            if onset > 0:
                pre = db[:onset]
                imax = int(np.argmax(pre))
                # 间隙必须在头部最响帧「之后」：先响后静才叫孤立伪影；
                # 从静到响的连续爬坡是合法气声起音，不许裁。
                if (pre.max() >= BURST_FLOOR_DB and np.median(pre) <= bm - 8.0
                        and imax < onset - 1 and pre[imax + 1:].min() <= GAP_DB):
                    start = max(0, onset * win - int(PRE_ROLL_S * sr))
                    if start > 0:
                        a = a[start:]
    f = min(int(FADE_S * sr), len(a))
    if f > 1 and abs(float(a[0])) > 0.005:
        a[:f] *= np.linspace(0.0, 1.0, f, dtype=np.float32)
    return a


if __name__ == "__main__":
    sr = 24000
    t = np.arange(int(1.0 * sr), dtype=np.float64) / sr
    speech = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    # 1) 伪影：80ms -30dB 头噪 + 100ms 间隙 + 正常正文 → 必裁
    bad = np.concatenate([0.03 * np.ones(int(0.08 * sr), dtype=np.float32),
                          1e-5 * np.ones(int(0.1 * sr), dtype=np.float32), speech])
    out = clean(bad, sr)
    assert len(out) < len(bad) - int(0.1 * sr), (len(bad), len(out))
    # 1b) 预卷收紧：裁后首 10ms 必须已进语音（防 20ms 旧行为留静音/噪底尾巴）
    r0 = np.sqrt((out[:int(0.01 * sr)] ** 2).mean())
    assert 20 * np.log10(r0 + 1e-9) > -25.0, "预卷里还留着尾巴"
    # 2) 连续气声起音（无间隙）→ 不许裁
    soft = np.concatenate([np.linspace(0.001, 0.3, int(0.3 * sr)).astype(np.float32),
                           speech[:int(0.5 * sr)]])
    s0 = soft[0]
    soft2 = soft.copy(); soft2[0] = 0.2  # 人为加回首样本跳变
    out2 = clean(soft2, sr)
    assert len(out2) == len(soft2), (len(out2), len(soft2))
    assert abs(float(out2[0])) < 0.01, "淡入没生效"
    # 3) 纯静音头（无能量）→ 不裁
    quiet = np.concatenate([1e-5 * np.ones(int(0.3 * sr), dtype=np.float32), speech])
    assert len(clean(quiet, sr)) == len(quiet)
    # 4) 过短音频原样返回
    tiny = np.zeros(int(0.1 * sr), dtype=np.float32)
    assert len(clean(tiny, sr)) == len(tiny)
    print("head_guard self-check OK")
'''

PAIRS = [
    ("import engines\n", "import engines\nimport head_guard\n", "import head_guard"),
    ("        sf.write(output_path, audio_array, sample_rate)",
     "        audio_array = head_guard.clean(audio_array, sample_rate)\n"
     "        sf.write(output_path, audio_array, sample_rate)",
     "head_guard.clean"),
]


def main():
    src = open(TTS, encoding="utf-8").read()
    done = [m in src for m, _ in [(p[2], 0) for p in PAIRS]]
    with open(HG, "w", encoding="utf-8") as f:
        f.write(HG_SRC)
    try:
        py_compile.compile(HG, doraise=True)
    except py_compile.PyCompileError as e:
        os.remove(HG)
        raise SystemExit(f"GUARD_FAIL: head_guard 编译失败 {e}")
    if all(done):
        print("TTS: ALREADY")
        return
    bak = TTS + ".bak_pre_head_guard"
    if not os.path.exists(bak):
        shutil.copy2(TTS, bak)
    for old, new, marker in PAIRS:
        if marker in src:
            continue
        assert old in src, f"TTS: anchor missing -> {old!r}"
        src = src.replace(old, new, 1)
    try:
        compile(src, TTS, "exec")
    except SyntaxError as e:
        raise SystemExit(f"TTS: 编译失败，未写入 {e}")
    with open(TTS, "w", encoding="utf-8") as f:
        f.write(src)
    print("TTS: PATCHED")


if __name__ == "__main__":
    main()
