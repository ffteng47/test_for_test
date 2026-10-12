"""context_manager — 三层记忆的提示装配（五层架构第①层 Story Bible + 第②层章节状态）。

第③层“相邻窗口”由 generate_script.py 引擎的 previous_entries 已覆盖，此处不重复。
产物：ROOT/script_context.json {"block": "..."}；generate_script.py 补丁在存在该文件时
把 block 追加进 system prompt。装配时机：sync_state 之后、剧本生成/复查之前。

用法： python3 context_manager.py [--write] [--title 书名]
"""
from __future__ import annotations

import argparse
import json
import os

from domain import ROOT_DIR, active_project_id, workspace_paths
from noveldb import Db, open_db

OUT_PATH = os.path.join(ROOT_DIR, 'script_context.json')


def build(db: Db, pid: int) -> str:
    proj = db.con.execute('SELECT title, author FROM projects WHERE id=?', (pid,)).fetchone()
    bible = db.get_bible(pid)
    chars = db.con.execute(
        'SELECT key, label, gender, personality, voice_config FROM characters WHERE project_id=? ORDER BY id',
        (pid,)).fetchall()

    lines = [f"作品：{proj['title']}" + (f"（作者 {proj['author']}）" if proj['author'] else '')]
    if bible.get('synopsis'):
        lines.append(f"梗概：{bible['synopsis']}")

    lines.append('登场人物：')
    for c in chars:
        vc = json.loads(c['voice_config'] or '{}')
        card = [f"- {c['label']}"]
        if c['gender']:
            card.append(f"性别:{c['gender']}")
        if c['personality']:
            card.append(f"性格:{c['personality']}")
        if vc.get('character_style'):
            card.append(f"声线:{vc['character_style']}")
        lines.append('；'.join(card))

    ch = db.con.execute(
        "SELECT no, state FROM chapters WHERE project_id=? ORDER BY no DESC LIMIT 1", (pid,)).fetchone()
    if ch and ch['state']:
        st = json.loads(ch['state'])
        if st.get('summary'):
            lines.append(f"第{ch['no']}章状态：{st['summary']}")

    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='落盘 script_context.json')
    args = ap.parse_args()

    paths = workspace_paths()
    db = Db(open_db(paths['db']))
    pid = active_project_id(db.con)
    if pid is None:
        raise SystemExit('DB 无项目，先跑 sync_state.py')
    block = build(db, pid)

    if args.write:
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump({'block': block}, f, ensure_ascii=False, indent=1)
        print(f'WROTE {OUT_PATH} ({len(block)} 字)')
    else:
        print(block)
    assert block.startswith('作品：') and '登场人物：' in block, '上下文块缺基本段落'


if __name__ == '__main__':
    main()
