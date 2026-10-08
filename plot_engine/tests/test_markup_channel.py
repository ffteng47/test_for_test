# markup → Proposal 通道 1（07 §4.3）：reader 标注生成 READER_* Proposal
from plot_engine.markup import parse_markup
from plot_engine.markup_channel import markup_to_proposals


def test_two_annos_two_proposals():
    m = parse_markup("<!-- reader_learns: fact_000003 -->\n\n"
                     "<!-- reader_hinted: fact_000001 -->")
    ps = markup_to_proposals(m, chapter=47, start_seq=10)
    assert len(ps) == 2
    p0, p1 = ps
    assert p0.proposed_event_type == "READER_LEARNS"
    assert p1.proposed_event_type == "READER_HINTED"
    assert p0.payload == {"fact_id": "fact_000003"}
    assert p0.extraction_method == "markup"
    assert p0.extraction_confidence == 1000 and p0.confidence == 1000
    assert p0.actor is None
    assert p0.chapter == 47
    # seq 连续
    assert p0.seq == 10 and p1.seq == 11


def test_kind_mapping_exact():
    m = parse_markup("<!-- reader_learns: fact_000003 -->\n\n"
                     "<!-- reader_deceived: fact_000002 -->\n\n"
                     "<!-- reader_hinted: fact_000001 -->")
    ps = markup_to_proposals(m, chapter=5, start_seq=0)
    assert [p.proposed_event_type for p in ps] == [
        "READER_LEARNS", "READER_DECEIVED", "READER_HINTED"]


def test_no_fact_anno_not_proposal():
    # 缺 fact_id 的 unknown 标注不产 Proposal（validator 负责 anno↔proposal 配对，M2）
    m = parse_markup("<!-- reader_knows: fact_000001 -->")
    assert markup_to_proposals(m, chapter=47, start_seq=0) == []


def test_source_ref_format():
    m = parse_markup("<!-- reader_learns: fact_000003 -->")
    p = markup_to_proposals(m, chapter=47, start_seq=3)[0]
    assert p.source_ref == "markup:reader_learns#3"
