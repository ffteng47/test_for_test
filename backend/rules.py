"""rules — 一致性规则引擎（不花 token 的那半边校验）。

原则：规则只报警、不改写；命中后可升级给 LLM reviewer 判断。
扩展方式：写一个 rule_xxx(segments, bible) -> list[Finding]，加进 RULES 元组即可。

用法： python3 rules.py [--write]   # --write 把命中段落 qc='retry' 回写库
Finding = {code, ord, severity(warn|error), detail}
"""
from __future__ import annotations

import argparse
import json
import os
import re

from domain import active_project_id, is_dialogue, workspace_paths
from noveldb import Db, open_db


def rule_unknown_speaker(segments, bible):
    known = set(bible.get('characters', {})) | {'narrator'}
    return [{'code': 'unknown_speaker', 'ord': s['ord'], 'severity': 'error',
             'detail': f"说话人 '{s['speaker']}' 不在 Story Bible"}
            for s in segments if s['speaker'] not in known]


def rule_quote_form(segments, bible):
    out = []
    for s in segments:
        quoted = is_dialogue(s['text'])
        if s['kind'] == 'dialogue' and not quoted:
            out.append({'code': 'dialogue_unquoted', 'ord': s['ord'], 'severity': 'warn',
                        'detail': '对白段未包外层引号，TTS 归属可能歧义'})
        if s['kind'] == 'narration' and quoted:
            out.append({'code': 'narration_quoted', 'ord': s['ord'], 'severity': 'warn',
                        'detail': '旁白段整体被引号包裹，疑似切分错误'})
    return out


def rule_duplicate_adjacent(segments, bible):
    return [{'code': 'duplicate_text', 'ord': s['ord'], 'severity': 'error',
             'detail': '与上一段文本完全相同'}
            for prev, s in zip(segments, segments[1:])
            if s['text'].strip() and s['text'].strip() == prev['text'].strip()]


_TAG_TAIL = re.compile(r'[“"」][\u4e00-\u9fff]{0,8}(?:说道|道|问道|喊道|低声说|喃喃道)$')


def rule_attribution_residue(segments, bible):
    return [{'code': 'attribution_residue', 'ord': s['ord'], 'severity': 'warn',
             'detail': '句尾残留“XX说道”式归属标签，建议移入旁白段'}
            for s in segments
            if _TAG_TAIL.search(s['text'].strip())]


def rule_emotion_jump(segments, bible):
    """同角色相邻台词 intensity 差 > 0.5 且中间无旁白 → 需剧情背书，升级 LLM。"""
    out, prev = [], None
    for s in segments:
        if s['kind'] == 'narration':
            prev = None
            continue
        if s.get('intensity') is None:
            continue
        if prev and prev['speaker'] == s['speaker'] and abs(prev['intensity'] - s['intensity']) > 0.5:
            out.append({'code': 'emotion_transition_anomaly', 'ord': s['ord'], 'severity': 'warn',
                        'detail': f"intensity {prev['intensity']:.2f}->{s['intensity']:.2f} 无旁白过渡"})
        prev = s
    return out


def rule_pause_sanity(segments, bible):
    return [{'code': 'pause_out_of_range', 'ord': s['ord'], 'severity': 'warn',
             'detail': f"pause_after={s['pause_after']} 超出 0..3000ms"}
            for s in segments if not 0 <= (s['pause_after'] or 0) <= 3000]


def rule_missing_audio(segments, bible):
    return [{'code': 'done_without_audio', 'ord': s['ord'], 'severity': 'error',
             'detail': 'status=done 但无已选音频版本'}
            for s in segments if s.get('status') == 'done' and not s.get('audio_path')]


RULES = (rule_unknown_speaker, rule_quote_form, rule_duplicate_adjacent,
         rule_attribution_residue, rule_emotion_jump, rule_pause_sanity, rule_missing_audio)


def run(project_id: int | None = None) -> list[dict]:
    paths = workspace_paths()
    db = Db(open_db(paths['db']))
    pid = project_id or active_project_id(db.con)
    bible = db.get_bible(pid)
    segments = [dict(r) for r in db.segments(pid)]
    findings = []
    for rule in RULES:
        findings.extend(rule(segments, bible))
    return sorted(findings, key=lambda f: (f['ord'], f['code']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='warn/error 命中段回写 qc=retry')
    args = ap.parse_args()
    findings = run()
    report = workspace_paths()['db'].replace('novelaudio.db', 'rules_report.json')
    with open(report, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=1)
    print(f'RULES: {len(findings)} findings -> {report}')
    for fi in findings:
        print(f"  [{fi['severity']}] #{fi['ord']} {fi['code']}: {fi['detail']}")
    if args.write:
        paths = workspace_paths()
        db = Db(open_db(paths['db']))
        pid = active_project_id(db.con)
        by_ord = {}
        for s in db.segments(pid):
            by_ord[s['ord']] = s['id']
        for fi in findings:
            if fi['ord'] in by_ord:
                db.set_segment_qc(by_ord[fi['ord']], 'retry')
        print('qc=retry 已回写')


def _selftest():
    bible = {'characters': {'chenmo': {}}}
    segs = [
        {'ord': 0, 'speaker': 'chenmo', 'kind': 'dialogue', 'text': '「你好。」', 'pause_after': 0},
        {'ord': 1, 'speaker': 'ghost', 'kind': 'narration', 'text': '「你好。」', 'pause_after': 0},
        {'ord': 2, 'speaker': 'chenmo', 'kind': 'dialogue', 'text': '你好', 'pause_after': 0},
        {'ord': 3, 'speaker': 'chenmo', 'kind': 'dialogue', 'text': '你好', 'pause_after': 5000},
    ]
    codes = {f['code'] for rule in RULES for f in rule(segs, bible)}
    expect = {'unknown_speaker', 'narration_quoted', 'dialogue_unquoted',
              'duplicate_text', 'pause_out_of_range'}
    assert expect <= codes, f'missing: {expect - codes}'
    print('SELFTEST OK')


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        _selftest()
    else:
        main()
