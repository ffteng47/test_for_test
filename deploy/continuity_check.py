"""Continuity checker: character-level diff between the novel source text and
annotated_script.json, attributing every dropped/added span to a chunk index.

Stdlib only. Importable from app.py (check()) and runnable as a CLI:
    python3 continuity_check.py [--source FILE] [--json OUT]
"""
import argparse
import difflib
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

_KEEP = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uf900-\ufaffa-zA-Z0-9]')


def normalize(text):
    return ''.join(_KEEP.findall(text))


def _load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _source_text(override=None):
    if override:
        path = override
    else:
        state = _load_json(os.path.join(ROOT_DIR, 'state.json'), {})
        rel = state.get('input_file_path') or ''
        path = rel if os.path.isabs(rel) else os.path.join(ROOT_DIR, rel)
    if not path or not os.path.exists(path):
        return None, path
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read(), path


def check(source_override=None):
    entries = _load_json(os.path.join(ROOT_DIR, 'annotated_script.json'), None)
    src_raw, src_path = _source_text(source_override)
    if entries is None:
        return {'error': 'annotated_script.json not found', 'source_path': src_path}
    if src_raw is None:
        return {'error': 'source text not found (upload a book or pass --source)', 'source_path': src_path}

    src = normalize(src_raw)
    chunk_norms = [normalize(e.get('text', '')) for e in entries]
    script = ''.join(chunk_norms)

    starts, off = [], 0
    for cn in chunk_norms:
        starts.append(off)
        off += len(cn)
    ends = starts[1:] + [off]

    def chunk_at(pos):
        for i, (s, e) in enumerate(zip(starts, ends)):
            if s <= pos < e or (i == len(starts) - 1 and pos >= s):
                return i
        return len(entries) - 1

    chunks = [{
        'index': i,
        'speaker': e.get('speaker', ''),
        'missing': [],
        'added': [],
    } for i, e in enumerate(entries)]

    missing_total = added_total = 0
    sm = difflib.SequenceMatcher(None, src, script, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag in ('delete', 'replace') and i2 > i1:
            ci = chunk_at(min(j1, len(script) - 1)) if script else len(entries) - 1
            chunks[ci]['missing'].append({'at_source': i1, 'text': src[i1:i2]})
            missing_total += i2 - i1
        if tag in ('insert', 'replace') and j2 > j1:
            ci = chunk_at(j1)
            chunks[ci]['added'].append({'at_script': j1, 'text': script[j1:j2]})
            added_total += j2 - j1

    for c in chunks:
        c['status'] = 'gap' if c['missing'] else ('drift' if c['added'] else 'ok')

    return {
        'source_path': src_path,
        'source_chars': len(src),
        'script_chars': len(script),
        'similarity': round(sm.ratio(), 4),
        'missing_chars': missing_total,
        'added_chars': added_total,
        'gap_chunks': [c['index'] for c in chunks if c['status'] == 'gap'],
        'drift_chunks': [c['index'] for c in chunks if c['status'] == 'drift'],
        'chunks': chunks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source')
    ap.add_argument('--json', default=os.path.join(ROOT_DIR, 'continuity_report.json'))
    args = ap.parse_args()
    report = check(args.source)
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if 'error' in report:
        print('ERROR:', report['error'])
        return
    print(f"source={report['source_chars']} script={report['script_chars']} "
          f"sim={report['similarity']} missing={report['missing_chars']} added={report['added_chars']}")
    for c in report['chunks']:
        if c['status'] != 'ok':
            print(f"  chunk {c['index']} [{c['status']}] {c['speaker']}")
            for m in c['missing']:
                print(f"    MISSING @{m['at_source']}: {m['text']}")
            for a in c['added']:
                print(f"    ADDED   @{a['at_script']}: {a['text']}")
    print('report ->', args.json)


if __name__ == '__main__':
    main()
