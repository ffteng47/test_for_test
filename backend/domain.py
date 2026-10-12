"""domain — 后端共享的小领域工具：说话人归一化、CJK 计量、工作区 JSON 读写。

放在最底层，供 noveldb/sync_state/rules/asr_qc 复用，避免各处再写一份。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # alexandria/

# 与前端 store.js 的 KEY_ALIASES 保持一致（新增别名两边都要加）
KEY_ALIASES = {'laoqiang': 'oldzhou', 'laozhou': 'oldzhou', 'zhoubo': 'oldzhou'}

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uf900-\ufaff]')
_QUOTE_PAIRS = [('「', '」'), ('“', '”'), ("'", "'"), ('"', '"')]


def speaker_key(label: str | None) -> str:
    """'CHEN MO' -> 'chenmo'；已知别名折叠（LAO ZHOU -> oldzhou）。"""
    raw = re.sub(r'[\s_-]+', '', str(label or 'narrator').strip().lower())
    return KEY_ALIASES.get(raw, raw)


def cjk_units(text: str) -> int:
    """CJK 每字算一个单位、拉丁连续串算一个单位——词数对中文无意义（见 CJK text-loss 教训）。"""
    return len(_CJK_RE.findall(text)) + len(re.findall(r'[A-Za-z0-9]+', text))


def is_dialogue(text: str) -> bool:
    t = text.strip()
    return any(t.startswith(a) and t.endswith(b) and len(t) > 2 for a, b in _QUOTE_PAIRS)


def load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def workspace_paths() -> dict:
    """Alexandria 工作区关键文件路径（唯一入口，别处不拼路径）。"""
    return {
        'state': os.path.join(ROOT_DIR, 'state.json'),
        'script': os.path.join(ROOT_DIR, 'annotated_script.json'),
        'chunks': os.path.join(ROOT_DIR, 'chunks.json'),
        'voice_config': os.path.join(ROOT_DIR, 'voice_config.json'),
        'db': os.path.join(ROOT_DIR, 'novelaudio.db'),
    }


# ---------- 多项目（多本书轮跑）：根目录条目按书换软链 ----------

PROJECTS_PATH = os.path.join(ROOT_DIR, 'projects.json')
PROJECTS_DIR = os.path.join(ROOT_DIR, 'projects')

# 每本书一份的根条目（引擎与产品层共用；designed_voices/clone_voices/uploads 是跨书资产，不换）
SWAP_ENTRIES = ['state.json', 'chunks.json', 'annotated_script.json', 'voice_config.json',
                'cloned_audiobook.mp3', 'audiobook.m4b', 'continuity_report.json',
                'rules_report.json', 'script_context.json', 'voicelines']


def registry() -> dict:
    return load_json(PROJECTS_PATH, {'active': None, 'projects': {}})


def active_title() -> str | None:
    reg = registry()
    return (reg.get('projects') or {}).get(reg.get('active') or '', {}).get('title')


def active_project_id(con) -> int | None:
    """活动项目的 DB id：优先按 projects.json 的 title 匹配，回退到最早项目。"""
    title = active_title()
    if title:
        row = con.execute('SELECT id FROM projects WHERE title=?', (title,)).fetchone()
        if row:
            return row['id']
    row = con.execute('SELECT id FROM projects ORDER BY id LIMIT 1').fetchone()
    return row['id'] if row else None
