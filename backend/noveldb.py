"""noveldb — SQLite 数据层（阶段 2 基座，Story Bible 架构的“状态”一侧）。

设计约定：
- Alexandria 引擎继续以工作区 JSON（state/annotated_script/chunks/voice_config）为运行时；
  本库是产品级唯一真源：项目、人物长期状态(bible/chapter memory)、场景、段落、音频版本、任务。
- 单 worker + WAL，裸 stdlib sqlite3，不引入 ORM。JSON 列以 TEXT 存储，读写走 json 包装。
- 所有写接口幂等：重复 sync 不产生重复行。

用法：
    from noveldb import open_db, Db
    db = Db(open_db('/path/novelaudio.db'))
    pid = db.upsert_project('《青石巷》', author='佚名')
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  author TEXT DEFAULT '',
  lang TEXT DEFAULT 'zh',
  bible TEXT DEFAULT '{}',                  -- Story Bible：关系/世界观/时间线/global_style（长期记忆）
  created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS characters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  key TEXT NOT NULL,                        -- 归一化 id，如 chenmo
  label TEXT,                               -- 引擎内原始标签，如 'CHEN MO'
  gender TEXT, age INTEGER,
  personality TEXT DEFAULT '[]',
  aliases TEXT DEFAULT '[]',
  voice_config TEXT,                        -- 引擎音色 config 原样存放（引擎无关）
  UNIQUE(project_id, key));

CREATE TABLE IF NOT EXISTS chapters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  no INTEGER NOT NULL,
  title TEXT,
  state TEXT DEFAULT '{}',                  -- chapter memory：在场人物/情绪轨迹/地点时间
  UNIQUE(project_id, no));

CREATE TABLE IF NOT EXISTS scenes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  ord INTEGER NOT NULL,
  setting TEXT, time TEXT,
  tension REAL,
  summary TEXT);

CREATE TABLE IF NOT EXISTS segments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  scene_id INTEGER REFERENCES scenes(id) ON DELETE SET NULL,
  ord INTEGER NOT NULL,
  speaker TEXT NOT NULL,
  kind TEXT DEFAULT 'narration',            -- narration | dialogue
  text TEXT NOT NULL,
  instruct TEXT DEFAULT '',
  pause_after INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending',            -- pending|generating|done|error（与引擎同步）
  qc TEXT,                                  -- pass | retry | NULL（规则+ASR 结论）
  qc_err REAL,                              -- 最近一次 ASR 字级错误率
  emotion TEXT, intensity REAL);            -- 内部数值表示；出口量化映射进 instruct

CREATE TABLE IF NOT EXISTS audio_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  model TEXT, seed INTEGER,
  chosen INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')));

CREATE TABLE IF NOT EXISTS voice_samples(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                       -- lab | chunk | file
  src_id TEXT DEFAULT '',                   -- 来源标识：实验室记录 id / 段序号 / 相对路径
  path TEXT NOT NULL,                       -- 相对 ROOT_DIR 的音频路径
  role TEXT DEFAULT '',                     -- 人物 key：不是标签维度，单列才好筛
  text TEXT DEFAULT '',
  tags TEXT DEFAULT '{}',                   -- tag_vocab 校验后的标签（含 pace/pitch 归一值）
  derived TEXT DEFAULT '{}',                -- 实测原始值：时长/字每秒/基频
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(project_id, kind, src_id, path));  -- 同源重复入库即覆盖，不产生重复行

CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
  task TEXT NOT NULL,
  name TEXT,
  status TEXT DEFAULT 'queued',
  payload TEXT DEFAULT '{}',
  created_at TEXT DEFAULT (datetime('now')));
"""
CONFIRM_TASK = 'plan_confirm'   # R8 #1 开书确认闸的唯一 task 值（docs/confirmation-gate-design.md v1.0）
# 状态机（设计稿 §2，代码层枚举，SQL 不动）：queued→confirmed / queued→rejected / rejected→queued
_JOB_TRANSITIONS = {('queued', 'confirmed'), ('queued', 'rejected'), ('rejected', 'queued')}
_JOB_STATUSES = frozenset(s for pair in _JOB_TRANSITIONS for s in pair)


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def open_db(path: str) -> sqlite3.Connection:
    """打开（必要时创建）数据库并确保 schema。调用方负责 close。"""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript(SCHEMA)
    _migrate(con)
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """幂等补列：CREATE TABLE IF NOT EXISTS 不会给已存在的表加新列。"""
    cols = {r['name'] for r in con.execute('PRAGMA table_info(segments)')}
    if 'qc_err' not in cols:
        con.execute('ALTER TABLE segments ADD COLUMN qc_err REAL')
        con.commit()


class Db:
    """薄封装：只做 upsert/query，不含业务判断（业务在 rules.py / 上层服务）。"""

    def __init__(self, con: sqlite3.Connection):
        self.con = con

    # ---- projects / bible ----
    def upsert_project(self, title: str, author: str = '') -> int:
        row = self.con.execute('SELECT id FROM projects WHERE title=?', (title,)).fetchone()
        if row:
            return row['id']
        cur = self.con.execute('INSERT INTO projects(title, author) VALUES(?, ?)', (title, author))
        self.con.commit()
        return cur.lastrowid

    def get_bible(self, project_id: int) -> dict:
        row = self.con.execute('SELECT bible FROM projects WHERE id=?', (project_id,)).fetchone()
        return json.loads(row['bible']) if row else {}

    def set_bible(self, project_id: int, bible: dict) -> None:
        self.con.execute('UPDATE projects SET bible=? WHERE id=?', (_j(bible), project_id))
        self.con.commit()

    # ---- characters ----
    def upsert_character(self, project_id: int, key: str, *, label: Optional[str] = None,
                         gender: Optional[str] = None, age: Optional[int] = None,
                         personality: Optional[list] = None, aliases: Optional[list] = None,
                         voice_config: Optional[dict] = None) -> int:
        self.con.execute(
            '''INSERT INTO characters(project_id, key, label, gender, age, personality, aliases, voice_config)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(project_id, key) DO UPDATE SET
                 label=COALESCE(excluded.label, label),
                 gender=COALESCE(excluded.gender, gender),
                 age=COALESCE(excluded.age, age),
                 personality=COALESCE(excluded.personality, personality),
                 aliases=COALESCE(excluded.aliases, aliases),
                 voice_config=COALESCE(excluded.voice_config, voice_config)''',
            (project_id, key, label, gender, age,
             _j(personality) if personality is not None else None,
             _j(aliases) if aliases is not None else None,
             _j(voice_config) if voice_config is not None else None))
        self.con.commit()
        return self.con.execute('SELECT id FROM characters WHERE project_id=? AND key=?',
                                (project_id, key)).fetchone()['id']

    def characters(self, project_id: int) -> list[sqlite3.Row]:
        return self.con.execute(
            'SELECT * FROM characters WHERE project_id=? ORDER BY key', (project_id,)).fetchall()

    # ---- chapters / scenes ----
    def upsert_chapter(self, project_id: int, no: int, title: str = '', state: Optional[dict] = None) -> int:
        self.con.execute(
            '''INSERT INTO chapters(project_id, no, title, state) VALUES(?,?,?,?)
               ON CONFLICT(project_id, no) DO UPDATE SET
                 title=COALESCE(excluded.title, title),
                 state=COALESCE(excluded.state, state)''',
            (project_id, no, title, _j(state) if state is not None else None))
        self.con.commit()
        return self.con.execute('SELECT id FROM chapters WHERE project_id=? AND no=?',
                                (project_id, no)).fetchone()['id']

    def upsert_scene(self, project_id: int, chapter_id: int, ord_: int, *,
                     setting: str = '', time_: str = '', tension: Optional[float] = None,
                     summary: str = '') -> int:
        row = self.con.execute('SELECT id FROM scenes WHERE project_id=? AND ord=?',
                               (project_id, ord_)).fetchone()
        if row:
            self.con.execute('UPDATE scenes SET chapter_id=?, setting=?, time=?, tension=?, summary=? WHERE id=?',
                             (chapter_id, setting, time_, tension, summary, row['id']))
            self.con.commit()
            return row['id']
        cur = self.con.execute(
            'INSERT INTO scenes(project_id, chapter_id, ord, setting, time, tension, summary) VALUES(?,?,?,?,?,?,?)',
            (project_id, chapter_id, ord_, setting, time_, tension, summary))
        self.con.commit()
        return cur.lastrowid

    # ---- segments / versions ----
    def replace_segments(self, project_id: int, rows: list[dict]) -> None:
        """整批幂等重写段落（单书工作区语义）。每行需含 ord/speaker/text，可选其余列。

        qc/qc_err/emotion/intensity 只存在于库里（工作区 JSON 没有）：文本未变按 ord 继承，
        文本变了则丢弃——质检结论绑定文本，过期结果比没有更危险。"""
        keep = {r['ord']: dict(r) for r in self.con.execute(
            'SELECT ord, text, qc, qc_err, emotion, intensity FROM segments WHERE project_id=?',
            (project_id,))}
        self.con.execute('DELETE FROM audio_versions WHERE segment_id IN '
                         '(SELECT id FROM segments WHERE project_id=?)', (project_id,))
        self.con.execute('DELETE FROM segments WHERE project_id=?', (project_id,))
        for r in rows:
            o = keep.get(r['ord'])
            if o is not None and o['text'] == r['text']:
                for name in ('qc', 'qc_err', 'emotion', 'intensity'):
                    r.setdefault(name, o[name])
            cur = self.con.execute(
                '''INSERT INTO segments(project_id, scene_id, ord, speaker, kind, text,
                                         instruct, pause_after, status, qc, qc_err, emotion, intensity)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (project_id, r.get('scene_id'), r['ord'], r['speaker'], r.get('kind', 'narration'),
                 r['text'], r.get('instruct', ''), r.get('pause_after', 0),
                 r.get('status', 'pending'), r.get('qc'), r.get('qc_err'),
                 r.get('emotion'), r.get('intensity')))
            if r.get('audio_path'):
                self.con.execute(
                    'INSERT INTO audio_versions(segment_id, path, model, seed, chosen) VALUES(?,?,?,?,1)',
                    (cur.lastrowid, r['audio_path'], r.get('model'), r.get('seed')))
        self.con.commit()

    def segments(self, project_id: int) -> list[sqlite3.Row]:
        """段落 + 当前选定音频路径（LEFT JOIN，无音频为 None）。"""
        return self.con.execute(
            '''SELECT s.*, v.path AS audio_path FROM segments s
               LEFT JOIN audio_versions v ON v.segment_id = s.id AND v.chosen = 1
               WHERE s.project_id=? ORDER BY s.ord''', (project_id,)).fetchall()

    def set_segment_qc(self, segment_id: int, qc: str, err: Optional[float] = None) -> None:
        # COALESCE：规则引擎只改结论时不清掉已有 ASR 错误率
        self.con.execute('UPDATE segments SET qc=?, qc_err=COALESCE(?, qc_err) WHERE id=?',
                         (qc, err, segment_id))
        self.con.commit()

    # ---- jobs ----
    def add_job(self, project_id: Optional[int], task: str, name: str = '',
                status: str = 'queued', payload: Optional[dict] = None) -> int:
        cur = self.con.execute('INSERT INTO jobs(project_id, task, name, status, payload) VALUES(?,?,?,?,?)',
                               (project_id, task, name, status, _j(payload or {})))
        self.con.commit()
        return cur.lastrowid

    def add_confirm_job(self, project_id: Optional[int], task: str, name: str,
                        payload: dict) -> int:
        """确认闸入册：状态恒从 queued 起步，推进只走 set_job_status。"""
        return self.add_job(project_id, task, name=name, status='queued', payload=payload)

    def get_job(self, job_id: int) -> Optional[sqlite3.Row]:
        return self.con.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()

    def latest_job(self, project_id: int, task: str) -> Optional[sqlite3.Row]:
        return self.con.execute(
            'SELECT * FROM jobs WHERE project_id=? AND task=? ORDER BY id DESC LIMIT 1',
            (project_id, task)).fetchone()

    def set_job_status(self, job_id: int, status: str, expected_status: str) -> bool:
        """CAS 推进：当前状态==expected 才写，返回是否抢到（防并发双确认）。状态机外组合直接报错。"""
        if status not in _JOB_STATUSES or expected_status not in _JOB_STATUSES:
            raise ValueError(f"非法状态: {expected_status}→{status}")
        if (expected_status, status) not in _JOB_TRANSITIONS:
            raise ValueError(f"非法迁移: {expected_status}→{status}，允许 {sorted(_JOB_TRANSITIONS)}")
        cur = self.con.execute('UPDATE jobs SET status=? WHERE id=? AND status=?',
                               (status, job_id, expected_status))
        self.con.commit()
        return cur.rowcount == 1

    def summary(self, project_id: int) -> dict:
        counts = {}
        for table in ('chapters', 'scenes', 'segments', 'characters'):
            counts[table] = self.con.execute(
                f'SELECT COUNT(*) n FROM {table} WHERE project_id=?', (project_id,)).fetchone()['n']
        counts['audio_done'] = self.con.execute(
            "SELECT COUNT(*) n FROM segments WHERE project_id=? AND status='done'", (project_id,)).fetchone()['n']
        return counts
