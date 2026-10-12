# M1 机检闸门安装器（幂等）：把 delivery_report.json 接成前端能读的一道拦。
#
# 修的真问题：母带后期跑完只往 `projects/<slug>/delivery_report.json` 写了一份报告，
# 谁都不读它。归一失败、响度不达标，导出照样出一个能下载的成品——不合格和合格在
# 界面上长得一样。闸门判据本身不在这里，唯一真源是 `backend/master_audio.py` 的 `gate()`。
#
# 两处接线：
#   1. `app.py` 新增 `GET /api/delivery_report`。报告在 `projects/<slug>/`，
#      `root_dir` 是多本书共用的软链根，所以从交付物软链反查真实书目录。
#   2. `project.py` 的 `_normalize_master`：归一抛异常时也写一份 `通过=false` 的报告。
#      否则前端读不到文件只能显示「未机检」，分不清「这台没导出过」和「刚崩了、成品不合格」。
#   3. `project.py` 两条导出路各加一次 `_verify_delivery(output_path)`——**机检必须看真成品**。
#      归一只能量中间 WAV，于是报告里 `章节数: 0→0`、体积 117.7 MB（那是 WAV，成品 m4b 是 20.4 MB），
#      「章节标记没丢」这条判据从来没生效过；而「导出把 259 章弄没了」恰恰是这一层该拦的事。
#      实测来自 2026-10-11 重跑一次导出后的 delivery_report.json。
#
# 跑法（服务器上，用 alexandria 的 venv）：
#   alexandria/venv/bin/python deploy/patches/add_delivery_gate.py
# app.py 的改动必须重启主服务才生效，重启前先确认没有生成任务在跑（见文件末尾打印）。

import os
import py_compile
import shutil

from add_export_loudnorm import BASE, M4B_RETURN_NEW, M4B_RETURN_OLD, MP3_OLD, VERIFY, patch

APP = os.path.join(BASE, "app.py")
PROJ = os.path.join(BASE, "project.py")

NORM_ANCHOR = "    def _normalize_master(self, final_audio, output_path):"
MP3_NEW = (MP3_OLD + '\n        # master-loudnorm:verify-mp3\n'
           '        self._verify_delivery(output_path)\n')

EXC_OLD = '''        except Exception as exc:
            print(f"!! 母带后期执行失败，成品未归一（不要交付）：{exc}")
            return final_audio'''

EXC_NEW = '''        except Exception as exc:
            # master-loudnorm:fail-report
            try:
                with open(_os.path.join(book_dir, "delivery_report.json"),
                          "w", encoding="utf-8") as f:
                    _json.dump({"书": _os.path.basename(book_dir), "错误": str(exc),
                                "验收": {"母带后期执行失败": False}, "通过": False},
                               f, ensure_ascii=False, indent=2)
            except OSError:
                pass
            print(f"!! 母带后期执行失败，成品未归一（不要交付）：{exc}")
            return final_audio'''

ANCHOR = '@app.get("/api/audiobook_m4b")'
ROUTE = '''@app.get("/api/delivery_report")
def get_delivery_report():
    """成品机检报告：前端只读这一份。读不到就明确返回「未机检」，不做乐观默认。"""
    import json as _json, os as _os
    for link in (M4B_PATH, AUDIOBOOK_PATH):
        if not _os.path.exists(link):
            continue
        # root_dir 是多本书共用的软链根，报告在软链真正指向的 projects/<slug>/ 里
        p = _os.path.join(_os.path.dirname(_os.path.realpath(link)), "delivery_report.json")
        if _os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                rep = _json.load(f)
            rep["报告"] = p
            return rep
    return {"未机检": True}


''' + ANCHOR


def main():
    backup = APP + ".bak_pre_gate"
    if not os.path.exists(backup):
        shutil.copy(APP, backup)
        print(f"BACKUP {backup}")

    patch(APP, [(ANCHOR, ROUTE, "/api/delivery_report")], "GATE_APP")
    patch(PROJ, [
        (EXC_OLD, EXC_NEW, "master-loudnorm:fail-report"),
        (NORM_ANCHOR, VERIFY + NORM_ANCHOR, "def _verify_delivery"),
        (MP3_OLD, MP3_NEW, "master-loudnorm:verify-mp3"),
        (M4B_RETURN_OLD, M4B_RETURN_NEW, "master-loudnorm:verify-m4b"),
    ], "GATE_PROJECT")

    py_compile.compile(APP, doraise=True)
    py_compile.compile(PROJ, doraise=True)
    print("GATE_OK（app.py 改动需重启主服务才生效；重启前先确认无生成任务在跑）")


if __name__ == "__main__":
    main()
