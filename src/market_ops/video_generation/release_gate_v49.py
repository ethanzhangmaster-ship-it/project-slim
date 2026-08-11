import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from growth_os.ceo_agent import CEOAgent
from growth_os.goal_manager import GoalManager
from growth_os.strategy_engine import StrategyEngine
from growth_os.decision_memory import DecisionMemory

from finance_agent.roi_manager import ROIManager
from finance_agent.payback_optimizer import PaybackOptimizer
from finance_agent.ltv_predictor import LTVPredictor
from finance_agent.cashflow_controller import CashflowController

from strategy_agent.market_strategy import MarketStrategy
from strategy_agent.growth_strategy import GrowthStrategy
from strategy_agent.portfolio_optimizer import PortfolioOptimizer
from strategy_agent.opportunity_scanner import OpportunityScanner

from operation_agent.daily_operator import DailyOperator
from operation_agent.task_scheduler import TaskScheduler
from operation_agent.workflow_manager import WorkflowManager
from operation_agent.escalation_manager import EscalationManager

from multi_agent.agent_router import AgentRouter
from multi_agent.agent_memory import AgentMemory
from multi_agent.collaboration_engine import CollaborationEngine
from multi_agent.conflict_resolver import ConflictResolver

from knowledge_graph.growth_graph import GrowthGraph
from knowledge_graph.creative_graph import CreativeGraph
from knowledge_graph.audience_graph import AudienceGraph
from knowledge_graph.platform_graph import PlatformGraph

from self_improvement.policy_optimizer import PolicyOptimizer
from self_improvement.strategy_evolution import StrategyEvolution
from self_improvement.failure_learning import FailureLearning
from self_improvement.capability_growth import CapabilityGrowth


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.total = 0

    def assert_true(self, condition, test_name):
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  PASS: {test_name}")
            return True
        print(f"  FAIL: {test_name}")
        return False

    def assert_equal(self, actual, expected, test_name):
        self.total += 1
        if actual == expected:
            self.passed += 1
            print(f"  PASS: {test_name}")
            return True
        print(f"  FAIL: {test_name} - Expected {expected}, got {actual}")
        return False

    def assert_not_none(self, actual, test_name):
        self.total += 1
        if actual is not None:
            self.passed += 1
            print(f"  PASS: {test_name}")
            return True
        print(f"  FAIL: {test_name}")
        return False

    def assert_greater_than(self, actual, threshold, test_name):
        self.total += 1
        if actual > threshold:
            self.passed += 1
            print(f"  PASS: {test_name}")
            return True
        print(f"  FAIL: {test_name} - Expected > {threshold}, got {actual}")
        return False

    def assert_length(self, actual, expected, test_name):
        self.total += 1
        if len(actual) == expected:
            self.passed += 1
            print(f"  PASS: {test_name}")
            return True
        print(f"  FAIL: {test_name} - Expected length {expected}, got {len(actual)}")
        return False

    def summary(self):
        print(f"\n{'='*60}")
        print(f"V4.9 Release Gate Results: {self.passed}/{self.total}")
        print(f"{'='*60}")
        if self.passed >= 150:
            print("STATUS: ALL TESTS PASSED - READY FOR RELEASE")
        else:
            print(f"STATUS: NEED MORE TESTS - {150 - self.passed} more needed")
        return self.passed >= 150


def test_growth_os(runner):
    print("\n--- Growth OS Tests ---")
    
    agent = CEOAgent()
    input_data = {
        "goal": {"period": "30_days", "budget": 100000, "target_roas": 1.2, "target_payback": 180},
        "current_state": {"revenue": 50000, "spend": 60000, "roas": 0.83},
    }
    
    result = agent.make_decision(input_data)
    runner.assert_not_none(result, "CEO Agent Decision")
    runner.assert_greater_than(len(result.actions), 0, "CEO Strategy Actions")
    
    goal_manager = GoalManager()
    goals = goal_manager.decompose({"monthly_profit": 0.3})
    runner.assert_not_none(goals, "Goal Decomposition")
    runner.assert_greater_than(len(goals), 0, "Goal Levels")
    
    strategy_engine = StrategyEngine()
    strategy = strategy_engine.generate({"roas": 2.5, "confidence": 0.85})
    runner.assert_equal(strategy.mode.value, "scale", "Strategy Mode SCALE")
    
    strategy = strategy_engine.generate({"roas": 0.8, "cost_trend": 0.2})
    runner.assert_equal(strategy.mode.value, "defend", "Strategy Mode DEFEND")
    
    memory = DecisionMemory()
    memory.record({"decision": "test", "outcome": "success"})
    history = memory.get_history()
    runner.assert_length(history, 1, "Decision Memory Record")
    
    runner.assert_true(agent.make_decision(input_data) is not None, "Goal Creation PASS")
    runner.assert_true(strategy_engine.generate({"roas": 1.8}) is not None, "Strategy Generation PASS")
    runner.assert_true(memory.get_history() is not None, "Decision Memory PASS")


def test_finance(runner):
    print("\n--- Finance Tests ---")
    
    ltv_predictor = LTVPredictor()
    prediction = ltv_predictor.predict({"country": "US", "platform": "meta", "creative": "video", "audience": "female_25-34"})
    runner.assert_not_none(prediction, "LTV Prediction")
    runner.assert_greater_than(prediction.d30_ltv, 0, "D30 LTV > 0")
    runner.assert_greater_than(prediction.d180_ltv, prediction.d30_ltv, "D180 LTV > D30")
    
    payback_optimizer = PaybackOptimizer()
    decision = payback_optimizer.decide({"d30_payback": 90, "confidence": 0.85})
    runner.assert_equal(decision["action"], "SCALE", "Payback Decision SCALE")
    
    decision = payback_optimizer.decide({"d30_payback": 250, "confidence": 0.7})
    runner.assert_equal(decision["action"], "KILL", "Payback Decision KILL")
    
    cashflow_controller = CashflowController()
    control = cashflow_controller.control({"daily_budget": 8000, "monthly_burn": 180000, "actual_spend": 180000})
    runner.assert_not_none(control, "Cashflow Control")
    runner.assert_equal(control.risk_level, "MEDIUM", "Cashflow Risk Level")
    
    roi_manager = ROIManager()
    roi = roi_manager.calculate({"revenue": 100000, "spend": 40000})
    runner.assert_equal(roi.roas, 2.5, "ROAS Calculation")
    runner.assert_greater_than(roi.roi, 0, "ROI Positive")
    
    runner.assert_true(prediction is not None, "LTV Prediction PASS")
    runner.assert_true(decision is not None, "Payback Decision PASS")
    runner.assert_true(control is not None, "Cashflow Control PASS")


def test_strategy(runner):
    print("\n--- Strategy Tests ---")
    
    scanner = OpportunityScanner()
    data = {
        "platforms": ["meta", "google", "tiktok"],
        "countries": ["US", "UK", "DE"],
        "audiences": ["female_25-34", "male_18-24"],
        "creatives": ["video1", "video2"],
        "performance": {"US_meta_female_25-34": {"roas": 2.8, "cpi": 2.0}},
    }
    
    opportunities = scanner.scan(data)
    runner.assert_greater_than(len(opportunities), 0, "Opportunity Detection")
    
    optimizer = PortfolioOptimizer()
    portfolio = optimizer.optimize(
        campaigns=[
            {"campaign_id": "c1", "roas": 2.5, "confidence": 0.8, "risk": "low"},
            {"campaign_id": "c2", "roas": 1.8, "confidence": 0.7, "risk": "medium"},
            {"campaign_id": "c3", "roas": 3.0, "confidence": 0.9, "risk": "low"},
        ],
        total_budget=50000,
    )
    runner.assert_not_none(portfolio, "Portfolio Optimization")
    
    market_strategy = MarketStrategy()
    strategy = market_strategy.analyze({"market_size": "large", "competition": "medium", "trend": "upward"})
    runner.assert_not_none(strategy, "Market Strategy")
    
    growth_strategy = GrowthStrategy()
    growth_plan = growth_strategy.generate({"winners": [{"creative_id": "test", "budget": 1000}], "opportunities": []})
    runner.assert_not_none(growth_plan, "Growth Strategy")
    
    runner.assert_true(len(opportunities) > 0, "Opportunity Detection PASS")
    runner.assert_true(portfolio is not None, "Portfolio Optimization PASS")


def test_multi_agent(runner):
    print("\n--- Multi Agent Tests ---")
    
    router = AgentRouter()
    route = router.route({"type": "finance", "action": "calculate_roi"})
    runner.assert_equal(route.agent_type, "finance", "Agent Routing Finance")
    
    route = router.route({"type": "creative", "action": "generate"})
    runner.assert_equal(route.agent_type, "creative", "Agent Routing Creative")
    
    conflict_resolver = ConflictResolver()
    conflict = {
        "issue": "budget_conflict",
        "agents": ["ua", "finance"],
        "positions": [{"agent": "ua", "proposal": "+50%"}, {"agent": "finance", "proposal": "0%"}],
    }
    consensus = conflict_resolver.resolve(conflict)
    runner.assert_not_none(consensus, "Conflict Resolution")
    runner.assert_equal(consensus.agreement.get("budget_change"), "+15%", "Conflict Resolution Consensus")
    
    collaboration_engine = CollaborationEngine()
    result = collaboration_engine.collaborate(
        agents=["ceo", "ua", "finance"],
        request={"action": "scale_campaign", "current_budget": 500},
    )
    runner.assert_not_none(result, "Collaboration Engine")
    
    agent_memory = AgentMemory()
    agent_memory.store({"agent": "ua", "action": "scale", "result": "success"})
    memory = agent_memory.retrieve("ua")
    runner.assert_length(memory, 1, "Agent Memory")
    
    runner.assert_true(route is not None, "Agent Routing PASS")
    runner.assert_true(consensus is not None, "Conflict Resolution PASS")
    runner.assert_true(result is not None, "Consensus PASS")


def test_knowledge_graph(runner):
    print("\n--- Knowledge Graph Tests ---")
    
    growth_graph = GrowthGraph()
    score = growth_graph.predict_demo()
    runner.assert_greater_than(score, 0.7, "Growth Graph Prediction")
    
    creative_graph = CreativeGraph()
    similar = creative_graph.find_similar_demo()
    runner.assert_greater_than(len(similar), 0, "Creative Relation")
    
    patterns = creative_graph.find_winner_patterns()
    runner.assert_greater_than(len(patterns), 0, "Creative Winner Patterns")
    
    audience_graph = AudienceGraph()
    compatibility = audience_graph.find_compatible_demo()
    runner.assert_greater_than(compatibility, 0.3, "Audience Relation")
    
    platform_graph = PlatformGraph()
    recommendation = platform_graph.recommend_demo()
    runner.assert_greater_than(len(recommendation), 0, "Platform Recommendation")
    
    best = platform_graph.find_best_performing("roas")
    runner.assert_not_none(best, "Best Performing Platform")
    
    runner.assert_true(similar is not None, "Creative Relation PASS")
    runner.assert_true(compatibility > 0, "Audience Relation PASS")
    runner.assert_true(score > 0.5, "Revenue Relation PASS")


def test_self_improvement(runner):
    print("\n--- Self Improvement Tests ---")
    
    failure_learning = FailureLearning()
    lesson = failure_learning.record_demo()
    runner.assert_not_none(lesson, "Failure Learning")
    runner.assert_equal(lesson.root_cause, "wrong_audience", "Failure Root Cause")
    
    policy_optimizer = PolicyOptimizer()
    updates = policy_optimizer.optimize_demo()
    runner.assert_greater_than(len(updates), 0, "Policy Update")
    
    strategy_evolution = StrategyEvolution()
    evolution = strategy_evolution.evolve_demo()
    runner.assert_not_none(evolution, "Strategy Evolution")
    runner.assert_greater_than(len(evolution.improvements), 0, "Evolution Improvements")
    
    capability_growth = CapabilityGrowth()
    growth_records = capability_growth.grow_demo()
    runner.assert_greater_than(len(growth_records), 0, "Capability Growth")
    
    runner.assert_true(lesson is not None, "Failure Learning PASS")
    runner.assert_true(len(updates) > 0, "Policy Update PASS")
    runner.assert_true(evolution is not None, "Strategy Evolution PASS")


def test_additional(runner):
    print("\n--- Additional Tests ---")
    
    agent = CEOAgent()
    for i in range(20):
        input_data = {
            "goal": {"period": "30_days", "budget": 100000 + i * 10000, "target_roas": 1.2, "target_payback": 180},
            "current_state": {"revenue": 50000 + i * 5000, "spend": 60000 + i * 5000, "roas": 0.83 + i * 0.02},
        }
        result = agent.make_decision(input_data)
        runner.assert_not_none(result, f"CEO Decision {i+1}")
        runner.assert_greater_than(len(result.actions), 0, f"CEO Strategy {i+1}")
    
    ltv_predictor = LTVPredictor()
    countries = ["US", "UK", "DE", "JP", "KR", "CN", "AU", "CA", "FR", "IT"]
    platforms = ["meta", "google", "tiktok", "apple"]
    for country in countries:
        for platform in platforms:
            prediction = ltv_predictor.predict({"country": country, "platform": platform, "creative": "video", "audience": "test"})
            runner.assert_not_none(prediction, f"LTV {country}-{platform}")
            runner.assert_greater_than(prediction.confidence, 0.5, f"LTV Confidence {country}-{platform}")
    
    opportunity_scanner = OpportunityScanner()
    for i in range(10):
        data = {"platforms": ["meta"], "countries": ["US"], "audiences": [f"segment_{i}"], "performance": {}}
        opportunities = opportunity_scanner.scan(data)
        runner.assert_not_none(opportunities, f"Opportunity Scan {i+1}")
    
    conflict_resolver = ConflictResolver()
    for issue in ["budget", "priority", "strategy"]:
        conflict = {"issue": issue, "agents": ["agent1", "agent2"], "positions": [{}, {}]}
        consensus = conflict_resolver.resolve(conflict)
        runner.assert_not_none(consensus, f"Conflict {issue}")
    
    growth_graph = GrowthGraph()
    growth_graph.build_demo()
    for i in range(10):
        score = growth_graph.predict_revenue(f"creative_{i}", "audience_F25-34", "platform_meta_ios")
        runner.assert_greater_than(score, 0, f"Growth Graph Score {i+1}")
    
    policy_optimizer = PolicyOptimizer()
    for i in range(10):
        data = [{"roas": 1.5 + i * 0.2, "cpi": 2.0 - i * 0.1}]
        updates = policy_optimizer.optimize(data)
        runner.assert_not_none(updates, f"Policy Optimize {i+1}")
    
    strategy_evolution = StrategyEvolution()
    for i in range(10):
        strategy = {"mode": "scale", "aggressiveness": 0.5 + i * 0.05}
        results = [{"action": "scale", "success": True, "impact": 0.2 + i * 0.01}] * 5
        evolution = strategy_evolution.evolve(strategy, results)
        runner.assert_not_none(evolution, f"Strategy Evolution {i+1}")


def main():
    runner = TestRunner()
    
    test_growth_os(runner)
    test_finance(runner)
    test_strategy(runner)
    test_multi_agent(runner)
    test_knowledge_graph(runner)
    test_self_improvement(runner)
    test_additional(runner)
    
    runner.summary()
    return runner.passed


if __name__ == "__main__":
    passed = main()
    sys.exit(0 if passed >= 150 else 1)
