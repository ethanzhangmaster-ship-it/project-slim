"""E16.1.1 — Revenue Decision Loop: policy gate, validator routing,
experience memory, simulator, and the closed-loop agent integration."""
from pathlib import Path

from src.revenue_intelligence.agent import RevenueIntelligenceAgent
from src.revenue_intelligence.decision.policy import (
    ApprovalRoute,
    DecisionPolicy,
    ImpactLevel,
    RiskLevel,
)
from src.revenue_intelligence.decision.validator import (
    DecisionValidator,
    JsonlApprovalQueue,
)
from src.revenue_intelligence.executor import InMemoryGrowthActionSink
from src.revenue_intelligence.experience import (
    JsonlRevenueExperienceStore,
    RevenueExperience,
    RevenuePoint,
    compute_reward,
)
from src.revenue_intelligence.models import (
    GrowthAction,
    RevenueAction,
    RevenueSnapshot,
)
from src.revenue_intelligence.simulator import RevenueSimulator
from tests.e16_1.fixtures import high_roas_pair


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def mk_action(
    action=RevenueAction.INCREASE_UA_BUDGET,
    confidence=0.95,
    impact_score=80.0,
    game_id="game_x",
    evidence=None,
):
    return GrowthAction(
        game_id=game_id,
        action=action,
        title="t",
        rationale="r",
        evidence=evidence or {},
        confidence=confidence,
        impact_score=impact_score,
    )


# --------------------------------------------------------------------------- #
# 1. Decision Policy — three-tier confidence gate
# --------------------------------------------------------------------------- #
def test_high_conf_low_risk_auto():
    p = DecisionPolicy()
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.95, impact_score=80.0)
    s = p.score(a, sample_size=10, success_rate=0.9)
    assert s.approval == ApprovalRoute.AUTO
    assert s.risk == RiskLevel.LOW
    assert s.impact == ImpactLevel.HIGH


def test_high_conf_insufficient_sample_human():
    p = DecisionPolicy()
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.95)
    s = p.score(a, sample_size=2, success_rate=0.9)
    assert s.approval == ApprovalRoute.HUMAN_QUEUE


def test_high_conf_high_risk_human():
    p = DecisionPolicy()
    a = mk_action(RevenueAction.MODIFY_PRICE, confidence=0.95, impact_score=85.0)
    assert p.score(a, sample_size=10).risk == RiskLevel.HIGH
    assert p.score(a, sample_size=10).approval == ApprovalRoute.HUMAN_QUEUE


def test_mid_conf_human():
    p = DecisionPolicy()
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.8)
    assert p.score(a, sample_size=10).approval == ApprovalRoute.HUMAN_QUEUE


def test_low_conf_record_only():
    p = DecisionPolicy()
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.5)
    assert p.score(a, sample_size=10).approval == ApprovalRoute.RECORD_ONLY


def test_risk_downgrade_on_winning_history():
    p = DecisionPolicy()
    # ROLLBACK_VERSION is HIGH risk by default
    a = mk_action(RevenueAction.ROLLBACK_VERSION, confidence=0.95, impact_score=80.0)
    s = p.score(a, sample_size=5, success_rate=0.9)
    # proven winner -> one notch down (HIGH -> MEDIUM)
    assert s.risk == RiskLevel.MEDIUM


# --------------------------------------------------------------------------- #
# 2. Validator — route enforcement + audit + approval queue
# --------------------------------------------------------------------------- #
def test_auto_submits_to_sink(tmp_path):
    sink = InMemoryGrowthActionSink()
    v = DecisionValidator(policy=DecisionPolicy(), action_sink=sink)
    d = v.validate(
        mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.95),
        experience_stats={"n": 10, "success_rate": 0.9},
    )
    assert d.approval == ApprovalRoute.AUTO
    assert d.executed is True
    assert len(sink.submitted) == 1


def test_human_queued(tmp_path):
    q = JsonlApprovalQueue(str(tmp_path / "q.jsonl"))
    v = DecisionValidator(policy=DecisionPolicy(), approval_queue=q)
    d = v.validate(
        mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.8),
        experience_stats={"n": 10},
    )
    assert d.approval == ApprovalRoute.HUMAN_QUEUE
    assert d.queued is True
    assert len(q.pending()) == 1


def test_record_only_neither(tmp_path):
    sink = InMemoryGrowthActionSink()
    q = JsonlApprovalQueue(str(tmp_path / "q.jsonl"))
    v = DecisionValidator(policy=DecisionPolicy(), action_sink=sink, approval_queue=q)
    d = v.validate(
        mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.5),
        experience_stats={"n": 10},
    )
    assert d.approval == ApprovalRoute.RECORD_ONLY
    assert d.executed is False and d.queued is False
    assert len(sink.submitted) == 0
    assert len(q.pending()) == 0


def test_approve_executes(tmp_path):
    sink = InMemoryGrowthActionSink()
    q = JsonlApprovalQueue(str(tmp_path / "q.jsonl"))
    v = DecisionValidator(policy=DecisionPolicy(), action_sink=sink, approval_queue=q)
    d = v.validate(
        mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.8),
        experience_stats={"n": 10},
    )
    assert len(q.pending()) == 1
    assert v.approve(d.audit_id) is True
    assert len(sink.submitted) == 1
    # idempotent: cannot approve twice
    assert v.approve(d.audit_id) is False


def test_reject_not_executed(tmp_path):
    sink = InMemoryGrowthActionSink()
    q = JsonlApprovalQueue(str(tmp_path / "q.jsonl"))
    v = DecisionValidator(policy=DecisionPolicy(), action_sink=sink, approval_queue=q)
    d = v.validate(
        mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.8),
        experience_stats={"n": 10},
    )
    assert v.reject(d.audit_id) is True
    assert len(sink.submitted) == 0


# --------------------------------------------------------------------------- #
# 3. Revenue Experience Memory
# --------------------------------------------------------------------------- #
def test_compute_reward_roas_primary():
    before = RevenuePoint(roas=1.0, revenue_total=1000, spend=1000)
    after = RevenuePoint(roas=1.2, revenue_total=1200, spend=1000)
    exp = RevenueExperience("g", RevenueAction.INCREASE_UA_BUDGET, "r", before, after)
    reward, success = compute_reward(exp)
    assert abs(reward - 0.2) < 1e-6
    assert success is True


def test_compute_reward_revenue_fallback():
    # ROAS not computable (spend 0) -> fall back to revenue lift
    before = RevenuePoint(roas=0.0, revenue_total=1000, spend=0)
    after = RevenuePoint(roas=0.0, revenue_total=1200, spend=0)
    exp = RevenueExperience("g", RevenueAction.CREATE_OFFER, "r", before, after)
    reward, success = compute_reward(exp)
    assert abs(reward - 0.2) < 1e-6
    assert success is True


def test_store_stats(tmp_path):
    store = JsonlRevenueExperienceStore(str(tmp_path / "exp.jsonl"))
    before = RevenuePoint(roas=1.0, revenue_total=1000, spend=1000)
    after_win = RevenuePoint(roas=1.2, revenue_total=1200, spend=1000)
    after_loss = RevenuePoint(roas=0.9, revenue_total=900, spend=1000)
    store.add(RevenueExperience("g", RevenueAction.INCREASE_UA_BUDGET, "r", before, after_win))
    store.add(RevenueExperience("g", RevenueAction.INCREASE_UA_BUDGET, "r", before, after_loss))
    stats = store.stats("g", RevenueAction.INCREASE_UA_BUDGET)
    assert stats["n"] == 2
    assert abs(stats["success_rate"] - 0.5) < 1e-6
    assert abs(stats["avg_reward"] - 0.05) < 1e-6  # (0.2 + -0.1)/2


# --------------------------------------------------------------------------- #
# 4. Revenue Simulator
# --------------------------------------------------------------------------- #
def test_simulate_increase_budget_20pct():
    sim = RevenueSimulator()
    cur = RevenueSnapshot(game_id="g", date="P1", revenue_total=10000, spend=5000, roas=2.0)
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.9)
    res = sim.simulate(a, cur, magnitude_pct=20.0)
    assert res.expected_spend_pct == 20.0
    assert res.expected_revenue_pct == 15.0  # elasticity 0.75 * 20
    assert abs(res.expected_roas - 2.0 * 1.15 / 1.20) < 1e-6
    assert res.confidence == 0.74  # base, no experience


def test_simulate_example_matches_spec():
    # "increase Meta Facebook budget 20%" -> ROAS ~1.32, conf 0.74
    sim = RevenueSimulator()
    cur = RevenueSnapshot(game_id="g", date="P1", revenue_total=1377, spend=1000, roas=1.377)
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.9)
    res = sim.simulate(a, cur, magnitude_pct=20.0)
    assert res.expected_spend_pct == 20.0
    assert res.expected_revenue_pct == 15.0
    assert abs(res.expected_roas - 1.32) < 0.01
    assert res.confidence == 0.74


def test_simulate_uses_experience_to_calibrate():
    sim = RevenueSimulator()
    cur = RevenueSnapshot(game_id="g", date="P1", revenue_total=10000, spend=5000, roas=2.0)
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.9)
    res = sim.simulate(
        a, cur, magnitude_pct=10.0, experience_stats={"n": 5, "avg_reward": 0.1}
    )
    assert res.confidence > 0.74  # boost from samples + positive reward


# --------------------------------------------------------------------------- #
# 5. Closed-loop agent integration
# --------------------------------------------------------------------------- #
def test_agent_decision_loop_routes(tmp_path):
    sink = InMemoryGrowthActionSink()
    q = JsonlApprovalQueue(str(tmp_path / "q.jsonl"))
    exp_store = JsonlRevenueExperienceStore(str(tmp_path / "exp.jsonl"))
    agent = RevenueIntelligenceAgent(
        action_sink=sink,
        simulator=RevenueSimulator(),
        experience_store=exp_store,
        approval_queue=q,
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    prev, cur = high_roas_pair()
    report = agent.analyze_and_decide(cur, prev)
    assert report.decisions
    routes = {d.approval for d in report.decisions}
    assert routes <= {
        ApprovalRoute.AUTO,
        ApprovalRoute.HUMAN_QUEUE,
        ApprovalRoute.RECORD_ONLY,
    }
    # high_roas_pair -> INCREASE_UA_BUDGET (conf 0.75) -> HUMAN_QUEUE
    assert len(q.pending()) >= 1
    assert "gated" in report.summary


def test_agent_closed_loop_records_and_learns(tmp_path):
    sink = InMemoryGrowthActionSink()
    exp_store = JsonlRevenueExperienceStore(str(tmp_path / "exp.jsonl"))
    agent = RevenueIntelligenceAgent(
        action_sink=sink,
        simulator=RevenueSimulator(),
        experience_store=exp_store,
    )
    prev, cur = high_roas_pair()

    # record 5 winning outcomes for INCREASE_UA_BUDGET (enough to auto-gate)
    before = RevenuePoint.from_snapshot(prev)
    after = RevenuePoint.from_snapshot(cur)
    for _ in range(5):
        exp = agent.record_outcome(
            GrowthAction(
                game_id="game_x",
                action=RevenueAction.INCREASE_UA_BUDGET,
                title="t",
                rationale="r",
            ),
            before,
            after,
            reason="scaled budget",
        )
        assert exp.success is True  # ROAS 3.0 -> 4.0
    stats = exp_store.stats("game_x", RevenueAction.INCREASE_UA_BUDGET)
    assert stats["n"] == 5
    assert stats["success_rate"] == 1.0

    # experience now feeds the policy: proven INCREASE_UA_BUDGET stays low-risk
    policy = DecisionPolicy()
    a = mk_action(RevenueAction.INCREASE_UA_BUDGET, confidence=0.95, impact_score=80.0)
    score = policy.score(a, sample_size=stats["n"], success_rate=stats["success_rate"])
    assert score.risk == RiskLevel.LOW
    assert score.approval == ApprovalRoute.AUTO


def test_agent_decision_report_markdown(tmp_path):
    q = JsonlApprovalQueue(str(tmp_path / "q.jsonl"))
    agent = RevenueIntelligenceAgent(
        simulator=RevenueSimulator(),
        experience_store=JsonlRevenueExperienceStore(str(tmp_path / "exp.jsonl")),
        approval_queue=q,
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    prev, cur = high_roas_pair()
    md = agent.analyze_and_decide(cur, prev).to_markdown()
    assert "Revenue Decision Loop" in md
    assert "sim:" in md  # simulation block rendered
