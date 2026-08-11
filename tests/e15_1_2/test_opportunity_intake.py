"""E15.1.2 — OpportunityIntake tests (drop-in + fleet-derived)."""
import json

from operation.factory_brain import MarketOpportunity
from operation.factory_brain.opportunity_intake import OpportunityIntake

from tests.e15_1_2.brainhelpers import game, registry, write_dropin


def _intake(tmp_path, games=(), opps=None):
    reg = registry(tmp_path, games)
    dropin = (write_dropin(tmp_path, opps) if opps is not None
              else str(tmp_path / "none.json"))
    return OpportunityIntake(reg, dropin_path=dropin)


# ---------------------------------------------------------------- score
def test_score_composite():
    o = MarketOpportunity("o", "merge", keyword_trend=1.0, competition=0.0,
                          ecpm_signal=1.0, ltv_forecast=1.0)
    assert o.score() == 1.0


def test_score_competition_inverted():
    lo = MarketOpportunity("a", "merge", competition=0.0)
    hi = MarketOpportunity("b", "merge", competition=1.0)
    assert lo.score() > hi.score()


def test_score_clamped():
    o = MarketOpportunity("o", "merge", keyword_trend=5.0, competition=-2.0,
                          ecpm_signal=9.0, ltv_forecast=3.0)
    assert o.score() <= 1.0


def test_roundtrip_dict():
    o = MarketOpportunity("o1", "word", theme="zen", target_geos=["US", "JP"])
    d = o.to_dict()
    o2 = MarketOpportunity.from_dict(d)
    assert o2.opportunity_id == "o1" and o2.theme == "zen"
    assert o2.target_geos == ["US", "JP"]


# ---------------------------------------------------------------- dropin
def test_dropin_missing_file_ok(tmp_path):
    it = _intake(tmp_path)
    assert it.load_dropin() == []


def test_dropin_loads_list(tmp_path):
    it = _intake(tmp_path, opps=[
        {"opportunity_id": "x", "genre": "merge", "theme": "witch"}])
    got = it.load_dropin()
    assert len(got) == 1 and got[0].source == "growth_os"


def test_dropin_wrapped_object(tmp_path):
    p = tmp_path / "opps.json"
    p.write_text(json.dumps({"opportunities": [
        {"opportunity_id": "y", "genre": "puzzle"}]}), encoding="utf-8")
    it = OpportunityIntake(registry(tmp_path), dropin_path=str(p))
    assert len(it.load_dropin()) == 1


def test_dropin_malformed_never_crashes(tmp_path):
    p = tmp_path / "opps.json"
    p.write_text("{not json", encoding="utf-8")
    it = OpportunityIntake(registry(tmp_path), dropin_path=str(p))
    assert it.load_dropin() == []


def test_dropin_skips_bad_rows(tmp_path):
    it = _intake(tmp_path, opps=[
        {"opportunity_id": "ok", "genre": "merge"},
        {"genre": "no_id_here"}, "not_a_dict"])
    assert [o.opportunity_id for o in it.load_dropin()] == ["ok"]


# ---------------------------------------------------------------- fleet
def test_fleet_derives_from_published_metrics(tmp_path):
    it = _intake(tmp_path, games=[
        game("p1", metrics={"revenue_per_dau": 0.06, "store_cvr": 0.2})])
    got = it.derive_from_fleet()
    assert len(got) == 1
    assert got[0].source == "fleet" and got[0].genre == "merge"


def test_fleet_ignores_unpublished(tmp_path):
    it = _intake(tmp_path, games=[
        game("p1", status="development",
             metrics={"revenue_per_dau": 0.9})])
    assert it.derive_from_fleet() == []


def test_fleet_threshold_filters_weak(tmp_path):
    it = _intake(tmp_path, games=[
        game("p1", metrics={"revenue_per_dau": 0.001})])
    assert it.derive_from_fleet() == []


# ---------------------------------------------------------------- collect
def test_collect_ranks_by_score(tmp_path):
    it = _intake(tmp_path, opps=[
        {"opportunity_id": "hi", "genre": "merge", "theme": "witch",
         "keyword_trend": 0.9, "competition": 0.1,
         "ecpm_signal": 0.9, "ltv_forecast": 0.9},
        {"opportunity_id": "lo", "genre": "word", "theme": "zen",
         "keyword_trend": 0.1, "competition": 0.9,
         "ecpm_signal": 0.1, "ltv_forecast": 0.1}])
    got = it.collect()
    assert [o.opportunity_id for o in got] == ["hi", "lo"]


def test_collect_dedupes_genre_theme_keeps_best(tmp_path):
    it = _intake(tmp_path, opps=[
        {"opportunity_id": "weak", "genre": "merge", "theme": "witch",
         "keyword_trend": 0.1},
        {"opportunity_id": "strong", "genre": "merge", "theme": "witch",
         "keyword_trend": 0.9, "ecpm_signal": 0.9}])
    got = it.collect()
    ids = [o.opportunity_id for o in got]
    assert "strong" in ids and "weak" not in ids


def test_collect_merges_both_sources(tmp_path):
    it = _intake(
        tmp_path,
        games=[game("p1", genre="idle", status="published",
                    metrics={"revenue_per_dau": 0.05})],
        opps=[{"opportunity_id": "g1", "genre": "merge", "theme": "witch"}])
    sources = {o.source for o in it.collect()}
    assert sources == {"growth_os", "fleet"}
