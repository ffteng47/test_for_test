# M3 审听工位安装器（幂等）：给「人工全听」加一个能记数的地方。
#
# 修的真问题：报价里的错读率 ‰ 和 cost-model §5 的「听感返工率」「prooflisten 工时比」
# 全是假设值。机检那一半已经有数（`/api/qc`：259 段 6 段 retry = 2.3%），但 ASR 只对文本，
# 听不出音色漂移和合法异读——**人工那一遍没有落点，所以永远出不来数**。
#
# 判定落在 `projects/<slug>/prooflisten.jsonl`（追加式），**不写 chunks.json**：
# `ProjectManager.update_chunk` 是白名单式的，未知字段直接丢；而 `save_chunks` 整体读改写，
# 和生成任务并发时会把对方刚写的状态覆盖回去。追加一行 JSON 既没有竞争也没有丢字段风险，
# 重听同一段以最后一条为准，工时按所有条累加（重听也是成本）。
#
# 跑法（在服务器上，用 alexandria 的 venv）：
#   alexandria/venv/bin/python deploy/patches/add_prooflisten.py
# app.py 的改动必须重启主服务才生效，重启前先确认没有生成任务在跑。

import os
import py_compile
import shutil

from add_export_loudnorm import BASE, patch

APP = os.path.join(BASE, "app.py")
ANCHOR = '@app.get("/api/audiobook_m4b")'

ROUTE = '''# prooflisten:route
def _proof_dir():
    """审听记录归书自己的目录（和 delivery_report.json 同级）。
    别用 `realpath(CHUNKS_PATH)`：`chunks.json` 虽然在 SWAP_ENTRIES 里，实测服务器上是根目录的
    真文件，反查会退到多本书共用的软链根，判定就会串书。唯一入口是 projects.json 的 active。"""
    import os as _os, sys as _sys
    _bk = _os.path.join(ROOT_DIR, "backend")
    if _bk not in _sys.path:
        _sys.path.insert(0, _bk)
    from domain import PROJECTS_DIR, registry
    active = registry().get("active")
    return _os.path.join(PROJECTS_DIR, active) if active else ROOT_DIR


@app.post("/api/prooflisten")
def post_prooflisten(ord: int, result: str, secs: float = 0, note: str = ""):
    """审听判定追加一行。四类分开计：合成语音的错读集中在生僻字/数字串/多音字，
    一个平均数会把问题藏起来（见 docs/post-production-plan.md §M3 判据风险）。"""
    import json as _json, os as _os, time as _time
    if result not in PROOFRESULTS:
        raise HTTPException(status_code=400, detail=f"未知判定 {result!r}，可用：{PROOFRESULTS}")
    total = len(project_manager.load_chunks())
    if not 0 <= ord < total:
        raise HTTPException(status_code=404, detail=f"段号 {ord} 超出 0..{total - 1}")
    d = _proof_dir()
    _os.makedirs(d, exist_ok=True)
    path = _os.path.join(d, "prooflisten.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(_json.dumps({"at": int(_time.time()), "ord": ord, "result": result,
                             "secs": round(secs, 1), "note": note[:200]}, ensure_ascii=False) + "\\n")
    return {"ok": True, "书": _os.path.basename(d), "落点": path}


@app.get("/api/prooflisten")
def get_prooflisten():
    """审听进度与三个待标定数的原料：出错率、工时比、返工率。未审段数在导出前检查条上显示。"""
    import json as _json, os as _os
    book_dir = _proof_dir()
    path = _os.path.join(book_dir, "prooflisten.jsonl")
    chunks = project_manager.load_chunks()
    latest = {}
    secs = 0.0
    if _os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = _json.loads(line)
                except ValueError:
                    continue
                if r.get("result") in PROOFRESULTS and isinstance(r.get("ord"), int):
                    latest[r["ord"]] = r
                    secs += r.get("secs") or 0
    counts = {k: sum(1 for r in latest.values() if r["result"] == k) for k in PROOFRESULTS}
    return {
        "书": _os.path.basename(book_dir), "总段数": len(chunks),
        "已审段数": len(latest), "未审段数": max(0, len(chunks) - len(latest)),
        "计数": counts,
        # 工时比 = 人工工时s / 成片时长；成片时长不在这张表里，交付时取 delivery_report 的 全项实测.时长s
        "人工工时s": round(secs, 1),
        "最新": {str(k): v["result"] for k, v in latest.items()},
        "报告": path,
    }


PROOFRESULTS = ("ok", "misread", "timbre", "regen")


''' + ANCHOR


def main():
    backup = APP + ".bak_pre_prooflisten"
    if not os.path.exists(backup):
        shutil.copy(APP, backup)
        print(f"BACKUP {backup}")

    patch(APP, [(ANCHOR, ROUTE, "# prooflisten:route")], "PROOF_APP")
    py_compile.compile(APP, doraise=True)
    print("PROOF_OK（app.py 改动需重启主服务才生效；重启前先确认无生成任务在跑）")


if __name__ == "__main__":
    main()
