"""emotion_map — instruct 自由文本 ⇄ 规范 emotion/intensity 的双向量化（五层架构第②层出口）。

方向一 infer：LLM/人工写的短 instruct（'平稳'、'阴阳怪气'、'喊'…）→ 规范 (emotion, intensity)。
方向二 instruct_for：规范值 → 确定的量化 instruct 文本，回写 DB 与 chunks.json（TTS 实际读它）。
量化后全库 instruct 收敛到有限词表：同 emotion 同 intensity 必同文本，风格可控、可复现。

用法（与 sync_state 同目录）：
    python3 emotion_map.py            # 只报告分布
    python3 emotion_map.py --write    # 回写 DB（emotion/intensity/量化 instruct）
    python3 emotion_map.py --push     # 并回写 chunks.json（先备份，引擎下次读取生效）
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil

# 规范情感表：keys 含中英关键词（匹配取最长优先）；intensity 为基准值，可被程度词修正。
EMOTIONS = {
    'calm':     {'intensity': 0.2, 'keys': ['平稳', '平静', '中性', '沉稳', '平缓', '清楚', '旁白',
                                            'neutral', 'calm', 'steady', 'narration', 'recitation']},
    'sarcasm':  {'intensity': 0.5, 'keys': ['阴阳怪气', '讥讽', '嘲讽', '冷笑', 'sarcastic', 'sneer']},
    'cold':     {'intensity': 0.3, 'keys': ['冷淡', '冷漠', '淡漠', '平淡', '冷', 'cold', 'flat']},
    'drawl':    {'intensity': 0.4, 'keys': ['拖长音', '慵懒', '慢条斯理', 'drawl', 'lazy']},
    'shout':    {'intensity': 0.8, 'keys': ['提高声音', '大喊', '高喊', '喊', '呼喊', 'shout', 'yell', 'higher volume']},
    'roar':     {'intensity': 1.0, 'keys': ['怒吼', '咆哮', '吼', 'roar']},
    'surprise': {'intensity': 0.7, 'keys': ['震惊', '惊讶', '惊', 'surprised', 'astonished']},
    'whisper':  {'intensity': 0.15, 'keys': ['压低声音', '耳语', '低语', '轻声', '悄悄', '小声', '轻', '低',
                                             'whisper', 'softly', 'lower volume']},
    'anger':    {'intensity': 0.8, 'keys': ['愤怒', '恼怒', '不服', '怒', 'angry', 'furious']},
    'sorrow':   {'intensity': 0.6, 'keys': ['哽咽', '哭泣', '悲伤', '难过', '哭', 'sad', 'sorrow', 'crying']},
    'fear':     {'intensity': 0.7, 'keys': ['恐惧', '害怕', '慌张', '发颤', '颤抖', '抖', '悬念', 'fear', 'scared',
                                            'trembling', 'cliffhanger']},
    'joy':      {'intensity': 0.6, 'keys': ['兴奋', '开心', '喜悦', '欢笑', '笑', 'joy', 'happy', 'excited']},
    'serious':  {'intensity': 0.35, 'keys': ['严肃', '郑重', '认真', '数', 'serious', 'solemn']},
    'rush':     {'intensity': 0.75, 'keys': ['急促', '催促', '抢答', '赶', '急', '喘', 'rushing', 'urgent']},
    'smug':     {'intensity': 0.5, 'keys': ['得意', '看热闹', 'smug', 'gloating']},
    'daze':     {'intensity': 0.25, 'keys': ['发愣', '发呆', '迟疑', '恍然', '愣', 'dazed', 'hesitant']},
}

# 量化出口文本：必须能被 infer 原样识别回来（幂等），改词表时同步验证 selftest。
INSTRUCT_TEXT = {
    'calm': '平稳叙述', 'sarcasm': '阴阳怪气，拖腔怪调', 'cold': '冷淡克制',
    'drawl': '拖长音', 'shout': '大声喊话', 'roar': '怒吼爆发',
    'surprise': '惊讶', 'whisper': '轻声耳语', 'anger': '愤怒',
    'sorrow': '悲伤', 'fear': '恐惧发颤', 'joy': '喜悦兴奋', 'serious': '严肃郑重',
    'rush': '语速急促', 'smug': '得意调侃', 'daze': '迟疑发呆',
}

_STRONG = re.compile(r'极度|非常|大声|强烈|fully|very|extremely')
_MILD = re.compile(r'微微|略带|稍|一点点|slightly|a bit')

# SenseVoice（ttslab/asr_server.py）回传的大写标签 → 规范 emotion。事件标签次优先级，
# 只在大类缺失时兜底。取 EMOTIONS 的基准 intensity，保证 instruct 文本仍是量化词表里的原句。
ASR_EMOTION = {
    'HAPPY': 'joy', 'SURPRISED': 'surprise', 'ANGRY': 'anger', 'SAD': 'sorrow',
    'FEARED': 'fear', 'DISGUSTED': 'sarcasm', 'NEUTRAL': 'calm',
}
ASR_EVENT = {'Laughter': 'joy', 'Cry': 'sorrow', 'Cough': 'calm', 'BGM': 'calm'}

_ALL_KEYS = sorted((k for e in EMOTIONS.values() for k in e['keys']), key=len, reverse=True)


def asr_map(tags) -> tuple[str, float] | None:
    """ASR 标签列表（如 ['zh','HAPPY','Speech','withitn']）→ (emotion, intensity)。"""
    seen = {str(t) for t in (tags or [])}
    emo = ASR_EMOTION.get(next((t for t in seen if t.upper() in ASR_EMOTION), ''), '')
    if not emo:
        emo = ASR_EVENT.get(next((t for t in seen if t in ASR_EVENT), ''), '')
    return (emo, EMOTIONS[emo]['intensity']) if emo else None


def infer(instruct: str, text: str = '') -> tuple[str, float] | None:
    """自由 instruct → (emotion, intensity)；识别不了返回 None（宁缺毋滥，不强行归类）。"""
    s = (instruct or '').lower()
    for key in _ALL_KEYS:
        for emo, spec in EMOTIONS.items():
            if key in s and key in spec['keys']:
                i = spec['intensity']
                if _STRONG.search(s):
                    i = min(1.0, i + 0.2)
                elif _MILD.search(s):
                    i = max(0.0, i - 0.2)
                return emo, round(i, 2)
    return None


def instruct_for(emotion: str, intensity: float) -> str:
    out = INSTRUCT_TEXT[emotion]
    if intensity >= 0.9:
        out += '，情绪拉满'
    elif intensity <= 0.2:
        out += '，克制'
    return out


def main() -> None:
    # 只有 CLI 回写才碰 SQLite；sidecar 导入本模块取词表时不需要 domain/noveldb。
    from domain import active_project_id, workspace_paths
    from noveldb import Db, open_db

    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='回写 DB')
    ap.add_argument('--push', action='store_true', help='并回写 chunks.json（自动备份）')
    args = ap.parse_args()

    paths = workspace_paths()
    db = Db(open_db(paths['db']))
    pid = active_project_id(db.con)
    segs = [dict(r) for r in db.segments(pid)]

    dist = collections.Counter()
    updates = {}
    for s in segs:
        got = infer(s['instruct'])
        if not got:
            dist['<unmatched>'] += 1
            continue
        emo, inten = got
        new_instruct = instruct_for(emo, inten)
        dist[emo] += 1
        if new_instruct != s['instruct'] or s['emotion'] != emo:
            updates[s['ord']] = (emo, inten, new_instruct, s['id'])

    print('EMOTION_MAP:', dict(dist), f'→ 可量化 {len(updates)}/{len(segs)}')

    if args.write:
        for emo, inten, txt, sid in updates.values():
            db.con.execute('UPDATE segments SET emotion=?, intensity=?, instruct=? WHERE id=?',
                           (emo, inten, txt, sid))
        db.con.commit()
        print(f'DB: {len(updates)} 段已回写')

    if args.push:
        with open(paths['chunks'], encoding='utf-8') as f:
            data = json.load(f)
        chunks = data['chunks'] if isinstance(data, dict) else data
        backup = paths['chunks'] + '.bak_pre_emotion'
        if not os.path.exists(backup):
            shutil.copy(paths['chunks'], backup)
        changed = 0
        for i, c in enumerate(chunks):
            if i in updates and c.get('instruct') != updates[i][2]:
                c['instruct'] = updates[i][2]
                changed += 1
        with open(paths['chunks'], 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f'PUSH: chunks.json {changed} 段更新（备份 {backup}）')


if __name__ == '__main__':
    main()

    # selftest：量化幂等（instruct_for 结果必须原样 infer 回同一 emotion）
    for emo in EMOTIONS:
        for i in (0.1, 0.5, 1.0):
            back = infer(instruct_for(emo, i))
            assert back and back[0] == emo, (emo, instruct_for(emo, i), back)
    assert infer('阴阳怪气')[0] == 'sarcasm'
    assert infer('喊')[1] >= 0.8 and infer('吼')[1] >= 0.9
    assert infer('') is None and infer('opening jingle') is None
    assert asr_map(['zh', 'HAPPY', 'Speech', 'withitn']) == ('joy', 0.6)
    assert asr_map(['zh', 'NEUTRAL', 'Speech'])[0] == 'calm'
    assert asr_map(['zh', 'Speech', 'Laughter'])[0] == 'joy'
    assert asr_map(['zh', 'Speech']) is None and asr_map([]) is None
    print('SELFTEST OK')
