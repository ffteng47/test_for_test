# 修复已部署的母带后期接线：验收报告落错目录（幂等）。
#
# 修的真问题：`root_dir` 是多本书共用的软链根，交付物才是指向 `projects/<slug>/` 的软链。
# 原接线把 `delivery_report.json` 和两个临时 WAV 写在 `root_dir` 上，于是
#   1. 报告落在共享根，换一本书就被覆盖，给客户的验收单留不住；
#   2. `report["书"]` 恒为 "alexandria"，认不出是哪本书。
# 真跑一遍 /api/merge 才发现（2026-10-11）。
#
# 修法是让 `_normalize_master` 收到本次成品的 output_path，报告和临时文件写到它的真实目录
# （软链解析到 projects/<slug>/；非软链安装退回原行为）。两条导出路各自的 output_path
# 都已在上文定义，接线点不用新增变量。
#
# 为什么单开一个安装器：新装的机器直接用修好的 `add_export_loudnorm.py` 就是对的；
# 已经打过接线的机器上它会打印 LOUDNORM_PATCH_ALREADY 什么都不改，所以旧机器跑这份。
# 本安装器的锚点对应 2026-10-11 线上那份代码，其它历史版本会 assert 报错而不是瞎改。
#
# 跑法（服务器上，alexandria 的 venv）：
#   cd alexandria/deploy_patches && venv/bin/python fix_master_report_dir.py
# 后端改动，跑完必须重启主服务才生效（重启前先确认无生成任务在跑）。

import os
import py_compile

from add_export_loudnorm import PROJ, patch

PAIRS = [
    ('    def _normalize_master(self, final_audio):',
     '    def _normalize_master(self, final_audio, output_path):',
     'def _normalize_master(self, final_audio, output_path)'),

    ('        root = _os.path.realpath(self.root_dir)\n'
     '        pre = _os.path.join(root, "temp_master_pre.wav")\n'
     '        norm = _os.path.join(root, "temp_master_norm.wav")',
     '        book_dir = _os.path.dirname(_os.path.realpath(output_path))\n'
     '        pre = _os.path.join(book_dir, "temp_master_pre.wav")\n'
     '        norm = _os.path.join(book_dir, "temp_master_norm.wav")',
     'book_dir = _os.path.dirname(_os.path.realpath(output_path))'),

    ('            report["书"] = _os.path.basename(root)\n'
     '            with open(_os.path.join(root, "delivery_report.json"),',
     '            report["书"] = _os.path.basename(book_dir)\n'
     '            with open(_os.path.join(book_dir, "delivery_report.json"),',
     'report["书"] = _os.path.basename(book_dir)'),

    ('        # master-loudnorm:mp3\n'
     '        final_audio = self._normalize_master(final_audio)',
     '        # master-loudnorm:mp3\n'
     '        final_audio = self._normalize_master(final_audio, output_path)',
     'master-loudnorm:mp3\n        final_audio = self._normalize_master(final_audio, output_path)'),

    ('            # master-loudnorm:m4b\n'
     '            final_audio = self._normalize_master(final_audio)',
     '            # master-loudnorm:m4b\n'
     '            final_audio = self._normalize_master(final_audio, output_path)',
     'master-loudnorm:m4b\n            final_audio = self._normalize_master(final_audio, output_path)'),
]


def main():
    src = open(PROJ, encoding="utf-8").read()
    if "def _normalize_master" not in src:
        print(f"{PROJ} 里还没有母带后期接线，先跑 add_export_loudnorm.py。")
        raise SystemExit(1)

    backup = PROJ + ".bak_pre_report_dir_fix"
    if not os.path.exists(backup):
        import shutil
        shutil.copy(PROJ, backup)
        print(f"BACKUP {backup}")

    patch(PROJ, PAIRS, "REPORT_DIR_FIX")
    py_compile.compile(PROJ, doraise=True)
    print("REPORT_DIR_FIX_OK（后端改动，需重启主服务才生效；重启前先确认无生成任务在跑）")


if __name__ == "__main__":
    main()
