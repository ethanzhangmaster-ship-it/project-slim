"""E15.1.2 — SpecGenerator tests."""
from operation.factory_brain import SuccessPattern
from operation.factory_brain.spec_generator import SpecGenerator

from tests.e15_1_2.brainhelpers import opportunity


def test_generates_spec_from_strong_opportunity():
    s = SpecGenerator().generate(opportunity(score_hint=0.8))
    assert s is not None
    assert s.genre == "merge" and s.theme == "witch"


def test_below_threshold_returns_none():
    s = SpecGenerator().generate(opportunity(score_hint=0.1))
    assert s is None


def test_theme_fallback_from_genre():
    s = SpecGenerator().generate(opportunity(theme="", score_hint=0.8))
    assert s.theme == "fantasy"          # merge default


def test_spec_dict_shape_matches_product_yaml():
    d = SpecGenerator().generate(opportunity(score_hint=0.8)).to_dict()
    assert set(d["product"].keys()) == {"genre", "theme", "target_geo"}
    assert "type" in d["monetization"]
    assert "keywords" in d["aso"]


def test_keywords_deduped_and_genre_prefixed():
    s = SpecGenerator().generate(opportunity(score_hint=0.8))
    assert len(s.aso_keywords) == len(set(s.aso_keywords))
    assert any(k.startswith("merge ") for k in s.aso_keywords)


def test_monetization_default_per_genre():
    s = SpecGenerator().generate(
        opportunity(genre="word", theme="travel", score_hint=0.8))
    assert s.monetization == "iaa"
    assert s.starter_pack is False


def test_hybrid_gets_starter_pack():
    s = SpecGenerator().generate(opportunity(score_hint=0.8))
    assert s.monetization == "hybrid" and s.starter_pack is True


# ---------------------------------------------------------------- priors
def _pat(weight=1.5, rate=0.2, sample=5, theme="witch"):
    return SuccessPattern(pattern_id="pat_merge_hybrid", genre="merge",
                          theme=theme, monetization="hybrid",
                          rewarded_focus=True, success_rate=rate,
                          sample=sample, weight=weight)


def test_prior_boosts_confidence():
    base = SpecGenerator().generate(opportunity(score_hint=0.6))
    boosted = SpecGenerator(patterns=[_pat()]).generate(
        opportunity(score_hint=0.6))
    assert boosted.confidence > base.confidence


def test_prior_notes_attached():
    s = SpecGenerator(patterns=[_pat()]).generate(opportunity(score_hint=0.7))
    assert s.pattern_notes and "success_rate" in s.pattern_notes[0]


def test_prior_overrides_monetization():
    p = _pat()
    p.monetization = "iap"
    s = SpecGenerator(patterns=[p]).generate(opportunity(score_hint=0.7))
    assert s.monetization == "iap"


def test_prior_wrong_genre_ignored():
    p = _pat()
    p.genre = "word"
    s = SpecGenerator(patterns=[p]).generate(opportunity(score_hint=0.6))
    assert s.pattern_notes == []


def test_confidence_capped_at_one():
    s = SpecGenerator(patterns=[_pat(weight=1.5)]).generate(
        opportunity(score_hint=0.9))
    assert s.confidence <= 1.0


# ---------------------------------------------------------------- batch
def test_batch_respects_capacity():
    opps = [opportunity(oid=f"o{i}", genre="merge", theme=f"t{i}",
                        score_hint=0.8) for i in range(5)]
    got = SpecGenerator().generate_batch(opps, capacity=2)
    assert len(got) == 2


def test_batch_skips_weak_keeps_scanning():
    opps = [opportunity(oid="weak", score_hint=0.1),
            opportunity(oid="strong", genre="word", theme="zen",
                        score_hint=0.8)]
    got = SpecGenerator().generate_batch(opps, capacity=3)
    assert len(got) == 1 and got[0].opportunity_id == "strong"


# ---------------------------------------------------------------- to game
def test_to_game_product_contract():
    spec = SpecGenerator().generate(opportunity(score_hint=0.8), seq=7)
    gp = SpecGenerator.to_game_product(spec)
    assert gp.game_id.startswith("g_")
    assert gp.status == "development"
    assert gp.genre == "merge"
    assert gp.package_name == "com.leanfactory.merge.witch"
    assert gp.keywords == spec.aso_keywords


def test_to_game_product_jp_locale():
    o = opportunity(score_hint=0.8)
    o.target_geos = ["US", "JP"]
    gp = SpecGenerator.to_game_product(SpecGenerator().generate(o))
    assert "ja-JP" in gp.locales
