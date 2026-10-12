"""集成验证：pydub → 归一 → pydub 读回，整条接线是否真的把成品拉到目标响度。

安装器给 `project.py` 接的是 `_normalize_master`，它在导出链路中间，只有 venv 里的
pydub 才能验。这里不复刻那份代码的逻辑分支，只走同一条函数调用序列。
"""
import os
import subprocess
import sys
import tempfile

BASE = "/home/tff/software/novel-audiobook/alexandria"
sys.path.insert(0, os.path.join(BASE, "backend"))

from pydub import AudioSegment  # noqa: E402
from master_audio import normalize, measure  # noqa: E402

D = tempfile.mkdtemp(prefix="loudnorm_itest_")
src = os.path.join(D, "quiet_src.wav")
pre = os.path.join(D, "pre.wav")
norm = os.path.join(D, "norm.wav")

subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
                "-af", "volume=0.02", "-ar", "44100", src], check=True)

seg = AudioSegment.from_file(src)
lufs_before = float(measure(src)["input_i"])

seg.export(pre, format="wav")
report = normalize(pre, norm)
reloaded = AudioSegment.from_file(norm)          # 接线里最容易出问题的这一步
out = os.path.join(D, "after_reload.wav")
reloaded.export(out, format="wav")
lufs_after_reload = float(measure(out)["input_i"])

print(f"原始          {lufs_before:+.2f} LUFS")
print(f"归一后实测    {report['输出LUFS']:+.2f} LUFS   峰值 {report['输出真峰值dBTP']:+.2f} dBTP")
print(f"pydub 读回再导 {lufs_after_reload:+.2f} LUFS")
print(f"时长 {report['输入时长s']} → {report['输出时长s']} s   验收 {report['验收']}")

assert report["通过"], report
assert abs(lufs_after_reload - report["输出LUFS"]) <= 0.5, "pydub 往返把归一弄丢了"
print("INTEGRATION OK")
