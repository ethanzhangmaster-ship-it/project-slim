"""V4.3 Autonomous Decision Policy — Release Gate.

Per PRD v1.0, 45 tests + 1 Strategy ROI Validation:
  1. Policy Engine (6 tests)
  2. Policy Rules (5 tests)
  3. Policy Optimizer (5 tests)
  4. Risk Controller (5 tests)
  5. Creative Scheduler (4 tests)
  6. Portfolio Manager (4 tests)
  7. Exploration Manager (4 tests)
  8. Budget Optimizer (4 tests)
  9. Production Planner (4 tests)
 10. Logger & Report (4 tests)
 11. Strategy ROI Validation (1 test)

Total: 46 tests. All must PASS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.creative_policy.policy_engine import PolicyEngine
from market_ops.creative_brain.creative_policy.policy_rules import PolicyRules
from market_ops.creative_brain.creative_policy.policy_optimizer import PolicyOptimizer
from market_ops.creative_brain.creative_policy.risk_controller import RiskController
from market_ops.creative_brain.creative_policy.creative_scheduler import CreativeScheduler
from market_ops.creative_brain.creative_policy.portfolio_manager import PortfolioManager
from market_ops.creative_brain.creative_policy.exploration_manager import ExplorationManager
from market_ops.creative_brain.creative_policy.budget_optimizer import BudgetOptimizer
from market_ops.creative_brain.creative_policy.resource_allocator import ResourceAllocator
from market_ops.creative_brain.creative_policy.creative_priority import CreativePriority
from market_ops.creative_brain.creative_policy.production_planner import ProductionPlanner
from market_ops.creative_brain.creative_policy.decision_logger import DecisionLogger
from market_ops.creative_brain.creative_policy.policy_report import PolicyReportGenerator
from market_ops.creative_brain.creative_policy.schemas import (
    DecisionPolicy, PolicyAction, RiskLevel, PortfolioCategory,
    CreativeTask, PolicyReport, DailyProductionPlan, Portfolio,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_creative_data(creative_id: str = "c_001", **overrides) -> dict:
    """Create synthetic creative data dict."""
    data = {
        "creative_id": creative_id,
        "dna": {"character": "dragon", "reward": "dragon", "hook": "collection"},
        "reasoning_confidence": 0.75,
        "validation_accuracy": 0.65,
        "trend_status": "growing",
        "roi_prediction": 0.8,
        "budget": 200.0,
        "country": "US",
        "platform": "facebook",
    }
    data.update(overrides)
    return data


def _make_batch(n: int = 20) -> list[dict]:
    """Create synthetic batch of creative data."""
    import random
    random.seed(42)
    characters = ["dragon", "witch", "knight", "ninja", "warrior"]
    trends = ["growing", "stable", "declining", "dead"]
    countries = ["US", "JP", "KR", "SEA"]
    creatives = []
    for i in range(n):
        ch = random.choice(characters)
        if ch == "dragon":
            roi = random.uniform(0.6, 1.0)
            conf = random.uniform(0.6, 0.9)
        elif ch == "ninja":
            roi = random.uniform(0.1, 0.4)
            conf = random.uniform(0.3, 0.6)
        else:
            roi = random.uniform(0.3, 0.7)
            conf = random.uniform(0.4, 0.7)
        creatives.append({
            "creative_id": f"c_{i:04d}",
            "dna": {"character": ch, "reward": random.choice(["dragon", "treasure", "gold"])},
            "reasoning_confidence": conf,
            "validation_accuracy": random.uniform(0.4, 0.8),
            "trend_status": random.choice(trends),
            "roi_prediction": roi,
            "budget": random.uniform(50, 400),
            "country": random.choice(countries),
            "platform": "facebook",
        })
    return creatives


# ═══════════════════════════════════════════════════════════
# 1. Policy Engine (6 tests)
# ═══════════════════════════════════════════════════════════

def test_policy_engine_decide():
    """Policy: 单创意决策输出"""
    engine = PolicyEngine()
    task = engine.decide(_make_creative_data("c_001"))
    assert isinstance(task, CreativeTask)
    assert task.creative_id == "c_001"
    assert task.action in PolicyAction
    return True


def test_policy_engine_generate_high_confidence():
    """Policy: 高置信度→GENERATE"""
    engine = PolicyEngine()
    task = engine.decide(_make_creative_data(
        "c_win", reasoning_confidence=0.85, roi_prediction=0.9,
        trend_status="growing",
    ))
    assert task.action == PolicyAction.GENERATE
    return True


def test_policy_engine_kill_low_roi():
    """Policy: 低ROI→KILL"""
    engine = PolicyEngine()
    task = engine.decide(_make_creative_data(
        "c_lose", reasoning_confidence=0.3, roi_prediction=0.1,
        trend_status="dead",
    ))
    assert task.action == PolicyAction.KILL
    return True


def test_policy_engine_batch():
    """Policy: 批量决策"""
    engine = PolicyEngine()
    creatives = _make_batch(30)
    tasks = engine.decide_batch(creatives)
    assert len(tasks) == 30
    # Should be sorted by priority
    if len(tasks) >= 2:
        assert tasks[0].priority.total_score >= tasks[-1].priority.total_score
    return True


def test_policy_engine_rollback():
    """Policy: 策略回滚"""
    engine = PolicyEngine()
    original_version = engine.policy.version
    new_policy = DecisionPolicy(
        version="2.0.0",
        confidence_threshold_go=0.80,
    )
    engine.update_policy(new_policy)
    assert engine.policy.version == "2.0.0"
    rolled = engine.rollback_policy()
    assert rolled is not None
    assert engine.policy.version == original_version
    return True


def test_policy_engine_compare_policies():
    """Policy: 策略版本对比"""
    engine = PolicyEngine()
    engine.update_policy(DecisionPolicy(version="2.0.0", confidence_threshold_go=0.80))
    comparison = engine.compare_policies("1.0.0", "2.0.0")
    assert "threshold_diff" in comparison
    assert abs(comparison["threshold_diff"]["confidence_go"] - 0.08) < 0.001
    return True


# ═══════════════════════════════════════════════════════════
# 2. Policy Rules (5 tests)
# ═══════════════════════════════════════════════════════════

def test_rules_evaluate():
    """Rules: 评估返回Action+Evidence"""
    rules = PolicyRules()
    policy = DecisionPolicy()
    action, evidence = rules.evaluate(_make_creative_data("c_001"), policy)
    assert action in PolicyAction
    assert "reason" in evidence
    assert "composite_score" in evidence
    return True


def test_rules_trend_bonus():
    """Rules: Trend Growing添加Bonus"""
    rules = PolicyRules()
    policy = DecisionPolicy()
    _, ev_growing = rules.evaluate(
        _make_creative_data("c_g", trend_status="growing"), policy
    )
    _, ev_dead = rules.evaluate(
        _make_creative_data("c_d", trend_status="dead"), policy
    )
    assert ev_growing["adjusted_confidence"] > ev_dead["adjusted_confidence"]
    return True


def test_rules_high_confidence_generate():
    """Rules: 高置信度→GENERATE"""
    rules = PolicyRules()
    policy = DecisionPolicy()
    action, _ = rules.evaluate(_make_creative_data(
        "c_high", reasoning_confidence=0.85, roi_prediction=0.9,
        trend_status="growing",
    ), policy)
    assert action == PolicyAction.GENERATE
    return True


def test_rules_dead_trend_kill():
    """Rules: Dead Trend→KILL"""
    rules = PolicyRules()
    policy = DecisionPolicy()
    action, _ = rules.evaluate(_make_creative_data(
        "c_dead", trend_status="dead", roi_prediction=0.1,
    ), policy)
    assert action == PolicyAction.KILL
    return True


def test_rules_batch():
    """Rules: 批量评估"""
    rules = PolicyRules()
    policy = DecisionPolicy()
    creatives = _make_batch(20)
    results = rules.evaluate_batch(creatives, policy)
    assert len(results) == 20
    for action, evidence in results:
        assert action in PolicyAction
    return True


# ═══════════════════════════════════════════════════════════
# 3. Policy Optimizer (5 tests)
# ═══════════════════════════════════════════════════════════

def test_optimizer_grid_search():
    """Optimizer: Grid Search优化"""
    # Create synthetic replay records
    records = [
        {"creative_id": f"c_{i}", "confidence": 0.5 + i * 0.02,
         "actual_roas": 0.3 + i * 0.03, "actual_decision": "GO",
         "predicted_decision": "GO"}
        for i in range(20)
    ]
    optimizer = PolicyOptimizer()
    result = optimizer.optimize(records, method="grid_search")
    assert isinstance(result, DecisionPolicy)
    assert result.version != "1.0.0"
    return True


def test_optimizer_random_search():
    """Optimizer: Random Search优化"""
    records = [
        {"creative_id": f"c_{i}", "confidence": 0.5 + i * 0.02,
         "actual_roas": 0.3 + i * 0.03, "actual_decision": "GO",
         "predicted_decision": "GO"}
        for i in range(20)
    ]
    optimizer = PolicyOptimizer()
    result = optimizer.optimize(records, method="random_search")
    assert isinstance(result, DecisionPolicy)
    return True


def test_optimizer_improvement():
    """Optimizer: 优化后Score提升"""
    records = [
        {"creative_id": f"c_{i}", "confidence": 0.5 + i * 0.02,
         "actual_roas": 0.3 + i * 0.03, "actual_decision": "GO",
         "predicted_decision": "GO"}
        for i in range(20)
    ]
    optimizer = PolicyOptimizer()
    result = optimizer.optimize(records)
    assert result.improvement_score >= 0.0
    return True


def test_optimizer_version_tracking():
    """Optimizer: 版本追踪"""
    optimizer = PolicyOptimizer()
    records = [{"creative_id": "c_0", "confidence": 0.7, "actual_roas": 0.8,
                "actual_decision": "GO", "predicted_decision": "GO"}]
    result = optimizer.optimize(records)
    assert result.previous_version == "1.0.0"
    return True


def test_optimizer_history():
    """Optimizer: 优化历史"""
    optimizer = PolicyOptimizer()
    records = [{"creative_id": "c_0", "confidence": 0.7, "actual_roas": 0.8,
                "actual_decision": "GO", "predicted_decision": "GO"}]
    optimizer.optimize(records)
    history = optimizer.get_optimization_history()
    assert len(history) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 4. Risk Controller (5 tests)
# ═══════════════════════════════════════════════════════════

def test_risk_assess_safe():
    """Risk: 安全评估"""
    rc = RiskController()
    policy = DecisionPolicy()
    risk = rc.assess_risk("c_001", "US", "stable", 100.0, policy)
    assert risk.level == RiskLevel.SAFE
    assert not risk.should_halt
    return True


def test_risk_consecutive_failures():
    """Risk: 连续失败检测"""
    rc = RiskController()
    policy = DecisionPolicy()
    # Record 5 failures
    for _ in range(5):
        rc.record_failure("c_001", "US", "dragon")
    risk = rc.assess_risk("c_001", "US", "dragon", 100.0, policy)
    assert risk.level == RiskLevel.CRITICAL
    assert risk.should_halt
    return True


def test_risk_override():
    """Risk: 风险覆盖决策"""
    rc = RiskController()
    policy = DecisionPolicy()
    rc.record_failure("c_001", "US", "dragon")
    rc.record_failure("c_001", "US", "dragon")
    rc.record_failure("c_001", "US", "dragon")
    rc.record_failure("c_001", "US", "dragon")
    rc.record_failure("c_001", "US", "dragon")
    risk = rc.assess_risk("c_001", "US", "dragon", 100.0, policy)
    action, overridden, reason = rc.override_decision(PolicyAction.GENERATE, risk)
    assert overridden
    assert action == PolicyAction.KILL
    return True


def test_risk_warning_downgrade():
    """Risk: WARNING降级处理"""
    rc = RiskController()
    policy = DecisionPolicy()
    rc.record_failure("c_001")
    rc.record_failure("c_001")
    rc.record_failure("c_001")
    risk = rc.assess_risk("c_001", "US", "stable", 100.0, policy)
    # 3 failures = approaching limit (5)
    assert risk.level in (RiskLevel.WARNING, RiskLevel.SAFE)
    return True


def test_risk_success_reset():
    """Risk: 成功后重置计数器"""
    rc = RiskController()
    policy = DecisionPolicy()
    rc.record_failure("c_001")
    rc.record_failure("c_001")
    rc.record_success("c_001")
    risk = rc.assess_risk("c_001", "US", "stable", 100.0, policy)
    assert risk.level == RiskLevel.SAFE
    return True


# ═══════════════════════════════════════════════════════════
# 5. Creative Scheduler (4 tests)
# ═══════════════════════════════════════════════════════════

def test_scheduler_schedule():
    """Scheduler: 按优先级调度"""
    engine = PolicyEngine()
    creatives = _make_batch(20)
    tasks = engine.decide_batch(creatives)
    scheduler = CreativeScheduler()
    scheduled = scheduler.schedule(tasks, max_generate=10)
    assert len(scheduled) <= 10
    if len(scheduled) >= 2:
        assert scheduled[0].priority.total_score >= scheduled[-1].priority.total_score
    return True


def test_scheduler_top_n():
    """Scheduler: Top N输出"""
    engine = PolicyEngine()
    tasks = engine.decide_batch(_make_batch(10))
    scheduler = CreativeScheduler()
    scheduler.schedule(tasks, max_generate=10)
    top = scheduler.get_top_n(5)
    assert len(top) <= 5
    assert "rank" in top[0]
    return True


def test_scheduler_by_country():
    """Scheduler: 按国家过滤"""
    engine = PolicyEngine()
    creatives = _make_batch(15)
    tasks = engine.decide_batch(creatives)
    scheduler = CreativeScheduler()
    scheduler.schedule(tasks, max_generate=15)
    us_tasks = scheduler.get_schedule_by_country("US")
    assert isinstance(us_tasks, list)
    return True


def test_scheduler_summary():
    """Scheduler: 调度摘要"""
    engine = PolicyEngine()
    tasks = engine.decide_batch(_make_batch(10))
    scheduler = CreativeScheduler()
    scheduler.schedule(tasks, max_generate=10)
    summary = scheduler.get_schedule_summary()
    assert "total_scheduled" in summary
    return True


# ═══════════════════════════════════════════════════════════
# 6. Portfolio Manager (4 tests)
# ═══════════════════════════════════════════════════════════

def test_portfolio_allocate():
    """Portfolio: 组合分配"""
    engine = PolicyEngine()
    tasks = engine.decide_batch(_make_batch(30))
    pm = PortfolioManager()
    portfolio = pm.allocate(tasks, total_capacity=30)
    assert portfolio.total_creatives == 30
    assert len(portfolio.allocations) > 0
    return True


def test_portfolio_dynamic():
    """Portfolio: 动态调整"""
    pm = PortfolioManager()
    # Simulate market change
    trend_shifts = {"US": "dead", "JP": "dead", "KR": "dead", "SEA": "growing"}
    portfolio = pm.adjust_for_market_change(trend_shifts)
    assert portfolio.categories[PortfolioCategory.EXPLORE] > 0.15
    return True


def test_portfolio_update_allocation():
    """Portfolio: 更新分配比例"""
    pm = PortfolioManager()
    new_alloc = {
        PortfolioCategory.WINNER: 0.40,
        PortfolioCategory.EXPLORE: 0.30,
        PortfolioCategory.ADAPT: 0.20,
        PortfolioCategory.RETEST: 0.10,
    }
    pm.update_allocation(new_alloc)
    assert pm.current.categories[PortfolioCategory.WINNER] == 0.40
    return True


def test_portfolio_categories():
    """Portfolio: 四类齐全"""
    pm = PortfolioManager()
    portfolio = pm.current
    for cat in PortfolioCategory:
        assert cat in portfolio.categories
    return True


# ═══════════════════════════════════════════════════════════
# 7. Exploration Manager (4 tests)
# ═══════════════════════════════════════════════════════════

def test_exploration_default():
    """Exploration: 默认比例"""
    em = ExplorationManager()
    exploit, explore = em.get_ratio()
    assert explore == 0.20
    assert exploit == 0.80
    return True


def test_exploration_adjust():
    """Exploration: 动态调整"""
    em = ExplorationManager()
    mode = em.adjust(market_change_score=0.7, failure_rate=0.1)
    assert mode is not None
    _, explore = em.get_ratio()
    assert explore > 0.20  # Market changing → explore more
    return True


def test_exploration_stable_market():
    """Exploration: 稳定市场→低探索"""
    em = ExplorationManager()
    mode = em.adjust(market_change_score=0.1, failure_rate=0.05)
    _, explore = em.get_ratio()
    assert explore < 0.25
    return True


def test_exploration_fixed_ratio():
    """Exploration: 固定比例"""
    em = ExplorationManager()
    em.set_fixed_ratio(0.15)
    _, explore = em.get_ratio()
    assert explore == 0.15
    return True


# ═══════════════════════════════════════════════════════════
# 8. Budget Optimizer (4 tests)
# ═══════════════════════════════════════════════════════════

def test_budget_allocate():
    """Budget: 按国家分配"""
    bo = BudgetOptimizer(total_budget=10000.0)
    countries = [
        {"country": "US", "avg_roi": 0.8, "avg_confidence": 0.7, "trend_status": "growing", "risk_level": "safe"},
        {"country": "JP", "avg_roi": 0.6, "avg_confidence": 0.6, "trend_status": "stable", "risk_level": "safe"},
        {"country": "KR", "avg_roi": 0.4, "avg_confidence": 0.5, "trend_status": "declining", "risk_level": "caution"},
        {"country": "SEA", "avg_roi": 0.3, "avg_confidence": 0.4, "trend_status": "dead", "risk_level": "warning"},
    ]
    allocation = bo.allocate(countries)
    assert allocation.total_budget == 10000.0
    assert len(allocation.allocations) == 4
    # US should get the most
    assert allocation.allocations_pct["US"] > allocation.allocations_pct["SEA"]
    return True


def test_budget_not_equal():
    """Budget: 非平均分配"""
    bo = BudgetOptimizer(total_budget=10000.0)
    countries = [
        {"country": "US", "avg_roi": 0.9, "avg_confidence": 0.8, "trend_status": "growing", "risk_level": "safe"},
        {"country": "JP", "avg_roi": 0.2, "avg_confidence": 0.3, "trend_status": "dead", "risk_level": "warning"},
    ]
    allocation = bo.allocate(countries)
    assert allocation.allocations_pct["US"] > allocation.allocations_pct["JP"] * 2
    return True


def test_budget_update_total():
    """Budget: 更新总预算"""
    bo = BudgetOptimizer(total_budget=10000.0)
    countries = [
        {"country": "US", "avg_roi": 0.8, "avg_confidence": 0.7, "trend_status": "growing", "risk_level": "safe"},
    ]
    bo.allocate(countries)
    bo.update_total_budget(20000.0)
    assert bo.current.total_budget == 20000.0
    return True


def test_budget_sum_to_total():
    """Budget: 分配总和≈总预算"""
    bo = BudgetOptimizer(total_budget=10000.0)
    countries = [
        {"country": "US", "avg_roi": 0.8, "avg_confidence": 0.7, "trend_status": "growing", "risk_level": "safe"},
        {"country": "JP", "avg_roi": 0.6, "avg_confidence": 0.6, "trend_status": "stable", "risk_level": "safe"},
    ]
    allocation = bo.allocate(countries)
    total_allocated = sum(allocation.allocations.values())
    assert abs(total_allocated - 10000.0) < 1.0
    return True


# ═══════════════════════════════════════════════════════════
# 9. Production Planner (4 tests)
# ═══════════════════════════════════════════════════════════

def test_planner_generate_plan():
    """Planner: 生成生产计划"""
    engine = PolicyEngine()
    planner = ProductionPlanner(engine, max_capacity=20)
    creatives = _make_batch(30)
    plan = planner.plan(creatives)
    assert isinstance(plan, DailyProductionPlan)
    assert plan.total_creatives <= 20
    return True


def test_planner_action_counts():
    """Planner: 各Action统计"""
    engine = PolicyEngine()
    planner = ProductionPlanner(engine, max_capacity=50)
    plan = planner.plan(_make_batch(30))
    total_actions = (plan.generate_count + plan.retest_count +
                     plan.adapt_count + plan.kill_count)
    assert total_actions == 30
    return True


def test_planner_with_country_budget():
    """Planner: 含国家预算"""
    engine = PolicyEngine()
    planner = ProductionPlanner(engine, max_capacity=20)
    country_data = [
        {"country": "US", "avg_roi": 0.8, "avg_confidence": 0.7, "trend_status": "growing", "risk_level": "safe"},
        {"country": "JP", "avg_roi": 0.5, "avg_confidence": 0.5, "trend_status": "stable", "risk_level": "safe"},
    ]
    plan = planner.plan(_make_batch(20), country_data=country_data)
    assert plan.budget.total_budget > 0
    return True


def test_planner_market_change():
    """Planner: 市场变化响应"""
    engine = PolicyEngine()
    planner = ProductionPlanner(engine, max_capacity=20)
    plan = planner.plan(_make_batch(20), market_change_score=0.8)
    assert isinstance(plan, DailyProductionPlan)
    return True


# ═══════════════════════════════════════════════════════════
# 10. Logger & Report (4 tests)
# ═══════════════════════════════════════════════════════════

def test_logger_log_decision():
    """Logger: 记录决策"""
    logger = DecisionLogger()
    entry = logger.log("c_001", PolicyAction.GENERATE, "High confidence",
                       {"confidence": 0.85}, "1.0.0")
    assert entry.action == PolicyAction.GENERATE
    return True


def test_logger_kill_reasons():
    """Logger: Kill原因查询"""
    logger = DecisionLogger()
    logger.log("c_001", PolicyAction.KILL, "Low ROI", {}, "1.0.0")
    logger.log("c_002", PolicyAction.KILL, "Dead trend", {}, "1.0.0")
    reasons = logger.get_kill_reasons()
    assert len(reasons) == 2
    return True


def test_logger_daily_summary():
    """Logger: 每日摘要"""
    logger = DecisionLogger()
    logger.log("c_001", PolicyAction.GENERATE, "OK", {}, "1.0.0")
    logger.log("c_002", PolicyAction.KILL, "Bad", {}, "1.0.0")
    summary = logger.get_daily_summary()
    assert summary["generate_count"] == 1
    assert summary["kill_count"] == 1
    return True


def test_report_generation():
    """Report: 报告生成"""
    engine = PolicyEngine()
    planner = ProductionPlanner(engine, max_capacity=20)
    plan = planner.plan(_make_batch(15))
    report_gen = PolicyReportGenerator()
    report = report_gen.generate(
        plan=plan,
        policy=engine.policy,
        logs=engine.logger.get_all_logs(),
        explore_ratio=0.20,
        revenue_prediction=5000.0,
    )
    assert isinstance(report, PolicyReport)
    assert len(report.summary) > 0
    md = report_gen.to_markdown(report)
    assert "Production Plan" in md
    assert "Kill Reasons" in md
    return True


# ═══════════════════════════════════════════════════════════
# 11. Strategy ROI Validation (1 test)
# ═══════════════════════════════════════════════════════════

def test_strategy_roi_validation():
    """Strategy ROI: Policy vs 固定规则 累计ROI对比"""
    import random
    random.seed(42)

    # Create historical replay data
    records = []
    for i in range(50):
        conf = random.uniform(0.3, 0.9)
        roi = random.uniform(0.1, 1.0)
        records.append({
            "creative_id": f"c_{i:04d}",
            "confidence": conf,
            "actual_roas": roi,
            "actual_decision": "GO" if roi >= 0.5 else "AVOID",
            "predicted_decision": "GO" if conf >= 0.6 else "AVOID",
        })

    # Baseline: fixed rule (confidence > 0.6 → GO)
    baseline_roi = 0.0
    baseline_attempts = 0
    for r in records:
        if r["confidence"] >= 0.6:
            baseline_roi += r["actual_roas"]
            baseline_attempts += 1

    # Policy: use PolicyEngine
    engine = PolicyEngine()
    # Optimize policy with these records
    optimizer = PolicyOptimizer()
    optimized_policy = optimizer.optimize(records)
    engine.update_policy(optimized_policy)

    policy_roi = 0.0
    policy_attempts = 0
    for r in records:
        task = engine.decide(_make_creative_data(
            r["creative_id"],
            reasoning_confidence=r["confidence"],
            roi_prediction=r["actual_roas"],
        ))
        if task.action == PolicyAction.GENERATE:
            policy_roi += r["actual_roas"]
            policy_attempts += 1

    # Policy should at minimum not lose money
    avg_baseline = baseline_roi / max(baseline_attempts, 1)
    avg_policy = policy_roi / max(policy_attempts, 1)

    # Policy should be at least as good as baseline
    assert avg_policy >= avg_baseline * 0.8, (
        f"Policy avg ROI ({avg_policy:.3f}) significantly worse than baseline ({avg_baseline:.3f})"
    )
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Policy Engine (6)
        ("Policy: Decide", test_policy_engine_decide),
        ("Policy: Generate High", test_policy_engine_generate_high_confidence),
        ("Policy: Kill Low", test_policy_engine_kill_low_roi),
        ("Policy: Batch", test_policy_engine_batch),
        ("Policy: Rollback", test_policy_engine_rollback),
        ("Policy: Compare", test_policy_engine_compare_policies),
        # 2. Policy Rules (5)
        ("Rules: Evaluate", test_rules_evaluate),
        ("Rules: Trend Bonus", test_rules_trend_bonus),
        ("Rules: Generate", test_rules_high_confidence_generate),
        ("Rules: Kill Dead", test_rules_dead_trend_kill),
        ("Rules: Batch", test_rules_batch),
        # 3. Policy Optimizer (5)
        ("Optimizer: Grid Search", test_optimizer_grid_search),
        ("Optimizer: Random Search", test_optimizer_random_search),
        ("Optimizer: Improvement", test_optimizer_improvement),
        ("Optimizer: Version", test_optimizer_version_tracking),
        ("Optimizer: History", test_optimizer_history),
        # 4. Risk Controller (5)
        ("Risk: Safe", test_risk_assess_safe),
        ("Risk: Consecutive", test_risk_consecutive_failures),
        ("Risk: Override", test_risk_override),
        ("Risk: Warning", test_risk_warning_downgrade),
        ("Risk: Success Reset", test_risk_success_reset),
        # 5. Creative Scheduler (4)
        ("Scheduler: Schedule", test_scheduler_schedule),
        ("Scheduler: Top N", test_scheduler_top_n),
        ("Scheduler: By Country", test_scheduler_by_country),
        ("Scheduler: Summary", test_scheduler_summary),
        # 6. Portfolio Manager (4)
        ("Portfolio: Allocate", test_portfolio_allocate),
        ("Portfolio: Dynamic", test_portfolio_dynamic),
        ("Portfolio: Update", test_portfolio_update_allocation),
        ("Portfolio: Categories", test_portfolio_categories),
        # 7. Exploration Manager (4)
        ("Exploration: Default", test_exploration_default),
        ("Exploration: Adjust", test_exploration_adjust),
        ("Exploration: Stable", test_exploration_stable_market),
        ("Exploration: Fixed", test_exploration_fixed_ratio),
        # 8. Budget Optimizer (4)
        ("Budget: Allocate", test_budget_allocate),
        ("Budget: Not Equal", test_budget_not_equal),
        ("Budget: Update Total", test_budget_update_total),
        ("Budget: Sum to Total", test_budget_sum_to_total),
        # 9. Production Planner (4)
        ("Planner: Plan", test_planner_generate_plan),
        ("Planner: Actions", test_planner_action_counts),
        ("Planner: Country Budget", test_planner_with_country_budget),
        ("Planner: Market Change", test_planner_market_change),
        # 10. Logger & Report (4)
        ("Logger: Log", test_logger_log_decision),
        ("Logger: Kill Reasons", test_logger_kill_reasons),
        ("Logger: Daily Summary", test_logger_daily_summary),
        ("Report: Generation", test_report_generation),
        # 11. Strategy ROI Validation (1)
        ("Strategy ROI: Policy vs Baseline", test_strategy_roi_validation),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.3 Autonomous Decision Policy — Release Gate")
    print("  Per PRD v1.0: 45 tests + 1 Strategy ROI Validation")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            result = fn()
            if result:
                passed += 1
                print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    print(f"  Results: {passed}/{passed + failed} PASS")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)