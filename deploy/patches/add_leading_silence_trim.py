# 段首死气裁剪安装器（幂等）：给合并/时间轴两条路共用一个「裁掉段首静音」的前置步骤。
#
# 修的真问题（M2 实测，372 段）：段首静音中位 437 ms、最大 1273 ms，段尾中位 90 ms，
# 叠加标称 500 ms 段间静音后，**实际停顿 ≈1.0 s 且抖动 ±850 ms**。段间静音是代码里的固定值，
# 段首/段尾那截是 TTS 自己给的随机值——真人后期「剪气口」在我们这里的等价物就是把它收窄。
#
# 只改导出层：纯 CPU，不动任何已生成的段，重跑一次导出即生效。裁剪点在 `compute_timeline`
# 的循环里（章节偏移 = 累加裁剪后的长度，天然对齐）和 `combine_audio_with_pauses` 里
# （对已裁过的段是空操作，两条路时长因此一致）。**两处必须同时改**，只改一处章节轴会漂。
#
# 阈值不在这里定：段边界复测用 `backend/master_audio.py --boundaries`（它量首跳变 dB 与段首静默）。
# 关掉：把部署后的 `LEAD_SILENCE_KEEP_MS` 改回 None 再重启。
#
# 跑法（服务器上，alexandria 的 venv）：
#   cd alexandria/deploy_patches && ../venv/bin/python add_leading_silence_trim.py
# 后端改动，跑完必须重启主服务才生效（重启前先确认无生成任务在跑）。

import os
import py_compile

from add_export_loudnorm import BASE, patch

TTS = os.path.join(BASE, "tts.py")

PAIRS = [
    ('DEFAULT_PAUSE_MS = 500  # Pause between different speakers\n'
     'SAME_SPEAKER_PAUSE_MS = 250  # Shorter pause for same speaker continuing',
     'DEFAULT_PAUSE_MS = 500  # Pause between different speakers\n'
     'SAME_SPEAKER_PAUSE_MS = 250  # Shorter pause for same speaker continuing\n'
     'from pydub.silence import detect_leading_silence\n\n'
     '# 段首静音是 TTS 给的随机值（实测中位 437 ms / 最大 1273 ms），段间静音才是代码里的固定值。\n'
     '# 真人后期「剪气口」的等价动作：把段首那截收窄到 KEEP_MS。设成 None 即关闭。\n'
     'LEAD_SILENCE_FLOOR_DB = -45.0  # 绝对 dBFS：段内语音远高于此，切不到真词\n'
     'LEAD_SILENCE_KEEP_MS = 80\n\n'
     'def trim_leading_silence(segment):\n'
     '    """裁掉段首静音，只留 LEAD_SILENCE_KEEP_MS。返回新对象；对已裁过的段是空操作。"""\n'
     '    if LEAD_SILENCE_KEEP_MS is None:\n'
     '        return segment\n'
     '    lead = detect_leading_silence(segment, silence_threshold=LEAD_SILENCE_FLOOR_DB)\n'
     '    return segment[max(0, lead - LEAD_SILENCE_KEEP_MS):]',
     'def trim_leading_silence'),

    ('    combined = audio_segments[0]\n'
     '    prev_speaker = speakers[0]\n'
     '\n'
     '    for i, (segment, speaker) in enumerate(zip(audio_segments[1:], speakers[1:])):\n'
     '        override = pause_overrides[i] if pause_overrides else None',
     '    combined = trim_leading_silence(audio_segments[0])\n'
     '    prev_speaker = speakers[0]\n'
     '\n'
     '    for i, (segment, speaker) in enumerate(zip(audio_segments[1:], speakers[1:])):\n'
     '        segment = trim_leading_silence(segment)\n'
     '        override = pause_overrides[i] if pause_overrides else None',
     'combined = trim_leading_silence(audio_segments[0])'),

    ('    for chunk, segment in chunks_with_audio:\n'
     '        if prev_speaker is not None:',
     '    for chunk, raw_segment in chunks_with_audio:\n'
     '        segment = trim_leading_silence(raw_segment)  # 裁剪后长度进 cursor_ms，章节轴才不会漂\n'
     '        if prev_speaker is not None:',
     'segment = trim_leading_silence(raw_segment)'),
]


def main():
    backup = TTS + ".bak_pre_lead_trim"
    if not os.path.exists(backup):
        import shutil
        shutil.copy(TTS, backup)
        print(f"BACKUP {backup}")

    patch(TTS, PAIRS, "LEAD_TRIM")
    py_compile.compile(TTS, doraise=True)
    print("LEAD_TRIM_OK（后端改动，需重启主服务才生效；重启前先确认无生成任务在跑）")


if __name__ == "__main__":
    main()
