"""E15.1.1 — Metadata Engine (ASO) tests (20)."""
from tests.e15_1_1.e15_1_1_helpers import game
from operation.publishing_factory.metadata_engine.aso_generator import (
    AsoGenerator, AsoPack, _TITLE_MAX, _SUB_MAX,
)
from operation.publishing_factory.metadata_engine.localization_engine import (
    LocalizationEngine,
)
from operation.publishing_factory.metadata_engine.keyword_optimizer import (
    KeywordOptimizer, _KW_BUDGET,
)


def test_aso_title_generated():
    pack = AsoGenerator().generate(game(display_name="Merge Witch"))
    assert pack.title


def test_aso_title_within_limit():
    pack = AsoGenerator().generate(game(display_name="Merge Witch"))
    assert len(pack.title) <= _TITLE_MAX


def test_aso_subtitle_within_limit():
    pack = AsoGenerator().generate(game())
    assert len(pack.subtitle) <= _SUB_MAX


def test_aso_keywords_seeded_by_genre():
    pack = AsoGenerator().generate(game(genre="merge"))
    assert "merge" in pack.keywords


def test_aso_competitor_hints_first():
    pack = AsoGenerator().generate(game(genre="merge"),
                                    competitor_hints=["dragons"])
    assert pack.keywords[0] == "dragons"


def test_aso_rationale_present():
    pack = AsoGenerator().generate(game())
    assert pack.rationale.get("title")


def test_aso_to_dict():
    pack = AsoGenerator().generate(game())
    d = pack.to_dict()
    assert d["game_id"] == "merge_witch" and "keywords" in d


def test_aso_title_brand_kept():
    pack = AsoGenerator().generate(game(display_name="Merge Witch"))
    assert "Merge Witch" in pack.title


def test_aso_different_genre_diff_seeds():
    a = AsoGenerator().generate(game(genre="puzzle")).keywords
    b = AsoGenerator().generate(game(genre="idle")).keywords
    assert a[0] != b[0]


def test_localization_five_locales():
    pack = AsoGenerator().generate(game(display_name="Merge Witch"))
    loc = LocalizationEngine().localize(pack)
    assert set(loc.keys()) >= {"en-US", "de-DE", "fr-FR", "ja-JP", "ko-KR"}


def test_localization_brand_passthrough():
    pack = AsoGenerator().generate(game(display_name="Merge Witch"))
    loc = LocalizationEngine().localize(pack)
    assert "Merge Witch" in loc["ja-JP"].title


def test_localization_keyword_translated():
    pack = AsoGenerator().generate(game(genre="merge"))
    loc = LocalizationEngine().localize(pack)
    # 'merge' should be translated in ja-JP
    assert "マージ" in loc["ja-JP"].keywords


def test_localization_ko_translation():
    pack = AsoGenerator().generate(game(genre="puzzle"))
    loc = LocalizationEngine().localize(pack)
    assert "퍼즐" in loc["ko-KR"].keywords


def test_kw_optimizer_scores():
    plan = KeywordOptimizer().optimize("g", ["merge", "puzzle", "x"],
                                      genre_seed=["merge", "puzzle"])
    assert plan.ranked[0].relevance == 1.0


def test_kw_dedup():
    plan = KeywordOptimizer().optimize("g", ["merge", "Merge", "puzzle"],
                                      genre_seed=["merge"])
    assert len(plan.selected) == len(set(plan.selected))


def test_kw_budget_respected():
    big = [f"keyword{i}" for i in range(50)]
    plan = KeywordOptimizer().optimize("g", big)
    assert plan.budget_used <= _KW_BUDGET


def test_kw_selected_nonempty():
    plan = KeywordOptimizer().optimize("g", ["merge", "magic", "dragon"],
                                      genre_seed=["merge"])
    assert plan.selected


def test_kw_opportunity_low_for_high_competition():
    a = KeywordOptimizer().optimize("g", ["merge"], competition={"merge": 0.9})
    b = KeywordOptimizer().optimize("g", ["merge"], competition={"merge": 0.1})
    assert a.ranked[0].opportunity < b.ranked[0].opportunity


def test_kw_plan_to_dict():
    plan = KeywordOptimizer().optimize("g", ["merge", "magic"])
    d = plan.to_dict()
    assert d["game_id"] == "g" and "ranked" in d
