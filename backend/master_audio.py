"""交付级母带处理：两遍 EBU R128 响度归一 + 真峰值限制 + 验收判定。

这里是「成品能不能交出去」的唯一判定源。导出链路（`app/project.py` 的
`merge_audio` / `merge_m4b`，经 `deploy/patches/add_export_loudnorm.py` 接入）
与命令行复检共用本模块，不允许出现第二套阈值。

用法：
    python3 backend/master_audio.py 输入.m4b 输出.m4b     # 保章节重编码
    python3 backend/master_audio.py 输入.wav 输出.wav      # 导出链路走这条
    python3 backend/master_audio.py --check                # 模块自检
    python3 backend/master_audio.py --inspect 成品.m4b      # 只出全项实测 + 判定，不改写文件
    python3 backend/master_audio.py --boundaries voicelines/   # 段边界拼接痕标定（M2，可加 --clip-dir 出复听片段）

三个非显而易见的约束，改之前先读：
  1. `linear=true` 是章节时间轴可信的前提。 loudnorm 的动态模式会逐段伸缩增益，
     时间轴随之漂移，M4B 的章节标记就会指错位置。线性模式只做恒定增益。
  2. `alimiter` 必须显式 `level=0`。本机 ffmpeg build 的自动补偿增益默认开启，
     实测会把结果顶到 −14.8 LUFS / +0.19 dBTP，响度和峰值同时破。
  3. 采样峰值 ≠ 帧间真峰值。alimiter 限前者，验收读后者（dBTP，恒高于采样峰值），
     不留 TP_MARGIN_DB 时实测卡在 −1.19 dBTP，过不了 −1.5。

渠道清单里的「底噪检测」一项，在本产线上改测段边界拼接痕，理由见 boundary_flags()。
"""
import argparse
import array
import json
import math
import os
import re
import subprocess
import sys

# ── 阈值（对外承诺见 docs/price-list.md 的验收口径）────────────────
TARGET_I = -16.0        # 综合响度目标 LUFS
TOL_I = 1.0             # 容差 LU
TARGET_TP = -1.5        # 真峰值上限 dBTP
TP_MARGIN_DB = 2.0      # 帧间余量，见模块注释 3。1.0 时实测（shuxue 全卷）ISP 过冲 +1.58 dB，
                        # 采样天花板 −2.5 dBFS 被打成 −0.92 dBTP 顶穿 −1.5；2.0 → 预测 ≈ −1.92
TARGET_LRA = 7.0        # 动态范围目标 LU
SAMPLE_RATE = 44100
MAX_DURATION_DRIFT_S = 0.5
EDGE_FLOOR_DB = -45.0       # 绝对 dBFS，与 SILENCE_FLOOR_DB（相对段峰）不是一个量纲，别混用
EDGE_WIN_S = 5.0            # 首尾静默只扫文件两端各这么多次
MAX_MB = 170.0              # 渠道单文件上限，客户口径不卡这条

# 段边界拼接痕的跳变上限（相对本段峰值的 dB）。首版猜 −12，必须拿真实产料标定后定稿，
# 见 boundary_flags() 打印的分布与 docs/post-production-plan.md M2 的复听验收。
JUMP_FLAG_DB = -12.0
SILENCE_FLOOR_DB = -45.0    # 相对本段峰值，越过这条线算「段里开始有声音了」
AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".ogg")


def _run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")


def _parse_stats(stderr):
    """从 ffmpeg 的 stderr 里取 loudnorm 的 JSON（它不打到 stdout）。"""
    start, end = stderr.rfind("{"), stderr.rfind("}") + 1
    if start < 0 or end <= start:
        raise RuntimeError(f"ffmpeg 未返回 loudnorm JSON:\n{stderr[-400:]}")
    stats = json.loads(stderr[start:end])
    missing = [k for k in ("input_i", "input_lra", "input_tp",
                           "input_thresh", "target_offset") if k not in stats]
    if missing:
        raise RuntimeError(f"测量字段缺失: {missing}")
    return stats


def measure(path):
    """第一遍：实测输入（或复核输出）的响度参数。"""
    r = _run(["ffmpeg", "-nostats", "-hide_banner", "-i", path,
              "-af", f"loudnorm=I={TARGET_I}:LRA={TARGET_LRA}:TP={TARGET_TP}:print_format=json",
              "-f", "null", "-"])
    if r.returncode != 0:
        raise RuntimeError(f"测量失败 rc={r.returncode}: {r.stderr[-400:]}")
    return _parse_stats(r.stderr)


def duration(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "csv=p=0", path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise RuntimeError(f"ffprobe 读不到时长: {path} / {r.stdout!r}")


def rms_db(path):
    """渠道口径的宽带非门控 RMS（dBFS）。与 LUFS **不等价**，别拿一个换算另一个：
    实测差值在商用真人演播上是 +3.55 LU、在我方母带上只有 +0.65 LU，
    见 docs/channel-master-checklist.md §2.2。"""
    r = _run(["ffmpeg", "-nostats", "-hide_banner", "-i", path,
              "-af", "astats=measure_overall=RMS_level:measure_perchannel=0", "-f", "null", "-"])
    m = re.search(r"RMS level dB:\s*(-?[\d.]+|inf)", r.stderr)
    if not m:
        raise RuntimeError(f"astats 未返回 RMS: {r.stderr[-300:]}")
    txt = m.group(1)
    return None if txt == "inf" else float(txt)


def edge_silence_ms(path, win=EDGE_WIN_S):
    """文件头/尾静音 ms——渠道家族要求「头 ≈0.5 s、尾 ≈1.0 s」（清单 §1 第 10 项）。

    只解码头尾各 win 秒：母带是整本书，全量解码要 250 MB 内存和几分钟，这两条边用不着。
    """
    d = duration(path)

    def scan(ss, is_head):
        a = _mono_f32(path, ss=ss, t=min(win, d))
        if not a:
            return None
        onset = 10 ** (EDGE_FLOOR_DB / 20)
        if is_head:
            for i, x in enumerate(a):
                if abs(x) > onset:
                    return round(i / SAMPLE_RATE * 1000)
            return round(len(a) / SAMPLE_RATE * 1000)
        for i in range(len(a) - 1, -1, -1):
            if abs(a[i]) > onset:
                return round((len(a) - 1 - i) / SAMPLE_RATE * 1000)
        return round(len(a) / SAMPLE_RATE * 1000)

    return scan(0, True), scan(max(0, d - win), False)


def inspect(path, m=None):
    """一个成品文件的全项实测。闸门只看 `gate()` 那几项，其余是报给渠道/客户看的数。"""
    m = m or measure(path)
    head, tail = edge_silence_ms(path)
    return {
        "LUFS": float(m["input_i"]),
        "LRA_LU": float(m["input_lra"]),
        "真峰值dBTP": float(m["input_tp"]),
        "RMS_dB": rms_db(path),
        "时长s": round(duration(path), 2),
        "章节数": _count_chapters(path),
        "体积MB": round(os.path.getsize(path) / 1048576, 1),
        "首静默ms": head,
        "尾静默ms": tail,
    }


def gate(v, target_i=TARGET_I, target_tp=TARGET_TP):
    """客户交付口径的硬判据。只有这几项能拦交付——其余实测是「报数」，
    体积/首尾静默/RMS 属渠道 profile，在这里 fail 了也不该挡客户收货。"""
    return {
        f"响度落在 {target_i:+.0f}±{TOL_I:.1f} LU": abs(v["LUFS"] - target_i) <= TOL_I,
        f"真峰值 ≤ {target_tp:+.1f} dBTP": v["真峰值dBTP"] <= target_tp,
    }


def channel_gate(v):
    """渠道上架口径（AR/ACX 家族）的判据，实测数出问题用；默认导出链路不调它。"""
    return {
        "RMS 落在 −23 ～ −18 dB": v["RMS_dB"] is not None and -23.0 <= v["RMS_dB"] <= -18.0,
        "真峰值 ≤ −3 dB": v["真峰值dBTP"] <= -3.0,
        f"单文件 ≤ {MAX_MB:.0f} MB": v["体积MB"] <= MAX_MB,
    }


def _count_chapters(path):
    r = _run(["ffprobe", "-v", "error", "-show_chapters", "-of", "json", path])
    try:
        return len(json.loads(r.stdout or "{}").get("chapters", []))
    except json.JSONDecodeError:
        return 0


def _has_cover(path):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v",
              "-show_entries", "stream=index", "-of", "csv=p=0", path])
    return bool(r.stdout.strip())


def _encode_args(src, dst):
    """按输出后缀决定编码参数；M4B 要把章节/封面/元数据从输入带过来，否则母带标记会丢。"""
    suffix = dst[dst.rfind("."):].lower() if "." in dst.rsplit("/", 1)[-1] else ""
    if suffix in (".m4b", ".m4a", ".mp4"):
        args = ["-map_metadata", "0", "-map_chapters", "0", "-map", "0:a",
                "-c:a", "aac", "-b:a", "128k", "-ar", str(SAMPLE_RATE),
                "-movflags", "+faststart"]
        if _has_cover(src):
            args += ["-map", "0:v", "-c:v", "copy", "-disposition:v:0", "attached_pic"]
        return args
    if suffix == ".wav":
        return ["-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le"]
    if suffix == ".mp3":
        return ["-ar", str(SAMPLE_RATE), "-c:a", "libmp3lame", "-b:a", "128k"]
    raise RuntimeError(f"不支持的输出格式: {suffix or dst}")


def normalize(src, dst, target_i=TARGET_I, target_tp=TARGET_TP, lra=TARGET_LRA):
    """两遍归一 + 真峰值限制，返回验收报告 dict。dst 的后缀决定输出编码。"""
    m_in = measure(src)
    af = (f"loudnorm=I={target_i}:LRA={lra}:TP={target_tp}"
          f":measured_I={m_in['input_i']}:measured_LRA={m_in['input_lra']}"
          f":measured_TP={m_in['input_tp']}:measured_thresh={m_in['input_thresh']}"
          f":offset={m_in['target_offset']}:linear=true"
          f",alimiter=limit={10 ** ((target_tp - TP_MARGIN_DB) / 20):.4f}:level=0")

    r = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
              "-i", src, "-af", af] + _encode_args(src, dst) + [dst])
    if r.returncode != 0:
        raise RuntimeError(f"归一失败 rc={r.returncode}: {r.stderr[-500:]}")

    m_out = measure(dst)
    return build_report(src, dst, m_in, m_out, target_i, target_tp)


def build_report(src, dst, m_in, m_out, target_i, target_tp):
    """判定一律读实测输出，不信任滤镜的自我声明。"""
    v = inspect(dst, m=m_out)
    d_in = duration(src)
    checks = gate(v, target_i, target_tp)
    checks["时长未漂移（章节轴可信）"] = abs(v["时长s"] - d_in) <= MAX_DURATION_DRIFT_S
    ch_src, ch_dst = _count_chapters(src), v["章节数"]
    if ch_src:                     # WAV 一类的 0 章输入没什么可守恒的
        checks["章节数未丢失"] = ch_dst >= ch_src
    return {
        "输入": src, "输出": dst,
        "输入LUFS": float(m_in["input_i"]),
        "输入真峰值dBTP": float(m_in["input_tp"]),
        "输出LUFS": v["LUFS"],
        "输出真峰值dBTP": v["真峰值dBTP"],
        "输出LRA_LU": v["LRA_LU"],
        "输入时长s": round(d_in, 2),
        "输出时长s": v["时长s"],
        "章节数": f"{ch_src}→{ch_dst}",
        "全项实测": v,
        "渠道口径参考": channel_gate(v),
        "验收": checks,
        "通过": all(checks.values()),
    }


def finalize(output_path, expect_chapters=0):
    """把中间态报告升级成对**真成品**的判定，就地改写 `delivery_report.json`。

    `normalize()` 只能量归一后那个中间 WAV：章节标记、最终体积、AAC 编码带来的响度偏移，
    都是后面那次编码才产生的。「导出把 259 章弄没了」正是这一层该拦的事，量错文件等于没拦。
    量不了＝不合格：绝不把中间态那句「通过」留给客户当成品判定。
    """
    book_dir = os.path.dirname(os.path.realpath(output_path))
    rp = os.path.join(book_dir, "delivery_report.json")
    rep = {}
    if os.path.exists(rp):
        try:
            with open(rp, encoding="utf-8") as f:
                rep = json.load(f)
        except (OSError, ValueError):
            rep = {}
    ref = rep.get("全项实测") or {}
    try:
        v = inspect(output_path)
        checks = gate(v)
        if ref.get("时长s"):
            checks["编码未改变时长（章节轴可信）"] = abs(v["时长s"] - ref["时长s"]) <= MAX_DURATION_DRIFT_S
        if expect_chapters:
            checks[f"章节标记齐全（期望 {expect_chapters} 章）"] = v["章节数"] >= expect_chapters
        out = {"书": os.path.basename(book_dir), "成品": output_path,
               "输出LUFS": v["LUFS"], "输出真峰值dBTP": v["真峰值dBTP"],
               "输出LRA_LU": v["LRA_LU"], "输出时长s": v["时长s"],
               "章节数": f'{ref.get("章节数", 0)}→{v["章节数"]}',
               "全项实测": v, "渠道口径参考": channel_gate(v),
               "验收": checks, "通过": all(checks.values())}
    except Exception as exc:
        out = {"书": os.path.basename(book_dir), "成品": output_path,
               "错误": str(exc), "验收": {"成品读不出来，无法机检": False}, "通过": False}
    out.update({k: rep[k] for k in ("输入LUFS", "输入真峰值dBTP") if k in rep})
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(out if not rep else {**rep, **out}, f, ensure_ascii=False, indent=2)
    return out


def _mono_f32(path, ss=None, t=None):
    """解码成单声道 f32 采样。走 ffmpeg 管道 + array，不为这项检测引入 numpy/soundfile。"""
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    if t is not None:
        cmd += ["-t", str(t)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"解码失败 {path}: {r.stderr[-300:].decode('utf-8', 'replace')}")
    samples = array.array("f")
    samples.frombytes(r.stdout)
    return samples


def _rel_db(v, peak):
    return -120.0 if v <= 0 or peak <= 0 else round(20 * math.log10(v / peak), 2)


def head_tail_jump_db(path, win=3):
    """段首/段尾各 win 个样本的最大绝对值，相对本段峰值的 dB；再带回首尾静默时长。

    段间插的是数字零静音，所以「段首样本离零多远」就是拼接那一刻的台阶有多大：
    −0.5 dB ≈ 听不出，−3 dB 以上就是一记 click。取 3 个样本是为了容住编码器的振铃。
    台阶之外还量「段首/段尾本来就有多长静音」——它和 pause_ms 叠加成实际留白，
    是 TTS 产料里唯一还影响节奏的边界量（真人剪辑管的那一格在这里的等价物）。
    """
    a = _mono_f32(path)
    if len(a) < 2 * win:
        return None
    peak = max(abs(x) for x in a)
    head = max(abs(x) for x in a[:win])
    tail = max(abs(x) for x in a[-win:])
    onset = 10 ** (SILENCE_FLOOR_DB / 20) * peak        # 越过这条线算「真有声音」
    lead = next((i for i in range(len(a) - win)
                 if max(abs(x) for x in a[i:i + win]) > onset), len(a))
    trail = next((i for i in range(len(a) - win, win, -1)
                  if max(abs(x) for x in a[i:i + win]) > onset), win)
    return (_rel_db(head, peak), _rel_db(tail, peak),
            round(lead / SAMPLE_RATE * 1000), round((len(a) - trail) / SAMPLE_RATE * 1000))


def _audio_paths(arg):
    if os.path.isdir(arg):
        return sorted(os.path.join(arg, n) for n in os.listdir(arg)
                      if n.lower().endswith(AUDIO_EXT))
    return [arg]


def boundary_flags(paths, flag_db=JUMP_FLAG_DB):
    """扫一批段音频，标出首尾跳变超阈值的。返回 (逐段明细, 摘要)。

    渠道清单里那条「底噪 ≤ −60 dB RMS」在这里不测：本产线的段间静音是数字零，
    恒过、且没有信息量。会响的是另一件事——`combine_audio_with_pauses` 用 `+=`
    把 TTS 段硬接进零，段尾留半个波形就是一次爆音。这项检测测的就是它。
    """
    rows = []
    for p in paths:
        try:
            jump = head_tail_jump_db(p)
        except RuntimeError as e:
            rows.append({"文件": p, "错误": str(e)})
            continue
        if jump is None:
            rows.append({"文件": p, "跳过": "太短或静音"})
            continue
        head, tail, lead, trail = jump
        rows.append({"文件": p, "首跳变dB": head, "尾跳变dB": tail,
                     "段首静默ms": lead, "段尾静默ms": trail,
                     "超阈": max(head, tail) > flag_db})
    judged = [r for r in rows if "超阈" in r]

    def dist(pick):
        v = sorted(pick(r) for r in judged)
        if not v:
            return None
        at = lambda q: v[min(len(v) - 1, int(q * len(v)))]
        return {"最小": at(0), "中位": at(0.5), "p90": at(0.9), "最大": at(1.0)}

    summary = {
        "段数": len(judged), "跳过": len(rows) - len(judged),
        "阈值dB": flag_db, "超阈段数": sum(1 for r in judged if r["超阈"]),
        "跳变dB": dist(lambda r: max(r["首跳变dB"], r["尾跳变dB"])),
        "段首静默ms": dist(lambda r: r["段首静默ms"]),
        "段尾静默ms": dist(lambda r: r["段尾静默ms"]),
    }
    return rows, summary


def worst_first(rows, n=10):
    flagged = [r for r in rows if r.get("超阈")]
    return sorted(flagged, key=lambda r: -max(r["首跳变dB"], r["尾跳变dB"]))[:n]


def make_clips(src, dst_dir, head=True):
    """取段首或段尾 0.2 s，前面垫 120 ms 数字零——复听到的就是母带里那一记台阶。"""
    os.makedirs(dst_dir, exist_ok=True)
    t = 0.2
    ss = 0 if head else max(0, duration(src) - t)
    name = os.path.splitext(os.path.basename(src))[0] + ("_head" if head else "_tail") + ".wav"
    dst = os.path.join(dst_dir, name)
    r = _run(["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-t", str(t), "-i", src,
              "-af", "adelay=120:all=1", "-ar", str(SAMPLE_RATE), dst])
    if r.returncode != 0:
        raise RuntimeError(f"切片失败 {src}: {r.stderr[-300:]}")
    return dst


def show(report):
    for k, v in report.items():
        if k != "验收":
            print(f"  {k}: {v}")
    for label, ok in report["验收"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"  ==> {'验收通过' if report['通过'] else '不通过，别交客户'}")


def _self_check():
    """合成一段偏轻的 6 秒正弦，断言归一到位、峰值不超标、时长不动；
    再用两段同相正弦断言拼接痕检测「硬起步报、淡入不报」。"""
    import tempfile
    import wave
    d = tempfile.mkdtemp(prefix="master_audio_check_")
    src, dst = os.path.join(d, "in.wav"), os.path.join(d, "out.wav")
    r = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
              "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
              "-af", "volume=0.02", src])
    assert r.returncode == 0, r.stderr[-300:]
    rep = normalize(src, dst)
    show(rep)
    assert rep["输入LUFS"] < TARGET_I - 6, "测试样本必须偏轻，否则断言无意义"
    assert rep["通过"], f"自检未通过: {rep}"

    def write(name, samples):
        p = os.path.join(d, name)
        with wave.open(p, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(array.array("h", [int(s * 32767) for s in samples]).tobytes())
        return p

    n = SAMPLE_RATE
    tone = [0.5 * math.sin(2 * math.pi * 100 * (i / SAMPLE_RATE) + math.pi / 2)
            for i in range(n - SAMPLE_RATE // 10)]      # 相位取峰值起步 → 首样本就是峰值
    pad = [0.0] * (SAMPLE_RATE // 10)
    clicky = pad + tone + pad                           # 前后各 100 ms 留白，模拟 TTS 段
    hard = head_tail_jump_db(write("click.wav", tone))
    soft = head_tail_jump_db(write("smooth.wav", clicky))
    print(f"  拼接痕自检：硬起步 {hard} / 带头尾静默 {soft}（阈值 {JUMP_FLAG_DB} dB）")
    assert max(hard[:2]) > JUMP_FLAG_DB, f"硬起步没报出来，检测器无效: {hard}"
    assert max(soft[:2]) <= JUMP_FLAG_DB, f"首尾留白被误报成爆音，阈值太松: {soft}"
    assert hard[2] == 0 and 90 <= soft[2] <= 110, f"段首静默量不对: {hard} / {soft}"
    assert hard[3] == 0 and 90 <= soft[3] <= 110, f"段尾静默量不对: {hard} / {soft}"

    edge = edge_silence_ms(os.path.join(d, "smooth.wav"))
    print(f"  首尾静默自检（绝对 dBFS 口径）：{edge} ms")
    assert 90 <= edge[0] <= 110 and 90 <= edge[1] <= 110, f"文件首尾静默量不对: {edge}"

    # 闸门反例：顶满到削顶的样本必须被拦下。放行一个坏样本比阈值偏严危害大得多。
    # 注意 lavfi 的 sine 源只有 −18 dBFS，不加成 24 dB 就是个偏轻的正常信号。
    hot = os.path.join(d, "hot.wav")
    r = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
              "-f", "lavfi", "-i", "sine=frequency=220:duration=3",
              "-af", "volume=24dB", "-ar", str(SAMPLE_RATE), hot])
    assert r.returncode == 0, r.stderr[-300:]
    hv = inspect(hot)
    hres = gate(hv)
    print(f"  闸门反例：{hv['LUFS']} LUFS / {hv['真峰值dBTP']} dBTP / RMS {hv['RMS_dB']} dB → {hres}")
    assert not any(hres.values()), f"削顶样本没被拦下，闸门形同虚设: {hv} / {hres}"
    assert hv["RMS_dB"] is not None, "astats 没读出 RMS"

    # finalize：报告就地升级成真成品的判定，且「章节数对不上」必须能拦住
    fin = finalize(dst, expect_chapters=0)
    on_disk = json.load(open(os.path.join(d, "delivery_report.json"), encoding="utf-8"))
    print(f"  成品复判自检：{fin['全项实测']['LUFS']} LUFS / {fin['章节数']} / 通过 {fin['通过']}")
    assert fin["通过"] and on_disk["通过"], f"成品复判没落地: {fin} / {on_disk}"
    assert not finalize(dst, expect_chapters=5)["通过"], "WAV 0 章却被当成 5 章交付，章节判据没生效"
    print(f"SELF-CHECK OK  ({d})")


def main():
    ap = argparse.ArgumentParser(description="交付级母带响度归一 + 验收")
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--i", type=float, default=TARGET_I, help="目标 LUFS")
    ap.add_argument("--tp", type=float, default=TARGET_TP, help="目标真峰值 dBTP")
    ap.add_argument("--lra", type=float, default=TARGET_LRA, help="目标动态范围 LU")
    ap.add_argument("--check", action="store_true", help="只跑模块自检")
    ap.add_argument("--inspect", metavar="PATH", help="只出这个成品文件的全项实测 + 判定，不改写文件")
    ap.add_argument("--boundaries", nargs="+", metavar="PATH",
                    help="段边界拼接痕标定：PATH 是段音频目录或文件，可给多个")
    ap.add_argument("--flag-db", type=float, default=JUMP_FLAG_DB, help="跳变阈值 dB")
    ap.add_argument("--clip-dir", help="把最超阈的段首/段尾复听切片写到这里")
    ap.add_argument("--json", help="明细 + 摘要落这个文件")
    a = ap.parse_args()

    if a.inspect:
        v = inspect(a.inspect)
        res = gate(v)
        print(json.dumps({"文件": a.inspect, "全项实测": v, "客户口径": res,
                          "渠道口径参考": channel_gate(v), "通过": all(res.values())},
                         ensure_ascii=False, indent=2))
        return 0 if all(res.values()) else 1

    if a.boundaries:
        paths = [p for arg in a.boundaries for p in _audio_paths(arg)]
        if not paths:
            ap.error("--boundaries 没匹配到音频")
        rows, summary = boundary_flags(paths, a.flag_db)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        for r in worst_first(rows, 20):
            print(f"  {r['文件']}  首{r['首跳变dB']} / 尾{r['尾跳变dB']}")
        if a.clip_dir:
            for r in worst_first(rows, 10):
                make_clips(r["文件"], a.clip_dir, head=True)
                make_clips(r["文件"], a.clip_dir, head=False)
            print(f"  复听切片 → {a.clip_dir}")
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump({"摘要": summary, "明细": rows}, f, ensure_ascii=False, indent=1)
            print(f"  明细 → {a.json}")
        return 0

    if a.check:
        _self_check()
        return 0
    if not (a.src and a.dst):
        ap.error("需要 输入 输出 两个参数（或用 --check 跑自检、--boundaries 跑拼接痕标定）")
    rep = normalize(a.src, a.dst, a.i, a.tp, a.lra)
    show(rep)
    return 0 if rep["通过"] else 1


if __name__ == "__main__":
    sys.exit(main())
