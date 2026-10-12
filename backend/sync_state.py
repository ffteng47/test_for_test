"""sync_state — 把 Alexandria 工作区 JSON 幂等搬入 SQLite（产品状态真源）。

引擎（generate_script / TTS）仍读写工作区文件；本脚本在以下时机跑：
  - 标注/复查/生成任务结束后（后续由 worker 调用，现阶段 CLI）
  - 任何需要“以库为准”的读路径之前

用法： python3 sync_state.py [--title 书名]
"""
from __future__ import annotations

import argparse

from domain import active_title, is_dialogue, load_json, speaker_key, workspace_paths
from noveldb import Db, open_db


def sync(title: str | None = None) -> dict:
    paths = workspace_paths()
    script = load_json(paths['script'], [])
    chunks = load_json(paths['chunks'], [])
    voice_cfg = load_json(paths['voice_config'], {})
    state = load_json(paths['state'], {})

    db = Db(open_db(paths['db']))
    pid = db.upsert_project(title or active_title() or state.get('project_title') or '当前书籍')

    # ---- 人物：voice_config 提供 label 与音色；script 提供实际出场 ----
    labels = {}
    for raw_label in voice_cfg:
        labels.setdefault(speaker_key(raw_label), raw_label)
    for e in chunks or script:
        k = speaker_key(e.get('speaker'))
        labels.setdefault(k, e.get('speaker'))
    for k, label in labels.items():
        db.upsert_character(pid, k, label=label, voice_config=voice_cfg.get(label))

    # ---- 章节/场景：现阶段引擎无章节切分，先落 1 章 1 景（占位，阶段 4.1 细化） ----
    ch_id = db.upsert_chapter(pid, 1, '当前章节')
    sc_id = db.upsert_scene(pid, ch_id, 1, summary='单场景工作区（章节切分待 E2A 解析链）')

    rows = []
    src = chunks if chunks else [{'text': e.get('text', ''), 'speaker': e.get('speaker'),
                                  'instruct': e.get('instruct', ''), 'status': 'pending',
                                  'audio_path': None} for e in script]
    for i, c in enumerate(src):
        rows.append({'ord': i, 'scene_id': sc_id, 'speaker': speaker_key(c.get('speaker')),
                     'kind': 'dialogue' if is_dialogue(c.get('text', '')) else 'narration',
                     'text': c.get('text', ''), 'instruct': c.get('instruct', ''),
                     'status': c.get('status', 'pending'), 'audio_path': c.get('audio_path')})
    db.replace_segments(pid, rows)

    # ---- bible 骨架：只补不覆盖（长期状态由上层逐步充实） ----
    bible = db.get_bible(pid)
    bible.setdefault('characters', {})
    for k, label in labels.items():
        bible['characters'].setdefault(k, {'label': label})
    db.set_bible(pid, bible)

    return {'project_id': pid, **db.summary(pid)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--title')
    args = ap.parse_args()
    out = sync(args.title)
    print('SYNC:', out)
    assert out['segments'] > 0, '工作区无剧本可同步'
    assert out['characters'] > 0, '未解析出人物'
