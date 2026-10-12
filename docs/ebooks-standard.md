# E-books 标准目录格式（v1，2026-10-12）

> 裁决来源：用户 2026-10-12——「以后每本电子书都存放到 `E-books\`，新电子书按标准格式输出文件、放进目录即可自动处理」。
> 本文就是那个**标准格式**；处理器 = `deploy/ebook_import.py`（一条命令导入整册）。

## 一、目录布局（唯一硬约定）

```
E-books/
  <书名>/                      # 如 测试书
    <册名>/                    # 如 第1册 —— 一册 = 管线里一个「书目」（slug）
      meta.json                # 必需，见 §二
      docs/                    # 需求确认文档、音色提示词等（管线不读，人读）
      output/                  # 该书的转换脚本与中间产物（converter 按书定制，允许不同）
        annotated_script.json  # 必需：转换产出的标注剧本（可嵌在 output 的任意子目录）
        script_map.json        # 强烈建议：chunk→集映射（审听/交付账本，后端不读）
```

- 处理器在 `<册名>/` 下**递归找最新修改的 `annotated_script.json`**，所以 `output/第1册/` 这种嵌套子目录合法。
- 一册对应服务器 `alexandria/projects/<slug>/` 一个书目录；同册返工（改文本重新转换后再跑处理器）就是**原位升级**，旧脚本自动备份为 `annotated_script.json.bak_<时间戳>`。

## 二、meta.json（必需字段就三个）

```json
{ "slug": "shuxue", "title": "数学公益音频小说", "volume": "第1册" }
```

`slug`：小写字母数字短横线，与 `projects.json` 对齐；新书第一次导入时处理器自动 `projects.py add <slug> --title <title>` 登记。

## 三、annotated_script.json 的合格判据（处理器逐条校验）

1. 顶层是非空数组；
2. 每条 `{"speaker": "^[A-Z][A-Z0-9_]*$", "text": 非空, "instruct": 字符串}`；
3. 文本必须是**已人工定稿的剧本标注**（`【说话人·标记】台词` 经转换得到），**禁止**把这种格式再丢给 `/import` 的 LLM 整本标注——那是给无标注小说文本用的，对剧本是破坏性重猜。

## 四、导入（= 教学时确认的「路 B」）

```
python deploy/ebook_import.py E-books/测试书/第1册      # 校验 + 落服务器
python deploy/ebook_import.py --check E-books/测试书/第1册  # 只校验（自检入口）
```

处理器做的事：登记 slug（若新书）→ 备份远端旧 `annotated_script.json/chunks.json/script_map.json` 与**共享根的 `alexandria/chunks.json`**（后端实读的是根上这份真实文件，书目录那份只是换书时的仓库——只删书目录的等于没删，2026-10-12 踩过）→ 上传新脚本 → 两处 chunks.json 都删（后端下次读取时按 `group_into_chunks` 自动重建，全部 pending）→ 两处 chunks.json 都删（后端下次读取时按 `group_into_chunks` 自动重建，全部 pending）→ **旧成品整体让位**：书目录的 `voicelines/`、`cloned_audiobook.mp3`、`audiobook.m4b`、`prooflisten.jsonl` 全部改名归档为 `*.bak_<时间戳>` 并新建空 voicelines（不归档的话，新段与旧 `voiceline_NNNN` 同索引，播放器会播着旧书的音频显示新书的文本——2026-10-12 现场踩过）→ 对照远端 `voice_config.json` 打印**未绑音色的说话人清单** → 缺 `rights.json` 时跑 `check_rights.py --init` 生成模板。

**执行前提**：确认无生成任务在跑（处理器会探测后端，活着且有任务时直接拒绝）。导入只动文件、不重启后端。

## 五、导入之后仍要人做的事（标准管不了的部分）

1. 未绑角色去声音实验室按提示词造声 `选用`（绑定即 `type: clone`）；未绑角色的段落生成会失败，保持 pending 无害。
2. `rights.json` 必须人工填实（三判据 + 合同凭证），`check_rights.py` 不过关 → 不接单不生成母带。
3. 集边界信息在 `script_map.json`，审听/交付按它对号，后端 chunk 里没有集号。

## 六、「自动处理」的边界（ponytail 声明）

当前形态 = **放文件进目录，跑一条 `ebook_import.py`**。目录监听器（扫到新书自动导入）没有做——一本书时是 YAGNI，等第二本真书进来且嫌手敲烦再加。
