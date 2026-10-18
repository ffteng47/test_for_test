"""L3 轻档单测（批1-2，tff 2026-10-18 放行）。

口径锚全部来自人核台账（pack §7.9/§7.10）：章首豁免/意图≠离开/到达消解/
认识论配对标签/逐字重复块/ch50 三锚回归闸（集成）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plot_engine.l3.duplication import find_dup_runs
from plot_engine.l3.fact_intervals import extract_statements, project_intervals
from plot_engine.l3.interval_conflicts import (find_interval_conflicts,
                                               find_statement_conflicts)
from plot_engine.l3.scene_index import build_scene_index, strip_comments
from plot_engine.l3.temporal_checks import (find_entry_without_source,
                                            find_space_rewind)
from plot_engine.l3.triggers import run_light


class TestSceneIndex:
    def test_comment_lines_stripped_with_mapping(self):
        body = ["正文一", "<!-- hook: cliffhanger -->", "", "正文二"]
        kept, mapping = strip_comments(body)
        assert kept == ["正文一", "正文二"]
        assert mapping == [1, 4]

    def test_chapter_open_presence_exempt(self):
        body = ["藏宝阁内，赵六独自值守，翻着账簿。", "他抬头吹灭了油灯。"]
        frames = build_scene_index(1, body)
        assert find_entry_without_source(frames) == []

    def test_arrival_clears_entry(self):
        body = ["藏宝阁内，赵六独自值守。", "门被推开，张三走了进来。", "两人对坐。"]
        frames = build_scene_index(1, body)
        assert find_entry_without_source(frames) == []
        assert "张三" in frames[0].arrived

    def test_mid_chapter_entry_without_source_fires(self):
        # 人核口径：章中场景硬切后无到达=真（#09/#29 形态）
        body = ["藏宝阁内，赵六独自值守，翻着账簿。", "次日，书房里张三翻阅卷宗。"]
        frames = build_scene_index(1, body)
        cands = find_entry_without_source(frames)
        assert len(cands) == 1 and cands[0].family == "A"
        assert "张三" in cands[0].detail

    def test_intent_depart_not_counted(self):
        # ch20 #22 误报教训：「准备离开」≠离开
        body = ["藏宝阁内，王五收拾物品，准备离开藏宝阁。", "张三推门而入。", "王五又坐下研究账册。"]
        frames = build_scene_index(1, body)
        assert frames[0].departed == []
        assert find_space_rewind(frames) == []

    def test_space_rewind_fires_and_arrival_clears(self):
        body = ["藏宝阁内，张三翻着账簿。", "他转身离开藏宝阁。",
                "后院中，王五独自饮酒。", "藏宝阁内，张三又翻起账簿。"]
        frames = build_scene_index(1, body)
        cands = find_space_rewind(frames)
        assert len(cands) == 1 and cands[0].family == "B"
        body2 = body[:3] + ["张三推开藏宝阁的门，走了进来。", "藏宝阁内，张三又翻起账簿。"]
        frames2 = build_scene_index(1, body2)
        assert find_space_rewind(frames2) == []


class TestStatements:
    def test_count_conflict_narrator_pair(self):
        body = ["藏宝阁的钥匙只有一把，一直由赵六保管。",
                "次日，书房里张三翻阅卷宗。",
                "藏宝阁的钥匙一共有两把，另一把在长老那里。"]
        ss = extract_statements(1, body)
        cands = find_statement_conflicts(ss)
        assert any(c.rule_id == "statement_value_conflict" and c.family == "C"
                   and c.epistemic_pair == "narrator_narrator" for c in cands)

    def test_epistemic_pair_tags(self):
        body = ["藏宝阁的钥匙只有一把，一直由赵六保管。",
                "张三低声道：“钥匙一共有两把。”"]
        ss = extract_statements(1, body)
        assert {s.epistemic for s in ss} == {"narrator", "dialogue"}
        cands = find_statement_conflicts(ss)
        assert cands and cands[0].epistemic_pair == "dialogue_narrator"

    def test_speculation_tagged(self):
        body = ["王五觉得钥匙大概有两把，心中隐隐不安。"]
        ss = extract_statements(1, body)
        assert ss and ss[0].epistemic == "speculation"

    def test_interval_projection_supersede_keeps_rows(self):
        body1 = ["藏宝阁的钥匙只有一把，一直由赵六保管。"]
        body2 = ["藏宝阁的钥匙一共有两把，另一把在长老那里。"]
        ss = extract_statements(1, body1) + extract_statements(2, body2)
        ivs = project_intervals(ss)
        counts = [i for i in ivs if i.predicate == "key_count"]
        assert len(counts) == 2                    # expire 不删行
        assert counts[0].valid_until == 1          # 被 ch2 新取值顶替=上一章失效
        assert any(i.predicate == "key_custody" for i in ivs)  # custody 独立建区间
        assert find_interval_conflicts(ivs) == []  # 顶替后区间不重叠=无跨章冲突

    def test_interval_overlap_conflict(self):
        from plot_engine.l3.models import IntervalFact
        a = IntervalFact(subject="钥匙", predicate="key_custody", object="赵六",
                         valid_from=1, valid_until=None, source_chapter=1,
                         evidence_ref="ch01:1-1")
        b = IntervalFact(subject="钥匙", predicate="key_custody", object="长老",
                         valid_from=2, valid_until=None, source_chapter=2,
                         evidence_ref="ch02:1-1")
        cands = find_interval_conflicts([a, b])
        assert len(cands) == 1 and cands[0].rule_id == "interval_overlap_conflict"


class TestDuplication:
    def test_verbatim_run_detected(self):
        blk = ["张三坐在书房里，桌上摊着几张与案情相关的文件，心里想着近来发生的事。",
               "他回忆起李四与外客在山下会饮的情景，那个夜晚月光洒在山脚下。",
               "每一个细节都可能成为破案的关键，他深知现在正是挖掘真相的关键时刻。"]
        body = blk + ["过渡一句。"] + blk
        cands = find_dup_runs(body, chapter=1)
        assert len(cands) == 1 and cands[0].family == "D"

    def test_short_lines_ignored(self):
        body = ["好。", "走。", "好。", "走。", "好。", "走。"]
        assert find_dup_runs(body, chapter=1) == []


CH50 = Path(__file__).resolve().parents[2] / "sampling" / "wpe50ch" / "ch50.md"


@pytest.mark.skipif(not CH50.exists(), reason="wpe50ch 语料不在本机")
class TestCh50Regression:
    """批2 回归闸：ch50 三锚候选必须全中（pack §1.1 锚定义）。"""

    def _body(self):
        from plot_engine.metrics import _section_body
        return _section_body(CH50.read_text(encoding="utf-8", errors="replace").splitlines(),
                             "Draft")

    def test_three_anchors_all_fire(self):
        cands = run_light(50, self._body())
        fams = {c.family for c in cands}
        assert {"A", "B", "C"} <= fams, f"ch50 掉锚：只中 {fams}"

    def test_no_dup_false_fire(self):
        cands = run_light(50, self._body())
        assert not [c for c in cands if c.family == "D"]


class TestExtractorV2:
    """抽取层 v2 四条修复（tff 2026-10-18 立项规格）。"""

    def test_dialogue_mention_not_presence(self):
        # 修复①：台词提及行不造在场帧——李四型提及不算在场，不产 A 候选。
        body = ["藏宝阁内，赵六独坐。", "张三皱眉：「可是李四那晚却在山下与外客饮酒？」"]
        frames = build_scene_index(1, body)
        assert all("李四" not in fr.present for fr in frames)
        assert not [c for c in find_entry_without_source(frames) if "李四" in c.detail]

    def test_mid_scene_entry_backfilled(self):
        # 修复②：章首豁免收窄到首行；场景内后段凭空在场（张三型）照算 A，证据=在场行。
        body = ["藏宝阁内只剩赵六一人，他守着灯火。", "烛影摇动。",
                "张三和赵六坐在藏宝阁内，四周静悄悄的。"]
        cands = find_entry_without_source(build_scene_index(1, body))
        zs = [c for c in cands if "张三" in c.detail]
        assert len(zs) == 1 and zs[0].evidence_refs == ["3-3"]

    def test_deixis_and_loss_not_counted(self):
        # 修复③：代称/丢失不抽数；合法裸形「钥匙…N把」仍抽。
        assert extract_statements(1, ["张三望着另一把钥匙，没有说话。"]) == []
        assert extract_statements(1, ["库房里失踪了一把钥匙。"]) == []
        ks = extract_statements(1, ["藏宝阁的钥匙一共有两把。"])
        assert any(s.predicate == "key_count" and s.value == "2把" for s in ks)

    def test_statement_has_tense_field(self):
        # 修复④：陈述时点字段（当晚=on_scene / 事后追述=aftermath）。
        on = extract_statements(1, ["今晚藏宝阁由赵六值守。"])
        off = extract_statements(1, ["他想起那晚藏宝阁由赵六值守。"])
        assert on[0].tense == "on_scene" and off[0].tense == "aftermath"

    def test_watch_cross_tense_not_paired(self):
        # 修复②+④：值守跨时点（当晚 vs 事后）属不同参照夜，不可同真冲突。
        body = ["今晚藏宝阁由赵六值守。", "他想起那晚藏宝阁由张三值守。"]
        assert find_statement_conflicts(extract_statements(1, body)) == []
        same = ["今晚藏宝阁由赵六值守。", "当晚其实是张三守夜。"]
        assert find_statement_conflicts(extract_statements(1, same)) != []

    @pytest.mark.skipif(not CH50.exists(), reason="wpe50ch 语料不在本机")
    def test_ch50_anchor1_backfill_li_si_gone(self):
        from plot_engine.metrics import _section_body
        body = _section_body(CH50.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
        cands = run_light(50, body)
        a = [c for c in cands if c.family == "A"]
        assert any("张三" in c.detail for c in a), "锚①张三未回补"
        assert not any("李四" in c.detail for c in a), "李四提及造帧工件未消除"
