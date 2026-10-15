# 存量段首伪影离线修复（CPU，不占 GPU；与生成守卫共用 app/head_guard.clean）。
#
# 用法（服务器上，deploy_patches 目录）：
#   ../venv/bin/python repair_qwen_heads.py                      # 只报告命中
#   ../venv/bin/python repair_qwen_heads.py --apply              # 修复（先整目录备份）
#   ../venv/bin/python repair_qwen_heads.py --dir <voicelines>   # 指定书目
# 备份：voicelines 同级目录 voicelines.bak_headfix_<时间戳>/（cp -a 全量，命中文件的原件都在里面）。
# 注意：修复后的 mp3 由 libsndfile 重编码（与 _save_wav 同一通路），时长可能 ±几 ms。
import argparse
import datetime
import os
import shutil
import subprocess
import sys

ALEX = "/home/tff/software/novel-audiobook/alexandria"
sys.path.insert(0, os.path.join(ALEX, "app"))
import head_guard  # noqa: E402
import soundfile as sf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ALEX, "projects/shuxue/voicelines"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith(".mp3"))
    hits = []
    for name in files:
        p = os.path.join(args.dir, name)
        a, sr = sf.read(p, dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        b = head_guard.clean(a, sr)
        if len(b) != len(a) or abs(float(b[0]) - float(a[0])) > 1e-6:
            hits.append((name, len(a) - len(b), round(float(abs(a[0])), 4), sr))
    print("%s: %d 段，命中 %d 段" % (args.dir, len(files), len(hits)))
    for h in hits:
        print("  %s 裁 %d 样本 |s0|=%s sr=%d" % h)
    if not args.apply:
        print("（报告模式；--apply 才写文件）")
        return
    if not hits:
        return
    stamp = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
    bak = os.path.join(os.path.dirname(args.dir.rstrip("/")),
                       os.path.basename(args.dir.rstrip("/")) + ".bak_headfix_" + stamp)
    shutil.copytree(args.dir, bak)
    print("已备份 -> %s" % bak)
    hitset = {h[0] for h in hits}
    n = 0
    for name in files:
        if name not in hitset:
            continue
        p = os.path.join(args.dir, name)
        a, sr = sf.read(p, dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        b = head_guard.clean(a, sr)
        tmp = p + ".tmp"
        sf.write(tmp, b, sr, format="MP3")
        os.replace(tmp, p)
        n += 1
    print("已修复 %d 段" % n)


if __name__ == "__main__":
    main()
