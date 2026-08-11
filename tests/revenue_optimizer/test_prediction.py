from tests.revenue_optimizer.ro_helpers import ctx, winner_sig, report
from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.prediction.lift_model import LiftModel
from operation.revenue_optimizer.prediction.confidence import ConfidenceEstimator
from operation.revenue_optimizer.prediction.revenue_predictor import RevenuePredictor
from operation.optimizer.experiments.optimization_memory import OptimizationMemory

import tempfile, os


def _opp(lift=0.1, conf=0.9, risk=0.1, imps=5000):
    return RevenueOpportunity(
        id="x", app_id="ACCT_2", dimension="network", rule="hidden_winner",
        action="increase_bid_opportunity", target="MINT", current_value=imps,
        target_value=imps, expected_lift=lift, confidence=conf, risk=risk,
        metrics={"impressions": imps})


def test_lift_before_after():
    p = LiftModel().predict(_opp(lift=0.1), ctx(total_revenue=1000))
    assert p.before_revenue == 1000
    assert p.after_revenue == 1100


def test_lift_percent():
    p = LiftModel().predict(_opp(lift=0.12), ctx())
    assert p.lift_percent == 12.0


def test_dampen_full_when_enough_imps():
    assert LiftModel().dampen(_opp(imps=1000)) == 1.0


def test_dampen_floor_when_zero_imps():
    assert LiftModel().dampen(_opp(imps=0)) == 0.4


def test_dampen_partial():
    d = LiftModel().dampen(_opp(imps=100))
    assert 0.4 < d < 1.0


def test_dampen_note():
    p = LiftModel().predict(_opp(lift=0.1, imps=0), ctx(total_revenue=1000))
    assert "dampen" in p.note


def test_confidence_base():
    c = ConfidenceEstimator().estimate(_opp(conf=0.9, imps=2000), ctx())
    assert c == 0.9


def test_confidence_small_sample():
    c = ConfidenceEstimator().estimate(_opp(conf=0.9, imps=10), ctx())
    assert c < 0.9


def test_confidence_memory_bump(tmp_path):
    mem = OptimizationMemory(path=str(tmp_path / "m.jsonl"))
    mem.record(account="ACCT_2", action="increase_bid_opportunity",
               target="MINT", net_impact_pct=10.0, guardrail="pass",
               decision="KEEP", confidence=0.9, applied_at="2026-07-10")
    c = ConfidenceEstimator().estimate(_opp(conf=0.9, imps=2000), ctx(), mem)
    assert c > 0.9


def test_confidence_clamp():
    opp = _opp(conf=1.0, imps=5000)
    c = ConfidenceEstimator().estimate(opp, ctx())
    assert c <= 0.95


def test_predictor_composes_confidence():
    pred = RevenuePredictor().predict(_opp(conf=0.9, imps=2000), ctx())
    assert pred.confidence == 0.9


def test_predictor_lift_matches():
    pred = RevenuePredictor().predict(_opp(lift=0.1, imps=5000), ctx(total_revenue=2000))
    assert pred.after_revenue == 2200


def test_predictor_risk():
    pred = RevenuePredictor().predict(_opp(risk=0.2), ctx())
    assert pred.risk == 0.2


def test_predictor_memory_raises_confidence(tmp_path):
    mem = OptimizationMemory(path=str(tmp_path / "m.jsonl"))
    mem.record(account="ACCT_2", action="increase_bid_opportunity",
               target="MINT", net_impact_pct=10.0, guardrail="pass",
               decision="KEEP", confidence=0.9, applied_at="2026-07-10")
    pred = RevenuePredictor().predict(_opp(conf=0.9, imps=2000), ctx(), mem)
    assert pred.confidence > 0.9


def test_prediction_to_dict_rounds():
    pred = RevenuePredictor().predict(_opp(lift=0.1, imps=5000),
                                      ctx(total_revenue=1234.567))
    d = pred.to_dict()
    assert isinstance(d["before_revenue"], float)
    assert d["lift_percent"] == 10.0
