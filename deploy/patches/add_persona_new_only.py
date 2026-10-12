# 批量自动设计支持「仅未绑定」：/api/generate_personas 请求体加 new_only，转发 --new-only。
# 用法（服务器上）：cd alexandria && venv/bin/python deploy_patches/add_persona_new_only.py
# 幂等：app.py 已含 new_only 则 TAG_ALREADY。装完需重启 app.py。
import os
import py_compile
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.path.join(BASE, ".."))
TARGET = os.path.join(APP, "app", "app.py")

ANCHORS = [
    ("class GeneratePersonasRequest(BaseModel):\n    advanced: bool = False\n",
     "class GeneratePersonasRequest(BaseModel):\n    advanced: bool = False\n    new_only: bool = False\n"),
    ('    command = [sys.executable, "-u", "generate_personas.py"]\n',
     '    command = [sys.executable, "-u", "generate_personas.py"]\n    if request.new_only:\n        command.append("--new-only")\n'),
]


def main():
    src = open(TARGET, encoding="utf-8").read()
    if "new_only" in src:
        print("TAG_ALREADY")
        return
    for old, new in ANCHORS:
        if src.count(old) != 1:
            raise SystemExit(f"锚点失配（{src.count(old)} 处）: {old[:60]!r}")
        src = src.replace(old, new)
    shutil.copy(TARGET, TARGET + ".bak_pre_persona_new_only")
    open(TARGET, "w", encoding="utf-8").write(src)
    py_compile.compile(TARGET, doraise=True)
    print("OK generate_personas 支持 new_only（备份 .bak_pre_persona_new_only），重启 app.py 生效")


if __name__ == "__main__":
    main()
