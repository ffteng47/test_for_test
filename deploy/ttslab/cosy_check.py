import sys
sys.path.insert(0, "repos/CosyVoice"); sys.path.append("repos/CosyVoice/third_party/Matcha-TTS")
from cosyvoice.cli.cosyvoice import CosyVoice2
m = CosyVoice2("models/CosyVoice2-0.5B", load_vllm=False, fp16=False)
print("SPKS:", m.list_available_spks()[:8])
print("SR:", m.sample_rate)
