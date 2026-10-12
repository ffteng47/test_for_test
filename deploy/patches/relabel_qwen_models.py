# Voice Lab 模型改名（幂等）：让 Qwen3-TTS 的三个 checkpoint 在页签里认得出自己。
#
# 修的真问题：Qwen3-TTS 能克隆，`base17` / `base06`（`Qwen3-TTS-12Hz-*-Base`，
# 给 ref_audio + ref_text 的 zero-shot 克隆）就是它的克隆口，生产那本书的 8 个声线
# 全是「VoiceDesign 造声 → preview 当参考 → Base 克隆」两段式出来的。但列表里 label
# 只写 "Base 1.7B 克隆"，字符串里没有 Qwen；而「引擎」下拉框的数据源 /api/engines
# 只列本机 sidecar（cosy/index/kokoro），Qwen 是进程内默认引擎（engine_key 空串），
# 压根不在那张表里。两处都不提 Qwen，看上去就像「Qwen 只能 voice design、不能克隆」。
#
# 只改展示字符串，不动 model_id / method / backend —— 改 ENGINES 或给 Qwen 加 engine_key
# 会让 engines.resolve() 把 Qwen 当 sidecar 去 POST /tts，那是真能出事的，别这么修。
#
# 线上那份 label 是被安装器以 \u 转义写进去的（`"Base 1.7B \\u514b\\u9686"`），
# 锚点照这份字节写；改完统一成 UTF-8 中文，和同表里 sidecar 那几行的写法一致。
#
# 跑法（服务器上）：
#   cd alexandria/deploy_patches && ../venv/bin/python relabel_qwen_models.py
# 后端改动，跑完必须重启主服务才生效（重启前先确认无生成任务在跑）。

import os
import py_compile

from add_export_loudnorm import PROJ

# MODELS 表在 voice_lab.py，不在 project.py（`patch()` 的锚点断言会拦住选错文件）
LAB = os.path.join(os.path.dirname(PROJ), "voice_lab.py")

PAIRS = [
    ('"label": "VoiceDesign 1.7B"',
     '"label": "Qwen3-TTS VoiceDesign 1.7B"',
     '"label": "Qwen3-TTS VoiceDesign 1.7B"'),

    ('"label": "Base 1.7B \\u514b\\u9686"',
     '"label": "Qwen3-TTS Base 1.7B 克隆"',
     '"label": "Qwen3-TTS Base 1.7B 克隆"'),

    ('"label": "Base 0.6B \\u514b\\u9686"',
     '"label": "Qwen3-TTS Base 0.6B 克隆"',
     '"label": "Qwen3-TTS Base 0.6B 克隆"'),

    ('"label": "CustomVoice 1.7B"',
     '"label": "Qwen3-TTS CustomVoice 1.7B"',
     '"label": "Qwen3-TTS CustomVoice 1.7B"'),

    ('"label": "CustomVoice 0.6B"',
     '"label": "Qwen3-TTS CustomVoice 0.6B"',
     '"label": "Qwen3-TTS CustomVoice 0.6B"'),
]


def main():
    import shutil
    from add_export_loudnorm import patch

    if 'MODELS = {' not in open(LAB, encoding="utf-8").read():
        print(f"{LAB} 里没有 MODELS 表，先跑 add_voice_lab.py。")
        raise SystemExit(1)

    backup = LAB + ".bak_pre_qwen_label"
    if not os.path.exists(backup):
        shutil.copy(LAB, backup)
        print(f"BACKUP {backup}")
    patch(LAB, PAIRS, "QWEN_LABEL")
    py_compile.compile(LAB, doraise=True)
    print("QWEN_LABEL_OK（后端改动，需重启主服务才生效；重启前先确认无生成任务在跑）")


if __name__ == "__main__":
    main()
