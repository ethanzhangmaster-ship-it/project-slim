"""E15.1.2 — GameDecisionEngine (KEEP / SCALE / KILL + payback)."""
from operation.factory_brain import GameDecisionEngine, Verdict, payback_days

from tests.e15_1_2.brainhelpers import game, registry


def _verdict(metrics):
    g = game(genre="merge", status="published", metrics=metrics)
    return GameDecisionEngine().evaluate(g)


# --- payback_days properties ------------------------------------------- #
def test_payback_zero_cpi_is_zero():
    assert payback_days(0.0, 0.3, 0.4, 0.1) == 0.0


def test_payback_zero_arpdau_never_recoups():
    assert payback_days(1.0, 0.0, 0.4, 0.1) > 365


def test_payback_higher_cpi_takes_longer():
    assert payback_days(2.0, 0.3, 0.4, 0.14) > payback_days(1.0, 0.3, 0.4,
                                                            0.14)


def test_payback_better_retention_is_faster():
    weak = payback_days(1.0, 0.3, 0.30, 0.06)
    strong = payback_days(1.0, 0.3, 0.50, 0.20)
    assert strong < weak


# --- verdict branches -------------------------------------------------- #
def test_no_economics_returns_none():
    assert _verdict({"d1_retention": 0.4}) is None


def test_scale_when_proven_healthy_and_fast():
    d = _verdict({"cpi": 1.0, "arpdau": 0.35, "d1_retention": 0.42,
                  "d7_retention": 0.14, "roas": 1.3})
    assert d.verdict == Verdict.SCALE.value
    assert d.budget_delta_pct == 30.0


def test_kill_when_roas_bleeding():
    d = _verdict({"cpi": 2.0, "arpdau": 0.05, "d1_retention": 0.30,
                  "d7_retention": 0.09, "roas": 0.2})
    assert d.verdict == Verdict.KILL.value
    assert "bleeding" in d.reason


def test_proven_profit_never_killed_by_projection():
    # ROAS 1.1 proven profitable but weak arpdau -> KEEP, not KILL
    d = _verdict({"cpi": 1.0, "arpdau": 0.10, "d1_retention": 0.28,
                  "d7_retention": 0.08, "roas": 1.1})
    assert d.verdict == Verdict.KEEP.value
    assert "profitable" in d.reason


def test_kill_leaky_bucket_when_unproven():
    d = _verdict({"cpi": 1.5, "arpdau": 0.10, "d1_retention": 0.15,
                  "d7_retention": 0.03, "roas": 0.6})
    assert d.verdict == Verdict.KILL.value
    assert "leaky" in d.reason


def test_kill_no_payback_when_unproven():
    d = _verdict({"cpi": 2.5, "arpdau": 0.02, "d1_retention": 0.30,
                  "d7_retention": 0.08, "roas": 0.6})
    assert d.verdict == Verdict.KILL.value
    assert "payback" in d.reason


def test_keep_unproven_but_fast_payback():
    # no roas, fast payback, healthy retention -> KEEP (can't confirm SCALE)
    d = _verdict({"cpi": 1.0, "arpdau": 0.30, "d1_retention": 0.40,
                  "d7_retention": 0.14})
    assert d.verdict == Verdict.KEEP.value
    assert d.payback_days <= 90


def test_every_decision_requires_manual_apply():
    d = _verdict({"cpi": 1.0, "arpdau": 0.35, "d1_retention": 0.42,
                  "d7_retention": 0.14, "roas": 1.3})
    assert d.requires_manual_apply is True


def test_metric_snapshot_captured():
    d = _verdict({"cpi": 1.0, "arpdau": 0.35, "d1_retention": 0.42,
                  "d7_retention": 0.14, "roas": 1.3})
    assert d.metric_snapshot["cpi"] == 1.0
    assert d.metric_snapshot["arpdau"] == 0.35


def test_evaluate_fleet_skips_games_without_economics(tmp_path):
    reg = registry(tmp_path, [
        game(game_id="g1", status="published",
             metrics={"cpi": 1.0, "arpdau": 0.35, "d1_retention": 0.42,
                      "d7_retention": 0.14, "roas": 1.3}),
        game(game_id="g2", status="published", metrics={}),  # no economics
    ])
    verdicts = GameDecisionEngine().evaluate_fleet(reg)
    assert len(verdicts) == 1
    assert verdicts[0].game_id == "g1"
