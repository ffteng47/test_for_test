"""报价成本实测：从历史日志与段落数据算出真实产速，供报价单使用。

只读，不改动任何生产数据。在服务器上跑：
    python3 deploy/cost_probe.py /home/tff/software/novel-audiobook
输出是一份可直接抄进报价表的数字，不含任何估算值。
"""
import collections
import json
import os
import re
import sys

LOG_NAMES = ("logs/alexandria.log",)
DONE_PAT = re.compile(r"TTS \[([^\]]+)\] done: ([\d.]+)s -> ([\d.]+)s audio")
ERROR_KWS = (
    "fail", "error", "Error", "retry", "重试", "Traceback",
    "CUDA out of memory", "Kokoro", "兜底", "fallback",
)


def scan_logs(root):
    groups = collections.defaultdict(lambda: [0.0, 0.0, 0])
    kw_counts = collections.Counter()
    seen = 0
    for rel in LOG_NAMES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for eng, gen_s, audio_s in DONE_PAT.findall(text):
            row = groups[eng]
            row[0] += float(gen_s)
            row[1] += float(audio_s)
            row[2] += 1
            seen += 1
        for kw in ERROR_KWS:
            kw_counts[kw] += len(re.findall(re.escape(kw), text))
    return groups, kw_counts, seen


def scan_project(root, slug=None):
    base = os.path.join(root, "alexandria")
    cand = []
    proj_dir = os.path.join(base, "projects")
    if os.path.isdir(proj_dir):
        for name in sorted(os.listdir(proj_dir)):
            p = os.path.join(proj_dir, name, "chunks.json")
            if os.path.exists(p):
                cand.append((name, p))
    top = os.path.join(base, "chunks.json")
    if os.path.exists(top):
        cand.append(("(root)", top))
    if slug:
        cand = [c for c in cand if c[0] == slug]
    out = []
    for name, path in cand:
        try:
            chunks = json.load(open(path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            out.append((name, None, str(exc)))
            continue
        if not isinstance(chunks, list):
            continue
        out.append((name, chunks, None))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    groups, kw_counts, seen = scan_logs(root)

    print("=" * 68)
    print("一、实测产速（来自真实生成日志，非估算）")
    print("=" * 68)
    if not seen:
        print("日志中没有可用的 TTS done 记录 —— 无法给出实测值。")
    else:
        print(f"{'出声路径':<20}{'次数':>6}{'GPU秒':>9}{'音频秒':>9}{'RTF':>7}{'总音频分钟':>11}")
        for eng, (gen_s, audio_s, n) in sorted(groups.items(), key=lambda x: -x[1][1]):
            rtf = gen_s / audio_s if audio_s else float("nan")
            print(f"{eng:<20}{n:>6}{gen_s:>9.0f}{audio_s:>9.0f}{rtf:>7.2f}{audio_s / 60:>11.1f}")
        tot_gen = sum(v[0] for v in groups.values())
        tot_aud = sum(v[1] for v in groups.values())
        print(f"\n合并 RTF = {tot_gen / tot_aud:.2f}"
              f"（{tot_gen / 3600:.2f} GPU 小时产出 {tot_aud / 3600:.2f} 音频小时）")

    print()
    print("=" * 68)
    print("二、异常关键词出现次数（用于估返工率，需人工确认口径）")
    print("=" * 68)
    for kw, c in kw_counts.most_common():
        if c:
            print(f"  {kw:<22}{c}")

    print()
    print("=" * 68)
    print("三、文本→成品换算（字数 / 段数 / 完成率）")
    print("=" * 68)
    for name, chunks, err in scan_project(root):
        if err:
            print(f"  {name}: 读取失败 {err}")
            continue
        done = [c for c in chunks if c.get("status") == "done"]
        chars = sum(len(str(c.get("text", ""))) for c in chunks)
        fb = sum(1 for c in chunks if c.get("voice_fallback"))
        eng = collections.Counter(c.get("voice_engine") for c in chunks)
        print(f"  书目 {name}: 段数={len(chunks)} 完成={len(done)} "
              f"完成率={len(done) / len(chunks) * 100:.1f}% 字数={chars}")
        print(f"      兜底段={fb}  引擎={dict(eng)}")
        if chunks:
            print(f"      平均段字数={chars / len(chunks):.1f} 字/段")


if __name__ == "__main__":
    main()
