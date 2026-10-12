import shutil

path = '/home/tff/software/novel-audiobook/alexandria/app/review_script.py'
shutil.copy(path, path + '.bak')
src = open(path, encoding='utf-8').read()

helper = '''
_CJK_RE = re.compile(r'[\\u4e00-\\u9fff\\u3040-\\u30ff\\uac00-\\ud7af\\uf900-\\ufaff]')


def tokenize_units(text):
    """CJK-aware unit count: each CJK char is one unit, each latin run is one unit."""
    units = []
    buf = []
    for ch in text:
        if _CJK_RE.match(ch):
            if buf:
                units.append(''.join(buf))
                buf = []
            units.append(ch)
        elif ch.isspace():
            if buf:
                units.append(''.join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        units.append(''.join(buf))
    return units


def check_text_loss('''

anchor = 'def check_text_loss('
assert anchor in src and 'tokenize_units' not in src
src = src.replace(anchor, helper, 1)

src = src.replace(
    'orig_words.extend(normalize_text(e.get("text", "")).split())',
    'orig_words.extend(tokenize_units(normalize_text(e.get("text", ""))))')
src = src.replace(
    'corr_words.extend(normalize_text(e.get("text", "")).split())',
    'corr_words.extend(tokenize_units(normalize_text(e.get("text", ""))))')

open(path, 'w', encoding='utf-8').write(src)
import py_compile
py_compile.compile(path, doraise=True)
print('CJK_TEXTLOSS_PATCH_APPLIED')
