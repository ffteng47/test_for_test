import json, shutil, time, urllib.request

BASE = '/home/tff/software/novel-audiobook/alexandria'
API = 'http://127.0.0.1:4200'
script_path = f'{BASE}/annotated_script.json'
backup = f'{BASE}/annotated_script.manual_fix.json'
shutil.copy(script_path, backup)

def call(path, method='GET', body=None):
    req = urllib.request.Request(API + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header('Content-Type', 'application/json')
    return json.load(urllib.request.urlopen(req, data=data, timeout=60))

def wait(task, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(6)
        st = call(f'/api/status/{task}')
        if not st.get('running', True):
            print(f'--- {task} log tail ---')
            for line in (st.get('logs') or [])[-6:]:
                print('   ', line[:150])
            return st
    print(task, 'TIMEOUT')
    return {}

def load():
    return json.load(open(script_path, encoding='utf-8'))

call('/api/generate_script', 'POST', {})
wait('script')
gen = load()
json.dump(gen, open('/tmp/after_gen.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('AFTER_ANNOTATE entries:', len(gen))

call('/api/review_script', 'POST', {})
wait('review')
rev = load()
json.dump(rev, open('/tmp/after_review.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('AFTER_REVIEW entries:', len(rev))

def joined(s):
    return ''.join(e.get('text', '') for e in s)

src = open(f'{BASE}/app/uploads/demo.txt', encoding='utf-8').read()
src_c = ''.join(c for c in src if '\u4e00' <= c <= '\u9fff')
for name, s in [('annotated', gen), ('reviewed', rev)]:
    t = ''.join(c for c in joined(s) if '\u4e00' <= c <= '\u9fff')
    print(f'{name}: hanzi_count={len(t)} vs source {len(src_c)}')

gmap = {i: e.get('speaker') for i, e in enumerate(gen)}
rmap = {i: e.get('speaker') for i, e in enumerate(rev)}
changed = [i for i in gmap if i in rmap and gmap[i] != rmap[i]]
print('SPEAKER_CHANGES:', [(i, gmap[i], rmap[i]) for i in changed])
for i in changed[:8]:
    print(i, '|', rev[i].get('text', '')[:42], '|', gmap[i], '->', rmap[i])

shutil.copy(backup, script_path)
print('RESTORED')
