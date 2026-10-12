"""ModelScope 权重拉取（CosyVoice2 / SenseVoice）；已存在自动跳过，重跑续传。"""
import sys
from modelscope import snapshot_download

for model_id, dirname in [
    ("iic/SenseVoiceSmall", "SenseVoiceSmall"),
    ("FunAudioLLM/CosyVoice2-0.5B", "CosyVoice2-0.5B"),
]:
    path = snapshot_download(model_id, local_dir=f"/home/tff/software/novel-audiobook/ttslab/models/{dirname}")
    print("[OK]", model_id, "->", path, flush=True)
