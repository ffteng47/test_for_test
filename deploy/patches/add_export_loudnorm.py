# 导出母带后期安装器（幂等）：把响度归一接进两条导出链路。
#
# 修的真问题：`merge_audio`（MP3）与 `merge_m4b`（M4B）都只做 concat + 转码，
# 没有任何响度处理。实测现有成品 `projects/shuxue/audiobook.m4b` 为
# −23.25 LUFS / −1.18 dBTP —— 比流媒体标准轻 7 dB 且峰值超标，两项都不合格。
#
# 阈值与判定不在这里定义，唯一真源是 `backend/master_audio.py`（按既有映射
# backend/*.py → alexandria/backend/*.py 部署，本安装器只检查它在不在）。
#
# 跑法（在服务器上，用 alexandria 的 venv）：
#   alexandria/venv/bin/python deploy/patches/add_export_loudnorm.py
# 跑完必须重启主服务才生效（sidecar 不用动）。

import os
import py_compile
import sys

BASE = "/home/tff/software/novel-audiobook/alexandria/app"
PROJ = os.path.join(BASE, "project.py")
MASTER = os.path.join(os.path.dirname(BASE), "backend", "master_audio.py")

VERIFY = '''    def _verify_delivery(self, output_path, expect_chapters=0):
        """机检最后一道：对**真正交出去的文件**复判，就地改写 delivery_report.json。

        `_normalize_master` 量的是归一后的中间 WAV，章节标记和最终体积是后面那次编码才产生的。
        判据全在 backend/master_audio.py，这里只接线。量不了＝不合格，不留中间态的「通过」。
        """
        import os as _os, sys as _sys
        _bk = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "backend")
        if _bk not in _sys.path:
            _sys.path.insert(0, _bk)
        try:
            from master_audio import finalize
            rep = finalize(output_path, expect_chapters)
            v = rep["全项实测"]
            print(("成品机检 OK：%s LUFS / %s dBTP / %s 章" % (v["LUFS"], v["真峰值dBTP"], v["章节数"]))
                  if rep["通过"] else f"!! 成品机检不通过（不要交付）：{rep['验收']}")
        except Exception as exc:
            print(f"!! 成品机检没跑成，按不合格处理：{exc}")
            try:
                import json as _json
                rp = _os.path.join(_os.path.dirname(_os.path.realpath(output_path)), "delivery_report.json")
                with open(rp, "w", encoding="utf-8") as f:
                    _json.dump({"错误": str(exc), "验收": {"机检未执行": False}, "通过": False},
                               f, ensure_ascii=False, indent=2)
            except OSError:
                pass


'''

METHOD = '''    def _normalize_master(self, final_audio, output_path):
        """交付级母带后期：响度归一 + 真峰值限制，并把 delivery_report.json 落在成品旁边。

        阈值与验收判定全在 backend/master_audio.py，这里只负责接线，不复述标准。
        失败时原样返回并在日志里显式留痕——归一没做，成品就不合格，绝不能静默当合格品交出去。
        """
        import json as _json
        import os as _os
        import sys as _sys

        _bk = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "backend")
        if _bk not in _sys.path:
            _sys.path.insert(0, _bk)

        # root_dir 是多本书共用的软链根，写那儿换书就被覆盖、书名也认不出。
        # 以本次成品的真实目录为准：软链会解析到 projects/<slug>/，非软链安装则退回 root_dir。
        book_dir = _os.path.dirname(_os.path.realpath(output_path))
        pre = _os.path.join(book_dir, "temp_master_pre.wav")
        norm = _os.path.join(book_dir, "temp_master_norm.wav")
        try:
            from master_audio import normalize
            final_audio.export(pre, format="wav")
            report = normalize(pre, norm)
            report["书"] = _os.path.basename(book_dir)
            with open(_os.path.join(book_dir, "delivery_report.json"),
                      "w", encoding="utf-8") as f:
                _json.dump(report, f, ensure_ascii=False, indent=2)
            if not report["通过"]:
                print(f"!! 母带后期未达标（不要交付）：{report['验收']}")
            else:
                print(f"母带后期 OK：{report['输出LUFS']} LUFS / {report['输出真峰值dBTP']} dBTP")
            # ponytail: 这里多写一次临时 WAV 再读回内存，省不掉是因为两条导出路都要
            # pydub 对象；要省就改成返回路径、由调用方直接喂 ffmpeg。
            return AudioSegment.from_file(norm)
        except Exception as exc:
            # 归一崩了也要留一份不合格报告：前端只认 delivery_report.json，
            # 缺文件会被读成「未机检」，看不出来是「这台没跑过」还是「刚崩了、成品不合格」。
            try:
                with open(_os.path.join(book_dir, "delivery_report.json"),
                          "w", encoding="utf-8") as f:
                    _json.dump({"书": _os.path.basename(book_dir), "错误": str(exc),
                                "验收": {"母带后期执行失败": False}, "通过": False},
                               f, ensure_ascii=False, indent=2)
            except OSError:
                pass
            print(f"!! 母带后期执行失败，成品未归一（不要交付）：{exc}")
            return final_audio
        finally:
            for _t in (pre, norm):
                if _os.path.exists(_t):
                    try:
                        _os.remove(_t)
                    except OSError:
                        pass


''' + VERIFY

MP3_OLD = '        final_audio.export(output_path, format="mp3")'
MP3_NEW = ('        # master-loudnorm:mp3\n'
           '        final_audio = self._normalize_master(final_audio, output_path)\n'
           + MP3_OLD + '\n'
           '        # master-loudnorm:verify-mp3\n'
           '        self._verify_delivery(output_path)\n')

WAV_OLD = '            final_audio.export(temp_wav, format="wav")'
WAV_NEW = ('            # master-loudnorm:m4b\n'
           '            final_audio = self._normalize_master(final_audio, output_path)\n'
           + WAV_OLD)

M4B_RETURN_OLD = '        return True, "audiobook.m4b"'
M4B_RETURN_NEW = ('        # master-loudnorm:verify-m4b\n'
                  '        self._verify_delivery(output_path, len(chapters))\n'
                  + M4B_RETURN_OLD)

M4B_ANCHOR = "    def merge_m4b(self, per_chunk_chapters=False, metadata=None):"


def patch(path, pairs, tag):
    """pairs: (old, new, marker)。marker 已存在则跳过该条。每个改动点 marker 必须唯一，
    否则第一条打上后其余锚点会被误判为已完成。"""
    src = open(path, encoding="utf-8").read()
    changed = False
    for old, new, marker in pairs:
        if marker in src:
            continue
        assert old in src, f"{tag}: anchor missing -> {old[:80]!r}"
        assert src.count(old) == 1, f"{tag}: anchor not unique -> {old[:80]!r}"
        src = src.replace(old, new, 1)
        changed = True
    if not changed:
        print(f"{tag}: ALREADY")
        return
    open(path, "w", encoding="utf-8").write(src)
    print(f"{tag}: PATCHED")


def main():
    if not os.path.exists(MASTER):
        print(f"MISSING {MASTER}\n先把 backend/master_audio.py 部署过去（它才是阈值的唯一真源）。")
        sys.exit(1)

    src = open(PROJ, encoding="utf-8").read()
    if "master-loudnorm:mp3" in src and "master-loudnorm:m4b" in src \
            and "def _normalize_master" in src:
        print("LOUDNORM_PATCH_ALREADY")
        return

    backup = PROJ + ".bak_pre_loudnorm"
    if not os.path.exists(backup):
        import shutil
        shutil.copy(PROJ, backup)
        print(f"BACKUP {backup}")

    patch(PROJ, [
        (M4B_ANCHOR, METHOD + M4B_ANCHOR, "def _normalize_master"),
        (MP3_OLD, MP3_NEW, "master-loudnorm:mp3"),
        (WAV_OLD, WAV_NEW, "master-loudnorm:m4b"),
        (M4B_RETURN_OLD, M4B_RETURN_NEW, "master-loudnorm:verify-m4b"),
    ], "EXPORT_LOUDNORM")

    py_compile.compile(PROJ, doraise=True)
    print("LOUDNORM_PATCH_OK（后端改动，需重启主服务才生效；重启前先确认无生成任务在跑）")


if __name__ == "__main__":
    main()
