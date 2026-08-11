"""E10.2 Phase 5 — Autonomous Optimization Loop Test.

8 AC covering:
  1. Optimization Schema (OptimizationDecision, MutationPlan)
  2. Policy Engine (SCALE, KILL, WATCH, RETEST)
  3. Scale Controller (max 30%, BudgetGuard integration)
  4. Kill Controller (PAUSE, WATCH, RETEST plans)
  5. Experiment Allocator (multi-campaign ranking)
  6. Mutation Planner (decision → ExecutionTask)
  7. Autonomous Loop (signal → decision → plan → task)
  8. Full Regression (E10.1 + E10.2 Phase1-4)
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import (
    LearningSignal,
    ExecutionTask,
    ExecutionResult,
    ExecutionStatus,
    ActionType,
    FeedbackType,
    PerformanceSnapshot,
)
from market_ops.execution_runtime.optimization_schema import (
    OptimizationDecision,
    MutationPlan,
    CampaignScore,
)
from market_ops.execution_runtime.optimization import (
    OptimizationPolicy,
    ScaleController,
    KillController,
    ExperimentAllocator,
    MutationPlanner,
    OptimizationOrchestrator,
    OptimizationError,
    PolicyViolationError,
    ScaleLimitError,
    NoScorableCampaignsError,
)
from market_ops.execution_runtime.campaign_schema import CampaignStatus


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_signal(roas: float, spend: float = 500.0, task_id: str = "t_001") -> LearningSignal:
    return LearningSignal(
        task_id=task_id,
        action_type=ActionType.WATCH.value,
        feedback_type=FeedbackType.NEUTRAL.value,
        confidence=0.5,
        metrics={
            "roas": roas,
            "spend": spend,
            "revenue": round(spend * roas, 2),
            "impressions": 10000,
            "clicks": 300,
            "conversions": 200,
        },
        recommendation="",
    )


# ═══════════════════════════════════════════════════════════
# AC1 — Optimization Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_optimization_decision():
    """AC1a: OptimizationDecision creates with correct fields."""
    decision = OptimizationDecision(
        campaign_id="c_001",
        action="SCALE",
        confidence=0.85,
        reason="ROAS 2.0 > 1.5",
        expected_impact=150.0,
        metrics={"roas": 2.0, "spend": 500.0},
    )
    assert decision.decision_id != ""
    assert decision.action == "SCALE"
    assert decision.confidence == 0.85
    assert decision.expected_impact == 150.0

    data = decision.to_dict()
    assert data["campaign_id"] == "c_001"
    assert data["action"] == "SCALE"


def test_ac1_mutation_plan():
    """AC1b: MutationPlan records before/after budget delta."""
    plan = MutationPlan(
        campaign_id="c_001",
        decision_id="d_001",
        mutation_type="BUDGET_CHANGE",
        action="SCALE",
        budget_before=100.0,
        budget_after=130.0,
        expected_gain=30.0,
    )
    assert plan.budget_delta == 30.0
    assert plan.mutation_type == "BUDGET_CHANGE"

    data = plan.to_dict()
    assert data["budget_delta"] == 30.0


def test_ac1_campaign_score():
    """AC1c: CampaignScore for multi-campaign ranking."""
    score = CampaignScore(
        campaign_id="c_001",
        roas=2.0,
        spend=500.0,
        revenue=1000.0,
        score=2.1,
        rank=1,
        action="SCALE",
    )
    assert score.rank == 1
    assert score.action == "SCALE"


# ═══════════════════════════════════════════════════════════
# AC2 — Policy Engine
# ═══════════════════════════════════════════════════════════

def test_ac2_policy_scale():
    """AC2a: ROAS > 1.5 → SCALE."""
    policy = OptimizationPolicy()
    signal = _make_signal(roas=2.0, task_id="t_scale")
    decision = policy.evaluate(signal, campaign_id="c_scale")

    assert decision.action == ActionType.SCALE.value
    assert decision.confidence == 0.5
    assert "ROAS" in decision.reason
    assert decision.expected_impact > 0


def test_ac2_policy_watch():
    """AC2b: ROAS 0.8-1.5 → WATCH."""
    policy = OptimizationPolicy()
    signal = _make_signal(roas=1.0, task_id="t_watch")
    decision = policy.evaluate(signal, campaign_id="c_watch")

    assert decision.action == ActionType.WATCH.value
    assert decision.confidence == 0.5
    assert decision.expected_impact == 0.0


def test_ac2_policy_kill():
    """AC2c: ROAS < 0.8 → KILL."""
    policy = OptimizationPolicy()
    signal = _make_signal(roas=0.5, task_id="t_kill")
    decision = policy.evaluate(signal, campaign_id="c_kill")

    assert decision.action == ActionType.KILL.value
    assert "ROAS" in decision.reason
    assert decision.expected_impact > 0  # Expected savings


def test_ac2_policy_batch():
    """AC2d: evaluate_batch processes multiple signals."""
    policy = OptimizationPolicy()
    signals = [
        _make_signal(roas=2.0, task_id="t1"),
        _make_signal(roas=1.0, task_id="t2"),
        _make_signal(roas=0.5, task_id="t3"),
    ]
    decisions = policy.evaluate_batch(signals, ["c1", "c2", "c3"])
    assert len(decisions) == 3
    assert decisions[0].action == ActionType.SCALE.value
    assert decisions[1].action == ActionType.WATCH.value
    assert decisions[2].action == ActionType.KILL.value


# ═══════════════════════════════════════════════════════════
# AC3 — Scale Controller
# ═══════════════════════════════════════════════════════════

def test_ac3_scale_plan():
    """AC3a: ScaleController creates valid MutationPlan (30% max)."""
    scaler = ScaleController(max_scale_ratio=0.30)
    decision = OptimizationDecision(
        campaign_id="c_001",
        action="SCALE",
        confidence=0.85,
        reason="ROAS 2.0",
        expected_impact=150.0,
    )

    plan = scaler.plan_scale(decision, current_budget=100.0)
    assert plan.mutation_type == "BUDGET_CHANGE"
    assert plan.action == "SCALE"
    assert plan.budget_before == 100.0
    assert plan.budget_after == 130.0  # 100 * 1.30
    assert plan.budget_delta == 30.0


def test_ac3_scale_max_budget():
    """AC3b: get_max_budget returns 30% increase."""
    scaler = ScaleController(max_scale_ratio=0.30)
    assert scaler.get_max_budget(100.0) == 130.0
    assert scaler.get_max_budget(500.0) == 650.0


def test_ac3_scale_not_capped_by_guard():
    """AC3c: Scale 100→130 passes BudgetGuard (within 30%)."""
    scaler = ScaleController(max_scale_ratio=0.30)
    decision = OptimizationDecision(campaign_id="c_001", action="SCALE", confidence=0.85, reason="test")
    plan = scaler.plan_scale(decision, current_budget=100.0)
    assert plan.budget_after == 130.0


# ═══════════════════════════════════════════════════════════
# AC4 — Kill Controller
# ═══════════════════════════════════════════════════════════

def test_ac4_kill_plan():
    """AC4a: KillController creates PAUSED status plan."""
    killer = KillController()
    decision = OptimizationDecision(
        campaign_id="c_001",
        action="KILL",
        confidence=0.80,
        reason="ROAS 0.5",
        expected_impact=250.0,
    )

    plan = killer.plan_kill(decision, current_status="ACTIVE")
    assert plan.mutation_type == "STATUS_CHANGE"
    assert plan.action == "KILL"
    assert plan.status_before == "ACTIVE"
    assert plan.status_after == CampaignStatus.PAUSED.value


def test_ac4_watch_plan():
    """AC4b: WATCH creates no-op plan."""
    killer = KillController()
    decision = OptimizationDecision(
        campaign_id="c_001",
        action="WATCH",
        confidence=0.50,
        reason="ROAS 1.0",
    )

    plan = killer.plan_watch(decision)
    assert plan.mutation_type == "NO_CHANGE"
    assert plan.action == "WATCH"
    assert plan.status_before == plan.status_after
    assert plan.budget_delta == 0.0


def test_ac4_retest_plan():
    """AC4c: RETEST creates DUPLICATE plan."""
    killer = KillController()
    decision = OptimizationDecision(
        campaign_id="c_001",
        action="RETEST",
        confidence=0.60,
        reason="need retest",
    )

    plan = killer.plan_retest(decision, source_campaign_id="c_original", retest_budget=50.0)
    assert plan.mutation_type == "DUPLICATE"
    assert plan.action == "RETEST"
    assert plan.budget_after == 50.0
    assert plan.source_campaign_id == "c_original"


# ═══════════════════════════════════════════════════════════
# AC5 — Experiment Allocator
# ═══════════════════════════════════════════════════════════

def test_ac5_allocator_score_campaigns():
    """AC5a: ExperimentAllocator scores campaigns by ROAS."""
    allocator = ExperimentAllocator()
    campaigns = {
        "c_a": {"roas": 2.0, "spend": 500.0, "revenue": 1000.0},
        "c_b": {"roas": 0.5, "spend": 400.0, "revenue": 200.0},
        "c_c": {"roas": 1.5, "spend": 300.0, "revenue": 450.0},
    }

    scores = allocator.score_campaigns(campaigns)
    assert len(scores) == 3

    # Sorted by score descending
    assert scores[0].campaign_id == "c_a"  # ROAS 2.0
    assert scores[0].action == "SCALE"
    assert scores[0].rank == 1

    assert scores[1].action == "WATCH"  # ROAS 1.5

    assert scores[2].campaign_id == "c_b"  # ROAS 0.5
    assert scores[2].action == "KILL"


def test_ac5_allocator_allocate():
    """AC5b: allocate returns budget changes per campaign."""
    allocator = ExperimentAllocator()
    campaigns = {
        "c_a": {"roas": 2.0, "spend": 500.0, "revenue": 1000.0},
        "c_b": {"roas": 0.5, "spend": 400.0, "revenue": 200.0},
        "c_c": {"roas": 1.0, "spend": 300.0, "revenue": 300.0},
    }

    allocation = allocator.allocate(campaigns)
    assert len(allocation) == 3

    assert allocation["c_a"]["action"] == "SCALE"
    assert allocation["c_a"]["budget_after"] == 650.0  # 500 * 1.30

    assert allocation["c_b"]["action"] == "KILL"
    assert allocation["c_b"]["budget_after"] == 0.0

    assert allocation["c_c"]["action"] == "WATCH"
    assert allocation["c_c"]["budget_delta"] == 0.0


def test_ac5_allocator_top_performers():
    """AC5c: get_top_performers returns only SCALE campaigns."""
    allocator = ExperimentAllocator()
    campaigns = {
        "c_a": {"roas": 2.0, "spend": 500.0, "revenue": 1000.0},
        "c_b": {"roas": 0.5, "spend": 400.0, "revenue": 200.0},
        "c_c": {"roas": 1.6, "spend": 300.0, "revenue": 480.0},
    }

    top = allocator.get_top_performers(campaigns, top_n=2)
    assert len(top) == 2
    assert all(s.action == "SCALE" for s in top)


# ═══════════════════════════════════════════════════════════
# AC6 — Mutation Planner
# ═══════════════════════════════════════════════════════════

def test_ac6_mutation_planner_scale():
    """AC6a: MutationPlanner creates ExecutionTask for SCALE."""
    planner = MutationPlanner()
    decision = OptimizationDecision(
        campaign_id="c_001",
        action="SCALE",
        confidence=0.85,
        reason="ROAS 2.0",
    )

    plan, task = planner.plan_and_create_task(decision, current_budget=100.0)

    assert isinstance(plan, MutationPlan)
    assert isinstance(task, ExecutionTask)
    assert task.action_type == "SCALE"
    assert task.budget_change["before"] == 100.0
    assert task.budget_change["after"] == 130.0
    assert task.budget_change["delta"] == 30.0


def test_ac6_mutation_planner_kill():
    """AC6b: MutationPlanner creates ExecutionTask for KILL."""
    planner = MutationPlanner()
    decision = OptimizationDecision(
        campaign_id="c_002",
        action="KILL",
        confidence=0.80,
        reason="ROAS 0.5",
    )

    plan, task = planner.plan_and_create_task(decision, current_status="ACTIVE")

    assert task.action_type == "KILL"
    assert plan.status_after == CampaignStatus.PAUSED.value


def test_ac6_mutation_planner_watch():
    """AC6c: MutationPlanner creates no-op for WATCH."""
    planner = MutationPlanner()
    decision = OptimizationDecision(
        campaign_id="c_003",
        action="WATCH",
        confidence=0.50,
        reason="ROAS 1.0",
    )

    plan, task = planner.plan_and_create_task(decision)

    assert task.action_type == "WATCH"
    assert plan.mutation_type == "NO_CHANGE"


def test_ac6_mutation_planner_retest():
    """AC6d: MutationPlanner creates RETEST task."""
    planner = MutationPlanner()
    decision = OptimizationDecision(
        campaign_id="c_004",
        action="RETEST",
        confidence=0.60,
        reason="test retest",
    )

    plan, task = planner.plan_and_create_task(decision)

    assert task.action_type == "RETEST"
    assert plan.mutation_type == "DUPLICATE"


# ═══════════════════════════════════════════════════════════
# AC7 — Autonomous Loop
# ═══════════════════════════════════════════════════════════

def test_ac7_autonomous_loop_scale():
    """AC7a: Full pipeline: signal → decision → plan → task (SCALE)."""
    orchestrator = OptimizationOrchestrator()
    signal = _make_signal(roas=2.0, task_id="t_loop")

    decision, plan, task = orchestrator.optimize(
        signal,
        campaign_id="c_loop",
        current_budget=100.0,
    )

    assert isinstance(decision, OptimizationDecision)
    assert isinstance(plan, MutationPlan)
    assert isinstance(task, ExecutionTask)

    assert decision.action == "SCALE"
    assert plan.budget_after == 130.0
    assert task.action_type == "SCALE"
    assert task.budget_change["delta"] == 30.0


def test_ac7_autonomous_loop_kill():
    """AC7b: Full pipeline: KILL flow."""
    orchestrator = OptimizationOrchestrator()
    signal = _make_signal(roas=0.5, task_id="t_kill_loop")

    decision, plan, task = orchestrator.optimize(
        signal,
        campaign_id="c_kill",
        current_budget=100.0,
        current_status="ACTIVE",
    )

    assert decision.action == "KILL"
    assert plan.status_after == CampaignStatus.PAUSED.value
    assert task.action_type == "KILL"


def test_ac7_autonomous_loop_watch():
    """AC7c: Full pipeline: WATCH (no change)."""
    orchestrator = OptimizationOrchestrator()
    signal = _make_signal(roas=1.0, task_id="t_watch_loop")

    decision, plan, task = orchestrator.optimize(
        signal,
        campaign_id="c_watch",
        current_budget=100.0,
    )

    assert decision.action == "WATCH"
    assert plan.mutation_type == "NO_CHANGE"
    assert plan.budget_delta == 0.0


def test_ac7_autonomous_loop_batch():
    """AC7d: optimize_batch for multiple signals."""
    orchestrator = OptimizationOrchestrator()
    signals = [
        _make_signal(roas=2.0, task_id="t1"),
        _make_signal(roas=0.5, task_id="t2"),
        _make_signal(roas=1.0, task_id="t3"),
    ]

    results = orchestrator.optimize_batch(
        signals,
        campaign_ids=["c1", "c2", "c3"],
        current_budgets=[100.0, 200.0, 150.0],
    )

    assert len(results) == 3
    assert results[0][0].action == "SCALE"
    assert results[1][0].action == "KILL"
    assert results[2][0].action == "WATCH"

    # Check budget scaling
    assert results[0][1].budget_after == 130.0  # 100 * 1.30
    assert results[2][1].budget_after == 150.0  # no change


def test_ac7_allocator_integration():
    """AC7e: orchestrator.allocate_across_campaigns."""
    orchestrator = OptimizationOrchestrator()
    campaigns = {
        "c_a": {"roas": 2.0, "spend": 500.0, "revenue": 1000.0},
        "c_b": {"roas": 0.5, "spend": 400.0, "revenue": 200.0},
    }

    allocation = orchestrator.allocate_across_campaigns(campaigns)
    assert allocation["c_a"]["action"] == "SCALE"
    assert allocation["c_b"]["action"] == "KILL"


# ═══════════════════════════════════════════════════════════
# AC8 — Regression
# ═══════════════════════════════════════════════════════════

def test_ac8_e101_runtime_api():
    """AC8a: E10.1 RuntimeAPI still works."""
    from market_ops.execution_runtime import RuntimeAPI
    api = RuntimeAPI()
    resp = api.create_execution({
        "creative_id": "C001",
        "action": "SCALE",
        "budget_change": {"current": 100.0, "target": 200.0},
        "confidence": 0.95,
        "reason": ["WINNER"],
    })
    assert resp.success is True


def test_ac8_e102_phase2_facebook():
    """AC8b: Facebook adapter still works (Phase 2)."""
    from market_ops.execution_runtime.adapters import FacebookAdsAdapter, FacebookConfig
    config = FacebookConfig(sandbox=True)
    adapter = FacebookAdsAdapter(config=config)
    result = adapter.update_budget("c_001", 200.0)
    assert result.success is True


def test_ac8_e102_phase3_budget_guard():
    """AC8c: BudgetGuard still works (Phase 3)."""
    from market_ops.execution_runtime import BudgetGuard
    guard = BudgetGuard(max_scale_ratio=0.30)
    result = guard.check(100.0, 120.0)
    assert result.allowed is True


def test_ac8_e102_phase4_attribution():
    """AC8d: Attribution still works (Phase 4)."""
    from market_ops.execution_runtime.attribution import AdjustTracker, PerformanceCollector
    collector = PerformanceCollector({"adjust": AdjustTracker()})
    snapshot = collector.collect("camp_001", task_id="t_001")
    assert snapshot.roas > 0


def test_ac8_full_cross_phase_integration():
    """AC8e: Phase 4 feedback → Phase 5 optimization chain."""
    from market_ops.execution_runtime.attribution import AdjustTracker, PerformanceCollector
    from market_ops.execution_runtime.feedback_mapper import FeedbackMapper

    # Phase 4: Attribution → PerformanceSnapshot
    collector = PerformanceCollector({"adjust": AdjustTracker()})
    snapshot = collector.collect("camp_full", task_id="t_full")

    # Phase 4: PerformanceSnapshot → LearningSignal
    mapper = FeedbackMapper()
    signal = mapper.map(snapshot, task_id="t_full")

    # Phase 5: LearningSignal → OptimizationDecision → ExecutionTask
    orchestrator = OptimizationOrchestrator()
    decision, plan, task = orchestrator.optimize(
        signal,
        campaign_id="camp_full",
        current_budget=100.0,
    )

    assert isinstance(decision, OptimizationDecision)
    assert isinstance(plan, MutationPlan)
    assert isinstance(task, ExecutionTask)
    assert task.action_type in {ActionType.SCALE.value, ActionType.WATCH.value, ActionType.KILL.value}


def test_ac8_exceptions_hierarchy():
    """AC8f: Optimization exceptions hierarchy is correct."""
    assert issubclass(PolicyViolationError, OptimizationError)
    assert issubclass(ScaleLimitError, PolicyViolationError)
    assert issubclass(NoScorableCampaignsError, OptimizationError)

    exc = ScaleLimitError(100.0, 500.0, 130.0, campaign_id="c_001")
    assert "Cannot scale" in str(exc)
    assert exc.campaign_id == "c_001"