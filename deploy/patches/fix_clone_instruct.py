# Fix: single-chunk clone generation dropped the per-line instruct (试听/重生成句子无感情，
# 而批量生成走 instruct_ids 有感情)。Pass instruct_text through generate_clone_voice ->
# _local_generate_clone, mirroring the batch path's chatml formatting (tts.py:1557).
# Idempotent. Target: alexandria/app/tts.py
import py_compile
import shutil
import sys

TTS = "/home/tff/software/novel-audiobook/alexandria/app/tts.py"
SRC = open(TTS, encoding="utf-8").read()

if "instruct_text=instruct_text" in SRC:
    print("ALREADY_PATCHED")
    sys.exit(0)

shutil.copy(TTS, TTS + ".bak_pre_clone_instruct")

EDITS = [
    # 1) dispatcher: pass instruct into clone branch
    ("""        if voice_type == "clone":
            return self.generate_clone_voice(text, speaker, voice_config, output_path)""",
     """        if voice_type == "clone":
            return self.generate_clone_voice(text, speaker, voice_config, output_path,
                                            instruct_text=instruct_text)"""),
    # 2) clone entry: accept + forward instruct (local only; gradio endpoint lacks instruct)
    ("""    def generate_clone_voice(self, text, speaker, voice_config, output_path):
        \"\"\"Generate audio using voice cloning. Returns True on success.\"\"\"
        if self._mode == "local":
            return self._local_generate_clone(text, speaker, voice_config, output_path)""",
     """    def generate_clone_voice(self, text, speaker, voice_config, output_path, instruct_text=None):
        \"\"\"Generate audio using voice cloning. Returns True on success.\"\"\"
        if self._mode == "local":
            return self._local_generate_clone(text, speaker, voice_config, output_path,
                                              instruct_text=instruct_text)"""),
    # 3) local clone: build instruct_ids like the batch path
    ("""    def _local_generate_clone(self, text, speaker, voice_config, output_path):""",
     """    def _local_generate_clone(self, text, speaker, voice_config, output_path, instruct_text=None):"""),
    ("""            t_start = time.time()
            wavs, sr = model.generate_voice_clone(
                text=text,
                voice_clone_prompt=prompt,
                non_streaming_mode=True,
                max_new_tokens=2048,
            )""",
     """            gen_extra = {}
            instruct = (instruct_text or "").strip()
            if character_style:
                instruct = f"{instruct} {character_style}".strip()
            if instruct:
                # 与包内 custom/design 路径同格式；model.generate 期望按 batch 对齐的 list
                tok = model._tokenize_texts([model._build_instruct_text(instruct)])[0]
                gen_extra["instruct_ids"] = [tok]

            t_start = time.time()
            wavs, sr = model.generate_voice_clone(
                text=text,
                voice_clone_prompt=prompt,
                non_streaming_mode=True,
                max_new_tokens=2048,
                **gen_extra,
            )"""),
    # 3a) fetch character_style before use
    ("""            seed = int(voice_data.get("seed", -1))

            import time

            print(f"TTS [local clone] generating for speaker='{speaker}', text='{text[:50]}...'")""",
     """            seed = int(voice_data.get("seed", -1))
            character_style = (voice_data.get("character_style") or "").strip()

            import time

            print(f"TTS [local clone] generating for speaker='{speaker}', text='{text[:50]}...'")"""),
]

for old, new in EDITS:
    if SRC.count(old) != 1:
        sys.exit(f"ANCHOR COUNT {SRC.count(old)} (expect 1):\n{old[:120]}")
    SRC = SRC.replace(old, new)

open(TTS, "w", encoding="utf-8").write(SRC)
py_compile.compile(TTS, doraise=True)
print("PATCHED_OK")
