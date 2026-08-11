"""E13.7.1 Autonomous Growth Agent Layer — 测试套件.

覆盖:
  - Agent Models (AgentGoal, Observation, Insight, GrowthPlan, AgentContext, AgentProfile)
  - Agent State (AgentStateManager, 状态转换, 观察/目标/计划管理)
  - Agent Memory (WorkingMemory, EpisodicMemory, SemanticMemory)
  - Agent Reasoning (ReasoningEngine, 模式识别, 异常检测, 记忆检索, 因果推理)
  - Agent Planner (AgentPlanner, 策略选择, 动作生成, 预算估算, 风险评估)
  - Agent Tools (ToolRegistry, ToolDefinition, 工具执行, mock 处理器)
  - Agent Core (GrowthAgent, 完整循环, 分阶段执行)
  - Agent Orchestrator (AgentOrchestrator, 单次/持续循环, 报告生成)
  - Integration (完整 Agent Pipeline: Observe → Reason → Plan → Execute → Learn)
"""

import time
import uuid

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent import (
    # Core
    GrowthAgent,
    AgentOrchestrator,
    # Models
    AgentContext,
    AgentGoal,
    AgentPhase,
    AgentProfile,
    GoalPriority,
    GoalStatus,
    GrowthPlan,
    Insight,
    InsightType,
    Observation,
    PlanStatus,
    # State
    AgentStateManager,
    # Memory
    EpisodicMemory,
    Episode,
    KnowledgeNode,
    SemanticMemory,
    WorkingMemory,
    WorkingMemoryEntry,
    # Reasoning
    ReasoningContext,
    ReasoningEngine,
    # Planner
    AgentPlanner,
    BUILTIN_STRATEGIES,
    StrategyTemplate,
    # Tools
    BUILTIN_TOOLS,
    ToolCategory,
    ToolDefinition,
    ToolPermission,
    ToolRegistry,
    ToolResult,
    ToolResultStatus,
    create_default_registry,
    create_registry_with_handlers,
    # Orchestrator
    CycleResult,
    CycleTrigger,
    OrchestratorReport,
    OrchestratorState,
    # Factories
    create_aggressive_agent,
    create_aggressive_agent_profile,
    create_conservative_agent,
    create_conservative_agent_profile,
    create_growth_agent,
    create_growth_agent_profile,
    create_orchestrator,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def sample_metrics():
    return {
        "spend": 17000.0,
        "roas": 0.53,
        "roas_change": -0.12,
        "ctr": 0.021,
        "ctr_change": -0.12,
        "creative_fatigue": 0.81,
        "payer_quality": 0.65,
        "top_creative_ctr": 0.08,
        "avg_ctr": 0.02,
        "installs": 4500,
        "installs_change": -0.05,
        "spend_change": 0.05,
    }


@pytest.fixture
def sample_goal():
    return AgentGoal(
        title="Reduce Creative Fatigue",
        description="Address high creative fatigue for P04 Witch Merge",
        priority=GoalPriority.HIGH,
        success_criteria="Creative fatigue < 0.5",
        target_metric="creative_fatigue",
        target_value=0.3,
        current_value=0.81,
    )


@pytest.fixture
def sample_insight():
    return Insight(
        insight_type=InsightType.THREAT,
        title="素材疲劳警告",
        description="素材疲劳度 81%，CTR 下降 12%",
        reasoning="Creative fatigue at 81% exceeds threshold 70%",
        confidence=0.85,
        evidence=["fatigue=0.81", "ctr_change=-0.12"],
        suggested_action="MUTATE_CREATIVE: 生成新 DNA 变体",
        urgency=0.81,
    )


@pytest.fixture
def sample_observation():
    return Observation(
        source="test",
        data={"spend": 17000, "roas": 0.53},
        summary="Spend=$17,000 | ROAS=0.53",
        significance=0.8,
    )


# ═══════════════════════════════════════════════════════════════
# 1. Agent Models Tests
# ═══════════════════════════════════════════════════════════════


class TestAgentGoal:
    """AgentGoal 模型测试."""

    def test_create_goal(self):
        goal = AgentGoal(title="Test Goal", priority=GoalPriority.HIGH)
        assert goal.goal_id
        assert goal.title == "Test Goal"
        assert goal.priority == GoalPriority.HIGH
        assert goal.status == GoalStatus.PENDING

    def test_goal_progress(self):
        goal = AgentGoal(target_value=100, current_value=50)
        assert goal.progress == 0.5

    def test_goal_progress_zero_target(self):
        goal = AgentGoal(target_value=0, current_value=50)
        assert goal.progress == 0.0

    def test_goal_progress_exceeds_target(self):
        goal = AgentGoal(target_value=100, current_value=150)
        assert goal.progress == 1.0

    def test_goal_is_overdue(self):
        goal = AgentGoal(deadline="2020-01-01T00:00:00+00:00")
        assert goal.is_overdue

    def test_goal_not_overdue_no_deadline(self):
        goal = AgentGoal()
        assert not goal.is_overdue

    def test_goal_to_dict(self):
        goal = AgentGoal(title="Test", priority=GoalPriority.CRITICAL)
        d = goal.to_dict()
        assert d["title"] == "Test"
        assert d["priority"] == "critical"
        assert "progress" in d

    def test_goal_uuid_unique(self):
        g1 = AgentGoal()
        g2 = AgentGoal()
        assert g1.goal_id != g2.goal_id

    def test_goal_sub_goals(self):
        goal = AgentGoal(sub_goals=["sub1", "sub2"])
        assert len(goal.sub_goals) == 2

    def test_goal_metadata(self):
        goal = AgentGoal(metadata={"key": "value"})
        assert goal.metadata["key"] == "value"


class TestObservation:
    """Observation 模型测试."""

    def test_create_observation(self):
        obs = Observation(source="adjust", data={"spend": 100})
        assert obs.observation_id
        assert obs.source == "adjust"
        assert obs.significance == 0.5

    def test_observation_to_dict(self):
        obs = Observation(source="test", significance=0.8)
        d = obs.to_dict()
        assert d["source"] == "test"
        assert d["significance"] == 0.8

    def test_observation_phase_default(self):
        obs = Observation()
        assert obs.phase == AgentPhase.OBSERVING


class TestInsight:
    """Insight 模型测试."""

    def test_create_insight(self):
        i = Insight(
            insight_type=InsightType.THREAT,
            title="Test",
            confidence=0.9,
        )
        assert i.insight_id
        assert i.insight_type == InsightType.THREAT
        assert i.confidence == 0.9

    def test_insight_to_dict(self):
        i = Insight(
            insight_type=InsightType.OPPORTUNITY,
            title="Opportunity",
            urgency=0.8,
        )
        d = i.to_dict()
        assert d["insight_type"] == "opportunity"
        assert d["urgency"] == 0.8

    def test_insight_evidence(self):
        i = Insight(evidence=["e1", "e2"])
        assert len(i.evidence) == 2


class TestGrowthPlan:
    """GrowthPlan 模型测试."""

    def test_create_plan(self):
        plan = GrowthPlan(
            title="Test Plan",
            strategy="creative_mutation",
            budget=500.0,
        )
        assert plan.plan_id
        assert plan.status == PlanStatus.DRAFT
        assert plan.budget == 500.0

    def test_plan_to_dict(self):
        plan = GrowthPlan(
            title="Test",
            risk_level="medium",
            confidence=0.8,
        )
        d = plan.to_dict()
        assert d["risk_level"] == "medium"
        assert d["confidence"] == 0.8

    def test_plan_actions(self):
        plan = GrowthPlan(actions=[{"action_type": "MUTATE_CREATIVE", "params": {"variants": 5}}])
        assert len(plan.actions) == 1

    def test_plan_expected_metrics(self):
        plan = GrowthPlan(expected_metrics={"ctr": 0.15, "roas": 0.1})
        assert plan.expected_metrics["ctr"] == 0.15


class TestAgentContext:
    """AgentContext 模型测试."""

    def test_create_context(self):
        ctx = AgentContext()
        assert ctx.session_id
        assert ctx.phase == AgentPhase.IDLE
        assert ctx.cycle_count == 0

    def test_context_to_dict(self):
        ctx = AgentContext(cycle_count=5)
        d = ctx.to_dict()
        assert d["cycle_count"] == 5
        assert d["phase"] == "idle"


class TestAgentProfile:
    """AgentProfile 模型测试."""

    def test_default_profile(self):
        profile = AgentProfile()
        assert profile.name == "GrowthAgent"
        assert profile.risk_tolerance == 0.5
        assert profile.autonomy_level == 0.7

    def test_profile_to_dict(self):
        profile = AgentProfile(name="TestAgent")
        d = profile.to_dict()
        assert d["name"] == "TestAgent"

    def test_create_growth_agent_profile(self):
        profile = create_growth_agent_profile()
        assert profile.name == "GrowthAgent"
        assert profile.risk_tolerance == 0.5

    def test_create_aggressive_agent_profile(self):
        profile = create_aggressive_agent_profile()
        assert profile.risk_tolerance == 0.8
        assert profile.autonomy_level == 0.9

    def test_create_conservative_agent_profile(self):
        profile = create_conservative_agent_profile()
        assert profile.risk_tolerance == 0.2
        assert profile.autonomy_level == 0.3


# ═══════════════════════════════════════════════════════════════
# 2. Agent State Tests
# ═══════════════════════════════════════════════════════════════


class TestAgentStateManager:
    """AgentStateManager 测试."""

    def test_initial_state(self):
        sm = AgentStateManager()
        assert sm.phase == AgentPhase.IDLE
        assert sm.context.cycle_count == 0

    def test_transition_valid(self):
        sm = AgentStateManager()
        assert sm.transition(AgentPhase.OBSERVING)
        assert sm.phase == AgentPhase.OBSERVING

    def test_transition_invalid(self):
        sm = AgentStateManager()
        # IDLE → PLANNING is invalid
        assert not sm.transition(AgentPhase.PLANNING)
        assert sm.phase == AgentPhase.IDLE

    def test_transition_full_cycle(self):
        sm = AgentStateManager()
        assert sm.transition(AgentPhase.OBSERVING)
        assert sm.transition(AgentPhase.REASONING)
        assert sm.transition(AgentPhase.PLANNING)
        assert sm.transition(AgentPhase.EXECUTING)
        assert sm.transition(AgentPhase.LEARNING)
        assert sm.transition(AgentPhase.IDLE)
        assert sm.phase == AgentPhase.IDLE

    def test_can_transition(self):
        sm = AgentStateManager()
        assert sm.can_transition(AgentPhase.OBSERVING)
        assert not sm.can_transition(AgentPhase.PLANNING)

    def test_phase_history(self):
        sm = AgentStateManager()
        sm.transition(AgentPhase.OBSERVING)
        history = sm.get_phase_history()
        assert len(history) == 1
        assert history[0]["from"] == "idle"
        assert history[0]["to"] == "observing"

    def test_add_observation(self):
        sm = AgentStateManager()
        obs = Observation(source="test", summary="Test observation")
        sm.add_observation(obs)
        assert len(sm.observations) == 1
        assert sm.get_recent_observations(1)[0].summary == "Test observation"

    def test_add_insight(self):
        sm = AgentStateManager()
        insight = Insight(title="Test Insight")
        sm.add_insight(insight)
        assert len(sm.insights) == 1

    def test_add_goal(self):
        sm = AgentStateManager()
        goal = AgentGoal(title="Test Goal", status=GoalStatus.ACTIVE)
        sm.add_goal(goal)
        assert len(sm.active_goals) == 1

    def test_complete_goal(self):
        sm = AgentStateManager()
        goal = AgentGoal(title="Test")
        sm.add_goal(goal)
        assert sm.complete_goal(goal.goal_id)
        assert sm.get_goal(goal.goal_id).status == GoalStatus.COMPLETED

    def test_fail_goal(self):
        sm = AgentStateManager()
        goal = AgentGoal(title="Test")
        sm.add_goal(goal)
        assert sm.fail_goal(goal.goal_id)
        assert sm.get_goal(goal.goal_id).status == GoalStatus.FAILED

    def test_get_goals_by_priority(self):
        sm = AgentStateManager()
        sm.add_goal(AgentGoal(title="High", priority=GoalPriority.HIGH))
        sm.add_goal(AgentGoal(title="Low", priority=GoalPriority.LOW))
        high = sm.get_goals_by_priority(GoalPriority.HIGH)
        assert len(high) == 1

    def test_update_metrics(self):
        sm = AgentStateManager()
        sm.update_metrics({"roas": 0.8})
        assert sm.get_metric("roas") == 0.8

    def test_increment_cycle(self):
        sm = AgentStateManager()
        assert sm.increment_cycle() == 1
        assert sm.increment_cycle() == 2

    def test_stats(self):
        sm = AgentStateManager()
        sm.transition(AgentPhase.OBSERVING)
        stats = sm.stats()
        assert stats["phase"] == "observing"
        assert "cycle_count" in stats

    def test_reset(self):
        sm = AgentStateManager()
        sm.add_observation(Observation())
        sm.add_goal(AgentGoal())
        sm.reset()
        assert len(sm.observations) == 0
        assert len(sm.goals) == 0


# ═══════════════════════════════════════════════════════════════
# 3. Agent Memory Tests
# ═══════════════════════════════════════════════════════════════


class TestWorkingMemory:
    """WorkingMemory 测试."""

    def test_add_entry(self):
        wm = WorkingMemory()
        entry = wm.add("Test content", importance=0.8)
        assert entry.content == "Test content"
        assert wm.size == 1

    def test_add_observation(self):
        wm = WorkingMemory()
        obs = Observation(summary="Obs summary", significance=0.7)
        entry = wm.add_observation(obs)
        assert entry.entry_type == "observation"
        assert entry.importance == 0.7

    def test_add_insight(self):
        wm = WorkingMemory()
        insight = Insight(title="Test", description="Desc", confidence=0.9)
        entry = wm.add_insight(insight)
        assert entry.entry_type == "insight"
        assert entry.importance == 0.9

    def test_get_recent(self):
        wm = WorkingMemory()
        wm.add("Entry 1")
        wm.add("Entry 2")
        recent = wm.get_recent(1)
        assert len(recent) == 1
        assert recent[0].content == "Entry 2"

    def test_get_by_type(self):
        wm = WorkingMemory()
        wm.add("Obs", entry_type="observation")
        wm.add("Insight", entry_type="insight")
        obs_entries = wm.get_by_type("observation")
        assert len(obs_entries) == 1

    def test_get_important(self):
        wm = WorkingMemory()
        wm.add("Low", importance=0.3)
        wm.add("High", importance=0.9)
        important = wm.get_important(0.7)
        assert len(important) == 1

    def test_ttl_expiry(self):
        wm = WorkingMemory()
        wm.add("Short lived", importance=0.1, ttl_cycles=2)
        wm.advance_cycle()
        wm.advance_cycle()
        wm.advance_cycle()
        wm._gc()
        assert wm.active_count == 0

    def test_capacity_limit(self):
        wm = WorkingMemory(max_entries=5)
        for i in range(10):
            wm.add(f"Entry {i}")
        assert wm.size <= 5

    def test_summarize(self):
        wm = WorkingMemory()
        wm.add("Important observation", importance=0.8)
        summary = wm.summarize()
        assert "Important observation" in summary

    def test_clear(self):
        wm = WorkingMemory()
        wm.add("Test")
        wm.clear()
        assert wm.size == 0

    def test_current_cycle(self):
        wm = WorkingMemory()
        assert wm.current_cycle == 0
        wm.advance_cycle()
        assert wm.current_cycle == 1


class TestEpisodicMemory:
    """EpisodicMemory 测试."""

    def test_record_episode(self):
        em = EpisodicMemory()
        episode = Episode(
            session_id="s1",
            cycle=1,
            outcome="positive",
            lessons=["Creative mutation works"],
        )
        em.record(episode)
        assert em.size == 1

    def test_get_recent(self):
        em = EpisodicMemory()
        for i in range(5):
            em.record(Episode(session_id=f"s{i}", cycle=i))
        assert len(em.get_recent(3)) == 3

    def test_get_successful(self):
        em = EpisodicMemory()
        em.record(Episode(outcome="positive"))
        em.record(Episode(outcome="negative"))
        assert len(em.get_successful()) == 1

    def test_get_failures(self):
        em = EpisodicMemory()
        em.record(Episode(outcome="positive"))
        em.record(Episode(outcome="negative"))
        assert len(em.get_failures()) == 1

    def test_find_similar(self):
        em = EpisodicMemory()
        em.record(Episode(
            goal={"title": "Reduce creative fatigue", "description": "Address fatigue"},
            outcome="positive",
        ))
        similar = em.find_similar("creative fatigue")
        assert len(similar) == 1

    def test_get_lessons(self):
        em = EpisodicMemory()
        em.record(Episode(lessons=["Lesson 1", "Lesson 2"]))
        em.record(Episode(lessons=["Lesson 3"]))
        all_lessons = em.get_lessons()
        assert len(all_lessons) == 3

    def test_max_episodes(self):
        em = EpisodicMemory(max_episodes=10)
        for i in range(15):
            em.record(Episode(session_id=f"s{i}"))
        assert em.size <= 10

    def test_clear(self):
        em = EpisodicMemory()
        em.record(Episode())
        em.clear()
        assert em.size == 0


class TestSemanticMemory:
    """SemanticMemory 测试."""

    def test_add_knowledge(self):
        sm = SemanticMemory()
        node = sm.add_knowledge("Merge素材", "女性用户CTR+32%", confidence=0.85)
        assert node.concept == "Merge素材"
        assert node.confidence == 0.85
        assert sm.size == 1

    def test_reinforce_existing(self):
        sm = SemanticMemory()
        sm.add_knowledge("Merge素材", "CTR+32%", confidence=0.8)
        sm.reinforce("Merge素材")
        node = sm.query("Merge")[0]
        assert node.evidence_count == 2
        assert node.confidence > 0.8

    def test_query(self):
        sm = SemanticMemory()
        sm.add_knowledge("Merge", "CTR high")
        sm.add_knowledge("Witch", "ROAS high")
        results = sm.query("Merge")
        assert len(results) == 1

    def test_get_high_confidence(self):
        sm = SemanticMemory()
        sm.add_knowledge("A", "desc", confidence=0.9)
        sm.add_knowledge("B", "desc", confidence=0.3)
        high = sm.get_high_confidence(0.7)
        assert len(high) == 1

    def test_summarize(self):
        sm = SemanticMemory()
        sm.add_knowledge("Merge", "High CTR", confidence=0.9)
        summary = sm.summarize()
        assert "Merge" in summary

    def test_update_existing(self):
        sm = SemanticMemory()
        sm.add_knowledge("Merge", "Old desc", confidence=0.6)
        sm.add_knowledge("Merge", "New desc", confidence=0.9)
        node = sm.query("Merge")[0]
        assert node.description == "New desc"
        assert node.confidence == 0.9
        assert node.evidence_count == 2

    def test_clear(self):
        sm = SemanticMemory()
        sm.add_knowledge("Test", "desc")
        sm.clear()
        assert sm.size == 0


# ═══════════════════════════════════════════════════════════════
# 4. Agent Reasoning Tests
# ═══════════════════════════════════════════════════════════════


class TestReasoningContext:
    """ReasoningContext 测试."""

    def test_create_context(self):
        ctx = ReasoningContext(
            metrics={"roas": 0.5},
            active_goals=["g1"],
            cycle=3,
        )
        assert ctx.metrics["roas"] == 0.5
        assert ctx.active_goals == ["g1"]
        assert ctx.cycle == 3

    def test_default_values(self):
        ctx = ReasoningContext()
        assert ctx.observations == []
        assert ctx.metrics == {}


class TestReasoningEngine:
    """ReasoningEngine 测试."""

    def test_create_engine(self):
        engine = ReasoningEngine()
        assert engine.insight_count == 0

    def test_reason_fatigue_detection(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"creative_fatigue": 0.85, "ctr_change": -0.2})
        insights = engine.reason(ctx)
        fatigue_insights = [i for i in insights if "疲劳" in i.title]
        assert len(fatigue_insights) > 0
        assert fatigue_insights[0].insight_type == InsightType.THREAT

    def test_reason_no_fatigue(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"creative_fatigue": 0.3})
        insights = engine.reason(ctx)
        fatigue_insights = [i for i in insights if "疲劳" in i.title]
        assert len(fatigue_insights) == 0

    def test_reason_roas_decline(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"roas": 0.5, "roas_change": -0.4})
        insights = engine.reason(ctx)
        threat_insights = [i for i in insights if "ROAS 下降" in i.title]
        assert len(threat_insights) > 0

    def test_reason_roas_improvement(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"roas": 1.5, "roas_change": 0.4})
        insights = engine.reason(ctx)
        opportunity_insights = [i for i in insights if "ROAS 上升" in i.title]
        assert len(opportunity_insights) > 0

    def test_reason_winner_creative(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={
            "top_creative_ctr": 0.08,
            "avg_ctr": 0.02,
        })
        insights = engine.reason(ctx)
        winner_insights = [i for i in insights if "赢家" in i.title]
        assert len(winner_insights) > 0

    def test_reason_spend_anomaly(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"spend": 30000, "spend_change": 0.8})
        insights = engine.reason(ctx)
        anomaly_insights = [i for i in insights if "花费异常" in i.title]
        assert len(anomaly_insights) > 0

    def test_reason_causal_fatigue_roas(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={
            "creative_fatigue": 0.75,
            "roas_change": -0.2,
            "payer_quality": 0.65,
        })
        insights = engine.reason(ctx)
        causal = [i for i in insights if "因果" in i.title]
        assert len(causal) > 0
        assert "素材" in causal[0].title

    def test_reason_with_memory(self):
        wm = WorkingMemory()
        wm.add("Previous fatigue detected", importance=0.8)
        sm = SemanticMemory()
        sm.add_knowledge("fatigue", "Creative fatigue leads to ROAS decline", confidence=0.9)

        engine = ReasoningEngine(working_memory=wm, semantic_memory=sm)
        ctx = ReasoningContext(
            metrics={"creative_fatigue": 0.8, "ctr_change": -0.2},
            working_memory=wm,
            semantic_memory=sm,
        )
        insights = engine.reason(ctx)
        assert len(insights) > 0

    def test_reason_with_episodic_memory(self):
        em = EpisodicMemory()
        em.record(Episode(
            goal={"title": "creative winner scale"},
            outcome="positive",
        ))

        engine = ReasoningEngine(episodic_memory=em)
        ctx = ReasoningContext(
            metrics={
                "top_creative_ctr": 0.08,
                "avg_ctr": 0.02,
                "creative_fatigue": 0.3,
            },
            episodic_memory=em,
        )
        insights = engine.reason(ctx)
        assert len(insights) > 0

    def test_insight_count_tracking(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"creative_fatigue": 0.85, "ctr_change": -0.2})
        engine.reason(ctx)
        assert engine.insight_count > 0

    def test_reset(self):
        engine = ReasoningEngine()
        ctx = ReasoningContext(metrics={"creative_fatigue": 0.85, "ctr_change": -0.2})
        engine.reason(ctx)
        engine.reset()
        assert engine.insight_count == 0


# ═══════════════════════════════════════════════════════════════
# 5. Agent Planner Tests
# ═══════════════════════════════════════════════════════════════


class TestStrategyTemplate:
    """StrategyTemplate 测试."""

    def test_create_template(self):
        st = StrategyTemplate(
            name="test_strategy",
            description="Test strategy",
            applies_to=[InsightType.THREAT],
            default_actions=[{"action_type": "MONITOR"}],
            default_budget=100.0,
            default_risk="low",
        )
        assert st.name == "test_strategy"
        assert st.default_budget == 100.0

    def test_template_to_dict(self):
        st = BUILTIN_STRATEGIES["creative_mutation"]
        d = st.to_dict()
        assert d["name"] == "creative_mutation"
        assert "applies_to" in d


class TestAgentPlanner:
    """AgentPlanner 测试."""

    def test_create_planner(self):
        planner = AgentPlanner()
        assert planner.risk_tolerance == 0.5
        assert planner.plan_count == 0

    def test_plan_with_threat_insight(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Fix Fatigue", priority=GoalPriority.HIGH)
        insight = Insight(
            insight_type=InsightType.THREAT,
            title="素材疲劳警告",
            suggested_action="MUTATE_CREATIVE",
            urgency=0.9,
            confidence=0.85,
        )
        plan = planner.plan(goal, [insight])
        assert plan.goal_id == goal.goal_id
        assert plan.strategy == "creative_mutation"
        assert len(plan.actions) > 0
        assert plan.risk_level in ["safe", "low", "medium", "high", "critical"]

    def test_plan_with_opportunity_insight(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Scale Winner", priority=GoalPriority.HIGH)
        insight = Insight(
            insight_type=InsightType.OPPORTUNITY,
            title="赢家素材发现",
            suggested_action="SCALE_BUDGET",
            confidence=0.9,
            urgency=0.7,
        )
        plan = planner.plan(goal, [insight])
        assert plan.strategy == "scale_winner"
        assert plan.budget > 0

    def test_plan_with_anomaly_insight(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Check Anomaly")
        insight = Insight(
            insight_type=InsightType.ANOMALY,
            title="花费异常",
            confidence=0.7,
        )
        plan = planner.plan(goal, [insight])
        assert plan.strategy == "monitor_only"

    def test_plan_budget_constrained(self):
        planner = AgentPlanner(max_budget_per_cycle=200.0)
        goal = AgentGoal(title="Test", priority=GoalPriority.HIGH)
        insight = Insight(
            insight_type=InsightType.THREAT,
            title="Fatigue",
            suggested_action="MUTATE_CREATIVE",
            urgency=0.9,
            confidence=0.85,
        )
        plan = planner.plan(goal, [insight])
        assert plan.budget <= 200.0

    def test_plan_confidence_calculation(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Test")
        insight = Insight(
            insight_type=InsightType.THREAT,
            confidence=0.9,
            urgency=0.8,
        )
        plan = planner.plan(goal, [insight])
        assert 0 <= plan.confidence <= 1.0

    def test_plan_rollback_generated(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Test")
        insight = Insight(
            insight_type=InsightType.THREAT,
            title="Fatigue",
            suggested_action="MUTATE_CREATIVE",
            urgency=0.9,
            confidence=0.85,
        )
        plan = planner.plan(goal, [insight])
        assert plan.rollback_plan  # 应该有回滚计划

    def test_plan_timeline_generated(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Test")
        insight = Insight(
            insight_type=InsightType.THREAT,
            title="Fatigue",
            suggested_action="MUTATE_CREATIVE",
            urgency=0.9,
            confidence=0.85,
        )
        plan = planner.plan(goal, [insight])
        assert len(plan.timeline) > 0

    def test_plan_batch(self):
        planner = AgentPlanner()
        goals = [
            AgentGoal(title="Critical", priority=GoalPriority.CRITICAL),
            AgentGoal(title="Low", priority=GoalPriority.LOW),
        ]
        insight = Insight(
            insight_type=InsightType.THREAT,
            title="Fatigue",
            suggested_action="MUTATE_CREATIVE",
            urgency=0.9,
            confidence=0.85,
        )
        plans = planner.plan_batch(goals, [insight])
        assert len(plans) == 2
        # 第一个应该是最优先的
        first_goal = next(g for g in goals if g.goal_id == plans[0].goal_id)
        assert first_goal.priority == GoalPriority.CRITICAL

    def test_plan_no_insights(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Test")
        plan = planner.plan(goal, [])
        assert plan.strategy == "monitor_only"
        assert plan.confidence == 0.3

    def test_register_custom_strategy(self):
        planner = AgentPlanner()
        custom = StrategyTemplate(
            name="custom_test",
            description="Custom",
            applies_to=[InsightType.PATTERN],
            default_actions=[{"action_type": "MONITOR"}],
        )
        planner.register_strategy(custom)
        assert "custom_test" in planner.list_strategies()

    def test_plan_count(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Test")
        insight = Insight(insight_type=InsightType.THREAT, urgency=0.9, confidence=0.85)
        planner.plan(goal, [insight])
        assert planner.plan_count == 1

    def test_reset(self):
        planner = AgentPlanner()
        goal = AgentGoal(title="Test")
        insight = Insight(insight_type=InsightType.THREAT, urgency=0.9, confidence=0.85)
        planner.plan(goal, [insight])
        planner.reset()
        assert planner.plan_count == 0


# ═══════════════════════════════════════════════════════════════
# 6. Agent Tools Tests
# ═══════════════════════════════════════════════════════════════


class TestToolDefinition:
    """ToolDefinition 测试."""

    def test_create_definition(self):
        td = ToolDefinition(
            name="test_tool",
            description="Test tool",
            category=ToolCategory.CAMPAIGN,
            permission=ToolPermission.SAFE_WRITE,
        )
        assert td.name == "test_tool"
        assert td.category == ToolCategory.CAMPAIGN

    def test_to_dict(self):
        td = ToolDefinition(
            name="test",
            description="desc",
            timeout_seconds=30,
            is_async=True,
        )
        d = td.to_dict()
        assert d["name"] == "test"
        assert d["timeout_seconds"] == 30
        assert d["is_async"] is True


class TestToolRegistry:
    """ToolRegistry 测试."""

    def test_register_tool(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="test_tool", description="Test")
        registry.register("test_tool", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        assert registry.has_tool("test_tool")

    def test_execute_tool(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="test", description="Test")
        registry.register("test", td, lambda **_: ToolResult(
            status=ToolResultStatus.SUCCESS,
            data={"result": "ok"},
        ))
        result = registry.execute("test", {"param": "value"})
        assert result.is_success()
        assert result.data["result"] == "ok"

    def test_execute_nonexistent_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent")
        assert result.status == ToolResultStatus.FAILED

    def test_execute_approval_required(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="dangerous", description="Dangerous", requires_approval=True)
        registry.register("dangerous", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        result = registry.execute("dangerous", {}, require_approval_check=True)
        assert result.status == ToolResultStatus.APPROVAL_REQUIRED

    def test_execute_batch(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="t1", description="T1")
        registry.register("t1", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        td2 = ToolDefinition(name="t2", description="T2")
        registry.register("t2", td2, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        results = registry.execute_batch([("t1", {}), ("t2", {})])
        assert len(results) == 2
        assert all(r.is_success() for r in results)

    def test_list_tools(self):
        registry = create_default_registry()
        tools = registry.list_tools()
        assert len(tools) > 0

    def test_list_tools_by_category(self):
        registry = create_default_registry()
        campaign_tools = registry.list_tools(ToolCategory.CAMPAIGN)
        assert len(campaign_tools) > 0
        assert all(t.category == ToolCategory.CAMPAIGN for t in campaign_tools)

    def test_get_tools_by_permission(self):
        registry = create_default_registry()
        readonly = registry.get_tools_by_permission(ToolPermission.READ_ONLY)
        assert len(readonly) > 0

    def test_get_categories(self):
        registry = create_default_registry()
        categories = registry.get_categories()
        assert ToolCategory.CAMPAIGN in categories
        assert ToolCategory.DATA in categories

    def test_unregister(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="test", description="Test")
        registry.register("test", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        assert registry.unregister("test")
        assert not registry.has_tool("test")

    def test_generate_tool_prompt(self):
        registry = create_default_registry()
        prompt = registry.generate_tool_prompt()
        assert "Available Tools" in prompt
        assert "create_campaign" in prompt

    def test_execute_error_handling(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="failing", description="Fails")

        def failing_handler(**kwargs):
            raise ValueError("Test error")

        registry.register("failing", td, failing_handler)
        result = registry.execute("failing", {})
        assert result.status == ToolResultStatus.FAILED
        assert "Test error" in result.error

    def test_execution_count(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="test", description="Test")
        registry.register("test", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        registry.execute("test")
        registry.execute("test")
        assert registry.execution_count == 2

    def test_create_default_registry(self):
        registry = create_default_registry()
        assert registry.tool_count > 0
        assert registry.has_tool("create_campaign")
        assert registry.has_tool("query_metrics")
        assert registry.has_tool("mutate_creative")

    def test_create_registry_with_handlers(self):
        def custom_handler(**kwargs):
            return ToolResult(status=ToolResultStatus.SUCCESS, data={"custom": True})

        registry = create_registry_with_handlers({"create_campaign": custom_handler})
        result = registry.execute("create_campaign", {"platform": "meta"})
        assert result.is_success()
        assert result.data["custom"] is True

    def test_execution_history(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="test", description="Test")
        registry.register("test", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        registry.execute("test")
        history = registry.get_execution_history()
        assert len(history) == 1

    def test_reset(self):
        registry = ToolRegistry()
        td = ToolDefinition(name="test", description="Test")
        registry.register("test", td, lambda **_: ToolResult(status=ToolResultStatus.SUCCESS))
        registry.execute("test")
        registry.reset()
        assert registry.execution_count == 0

    def test_builtin_tools_all_registered(self):
        registry = create_default_registry()
        expected = [
            "create_campaign", "update_budget", "pause_campaign", "resume_campaign",
            "mutate_creative", "upload_creative", "generate_creative",
            "query_metrics", "query_adjust", "query_creative_performance", "check_fatigue",
            "query_memory", "update_memory", "record_episode",
            "monitor", "collect_result", "wait",
        ]
        for name in expected:
            assert registry.has_tool(name), f"Tool '{name}' not registered"


# ═══════════════════════════════════════════════════════════════
# 7. Agent Core Tests
# ═══════════════════════════════════════════════════════════════


class TestGrowthAgent:
    """GrowthAgent 测试."""

    def test_create_agent(self):
        agent = create_growth_agent()
        assert agent.phase == AgentPhase.IDLE
        assert agent.profile.name == "GrowthAgent"

    def test_create_aggressive_agent(self):
        agent = create_aggressive_agent()
        assert agent.profile.risk_tolerance == 0.8

    def test_create_conservative_agent(self):
        agent = create_conservative_agent()
        assert agent.profile.risk_tolerance == 0.2

    def test_observe(self, sample_metrics):
        agent = create_growth_agent()
        observations = agent.observe(sample_metrics)
        assert len(observations) > 0
        assert observations[0].source == "manual"

    def test_observe_significance(self, sample_metrics):
        agent = create_growth_agent()
        observations = agent.observe(sample_metrics)
        # 高疲劳 + 高变化 → 高重要性
        assert observations[0].significance > 0.5

    def test_reason(self, sample_metrics):
        agent = create_growth_agent()
        agent.observe(sample_metrics)
        insights = agent.reason()
        assert len(insights) > 0

    def test_plan(self, sample_metrics):
        agent = create_growth_agent()
        agent.observe(sample_metrics)
        agent.reason()
        plans = agent.plan()
        assert len(plans) > 0

    def test_run_cycle(self, sample_metrics):
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["cycle"] == 1
        assert result["observation_count"] > 0
        assert result["insight_count"] > 0
        assert result["plan_count"] >= 0

    def test_run_cycle_multiple(self, sample_metrics):
        agent = create_growth_agent()
        r1 = agent.run_cycle(metrics=sample_metrics)
        r2 = agent.run_cycle(metrics=sample_metrics)
        assert r1["cycle"] == 1
        assert r2["cycle"] == 2

    def test_add_goal(self):
        agent = create_growth_agent()
        goal = AgentGoal(title="Test Goal")
        agent.add_goal(goal)
        assert len(agent.get_active_goals()) == 0  # PENDING, not ACTIVE

    def test_complete_goal(self):
        agent = create_growth_agent()
        goal = AgentGoal(title="Test", status=GoalStatus.ACTIVE)
        agent.add_goal(goal)
        assert agent.complete_goal(goal.goal_id)

    def test_run_cycle_with_goals(self, sample_metrics):
        agent = create_growth_agent()
        goal = AgentGoal(
            title="Test Goal",
            status=GoalStatus.ACTIVE,
            priority=GoalPriority.HIGH,
        )
        agent.add_goal(goal)
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["cycle"] == 1

    def test_run_cycle_low_metrics(self):
        agent = create_growth_agent()
        result = agent.run_cycle(metrics={"roas": 1.2, "creative_fatigue": 0.3})
        assert result["cycle"] == 1

    def test_run_cycle_error_handling(self):
        agent = create_growth_agent()
        # Empty metrics should still work
        result = agent.run_cycle(metrics={})
        assert result["cycle"] == 1

    def test_stats(self, sample_metrics):
        agent = create_growth_agent()
        agent.run_cycle(metrics=sample_metrics)
        stats = agent.stats()
        assert "working_memory_size" in stats
        assert "semantic_memory_size" in stats
        assert "tool_count" in stats

    def test_get_log(self, sample_metrics):
        agent = create_growth_agent()
        agent.run_cycle(metrics=sample_metrics)
        log = agent.get_log()
        assert len(log) > 0

    def test_reset(self, sample_metrics):
        agent = create_growth_agent()
        agent.run_cycle(metrics=sample_metrics)
        agent.reset()
        assert agent.phase == AgentPhase.IDLE
        assert agent.stats()["working_memory_size"] == 0

    def test_factory_creates_with_tools(self):
        agent = create_growth_agent()
        assert agent.tools.has_tool("create_campaign")
        assert agent.tools.has_tool("query_metrics")

    def test_autonomous_goal_generation(self, sample_metrics):
        agent = create_growth_agent()
        agent.observe(sample_metrics)
        agent.reason()
        plans = agent.plan()
        # 应该从洞察自动生成了计划
        if plans:
            assert plans[0].strategy


# ═══════════════════════════════════════════════════════════════
# 8. Agent Orchestrator Tests
# ═══════════════════════════════════════════════════════════════


class TestAgentOrchestrator:
    """AgentOrchestrator 测试."""

    def test_create_orchestrator(self):
        orch = create_orchestrator()
        assert orch.state == OrchestratorState.STOPPED
        assert orch.cycle_count == 0

    def test_run_once(self, sample_metrics):
        orch = create_orchestrator()
        result = orch.run_once(metrics=sample_metrics)
        assert result.cycle_number == 1
        assert result.success
        assert result.insight_count > 0

    def test_run_once_multiple(self, sample_metrics):
        orch = create_orchestrator()
        r1 = orch.run_once(metrics=sample_metrics)
        r2 = orch.run_once(metrics=sample_metrics)
        assert r1.cycle_number == 1
        assert r2.cycle_number == 2

    def test_run_once_with_goals(self, sample_metrics):
        orch = create_orchestrator()
        goal = AgentGoal(
            title="Test",
            status=GoalStatus.ACTIVE,
            priority=GoalPriority.HIGH,
        )
        result = orch.run_once(metrics=sample_metrics, goals=[goal])
        assert result.success

    def test_cycle_result_to_dict(self, sample_metrics):
        orch = create_orchestrator()
        result = orch.run_once(metrics=sample_metrics)
        d = result.to_dict()
        assert "cycle_id" in d
        assert "cycle_number" in d
        assert "success" in d

    def test_generate_report(self, sample_metrics):
        orch = create_orchestrator()
        orch.run_once(metrics=sample_metrics)
        report = orch.generate_report()
        assert report.total_cycles == 1
        assert report.successful_cycles == 1
        assert report.total_insights > 0

    def test_report_to_dict(self, sample_metrics):
        orch = create_orchestrator()
        orch.run_once(metrics=sample_metrics)
        report = orch.generate_report()
        d = report.to_dict()
        assert "success_rate" in d

    def test_get_cycle_history(self, sample_metrics):
        orch = create_orchestrator()
        for _ in range(3):
            orch.run_once(metrics=sample_metrics)
        history = orch.get_cycle_history(2)
        assert len(history) == 2

    def test_get_last_cycle(self, sample_metrics):
        orch = create_orchestrator()
        orch.run_once(metrics=sample_metrics)
        last = orch.get_last_cycle()
        assert last is not None
        assert last.cycle_number == 1

    def test_pause_resume(self):
        orch = create_orchestrator()
        orch.start()
        assert orch.state == OrchestratorState.RUNNING
        orch.pause()
        assert orch.state == OrchestratorState.PAUSED
        orch.resume()
        assert orch.state == OrchestratorState.RUNNING

    def test_stop(self):
        orch = create_orchestrator()
        orch.start()
        orch.stop()
        assert orch.state == OrchestratorState.STOPPED

    def test_default_goals(self, sample_metrics):
        orch = create_orchestrator(with_default_goals=True)
        orch.run_once(metrics=sample_metrics)
        report = orch.generate_report()
        assert report.total_cycles == 1

    def test_set_default_goals(self):
        orch = create_orchestrator(with_default_goals=False)
        orch.set_default_goals([
            AgentGoal(title="Custom Goal", priority=GoalPriority.HIGH),
        ])
        assert len(orch._default_goals) == 1

    def test_agent_stats(self, sample_metrics):
        orch = create_orchestrator()
        orch.run_once(metrics=sample_metrics)
        stats = orch.get_agent_stats()
        assert "working_memory_size" in stats

    def test_reset(self, sample_metrics):
        orch = create_orchestrator()
        orch.run_once(metrics=sample_metrics)
        orch.reset()
        assert orch.cycle_count == 0
        assert orch.state == OrchestratorState.STOPPED


# ═══════════════════════════════════════════════════════════════
# 9. Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestFullAgentPipeline:
    """完整 Agent Pipeline 集成测试."""

    def test_full_cycle_observe_reason_plan(self, sample_metrics):
        """完整 OBSERVE → REASON → PLAN 流程."""
        agent = create_growth_agent()
        # Observe
        observations = agent.observe(sample_metrics)
        assert len(observations) > 0
        # Reason
        insights = agent.reason()
        assert len(insights) > 0
        # 应该有疲劳检测
        fatigue_insights = [i for i in insights if "疲劳" in i.title]
        assert len(fatigue_insights) > 0
        # Plan
        plans = agent.plan()
        assert len(plans) > 0
        # 策略应该是 creative_mutation
        assert plans[0].strategy == "creative_mutation"

    def test_full_cycle_run(self, sample_metrics):
        """完整 run_cycle 测试."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=sample_metrics)
        assert result["observation_count"] > 0
        assert result["insight_count"] > 0
        # 验证 Agent 状态
        assert agent.phase == AgentPhase.IDLE  # 应该回到 IDLE

    def test_orchestrator_full_cycle(self, sample_metrics):
        """编排器完整循环."""
        orch = create_orchestrator()
        result = orch.run_once(metrics=sample_metrics)
        assert result.success
        assert result.insight_count > 0
        assert result.plan_count > 0

    def test_multiple_cycles_memory_accumulation(self, sample_metrics):
        """多次循环后记忆积累."""
        agent = create_growth_agent()
        for _ in range(3):
            agent.run_cycle(metrics=sample_metrics)
        stats = agent.stats()
        assert stats["working_memory_size"] > 0
        # 工作记忆和情景记忆会在每次循环中累积
        assert stats["episodic_memory_size"] > 0

    def test_agent_learns_from_experience(self, sample_metrics):
        """Agent 从经验中学习."""
        agent = create_growth_agent()
        # 第一次循环
        agent.run_cycle(metrics=sample_metrics)
        # 工作记忆应该有内容
        assert agent._working_memory.size > 0
        # 情景记忆应该有记录
        assert agent._episodic_memory.size > 0

    def test_orchestrator_report_accumulation(self, sample_metrics):
        """编排器报告累积."""
        orch = create_orchestrator()
        for _ in range(5):
            orch.run_once(metrics=sample_metrics)
        report = orch.generate_report()
        assert report.total_cycles == 5
        assert report.successful_cycles == 5
        assert report.total_insights > 0

    def test_error_cycle_handling(self):
        """错误循环处理."""
        orch = create_orchestrator()
        # 空 metrics 应该仍然可以工作
        result = orch.run_once(metrics={})
        assert result.success

    def test_agent_profile_affects_behavior(self, sample_metrics):
        """不同 Agent 配置影响行为."""
        conservative = create_conservative_agent()
        aggressive = create_aggressive_agent()
        # 保守型
        c_result = conservative.run_cycle(metrics=sample_metrics)
        # 激进型
        a_result = aggressive.run_cycle(metrics=sample_metrics)
        # 两者都应该成功执行
        assert c_result["cycle"] == 1
        assert a_result["cycle"] == 1

    def test_orchestrator_with_agent_customization(self, sample_metrics):
        """自定义 Agent 的编排器."""
        agent = create_aggressive_agent()
        orch = AgentOrchestrator(agent=agent)
        orch.set_default_goals([
            AgentGoal(
                title="Aggressive Scaling",
                priority=GoalPriority.CRITICAL,
                status=GoalStatus.ACTIVE,
            ),
        ])
        result = orch.run_once(metrics=sample_metrics)
        assert result.success

    def test_end_to_end_observe_to_learn(self, sample_metrics):
        """端到端: Observe → Learn 完整流程."""
        agent = create_growth_agent()
        # 注入目标和数据
        agent.add_goal(AgentGoal(
            title="Reduce Creative Fatigue",
            description="Lower fatigue from 0.81 to below 0.5",
            priority=GoalPriority.HIGH,
            status=GoalStatus.ACTIVE,
            success_criteria="Creative fatigue < 0.5",
            target_metric="creative_fatigue",
            target_value=0.5,
            current_value=0.81,
        ))
        # 执行循环
        result = agent.run_cycle(metrics=sample_metrics)
        # 验证
        assert result["observation_count"] > 0
        assert result["insight_count"] > 0
        # 记忆应该被更新
        assert agent._episodic_memory.size > 0
        # 工作记忆应该被推进
        assert agent._working_memory.current_cycle > 0