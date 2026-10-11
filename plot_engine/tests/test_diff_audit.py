from plot_engine.diff_audit import summarize


def row(ch, declared, committed, changed, goal="confrontation"):
    return {"chapter": ch, "goal_type": goal, "declared": declared,
            "committed": committed, "changed": changed}


def test_counts_every_class_once():
    rows = [row(1, 0, False, False, "transition"),   # 没声明、也没开工 → 只算拒开工
            row(2, 1, True, False),                  # 提交了但状态没动
            row(3, 0, True, False),                  # 真·水章（既没声明也没动）
            row(4, 2, True, True)]                   # 正常
    out = summarize(rows)
    assert "拒开工 2 章（第 [1, 3] 章" in out
    assert "goal_type=['confrontation', 'transition']" in out
    assert "毫无变化 2 章" in out
    assert "真·水章）1 章" in out
    assert "已提交 3 章" in out


def test_all_clean_reads_zero():
    out = summarize([row(c, 1, True, True) for c in range(1, 11)])
    assert "拒开工 0 章（第 — 章" in out and "毫无变化 0 章" in out and "已提交 10 章" in out
