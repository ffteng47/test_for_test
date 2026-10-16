# patch-v2 归因机检（S 批条件②/③取证，报告 §14 表的生成脚本）
# 口径：稳定死项 vs 终轮 Proposals，逐批复跑。仓库根目录运行：
#   PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe sampling/forensic_patchv2_attribution.py
import re

# (ch, actor, field, fact, expected) 稳定死项（两代六批同判面，ch02/03/04/06/10）
checks = {
    2:  ("char_000003", "belief", "fact_000008", "believes"),
    3:  ("char_000001", "knowledge", "fact_000006", "believed"),
    4:  ("char_000003", "knowledge", "fact_000007", "known"),
    6:  ("char_000004", "knowledge", "fact_000010", "known"),
    10: ("char_000001", "knowledge", "fact_000002", "believed"),
}
# 档位表与 plot_engine/models/contract.py 的 K_RANK/KNOWLEDGE_RANK_CAP、
# reducers/belief.py 的 B_RANK 逐字同值（单源表的手抄镜像，改码面须同步改这里）。
KNOW_IMPL = {"OBSERVES": "known", "READS": "known", "IS_TOLD": "believed", "INFERS": "suspected"}
BEL = {"BELIEVES": "believes", "SUSPECTS": "suspects", "DOUBTS": "doubts"}
K = {"unknown": 0, "suspected": 1, "believed": 2, "known": 3, "confirmed": 4}
B = {"doubts": 0, "suspects": 1, "believes": 2}

for N in (1, 2, 3):
    print(f"== r{N}")
    for ch, (actor, field, fact, exp) in checks.items():
        path = f"sampling/ep1v39pv2-r{N}/ch{ch:02d}.md"
        txt = open(path, encoding="utf-8").read()
        m = re.search(r"## Proposals\n(.*?)(\n## |\Z)", txt, re.S)  # 最终 Proposals 段
        props = m.group(1) if m else ""
        hits = []
        for line in props.splitlines():
            pm = re.match(r"- (\w+) actor=(\S+).*payload=(\{.*\})", line)
            if not pm:
                continue
            et, ac = pm.group(1), pm.group(2)
            if ac != actor:
                continue
            if f"'{fact}'" not in pm.group(3):
                continue
            if field == "knowledge" and et in KNOW_IMPL:
                hits.append(f"达档 {et}" if K[KNOW_IMPL[et]] >= K[exp]
                            else f"型别偷懒 {et}(上限{KNOW_IMPL[et]})")
            if field == "belief" and et in BEL:
                hits.append(f"达档 {et}" if B[BEL[et]] >= B[exp]
                            else f"档位不足 {et}(上限{BEL[et]})")
        # 「疑错绑」判型口径：该 actor 对该 fact 无实现事件（hits 空）且
        # Proposals 里别的 actor 行出现了这个 fact ⇒ 标「疑似错绑他人」。
        # 严格说是「没写 + 该 fact 在别处被写过」，不构成绑定的直接证明。
        wrong_actor = any(f"actor=" in l and fact in l and actor not in l
                          for l in props.splitlines() if re.match(r"- \w+ actor=", l))
        print(f"  ch{ch:02d} {field}/{fact}->{exp}@{actor}: "
              f"{hits or '无实现事件'}{'｜疑似错绑他人' if (not hits and wrong_actor) else ''}")
