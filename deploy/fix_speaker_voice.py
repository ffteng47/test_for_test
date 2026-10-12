import json, os, shutil, sys, time

BASE = '/home/tff/software/novel-audiobook/alexandria'
sys.path.insert(0, os.path.join(BASE, 'app'))
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HOME', '/home/tff/software/novel-audiobook/hf-cache')

from tts import TTSEngine

SPEAKER = 'LAO ZHOU'
STEM = 'lao_zhou'
DESC = ('An elderly Chinese man in his late fifties, weathered gravelly voice, '
        'slightly breathy and trembling with age, respectful and urgent tone, '
        'natural Mandarin audiobook dialogue delivery.')
REF_TEXT = '少爷，老爷请您回去。'

engine = TTSEngine({'tts': {'mode': 'local', 'language': 'Chinese', 'device': 'auto'}})
wav, sr = engine.generate_voice_design(DESC, REF_TEXT)

ts = int(time.time() * 1e9)
name = f'{STEM}_{ts}_preview.wav'
dest = os.path.join(BASE, 'designed_voices', name)
shutil.copy(wav, dest)

meta = {'description': DESC, 'ref_text': REF_TEXT, 'preview': f'designed_voices/{name}'}
json.dump(meta, open(os.path.join(BASE, 'designed_voices', f'{STEM}_{ts}_meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

vc_path = os.path.join(BASE, 'voice_config.json')
vc = json.load(open(vc_path, encoding='utf-8'))
vc[SPEAKER]['ref_audio'] = f'designed_voices/{name}'
vc[SPEAKER]['description'] = DESC
vc[SPEAKER]['character_style'] = DESC
json.dump(vc, open(vc_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

removed = 0
for f in os.listdir(os.path.join(BASE, 'voicelines')):
    if f.endswith(f'_{STEM}.mp3'):
        os.remove(os.path.join(BASE, 'voicelines', f))
        removed += 1

print('NEW_VOICE:', name)
print('REMOVED_LINES:', removed)
print('VOICE_FIX_DONE')
