"""SenseVoice 转写冒烟测试：验证能否自动产出克隆用的 ref_text（CPU 跑，不抢生产显存）。"""
import sys
from funasr import AutoModel

m = AutoModel(model="/home/tff/software/novel-audiobook/ttslab/models/SenseVoiceSmall",
              device="cpu", disable_update=True, trust_remote_code=True)
r = m.generate(input=sys.argv[1], cache={}, language="zh", use_itn=True)
print("TEXT:", r[0]["text"])
print("RAW:", {k: v for k, v in r[0].items() if k != "text"})
