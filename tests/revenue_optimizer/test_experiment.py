from tests.revenue_optimizer.ro_helpers import report, zombie_sig, winner_sig, max_rows
from operation.revenue_optimizer.experiment.planner import ExperimentPlanner
from operation.revenue_optimizer.experiment.allocator import TrafficAllocator
from operation.revenue_optimizer.experiment.evaluator import ExperimentEvaluator
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector
from operation.optimizer.experiments.experiment_models import ExperimentDefinition


def _exp(target="MINT_BIDDING"):
    return ExperimentDefinition(
        exp_id="abc123", account="ACCT_2", title="t",
        hypothesis="h", action_type="increase_bid_opportunity",
        target=target, source_rule="hidden_winner", min_days=3, max_days=14,
        expected_metric="revenue_per_dau", expected_lift_pct=5.0,
        variant_a="a", variant_b="b")


def test_planner_returns_experiments():
    exps = ExperimentPlanner().plan(report(signals=[winner_sig()]))
    assert len(exps) >= 1


def test_planner_plan_one():
    rep = report(signals=[winner_sig()])
    opps = OpportunityDetector().detect(rep)
    exp = ExperimentPlanner().plan_one(opps[0], rep)
    assert exp is not None
    assert exp.target == opps[0].target


def test_experiment_metric():
    exps = ExperimentPlanner().plan(report(signals=[winner_sig()]))
    assert exps[0].expected_metric == "revenue_per_dau"


def test_experiment_variants():
    exps = ExperimentPlanner().plan(report(signals=[winner_sig()]))
    assert exps[0].variant_a and exps[0].variant_b


def test_allocator_full():
    a = TrafficAllocator().allocate(_exp())
    assert a["variant_share"] == 1.0 and a["control_share"] == 0.0


def test_allocator_split():
    a = TrafficAllocator().allocate(_exp(), mode="split")
    assert a["control_share"] == 0.5 and a["variant_share"] == 0.5


def test_allocator_duration():
    a = TrafficAllocator().allocate(_exp())
    assert a["duration_days"] == 7


def test_allocator_guardrail():
    a = TrafficAllocator().allocate(_exp())
    assert a["guardrail"] == "arpdau"


def test_evaluator_winner():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    assert r.decision == "WINNER" and r.winner is True


def test_evaluator_loser():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    for row in rows:
        if row["day"] > "2026-07-18" and row["network"] == "MINT_BIDDING":
            row["estimated_revenue"] = 1.0
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    assert r.decision == "LOSER"


def test_evaluator_unknown_not_applied():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        None, "pending")
    assert r.decision == "UNKNOWN"


def test_evaluator_unknown_within_noise():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    for row in rows:
        if row["day"] > "2026-07-18" and row["network"] == "MINT_BIDDING":
            row["estimated_revenue"] = 10.1
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    assert r.decision == "UNKNOWN"


def test_evaluator_net_impact_passthrough():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    assert r.lift is not None and r.lift > 0


def test_evaluator_guardrail_regression():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "regression")
    assert r.decision == "LOSER"


def test_evaluator_lift_equals_net():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    assert r.lift == r.lift  # identity; ensures field set


def test_experiment_result_to_dict():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    d = r.to_dict()
    assert d["decision"] == "WINNER" and "lift" in d


def test_planner_empty_for_no_signals():
    exps = ExperimentPlanner().plan(report(signals=[]))
    assert exps == []


def test_allocator_uses_exp_days():
    a = TrafficAllocator().allocate(_exp())
    assert a["min_days"] == 3 and a["max_days"] == 14


def test_evaluator_zero_baseline_winner():
    rows = max_rows("MINT_BIDDING", "2026-07-18")
    for row in rows:
        if row["day"] < "2026-07-18" and row["network"] == "MINT_BIDDING":
            row["estimated_revenue"] = 0.0
    r = ExperimentEvaluator().evaluate(rows, _exp("MINT_BIDDING"),
                                        "2026-07-18", "pass")
    assert r.decision == "WINNER"


def test_planner_detector_exp_id_matches():
    rep = report(signals=[winner_sig()])
    opps = OpportunityDetector().detect(rep)
    exp = ExperimentPlanner().plan_one(opps[0], rep)
    assert exp.exp_id == opps[0].id
