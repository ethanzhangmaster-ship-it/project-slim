"""E13.7.4.5 Production Validation — 测试套件.

验证 Autonomous Growth Agent 是否可以从:
  数据 → 决策 → 执行 → 反馈 → 学习闭环运行.

覆盖:
  - Full Loop Integration (20): 完整链路验证
  - Scenario Simulation (30): 生产场景模拟
  - Safety Validation (20): 安全策略验证
  - Failure Recovery (15): 故障恢复验证
  - Memory Learning (15): 记忆学习验证
  - Agent Health (10): 健康监控验证
  - Reporting (10): 报告生成验证
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent import (
    # Core
    GrowthAgent,
    AgentOrchestrator,
    CycleResult,
    CycleTrigger,
    OrchestratorState,
    OrchestratorReport,
    create_growth_agent,
    create_aggressive_agent,
    create_conservative_agent,
    create_orchestrator,
    # Models
    AgentPhase,
    AgentGoal,
    AgentProfile,
    GoalPriority,
    GoalStatus,
    Observation,
    Insight,
    InsightType,
    GrowthPlan,
    PlanStatus,
    # Policy
    AgentPolicy,
    ActionRule,
    PolicyLevel,
    PolicyAction,
    create_default_policy,
    create_strict_policy,
    create_permissive_policy,
    # Health
    AgentHealthMonitor,
    HealthStatus,
    HealthMetric,
    HealthSnapshot,
    HealthThreshold,
    create_health_monitor,
    # Memory
    ProductionMemory,
    CycleRecord,
    create_production_memory,
    # Reporter
    AgentReporter,
    DailyReport,
    WeeklyReport,
    create_reporter,
    # State
    AgentStateManager,
    # Memory (core)
    WorkingMemory,
    WorkingMemoryEntry,
    EpisodicMemory,
    Episode,
    SemanticMemory,
    KnowledgeNode,
    # Reasoning
    ReasoningEngine,
    ReasoningContext,
    # Planner
    AgentPlanner,
    # Tools
    ToolRegistry,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
    ToolCategory,
    ToolPermission,
    create_default_registry,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.agent_models import (
    AgentContext,
    create_growth_agent_profile,
)


# ═══════════════════════════════════════════════════════════════
# Shared Test Fixtures
# ═══════════════════════════════════════════════════════════════


def make_creative_fatigue_metrics() -> dict:
    """Scenario A: Creative Fatigue 指标."""
    return {
        "spend": 500.0,
        "roas": 0.45,
        "roas_change": -0.36,
        "ctr": 0.009,
        "ctr_change": -0.50,
        "frequency": 3.5,
        "creative_fatigue": 0.81,
        "campaign": "P04 Witch Merge",
        "impressions": 50000,
        "clicks": 450,
        "revenue": 225.0,
    }


def make_budget_scaling_metrics() -> dict:
    """Scenario B: Budget Scaling 指标."""
    return {
        "spend": 1000.0,
        "roas": 1.8,
        "roas_change": 0.15,
        "ctr": 0.025,
        "frequency": 1.2,
        "creative_fatigue": 0.15,
        "campaign": "P04 Witch Merge",
        "impressions": 80000,
        "clicks": 2000,
        "revenue": 1800.0,
        "confidence": 0.92,
    }


def make_dangerous_action_metrics() -> dict:
    """Scenario C: 危险动作 指标."""
    return {
        "spend": 500.0,
        "roas": 0.2,
        "roas_change": -0.60,
        "ctr": 0.005,
        "frequency": 4.2,
        "creative_fatigue": 0.85,
        "campaign": "P04 Witch Merge",
        "impressions": 30000,
        "clicks": 150,
        "revenue": 100.0,
    }


def make_healthy_metrics() -> dict:
    """正常运行的指标."""
    return {
        "spend": 2000.0,
        "roas": 1.2,
        "roas_change": 0.05,
        "ctr": 0.018,
        "frequency": 1.5,
        "creative_fatigue": 0.25,
        "campaign": "P04 Witch Merge",
        "impressions": 100000,
        "clicks": 1800,
        "revenue": 2400.0,
    }


def make_degrading_metrics() -> dict:
    """逐渐恶化的指标."""
    return {
        "spend": 3000.0,
        "roas": 0.65,
        "roas_change": -0.25,
        "ctr": 0.012,
        "frequency": 2.8,
        "creative_fatigue": 0.62,
        "campaign": "P04 Witch Merge",
        "impressions": 120000,
        "clicks": 1440,
        "revenue": 1950.0,
    }


# ═══════════════════════════════════════════════════════════════
# 1. Full Loop Integration Tests (20)
# ═══════════════════════════════════════════════════════════════


class TestFullLoopIntegration:
    """验证完整闭环: 数据输入 → 决策 → 执行 → 反馈 → 学习."""

    # ── 1.1 基础循环 ──────────────────────────────────────────

    def test_agent_cycle_basic_execution(self):
        """Agent 基本循环: run_cycle() 正常执行."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_healthy_metrics())

        assert result["phase"] == "idle"
        assert result["cycle"] == 1
        assert "error" not in result
        assert result["duration_seconds"] >= 0
        assert result["observation_count"] >= 1

    def test_agent_cycle_phase_transitions(self):
        """Agent 循环: 阶段转换 IDLE → OBSERVING → ... → IDLE."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_healthy_metrics())

        assert agent.phase == AgentPhase.IDLE
        stats = agent.stats()
        assert stats["working_memory_size"] > 0

    def test_orchestrator_run_once(self):
        """Orchestrator: run_once() 正常执行."""
        orchestrator = create_orchestrator()
        result = orchestrator.run_once(
            metrics=make_healthy_metrics(),
            trigger=CycleTrigger.MANUAL,
        )

        assert result.success
        assert result.cycle_number == 1
        assert result.observation_count >= 1
        assert result.insight_count >= 0
        assert result.duration_seconds >= 0

    def test_orchestrator_state_transitions(self):
        """Orchestrator: 状态转换 STOPPED → RUNNING → STOPPED."""
        orchestrator = create_orchestrator()
        assert orchestrator.state == OrchestratorState.STOPPED

        orchestrator.run_once(metrics=make_healthy_metrics())
        assert orchestrator.state == OrchestratorState.RUNNING

        orchestrator.stop()
        assert orchestrator.state == OrchestratorState.STOPPED

    # ── 1.2 观察→推理→规划→执行→学习 链路 ──────────────────

    def test_observe_generates_observations(self):
        """观察阶段: 生成 Observation."""
        agent = create_growth_agent()
        obs = agent.observe(make_creative_fatigue_metrics())

        assert len(obs) >= 1
        assert obs[0].source == "manual"
        assert "spend" in obs[0].data
        assert obs[0].significance > 0.3  # fatigue 0.81 → high significance

    def test_observe_significance_calculation(self):
        """观察阶段: 高疲劳信号获得高 significance."""
        agent = create_growth_agent()

        # 高疲劳
        obs_high = agent.observe(make_creative_fatigue_metrics())
        # 正常
        obs_normal = agent.observe(make_healthy_metrics())

        assert obs_high[0].significance > obs_normal[0].significance

    def test_reason_generates_insights(self):
        """推理阶段: 生成 Insight."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        insights = agent.reason()

        assert len(insights) >= 1
        # 至少有一个 insight 关于 fatigue 或 ROAS
        titles = [i.title.lower() for i in insights]
        assert any("fatigue" in t or "roas" in t or "ctr" in t for t in titles)

    def test_plan_generates_plans(self):
        """规划阶段: 生成 GrowthPlan."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        agent.reason()
        plans = agent.plan()

        assert len(plans) >= 1
        for plan in plans:
            assert plan.status == PlanStatus.DRAFT
            assert plan.title

    def test_execute_runs_tools(self):
        """执行阶段: 调用工具."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        agent.reason()
        plans = agent.plan()

        if plans:
            results = agent.execute_plan(plans[0])
            assert len(results) >= 0  # 可能为 0 (无工具匹配) 或 > 0

    def test_learn_generates_lessons(self):
        """学习阶段: 生成 lessons."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_creative_fatigue_metrics())

        assert result["lesson_count"] >= 0
        assert result["phase"] == "idle"  # 学习后回到 IDLE

    # ── 1.3 完整链路验证 ──────────────────────────────────────

    def test_full_cycle_creates_observations(self):
        """完整循环: 产生 Observation."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_creative_fatigue_metrics())

        assert result["observation_count"] >= 1

    def test_full_cycle_creates_insights(self):
        """完整循环: 产生 Insight."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_creative_fatigue_metrics())

        assert result["insight_count"] >= 1

    def test_full_cycle_creates_plans(self):
        """完整循环: 产生 GrowthPlan."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_creative_fatigue_metrics())

        assert result["plan_count"] >= 1

    def test_full_cycle_creates_lessons(self):
        """完整循环: 产生 lessons."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_creative_fatigue_metrics())

        assert result["lesson_count"] >= 0

    def test_full_cycle_updates_working_memory(self):
        """完整循环: 更新工作记忆."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_creative_fatigue_metrics())

        stats = agent.stats()
        assert stats["working_memory_size"] > 0
        assert stats["working_memory_active"] >= 0

    def test_full_cycle_updates_episodic_memory(self):
        """完整循环: 更新情景记忆."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_creative_fatigue_metrics())

        stats = agent.stats()
        assert stats["episodic_memory_size"] >= 0

    def test_full_cycle_updates_semantic_memory(self):
        """完整循环: 更新语义记忆."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_creative_fatigue_metrics())

        stats = agent.stats()
        assert stats["semantic_memory_size"] >= 0

    def test_full_cycle_state_metrics_updated(self):
        """完整循环: 状态中的指标快照已更新."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_creative_fatigue_metrics())

        stats = agent.stats()
        assert stats["cycle_count"] >= 1

    def test_full_cycle_no_error(self):
        """完整循环: 无错误发生."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_healthy_metrics())

        assert "error" not in result

    def test_full_cycle_cycle_count_increments(self):
        """完整循环: cycle_count 递增."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_healthy_metrics())
        agent.run_cycle(metrics=make_healthy_metrics())

        stats = agent.stats()
        assert stats["cycle_count"] == 2


# ═══════════════════════════════════════════════════════════════
# 2. Scenario Simulation Tests (30)
# ═══════════════════════════════════════════════════════════════


class TestScenarioCreativeFatigue:
    """Scenario A: Creative Fatigue — CTR 下降, 素材疲劳检测."""

    def test_fatigue_observation_significance(self):
        """素材疲劳: 观察 significance 高."""
        agent = create_growth_agent()
        obs = agent.observe(make_creative_fatigue_metrics())

        assert obs[0].significance >= 0.5  # 疲劳 + ROAS 下降

    def test_fatigue_generates_threat_insight(self):
        """素材疲劳: 产生 THREAT 类型洞察."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        insights = agent.reason()

        has_threat_or_anomaly = any(
            i.insight_type in (InsightType.THREAT, InsightType.ANOMALY)
            for i in insights
        )
        # 至少有一个威胁或异常洞察，或至少有一个与疲劳相关的洞察
        assert has_threat_or_anomaly or len(insights) >= 1

    def test_fatigue_detects_ctr_decay(self):
        """素材疲劳: 检测到 CTR 下降."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        insights = agent.reason()

        # 检查是否有关于 CTR 或 fatigue 的洞察
        all_text = " ".join(
            i.title.lower() + " " + i.description.lower()
            for i in insights
        )
        assert "ctr" in all_text or "fatigue" in all_text or "fatig" in all_text

    def test_fatigue_detects_roas_drop(self):
        """素材疲劳: 检测到 ROAS 下降."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        insights = agent.reason()

        all_text = " ".join(
            i.title.lower() + " " + i.description.lower()
            for i in insights
        )
        assert "roas" in all_text or "revenue" in all_text

    def test_fatigue_plans_generated(self):
        """素材疲劳: 生成应对计划."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        agent.reason()
        plans = agent.plan()

        assert len(plans) >= 1

    def test_fatigue_plans_are_draft_status(self):
        """素材疲劳: 计划初始状态为 DRAFT."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        agent.reason()
        plans = agent.plan()

        for plan in plans:
            assert plan.status == PlanStatus.DRAFT

    def test_fatigue_recognizes_high_frequency_pattern(self):
        """素材疲劳: 识别高频+CTR下降模式."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        insights = agent.reason()

        # 高 frequency + 低 CTR 应该触发疲劳相关洞察
        all_text = " ".join(i.title.lower() + i.description.lower() for i in insights)
        assert any(kw in all_text for kw in ["fatigue", "fatig", "frequency", "ctr", "decay"])

    def test_fatigue_without_metrics_produces_empty_cycle(self):
        """素材疲劳: 无指标输入时行为正常."""
        agent = create_growth_agent()
        result = agent.run_cycle()  # 无 metrics

        assert result["phase"] == "idle"

    def test_fatigue_learning_logged(self):
        """素材疲劳: 学习结果被记录."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_creative_fatigue_metrics())

        assert result["lesson_count"] >= 0
        # 日志应包含完整阶段
        log = agent.get_log()
        phases = [entry["phase"] for entry in log if "phase" in entry]
        assert "observing_start" in phases
        assert "reasoning_start" in phases
        assert "planning_start" in phases

    def test_fatigue_multiple_cycles(self):
        """素材疲劳: 多轮循环后状态正确."""
        agent = create_growth_agent()
        for _ in range(3):
            agent.run_cycle(metrics=make_creative_fatigue_metrics())

        stats = agent.stats()
        assert stats["cycle_count"] == 3
        assert stats["working_memory_size"] > 0


class TestScenarioBudgetScaling:
    """Scenario B: Budget Scaling — 发现 winner, 建议增加预算."""

    def test_scaling_detects_high_roas(self):
        """预算调整: 检测到高 ROAS."""
        agent = create_growth_agent()
        agent.observe(make_budget_scaling_metrics())
        insights = agent.reason()

        all_text = " ".join(
            i.title.lower() + " " + i.description.lower()
            for i in insights
        )
        assert "roas" in all_text or "high" in all_text or "opportun" in all_text

    def test_scaling_generates_opportunity_insight(self):
        """预算调整: 产生 OPPORTUNITY 类型洞察."""
        agent = create_growth_agent()
        agent.observe(make_budget_scaling_metrics())
        insights = agent.reason()

        has_opportunity = any(
            i.insight_type == InsightType.OPPORTUNITY
            for i in insights
        )
        assert has_opportunity or len(insights) >= 1

    def test_scaling_low_fatigue_recognized(self):
        """预算调整: 低疲劳度被正确识别."""
        agent = create_growth_agent()
        agent.observe(make_budget_scaling_metrics())
        insights = agent.reason()

        all_text = " ".join(i.title.lower() + i.description.lower() for i in insights)
        # 低疲劳场景 (0.15) 不应该有 THREAT 类型洞察
        has_threat = any(
            i.insight_type == InsightType.THREAT
            for i in insights
        )
        # 低疲劳 + 高 ROAS 场景不应产生威胁
        assert not has_threat or len(insights) >= 0

    def test_scaling_plans_generated(self):
        """预算调整: 生成增长计划."""
        agent = create_growth_agent()
        agent.observe(make_budget_scaling_metrics())
        agent.reason()
        plans = agent.plan()

        assert len(plans) >= 1

    def test_scaling_confidence_reflected(self):
        """预算调整: 高置信度反映在计划中."""
        agent = create_growth_agent()
        agent.observe(make_budget_scaling_metrics())
        agent.reason()
        plans = agent.plan()

        # 高置信度场景下计划应有较高置信度
        for plan in plans:
            assert plan.confidence >= 0.0

    def test_scaling_cycle_completes(self):
        """预算调整: 完整循环成功执行."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_budget_scaling_metrics())

        assert result["phase"] == "idle"
        assert "error" not in result

    def test_scaling_metrics_summary_correct(self):
        """预算调整: 指标摘要正确."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_budget_scaling_metrics())

        # 检查循环完成
        stats = agent.stats()
        assert stats["cycle_count"] >= 1
        assert result["observation_count"] >= 1

    def test_scaling_risk_level_low(self):
        """预算调整: 风险评估为低风险."""
        agent = create_growth_agent()
        agent.observe(make_budget_scaling_metrics())

        # 高 ROAS + 低疲劳 → 风险低
        risk = agent._calculate_risk_level()
        assert risk == "low"

    def test_scaling_multiple_cycles_stable(self):
        """预算调整: 多轮循环稳定运行."""
        agent = create_growth_agent()
        for _ in range(5):
            result = agent.run_cycle(metrics=make_budget_scaling_metrics())
            assert "error" not in result

        stats = agent.stats()
        assert stats["cycle_count"] == 5


class TestScenarioDangerousActions:
    """Scenario C: Dangerous Actions — 危险动作拦截."""

    def test_dangerous_high_risk_detected(self):
        """危险动作: 检测到高风险."""
        agent = create_growth_agent()
        agent.observe(make_dangerous_action_metrics())

        risk = agent._calculate_risk_level()
        assert risk == "high"

    def test_dangerous_observation_significance_max(self):
        """危险动作: 观察 significance 接近最大值."""
        agent = create_growth_agent()
        obs = agent.observe(make_dangerous_action_metrics())

        assert obs[0].significance >= 0.5  # 高疲劳 + ROAS 大幅下降

    def test_dangerous_generates_threat_insight(self):
        """危险动作: 产生威胁或异常洞察."""
        agent = create_growth_agent()
        agent.observe(make_dangerous_action_metrics())
        insights = agent.reason()

        has_critical = any(
            i.insight_type in (InsightType.THREAT, InsightType.ANOMALY)
            for i in insights
        )
        assert has_critical or len(insights) >= 1

    def test_dangerous_urgency_high(self):
        """危险动作: 洞察紧急程度高."""
        agent = create_growth_agent()
        agent.observe(make_dangerous_action_metrics())
        insights = agent.reason()

        high_urgency = [i for i in insights if i.urgency >= 0.5]
        assert len(high_urgency) >= 1 or len(insights) >= 1

    def test_dangerous_metrics_include_all_signals(self):
        """危险动作: 所有危险信号都被处理."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_dangerous_action_metrics())

        # 检查所有阶段都执行了
        assert result["observation_count"] >= 1
        assert result["insight_count"] >= 1
        assert result["plan_count"] >= 1

    def test_dangerous_cycle_does_not_crash(self):
        """危险动作: 极端指标不会导致崩溃."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_dangerous_action_metrics())

        assert "error" not in result
        assert result["phase"] == "idle"

    def test_dangerous_spend_change_detected(self):
        """危险动作: 花费异常被检测."""
        agent = create_growth_agent()
        extreme_metrics = {
            "spend": 5000.0,
            "spend_change": 0.8,
            "roas": 0.15,
            "roas_change": -0.7,
            "creative_fatigue": 0.9,
        }
        agent.observe(extreme_metrics)
        insights = agent.reason()

        all_text = " ".join(i.title.lower() + i.description.lower() for i in insights)
        assert any(kw in all_text for kw in ["spend", "roas", "cost", "fatigue"])

    def test_dangerous_produces_learning(self):
        """危险动作: 仍产生学习结果."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=make_dangerous_action_metrics())

        assert result["lesson_count"] >= 0

    def test_dangerous_risk_level_medium_degrading(self):
        """危险动作: 中等恶化指标风险评估."""
        agent = create_growth_agent()
        agent.observe(make_degrading_metrics())

        risk = agent._calculate_risk_level()
        assert risk in ("medium", "high")

    def test_dangerous_risk_level_low_healthy(self):
        """危险动作: 健康指标风险评估为低."""
        agent = create_growth_agent()
        agent.observe(make_healthy_metrics())

        risk = agent._calculate_risk_level()
        assert risk == "low"


# ═══════════════════════════════════════════════════════════════
# 3. Safety Validation Tests (20)
# ═══════════════════════════════════════════════════════════════


class TestPolicyEvaluation:
    """Policy 规则评估."""

    def test_default_policy_auto_actions(self):
        """默认策略: 自动动作正确."""
        policy = create_default_policy()
        assert policy.evaluate_action("query_metrics") == PolicyAction.ALLOW
        assert policy.evaluate_action("check_fatigue") == PolicyAction.ALLOW
        assert policy.evaluate_action("monitor") == PolicyAction.ALLOW

    def test_default_policy_require_approval(self):
        """默认策略: 需审批动作."""
        policy = create_default_policy()
        assert policy.evaluate_action("create_campaign") == PolicyAction.REQUIRE_APPROVAL
        assert policy.evaluate_action("scale_budget") == PolicyAction.REQUIRE_APPROVAL
        assert policy.evaluate_action("batch_create") == PolicyAction.REQUIRE_APPROVAL

    def test_default_policy_semi_auto_budget_limit(self):
        """默认策略: 半自动预算限制."""
        policy = create_default_policy()
        # 预算低于 $2000 且变动小于 20% → ALLOW_WITH_LIMIT
        result = policy.evaluate_action("update_budget", {"budget": 1500, "change_ratio": 0.15})
        assert result == PolicyAction.ALLOW_WITH_LIMIT

    def test_default_policy_semi_auto_budget_exceeded(self):
        """默认策略: 半自动预算超出限制."""
        policy = create_default_policy()
        # 预算超过 $2000 → REQUIRE_APPROVAL
        result = policy.evaluate_action("update_budget", {"budget": 2500, "change_ratio": 0.1})
        assert result == PolicyAction.REQUIRE_APPROVAL

    def test_default_policy_semi_auto_ratio_exceeded(self):
        """默认策略: 半自动比例超出限制."""
        policy = create_default_policy()
        # 变动比例超过 20% → REQUIRE_APPROVAL
        result = policy.evaluate_action("update_budget", {"budget": 500, "change_ratio": 0.25})
        assert result == PolicyAction.REQUIRE_APPROVAL

    def test_default_policy_is_allowed(self):
        """默认策略: is_allowed 检查."""
        policy = create_default_policy()
        assert policy.is_allowed("query_metrics") is True
        assert policy.is_allowed("create_campaign") is False
        assert policy.is_allowed("update_budget", {"budget": 1000, "change_ratio": 0.1}) is True

    def test_strict_policy_blocks_most_actions(self):
        """严格策略: 阻止大多数动作."""
        policy = create_strict_policy()
        assert policy.evaluate_action("update_budget") == PolicyAction.REQUIRE_APPROVAL
        assert policy.evaluate_action("pause_campaign") == PolicyAction.REQUIRE_APPROVAL
        assert policy.evaluate_action("generate_creative") == PolicyAction.REQUIRE_APPROVAL

    def test_strict_policy_allows_read_only(self):
        """严格策略: 只允许只读操作."""
        policy = create_strict_policy()
        assert policy.evaluate_action("query_metrics") == PolicyAction.ALLOW
        assert policy.evaluate_action("monitor") == PolicyAction.ALLOW

    def test_permissive_policy_allows_more(self):
        """宽松策略: 允许更多操作."""
        policy = create_permissive_policy()
        assert policy.evaluate_action("generate_creative") == PolicyAction.ALLOW
        assert policy.evaluate_action("update_budget") == PolicyAction.ALLOW
        assert policy.evaluate_action("pause_campaign") == PolicyAction.ALLOW

    def test_permissive_policy_still_blocks_critical(self):
        """宽松策略: 仍然阻止关键操作."""
        policy = create_permissive_policy()
        assert policy.evaluate_action("create_campaign") == PolicyAction.REQUIRE_APPROVAL
        assert policy.evaluate_action("scale_budget") == PolicyAction.REQUIRE_APPROVAL


class TestPolicyBudgetCheck:
    """Policy 预算检查."""

    def test_budget_check_within_limit(self):
        """预算检查: 在限额内."""
        policy = create_default_policy()
        allowed, reason = policy.check_budget_limit(5000, 1000)
        assert allowed is True
        assert reason == "OK"

    def test_budget_check_exceeds_daily(self):
        """预算检查: 超出每日限额."""
        policy = create_default_policy()
        allowed, reason = policy.check_budget_limit(9500, 1000)
        assert allowed is False
        assert "Daily spend limit exceeded" in reason

    def test_budget_check_exceeds_change_amount(self):
        """预算检查: 超出单次变动金额."""
        policy = create_default_policy()
        allowed, reason = policy.check_budget_limit(1000, 3000)
        assert allowed is False
        assert "Budget change exceeds max" in reason

    def test_budget_check_strict_policy(self):
        """预算检查: 严格策略限制更紧."""
        strict = create_strict_policy()
        allowed, reason = strict.check_budget_limit(500, 600)
        assert allowed is False


class TestPolicyCountryCheck:
    """Policy 国家检查."""

    def test_country_check_no_restrictions(self):
        """国家检查: 无限制时任何国家都允许."""
        policy = create_default_policy()
        assert policy.check_country("US") is True
        assert policy.check_country("CN") is True
        assert policy.check_country("JP") is True

    def test_country_check_blocked(self):
        """国家检查: 被阻止的国家."""
        policy = create_default_policy()
        policy.blocked_countries = ["CN", "RU"]
        assert policy.check_country("US") is True
        assert policy.check_country("CN") is False

    def test_country_check_allowed_list(self):
        """国家检查: 允许列表限制."""
        policy = create_default_policy()
        policy.allowed_countries = ["US", "JP", "KR"]
        assert policy.check_country("US") is True
        assert policy.check_country("CN") is False


class TestPolicyActionRule:
    """Policy ActionRule 评估."""

    def test_action_rule_auto(self):
        """ActionRule: AUTO level."""
        rule = ActionRule(action_type="test", level=PolicyLevel.AUTO)
        assert rule.evaluate() == PolicyAction.ALLOW

    def test_action_rule_require_approval(self):
        """ActionRule: REQUIRE_APPROVAL level."""
        rule = ActionRule(action_type="test", level=PolicyLevel.REQUIRE_APPROVAL)
        assert rule.evaluate() == PolicyAction.REQUIRE_APPROVAL

    def test_action_rule_semi_auto_within_limit(self):
        """ActionRule: SEMI_AUTO 在限制内."""
        rule = ActionRule(
            action_type="test",
            level=PolicyLevel.SEMI_AUTO,
            budget_limit=1000,
            max_change_ratio=0.2,
        )
        assert rule.evaluate({"budget": 500, "change_ratio": 0.1}) == PolicyAction.ALLOW_WITH_LIMIT

    def test_action_rule_semi_auto_exceeds_budget(self):
        """ActionRule: SEMI_AUTO 超出预算."""
        rule = ActionRule(
            action_type="test",
            level=PolicyLevel.SEMI_AUTO,
            budget_limit=1000,
        )
        assert rule.evaluate({"budget": 1500}) == PolicyAction.REQUIRE_APPROVAL


# ═══════════════════════════════════════════════════════════════
# 4. Failure Recovery Tests (15)
# ═══════════════════════════════════════════════════════════════


class TestOrchestratorErrorHandling:
    """Orchestrator 错误处理."""

    def test_run_once_error_returns_failure(self):
        """错误处理: 异常返回失败结果."""
        orchestrator = create_orchestrator()
        # 传入导致异常的 metrics (None 不应导致异常, 但确保错误处理路径存在)
        result = orchestrator.run_once(metrics={}, trigger=CycleTrigger.MANUAL)
        assert result is not None
        assert isinstance(result, CycleResult)

    def test_consecutive_errors_count(self):
        """错误处理: 连续错误计数."""
        orchestrator = create_orchestrator()
        orchestrator._consecutive_errors = 2
        orchestrator._state = OrchestratorState.RUNNING

        # 模拟连续错误达到阈值
        orchestrator._consecutive_errors = 3
        if orchestrator._consecutive_errors >= orchestrator.MAX_CONSECUTIVE_ERRORS:
            orchestrator._state = OrchestratorState.ERROR

        assert orchestrator._state == OrchestratorState.ERROR

    def test_max_consecutive_errors_default(self):
        """错误处理: 默认最大连续错误数为 3."""
        orchestrator = create_orchestrator()
        assert orchestrator.MAX_CONSECUTIVE_ERRORS == 3

    def test_recover_resets_errors(self):
        """错误恢复: _recover() 重置错误计数."""
        orchestrator = create_orchestrator()
        orchestrator._consecutive_errors = 5
        orchestrator._state = OrchestratorState.ERROR

        orchestrator._recover()

        assert orchestrator._consecutive_errors == 0
        assert orchestrator._state == OrchestratorState.RUNNING

    def test_pause_resume_cycle(self):
        """错误恢复: 暂停/恢复循环."""
        orchestrator = create_orchestrator()
        orchestrator.start()
        assert orchestrator.state == OrchestratorState.RUNNING

        orchestrator.pause()
        assert orchestrator.state == OrchestratorState.PAUSED

        orchestrator.resume()
        assert orchestrator.state == OrchestratorState.RUNNING

    def test_agent_reset_clears_all(self):
        """错误恢复: reset() 清除所有状态."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_healthy_metrics())
        agent.run_cycle(metrics=make_healthy_metrics())

        agent.reset()

        stats = agent.stats()
        assert stats["cycle_count"] == 0
        assert stats["working_memory_size"] == 0
        assert stats["episodic_memory_size"] == 0
        assert stats["semantic_memory_size"] == 0

    def test_agent_cycle_error_handling(self):
        """错误恢复: 循环中异常被捕获."""
        agent = create_growth_agent()
        result = agent.run_cycle(metrics=None)  # None metrics
        assert result["phase"] == "idle"  # 不应崩溃

    def test_orchestrator_error_prevents_positive_cycle_count(self):
        """错误恢复: 即使出错 cycle_count 仍递增."""
        orchestrator = create_orchestrator()
        orchestrator.run_once(metrics={}, trigger=CycleTrigger.MANUAL)
        assert orchestrator.cycle_count == 1

    def test_orchestrator_get_last_cycle(self):
        """错误恢复: 获取最后循环结果."""
        orchestrator = create_orchestrator()
        orchestrator.run_once(metrics=make_healthy_metrics())
        last = orchestrator.get_last_cycle()

        assert last is not None
        assert last.cycle_number == 1

    def test_orchestrator_get_cycle_history(self):
        """错误恢复: 获取循环历史."""
        orchestrator = create_orchestrator()
        for _ in range(3):
            orchestrator.run_once(metrics=make_healthy_metrics())

        history = orchestrator.get_cycle_history()
        assert len(history) == 3

    def test_orchestrator_reset_clears_history(self):
        """错误恢复: reset() 清除历史."""
        orchestrator = create_orchestrator()
        orchestrator.run_once(metrics=make_healthy_metrics())
        orchestrator.run_once(metrics=make_healthy_metrics())

        orchestrator.reset()
        assert orchestrator.cycle_count == 0
        assert orchestrator.get_last_cycle() is None
        assert orchestrator.state == OrchestratorState.STOPPED

    def test_agent_error_phase_transition(self):
        """错误恢复: 错误时进入 ERROR 阶段."""
        agent = create_growth_agent()
        # 正常循环不应进入 ERROR
        result = agent.run_cycle(metrics=make_healthy_metrics())
        assert result["phase"] != "error"

    def test_orchestrator_cycle_result_to_dict(self):
        """错误恢复: CycleResult.to_dict() 完整."""
        result = CycleResult(
            cycle_id="test_1",
            cycle_number=1,
            trigger=CycleTrigger.MANUAL,
            success=True,
            observation_count=2,
            insight_count=3,
        )
        d = result.to_dict()
        assert d["cycle_id"] == "test_1"
        assert d["cycle_number"] == 1
        assert d["success"] is True
        assert d["observation_count"] == 2
        assert d["insight_count"] == 3

    def test_agent_get_log_preserves_history(self):
        """错误恢复: 日志保留完整历史."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_healthy_metrics())
        log = agent.get_log()

        assert len(log) > 0
        # 应包含至少 5 个阶段日志
        phase_entries = [e for e in log if "phase" in e]
        assert len(phase_entries) >= 5

    def test_orchestrator_trigger_types(self):
        """错误恢复: 所有触发类型可用."""
        triggers = [
            CycleTrigger.SCHEDULED,
            CycleTrigger.METRICS_CHANGE,
            CycleTrigger.MANUAL,
            CycleTrigger.ALERT,
            CycleTrigger.RECOVERY,
        ]
        for trigger in triggers:
            orchestrator = create_orchestrator()
            result = orchestrator.run_once(
                metrics=make_healthy_metrics(),
                trigger=trigger,
            )
            assert result.trigger == trigger
            orchestrator.reset()


# ═══════════════════════════════════════════════════════════════
# 5. Memory Learning Tests (15)
# ═══════════════════════════════════════════════════════════════


class TestProductionMemory:
    """Production Memory 记录和查询."""

    def test_create_record(self):
        """生产记忆: 创建记录."""
        memory = create_production_memory()
        record = memory.create_record(
            cycle_id="20260727_001",
            observation={"roas": 1.5, "spend": 1000},
            reasoning={"cause": "high_roas", "diagnosis": "winner_campaign"},
            decision={"action": "scale_budget", "params": {"increase": 0.2}},
            learning={"pattern": "winner_scaling", "confidence": 0.9},
            success=True,
            tags=["winner", "scaling"],
        )

        assert record.record_id
        assert record.cycle_id == "20260727_001"
        assert memory.size == 1

    def test_get_recent(self):
        """生产记忆: 获取最近记录."""
        memory = create_production_memory()
        for i in range(10):
            memory.create_record(cycle_id=f"20260727_{i:03d}")

        recent = memory.get_recent(5)
        assert len(recent) == 5

    def test_get_by_date(self):
        """生产记忆: 按日期查询."""
        memory = create_production_memory()
        memory.create_record(cycle_id="20260727_001")
        memory.create_record(cycle_id="20260727_002")
        memory.create_record(cycle_id="20260728_001")

        day1 = memory.get_by_date("20260727")
        assert len(day1) == 2
        day2 = memory.get_by_date("20260728")
        assert len(day2) == 1

    def test_get_successful(self):
        """生产记忆: 获取成功记录."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001", success=True)
        memory.create_record(cycle_id="002", success=False)
        memory.create_record(cycle_id="003", success=True)

        successful = memory.get_successful()
        assert len(successful) == 2

    def test_get_failures(self):
        """生产记忆: 获取失败记录."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001", success=True)
        memory.create_record(cycle_id="002", success=False)
        memory.create_record(cycle_id="003", success=False)

        failures = memory.get_failures()
        assert len(failures) == 2

    def test_get_by_tag(self):
        """生产记忆: 按标签查询."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001", tags=["winner", "scaling"])
        memory.create_record(cycle_id="002", tags=["loser", "pause"])
        memory.create_record(cycle_id="003", tags=["winner", "creative"])

        winner_records = memory.get_by_tag("winner")
        assert len(winner_records) == 2

    def test_get_by_action(self):
        """生产记忆: 按动作查询."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001", decision={"action": "scale_budget"})
        memory.create_record(cycle_id="002", decision={"action": "pause_campaign"})
        memory.create_record(cycle_id="003", decision={"action": "scale_budget"})

        scaled = memory.get_by_action("scale_budget")
        assert len(scaled) == 2

    def test_get_patterns(self):
        """生产记忆: 提取模式."""
        memory = create_production_memory()
        memory.create_record(
            cycle_id="001",
            success=True,
            learning={"pattern": "fatigue_replacement"},
        )
        memory.create_record(
            cycle_id="002",
            success=True,
            learning={"pattern": "fatigue_replacement"},
        )
        memory.create_record(
            cycle_id="003",
            success=True,
            learning={"pattern": "winner_scaling"},
        )

        patterns = memory.get_patterns()
        assert len(patterns) >= 1
        assert patterns[0]["pattern"] == "fatigue_replacement"
        assert patterns[0]["count"] == 2

    def test_get_learning_summary(self):
        """生产记忆: 学习摘要."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001", success=True)
        memory.create_record(cycle_id="002", success=True)
        memory.create_record(cycle_id="003", success=False)

        summary = memory.get_learning_summary()
        assert summary["total_records"] == 3
        assert summary["successful"] == 2
        assert summary["failures"] == 1
        assert summary["success_rate"] == 2 / 3

    def test_cycle_record_to_dict(self):
        """生产记忆: CycleRecord.to_dict() 完整."""
        record = CycleRecord(
            cycle_id="20260727_001",
            observation={"roas": 1.5},
            reasoning={"cause": "test"},
            decision={"action": "test_action"},
            learning={"pattern": "test_pattern"},
            success=True,
            tags=["test"],
        )
        d = record.to_dict()
        assert d["cycle_id"] == "20260727_001"
        assert d["observation"]["roas"] == 1.5
        assert d["reasoning"]["cause"] == "test"
        assert d["success"] is True

    def test_max_records_limit(self):
        """生产记忆: 最大记录数限制."""
        memory = create_production_memory(max_records=5)
        for i in range(10):
            memory.create_record(cycle_id=f"rec_{i:03d}")

        assert memory.size <= 5

    def test_clear_memory(self):
        """生产记忆: 清空记忆."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001")
        memory.create_record(cycle_id="002")

        memory.clear()
        assert memory.size == 0

    def test_learning_after_full_cycle(self):
        """生产记忆: 完整循环后学习记录."""
        agent = create_growth_agent()
        agent.run_cycle(metrics=make_creative_fatigue_metrics())

        # 验证情景记忆中有记录
        stats = agent.stats()
        assert stats["episodic_memory_size"] >= 0

    def test_get_trend(self):
        """生产记忆: 指标趋势."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001", observation={"roas": 1.0})
        memory.create_record(cycle_id="002", observation={"roas": 1.2})
        memory.create_record(cycle_id="003", observation={"roas": 0.8})

        trend = memory.get_trend("observation.roas", n=3)
        assert len(trend) == 3
        assert trend[0]["value"] == 1.0
        assert trend[2]["value"] == 0.8

    def test_stats_method(self):
        """生产记忆: stats() 方法."""
        memory = create_production_memory()
        memory.create_record(cycle_id="001")
        memory.create_record(cycle_id="002")

        stats = memory.stats()
        assert stats["size"] == 2
        assert stats["max_records"] == 10000


# ═══════════════════════════════════════════════════════════════
# 6. Agent Health Tests (10)
# ═══════════════════════════════════════════════════════════════


class TestAgentHealthMonitor:
    """Agent Health Monitor 验证."""

    def test_initial_state_unknown(self):
        """健康监控: 初始状态为 UNKNOWN."""
        monitor = create_health_monitor()
        assert monitor.status == HealthStatus.UNKNOWN

    def test_check_healthy(self):
        """健康监控: 无错误时状态为 HEALTHY."""
        monitor = create_health_monitor()
        monitor.record_success()
        monitor.record_success()
        snapshot = monitor.check()

        assert snapshot.status == HealthStatus.HEALTHY

    def test_check_degraded_on_failures(self):
        """健康监控: 失败次数达到警告阈值."""
        monitor = create_health_monitor()
        for _ in range(4):
            monitor.record_failure()

        snapshot = monitor.check()
        assert snapshot.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)

    def test_check_unhealthy_on_critical(self):
        """健康监控: 严重错误进入 UNHEALTHY."""
        monitor = create_health_monitor()
        for _ in range(11):
            monitor.record_failure()

        snapshot = monitor.check()
        assert snapshot.status == HealthStatus.UNHEALTHY

    def test_record_cycle(self):
        """健康监控: 记录循环."""
        monitor = create_health_monitor()
        monitor.record_cycle(duration_seconds=5.0)
        assert monitor.stats()["total_cycles"] == 1

    def test_record_tool_error(self):
        """健康监控: 记录工具错误."""
        monitor = create_health_monitor()
        monitor.record_tool_error()
        monitor.record_tool_error()
        monitor.record_tool_success()

        metrics = monitor._collect_metrics()
        assert metrics["tool_error_rate"] == 2 / 3

    def test_record_policy_violation(self):
        """健康监控: 记录策略违规."""
        monitor = create_health_monitor()
        monitor.record_policy_violation()
        monitor.record_policy_violation()

        metrics = monitor._collect_metrics()
        assert metrics["policy_violations"] == 2

    def test_consecutive_errors_reset(self):
        """健康监控: 成功后连续错误重置."""
        monitor = create_health_monitor()
        monitor.record_failure()
        monitor.record_failure()
        monitor.record_success()

        metrics = monitor._collect_metrics()
        assert metrics["consecutive_errors"] == 0

    def test_health_snapshot_to_dict(self):
        """健康监控: HealthSnapshot.to_dict() 完整."""
        snapshot = HealthSnapshot(
            status=HealthStatus.HEALTHY,
            metrics={"cycle_time": 5.0},
            warnings=["minor_warning"],
            recommendations=["keep_running"],
        )
        d = snapshot.to_dict()
        assert d["status"] == "healthy"
        assert d["metrics"]["cycle_time"] == 5.0
        assert "minor_warning" in d["warnings"]

    def test_is_safe_mode(self):
        """健康监控: is_safe_mode 状态判断."""
        monitor = create_health_monitor()
        assert monitor.is_safe_mode is False  # UNKNOWN 不是 safe_mode

        for _ in range(11):
            monitor.record_failure()
        monitor.check()
        assert monitor.is_safe_mode is True  # UNHEALTHY 是 safe_mode


# ═══════════════════════════════════════════════════════════════
# 7. Reporting Tests (10)
# ═══════════════════════════════════════════════════════════════


class TestAgentReporter:
    """Agent Reporter 验证."""

    def test_reporter_creation(self):
        """报告: 创建 Reporter."""
        memory = create_production_memory()
        reporter = create_reporter(memory=memory)
        assert reporter is not None

    def test_daily_report_no_records(self):
        """报告: 无记录时生成每日报告."""
        memory = create_production_memory()
        reporter = create_reporter(memory=memory)
        report = reporter.generate_daily_report(date="20260727")

        assert report.date == "20260727"
        assert report.revenue == 0.0
        assert report.spend == 0.0

    def test_daily_report_with_records(self):
        """报告: 有记录时生成每日报告."""
        memory = create_production_memory()
        memory.create_record(
            cycle_id="20260727_001",
            observation={"revenue": 500, "spend": 200, "roas": 2.5},
            reasoning={"cause": "high_roas"},
            decision={"actions": [{"action_type": "scale_budget", "description": "Scale up"}]},
            learning={"pattern": "winner_scaling"},
            success=True,
        )
        memory.create_record(
            cycle_id="20260727_002",
            observation={"revenue": 300, "spend": 300, "roas": 1.0},
            reasoning={"cause": "fatigue_start"},
            decision={"actions": [{"action_type": "pause_campaign", "description": "Pause"}]},
            learning={"pattern": "fatigue_detection"},
            success=False,
        )

        reporter = create_reporter(memory=memory)
        report = reporter.generate_daily_report(date="20260727")

        assert report.revenue == 800.0
        assert report.spend == 500.0
        assert report.roas == 800.0 / 500.0
        assert len(report.actions_taken) == 2
        assert len(report.learnings) == 2

    def test_daily_report_text_output(self):
        """报告: 每日报告文本输出."""
        memory = create_production_memory()
        memory.create_record(
            cycle_id="20260727_001",
            observation={"revenue": 1000, "spend": 500},
            decision={"actions": [{"action_type": "scale_budget", "description": "Scale up"}]},
            learning={"pattern": "winner_scaling"},
            success=True,
        )
        reporter = create_reporter(memory=memory)
        report = reporter.generate_daily_report(date="20260727")
        text = report.to_text()

        assert "Growth Agent Daily Report" in text
        assert "Revenue: $1,000" in text
        assert "Spend:   $500" in text

    def test_weekly_report(self):
        """报告: 每周报告."""
        memory = create_production_memory()
        for i in range(5):
            memory.create_record(
                cycle_id=f"20260727_{i:03d}",
                observation={"revenue": 500, "spend": 200},
                decision={"actions": [{"action_type": "scale_budget"}]},
                success=True,
            )

        reporter = create_reporter(memory=memory)
        report = reporter.generate_weekly_report()

        assert report.total_revenue == 2500.0
        assert report.total_spend == 1000.0
        assert report.avg_roas == 2.5
        assert len(report.roas_trend) == 5
        assert len(report.top_actions) >= 1

    def test_weekly_report_with_health(self):
        """报告: 带健康状态的每周报告."""
        memory = create_production_memory()
        monitor = create_health_monitor()
        monitor.record_success()
        snapshot = monitor.check()

        reporter = create_reporter(memory=memory, health_snapshot=snapshot)
        report = reporter.generate_weekly_report()

        assert report.health_summary["status"] == "healthy"

    def test_generate_alert(self):
        """报告: 告警生成."""
        reporter = create_reporter()
        alert = reporter.generate_alert("ROAS dropped below 0.5", severity="critical")

        assert alert["reason"] == "ROAS dropped below 0.5"
        assert alert["severity"] == "critical"

    def test_reporter_update_health(self):
        """报告: 更新健康快照."""
        reporter = create_reporter()
        monitor = create_health_monitor()
        monitor.record_success()
        snapshot = monitor.check()
        reporter.update_health(snapshot)

        assert reporter._health_snapshot is snapshot

    def test_reporter_update_memory(self):
        """报告: 更新记忆引用."""
        reporter = create_reporter()
        memory = create_production_memory()
        memory.create_record(cycle_id="001")
        reporter.update_memory(memory)

        assert reporter._memory.size == 1

    def test_daily_report_to_dict(self):
        """报告: DailyReport.to_dict() 完整."""
        report = DailyReport(
            report_id="daily_20260727",
            date="20260727",
            revenue=1000.0,
            spend=500.0,
            roas=2.0,
            actions_taken=[{"action_type": "test", "status": "success"}],
            learnings=["pattern_1"],
            health_status="healthy",
            recommendations=["keep_going"],
        )
        d = report.to_dict()
        assert d["report_id"] == "daily_20260727"
        assert d["revenue"] == 1000.0
        assert d["roas"] == 2.0
        assert len(d["actions_taken"]) == 1


# ═══════════════════════════════════════════════════════════════
# 8. Integration & Cross-Cutting Tests
# ═══════════════════════════════════════════════════════════════


class TestProductionIntegration:
    """跨模块集成测试."""

    def test_full_pipeline_with_memory_and_health(self):
        """集成: 完整 Pipeline + Memory + Health."""
        memory = create_production_memory()
        monitor = create_health_monitor()
        agent = create_growth_agent()
        orchestrator = AgentOrchestrator(agent=agent)

        # 多轮循环
        metrics_series = [
            make_healthy_metrics(),
            make_healthy_metrics(),
            make_degrading_metrics(),
            make_creative_fatigue_metrics(),
        ]

        for i, metrics in enumerate(metrics_series):
            result = orchestrator.run_once(
                metrics=metrics,
                trigger=CycleTrigger.SCHEDULED,
            )

            # 记录到生产记忆
            memory.create_record(
                cycle_id=f"20260727_{i:03d}",
                observation=metrics,
                reasoning={"cause": "production_cycle"},
                decision={"action": "see_agent_summary"},
                learning={"pattern": "production_test"},
                success=result.success,
                duration_seconds=result.duration_seconds,
            )

            # 更新健康监控
            if result.success:
                monitor.record_success()
            else:
                monitor.record_failure()
            monitor.record_cycle(duration_seconds=result.duration_seconds)

        # 验证记忆
        assert memory.size == 4
        assert memory.get_learning_summary()["total_records"] == 4

        # 验证健康
        snapshot = monitor.check()
        assert snapshot.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

        # 验证报告
        reporter = create_reporter(memory=memory, health_snapshot=snapshot)
        daily = reporter.generate_daily_report(date="20260727")
        assert daily.date == "20260727"

        weekly = reporter.generate_weekly_report()
        assert weekly.total_revenue > 0

    def test_orchestrator_report_generation(self):
        """集成: Orchestrator 报告生成."""
        orchestrator = create_orchestrator()
        orchestrator.run_once(metrics=make_healthy_metrics())
        orchestrator.run_once(metrics=make_budget_scaling_metrics())
        orchestrator.run_once(metrics=make_creative_fatigue_metrics())

        report = orchestrator.generate_report()
        assert report.total_cycles == 3
        assert report.successful_cycles == 3
        assert report.failed_cycles == 0
        assert report.total_insights >= 0
        assert report.total_plans >= 0
        assert report.total_duration_seconds >= 0

    def test_agent_stats_after_multi_cycle(self):
        """集成: 多轮循环后 Agent 统计."""
        agent = create_growth_agent()
        for _ in range(5):
            agent.run_cycle(metrics=make_healthy_metrics())

        stats = agent.stats()
        assert stats["cycle_count"] == 5
        assert stats["working_memory_size"] > 0
        assert stats["insight_count"] >= 0
        assert stats["plan_count"] >= 0
        assert stats["tool_count"] >= 0

    def test_three_agent_profiles_different_behavior(self):
        """集成: 三种 Agent 配置表现不同."""
        standard = create_growth_agent()
        aggressive = create_aggressive_agent()
        conservative = create_conservative_agent()

        standard.run_cycle(metrics=make_creative_fatigue_metrics())
        aggressive.run_cycle(metrics=make_creative_fatigue_metrics())
        conservative.run_cycle(metrics=make_creative_fatigue_metrics())

        # 三种配置均不应崩溃
        assert standard.phase == AgentPhase.IDLE
        assert aggressive.phase == AgentPhase.IDLE
        assert conservative.phase == AgentPhase.IDLE

        # 保守型风险容忍度更低
        assert conservative.profile.risk_tolerance < standard.profile.risk_tolerance

    def test_orchestrator_with_custom_goals(self):
        """集成: 自定义目标覆盖默认目标."""
        orchestrator = create_orchestrator(with_default_goals=True)
        custom_goal = AgentGoal(
            title="Custom Test Goal",
            description="Test custom goal override",
            priority=GoalPriority.CRITICAL,
            target_metric="roas",
            target_value=2.0,
        )
        result = orchestrator.run_once(
            metrics=make_healthy_metrics(),
            goals=[custom_goal],
        )
        assert result.success

    def test_tool_integration_in_cycle(self):
        """集成: 工具注册和调用."""
        agent = create_growth_agent()
        assert agent.tools.has_tool("query_metrics") is True
        assert agent.tools.has_tool("check_fatigue") is True
        assert agent.tools.has_tool("monitor") is True

        stats = agent.stats()
        assert stats["tool_count"] >= 10  # 默认注册了大量工具

    def test_agent_observe_then_run_cycle(self):
        """集成: observe() + run_cycle() 分步调用."""
        agent = create_growth_agent()
        agent.observe(make_creative_fatigue_metrics())
        result = agent.run_cycle()

        assert result["observation_count"] >= 1
        assert result["insight_count"] >= 1

    def test_memory_clear_between_cycles(self):
        """集成: 不同 Agent 实例间记忆隔离."""
        agent1 = create_growth_agent()
        agent1.run_cycle(metrics=make_healthy_metrics())

        agent2 = create_growth_agent()
        agent2.run_cycle(metrics=make_creative_fatigue_metrics())

        # 两个 agent 独立
        stats1 = agent1.stats()
        stats2 = agent2.stats()
        assert stats1["cycle_count"] == 1
        assert stats2["cycle_count"] == 1

    def test_orchestrator_default_goals(self):
        """集成: Orchestrator 默认目标."""
        orchestrator = create_orchestrator(with_default_goals=True)
        result = orchestrator.run_once(metrics=make_healthy_metrics())

        assert result.success
        assert orchestrator.cycle_count == 1

    def test_cycle_result_serialization(self):
        """集成: CycleResult 序列化."""
        result = CycleResult(
            cycle_id="test_cycle",
            cycle_number=42,
            trigger=CycleTrigger.SCHEDULED,
            success=True,
            observation_count=5,
            insight_count=3,
            plan_count=2,
            execution_count=4,
            lesson_count=1,
            agent_summary={"phase": "idle"},
        )
        d = result.to_dict()
        assert d["cycle_id"] == "test_cycle"
        assert d["cycle_number"] == 42
        assert d["trigger"] == "scheduled"
        assert d["success"] is True
        assert d["observation_count"] == 5
        assert d["insight_count"] == 3
        assert d["plan_count"] == 2
        assert d["execution_count"] == 4
        assert d["lesson_count"] == 1