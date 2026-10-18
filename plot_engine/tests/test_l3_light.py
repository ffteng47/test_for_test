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
        # 修复④：陈述时点字段（当晚=on_scene / 事后追述=aftermath，custody 承载）。
        on = extract_statements(1, ["今晚藏宝阁的钥匙由赵六亲自保管。"])
        off = extract_statements(1, ["他想起那晚藏宝阁的钥匙由赵六亲自保管。"])
        assert on[0].tense == "on_scene" and off[0].tense == "aftermath"

    def test_night_watch_predicate_retired(self):
        # v2.2②（tff 拍板）：night_watch 全库真人终审零条真=谓词退役，值守不再出陈述。
        assert extract_statements(1, ["今晚藏宝阁由赵六值守。",
                                      "当晚其实是张三守夜。"]) == []

    @pytest.mark.skipif(not CH50.exists(), reason="wpe50ch 语料不在本机")
    def test_ch50_anchor1_backfill_li_si_gone(self):
        from plot_engine.metrics import _section_body
        body = _section_body(CH50.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
        cands = run_light(50, body)
        a = [c for c in cands if c.family == "A"]
        assert any("张三" in c.detail for c in a), "锚①张三未回补"
        assert not any("李四" in c.detail for c in a), "李四提及造帧工件未消除"


class TestSkydropArrival:
    """§7.18 空降到达闸（v0.3 中批后续，旁路确定性检查，本批不接 run_light=待 tff 双面验收裁定）。

    双面验收：①真穿帮 ch08（山下落定→凭空进书房）必须过闸；②§7.16 判误的「到达叙述被误引为
    证据」型 B 不得因本闸转成宿主新火。
    """

    def test_door_only_arrival_after_elsewhere_fires(self):
        from plot_engine.l3.temporal_checks import find_skydrop_arrivals
        frames = build_scene_index(8, ["张三在书房内翻查簿记。",
                                       "走出院门，张三向山下走去，来到了山下的一家小酒馆。",
                                       "张三推开书房的门，一股墨香扑面而来。"])
        e = find_skydrop_arrivals(frames)
        assert len(e) == 1 and e[0].family == "B" and e[0].rule_id == "skydrop_arrival"
        assert "空降到达" in e[0].detail

    def test_movement_arrival_not_fired(self):
        from plot_engine.l3.temporal_checks import find_skydrop_arrivals
        frames = build_scene_index(8, ["张三在书房内翻查簿记。",
                                       "走出院门，张三向山下走去，来到了山下的一家小酒馆。",
                                       "张三回到书房，把灯点上。"])
        assert find_skydrop_arrivals(frames) == []  # 位移支到达=续接位移链，保留全消解权

    def test_same_location_door_arrival_not_fired(self):
        from plot_engine.l3.temporal_checks import find_skydrop_arrivals
        frames = build_scene_index(8, ["赵六在藏宝阁内值守，翻着簿记。",
                                       "赵六推开藏宝阁的门，取出钥匙。"])
        assert find_skydrop_arrivals(frames) == []  # 人没换地方=没有位移蒸发

    @pytest.mark.skipif(not (CH50.parent / "ch08.md").exists(), reason="wpe50ch 语料不在本机")
    def test_ch08_real_evaporation_fires(self):
        """tff 亲裁真穿帮：ch08 L015 人已落到山下 ↔ L016 凭空推开书房的门。"""
        from plot_engine.metrics import _section_body
        from plot_engine.l3.temporal_checks import find_skydrop_arrivals
        body = _section_body((CH50.parent / "ch08.md").read_text(
            encoding="utf-8", errors="replace").splitlines(), "Draft")
        e = find_skydrop_arrivals(build_scene_index(8, body))
        assert [c.evidence_refs for c in e] == [["15-15", "16-18"]]


class TestSceneReplay:
    """E 族旁路：语义级场景重演（不接 run_light，本批尺面 v0.2 不含 E）。"""

    def test_same_scene_three_segments_fire(self):
        from plot_engine.l3.scene_replay import find_scene_replay
        body = ["藏宝阁内赵六查钥匙，盘点簿记。", "赵六盯着那枚印章。",
                "张三走进藏宝阁查钥匙，翻看记录。", "张三怀疑有人动过。",
                "王五赶到藏宝阁查钥匙，核对簿记。", "赵六又谈起伪造的印章。"]
        frames = build_scene_index(1, body)
        e = find_scene_replay(1, strip_comments(body)[0], frames)
        assert e and e[0].family == "E" and e[0].rule_id == "scene_replay"
        assert e[0].evidence_refs == ["1-2", "3-4", "5-6"]

    @pytest.mark.skipif(not CH50.exists(), reason="wpe50ch 语料不在本机")
    def test_ch50_three_segments_calibrated(self):
        from plot_engine.l3.scene_replay import find_scene_replay
        from plot_engine.metrics import _section_body
        body = _section_body(CH50.read_text(encoding="utf-8", errors="replace").splitlines(), "Draft")
        e = find_scene_replay(50, strip_comments(body)[0], build_scene_index(50, body))
        assert [c.evidence_refs for c in e if c.family == "E"] == [["1-8", "9-20", "22-30"]], \
            "ch50 三段重演（001-008/009-021/022-030）校准未命中"


class TestExtractorV21:
    """v2.1 三笔残余漏洞（judge-v1.1 预核呈堂，tff 2026-10-18「程序漏洞要修补」）。"""

    def test_seek_target_not_presence(self):
        # ①ch27 型：叙述「去找X」=移动意图目标提及，被找者不在本场景在场。
        body = ["藏宝阁内，张三翻找记录，王五则去找李四询问。"]
        frames = build_scene_index(1, body)
        assert "李四" not in frames[0].present
        assert "张三" in frames[0].present and "王五" in frames[0].present

    def test_watch_question_not_statement(self):
        # ②ch42/ch32 型询问句不抽（v2.2 拍板后整谓词退役，问/陈述均出空）。
        assert extract_statements(1, ["张三问：「昨晚在这里值夜班的是谁吗？」"]) == []
        assert extract_statements(1, ["赵六说：「我昨晚值夜班的时候，一切如常。」"]) == []

    def test_day_scene_watch_cross_tense_paired_out(self):
        # ③ch45 型：白日词入时点表（tense 字段仍产，供 key 类跨时点标注）。
        on = extract_statements(1, ["深夜的藏宝阁钥匙一共两把，由赵六保管。"])
        day = extract_statements(1, ["阳光透过窗户，藏宝阁钥匙一共三把的说法无人再提，由长老保管。"])
        assert on[0].tense == "on_scene" and any(s.tense == "aftermath" for s in day)


class TestExtractorV22:
    """v2.2（tff 真人终审 92 卡呈规格：A 族宿主独报 27 条全误=回忆/传闻小句造帧）。"""

    def test_recall_and_hearsay_clauses_not_presence(self):
        # ①ch05/06/12/20/22/26 型：想起/听说/怀疑/念头小句不造在场帧。
        body = ["张三独自坐在书房，整理着旧文档。",
                "他想起赵六曾在藏宝阁出没，又听说李四那晚在山下与外客饮酒。",
                "王五低声怀疑钥匙的事另有隐情。"]
        frames = build_scene_index(1, body)
        for fr in frames:
            assert "赵六" not in fr.present and "李四" not in fr.present
        assert any("张三" in fr.present for fr in frames)
        # 经验者与被提及者同小句时一起剥（「王五低声怀疑…」）；真实在场靠其他行建立。
        assert all("王五" not in fr.present for fr in frames)

    def test_real_presence_after_mention_line_survives(self):
        # ①不过杀：提及小句剥掉后，同他行的真实在场互动行仍建立在场（锚①同款句式保真）。
        body = ["藏宝阁内只剩赵六一人，他守着灯火。",
                "赵六想起张三昨日的疑话，沉默不语。",
                "张三和赵六坐在藏宝阁内，四周静悄悄的。"]
        frames = build_scene_index(1, body)
        assert frames[-1].present_line["张三"] == 3

    def test_night_watch_gone_from_corpus_predicates(self):
        # ②退役核验：C 域谓词白名单只剩 key_count/key_custody。
        cands = run_light(1, ["今晚藏宝阁由赵六值守。", "他想起那晚其实是张三守夜。"])
        assert all("night_watch" not in c.detail for c in cands if c.family == "C")


class TestExtractorV23:
    """v2.3 小批（tff 裁定＝稽核 F1+F3+F4 先行，F2 挂中批）。每规则一条。"""

    def test_f1_memory_line_not_departure(self):
        # F1 作用域：行级拒绝从在场扩到到达/离开（稽核 ch40 L17「他记得自己离开时…」）。
        frames = build_scene_index(1, ["书房内张三坐在案前，翻着旧文档。",
                                       "他记得自己离开时，门是盖得严丝合缝的。"])
        assert all("张三" not in fr.departed for fr in frames)

    def test_f1_negated_departure_not_counted(self):
        # F1 否定守卫（稽核 ch40 L2「然而他并未离开藏宝阁一步」）。
        frames = build_scene_index(1, ["藏宝阁内赵六坐在木椅上。",
                                       "然而他并未离开藏宝阁一步。"])
        assert all(not fr.departed for fr in frames)

    def test_f3_come_arrival_words(self):
        # F3 到达词表补「前来/赶来/过来」（稽核 ch26 L6「赵六匆匆前来」）。
        frames = build_scene_index(1, ["藏宝阁内只剩王五一人守着灯火。",
                                       "赵六匆匆前来，两人对坐无言。"])
        assert any("赵六" in fr.arrived for fr in frames)

    def test_f4_pointed_hearsay_not_presence(self):
        # F4 转述漏网（稽核 ch15 L10「…那就是李四在山下与一个陌生人会饮」）。
        frames = build_scene_index(1, ["书房内张三翻查着卷宗。",
                                       "他发现了新的线索，那就是李四在山下与一个陌生人会饮。"])
        assert all("李四" not in fr.present for fr in frames)


class TestExtractorV3:
    """v0.3 中批（tff 2026-10-19 拍板=启动中批）：在场认定改「叙述层施事」双闸，根治稽核 F2。"""

    def test_subject_before_trigger_survives(self):
        # F2 根治主案：触发词在后半句不再把主语连坐（ch08 L1 型=整行拒绝的头号误杀）。
        frames = build_scene_index(1, ["张三站在藏宝阁外，心中满是疑惑。",
                                       "他知道这把钥匙只有两枚。"])
        assert frames[0].present_line.get("张三") == 1

    def test_mentioned_entity_not_presence(self):
        # 闸二：被提及者不是施事=不在场（ch08 L7 型=笔迹与王五的手书相似）。
        frames = build_scene_index(1, ["张三独自坐在书房，整理着旧文档。",
                                       "他凝视着密信，笔迹与王五的手书有几分类似。"])
        assert all("王五" not in fr.present for fr in frames)
        assert frames[0].present_line.get("张三") == 1

    def test_memory_clause_scope_until_sentence_end(self):
        # 闸一：触发词小句起、到句末为止的辖域内一律不建立在场（冒号蔓延案）。
        frames = build_scene_index(1, ["藏宝阁内只剩下赵六一人。",
                                       "他想起那些消失的簿记：李四曾在山下会饮，王五也来过这里。"])
        assert frames[0].present_line.get("赵六") == 1
        assert all("李四" not in fr.present and "王五" not in fr.present for fr in frames)

    def test_ch08_movement_anchor_lines_visible(self):
        # §7.18 前置实证：位移锚行 L015 与再入场行 L016 不再被整行拒绝吞掉（v2.2/v2.3 面上两帧 present 全空）。
        body = ["张三走出书房，来到后院，王五正在院中独自饮酒。",
                "走出院门，张三向山下走去，来到了山下的一家小酒馆。",
                "张三推开书房的门，一股淡淡的墨香扑面而来。"]
        frames = build_scene_index(8, body)
        at山下 = [fr for fr in frames if fr.location_text == "山下"]
        at书房 = [fr for fr in frames if fr.location_text == "书房"]
        assert "张三" in at山下[0].present and "张三" in at书房[-1].present

