# WP-F B2 读者已知阅读卡：纯派生投影，账外 fact 记「未感知」
from plot_engine.metrics import render_reader_card
from plot_engine.models.fact import Fact
from plot_engine.models.ledger import ReaderKnowledgeEntry
from plot_engine.models.state import StoryState


def _state():
    return StoryState(
        story_id="s1", chapter_no=3, version=1, epoch="epoch_1", state_hash="",
        facts={
            "fact_000001": Fact(fact_id="fact_000001", fact_type="existence",
                                proposition="藏宝阁有叛徒", canonical_form="traitor(阁楼)",
                                narrative_truth="true", objective_truth="true",
                                reveal_stage="hinted", defined_at_chapter=1, epoch="epoch_1"),
            "fact_000002": Fact(fact_id="fact_000002", fact_type="identity",
                                proposition="王五是内应", canonical_form="mole(王五)",
                                narrative_truth="true", objective_truth="true",
                                defined_at_chapter=2, epoch="epoch_1"),
        },
        reader_ledger=[ReaderKnowledgeEntry(
            fact_id="fact_000001", reader_state="knows", reader_strength=800,
            established_at_chapter=1, last_updated_chapter=3,
            source_event_id="e1", epoch="epoch_1")])


def test_card_projects_ledger_and_defaults_unledgered_to_unaware():
    card = render_reader_card(_state(), "s1")
    assert "fact_000001 | 已知 | 800 | 1→3" in card      # 入账：态/强度/建立→更新章
    assert "fact_000002 | 未感知 | - | -" in card        # 账外：没记≠知道，不兜假账
    assert "已知=1 未感知=1" in card                     # 分布按四态聚合
    assert "不进闸" in card                              # 纯派生只读的身份声明在卡面上
