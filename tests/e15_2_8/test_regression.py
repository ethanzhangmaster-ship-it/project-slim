"""Regression — 10 tests verifying existing player_monetization + revenue_optimizer modules still work after E15.2.8 additions."""
import subprocess, sys, os

LAUNCHFORGE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(__file__))))

def _run(label, *args):
    """Run pytest on a test dir; return (label, passed, failed, total)."""
    cp = subprocess.run([sys.executable, "-m", "pytest", *args, "-q"],
                        cwd=LAUNCHFORGE, capture_output=True, text=True)
    lines = cp.stdout.splitlines() + cp.stderr.splitlines()
    for line in lines:
        if "passed" in line and "failed" in line:
            parts = line.strip().split(",")
            p = f = t = 0
            for part in parts:
                part = part.strip()
                if "passed" in part:
                    p = int(part.split(" ")[0])
                if "failed" in part:
                    f = int(part.split(" ")[0])
            t = p + f
            return label, p, f, t
    return label, 0, 0, 0

def test_regression_player_monetization():
    """Existing 100 player_monetization tests still pass."""
    _, passed, failed, total = _run("pm", "tests/player_monetization")
    assert failed == 0, f"player_monetization: {failed}/{total} failed"

def test_regression_revenue_optimizer():
    """Existing 80 revenue_optimizer tests still pass."""
    _, passed, failed, total = _run("ro", "tests/revenue_optimizer")
    assert failed == 0, f"revenue_optimizer: {failed}/{total} failed"

def test_regression_pm_segmenter():
    """Player segmenter: existing segmenter tests still work."""
    from tests.player_monetization.pm_helpers import high_value_profile
    from operation.player_monetization.user_profile.player_segment import PlayerSegmenter
    s = PlayerSegmenter().classify(high_value_profile())
    assert s.segment in ("power_user", "high_value_ad_player")

def test_regression_pm_frequency():
    """Frequency optimizer: existing caps unchanged."""
    from operation.player_monetization.frequency.frequency_optimizer import FrequencyOptimizer
    from tests.player_monetization.pm_helpers import segment
    r = FrequencyOptimizer().optimize("u1", segment(seg="at_risk_churn"))
    assert r.max_per_session == 1

def test_regression_pm_collector():
    """EventCollector: synthetic aggregation unchanged."""
    from operation.player_monetization.events.collector import SyntheticProvider, EventCollector
    ev = SyntheticProvider().one_user("u99", sessions=2, ad_requests=10, ad_shows=8)
    p = EventCollector._aggregate(ev)
    assert len(p) == 1

def test_regression_rm_lifecycle():
    """Lifecycle: stages unchanged."""
    from tests.player_monetization.pm_helpers import new_profile
    from operation.player_monetization.user_profile.lifecycle import LifecycleDetector
    assert LifecycleDetector().stage(new_profile()) == "NEW"

def test_regression_rm_value_predictor():
    """ValuePredictor: predictions unchanged."""
    from tests.player_monetization.pm_helpers import high_value_profile
    from operation.player_monetization.user_profile.player_segment import PlayerSegmenter
    from operation.player_monetization.user_profile.value_predictor import ValuePredictor
    p = high_value_profile()
    seg = PlayerSegmenter().classify(p)
    vp = ValuePredictor().predict(p, seg)
    assert vp.predicted_30d_iaa > 0

def test_regression_e15_2_5_validate():
    """E15.2.5 intel_models MonetizationDailyReport constructible."""
    from operation.optimizer.intel_models import MonetizationDailyReport
    r = MonetizationDailyReport(account="x", date="", period_start="", period_end="",
        revenue=0, impressions=0, attempts=0, blended_ecpm=0, waterfall_depth=0,
        health_score=0, health_grade="", signals=[], validated_actions=[])
    assert r.to_dict()["account"] == "x"

def test_regression_e15_2_4_validate():
    """E15.2.4 experiment_models importable and canon_target works."""
    from operation.optimizer.experiments.experiment_models import canon_target
    assert canon_target("CHARTBOOST_NETWORK") == "CHARTBOOST"

def test_regression_revenue_cycle():
    """RevenueCycle process still works."""
    from tests.revenue_optimizer.ro_helpers import report, winner_sig, zombie_sig
    from operation.revenue_optimizer.scheduler.revenue_cycle import RevenueCycle
    out = RevenueCycle().process(report(signals=[winner_sig()]), 100000.0, "ACCT_2")
    assert out["opportunities"] > 0
