# markup 解析（07 §4.4）：解析器只分类、不判数量/位置（M1/M5 归 validator）
from plot_engine.markup import DraftMarkup, HookAnno, ReaderAnno, parse_markup


def test_wellformed_hook_and_reader():
    draft = "第一段正文。\n\n第二段正文。\n\n<!-- hook: cliffhanger strength=800 -->"
    m = parse_markup(draft)
    assert m.para_count == 3
    assert m.hooks == [HookAnno(kind="cliffhanger", strength=800, para_index=2,
                                raw="<!-- hook: cliffhanger strength=800 -->")]
    assert m.readers == [] and m.unknown == []


def test_strength_out_of_range_still_parsed():
    # 值域由 validator 判定；解析器照单捕获
    m = parse_markup("正文\n\n<!-- hook: cliffhanger strength=1001 -->")
    assert m.hooks[0].strength == 1001


def test_reader_three_kinds():
    draft = ("<!-- reader_learns: fact_000003 -->\n\n"
             "<!-- reader_hinted: fact_000001 -->\n\n"
             "<!-- reader_deceived: fact_000002 -->")
    m = parse_markup(draft)
    assert [r.kind for r in m.readers] == ["learns", "hinted", "deceived"]
    assert [r.fact_id for r in m.readers] == ["fact_000003", "fact_000001", "fact_000002"]
    assert [r.para_index for r in m.readers] == [0, 1, 2]


def test_near_miss_reader_goes_to_unknown():
    # reader_knows 不是合法 kind（07 §4.4），不得静默丢弃（05 §9 I6）
    m = parse_markup("正文\n\n<!-- reader_knows: fact_000001 -->")
    assert m.readers == []
    assert m.unknown == ["<!-- reader_knows: fact_000001 -->"]


def test_cjk_body_unaffected():
    m = parse_markup("张三凝视印章，意识到叛徒可能就在身边。\n\n<!-- hook: none strength=0 -->")
    assert m.para_count == 2
    assert m.hooks[0].kind == "none"


def test_empty_draft():
    m = parse_markup("")
    assert m == DraftMarkup(hooks=[], readers=[], para_count=0, unknown=[])


def test_two_annos_in_one_paragraph():
    m = parse_markup("前文 <!-- reader_learns: fact_000003 --> 中段 "
                     "<!-- hook: cliffhanger strength=800 -->")
    assert m.para_count == 1
    assert m.readers[0].para_index == 0 and m.hooks[0].para_index == 0
