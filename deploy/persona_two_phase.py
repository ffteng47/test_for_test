# 两阶段音色设计：绕开 ollama llama-server 与 VoiceDesign 的显存争抢。
# 阶段1 llm   —— 只用 LLM 出 description/ref_text，写 logs/persona_desc.json，随后退出（llama-server 靠 keep_alive 自动卸载）
# 阶段2 design —— 独占显存跑 VoiceDesign 预览，写 designed_voices/ 并更新 voice_config.json
# 用法: venv/bin/python persona_two_phase.py llm | design [--speakers A,B]
import json
import os
import shutil
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))          # alexandria/
APP = os.path.join(BASE, 'app')
sys.path.insert(0, APP)
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HOME', os.path.join(os.path.dirname(BASE), 'hf-cache'))

DESC_PATH = os.path.join(BASE, 'logs', 'persona_desc.json')
VC_PATH = os.path.join(BASE, 'voice_config.json')          # 可能是软链，写前先 realpath


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


DESC_OVERRIDES = {
    # LLM 无法从台词可靠推断性别/年龄（小满=女孩，云纹=男孩，旁白≠剧中人）。改后重跑 llm 阶段。
    'NARRATOR': ('A composed Chinese storyteller, neutral warm adult voice, steady moderate pace, '
                 'clear diction, calm and engaging audiobook narration style, never theatrical.'),
    'XIAOMAN': ('A young Chinese girl, around 10 years old. Bright, lively child voice with a '
                'slightly nasal timbre and quick, energetic delivery. She is curious and a bit '
                'impulsive, reacting with exaggerated surprise and excitement. Natural Mandarin '
                'children\'s audiobook dialogue.'),
    'XIAOMAN2': ('A young Chinese girl, around 8 years old, softer and shier than her sister. '
                 'Small, sweet child voice, sometimes teary and whiny when doubted, speaking in '
                 'short eager sentences. Natural Mandarin children\'s audiobook dialogue.'),
    'YUNWEN': ('A teenage Chinese boy, quick-witted and cheeky. Light, confident young male voice '
               'with a teasing lilt, brash but good-natured, speaking briskly with playful '
               'exaggeration. Natural Mandarin audiobook dialogue.'),
}


def collect(script):
    samples = {}
    for entry in script:
        spk = (entry.get('speaker') or '').strip()
        if spk:
            samples.setdefault(spk, []).append((entry.get('text') or '').strip())
    return samples


def phase_llm(allow):
    from openai import OpenAI
    from generate_personas import (PERSONA_SYSTEM_PROMPT, PERSONA_USER_PROMPT,
                                   extract_json_object, _fallback_compiled_persona,
                                   pick_ref_text, _collect_narrator_context)

    script = load_json(os.path.join(BASE, 'annotated_script.json'), [])
    if not script:
        sys.exit('annotated_script.json 为空，先跑剧本标注')
    cfg = load_json(os.path.join(APP, 'config.json'), {})
    llm = cfg.get('llm', {})
    prompts = cfg.get('prompts', {})
    client = OpenAI(base_url=llm.get('base_url', 'http://localhost:11434/v1'),
                    api_key=llm.get('api_key', 'local'))
    model = llm.get('model_name', 'richardyoung/qwen3-14b-abliterated:Q8_0')
    system = prompts.get('persona_system_prompt') or PERSONA_SYSTEM_PROMPT
    user_tpl = prompts.get('persona_user_prompt') or PERSONA_USER_PROMPT

    samples = collect(script)
    if allow:
        samples = {k: v for k, v in samples.items() if k in allow}
    result = load_json(DESC_PATH, {})
    for spk, lines in samples.items():
        print(f'[llm] {spk} ({len(lines)} lines)', flush=True)
        ctx = _collect_narrator_context(script, spk, 4)
        user_prompt = user_tpl.format(
            speaker=spk,
            narrator_context='\n'.join(ctx) if ctx else '(No nearby narrator intro lines found.)',
            sample_lines='\n'.join(lines[:8]),
        )
        description = ref_text = ''
        try:
            resp = client.chat.completions.create(
                model=model, temperature=0.3, max_tokens=800,
                messages=[{'role': 'system', 'content': system},
                          {'role': 'user', 'content': user_prompt}])
            parsed = extract_json_object(resp.choices[0].message.content.strip())
            if parsed:
                description = str(parsed.get('description', '') or '').strip()
                ref_text = str(parsed.get('ref_text', '') or '').strip()
        except Exception as e:
            print(f'[llm] LLM failed for {spk}: {e}', flush=True)
        if not description:
            print(f'[llm] WARNING {spk}: 走了兜底描述（LLM 输出不可解析），音色可能与他人雷同', flush=True)
            description, ref_text = _fallback_compiled_persona({'name': spk, 'sample_lines': lines})
        result[spk] = {'description': description, 'ref_text': ref_text or pick_ref_text(lines)}
        with open(DESC_PATH, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'[llm] 完成 {len(result)} 个角色 -> {DESC_PATH}')


def phase_design(allow):
    from tts import TTSEngine, sanitize_filename

    descs = load_json(DESC_PATH, {})
    if not descs:
        sys.exit(f'{DESC_PATH} 不存在，先跑 llm 阶段')
    if allow:
        descs = {k: v for k, v in descs.items() if k in allow}
    cfg = load_json(os.path.join(APP, 'config.json'), {})
    tts_cfg = dict(cfg.get('tts', {}))
    tts_cfg['compile_codec'] = False
    engine = TTSEngine({'tts': tts_cfg})

    vc_path = os.path.realpath(VC_PATH)
    vc = load_json(vc_path, {})
    shutil.copy2(vc_path, vc_path + '.bak_persona')
    out_dir = os.path.join(BASE, 'designed_voices')
    os.makedirs(out_dir, exist_ok=True)

    for spk, d in descs.items():
        print(f'[design] {spk}: {d["description"][:70]}', flush=True)
        wav, sr = engine.generate_voice_design(d['description'], d['ref_text'])
        voice_id = f'{sanitize_filename(spk)}_{int(time.time_ns())}'
        dest = os.path.join(out_dir, f'{voice_id}_preview.wav')
        shutil.copy2(wav, dest)
        rel = f'designed_voices/{voice_id}_preview.wav'
        with open(os.path.join(out_dir, f'{voice_id}_meta.json'), 'w', encoding='utf-8') as f:
            json.dump({'description': d['description'], 'ref_text': d['ref_text'],
                       'preview': rel}, f, ensure_ascii=False, indent=2)
        entry = vc.get(spk, {})
        entry.update({'type': 'clone', 'ref_audio': rel, 'ref_text': d['ref_text'],
                      'description': d['description'], 'character_style': d['description'],
                      'seed': -1})
        entry.pop('alias_of', None)
        vc[spk] = entry
        with open(vc_path, 'w', encoding='utf-8') as f:
            json.dump(vc, f, ensure_ascii=False, indent=2)
        print(f'[design] {spk} -> {rel}', flush=True)
    print('[design] 全部完成')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    allow = set()
    for a in sys.argv[1:]:
        if a.startswith('--allow='):
            allow = {s.strip() for s in a.split('=', 1)[1].split(',') if s.strip()}
    if not args or args[0] not in ('llm', 'design'):
        sys.exit('用法: persona_two_phase.py llm|design [--allow=A,B]')
    (phase_llm if args[0] == 'llm' else phase_design)(allow)
