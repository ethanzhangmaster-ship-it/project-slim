"""E15.1.2 — FactoryBrain integration tests (the closed loop)."""
import json

from operation.factory_brain import AsoVariant
from operation.publishing_factory.memory import (
    PublishingMemory, PublishingMemoryEntry,
)

from tests.e15_1_2.brainhelpers import brain, game


_OPPS = [
    {"opportunity_id": "gos_merge_witch", "genre": "merge",
     "theme": "witch", "target_geos": ["US", "JP"],
     "keyword_trend": 0.8, "competition": 0.3,
     "ecpm_signal": 0.7, "ltv_forecast": 0.6},
    {"opportunity_id": "gos_word_zen", "genre": "word", "theme": "zen",
     "keyword_trend": 0.5, "competition": 0.6,
     "ecpm_signal": 0.3, "ltv_forecast": 0.3},
]


def _fleet():
    return [
        game("p1", package="com.lf.merge.vampire",
             metrics={"revenue_per_dau": 0.08, "roas": 1.4}),
        game("p2", genre="simulation", monetization="iaa",
             package="com.lf.simulation.hospital",
             metrics={"revenue_per_dau": 0.004, "store_cvr": 0.08,
                      "baseline_cvr": 0.15}),
        game("p3", genre="puzzle", monetization="iaa",
             package="com.lf.puzzle.block", metrics={"roas": 0.2}),
    ]


def test_run_daily_full_report(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    r = b.run_daily()
    assert r.opportunities and r.specs and r.decisions and r.patterns
    assert r.real_api_called is False


def test_report_serializable(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    assert json.dumps(b.run_daily().to_dict())


def test_specs_biased_by_revenue_patterns(tmp_path):
    """The Revenue->Publishing feedback line: merge/hybrid succeeded,
    so the merge spec's confidence carries the pattern boost."""
    b = brain(tmp_path, games=[
        game("w1", package="com.lf.merge.a",
             metrics={"revenue_per_dau": 0.06}),
        game("w2", package="com.lf.merge.b",
             metrics={"revenue_per_dau": 0.07}),
    ], opps=_OPPS)
    r = b.run_daily()
    merge_spec = next(s for s in r.specs if s.genre == "merge")
    assert merge_spec.pattern_notes            # prior attached
    assert merge_spec.confidence >= 0.71       # boosted above raw score


def test_dedupe_never_proposes_operated_theme(tmp_path):
    b = brain(tmp_path, games=[
        game("p1", package="com.lf.merge.witch")], opps=_OPPS)
    r = b.run_daily()
    assert all(not (s.genre == "merge" and s.theme == "witch")
               for s in r.specs)


def test_capacity_limits_specs(tmp_path):
    many = [dict(o, opportunity_id=f"o{i}", theme=f"t{i}")
            for i, o in enumerate(_OPPS * 3)]
    b = brain(tmp_path, opps=many, capacity=2)
    assert len(b.run_daily().specs) <= 2


def test_fleet_ceiling_blocks_new_specs(tmp_path):
    fleet = [game(f"p{i:03d}", genre="idle",
                  package=f"com.lf.idle.t{i}") for i in range(50)]
    b = brain(tmp_path, games=fleet, opps=_OPPS)
    assert b.run_daily().specs == []


def test_register_specs_enters_fleet_as_development(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    n0 = b.registry.count()
    r = b.run_daily(register_specs=True)
    assert b.registry.count() == n0 + len(r.specs)
    for s in r.specs:
        gid = s.spec_id.replace("spec_", "g_")
        assert b.registry.get(gid).status == "development"
        assert b.portfolio.stage_of(gid) == "idea"


def test_register_idempotent(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    b.run_daily(register_specs=True)
    n1 = b.registry.count()
    b.run_daily(register_specs=True)
    assert b.registry.count() == n1            # dedupe holds


def test_decisions_cover_fleet(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    b.portfolio.set_stage("p1", "ua_test")
    b.portfolio.set_stage("p3", "ua_test")
    r = b.run_daily()
    by_game = {d.game_id: d.action for d in r.decisions}
    assert by_game["p1"] == "increase_budget"
    assert by_game["p3"] == "stop_ua"


def test_aso_winner_flows_into_report_and_memory(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    b.bandit.register(AsoVariant("va", "p1", "title", "Build Your Kingdom"))
    b.bandit.register(AsoVariant("vb", "p1", "title", "Merge Magic Castle"))
    b.bandit.observe("p1", "title", "va", 1000, 180)
    b.bandit.observe("p1", "title", "vb", 1000, 250)
    r = b.run_daily()
    assert r.aso_winners and r.aso_winners[0]["payload"] == "Merge Magic Castle"
    assert b.memory.recall(kind="aso_variant")


def test_store_experiments_for_cvr_drop(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    r = b.run_daily()
    assert any(e.game_id == "p2" for e in r.store_experiments)


def test_theme_learned_from_memory_feeds_spec(tmp_path):
    """Full memory loop: screenshot style winner -> pattern theme ->
    next-generation spec theme (when opportunity has no theme)."""
    mem = PublishingMemory(path=str(tmp_path / "m2.jsonl"))
    mem.record(PublishingMemoryEntry(
        game_id="w1", kind="screenshot_style", key="merge_fantasy",
        outcome="good", value=0.3, genre="merge"))
    b = brain(tmp_path, games=[
        game("w1", package="com.lf.merge.a",
             metrics={"revenue_per_dau": 0.06}),
        game("w2", package="com.lf.merge.b",
             metrics={"revenue_per_dau": 0.07})],
        opps=[{"opportunity_id": "o_merge", "genre": "merge", "theme": "",
               "keyword_trend": 0.8, "competition": 0.2,
               "ecpm_signal": 0.7, "ltv_forecast": 0.7}],
        memory=mem)
    r = b.run_daily()
    pat = next(p for p in r.patterns if p.pattern_id == "pat_merge_hybrid")
    assert pat.theme == "fantasy"


def test_no_dropin_still_runs_on_fleet_signals(tmp_path):
    b = brain(tmp_path, games=[
        game("p1", package="com.lf.merge.a",
             metrics={"revenue_per_dau": 0.06, "store_cvr": 0.2})])
    r = b.run_daily()
    assert any(o.source == "fleet" for o in r.opportunities)


def test_real_api_locked_false(tmp_path):
    b = brain(tmp_path, games=_fleet(), opps=_OPPS)
    assert b.real_api_called is False
    assert b.run_daily().real_api_called is False


def test_empty_world_no_crash(tmp_path):
    b = brain(tmp_path)
    r = b.run_daily()
    assert r.decisions == [] and r.patterns == []
    assert json.dumps(r.to_dict())


def test_scale_at_50_games_fast(tmp_path):
    """The 10-50 game promise: full daily cycle on 50 games stays sane."""
    fleet = [game(f"p{i:03d}",
                  genre=["merge", "puzzle", "idle", "word"][i % 4],
                  package=f"com.lf.g{i}.t{i}",
                  metrics={"revenue_per_dau": 0.01 * (i % 8),
                           "roas": 0.1 * (i % 15)})
             for i in range(50)]
    b = brain(tmp_path, games=fleet, opps=_OPPS)
    r = b.run_daily()
    assert len(r.decisions) == 50
    assert json.dumps(r.to_dict())
