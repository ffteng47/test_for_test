"""add_script_context — 给远程 generate_script.py 打“三层记忆注入”补丁（幂等）。

在 `system_prompt = prompts_config.get(...) or DEFAULT_SYSTEM_PROMPT` 之后插入：
若 script_context.json 存在（由 backend/context_manager.py --write 产出，位于工作区根
或 app/ 上级），把其 block 追加进 system prompt。找不到文件时行为完全不变。

用法（在 3090 上）： python3 add_script_context.py   # 需 app/generate_script.py 相对路径可解析
"""
import os
import shutil

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'generate_script.py')

ANCHOR = '    system_prompt = prompts_config.get("system_prompt") or DEFAULT_SYSTEM_PROMPT\n'
INJECT = ANCHOR + '''    # [novel-studio] 三层记忆注入：context_manager.py 产出的项目设定块（无文件时零影响）
    for _ctx_p in (MARK, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", MARK)):
        if os.path.exists(_ctx_p):
            with open(_ctx_p, encoding="utf-8") as _ctx_f:
                system_prompt += "\\n\\n【项目设定（Story Bible·角色·章节状态）】\\n" + json.load(_ctx_f)["block"]
            break
'''.replace('MARK', "'script_context.json'")


def main() -> None:
    with open(TARGET, encoding='utf-8') as f:
        src = f.read()
    if 'novel-studio] 三层记忆注入' in src:
        print('ALREADY PATCHED:', TARGET)
        return
    if src.count(ANCHOR) != 1:
        raise SystemExit(f'anchor 出现 {src.count(ANCHOR)} 次，上游版本已变，人工确认后再插')
    shutil.copy(TARGET, TARGET + '.bak_pre_ctx')
    with open(TARGET, 'w', encoding='utf-8') as f:
        f.write(src.replace(ANCHOR, INJECT))
    import py_compile
    py_compile.compile(TARGET, doraise=True)
    print('PATCHED + COMPILED:', TARGET)


if __name__ == '__main__':
    main()
