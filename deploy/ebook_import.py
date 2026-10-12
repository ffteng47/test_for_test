# E-books 标准册 → Alexandria 书目导入器（路 B，纯文件级，不重启后端）。
#
# 标准格式见 docs/ebooks-standard.md：册目录必须有 meta.json {slug,title,volume}
# 和（output 下任意深度、按 mtime 最新的）annotated_script.json。
#
# 用法（本机 Windows 跑，依赖 ssh/scp 免密到服务器）：
#   python deploy/ebook_import.py --check E-books/测试书/第1册   # 只校验，不动服务器
#   python deploy/ebook_import.py        E-books/测试书/第1册   # 校验 + 导入
#
# 真跑前会探测后端：活着且 script/review/audio/persona/m4b_export/audacity_export
# 任一 running → 拒绝（改 chunks.json 不能撞正在跑的生成）。后端没起来反而放行——
# 文件级替换本来就是停机窗口的活。

import argparse
import glob
import json
import os
import re
import subprocess
import sys

SERVER = "tff@192.168.31.213"
ALEX = "/home/tff/software/novel-audiobook/alexandria"
TASKS = ["script", "review", "audio", "persona", "m4b_export", "audacity_export"]
SPEAKER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

if hasattr(sys.stdout, "reconfigure"):  # Windows GBK 控制台打不了中文以外的符号
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ssh(cmd, capture=False):
    r = subprocess.run(["ssh", SERVER, cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and not capture:
        raise SystemExit(f"SSH FAIL: {cmd}\n{r.stderr[:400]}")
    return r.stdout.strip()


def scp(local, remote):
    subprocess.run(["scp", local, f"{SERVER}:{remote}"], check=True)


def find_script(voldir):
    cands = glob.glob(os.path.join(voldir, "**", "annotated_script.json"), recursive=True)
    if not cands:
        raise SystemExit(f"{voldir} 下找不到 annotated_script.json（标准见 docs/ebooks-standard.md）")
    return max(cands, key=os.path.getmtime)


def validate(path):
    """返回 (entries, speakers_sorted)。不合格直接 SystemExit。"""
    data = json.load(open(path, encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise SystemExit("annotated_script.json 必须是非空数组")
    for i, e in enumerate(data):
        if not (isinstance(e, dict) and SPEAKER_RE.match(str(e.get("speaker") or ""))
                and str(e.get("text") or "").strip()
                and isinstance(e.get("instruct", ""), str)):
            raise SystemExit(f"entry {i} 不合格: {str(e)[:120]}")
    return data, sorted({e["speaker"] for e in data})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("voldir")
    ap.add_argument("--check", action="store_true", help="只校验不导入")
    a = ap.parse_args()

    meta = json.load(open(os.path.join(a.voldir, "meta.json"), encoding="utf-8"))
    slug, title = meta["slug"], meta["title"]
    assert re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", slug), f"slug 非法: {slug}"

    script = find_script(a.voldir)
    entries, speakers = validate(script)
    print(f"校验通过: {script}\n  entries={len(entries)} speakers={len(speakers)} {speakers}")

    other = os.path.join(os.path.dirname(script), "script_map.json")
    book = f"{ALEX}/projects/{slug}"

    if a.check:
        vc = os.path.join(a.voldir, "voice_config.json")
        if os.path.exists(vc):  # --check 离线自检：和本地快照对一下未绑角色
            bound = set(json.load(open(vc, encoding="utf-8")))
            print(f"本地快照未绑音色: {sorted(set(speakers) - bound) or '（无）'}")
        return

    # 后端活着才探测忙闲；拒绝在有生成任务时动文件
    up = ssh(f"curl -s -m 5 http://127.0.0.1:4200/api/system/stats >/dev/null 2>&1 && echo UP || echo DOWN",
             capture=True)
    if up == "UP":
        for t in TASKS:
            s = ssh(f"curl -s -m 5 http://127.0.0.1:4200/api/status/{t}", capture=True)
            if '"running":true' in s.replace(" ", ""):
                raise SystemExit(f"任务 {t} 正在跑，暂缓导入（标准 §四 执行前提）")
    else:
        print("后端未响应：按停机窗口处理，允许直接落文件")

    if slug not in json.loads(ssh(f"cat {ALEX}/projects.json", capture=True) or "{}").get("projects", {}):
        ssh(f"cd {ALEX} && venv/bin/python backend/projects.py add {slug} --title '{title}'")
        print(f"ADD {slug}（新册已登记；注意 CLI add 不切工作区，切换需重启窗口）")

    ts = ssh("date +%y%m%d_%H%M%S", capture=True)
    # chunks.json 的家在共享根（alexandria/chunks.json 是真实文件，书目录那份只是换书时的仓库），
    # 只删书目录那份后端照读根的旧段——2026-10-12 踩过。两处都备份、都删。
    ssh(f"for f in {book}/annotated_script.json {book}/chunks.json {book}/script_map.json "
        f"{ALEX}/chunks.json; do [ -e $f ] && cp $f $f.bak_{ts}; done; "
        f"rm -f {book}/chunks.json {ALEX}/chunks.json; true")
    # 旧成品必须整体让位，否则新脚本按 voiceline_NNNN 同名索引出音时会**混着播上一版的音频**
    # （2026-10-12 现场：864 新段 + 旧 voicelines/母带 = 播放旧书声）。全部归档，不删。
    ssh(f"cd {book} && [ -d voicelines ] && mv voicelines voicelines.bak_{ts} && mkdir voicelines; "
        f"for f in cloned_audiobook.mp3 audiobook.m4b prooflisten.jsonl; do "
        f"[ -e $f ] && mv $f $f.bak_{ts}; done; true")

    scp(script, f"{book}/annotated_script.json")
    if os.path.exists(other):
        scp(other, f"{book}/script_map.json")

    vc_raw = ssh(f"cat {book}/voice_config.json 2>/dev/null", capture=True)
    bound = set(json.loads(vc_raw)) if vc_raw else set()
    unbound = sorted(set(speakers) - bound)
    print(f"导入完成: {book}/annotated_script.json（chunks.json 已删，后端下次读取自动重建 {len(entries)} 段 pending）")
    print(f"未绑音色: {unbound or '（无）'} —— 绑完之前这些角色的段落不要生成")

    rights = ssh(f"test -f {book}/rights.json && echo Y || echo N", capture=True)
    if rights == "N":
        ssh(f"cd {ALEX} && venv/bin/python deploy_patches/check_rights.py --slug {slug} --init", capture=True)
        print("rights.json 缺 → 已生成模板，人工填实前 check_rights 不开工（M5④）")


if __name__ == "__main__":
    main()
