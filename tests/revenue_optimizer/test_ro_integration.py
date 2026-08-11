from tests.revenue_optimizer.ro_helpers import report, winner_sig, zombie_sig, floor_sig, max_rows
from operation.revenue_optimizer.scheduler.revenue_cycle import RevenueCycle
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector
from operation.revenue_optimizer.experiment.planner import ExperimentPlanner
from operation.revenue_optimizer.experiment.evaluator import ExperimentEvaluator
from operation.optimizer.experiments.optimization_memory import OptimizationMemory
from operation.revenue_optimizer.memory.optimization_memory import record_outcome
from operation.optimizer.experiments.experiment_models import ExperimentDefinition


def _rep():
    return report(signals=[winner_sig(), zombie_sig(), floor_sig()],
                  dau=100_000.0)


def test_process_finds_opportunities():
    out = RevenueCycle().process(_rep(), 100_000.0, "ACCT_2")
    assert out["opportunities"] > 0


def test_process_ai_actions_impact():
    out = RevenueCycle().process(_rep(), 100_000.0, "ACCT_2")
    assert out["ai_actions"]
    assert "impact_per_day_usd" in out["ai_actions"][0]


def test_process_tiers_sum():
    out = RevenueCycle().process(_rep(), 100_000.0, "ACCT_2")
    s = sum(out["safety_tiers"].values())
    assert s == out["opportunities"]


def test_process_total_estimated():
    out = RevenueCycle().process(_rep(), 100_000.0, "ACCT_2")
    assert out["total_ai_estimated_per_day_usd"] >= 0


def test_process_package_built_for_auto():
    out = RevenueCycle().process(_rep(), 100_000.0, "ACCT_2")
    auto = [a for a in out["ai_actions"] if a["tier"] == "AUTO"]
    if auto:
        assert auto[0]["change_package"]["actions"]


def test_process_keys_present():
    out = RevenueCycle().process(_rep(), 100_000.0, "ACCT_2")
    for k in ("account", "dau", "period_revenue", "arpdau",
              "ai_actions", "experiments_planned", "safety_tiers"):
        assert k in out


def test_run_with_fake_agent():
    class FakeAgent:
        def run(self, account, start, end, rows=None, user_metrics=None,
                save=True, notify=True):
            return _rep()
    out = RevenueCycle().run("ACCT_2", "2026-07-14", "2026-07-23",
                             agent=FakeAgent())
    assert out["opportunities"] > 0


def test_exp_id_consistency():
    rep = _rep()
    opps = OpportunityDetector().detect(rep)
    exp = ExperimentPlanner().plan_one(opps[0], rep)
    assert exp.exp_id == opps[0].id


def test_memory_records_winner(tmp_path):
    mem = OptimizationMemory(path=str(tmp_path / "m.jsonl"))
    record_outcome(mem, account="ACCT_2", action="increase_bid_opportunity",
                   target="MINT", net_impact_pct=8.0, guardrail="pass",
                   decision="KEEP", confidence=0.9, applied_at="2026-07-10")
    q = mem.query(action="increase_bid_opportunity")
    assert q["prior"]["n"] == 1


def test_process_zero_opportunities_no_crash():
    out = RevenueCycle().process(report(signals=[], dau=100_000.0),
                                 100_000.0, "ACCT_2")
    assert out["opportunities"] == 0
    assert out["ai_actions"] == []
