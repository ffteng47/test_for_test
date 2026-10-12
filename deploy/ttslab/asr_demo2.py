"""Paraformer-large(+VAD+标点) vs SenseVoice：同一音频并跑，看 ref_text 该用哪个。"""
from funasr import AutoModel

WAV = "/home/tff/software/novel-audiobook/alexandria/voicelines/batchAB_voiceline0008_batch.wav"
m = AutoModel(model="paraformer-zh", model_revision="v2.0.4",
              vad_model="fsmn-vad", vad_model_revision="v2.0.4",
              punc_model="ct-punc", punc_model_revision="v2.0.4",
              device="cpu", disable_update=True)
r = m.generate(input=WAV, batch_size=1)
print("PARAFORMER:", r[0]["text"])
