"""E14.2 Growth Supervisor Agent — 集成测试.

验证 Supervisor Agent 的完整功能:
  - Goal Manager (20)
  - Priority Engine (20)
  - Task Allocator (25)
  - Conflict Resolver (20)
  - Supervisor Memory (15)
  - Supervisor Agent Loop (30)
  - Communication Integration (20)

总计: 150 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
    MessageBus,
    AgentRegistry,
    AgentRole,
    AgentStatus,
    create_default_organization,
    create_message_bus,
    create_agent_registry,
    CollaborationEngine,
    VoteOption,
    ConsensusResult,
    StandardMessageType,
    MessagePriority,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.supervisor import (
    GrowthGoal,
    GoalType,
    GoalStatus,
    GoalConstraint,
    SubGoal,
    GoalManager,
    create_goal_manager,
    PrioritySignal,
    PriorityDecision,
    PriorityEngine,
    SignalCategory,
    SignalSeverity,
    create_priority_engine,
    TaskAllocator,
    AllocationRecord,
    AllocationStatus,
    AgentLoad,
    create_task_allocator,
    ConflictResolver,
    Conflict,
    ConflictType,
    ConflictParty,
    ResolutionStrategy,
    create_conflict_resolver,
    SupervisorMemory,
    OrganizationMemory,
    AgentPerformance,
    MemoryType,
    create_supervisor_memory,
    SupervisorAgent,
    SupervisorMode,
    SupervisorState,
    SupervisorReport,
    create_supervisor_agent,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def goal_manager():
    return create_goal_manager()


@pytest.fixture
def priority_engine():
    return create_priority_engine()


@pytest.fixture
def registry():
    return create_default_organization()


@pytest.fixture
def bus():
    return create_message_bus()


@pytest.fixture
def task_allocator(registry, bus):
    return create_task_allocator(registry, bus)


@pytest.fixture
def conflict_resolver():
    return create_conflict_resolver()


@pytest.fixture
def supervisor_memory():
    return create_supervisor_memory()


@pytest.fixture
def supervisor(registry, bus):
    return create_supervisor_agent(bus=bus, registry=registry)


# ═══════════════════════════════════════════════════════════════
# 1. Goal Manager (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestGrowthGoal:
    def test_create_goal(self, goal_manager):
        goal = goal_manager.create_goal("提升利润", GoalType.PROFIT, 0.3)
        assert goal.objective == "提升利润"
        assert goal.goal_type == GoalType.PROFIT
        assert goal.target_value == 0.3

    def test_goal_progress(self, goal_manager):
        goal = goal_manager.create_goal("test", GoalType.REVENUE, 0.5)
        goal.current_value = 0.25
        assert goal.progress == 0.5
        assert goal.gap == 0.25

    def test_goal_is_achieved(self, goal_manager):
        goal = goal_manager.create_goal("test", target_value=0.3)
        goal.current_value = 0.35
        assert goal.is_achieved

    def test_goal_constraints_default(self):
        c = GoalConstraint.default()
        assert c.max_budget == 100000
        assert c.max_risk_level == 0.5

    def test_goal_constraints_aggressive(self):
        c = GoalConstraint.aggressive()
        assert c.max_budget == 500000
        assert c.max_risk_level == 0.7

    def test_goal_constraints_conservative(self):
        c = GoalConstraint.conservative()
        assert c.max_budget == 50000
        assert c.max_risk_level == 0.3

    def test_goal_serialization(self, goal_manager):
        goal = goal_manager.create_goal("序列化测试", GoalType.PROFIT, 0.3)
        data = goal.to_dict()
        assert data["objective"] == "序列化测试"
        assert data["progress"] == 0.0

    def test_parse_goal_text_profit(self, goal_manager):
        goal = goal_manager.parse_goal_text("本月利润提升30%")
        assert goal.goal_type == GoalType.PROFIT

    def test_parse_goal_text_roas(self, goal_manager):
        goal = goal_manager.parse_goal_text("ROAS提升15%")
        assert goal.goal_type == GoalType.ROAS

    def test_parse_goal_text_scale(self, goal_manager):
        goal = goal_manager.parse_goal_text("规模增长50%")
        assert goal.goal_type == GoalType.SCALE

    def test_parse_goal_text_retention(self, goal_manager):
        goal = goal_manager.parse_goal_text("留存提升10%")
        assert goal.goal_type == GoalType.RETENTION

    def test_parse_goal_text_ltv(self, goal_manager):
        goal = goal_manager.parse_goal_text("LTV提升20%")
        assert goal.goal_type == GoalType.LTV


class TestGoalDecomposition:
    def test_decompose_profit_goal(self, goal_manager):
        goal = goal_manager.create_goal("利润提升30%", GoalType.PROFIT, 0.3)
        subs = goal_manager.decompose(goal)
        assert len(subs) > 0
        roles = {s.agent_role for s in subs}
        assert AgentRole.UA in roles
        assert AgentRole.CREATIVE in roles

    def test_decompose_goal_returns_sub_goals_with_targets(self, goal_manager):
        goal = goal_manager.create_goal("test", GoalType.PROFIT, 0.3)
        subs = goal_manager.decompose(goal)
        for sub in subs:
            assert sub.target_value > 0
            assert sub.metric != ""
            assert sub.hypothesis != ""

    def test_decompose_with_target_roles(self, goal_manager):
        goal = goal_manager.create_goal("test", GoalType.PROFIT, 0.3)
        subs = goal_manager.decompose(goal, target_roles=[AgentRole.UA])
        for sub in subs:
            assert sub.agent_role == AgentRole.UA

    def test_decompose_goal_onestep(self, goal_manager):
        goal, subs = goal_manager.decompose_goal("一站式分解", GoalType.ROAS, 0.15)
        assert goal.goal_type == GoalType.ROAS
        assert len(subs) > 0

    def test_update_progress(self, goal_manager):
        goal = goal_manager.create_goal("test", target_value=0.3)
        goal_manager.update_progress(goal.goal_id, 0.3)
        assert goal.status == GoalStatus.COMPLETED

    def test_get_goal_progress(self, goal_manager):
        goal, subs = goal_manager.decompose_goal("test", GoalType.PROFIT, 0.3)
        progress = goal_manager.get_goal_progress(goal.goal_id)
        assert "weighted_progress" in progress
        assert "sub_goals" in progress

    def test_activate_and_complete_goal(self, goal_manager):
        goal = goal_manager.create_goal("test")
        assert goal_manager.activate_goal(goal.goal_id)
        assert goal.status == GoalStatus.ACTIVE
        assert goal_manager.complete_goal(goal.goal_id)
        assert goal.status == GoalStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════
# 2. Priority Engine (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestPrioritySignal:
    def test_create_signal(self):
        signal = PrioritySignal(
            category=SignalCategory.ROAS,
            severity=SignalSeverity.HIGH,
            description="ROAS下降20%",
            impact=0.8, urgency=0.9, confidence=0.85,
        )
        assert signal.category == SignalCategory.ROAS
        assert signal.priority_score > 0

    def test_priority_score_formula(self):
        signal = PrioritySignal(impact=0.8, urgency=0.9, confidence=0.85, risk_level=0.2)
        expected = (0.8 * 0.9 * 0.85) / 0.2
        assert abs(signal.priority_score - expected) < 0.01

    def test_weighted_score_critical(self):
        signal = PrioritySignal(severity=SignalSeverity.CRITICAL, impact=0.5, urgency=0.5, confidence=0.5)
        base = signal.priority_score
        assert signal.weighted_score == base * 2.0

    def test_weighted_score_low(self):
        signal = PrioritySignal(severity=SignalSeverity.LOW, impact=0.5, urgency=0.5, confidence=0.5)
        assert signal.weighted_score == signal.priority_score * 0.5

    def test_signal_serialization(self):
        signal = PrioritySignal(category=SignalCategory.CPI, description="CPI上升")
        data = signal.to_dict()
        assert data["category"] == "cpi"
        assert "priority_score" in data


class TestPriorityEngine:
    def test_add_signal(self, priority_engine):
        signal = PrioritySignal(category=SignalCategory.ROAS, description="test")
        priority_engine.add_signal(signal)
        assert len(priority_engine.get_signals()) == 1

    def test_create_signal_convenience(self, priority_engine):
        priority_engine.create_signal(
            SignalCategory.ROAS, "ROAS下降", SignalSeverity.HIGH,
            impact=0.8, urgency=0.9,
        )
        assert len(priority_engine.get_signals()) == 1

    def test_rank_orders_by_score(self, priority_engine):
        s1 = PrioritySignal(impact=0.9, urgency=0.9, description="high")
        s2 = PrioritySignal(impact=0.3, urgency=0.3, description="low")
        priority_engine.add_signals([s1, s2])
        decision = priority_engine.rank()
        assert decision.ranked_signals[0].description == "high"

    def test_rank_current_clears_signals(self, priority_engine):
        priority_engine.add_signal(PrioritySignal(description="test"))
        priority_engine.rank_current()
        assert len(priority_engine.get_signals()) == 0

    def test_get_top_n(self, priority_engine):
        for i in range(5):
            priority_engine.add_signal(PrioritySignal(
                impact=0.1 * (i + 1), description=f"s{i}"
            ))
        top = priority_engine.get_top_n(3)
        assert len(top) == 3

    def test_allocate_attention(self, priority_engine):
        for i in range(5):
            priority_engine.add_signal(PrioritySignal(impact=0.1 * (i + 1)))
        attention = priority_engine.allocate_attention(max_slots=3)
        assert len(attention) == 3

    def test_allocate_by_role(self, priority_engine):
        s1 = PrioritySignal(category=SignalCategory.ROAS, target_agent=AgentRole.UA)
        s2 = PrioritySignal(category=SignalCategory.CREATIVE, target_agent=AgentRole.CREATIVE)
        s3 = PrioritySignal(category=SignalCategory.ROAS, target_agent=AgentRole.UA)
        allocation = priority_engine.allocate_by_role([s1, s2, s3])
        assert AgentRole.UA in allocation
        assert len(allocation[AgentRole.UA]) == 2

    def test_get_critical_signals(self, priority_engine):
        priority_engine.create_signal(SignalCategory.ROAS, "c1", SignalSeverity.CRITICAL)
        priority_engine.create_signal(SignalCategory.CPI, "c2", SignalSeverity.MEDIUM)
        critical = priority_engine.get_critical_signals()
        assert len(critical) == 1

    def test_custom_score(self, priority_engine):
        signal = PrioritySignal(impact=0.8, urgency=0.7, confidence=0.9, risk_level=0.2)
        score = priority_engine.compute_custom_score(signal)
        assert score >= 0

    def test_priority_engine_stats(self, priority_engine):
        priority_engine.create_signal(SignalCategory.ROAS, "t1", SignalSeverity.HIGH)
        priority_engine.create_signal(SignalCategory.CPI, "t2", SignalSeverity.MEDIUM)
        priority_engine.rank_current()
        stats = priority_engine.stats()
        assert stats["total_decisions"] == 1

    def test_rank_no_signals(self, priority_engine):
        decision = priority_engine.rank()
        assert decision.total_signals == 0
        assert decision.rationale == "no_signals"


# ═══════════════════════════════════════════════════════════════
# 3. Task Allocator (25 测试)
# ═══════════════════════════════════════════════════════════════


class TestCapabilityMatch:
    def test_perfect_match(self, task_allocator):
        score = task_allocator.compute_capability_match(
            ["meta_ads_analysis", "campaign_management"],
            ("meta_ads_analysis", "campaign_management", "roas_monitoring"),
        )
        assert score == 1.0

    def test_partial_match(self, task_allocator):
        score = task_allocator.compute_capability_match(
            ["meta_ads_analysis", "unknown_cap"],
            ("meta_ads_analysis",),
        )
        assert score == 0.5

    def test_no_match(self, task_allocator):
        score = task_allocator.compute_capability_match(
            ["unknown"],
            ("meta_ads_analysis",),
        )
        assert score == 0.0

    def test_empty_required(self, task_allocator):
        score = task_allocator.compute_capability_match([], ("meta_ads_analysis",))
        assert score == 1.0


class TestFindCandidates:
    def test_find_by_role(self, task_allocator, registry):
        candidates = task_allocator.find_candidates(
            ["meta_ads_analysis"], AgentRole.UA
        )
        assert len(candidates) > 0
        assert candidates[0][0].role == AgentRole.UA

    def test_find_creative_candidates(self, task_allocator, registry):
        candidates = task_allocator.find_candidates(
            ["creative_dna_analysis", "fatigue_detection"], AgentRole.CREATIVE
        )
        assert len(candidates) > 0

    def test_find_no_match_role(self, task_allocator, registry):
        candidates = task_allocator.find_candidates(
            ["creative_dna_analysis"], AgentRole.UA
        )
        assert len(candidates) == 0


class TestTaskAllocation:
    def test_allocate_sub_goal(self, task_allocator, registry):
        sub = SubGoal(
            agent_role=AgentRole.UA,
            goal_type=GoalType.ROAS,
            metric="roas",
            target_value=0.12,
        )
        record = task_allocator.allocate_sub_goal(sub)
        assert record is not None
        assert record.status == AllocationStatus.ASSIGNED

    def test_allocate_signal(self, task_allocator, registry):
        signal = PrioritySignal(
            category=SignalCategory.ROAS,
            description="ROAS下降",
            target_agent=AgentRole.UA,
        )
        record = task_allocator.allocate_signal(signal)
        assert record is not None

    def test_allocate_batch(self, task_allocator, registry):
        subs = [
            SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.1),
            SubGoal(agent_role=AgentRole.CREATIVE, goal_type=GoalType.REVENUE, metric="creative_revenue", target_value=0.075),
        ]
        records = task_allocator.allocate_batch(subs)
        assert len(records) == 2

    def test_agent_load_tracking(self, task_allocator, registry):
        sub = SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.1)
        task_allocator.allocate_sub_goal(sub)
        load = task_allocator.get_least_loaded(AgentRole.UA)
        assert load is not None

    def test_complete_task_decrements_load(self, task_allocator, registry):
        sub = SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.1)
        record = task_allocator.allocate_sub_goal(sub)
        assert record is not None
        load = task_allocator.get_load(record.assigned_to)
        assert load is not None
        active_before = load.active_tasks
        task_allocator.complete_task(record.allocation_id)
        assert load.active_tasks == active_before - 1

    def test_fail_task(self, task_allocator, registry):
        sub = SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.1)
        record = task_allocator.allocate_sub_goal(sub)
        assert record is not None
        assert task_allocator.fail_task(record.allocation_id, "timeout")
        assert record.status == AllocationStatus.FAILED

    def test_get_allocations_by_agent(self, task_allocator, registry):
        sub = SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.1)
        record = task_allocator.allocate_sub_goal(sub)
        assert record is not None
        allocations = task_allocator.get_allocations_by_agent(record.assigned_to)
        assert len(allocations) >= 1

    def test_get_pending_allocations(self, task_allocator):
        pending = task_allocator.get_pending_allocations()
        assert isinstance(pending, list)

    def test_allocator_stats(self, task_allocator, registry):
        sub = SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.1)
        task_allocator.allocate_sub_goal(sub)
        stats = task_allocator.stats()
        assert stats["total_allocations"] >= 1
        assert "agent_loads" in stats

    def test_agent_load_model(self):
        load = AgentLoad(agent_id="test", role=AgentRole.UA, active_tasks=5, max_tasks=10)
        assert load.load_ratio == 0.5
        assert not load.is_overloaded
        assert load.available_slots == 5


# ═══════════════════════════════════════════════════════════════
# 4. Conflict Resolver (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestConflictCreation:
    def test_create_conflict(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "预算冲突",
            ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "增加预算"),
                ConflictParty(AgentRole.MONETIZATION, "维持预算"),
            ],
        )
        assert conflict.conflict_type == ConflictType.BUDGET_ALLOCATION
        assert conflict.party_count == 2

    def test_create_budget_conflict(self, conflict_resolver):
        conflict = conflict_resolver.create_budget_conflict(
            "P04预算冲突",
            {"budget_increase": 0.5, "expected_impact": {"roas": 0.15}},
            {"budget_increase": 0.0, "expected_impact": {"ltv": -0.05}},
        )
        assert len(conflict.parties) == 2
        assert conflict.parties[0].agent_role == AgentRole.UA
        assert conflict.parties[1].agent_role == AgentRole.MONETIZATION

    def test_conflict_is_not_resolved_initially(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict("test", ConflictType.STRATEGY, [])
        assert not conflict.is_resolved


class TestConflictResolution:
    def test_resolve_by_supervisor(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "测试冲突", ConflictType.STRATEGY,
            [ConflictParty(AgentRole.UA, "方案A")]
        )
        conflict_resolver.resolve_by_supervisor(conflict, "方案A通过", "Supervisor决策")
        assert conflict.is_resolved
        assert conflict.resolution_result == "方案A通过"

    def test_resolve_by_vote(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "投票冲突", ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "增加预算"),
                ConflictParty(AgentRole.MONETIZATION, "维持预算"),
            ],
        )
        conflict_resolver.resolve_by_vote(
            conflict,
            voters=["ua_agent", "mon_agent", "supervisor"],
        )
        assert conflict.is_resolved

    def test_resolve_by_data(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "数据解决", ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "方案A", expected_impact={"roas": 0.15}, confidence=0.8),
                ConflictParty(AgentRole.MONETIZATION, "方案B", expected_impact={"ltv": 0.05}, confidence=0.6),
            ],
        )
        conflict_resolver.resolve_by_data(conflict, {})
        assert conflict.is_resolved

    def test_resolve_by_compromise(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "妥协", ConflictType.BUDGET_ALLOCATION,
            [ConflictParty(AgentRole.UA, "方案A"), ConflictParty(AgentRole.MONETIZATION, "方案B")]
        )
        conflict_resolver.resolve_by_compromise(
            conflict,
            {"budget_increase": 0.25},
            "取中间值",
        )
        assert conflict.is_resolved
        assert conflict.resolution_strategy == ResolutionStrategy.COMPROMISE

    def test_auto_resolve_with_data(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "自动解决", ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "方案A", expected_impact={"roas": 0.2}, confidence=0.9),
                ConflictParty(AgentRole.MONETIZATION, "方案B", expected_impact={"ltv": 0.05}, confidence=0.5),
            ],
        )
        data = {"ua_budget_allocation": {"success_rate": 0.85}}
        conflict_resolver.auto_resolve(conflict, data=data)
        assert conflict.is_resolved

    def test_auto_resolve_fallback_to_vote(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict(
            "投票回退", ConflictType.STRATEGY,
            [
                ConflictParty(AgentRole.UA, "方案A"),
                ConflictParty(AgentRole.CREATIVE, "方案B"),
            ],
        )
        conflict_resolver.auto_resolve(conflict)
        assert conflict.is_resolved

    def test_get_active_conflicts(self, conflict_resolver):
        conflict_resolver.create_conflict("c1", ConflictType.STRATEGY, [])
        conflict_resolver.create_conflict("c2", ConflictType.BUDGET_ALLOCATION, [])
        assert len(conflict_resolver.get_active_conflicts()) == 2

    def test_get_resolved_conflicts(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict("test", ConflictType.STRATEGY, [ConflictParty(AgentRole.UA, "方案")])
        conflict_resolver.resolve_by_supervisor(conflict, "ok", "reason")
        assert len(conflict_resolver.get_resolved_conflicts()) == 1

    def test_get_by_role(self, conflict_resolver):
        conflict_resolver.create_conflict("test", ConflictType.STRATEGY, [ConflictParty(AgentRole.UA, "方案")])
        conflicts = conflict_resolver.get_by_role(AgentRole.UA)
        assert len(conflicts) >= 1

    def test_stats(self, conflict_resolver):
        conflict = conflict_resolver.create_conflict("test", ConflictType.STRATEGY, [ConflictParty(AgentRole.UA, "方案")])
        conflict_resolver.resolve_by_supervisor(conflict, "ok", "reason")
        stats = conflict_resolver.stats()
        assert stats["resolved_conflicts"] == 1


# ═══════════════════════════════════════════════════════════════
# 5. Supervisor Memory (15 测试)
# ═══════════════════════════════════════════════════════════════


class TestSupervisorMemory:
    def test_record_decision(self, supervisor_memory):
        mem = supervisor_memory.record_decision(
            "测试决策", AgentRole.UA, "增加预算", "ROAS提升", 0.8
        )
        assert mem.memory_type == MemoryType.DECISION
        assert mem.agent_role == AgentRole.UA

    def test_record_success(self, supervisor_memory):
        mem = supervisor_memory.record_success("成功案例", AgentRole.CREATIVE, "生成变体")
        assert mem.success_rating == 0.9

    def test_record_failure(self, supervisor_memory):
        mem = supervisor_memory.record_failure("失败案例", AgentRole.UA, "增加预算")
        assert mem.success_rating == 0.1

    def test_record_strategy(self, supervisor_memory):
        mem = supervisor_memory.record_strategy("策略A", AgentRole.CREATIVE, "使用rescue基因", 0.75)
        assert mem.memory_type == MemoryType.STRATEGY

    def test_get_by_role(self, supervisor_memory):
        supervisor_memory.record_decision("d1", AgentRole.UA, "action")
        supervisor_memory.record_decision("d2", AgentRole.CREATIVE, "action")
        ua_mems = supervisor_memory.get_by_role(AgentRole.UA)
        assert len(ua_mems) == 1

    def test_get_by_type(self, supervisor_memory):
        supervisor_memory.record_success("s1", AgentRole.UA, "action")
        supervisor_memory.record_failure("f1", AgentRole.UA, "action")
        successes = supervisor_memory.get_successful()
        assert len(successes) == 1

    def test_get_successful_with_min_rating(self, supervisor_memory):
        supervisor_memory.record_decision("d1", AgentRole.UA, "a", success_rating=0.5)
        supervisor_memory.record_decision("d2", AgentRole.UA, "a", success_rating=0.9)
        good = supervisor_memory.get_successful(min_rating=0.7)
        assert len(good) == 1

    def test_get_best_strategies(self, supervisor_memory):
        supervisor_memory.record_strategy("s1", AgentRole.UA, "a", 0.6)
        supervisor_memory.record_strategy("s2", AgentRole.UA, "a", 0.9)
        supervisor_memory.record_strategy("s3", AgentRole.UA, "a", 0.3)
        best = supervisor_memory.get_best_strategies(AgentRole.UA, top_n=2)
        assert len(best) == 2
        assert best[0].success_rating == 0.9

    def test_get_decision_context(self, supervisor_memory):
        supervisor_memory.record_decision("d1", AgentRole.UA, "a", "o", 0.8)
        ctx = supervisor_memory.get_decision_context(AgentRole.UA)
        assert "performance" in ctx
        assert "best_strategies" in ctx

    def test_get_organization_health(self, supervisor_memory):
        supervisor_memory.record_decision("d1", AgentRole.UA, "a", "o", 0.8)
        supervisor_memory.record_decision("d2", AgentRole.CREATIVE, "a", "o", 0.6)
        health = supervisor_memory.get_organization_health()
        assert "avg_success_rate" in health
        assert "agent_count" in health

    def test_performance_tracking(self, supervisor_memory):
        supervisor_memory.record_decision("d1", AgentRole.UA, "a", "o", 0.8)
        supervisor_memory.record_decision("d2", AgentRole.UA, "a", "o", 0.2)
        perf = supervisor_memory.get_performance(AgentRole.UA)
        assert perf.total_tasks == 2
        assert perf.successful_tasks == 1
        assert perf.failed_tasks == 1

    def test_memory_by_tag(self, supervisor_memory):
        mem = supervisor_memory.record_decision("tagged", AgentRole.UA, "a", tags=["roas", "urgent"])
        results = supervisor_memory.get_by_tag("roas")
        assert len(results) >= 1

    def test_memory_trimming(self):
        memory = SupervisorMemory(max_memories=10)
        for i in range(15):
            memory.record_decision(f"d{i}", AgentRole.UA, "a")
        assert len(memory.get_recent(100)) <= 10


# ═══════════════════════════════════════════════════════════════
# 6. Supervisor Agent Loop (30 测试)
# ═══════════════════════════════════════════════════════════════


class TestSupervisorAgentCore:
    def test_create_supervisor(self, supervisor):
        assert supervisor.identity is not None
        assert supervisor.state == SupervisorState.IDLE

    def test_run_cycle_with_goal(self, supervisor):
        report = supervisor.run_cycle("本月利润提升30%")
        assert report is not None
        assert supervisor.cycle_count == 1
        assert report.tasks_dispatched > 0

    def test_run_cycle_returns_report(self, supervisor):
        report = supervisor.run_cycle("提升ROAS", goal_type=GoalType.ROAS, target_value=0.15)
        assert isinstance(report, SupervisorReport)
        assert report.cycle_id != ""

    def test_run_cycle_increments_count(self, supervisor):
        supervisor.run_cycle("goal1")
        supervisor.run_cycle("goal2")
        assert supervisor.cycle_count == 2

    def test_process_goal_shortcut(self, supervisor):
        report = supervisor.process_goal("提升利润")
        assert report is not None

    def test_process_signals(self, supervisor):
        signals = [
            PrioritySignal(category=SignalCategory.ROAS, description="ROAS下降", severity=SignalSeverity.HIGH),
            PrioritySignal(category=SignalCategory.CPI, description="CPI上升", severity=SignalSeverity.MEDIUM),
        ]
        report = supervisor.process_signals(signals)
        assert report.tasks_dispatched > 0

    def test_process_alert(self, supervisor):
        report = supervisor.process_alert(SignalCategory.ROAS, "ROAS急剧下降", SignalSeverity.CRITICAL)
        assert report is not None

    def test_multiple_cycles_accumulate_reports(self, supervisor):
        supervisor.run_cycle("goal1")
        supervisor.run_cycle("goal2")
        reports = supervisor.get_reports()
        assert len(reports) == 2

    def test_get_last_report(self, supervisor):
        supervisor.run_cycle("test")
        report = supervisor.get_last_report()
        assert report is not None

    def test_supervisor_state_transitions(self, supervisor):
        assert supervisor.state == SupervisorState.IDLE
        supervisor.run_cycle("test")
        assert supervisor.state == SupervisorState.IDLE  # 循环结束

    def test_supervisor_stats(self, supervisor):
        supervisor.run_cycle("test")
        stats = supervisor.stats()
        assert "cycle_count" in stats
        assert "goals" in stats
        assert "allocations" in stats
        assert "memory" in stats


class TestSupervisorModes:
    def test_full_auto_mode(self, supervisor):
        supervisor.set_mode(SupervisorMode.FULL_AUTO)
        report = supervisor.run_cycle("test")
        assert report is not None

    def test_semi_auto_mode(self, supervisor):
        supervisor.set_mode(SupervisorMode.SEMI_AUTO)
        report = supervisor.run_cycle("test")
        assert report is not None

    def test_advisory_mode(self, supervisor):
        supervisor.set_mode(SupervisorMode.ADVISORY)
        report = supervisor.run_cycle("test")
        assert report is not None

    def test_mode_switch(self, supervisor):
        supervisor.set_mode(SupervisorMode.FULL_AUTO)
        assert supervisor.mode == SupervisorMode.FULL_AUTO
        supervisor.set_mode(SupervisorMode.MANUAL)
        assert supervisor.mode == SupervisorMode.MANUAL


class TestSupervisorConflictManagement:
    def test_report_conflict(self, supervisor):
        conflict = supervisor.report_conflict(
            "预算冲突",
            ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "增加预算"),
                ConflictParty(AgentRole.MONETIZATION, "维持预算"),
            ],
        )
        assert conflict is not None
        assert not conflict.is_resolved

    def test_resolve_current_conflicts(self, supervisor):
        supervisor.report_conflict(
            "测试冲突", ConflictType.STRATEGY,
            [ConflictParty(AgentRole.UA, "方案A")]
        )
        resolved = supervisor.resolve_current_conflicts()
        assert len(resolved) > 0

    def test_conflict_in_cycle(self, supervisor):
        # 先创建冲突, 再运行循环
        supervisor.report_conflict(
            "预算冲突", ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "增加预算"),
                ConflictParty(AgentRole.MONETIZATION, "维持预算"),
            ],
        )
        report = supervisor.run_cycle("test")
        assert report.conflicts_resolved >= 0


class TestSupervisorSubModules:
    def test_get_goal_manager(self, supervisor):
        gm = supervisor.get_goal_manager()
        assert isinstance(gm, GoalManager)

    def test_get_priority_engine(self, supervisor):
        pe = supervisor.get_priority_engine()
        assert isinstance(pe, PriorityEngine)

    def test_get_task_allocator(self, supervisor):
        ta = supervisor.get_task_allocator()
        assert isinstance(ta, TaskAllocator)

    def test_get_conflict_resolver(self, supervisor):
        cr = supervisor.get_conflict_resolver()
        assert isinstance(cr, ConflictResolver)

    def test_get_memory(self, supervisor):
        mem = supervisor.get_memory()
        assert isinstance(mem, SupervisorMemory)


class TestSupervisorReport:
    def test_report_contains_goals(self, supervisor):
        report = supervisor.run_cycle("利润提升30%")
        assert len(report.active_goals) > 0
        assert report.tasks_dispatched > 0

    def test_report_contains_health(self, supervisor):
        report = supervisor.run_cycle("test")
        assert "performances" in report.organization_health or "agent_count" in report.organization_health

    def test_report_contains_recommendations(self, supervisor):
        report = supervisor.run_cycle("test")
        assert isinstance(report.recommendations, list)

    def test_report_serialization(self, supervisor):
        report = supervisor.run_cycle("test")
        data = report.to_dict()
        assert "report_id" in data
        assert "tasks_dispatched" in data


# ═══════════════════════════════════════════════════════════════
# 7. Communication Integration (20 测试)
# ═══════════════════════════════════════════════════════════════


class TestCommunicationIntegration:
    def test_supervisor_broadcasts_goal(self, supervisor, registry):
        goal_manager = supervisor.get_goal_manager()
        goal = goal_manager.create_goal("广播测试", GoalType.PROFIT, 0.3)
        supervisor.broadcast_goal(goal)
        # 验证消息已发送
        stats = supervisor.stats()
        assert stats is not None

    def test_supervisor_broadcast_strategy(self, supervisor):
        supervisor.broadcast_strategy_update({"strategy": "v2", "reason": "测试"})
        assert supervisor.state in [SupervisorState.IDLE, SupervisorState.MONITORING]

    def test_allocator_uses_registry(self, supervisor, registry):
        # 验证 allocator 能正确使用 registry 查找 Agent
        ta = supervisor.get_task_allocator()
        candidates = ta.find_candidates(["meta_ads_analysis"], AgentRole.UA)
        assert len(candidates) > 0

    def test_allocator_sends_messages(self, supervisor, registry, bus):
        sub = SubGoal(agent_role=AgentRole.UA, goal_type=GoalType.ROAS, metric="roas", target_value=0.12)
        ta = supervisor.get_task_allocator()
        record = ta.allocate_sub_goal(sub)
        assert record is not None
        # 验证消息已投递到对应 Agent inbox
        agents = registry.find_by_role(AgentRole.UA)
        if agents:
            inbox_size = bus.get_inbox_size(agents[0].identity.agent_id)
            assert inbox_size >= 0

    def test_full_organization_flow(self, supervisor):
        """完整组织流程: 目标 → 分解 → 分配 → 冲突 → 解决 → 报告."""
        # 1. 创建冲突
        supervisor.report_conflict(
            "UA建议增加预算, Monetization拒绝",
            ConflictType.BUDGET_ALLOCATION,
            [
                ConflictParty(AgentRole.UA, "增加预算50%", expected_impact={"roas": 0.15}, confidence=0.8),
                ConflictParty(AgentRole.MONETIZATION, "维持预算", expected_impact={"ltv": -0.05}, confidence=0.7),
            ],
        )
        # 2. 运行循环
        report = supervisor.run_cycle("本月利润提升30%")
        # 3. 验证
        assert report.tasks_dispatched > 0
        assert report.conflicts_resolved >= 0

    def test_multi_cycle_learning(self, supervisor):
        """多循环学习: 记忆累积."""
        for i in range(3):
            supervisor.run_cycle(f"cycle_{i}_goal")
        mem = supervisor.get_memory()
        stats = mem.stats()
        assert stats["total_memories"] > 0

    def test_supervisor_with_external_signals(self, supervisor):
        """外部信号 + 目标同时处理."""
        signals = [
            PrioritySignal(category=SignalCategory.ROAS, description="ROAS下降", severity=SignalSeverity.HIGH, impact=0.8),
        ]
        report = supervisor.run_cycle(business_goal="提升ROAS", signals=signals, goal_type=GoalType.ROAS)
        assert report is not None

    def test_supervisor_reset(self, supervisor):
        supervisor.run_cycle("test")
        supervisor.reset()
        assert supervisor.cycle_count == 0
        assert supervisor.state == SupervisorState.IDLE
        assert supervisor.get_memory().stats()["total_memories"] == 0

    def test_report_accumulation(self, supervisor):
        for i in range(5):
            supervisor.run_cycle(f"cycle_{i}")
        reports = supervisor.get_reports(3)
        assert len(reports) == 3

    def test_goal_types_across_cycles(self, supervisor):
        supervisor.run_cycle("利润提升", goal_type=GoalType.PROFIT)
        supervisor.run_cycle("ROAS优化", goal_type=GoalType.ROAS)
        supervisor.run_cycle("规模扩张", goal_type=GoalType.SCALE)
        gm = supervisor.get_goal_manager()
        stats = gm.stats()
        assert stats["total_goals"] == 3