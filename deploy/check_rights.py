r"""接单闸门 ③：权利台账（post-production-plan.md §M5 / monetization-wiki §13 缺口 5）。

卖的是产出，不是软件——但「委托方担保权利」这句话只有落到一张填完的表上才成立。
这里补的是 §14 闸门 A（文本三权利）+ §15 声纹风险（克隆声线单独授权）+ AI 朗读披露，
三样原来「完全空白」的东西各有一处落库。

落库位置：`alexandria/projects/<slug>/rights.json`，和 `delivery_report.json` 同级
（`projects.json` 的 `active` 是唯一认书入口，同 `add_prooflisten.py` 的结论：
`chunks.json` 在共享根上是真文件，不能靠 `realpath(CHUNKS_PATH)` 反查）。

只读检查器，不改后端、不需要重启：
    alexandria/venv/bin/python deploy/check_rights.py            # 查当前 active 书
    alexandria/venv/bin/python deploy/check_rights.py --slug shuxue
写模板（已存在的字段一个都不动）：
    alexandria/venv/bin/python deploy/check_rights.py --slug 新书 --init

判据三条，缺任一条不开工（退出码 1）：
  1. 文本权利：`原文来源` 不是网盘/转载口径，且 `改编权 / 信息网络传播权 / 声音表演` 三项都 true，
     `担保` 写明书面 + 侵权自担，`合同` 给了凭证文件名。
  2. 声线来源：`voice_config.json` 里每个 `type == "clone"` 的角色都要在 `声线来源` 里有对应行，
     `来源` ∈ {自研音色, 授权样本}。实测这本书 8 个角色的参考音频全是 `designed_voices/*_preview.wav`
     （persona 那一步造的，不是真人），所以 `自研音色` 是合法答案——但参考音频落在
     `designed_voices/` 之外却按「自研」填的，直接拦；`授权样本` 必须 `商用=true` 且有 `凭证`。
  3. AI 朗读披露：`披露.声明文本` 非空（导出的 M4B 元数据 `演播 AI · Qwen3-TTS` 只是对内标记，
     对外还得有一份能贴进详情页的文本）。
"""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):  # 中文台账在 Windows GBK 控制台上会直接编码崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))


def _app_root():
    """兼容两种摆法：仓库里的 `deploy/`（同级有 alexandria/）与线上的 `alexandria/deploy_patches/`。"""
    for cand in (os.path.join(_HERE, "alexandria"), os.path.join(_HERE, "..", "alexandria"),
                 os.path.join(_HERE, "..")):
        if os.path.exists(os.path.join(cand, "projects.json")):
            return os.path.abspath(cand)
    return os.path.abspath(os.path.join(_HERE, "..", "alexandria"))


APP = _app_root()
PROJECTS_JSON = os.path.join(APP, "projects.json")
PROJECTS_DIR = os.path.join(APP, "projects")
RIGHTS = "rights.json"

# 一眼就能认出来的「没有权利可言」的来源口径，出现即拦（子串匹配，写清出处比写「其他」有用）
DIRTY_SOURCE = ("网盘", "夸克", "quark", "转载", "爬取", "抓取", "无出处", "未知")

TEXT_RIGHTS = ("改编权", "信息网络传播权", "声音表演")

TEMPLATE = {
    "书名": "",
    "客户": {
        "名称": "",
        "联系人": "",
        "联系方式": "",
        "合同": "委托制作合同_<客户>_<书名>.pdf",
        "权利担保": {
            "书面担保": False,
            "侵权自担": False,
            "文本": "委托方声明其持有原文的改编权、信息网络传播权与声音表演权，"
                    "并保证上述权利无瑕疵；因权利瑕疵产生的纠纷与损失由委托方承担。",
        },
    },
    "原文来源": {
        "途径": "",              # 委托方自有 / 签约原创 / 公版
        "作者与逝世纪年": "",     # 走公版才填，例：鲁迅（1936 逝，满 50 年）
        "凭证": "",              # 授权书或公版判据的文件名
    },
    "文本权利": {k: False for k in TEXT_RIGHTS},
    "声线来源": [
        {
            "角色": "",
            "类型": "",           # design / custom / clone，与 voice_config.json 对齐
            "来源": "",           # 自研音色 / 授权样本
            "商用": False,
            "凭证": "",
        }
    ],
    "披露": {
        "声明文本": "本有声书由 AI 合成朗读，无真人演播。",
        "标注位置": ["M4B 元数据 narrator", "商品详情页", "母带开头 3 s 内"],
    },
    "记录": {"填写人": "", "填写日期": "", "复核": ""},
}


def _enc():
    return dict(encoding="utf-8")


def load_json(path):
    try:
        with open(path, **_enc()) as f:
            return json.load(f)
    except Exception:
        return None


def active_slug():
    reg = load_json(PROJECTS_JSON) or {}
    return reg.get("active") or ""


def book_dir(slug):
    # 和 add_prooflisten.py 同一个唯一入口：projects.json 的 active，不做软链反查
    return os.path.join(PROJECTS_DIR, slug)


def clone_roles(cfg):
    """`voice_config.json` 里用了克隆声线的角色：`[(角色, 参考音频, 是否自研设计音色)]`。
    线上是 `{角色: {type, ref_audio, ...}}`，老的 mock/接口摆法是 `{voices: [{name, config:{type}}]}`
    —— 两种都认，别在这里猜第三种。
    实测口径（2026-10-11，`projects/shuxue/voice_config.json` 8 个角色全 `type=clone`）：
    参考音频一律是 `designed_voices/*_preview.wav`，即 persona 那一步自己造出来的音色，
    不是真人声纹。落在 `designed_voices/` 之外的一律按「拿了别人的声音」处理。"""
    rows = cfg.get("voices") if isinstance(cfg, dict) and "voices" in cfg else cfg
    if isinstance(rows, dict):
        items = list(rows.items())
    else:
        items = [(v.get("name") or (v.get("config") or {}).get("name"), v) for v in rows or [] if isinstance(v, dict)]
    out = []
    for name, v in items:
        conf = v.get("config") or v
        if name and conf.get("type") == "clone":
            ref = str(conf.get("ref_audio") or "")
            out.append((name, ref, "designed_voices/" in ref.replace("\\", "/")))
    return out


def check(d, cfg):
    bad, warn = [], []
    if not isinstance(d, dict):
        return [f"缺 {RIGHTS}：接单前必须填完权利台账"], []

    src = json.dumps(d.get("原文来源", {}), ensure_ascii=False)
    dirty = [k for k in DIRTY_SOURCE if k in src]
    if dirty:
        bad.append(f"原文来源含「{'、'.join(dirty)}」：这类文本上架即下架，拿它做样音是营利性侵权")
    担保 = (d.get("客户") or {}).get("权利担保") or {}
    if not 担保.get("书面担保"):
        bad.append("客户书面担保缺失")
    if not 担保.get("侵权自担"):
        bad.append("侵权自担条款缺失")
    if not (d.get("客户") or {}).get("合同"):
        bad.append("合同凭证文件名为空")

    rights = d.get("文本权利") or {}
    miss = [k for k in TEXT_RIGHTS if rights.get(k) is not True]
    if miss:
        bad.append(f"文本权利未取证：{'、'.join(miss)}")

    rows = d.get("声线来源") or []
    by_role = {r.get("角色"): r for r in rows if isinstance(r, dict)}
    for name, ref, self_made in clone_roles(cfg):
        r = by_role.get(name)
        if not r:
            bad.append(f"克隆声线「{name}」没有来源行")
            continue
        if r.get("来源") not in ("自研音色", "授权样本"):
            bad.append(f"克隆声线「{name}」来源未填（自研音色 / 授权样本）")
        elif r["来源"] == "自研音色" and not self_made:
            bad.append(f"克隆声线「{name}」参考音频不是 designed_voices 产物，却按自研填写：{ref or '（空）'}")
        elif r["来源"] == "授权样本" and (not r.get("商用") or not r.get("凭证")):
            bad.append(f"克隆声线「{name}」缺商用授权凭证")
        elif r["来源"] == "自研音色" and not r.get("凭证"):
            warn.append(f"克隆声线「{name}」未记自研凭证（填 `designed_voices/` 那个预览文件名，证明它不是真人）")

    disc = (d.get("披露") or {}).get("声明文本")
    if not disc or not str(disc).strip():
        bad.append("AI 朗读声明文本为空")

    if not (d.get("记录") or {}).get("复核"):
        warn.append("台账未复核（首单建议法务过一遍再开工）")
    return bad, warn


def emit(slug, d, bad, warn):
    book = (d or {}).get("书名") or slug or "未填"
    print(f"权利台账 · {book}")
    print(f"客户 {(d or {}).get('客户', {}).get('名称') or '—'} · 合同 {(d or {}).get('客户', {}).get('合同') or '—'}")
    src = (d or {}).get("原文来源") or {}
    print(f"原文来源 {src.get('途径') or '—'} · 凭证 {src.get('凭证') or '—'}")
    for line in bad:
        print(f"  ✕ {line}")
    for line in warn:
        print(f"  ! {line}")
    if not bad:
        print("  ✓ 三条判据齐：文本权利 / 克隆声线来源 / AI 朗读披露")
    print(f"→ {'不开工' if bad else '可开工'}")
    return 1 if bad else 0


def write_template(dirpath):
    path = os.path.join(dirpath, RIGHTS)
    if os.path.exists(path):
        print(f"SKIP {path}（已存在，不覆盖）")
        return
    os.makedirs(dirpath, exist_ok=True)
    with open(path, "w", **_enc()) as f:
        json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"WROTE {path}（填完再跑 check）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="", help="缺省取 projects.json 的 active")
    ap.add_argument("--init", action="store_true", help="写空模板，不覆盖已有台账")
    ap.add_argument("--demo", action="store_true", help="自检：网盘文本 + 无来源克隆声线，必须判 FAIL")
    a = ap.parse_args()

    if a.demo:
        # 负例：网盘文本 + 一个外录参考音频的克隆声线，没有任何授权
        cfg = {"NARRATOR": {"type": "clone", "ref_audio": "sample/真人样本.wav"}}
        dirty = {"书名": "鬼吹灯", "原文来源": {"途径": "夸克网盘"}, "客户": {},
                 "文本权利": {}, "声线来源": [], "披露": {}}
        bad, _ = check(dirty, cfg)
        print("DEMO FAILS:", len(bad))
        for line in bad:
            print("  ✕", line)
        ok = len(bad) == 7
        clean = json.loads(json.dumps(TEMPLATE))
        clean.update({"书名": "公版样本", "原文来源": {"途径": "公版", "凭证": "公版判据.pdf"},
                      "客户": {"名称": "某出版社", "合同": "合同.pdf",
                              "权利担保": {"书面担保": True, "侵权自担": True}},
                      "文本权利": {k: True for k in TEXT_RIGHTS},
                      "声线来源": [{"角色": "NARRATOR", "类型": "clone", "来源": "自研音色",
                                    "商用": True, "凭证": "designed_voices/narrator_preview.wav"}],
                      "披露": {"声明文本": "本有声书由 AI 合成朗读。"},
                      "记录": {"复核": "法务"}})
        bad2, warn2 = check(clean, {"NARRATOR": {"type": "clone",
                                                "ref_audio": "designed_voices/narrator_preview.wav"}})
        print("DEMO CLEAN:", "pass" if not bad2 else f"FAIL {bad2}")
        # 冒名顶替：外录样本按「自研音色」填，必须被拦
        bad3, _ = check(clean, cfg)
        print("DEMO SPOOF:", "caught" if any("不是 designed_voices" in b for b in bad3) else f"MISSED {bad3}")
        ok = ok and not bad2 and any("不是 designed_voices" in b for b in bad3)
        print("SELF-CHECK:", "OK" if ok else "BROKEN")
        return 0 if ok else 1

    slug = a.slug or active_slug()
    if not slug:
        print("认不出是哪本书：projects.json 没有 active，且没给 --slug")
        return 1
    dirpath = book_dir(slug)
    if a.init:
        write_template(dirpath)
        return 0
    d = load_json(os.path.join(dirpath, RIGHTS))
    cfg = load_json(os.path.join(dirpath, "voice_config.json")) or {}
    return emit(slug, d, *check(d, cfg))


if __name__ == "__main__":
    sys.exit(main())
