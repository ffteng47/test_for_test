"""projects — 多本书轮跑：每本书一个工作区目录，根目录条目用软链指向当前书。

引擎（app.py/脚本）仍按 ROOT/<file> 读写 → 换书 = 换软链 + 重启服务。
projects.json: {"active": slug, "projects": {slug: {"title": str, "created": str}}}

用法：
    python3 projects.py list
    python3 projects.py adopt <slug> --title 书名     # 把当前根目录实体收编为某书并设为活动
    python3 projects.py add <slug> --title 书名 [--from 目录]   # 登记新书（可从备份目录拷入）
    python3 projects.py switch <slug>                 # 空闲守卫 → 收编旧书 → 换链 → 重启 → 再同步
    python3 projects.py current
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request

from domain import (PROJECTS_DIR, PROJECTS_PATH, ROOT_DIR, SWAP_ENTRIES, load_json, registry)

SERVICE_DIR = os.path.dirname(ROOT_DIR)          # novel-audiobook/（start/stop 脚本所在）
ENGINE = 'http://localhost:4200'
GUARDED_TASKS = ('script', 'review', 'audio', 'persona', 'm4b_export', 'audacity_export',
                 'lora_training', 'dataset_gen')
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')


def _save(reg: dict) -> None:
    with open(PROJECTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)


def book_dir(slug: str) -> str:
    return os.path.join(PROJECTS_DIR, slug)


def link_all(slug: str) -> int:
    """把 SWAP_ENTRIES 软链到 projects/<slug>/；书目录里没有的条目撤掉旧链。"""
    d, n = book_dir(slug), 0
    for name in SWAP_ENTRIES:
        target, link = os.path.join(d, name), os.path.join(ROOT_DIR, name)
        if os.path.islink(link):
            os.unlink(link)
        elif os.path.lexists(link):
            raise SystemExit(f'根目录 {name} 是实体（非软链），先 adopt 收编，不覆盖')
        if os.path.lexists(target):
            os.symlink(target, link)
            n += 1
    return n


def adopt(slug: str) -> list:
    """根目录现存实体移入 projects/<slug>/（重名冲突加时间戳，绝不静默覆盖）。"""
    d = book_dir(slug)
    os.makedirs(d, exist_ok=True)
    moved = []
    for name in SWAP_ENTRIES:
        src = os.path.join(ROOT_DIR, name)
        if not os.path.lexists(src) or os.path.islink(src):
            continue
        dst = os.path.join(d, name)
        if os.path.lexists(dst):
            dst += '.conflict_' + time.strftime('%Y%m%d%H%M%S')
        shutil.move(src, dst)
        moved.append(name)
    link_all(slug)
    return moved


def engine_busy() -> bool:
    """切换/重启前的守卫：三个引擎任务都不在跑才放行；引擎没起视为空闲。"""
    for task in GUARDED_TASKS:
        try:
            with urllib.request.urlopen(f'{ENGINE}/api/status/{task}', timeout=3) as r:
                if json.load(r).get('running'):
                    return True
        except OSError:
            continue
    return False


def restart_service() -> None:
    p = subprocess.run(['bash', '-c',
                        f'cd {SERVICE_DIR} && ./stop_novelTTS.sh >/dev/null 2>&1; sleep 2; ./start_novelTTS.sh'],
                       capture_output=True, text=True, timeout=300)
    print(p.stdout.strip().splitlines()[-1] if p.stdout else f'启动输出为空 rc={p.returncode}')


def wait_health(secs: int = 120) -> bool:
    deadline = time.time() + secs
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'{ENGINE}/api/system/stats', timeout=3):
                return True
        except OSError:
            time.sleep(2)
    return False


def switch(slug: str) -> None:
    reg = registry()
    if slug not in reg.get('projects', {}):
        raise SystemExit(f'未知项目 {slug}，先 projects.py add')
    if engine_busy():
        raise SystemExit('引擎正在跑任务（script/review/audio），等它结束或先取消')
    if reg.get('active') and reg['active'] != slug:
        adopt(reg['active'])           # 上一书可能有直写根目录的新文件，先收编
    n = link_all(slug)
    reg['active'] = slug
    _save(reg)
    print(f'SWITCH → {slug}（换链 {n} 项），重启服务…')
    restart_service()
    if not wait_health():
        raise SystemExit('服务 120s 未恢复，手动查 start_novelTTS 日志')
    from sync_state import sync
    print('SYNC:', sync(reg['projects'][slug]['title']))


def create_project(title: str, slug: str | None = None, src: str | None = None) -> str:
    """登记新书（可空工作区，上传即写入）；slug 缺省时由书名/时间戳生成。"""
    if slug is not None and not SLUG_RE.match(slug):
        raise SystemExit('slug 只允许小写字母数字短横线')
    reg = registry()
    projects = reg.setdefault('projects', {})
    if slug:
        if slug in projects:
            raise SystemExit(f'{slug} 已存在')
    else:
        base = re.sub(r'[^a-z0-9-]+', '-', title.lower()).strip('-')[:20] or 'book'
        slug, n = base, 1
        while slug in projects:
            n += 1
            slug = f'{base}-{n}'
    os.makedirs(book_dir(slug), exist_ok=True)
    if src:
        for name in SWAP_ENTRIES:
            s = os.path.join(src, name)
            if os.path.lexists(s):
                (shutil.copytree if os.path.isdir(s) else shutil.copy)(s, os.path.join(book_dir(slug), name))
    projects[slug] = {'title': title, 'created': time.strftime('%F')}
    _save(reg)
    return slug


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list')
    pa = sub.add_parser('adopt'); pa.add_argument('slug'); pa.add_argument('--title', required=True)
    pb = sub.add_parser('add'); pb.add_argument('slug', nargs='?'); pb.add_argument('--title', required=True)
    pb.add_argument('--from', dest='src', help='从该目录拷入 SWAP_ENTRIES（如工作区备份）')
    ps = sub.add_parser('switch'); ps.add_argument('slug')
    sub.add_parser('current')
    args = ap.parse_args()

    reg = registry()
    if args.cmd == 'list':
        active = reg.get('active')
        for slug, meta in sorted(reg.get('projects', {}).items()):
            cnt = len([e for e in SWAP_ENTRIES if os.path.lexists(os.path.join(book_dir(slug), e))])
            print(f"{'*' if slug == active else ' '} {slug:<14} {meta['title']}（{cnt}/{len(SWAP_ENTRIES)} 项）")
        if not reg.get('projects'):
            print('（空）先 adopt 当前工作区')
    elif args.cmd == 'current':
        print(reg.get('active'), (reg.get('projects', {}).get(reg.get('active') or '', {})).get('title'))
    elif args.cmd == 'adopt':
        if not SLUG_RE.match(args.slug):
            raise SystemExit('slug 只允许小写字母数字短横线')
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        moved = adopt(args.slug)
        reg.setdefault('projects', {})[args.slug] = {'title': args.title, 'created': time.strftime('%F')}
        reg['active'] = args.slug
        _save(reg)
        print(f'ADOPT {args.slug}: 收编 {moved or "（根目录已是软链/空）"}')
    elif args.cmd == 'add':
        slug = create_project(args.title, args.slug, args.src)
        print(f'ADD {slug}: title={args.title}')
    elif args.cmd == 'switch':
        if not (reg.get('projects', {}).get(args.slug, {}).get('title')):
            raise SystemExit(f'{args.slug} 未登记')
        switch(args.slug)


if __name__ == '__main__':
    main()
