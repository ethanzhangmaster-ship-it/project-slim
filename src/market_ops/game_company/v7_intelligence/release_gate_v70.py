import sys
import os
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence_core import (
    CEOBrain, CEODecision, DecisionType, CompanyState,
    ReasoningEngine, ReasoningChain, Observation, Hypothesis,
    DecisionEngine, DecisionScore, ScoredDecision,
    InvestmentEngine, InvestmentAllocation, ProjectInvestment,
    StrategicMemory, StrategyRecord as ICStrategyRecord, StrategicInsight,
    CompanyStateModel, FinanceState, ProductState, MarketState, GrowthState, RiskState,
)
from opportunity_intelligence import (
    AppStoreRadar, AppInfo, TrendingApp, NewRelease,
    GenreForecaster, GenreForecast, GrowthTrend, PeakPrediction,
    CompetitorPrediction, CompetitorProfile, PredictedMove, StrengthAssessment,
    MarketGapAI, MarketGap, ScoredGap, Opportunity as OppOpportunity,
    TrendPrediction, Trend, EmergingTrend, TrendScore,
    OpportunityRanker, RankerOpportunity, RankedOpportunity, OpportunityScoreBreakdown,
)
from autonomous_product_studio import (
    IdeaGenerator, GameIdea, Opportunity as StudioOpportunity,
    GameDesigner, GameDesignDocument, CoreLoop, Mechanics,
    EconomyArchitect, Currency, RewardLoop, EconomyModel,
    LevelGenerator, Level,
    PrototypeBuilder, Feature, EffortEstimate,
    PlaytestAgent, PlaySession, Feedback, Issue,
    ProductManager, Milestone, ProductPackage,
)
from ai_playtest import (
    PlayerSimulator, PlayerBehavior,
    RetentionPredictor, RetentionForecast,
    ChurnAnalyzer, ChurnReport,
    DifficultyOptimizer, DifficultyProfile,
    FunScoreModel, FunScore, FunFactors,
)
from capital_allocator import (
    ProjectRanker, RankedProject, ProjectScore,
    BudgetAllocator, BudgetAllocation, AllocationChange,
    RiskModel, RiskAssessment, PortfolioRisk,
    KillDecision, KillRecommendation, ProjectHealth,
    PortfolioManager, PortfolioSummary, PortfolioOptimization,
)
from autonomous_growth import (
    UABrain, CampaignOptimization, UARecommendation,
    CreativeBrain, CreativeConcept, CreativeEvaluation,
    ASOBrain, ASORecommendation, KeywordOptimization,
    MonetizationBrain, MonetizationRecommendation, RevenueOptimization,
    ExperimentEngine, Experiment, ExperimentResult,
    GrowthLoop, GrowthIssue, GrowthExperiment, GrowthLearning,
)
from company_memory_v2 import (
    ExperienceMemory, ExperienceRecord,
    FailureMemory, FailureRecord,
    StrategyMemory, StrategyRecord as MemStrategyRecord,
    CompetitorMemory, CompetitorRecord,
    CausalMemory, CausalLink,
)
from autonomous_research import (
    PaperReader, PaperSummary, ResearchInsight,
    MarketReporter, MarketReport, MarketUpdate,
    CompetitorWatcher, CompetitorMove, CompetitorAnalysis, ThreatLevel,
    TechnologyTracker, TechTrend, TechAssessment, ImpactLevel,
    ReportGenerator, CEOReport, StrategyReport, RiskReport,
)


# ---------------------------------------------------------------------------
# intelligence_core (~100 tests)
# ---------------------------------------------------------------------------
class TestIntelligenceCore(unittest.TestCase):
    # CEOBrain
    def test_evaluate_returns_list(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        result = brain.evaluate(state)
        self.assertIsInstance(result, list)

    def test_evaluate_with_empty_state(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        result = brain.evaluate(state)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], CEODecision)

    def test_decide_returns_decision(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        result = brain.decide(state)
        self.assertIsInstance(result, CEODecision)

    def test_decide_hold_when_no_rules(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        state.finance.roas = 1.0
        state.finance.runway_months = 6
        state.finance.cash = 100000
        state.products.active_games = 2
        result = brain.decide(state)
        self.assertEqual(result.decision_type, DecisionType.HOLD)

    def test_analyze_project_strong_roi(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        state.products.projects = [{"name": "GameA", "roi": 2.0, "budget": 100000}]
        result = brain.analyze_project(state, "GameA")
        self.assertIsInstance(result, CEODecision)

    def test_analyze_project_low_roi(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        state.products.projects = [{"name": "GameB", "roi": 0.5}]
        result = brain.analyze_project(state, "GameB")
        self.assertIsInstance(result, CEODecision)

    def test_analyze_project_not_found(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        result = brain.analyze_project(state, "Missing")
        self.assertEqual(result.decision_type, DecisionType.HOLD)

    def test_get_decision_history(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        brain.decide(state)
        hist = brain.get_decision_history()
        self.assertIsInstance(hist, list)
        self.assertGreater(len(hist), 0)

    def test_get_decision_history_limit(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        brain.decide(state)
        hist = brain.get_decision_history(limit=1)
        self.assertLessEqual(len(hist), 1)

    def test_get_stats(self):
        brain = CEOBrain()
        state = CompanyStateModel()
        brain.decide(state)
        stats = brain.get_stats()
        self.assertIn("total_decisions", stats)

    # DecisionType
    def test_decision_type_values(self):
        self.assertTrue(hasattr(DecisionType, "CREATE_PROJECT"))
        self.assertTrue(hasattr(DecisionType, "SCALE_PROJECT"))
        self.assertTrue(hasattr(DecisionType, "KILL_PROJECT"))
        self.assertTrue(hasattr(DecisionType, "HOLD"))

    def test_create_project_value(self):
        self.assertEqual(DecisionType.CREATE_PROJECT.value, "create_project")

    def test_scale_project_value(self):
        self.assertEqual(DecisionType.SCALE_PROJECT.value, "scale_project")

    def test_hold_value(self):
        self.assertEqual(DecisionType.HOLD.value, "hold")

    def test_kill_project_value(self):
        self.assertEqual(DecisionType.KILL_PROJECT.value, "kill_project")

    # CEODecision
    def test_create_decision(self):
        d = CEODecision(decision_type=DecisionType.HOLD, reason="test", confidence=0.5)
        self.assertEqual(d.decision_type, DecisionType.HOLD)

    def test_decision_to_dict(self):
        d = CEODecision(decision_type=DecisionType.HOLD)
        result = d.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn("decision_type", result)

    def test_decision_default_values(self):
        d = CEODecision(decision_type=DecisionType.HOLD)
        self.assertEqual(d.confidence, 0.0)
        self.assertEqual(d.priority, 5)

    def test_decision_with_target(self):
        d = CEODecision(decision_type=DecisionType.SCALE_PROJECT, target_project="P1")
        self.assertEqual(d.target_project, "P1")

    def test_decision_with_budget(self):
        d = CEODecision(decision_type=DecisionType.INVEST_MORE, budget_change=1000.0)
        self.assertEqual(d.budget_change, 1000.0)

    # CompanyState
    def test_create_state(self):
        s = CompanyState(revenue=100.0, cash=50.0)
        self.assertEqual(s.revenue, 100.0)

    def test_state_to_dict(self):
        s = CompanyState()
        result = s.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn("revenue", result)

    def test_state_defaults(self):
        s = CompanyState()
        self.assertEqual(s.revenue, 0.0)
        self.assertEqual(s.projects, [])

    def test_state_with_projects(self):
        s = CompanyState(projects=[{"name": "A"}])
        self.assertEqual(len(s.projects), 1)

    # ReasoningEngine
    def test_reason_returns_chain(self):
        engine = ReasoningEngine()
        result = engine.reason({"text": "obs"})
        self.assertIsInstance(result, ReasoningChain)

    def test_observe_returns_observation(self):
        engine = ReasoningEngine()
        result = engine.observe({"text": "hello"})
        self.assertIsInstance(result, Observation)

    def test_hypothesize_returns_hypothesis(self):
        engine = ReasoningEngine()
        obs = engine.observe({"text": "hello"})
        result = engine.hypothesize(obs)
        self.assertIsInstance(result, Hypothesis)

    def test_reason_populates_chain(self):
        engine = ReasoningEngine()
        chain = engine.reason({"text": "x"})
        self.assertGreater(len(chain.observations), 0)
        self.assertGreater(len(chain.hypotheses), 0)

    def test_multiple_reasons(self):
        engine = ReasoningEngine()
        engine.reason({"text": "a"})
        engine.reason({"text": "b"})

    def test_observe_with_data(self):
        engine = ReasoningEngine()
        obs = engine.observe({"text": "t", "source": "s", "confidence": 0.8})
        self.assertEqual(obs.source, "s")

    # ReasoningChain
    def test_create_chain(self):
        c = ReasoningChain()
        self.assertIsInstance(c.observations, list)

    def test_chain_to_dict(self):
        c = ReasoningChain()
        result = c.to_dict()
        self.assertIsInstance(result, dict)

    def test_chain_defaults(self):
        c = ReasoningChain()
        self.assertEqual(c.decisions, [])
        self.assertEqual(c.expected_results, [])

    def test_chain_with_items(self):
        c = ReasoningChain(observations=[Observation()], hypotheses=[Hypothesis()])
        self.assertEqual(len(c.observations), 1)

    # Observation
    def test_create_observation(self):
        o = Observation(text="t", source="s")
        self.assertEqual(o.text, "t")

    def test_observation_to_dict(self):
        o = Observation()
        result = o.to_dict()
        self.assertIsInstance(result, dict)

    def test_observation_defaults(self):
        o = Observation()
        self.assertEqual(o.text, "")
        self.assertEqual(o.confidence, 0.0)

    def test_observation_with_data(self):
        o = Observation(text="x", confidence=0.9)
        self.assertEqual(o.confidence, 0.9)

    # Hypothesis
    def test_create_hypothesis(self):
        h = Hypothesis(text="h", confidence=0.5)
        self.assertEqual(h.text, "h")

    def test_hypothesis_to_dict(self):
        h = Hypothesis()
        result = h.to_dict()
        self.assertIsInstance(result, dict)

    def test_hypothesis_defaults(self):
        h = Hypothesis()
        self.assertEqual(h.text, "")
        self.assertEqual(h.supporting_evidence, [])

    def test_hypothesis_with_evidence(self):
        h = Hypothesis(supporting_evidence=["e1"])
        self.assertIn("e1", h.supporting_evidence)

    # DecisionEngine
    def test_score_decision(self):
        engine = DecisionEngine()
        score = engine.score_decision({"revenue_impact": 10, "strategic_fit": 5})
        self.assertIsInstance(score, DecisionScore)

    def test_score_decision_defaults(self):
        engine = DecisionEngine()
        score = engine.score_decision({})
        self.assertEqual(score.total_score, 0.05)

    def test_evaluate_returns_list(self):
        engine = DecisionEngine()
        result = engine.evaluate([{"name": "a"}, {"name": "b"}])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_evaluate_empty(self):
        engine = DecisionEngine()
        result = engine.evaluate([])
        self.assertEqual(result, [])

    def test_rank_descending(self):
        engine = DecisionEngine()
        d1 = ScoredDecision(decision_name="a", score=DecisionScore(total_score=10))
        d2 = ScoredDecision(decision_name="b", score=DecisionScore(total_score=5))
        ranked = engine.rank([d2, d1])
        self.assertEqual(ranked[0].decision_name, "a")

    def test_rank_empty(self):
        engine = DecisionEngine()
        result = engine.rank([])
        self.assertEqual(result, [])

    # DecisionScore
    def test_create_score(self):
        s = DecisionScore(revenue_impact=1.0, total_score=5.0)
        self.assertEqual(s.total_score, 5.0)

    def test_score_to_dict(self):
        s = DecisionScore()
        result = s.to_dict()
        self.assertIsInstance(result, dict)

    def test_score_defaults(self):
        s = DecisionScore()
        self.assertEqual(s.revenue_impact, 0.0)

    def test_score_with_values(self):
        s = DecisionScore(strategic_fit=3.0, confidence=0.8)
        self.assertEqual(s.strategic_fit, 3.0)

    # ScoredDecision
    def test_create_scored(self):
        d = ScoredDecision(decision_name="d1")
        self.assertEqual(d.decision_name, "d1")

    def test_scored_to_dict(self):
        d = ScoredDecision()
        result = d.to_dict()
        self.assertIsInstance(result, dict)

    def test_scored_defaults(self):
        d = ScoredDecision()
        self.assertEqual(d.risk_level, "medium")

    def test_scored_with_risk(self):
        d = ScoredDecision(risk_level="high")
        self.assertEqual(d.risk_level, "high")

    # InvestmentEngine
    def test_allocate_budget(self):
        engine = InvestmentEngine()
        result = engine.allocate_budget([{"name": "A", "score": 2}, {"name": "B", "score": 1}], 1000)
        self.assertIsInstance(result, InvestmentAllocation)

    def test_allocate_empty_projects(self):
        engine = InvestmentEngine()
        result = engine.allocate_budget([], 1000)
        self.assertEqual(result.allocations, {})

    def test_evaluate_project(self):
        engine = InvestmentEngine()
        result = engine.evaluate_project({"name": "P1", "expected_roi": 1.5})
        self.assertIsInstance(result, ProjectInvestment)

    def test_get_portfolio(self):
        engine = InvestmentEngine()
        engine.evaluate_project({"name": "P1"})
        result = engine.get_portfolio()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_get_portfolio_multiple(self):
        engine = InvestmentEngine()
        engine.evaluate_project({"name": "P1"})
        engine.evaluate_project({"name": "P2"})
        self.assertEqual(len(engine.get_portfolio()), 2)

    def test_allocate_budget_total(self):
        engine = InvestmentEngine()
        result = engine.allocate_budget([{"name": "A"}], 1000)
        self.assertEqual(result.total_budget, 1000)

    # InvestmentAllocation
    def test_create_allocation(self):
        a = InvestmentAllocation(allocations={"A": 100}, reserve=10, total_budget=110)
        self.assertEqual(a.reserve, 10)

    def test_allocation_to_dict(self):
        a = InvestmentAllocation()
        result = a.to_dict()
        self.assertIsInstance(result, dict)

    def test_allocation_defaults(self):
        a = InvestmentAllocation()
        self.assertEqual(a.allocations, {})

    def test_allocation_with_data(self):
        a = InvestmentAllocation(allocations={"A": 50})
        self.assertIn("A", a.allocations)

    # ProjectInvestment
    def test_create_investment(self):
        p = ProjectInvestment(project_name="P1", allocated_amount=100)
        self.assertEqual(p.project_name, "P1")

    def test_investment_to_dict(self):
        p = ProjectInvestment()
        result = p.to_dict()
        self.assertIsInstance(result, dict)

    def test_investment_defaults(self):
        p = ProjectInvestment()
        self.assertEqual(p.project_name, "")

    def test_investment_with_values(self):
        p = ProjectInvestment(expected_roi=2.0, risk_score=0.3)
        self.assertEqual(p.expected_roi, 2.0)

    # StrategicMemory
    def test_record_strategy(self):
        mem = StrategicMemory()
        r = ICStrategyRecord(name="s1", outcome="success")
        result = mem.record_strategy(r)
        self.assertIsInstance(result, ICStrategyRecord)

    def test_get_successful_strategies(self):
        mem = StrategicMemory()
        mem.record_strategy(ICStrategyRecord(name="s1", outcome="success"))
        mem.record_strategy(ICStrategyRecord(name="s2", outcome="failure"))
        result = mem.get_successful_strategies()
        self.assertEqual(len(result), 1)

    def test_get_failed_strategies(self):
        mem = StrategicMemory()
        mem.record_strategy(ICStrategyRecord(name="s1", outcome="failure"))
        result = mem.get_failed_strategies()
        self.assertEqual(len(result), 1)

    def test_search_by_name(self):
        mem = StrategicMemory()
        mem.record_strategy(ICStrategyRecord(name="alpha", reason="test"))
        result = mem.search("alpha")
        self.assertEqual(len(result), 1)

    def test_search_by_tag(self):
        mem = StrategicMemory()
        mem.record_strategy(ICStrategyRecord(name="s1", tags=["merge"]))
        result = mem.search("merge")
        self.assertEqual(len(result), 1)

    def test_search_no_results(self):
        mem = StrategicMemory()
        result = mem.search("xyz")
        self.assertEqual(len(result), 0)

    def test_add_insight(self):
        mem = StrategicMemory()
        i = StrategicInsight(topic="t", insight_text="info")
        result = mem.add_insight(i)
        self.assertIsInstance(result, StrategicInsight)

    def test_empty_memory(self):
        mem = StrategicMemory()
        self.assertEqual(len(mem.get_successful_strategies()), 0)

    # StrategyRecord
    def test_create_record(self):
        r = ICStrategyRecord(name="s1", outcome="success")
        self.assertEqual(r.name, "s1")

    def test_record_to_dict(self):
        r = ICStrategyRecord()
        result = r.to_dict()
        self.assertIsInstance(result, dict)

    def test_record_defaults(self):
        r = ICStrategyRecord()
        self.assertEqual(r.name, "")
        self.assertEqual(r.tags, [])

    def test_record_with_tags(self):
        r = ICStrategyRecord(tags=["a", "b"])
        self.assertEqual(len(r.tags), 2)

    # StrategicInsight
    def test_create_insight(self):
        i = StrategicInsight(topic="t", insight_text="info")
        self.assertEqual(i.topic, "t")

    def test_insight_to_dict(self):
        i = StrategicInsight()
        result = i.to_dict()
        self.assertIsInstance(result, dict)

    def test_insight_defaults(self):
        i = StrategicInsight()
        self.assertEqual(i.confidence, 0.0)

    def test_insight_with_values(self):
        i = StrategicInsight(confidence=0.9, source="AI")
        self.assertEqual(i.confidence, 0.9)

    # CompanyStateModel
    def test_create_model(self):
        m = CompanyStateModel()
        self.assertIsInstance(m.finance, FinanceState)

    def test_model_to_dict(self):
        m = CompanyStateModel()
        result = m.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn("finance", result)

    def test_model_defaults(self):
        m = CompanyStateModel()
        self.assertIsInstance(m.products, ProductState)

    def test_health_score(self):
        m = CompanyStateModel()
        score = m.health_score()
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_is_healthy_true(self):
        m = CompanyStateModel()
        m.finance.roas = 2.0
        m.finance.runway_months = 15
        self.assertTrue(m.is_healthy())

    def test_is_healthy_false(self):
        m = CompanyStateModel()
        m.finance.roas = 0.5
        m.finance.runway_months = 1
        self.assertFalse(m.is_healthy())

    # FinanceState
    def test_create_finance(self):
        f = FinanceState(cash=1000.0)
        self.assertEqual(f.cash, 1000.0)

    def test_finance_to_dict(self):
        f = FinanceState()
        result = f.to_dict()
        self.assertIsInstance(result, dict)

    def test_finance_defaults(self):
        f = FinanceState()
        self.assertEqual(f.cash, 0.0)

    def test_finance_with_values(self):
        f = FinanceState(roas=1.5, runway_months=6)
        self.assertEqual(f.roas, 1.5)

    # ProductState
    def test_create_product(self):
        p = ProductState(active_games=3)
        self.assertEqual(p.active_games, 3)

    def test_product_to_dict(self):
        p = ProductState()
        result = p.to_dict()
        self.assertIsInstance(result, dict)

    def test_product_defaults(self):
        p = ProductState()
        self.assertEqual(p.active_games, 0)

    def test_product_with_projects(self):
        p = ProductState(projects=[{"name": "A"}])
        self.assertEqual(len(p.projects), 1)

    # MarketState
    def test_create_market(self):
        m = MarketState(target_market="US")
        self.assertEqual(m.target_market, "US")

    def test_market_to_dict(self):
        m = MarketState()
        result = m.to_dict()
        self.assertIsInstance(result, dict)

    def test_market_defaults(self):
        m = MarketState()
        self.assertEqual(m.market_size, 0.0)

    def test_market_with_values(self):
        m = MarketState(competition_level="high")
        self.assertEqual(m.competition_level, "high")

    # GrowthState
    def test_create_growth(self):
        g = GrowthState(daily_spend=100)
        self.assertEqual(g.daily_spend, 100)

    def test_growth_to_dict(self):
        g = GrowthState()
        result = g.to_dict()
        self.assertIsInstance(result, dict)

    def test_growth_defaults(self):
        g = GrowthState()
        self.assertEqual(g.daily_spend, 0.0)

    def test_growth_with_values(self):
        g = GrowthState(ua_channels={"meta": 50})
        self.assertIn("meta", g.ua_channels)

    # RiskState
    def test_create_risk(self):
        r = RiskState(overall_risk_score=0.5)
        self.assertEqual(r.overall_risk_score, 0.5)

    def test_risk_to_dict(self):
        r = RiskState()
        result = r.to_dict()
        self.assertIsInstance(result, dict)

    def test_risk_defaults(self):
        r = RiskState()
        self.assertEqual(r.budget_risk, 0.0)

    def test_risk_with_alerts(self):
        r = RiskState(active_alerts=["alert1"])
        self.assertIn("alert1", r.active_alerts)


# ---------------------------------------------------------------------------
# opportunity_intelligence (~80 tests)
# ---------------------------------------------------------------------------
class TestOpportunityIntelligence(unittest.TestCase):
    # AppStoreRadar
    def test_scan(self):
        radar = AppStoreRadar()
        result = radar.scan("App Store", "Puzzle")
        self.assertIsInstance(result, dict)
        self.assertIn("app_count", result)

    def test_scan_no_results(self):
        radar = AppStoreRadar()
        result = radar.scan("Unknown Store", "Unknown")
        self.assertEqual(result["app_count"], 0)

    def test_get_top_apps(self):
        radar = AppStoreRadar()
        result = radar.get_top_apps()
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 10)

    def test_get_top_apps_count(self):
        radar = AppStoreRadar()
        result = radar.get_top_apps()
        self.assertGreater(len(result), 0)

    def test_get_trending(self):
        radar = AppStoreRadar()
        result = radar.get_trending()
        self.assertIsInstance(result, list)

    def test_get_trending_sorted(self):
        radar = AppStoreRadar()
        result = radar.get_trending()
        if len(result) > 1:
            self.assertGreaterEqual(result[0].momentum_score, result[-1].momentum_score)

    def test_get_new_releases(self):
        radar = AppStoreRadar()
        result = radar.get_new_releases()
        self.assertIsInstance(result, list)

    def test_get_new_releases_recent(self):
        radar = AppStoreRadar()
        result = radar.get_new_releases()
        for r in result:
            self.assertIsInstance(r, NewRelease)

    # AppInfo
    def test_create_app_info(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        self.assertEqual(a.name, "Game")

    def test_app_info_attributes(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        self.assertEqual(a.store, "App Store")

    def test_app_info_with_trend(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store", trend_score=80.0)
        self.assertEqual(a.trend_score, 80.0)

    def test_app_info_defaults(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        self.assertEqual(a.trend_score, 0.0)

    # TrendingApp
    def test_create_trending(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        t = TrendingApp(app=a, rank_change=5, momentum_score=70.0)
        self.assertEqual(t.rank_change, 5)

    def test_trending_attributes(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        t = TrendingApp(app=a, rank_change=5, momentum_score=70.0)
        self.assertIsInstance(t.app, AppInfo)

    def test_trending_with_app(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        t = TrendingApp(app=a, rank_change=-2, momentum_score=60.0)
        self.assertEqual(t.momentum_score, 60.0)

    # NewRelease
    def test_create_new_release(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        n = NewRelease(app=a, launch_date="2026-01-01", early_rating=4.5, download_velocity=1000)
        self.assertEqual(n.launch_date, "2026-01-01")

    def test_new_release_attributes(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        n = NewRelease(app=a, launch_date="2026-01-01", early_rating=4.5, download_velocity=1000)
        self.assertIsInstance(n.app, AppInfo)

    def test_new_release_with_app(self):
        a = AppInfo(app_id="1", name="Game", developer="Dev", category="Puzzle", rating=4.5, downloads=1000, revenue=500.0, release_date="2026-01-01", store="App Store")
        n = NewRelease(app=a, launch_date="2026-01-01", early_rating=4.5, download_velocity=5000)
        self.assertEqual(n.download_velocity, 5000)

    # GenreForecaster
    def test_forecast(self):
        f = GenreForecaster()
        result = f.forecast("RPG", 3)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_forecast_multiple_months(self):
        f = GenreForecaster()
        result = f.forecast("Strategy", 12)
        self.assertEqual(len(result), 12)

    def test_get_growth_trend(self):
        f = GenreForecaster()
        result = f.get_growth_trend("Puzzle")
        self.assertIsInstance(result, GrowthTrend)

    def test_get_growth_trend_direction(self):
        f = GenreForecaster()
        result = f.get_growth_trend("Puzzle")
        self.assertIn(result.trend_direction, ["upward", "downward", "stable"])

    def test_predict_peak(self):
        f = GenreForecaster()
        result = f.predict_peak("Action")
        self.assertIsInstance(result, PeakPrediction)

    def test_predict_peak_confidence(self):
        f = GenreForecaster()
        result = f.predict_peak("Action")
        self.assertGreater(result.confidence, 0)

    # GenreForecast
    def test_create_forecast(self):
        g = GenreForecast(genre="RPG", month="2026-01", predicted_users=1000, predicted_revenue=500.0, confidence=0.8)
        self.assertEqual(g.genre, "RPG")

    def test_forecast_attributes(self):
        g = GenreForecast(genre="RPG", month="2026-01", predicted_users=1000, predicted_revenue=500.0, confidence=0.8)
        self.assertEqual(g.predicted_users, 1000)

    def test_forecast_with_values(self):
        g = GenreForecast(genre="RPG", month="2026-01", predicted_users=1000, predicted_revenue=500.0, confidence=0.8)
        self.assertEqual(g.confidence, 0.8)

    # GrowthTrend
    def test_create_growth_trend(self):
        g = GrowthTrend(genre="RPG", monthly_growth=[0.1], avg_growth_rate=0.1, trend_direction="upward")
        self.assertEqual(g.genre, "RPG")

    def test_growth_trend_direction(self):
        g = GrowthTrend(genre="RPG", monthly_growth=[0.1], avg_growth_rate=0.1, trend_direction="upward")
        self.assertEqual(g.trend_direction, "upward")

    def test_growth_trend_monthly(self):
        g = GrowthTrend(genre="RPG", monthly_growth=[0.1, 0.2], avg_growth_rate=0.15, trend_direction="upward")
        self.assertEqual(len(g.monthly_growth), 2)

    # PeakPrediction
    def test_create_peak(self):
        p = PeakPrediction(genre="RPG", predicted_peak_month="2026-06", peak_user_count=1000, peak_revenue=500.0, confidence=0.8)
        self.assertEqual(p.genre, "RPG")

    def test_peak_attributes(self):
        p = PeakPrediction(genre="RPG", predicted_peak_month="2026-06", peak_user_count=1000, peak_revenue=500.0, confidence=0.8)
        self.assertEqual(p.predicted_peak_month, "2026-06")

    def test_peak_with_values(self):
        p = PeakPrediction(genre="RPG", predicted_peak_month="2026-06", peak_user_count=1000, peak_revenue=500.0, confidence=0.8)
        self.assertEqual(p.peak_user_count, 1000)

    # CompetitorPrediction
    def test_track(self):
        c = CompetitorPrediction()
        result = c.track("Competitor 1")
        self.assertIsInstance(result, dict)

    def test_track_new_competitor(self):
        c = CompetitorPrediction()
        result = c.track("NewComp")
        self.assertIn("profile", result)

    def test_predict_next_move(self):
        c = CompetitorPrediction()
        result = c.predict_next_move("Competitor 1")
        self.assertIsInstance(result, PredictedMove)

    def test_predict_move_probability(self):
        c = CompetitorPrediction()
        result = c.predict_next_move("Competitor 1")
        self.assertGreaterEqual(result.probability, 0)
        self.assertLessEqual(result.probability, 1)

    def test_get_strengths(self):
        c = CompetitorPrediction()
        result = c.get_strengths("Competitor 1")
        self.assertIsInstance(result, StrengthAssessment)

    def test_get_strengths_score(self):
        c = CompetitorPrediction()
        result = c.get_strengths("Competitor 1")
        self.assertGreaterEqual(result.score, 0)

    # CompetitorProfile
    def test_create_profile(self):
        p = CompetitorProfile(name="C1", market_share=10.0, active_games=5, avg_rating=4.0, monthly_revenue=1000.0, user_base=1000)
        self.assertEqual(p.name, "C1")

    def test_profile_attributes(self):
        p = CompetitorProfile(name="C1", market_share=10.0, active_games=5, avg_rating=4.0, monthly_revenue=1000.0, user_base=1000)
        self.assertEqual(p.active_games, 5)

    def test_profile_with_values(self):
        p = CompetitorProfile(name="C1", market_share=10.0, active_games=5, avg_rating=4.0, monthly_revenue=1000.0, user_base=1000)
        self.assertEqual(p.user_base, 1000)

    # PredictedMove
    def test_create_move(self):
        m = PredictedMove(competitor="C1", move_type="launch", probability=0.5, expected_timeline="1 month", potential_impact="high")
        self.assertEqual(m.competitor, "C1")

    def test_move_attributes(self):
        m = PredictedMove(competitor="C1", move_type="launch", probability=0.5, expected_timeline="1 month", potential_impact="high")
        self.assertEqual(m.move_type, "launch")

    def test_move_with_values(self):
        m = PredictedMove(competitor="C1", move_type="launch", probability=0.5, expected_timeline="1 month", potential_impact="high")
        self.assertEqual(m.potential_impact, "high")

    # StrengthAssessment
    def test_create_assessment(self):
        a = StrengthAssessment(competitor="C1", strengths=["ip"], weaknesses=["cost"], threat_level="medium", score=50.0)
        self.assertEqual(a.competitor, "C1")

    def test_assessment_attributes(self):
        a = StrengthAssessment(competitor="C1", strengths=["ip"], weaknesses=["cost"], threat_level="medium", score=50.0)
        self.assertIn("ip", a.strengths)

    def test_assessment_threat(self):
        a = StrengthAssessment(competitor="C1", strengths=["ip"], weaknesses=["cost"], threat_level="high", score=50.0)
        self.assertEqual(a.threat_level, "high")

    # MarketGapAI
    def test_find_gaps(self):
        m = MarketGapAI()
        result = m.find_gaps()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_find_gaps_count(self):
        m = MarketGapAI()
        result = m.find_gaps()
        self.assertEqual(len(result), 10)

    def test_score_gap(self):
        m = MarketGapAI()
        gaps = m.find_gaps()
        result = m.score_gap(gaps[0])
        self.assertIsInstance(result, ScoredGap)

    def test_score_gap_confidence(self):
        m = MarketGapAI()
        gaps = m.find_gaps()
        result = m.score_gap(gaps[0])
        self.assertGreater(result.confidence, 0)

    def test_get_opportunities(self):
        m = MarketGapAI()
        result = m.get_opportunities()
        self.assertIsInstance(result, list)

    def test_get_opportunities_priority(self):
        m = MarketGapAI()
        result = m.get_opportunities()
        for opp in result:
            self.assertIn(opp.priority, ["high", "medium", "low"])

    # MarketGap
    def test_create_gap(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        self.assertEqual(g.gap_id, "g1")

    def test_gap_attributes(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        self.assertEqual(g.genre, "RPG")

    def test_gap_with_values(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        self.assertEqual(g.estimated_demand, 1000)

    # ScoredGap
    def test_create_scored_gap(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        s = ScoredGap(gap=g, score=80.0, confidence=0.8, reasoning="good")
        self.assertEqual(s.score, 80.0)

    def test_scored_gap_attributes(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        s = ScoredGap(gap=g, score=80.0, confidence=0.8, reasoning="good")
        self.assertIsInstance(s.gap, MarketGap)

    def test_scored_gap_with_values(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        s = ScoredGap(gap=g, score=80.0, confidence=0.8, reasoning="good")
        self.assertEqual(s.reasoning, "good")

    # OppOpportunity
    def test_create_opportunity(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        o = OppOpportunity(opportunity_id="o1", gap=g, recommended_action="develop", expected_roi=2.0, time_to_market="6 months", priority="high")
        self.assertEqual(o.opportunity_id, "o1")

    def test_opportunity_attributes(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        o = OppOpportunity(opportunity_id="o1", gap=g, recommended_action="develop", expected_roi=2.0, time_to_market="6 months", priority="high")
        self.assertEqual(o.expected_roi, 2.0)

    def test_opportunity_with_values(self):
        g = MarketGap(gap_id="g1", genre="RPG", sub_genre="mid", underserved_segment="gen_z", estimated_demand=1000, competition_level="low", barrier_to_entry="low", description="desc")
        o = OppOpportunity(opportunity_id="o1", gap=g, recommended_action="develop", expected_roi=2.0, time_to_market="6 months", priority="high")
        self.assertEqual(o.priority, "high")

    # TrendPrediction
    def test_predict_trends(self):
        t = TrendPrediction()
        result = t.predict_trends()
        self.assertIsInstance(result, list)

    def test_predict_trends_sorted(self):
        t = TrendPrediction()
        result = t.predict_trends()
        if len(result) > 1:
            self.assertGreaterEqual(result[0].current_momentum, result[-1].current_momentum)

    def test_get_emerging_trends(self):
        t = TrendPrediction()
        result = t.get_emerging_trends()
        self.assertIsInstance(result, list)

    def test_get_emerging_trends_signals(self):
        t = TrendPrediction()
        result = t.get_emerging_trends()
        for r in result:
            self.assertGreater(len(r.early_signals), 0)

    def test_score_trend(self):
        t = TrendPrediction()
        trends = t.predict_trends()
        result = t.score_trend(trends[0])
        self.assertIsInstance(result, TrendScore)

    def test_score_trend_overall(self):
        t = TrendPrediction()
        trends = t.predict_trends()
        result = t.score_trend(trends[0])
        self.assertGreater(result.overall_score, 0)

    # Trend
    def test_create_trend(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        self.assertEqual(t.name, "AI")

    def test_trend_attributes(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        self.assertEqual(t.category, "tech")

    def test_trend_with_genres(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG", "Strategy"])
        self.assertEqual(len(t.related_genres), 2)

    # EmergingTrend
    def test_create_emerging(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        e = EmergingTrend(trend=t, detection_confidence=0.8, early_signals=["s1"], potential_scale="mass_market")
        self.assertEqual(e.detection_confidence, 0.8)

    def test_emerging_attributes(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        e = EmergingTrend(trend=t, detection_confidence=0.8, early_signals=["s1"], potential_scale="mass_market")
        self.assertIsInstance(e.trend, Trend)

    def test_emerging_with_trend(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        e = EmergingTrend(trend=t, detection_confidence=0.8, early_signals=["s1"], potential_scale="mass_market")
        self.assertEqual(e.potential_scale, "mass_market")

    # TrendScore
    def test_create_score(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        s = TrendScore(trend=t, relevance_score=80.0, longevity_score=70.0, monetization_potential=60.0, overall_score=70.0)
        self.assertEqual(s.overall_score, 70.0)

    def test_score_attributes(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        s = TrendScore(trend=t, relevance_score=80.0, longevity_score=70.0, monetization_potential=60.0, overall_score=70.0)
        self.assertEqual(s.relevance_score, 80.0)

    def test_score_with_values(self):
        t = Trend(trend_id="t1", name="AI", category="tech", start_date="2026-01-01", predicted_peak="2026-06-01", current_momentum=50.0, related_genres=["RPG"])
        s = TrendScore(trend=t, relevance_score=80.0, longevity_score=70.0, monetization_potential=60.0, overall_score=70.0)
        self.assertEqual(s.monetization_potential, 60.0)

    # OpportunityRanker
    def test_rank(self):
        r = OpportunityRanker()
        opps = [RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)]
        result = r.rank(opps)
        self.assertIsInstance(result, list)

    def test_rank_sorted(self):
        r = OpportunityRanker()
        opps = [
            RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0),
            RankerOpportunity(opportunity_id="o2", name="O2", genre="Puzzle", market_size=500000, competition_score=60.0, team_fit=50.0, estimated_cost=100000.0, estimated_revenue=200000.0, risk_score=40.0, strategic_alignment=50.0),
        ]
        result = r.rank(opps)
        self.assertEqual(result[0].rank, 1)

    def test_rank_tiers(self):
        r = OpportunityRanker()
        opps = [RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)]
        result = r.rank(opps)
        self.assertIn(result[0].tier, ["S", "A", "B", "C"])

    def test_get_top_n(self):
        r = OpportunityRanker()
        opps = [
            RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0),
            RankerOpportunity(opportunity_id="o2", name="O2", genre="Puzzle", market_size=500000, competition_score=60.0, team_fit=50.0, estimated_cost=100000.0, estimated_revenue=200000.0, risk_score=40.0, strategic_alignment=50.0),
        ]
        result = r.get_top_n(opps, 1)
        self.assertEqual(len(result), 1)

    def test_get_top_n_empty(self):
        r = OpportunityRanker()
        result = r.get_top_n([], 5)
        self.assertEqual(len(result), 0)

    def test_score_opportunity(self):
        r = OpportunityRanker()
        opp = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        result = r.score_opportunity(opp)
        self.assertIsInstance(result, float)

    # RankerOpportunity
    def test_create_ranker_opp(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        self.assertEqual(o.name, "O1")

    def test_ranker_opp_attributes(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        self.assertEqual(o.genre, "RPG")

    def test_ranker_opp_with_values(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        self.assertEqual(o.market_size, 1000000)

    # RankedOpportunity
    def test_create_ranked(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        r = RankedOpportunity(opportunity=o, total_score=80.0, rank=1, tier="A")
        self.assertEqual(r.rank, 1)

    def test_ranked_attributes(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        r = RankedOpportunity(opportunity=o, total_score=80.0, rank=1, tier="A")
        self.assertIsInstance(r.opportunity, RankerOpportunity)

    def test_ranked_with_values(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        r = RankedOpportunity(opportunity=o, total_score=80.0, rank=1, tier="A")
        self.assertEqual(r.total_score, 80.0)

    # OpportunityScoreBreakdown
    def test_create_breakdown(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        b = OpportunityScoreBreakdown(opportunity=o, market_score=80.0, competition_score=70.0, team_fit_score=60.0, financial_score=50.0, risk_adjusted_score=40.0, strategic_score=30.0)
        self.assertEqual(b.market_score, 80.0)

    def test_breakdown_attributes(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        b = OpportunityScoreBreakdown(opportunity=o, market_score=80.0, competition_score=70.0, team_fit_score=60.0, financial_score=50.0, risk_adjusted_score=40.0, strategic_score=30.0)
        self.assertIsInstance(b.opportunity, RankerOpportunity)

    def test_breakdown_with_values(self):
        o = RankerOpportunity(opportunity_id="o1", name="O1", genre="RPG", market_size=1000000, competition_score=30.0, team_fit=80.0, estimated_cost=100000.0, estimated_revenue=500000.0, risk_score=20.0, strategic_alignment=90.0)
        b = OpportunityScoreBreakdown(opportunity=o, market_score=80.0, competition_score=70.0, team_fit_score=60.0, financial_score=50.0, risk_adjusted_score=40.0, strategic_score=30.0)
        self.assertEqual(b.strategic_score, 30.0)


# ---------------------------------------------------------------------------
# autonomous_product_studio (~80 tests)
# ---------------------------------------------------------------------------
class TestAutonomousProductStudio(unittest.TestCase):
    # IdeaGenerator
    def test_generate(self):
        gen = IdeaGenerator()
        opp = StudioOpportunity(market_segment="casual", trend="merge", audience_size=1000000, monetization_potential=0.8)
        result = gen.generate(opp)
        self.assertIsInstance(result, GameIdea)

    def test_generate_with_opportunity(self):
        gen = IdeaGenerator()
        opp = StudioOpportunity(market_segment="casual", trend="merge", audience_size=1000000, monetization_potential=0.8)
        result = gen.generate(opp)
        self.assertIn("merge", result.tags)

    def test_brainstorm(self):
        gen = IdeaGenerator()
        result = gen.brainstorm(5)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_brainstorm_count(self):
        gen = IdeaGenerator()
        result = gen.brainstorm(3)
        self.assertEqual(len(result), 3)

    def test_evaluate_idea(self):
        gen = IdeaGenerator()
        opp = StudioOpportunity(market_segment="casual", trend="merge", audience_size=1000000, monetization_potential=0.8)
        idea = gen.generate(opp)
        result = gen.evaluate_idea(idea)
        self.assertIsInstance(result, dict)

    def test_evaluate_idea_scores(self):
        gen = IdeaGenerator()
        opp = StudioOpportunity(market_segment="casual", trend="merge", audience_size=1000000, monetization_potential=0.8)
        idea = gen.generate(opp)
        result = gen.evaluate_idea(idea)
        self.assertIn("overall_score", result)

    def test_evaluate_low_score(self):
        gen = IdeaGenerator()
        idea = GameIdea(risk_score=0.9, estimated_market_potential=0.1)
        result = gen.evaluate_idea(idea)
        self.assertIn(result["recommendation"], ["proceed", "revise", "reject"])

    def test_generator_empty(self):
        gen = IdeaGenerator()
        self.assertEqual(len(gen._ideas), 0)

    # GameIdea
    def test_create_idea(self):
        i = GameIdea(title="MyGame", genre="RPG")
        self.assertEqual(i.title, "MyGame")

    def test_idea_attributes(self):
        i = GameIdea(title="MyGame", genre="RPG")
        self.assertEqual(i.genre, "RPG")

    def test_idea_defaults(self):
        i = GameIdea()
        self.assertEqual(i.title, "")

    def test_idea_with_tags(self):
        i = GameIdea(tags=["a", "b"])
        self.assertEqual(len(i.tags), 2)

    # StudioOpportunity
    def test_create_opportunity(self):
        o = StudioOpportunity(market_segment="casual", trend="merge")
        self.assertEqual(o.market_segment, "casual")

    def test_opportunity_attributes(self):
        o = StudioOpportunity(market_segment="casual", trend="merge")
        self.assertEqual(o.trend, "merge")

    def test_opportunity_defaults(self):
        o = StudioOpportunity()
        self.assertEqual(o.market_segment, "")

    # GameDesigner
    def test_design_game(self):
        d = GameDesigner()
        idea = GameIdea(title="G1", genre="RPG", target_platform="Mobile")
        result = d.design_game(idea)
        self.assertIsInstance(result, GameDesignDocument)

    def test_design_game_with_idea(self):
        d = GameDesigner()
        idea = GameIdea(title="G1", genre="RPG", target_platform="Mobile")
        result = d.design_game(idea)
        self.assertEqual(result.title, "G1")

    def test_create_gdd(self):
        d = GameDesigner()
        result = d.create_gdd()
        self.assertIsInstance(result, GameDesignDocument)

    def test_create_gdd_returns_doc(self):
        d = GameDesigner()
        result = d.create_gdd()
        self.assertEqual(result.title, "Untitled Project")

    def test_design_core_loop(self):
        d = GameDesigner()
        result = d.design_core_loop()
        self.assertIsInstance(result, CoreLoop)

    def test_core_loop_steps(self):
        d = GameDesigner()
        result = d.design_core_loop()
        self.assertGreater(len(result.steps), 0)

    def test_design_mechanics(self):
        d = GameDesigner()
        result = d.design_mechanics()
        self.assertIsInstance(result, list)

    def test_design_mechanics_count(self):
        d = GameDesigner()
        result = d.design_mechanics()
        self.assertEqual(len(result), 6)

    # GameDesignDocument
    def test_create_gdd(self):
        g = GameDesignDocument(title="G1", genre="RPG")
        self.assertEqual(g.title, "G1")

    def test_gdd_attributes(self):
        g = GameDesignDocument(title="G1", genre="RPG")
        self.assertEqual(g.genre, "RPG")

    def test_gdd_defaults(self):
        g = GameDesignDocument()
        self.assertEqual(g.title, "")

    def test_gdd_with_values(self):
        g = GameDesignDocument(platforms=["Mobile", "PC"])
        self.assertEqual(len(g.platforms), 2)

    # CoreLoop
    def test_create_loop(self):
        c = CoreLoop(name="Loop1", steps=["a", "b"])
        self.assertEqual(c.name, "Loop1")

    def test_loop_attributes(self):
        c = CoreLoop(name="Loop1", steps=["a", "b"])
        self.assertEqual(len(c.steps), 2)

    def test_loop_with_steps(self):
        c = CoreLoop(steps=["a", "b", "c"], duration_minutes=15.0)
        self.assertEqual(c.duration_minutes, 15.0)

    # Mechanics
    def test_create_mechanics(self):
        m = Mechanics(name="Combat", type="combat")
        self.assertEqual(m.name, "Combat")

    def test_mechanics_attributes(self):
        m = Mechanics(name="Combat", type="combat")
        self.assertEqual(m.type, "combat")

    def test_mechanics_with_complexity(self):
        m = Mechanics(complexity="high")
        self.assertEqual(m.complexity, "high")

    # EconomyArchitect
    def test_design_economy(self):
        e = EconomyArchitect()
        result = e.design_economy()
        self.assertIsInstance(result, EconomyModel)

    def test_design_economy_currencies(self):
        e = EconomyArchitect()
        result = e.design_economy()
        self.assertGreater(len(result.currencies), 0)

    def test_balance_currency(self):
        e = EconomyArchitect()
        e.design_economy()
        curr = e.get_economy_model().currencies[0]
        result = e.balance_currency(curr.id)
        self.assertIsInstance(result, dict)

    def test_balance_currency_not_found(self):
        e = EconomyArchitect()
        result = e.balance_currency("missing")
        self.assertIn("error", result)

    def test_design_reward_loop(self):
        e = EconomyArchitect()
        result = e.design_reward_loop()
        self.assertIsInstance(result, RewardLoop)

    def test_reward_loop_values(self):
        e = EconomyArchitect()
        result = e.design_reward_loop()
        self.assertGreater(result.reward_amount, 0)

    def test_get_economy_model(self):
        e = EconomyArchitect()
        result = e.get_economy_model()
        self.assertIsInstance(result, EconomyModel)

    def test_get_economy_model_creates(self):
        e = EconomyArchitect()
        result = e.get_economy_model()
        self.assertGreater(len(result.currencies), 0)

    # Currency
    def test_create_currency(self):
        c = Currency(name="Gold", symbol="G", type="soft")
        self.assertEqual(c.name, "Gold")

    def test_currency_attributes(self):
        c = Currency(name="Gold", symbol="G", type="soft")
        self.assertEqual(c.type, "soft")

    def test_currency_defaults(self):
        c = Currency()
        self.assertEqual(c.name, "")

    def test_currency_with_sinks(self):
        c = Currency(sink_sources=["shop", "upgrade"])
        self.assertEqual(len(c.sink_sources), 2)

    # RewardLoop
    def test_create_reward_loop(self):
        r = RewardLoop(name="Daily", trigger="login")
        self.assertEqual(r.name, "Daily")

    def test_reward_loop_attributes(self):
        r = RewardLoop(name="Daily", trigger="login")
        self.assertEqual(r.trigger, "login")

    def test_reward_loop_with_values(self):
        r = RewardLoop(reward_amount=100.0, cooldown_minutes=60.0)
        self.assertEqual(r.reward_amount, 100.0)

    # EconomyModel
    def test_create_model(self):
        m = EconomyModel(inflation_control="cap")
        self.assertEqual(m.inflation_control, "cap")

    def test_model_attributes(self):
        m = EconomyModel()
        self.assertIsInstance(m.currencies, list)

    def test_model_with_values(self):
        m = EconomyModel(conversion_rate_usd=0.01)
        self.assertEqual(m.conversion_rate_usd, 0.01)

    # LevelGenerator
    def test_generate_levels(self):
        g = LevelGenerator()
        result = g.generate_levels(5)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_generate_levels_count(self):
        g = LevelGenerator()
        result = g.generate_levels(3)
        self.assertEqual(len(result), 3)

    def test_get_level(self):
        g = LevelGenerator()
        levels = g.generate_levels(1)
        result = g.get_level(levels[0].id)
        self.assertIsInstance(result, Level)

    def test_get_level_not_found(self):
        g = LevelGenerator()
        result = g.get_level("missing")
        self.assertIsNone(result)

    def test_adjust_difficulty(self):
        g = LevelGenerator()
        levels = g.generate_levels(1)
        result = g.adjust_difficulty(levels[0].id, 0.5)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["adjusted"])

    def test_adjust_difficulty_not_found(self):
        g = LevelGenerator()
        result = g.adjust_difficulty("missing", 0.5)
        self.assertIn("error", result)

    # Level
    def test_create_level(self):
        l = Level(level_number=1, name="L1", difficulty=0.5)
        self.assertEqual(l.name, "L1")

    def test_level_attributes(self):
        l = Level(level_number=1, name="L1", difficulty=0.5)
        self.assertEqual(l.level_number, 1)

    def test_level_defaults(self):
        l = Level()
        self.assertEqual(l.level_number, 0)

    def test_level_with_rewards(self):
        l = Level(rewards={"xp": 100})
        self.assertIn("xp", l.rewards)

    # PrototypeBuilder
    def test_build_prototype(self):
        b = PrototypeBuilder()
        result = b.build_prototype(None)
        self.assertIsInstance(result, list)

    def test_build_prototype_features(self):
        b = PrototypeBuilder()
        result = b.build_prototype(None)
        self.assertGreater(len(result), 0)

    def test_get_features(self):
        b = PrototypeBuilder()
        b.build_prototype(None)
        result = b.get_features()
        self.assertIsInstance(result, list)

    def test_estimate_effort(self):
        b = PrototypeBuilder()
        b.build_prototype(None)
        result = b.estimate_effort()
        self.assertIsInstance(result, EffortEstimate)

    def test_estimate_effort_breakdown(self):
        b = PrototypeBuilder()
        b.build_prototype(None)
        result = b.estimate_effort()
        self.assertIn("programming", result.breakdown)

    def test_estimate_without_build(self):
        b = PrototypeBuilder()
        result = b.estimate_effort()
        self.assertIsInstance(result, EffortEstimate)

    # Feature
    def test_create_feature(self):
        f = Feature(name="Combat", status="planned", priority="high")
        self.assertEqual(f.name, "Combat")

    def test_feature_attributes(self):
        f = Feature(name="Combat", status="planned", priority="high")
        self.assertEqual(f.status, "planned")

    def test_feature_defaults(self):
        f = Feature()
        self.assertEqual(f.name, "")

    def test_feature_with_deps(self):
        f = Feature(dependencies=["a", "b"])
        self.assertEqual(len(f.dependencies), 2)

    # EffortEstimate
    def test_create_estimate(self):
        e = EffortEstimate(total_hours=100.0, team_size=3)
        self.assertEqual(e.total_hours, 100.0)

    def test_estimate_attributes(self):
        e = EffortEstimate(total_hours=100.0, team_size=3)
        self.assertEqual(e.team_size, 3)

    def test_estimate_defaults(self):
        e = EffortEstimate()
        self.assertEqual(e.total_hours, 0.0)

    def test_estimate_with_breakdown(self):
        e = EffortEstimate(breakdown={"code": 50.0})
        self.assertIn("code", e.breakdown)

    # PlaytestAgent
    def test_simulate_play(self):
        a = PlaytestAgent()
        result = a.simulate_play(5)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_simulate_play_count(self):
        a = PlaytestAgent()
        result = a.simulate_play(10)
        self.assertEqual(len(result), 10)

    def test_get_feedback(self):
        a = PlaytestAgent()
        a.simulate_play(5)
        result = a.get_feedback()
        self.assertIsInstance(result, Feedback)

    def test_feedback_rates(self):
        a = PlaytestAgent()
        a.simulate_play(5)
        result = a.get_feedback()
        self.assertGreaterEqual(result.completion_rate, 0)

    def test_find_issues(self):
        a = PlaytestAgent()
        a.simulate_play(5)
        result = a.find_issues()
        self.assertIsInstance(result, list)

    def test_find_issues_severity(self):
        a = PlaytestAgent()
        a.simulate_play(5)
        result = a.find_issues()
        for issue in result:
            self.assertIn(issue.severity, ["critical", "major", "minor", "trivial"])

    # PlaySession
    def test_create_session(self):
        s = PlaySession(session_number=1, duration_minutes=10.0)
        self.assertEqual(s.session_number, 1)

    def test_session_attributes(self):
        s = PlaySession(session_number=1, duration_minutes=10.0)
        self.assertEqual(s.duration_minutes, 10.0)

    def test_session_defaults(self):
        s = PlaySession()
        self.assertEqual(s.session_number, 0)

    def test_session_with_values(self):
        s = PlaySession(fun_rating=8.0, difficulty_rating=5.0)
        self.assertEqual(s.fun_rating, 8.0)

    # Feedback
    def test_create_feedback(self):
        f = Feedback(average_fun=7.0, completion_rate=0.8)
        self.assertEqual(f.average_fun, 7.0)

    def test_feedback_attributes(self):
        f = Feedback(average_fun=7.0, completion_rate=0.8)
        self.assertEqual(f.completion_rate, 0.8)

    def test_feedback_with_values(self):
        f = Feedback(nps_score=50.0)
        self.assertEqual(f.nps_score, 50.0)

    # Issue
    def test_create_issue(self):
        i = Issue(severity="major", category="crash", description="bug")
        self.assertEqual(i.severity, "major")

    def test_issue_attributes(self):
        i = Issue(severity="major", category="crash", description="bug")
        self.assertEqual(i.category, "crash")

    def test_issue_with_values(self):
        i = Issue(reproduction_rate=0.5)
        self.assertEqual(i.reproduction_rate, 0.5)

    # ProductManager
    def test_create_product_package(self):
        p = ProductManager()
        opp = StudioOpportunity(market_segment="casual")
        result = p.create_product_package(opp)
        self.assertIsInstance(result, ProductPackage)

    def test_create_package_with_opportunity(self):
        p = ProductManager()
        opp = StudioOpportunity(market_segment="casual")
        result = p.create_product_package(opp)
        self.assertEqual(result.opportunity_id, opp.id)

    def test_get_package(self):
        p = ProductManager()
        result = p.get_package()
        self.assertIsInstance(result, ProductPackage)

    def test_get_package_creates(self):
        p = ProductManager()
        result = p.get_package()
        self.assertIsNotNone(result.id)

    def test_estimate_timeline(self):
        p = ProductManager()
        p.create_product_package(StudioOpportunity())
        result = p.estimate_timeline()
        self.assertIsInstance(result, dict)

    def test_estimate_timeline_milestones(self):
        p = ProductManager()
        p.create_product_package(StudioOpportunity())
        result = p.estimate_timeline()
        self.assertIn("milestones", result)
        self.assertGreater(len(result["milestones"]), 0)

    # Milestone
    def test_create_milestone(self):
        m = Milestone(name="Alpha", duration_weeks=4)
        self.assertEqual(m.name, "Alpha")

    def test_milestone_attributes(self):
        m = Milestone(name="Alpha", duration_weeks=4)
        self.assertEqual(m.duration_weeks, 4)

    def test_milestone_with_deps(self):
        m = Milestone(dependencies=["Pre"])
        self.assertIn("Pre", m.dependencies)

    # ProductPackage
    def test_create_package(self):
        p = ProductPackage(idea_summary="Idea")
        self.assertEqual(p.idea_summary, "Idea")

    def test_package_attributes(self):
        p = ProductPackage(idea_summary="Idea")
        self.assertEqual(p.idea_summary, "Idea")

    def test_package_with_values(self):
        p = ProductPackage(timeline_weeks=12, budget_estimate_usd=100000.0)
        self.assertEqual(p.timeline_weeks, 12)


# ---------------------------------------------------------------------------
# ai_playtest (~60 tests)
# ---------------------------------------------------------------------------
class TestAIPlaytest(unittest.TestCase):
    # PlayerSimulator
    def test_simulate(self):
        s = PlayerSimulator()
        result = s.simulate(10)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 10)

    def test_simulate_count(self):
        s = PlayerSimulator()
        result = s.simulate(5)
        self.assertEqual(len(result), 5)

    def test_get_behaviors(self):
        s = PlayerSimulator()
        s.simulate(5)
        result = s.get_behaviors()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_get_behaviors_empty(self):
        s = PlayerSimulator()
        result = s.get_behaviors()
        self.assertEqual(result, [])

    def test_get_completion_rate(self):
        s = PlayerSimulator()
        s.simulate(5)
        result = s.get_completion_rate()
        self.assertIsInstance(result, float)

    def test_completion_rate_range(self):
        s = PlayerSimulator()
        s.simulate(5)
        result = s.get_completion_rate()
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    # PlayerBehavior
    def test_create_behavior(self):
        b = PlayerBehavior(player_id="p1", session_length_minutes=10.0, actions_per_session=20, preferred_mode="solo", spending_usd=5.0, social_interactions=0)
        self.assertEqual(b.player_id, "p1")

    def test_behavior_attributes(self):
        b = PlayerBehavior(player_id="p1", session_length_minutes=10.0, actions_per_session=20, preferred_mode="solo", spending_usd=5.0, social_interactions=0)
        self.assertEqual(b.preferred_mode, "solo")

    def test_behavior_defaults(self):
        b = PlayerBehavior(player_id="p1", session_length_minutes=10.0, actions_per_session=20, preferred_mode="solo", spending_usd=5.0, social_interactions=0)
        self.assertEqual(b.spending_usd, 5.0)

    def test_behavior_with_values(self):
        b = PlayerBehavior(player_id="p1", session_length_minutes=10.0, actions_per_session=20, preferred_mode="solo", spending_usd=5.0, social_interactions=10)
        self.assertEqual(b.social_interactions, 10)

    # RetentionPredictor
    def test_predict_d1(self):
        p = RetentionPredictor()
        result = p.predict_d1()
        self.assertIsInstance(result, float)

    def test_predict_d7(self):
        p = RetentionPredictor()
        result = p.predict_d7()
        self.assertIsInstance(result, float)

    def test_predict_d30(self):
        p = RetentionPredictor()
        result = p.predict_d30()
        self.assertIsInstance(result, float)

    def test_predict_ltv(self):
        p = RetentionPredictor()
        result = p.predict_ltv()
        self.assertIsInstance(result, float)

    def test_predictions_positive(self):
        p = RetentionPredictor()
        self.assertGreater(p.predict_d1(), 0)
        self.assertGreater(p.predict_d7(), 0)
        self.assertGreater(p.predict_ltv(), 0)

    def test_forecast_created(self):
        p = RetentionPredictor()
        p.predict_d1()
        self.assertIsNotNone(p._forecast)

    # RetentionForecast
    def test_create_forecast(self):
        f = RetentionForecast(d1=0.5, d7=0.3, d30=0.1, ltv_usd=10.0, confidence=0.8)
        self.assertEqual(f.d1, 0.5)

    def test_forecast_attributes(self):
        f = RetentionForecast(d1=0.5, d7=0.3, d30=0.1, ltv_usd=10.0, confidence=0.8)
        self.assertEqual(f.ltv_usd, 10.0)

    def test_forecast_positive(self):
        f = RetentionForecast(d1=0.5, d7=0.3, d30=0.1, ltv_usd=10.0, confidence=0.8)
        self.assertGreater(f.d1, 0)

    def test_forecast_with_values(self):
        f = RetentionForecast(d1=0.5, d7=0.3, d30=0.1, ltv_usd=10.0, confidence=0.8)
        self.assertEqual(f.confidence, 0.8)

    # ChurnAnalyzer
    def test_analyze_churn(self):
        a = ChurnAnalyzer()
        result = a.analyze_churn()
        self.assertIsInstance(result, ChurnReport)

    def test_analyze_churn_rate(self):
        a = ChurnAnalyzer()
        result = a.analyze_churn()
        self.assertGreater(result.churn_rate, 0)

    def test_get_churn_reasons(self):
        a = ChurnAnalyzer()
        result = a.get_churn_reasons()
        self.assertIsInstance(result, list)

    def test_get_churn_reasons_list(self):
        a = ChurnAnalyzer()
        result = a.get_churn_reasons()
        self.assertEqual(len(result), 3)

    def test_predict_churn_rate(self):
        a = ChurnAnalyzer()
        result = a.predict_churn_rate()
        self.assertIsInstance(result, float)

    def test_predict_churn_rate_range(self):
        a = ChurnAnalyzer()
        result = a.predict_churn_rate()
        self.assertGreater(result, 0)
        self.assertLess(result, 1)

    # ChurnReport
    def test_create_report(self):
        r = ChurnReport(churn_rate=0.2)
        self.assertEqual(r.churn_rate, 0.2)

    def test_report_attributes(self):
        r = ChurnReport(churn_rate=0.2, top_reasons=["r1"])
        self.assertIn("r1", r.top_reasons)

    def test_report_defaults(self):
        r = ChurnReport(churn_rate=0.2)
        self.assertEqual(r.top_reasons, [])

    def test_report_with_values(self):
        r = ChurnReport(churn_rate=0.2, risk_segments=["new"])
        self.assertIn("new", r.risk_segments)

    # DifficultyOptimizer
    def test_optimize(self):
        o = DifficultyOptimizer()
        result = o.optimize(5)
        self.assertIsInstance(result, DifficultyProfile)

    def test_optimize_level(self):
        o = DifficultyOptimizer()
        result = o.optimize(5)
        self.assertEqual(result.level, 5)

    def test_get_difficulty_curve(self):
        o = DifficultyOptimizer()
        result = o.get_difficulty_curve()
        self.assertIsInstance(result, list)

    def test_get_difficulty_curve_length(self):
        o = DifficultyOptimizer()
        result = o.get_difficulty_curve()
        self.assertEqual(len(result), 20)

    def test_test_balance(self):
        o = DifficultyOptimizer()
        result = o.test_balance()
        self.assertIsInstance(result, dict)

    def test_test_balance_scores(self):
        o = DifficultyOptimizer()
        result = o.test_balance()
        self.assertIn("balance_score", result)

    # DifficultyProfile
    def test_create_profile(self):
        p = DifficultyProfile(level=1, recommended_difficulty=0.2, expected_clear_rate=0.8, adjustments=[])
        self.assertEqual(p.level, 1)

    def test_profile_attributes(self):
        p = DifficultyProfile(level=1, recommended_difficulty=0.2, expected_clear_rate=0.8, adjustments=[])
        self.assertEqual(p.recommended_difficulty, 0.2)

    def test_profile_defaults(self):
        p = DifficultyProfile(level=1, recommended_difficulty=0.2, expected_clear_rate=0.8, adjustments=[])
        self.assertEqual(p.adjustments, [])

    def test_profile_with_values(self):
        p = DifficultyProfile(level=1, recommended_difficulty=0.2, expected_clear_rate=0.8, adjustments=["a"])
        self.assertIn("a", p.adjustments)

    # FunScoreModel
    def test_score(self):
        m = FunScoreModel()
        result = m.score("game1")
        self.assertIsInstance(result, FunScore)

    def test_score_verdict(self):
        m = FunScoreModel()
        result = m.score("game1")
        self.assertIn(result.verdict, ["highly_fun", "fun", "moderate", "low_fun"])

    def test_get_fun_factors(self):
        m = FunScoreModel()
        result = m.get_fun_factors()
        self.assertIsInstance(result, FunFactors)

    def test_get_fun_factors_range(self):
        m = FunScoreModel()
        result = m.get_fun_factors()
        self.assertGreaterEqual(result.novelty, 0)
        self.assertLessEqual(result.novelty, 1)

    def test_compare(self):
        m = FunScoreModel()
        a = m.score("game_a")
        b = m.score("game_b")
        result = m.compare(a, b)
        self.assertIsInstance(result, dict)

    def test_compare_winner(self):
        m = FunScoreModel()
        a = m.score("game_a")
        b = m.score("game_b")
        result = m.compare(a, b)
        self.assertIn(result["winner"], ["A", "B"])

    # FunScore
    def test_create_fun_score(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        s = FunScore(total_score=0.5, factors=f, verdict="fun")
        self.assertEqual(s.total_score, 0.5)

    def test_fun_score_attributes(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        s = FunScore(total_score=0.5, factors=f, verdict="fun")
        self.assertEqual(s.verdict, "fun")

    def test_fun_score_defaults(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        s = FunScore(total_score=0.5, factors=f, verdict="fun")
        self.assertIsInstance(s.factors, FunFactors)

    def test_fun_score_with_values(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        s = FunScore(total_score=0.5, factors=f, verdict="fun")
        self.assertEqual(s.factors.novelty, 0.8)

    # FunFactors
    def test_create_factors(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        self.assertEqual(f.novelty, 0.8)

    def test_factors_attributes(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        self.assertEqual(f.challenge, 0.7)

    def test_factors_defaults(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        self.assertEqual(f.reward, 0.6)

    def test_factors_with_values(self):
        f = FunFactors(novelty=0.8, challenge=0.7, reward=0.6, autonomy=0.5, social=0.4, narrative=0.3)
        self.assertEqual(f.narrative, 0.3)


# ---------------------------------------------------------------------------
# capital_allocator (~50 tests)
# ---------------------------------------------------------------------------
class TestCapitalAllocator(unittest.TestCase):
    # ProjectRanker
    def test_rank_projects(self):
        r = ProjectRanker()
        result = r.rank_projects([{"project_id": "p1", "project_name": "P1"}])
        self.assertIsInstance(result, list)

    def test_rank_projects_sorted(self):
        r = ProjectRanker()
        result = r.rank_projects([
            {"project_id": "p1", "project_name": "P1", "financial_score": 80},
            {"project_id": "p2", "project_name": "P2", "financial_score": 60},
        ])
        self.assertEqual(result[0].rank, 1)

    def test_get_top_projects(self):
        r = ProjectRanker()
        r.rank_projects([{"project_id": "p1"}, {"project_id": "p2"}, {"project_id": "p3"}])
        result = r.get_top_projects(2)
        self.assertEqual(len(result), 2)

    def test_get_top_projects_n(self):
        r = ProjectRanker()
        r.rank_projects([{"project_id": "p1"}])
        result = r.get_top_projects(5)
        self.assertEqual(len(result), 1)

    def test_score_project(self):
        r = ProjectRanker()
        result = r.score_project({"project_id": "p1"})
        self.assertIsInstance(result, ProjectScore)

    def test_score_project_total(self):
        r = ProjectRanker()
        result = r.score_project({"project_id": "p1", "financial_score": 100, "strategic_score": 100, "execution_score": 100, "market_score": 100})
        self.assertGreater(result.total_score, 0)

    # ProjectScore
    def test_create_score(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        self.assertEqual(s.project_id, "p1")

    def test_score_attributes(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        self.assertEqual(s.financial_score, 80.0)

    def test_score_total(self):
        s = ProjectScore(project_id="p1", financial_score=100.0, strategic_score=100.0, execution_score=100.0, market_score=100.0)
        self.assertEqual(s.total_score, 100.0)

    def test_score_with_values(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        self.assertEqual(s.market_score, 50.0)

    # RankedProject
    def test_create_ranked(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        r = RankedProject(rank=1, project_id="p1", project_name="P1", score=s)
        self.assertEqual(r.rank, 1)

    def test_ranked_attributes(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        r = RankedProject(rank=1, project_id="p1", project_name="P1", score=s)
        self.assertEqual(r.project_name, "P1")

    def test_ranked_priority(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        r = RankedProject(rank=1, project_id="p1", project_name="P1", score=s, priority="high")
        self.assertEqual(r.priority, "high")

    def test_ranked_with_values(self):
        s = ProjectScore(project_id="p1", financial_score=80.0, strategic_score=70.0, execution_score=60.0, market_score=50.0)
        r = RankedProject(rank=1, project_id="p1", project_name="P1", score=s, recommendation="accelerate")
        self.assertEqual(r.recommendation, "accelerate")

    # BudgetAllocator
    def test_allocate(self):
        a = BudgetAllocator()
        result = a.allocate(1000, [{"project_id": "p1", "weight": 1}, {"project_id": "p2", "weight": 1}])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_allocate_empty(self):
        a = BudgetAllocator()
        result = a.allocate(1000, [])
        self.assertEqual(result, [])

    def test_reallocate(self):
        a = BudgetAllocator()
        a.allocate(1000, [{"project_id": "p1", "weight": 1}])
        result = a.reallocate("p1", 2000)
        self.assertIsNotNone(result)

    def test_reallocate_not_found(self):
        a = BudgetAllocator()
        result = a.reallocate("missing", 100)
        self.assertIsNone(result)

    def test_get_allocation(self):
        a = BudgetAllocator()
        a.allocate(1000, [{"project_id": "p1", "weight": 1}])
        result = a.get_allocation()
        self.assertIsInstance(result, dict)
        self.assertIn("p1", result)

    def test_allocation_amounts(self):
        a = BudgetAllocator()
        result = a.allocate(1000, [{"project_id": "p1", "weight": 1}])
        self.assertEqual(result[0].allocated_amount, 1000.0)

    # BudgetAllocation
    def test_create_allocation(self):
        a = BudgetAllocation(allocation_id="a1", project_id="p1", allocated_amount=1000.0, spent_amount=0.0, remaining_amount=1000.0)
        self.assertEqual(a.project_id, "p1")

    def test_allocation_attributes(self):
        a = BudgetAllocation(allocation_id="a1", project_id="p1", allocated_amount=1000.0, spent_amount=0.0, remaining_amount=1000.0)
        self.assertEqual(a.allocated_amount, 1000.0)

    def test_allocation_remaining(self):
        a = BudgetAllocation(allocation_id="a1", project_id="p1", allocated_amount=1000.0, spent_amount=200.0, remaining_amount=0.0)
        self.assertEqual(a.remaining_amount, 800.0)

    def test_allocation_with_values(self):
        a = BudgetAllocation(allocation_id="a1", project_id="p1", allocated_amount=1000.0, spent_amount=0.0, remaining_amount=1000.0, currency="USD")
        self.assertEqual(a.currency, "USD")

    # AllocationChange
    def test_create_change(self):
        c = AllocationChange(change_id="c1", project_id="p1", previous_amount=1000.0, new_amount=2000.0, delta=0.0, reason="test")
        self.assertEqual(c.project_id, "p1")

    def test_change_attributes(self):
        c = AllocationChange(change_id="c1", project_id="p1", previous_amount=1000.0, new_amount=2000.0, delta=0.0, reason="test")
        self.assertEqual(c.reason, "test")

    def test_change_delta(self):
        c = AllocationChange(change_id="c1", project_id="p1", previous_amount=1000.0, new_amount=2000.0, delta=0.0, reason="test")
        self.assertEqual(c.delta, 1000.0)

    def test_change_with_values(self):
        c = AllocationChange(change_id="c1", project_id="p1", previous_amount=1000.0, new_amount=2000.0, delta=0.0, reason="test")
        self.assertEqual(c.new_amount, 2000.0)

    # RiskModel
    def test_assess_risk(self):
        m = RiskModel()
        result = m.assess_risk({"project_id": "p1"})
        self.assertIsInstance(result, RiskAssessment)

    def test_assess_risk_level(self):
        m = RiskModel()
        result = m.assess_risk({"project_id": "p1", "market_risk": 0.1, "execution_risk": 0.1, "financial_risk": 0.1, "technology_risk": 0.1})
        self.assertIn(result.risk_level, ["low", "medium", "high"])

    def test_get_portfolio_risk(self):
        m = RiskModel()
        m.assess_risk({"project_id": "p1"})
        result = m.get_portfolio_risk()
        self.assertIsInstance(result, PortfolioRisk)

    def test_get_portfolio_risk_empty(self):
        m = RiskModel()
        result = m.get_portfolio_risk()
        self.assertEqual(result.portfolio_id, "empty")

    def test_calculate_var(self):
        m = RiskModel()
        m.assess_risk({"project_id": "p1"})
        var95, var99 = m.calculate_var()
        self.assertIsInstance(var95, float)
        self.assertIsInstance(var99, float)

    def test_calculate_var_empty(self):
        m = RiskModel()
        var95, var99 = m.calculate_var()
        self.assertEqual(var95, 0.0)
        self.assertEqual(var99, 0.0)

    # RiskAssessment
    def test_create_assessment(self):
        a = RiskAssessment(assessment_id="a1", project_id="p1", market_risk=0.2, execution_risk=0.3, financial_risk=0.4, technology_risk=0.1)
        self.assertEqual(a.project_id, "p1")

    def test_assessment_attributes(self):
        a = RiskAssessment(assessment_id="a1", project_id="p1", market_risk=0.2, execution_risk=0.3, financial_risk=0.4, technology_risk=0.1)
        self.assertEqual(a.market_risk, 0.2)

    def test_assessment_level(self):
        a = RiskAssessment(assessment_id="a1", project_id="p1", market_risk=0.1, execution_risk=0.1, financial_risk=0.1, technology_risk=0.1)
        self.assertEqual(a.risk_level, "low")

    def test_assessment_with_values(self):
        a = RiskAssessment(assessment_id="a1", project_id="p1", market_risk=0.8, execution_risk=0.8, financial_risk=0.8, technology_risk=0.8)
        self.assertEqual(a.risk_level, "high")

    # PortfolioRisk
    def test_create_portfolio_risk(self):
        p = PortfolioRisk(portfolio_id="pf1", avg_risk_score=0.5, max_risk_project_id="p1", min_risk_project_id="p2", diversification_score=0.6, var_95=0.1, var_99=0.05)
        self.assertEqual(p.portfolio_id, "pf1")

    def test_portfolio_risk_attributes(self):
        p = PortfolioRisk(portfolio_id="pf1", avg_risk_score=0.5, max_risk_project_id="p1", min_risk_project_id="p2", diversification_score=0.6, var_95=0.1, var_99=0.05)
        self.assertEqual(p.avg_risk_score, 0.5)

    def test_portfolio_risk_var(self):
        p = PortfolioRisk(portfolio_id="pf1", avg_risk_score=0.5, max_risk_project_id="p1", min_risk_project_id="p2", diversification_score=0.6, var_95=0.1, var_99=0.05)
        self.assertEqual(p.var_95, 0.1)

    def test_portfolio_risk_with_values(self):
        p = PortfolioRisk(portfolio_id="pf1", avg_risk_score=0.5, max_risk_project_id="p1", min_risk_project_id="p2", diversification_score=0.6, var_95=0.1, var_99=0.05)
        self.assertEqual(p.diversification_score, 0.6)

    # KillDecision
    def test_should_kill(self):
        k = KillDecision()
        result = k.should_kill({"project_id": "p1"})
        self.assertIsInstance(result, KillRecommendation)

    def test_should_kill_healthy(self):
        k = KillDecision()
        result = k.should_kill({"project_id": "p1", "financial_health": 0.9, "schedule_health": 0.9, "team_health": 0.9, "quality_health": 0.9})
        self.assertFalse(result.should_kill)

    def test_analyze_project_health(self):
        k = KillDecision()
        result = k.analyze_project_health({"project_id": "p1"})
        self.assertIsInstance(result, ProjectHealth)

    def test_analyze_health_status(self):
        k = KillDecision()
        result = k.analyze_project_health({"project_id": "p1", "financial_health": 0.9, "schedule_health": 0.9, "team_health": 0.9, "quality_health": 0.9})
        self.assertEqual(result.health_status, "healthy")

    def test_get_kill_candidates(self):
        k = KillDecision()
        k.should_kill({"project_id": "p1", "financial_health": 0.1, "schedule_health": 0.1, "team_health": 0.1, "quality_health": 0.1})
        result = k.get_kill_candidates()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_get_kill_candidates_empty(self):
        k = KillDecision()
        result = k.get_kill_candidates()
        self.assertEqual(result, [])

    # ProjectHealth
    def test_create_health(self):
        h = ProjectHealth(project_id="p1", financial_health=0.8, schedule_health=0.7, team_health=0.6, quality_health=0.5)
        self.assertEqual(h.project_id, "p1")

    def test_health_attributes(self):
        h = ProjectHealth(project_id="p1", financial_health=0.8, schedule_health=0.7, team_health=0.6, quality_health=0.5)
        self.assertEqual(h.financial_health, 0.8)

    def test_health_status(self):
        h = ProjectHealth(project_id="p1", financial_health=0.9, schedule_health=0.9, team_health=0.9, quality_health=0.9)
        self.assertEqual(h.health_status, "healthy")

    def test_health_with_values(self):
        h = ProjectHealth(project_id="p1", financial_health=0.2, schedule_health=0.2, team_health=0.2, quality_health=0.2)
        self.assertEqual(h.health_status, "critical")

    # KillRecommendation
    def test_create_recommendation(self):
        r = KillRecommendation(recommendation_id="r1", project_id="p1", should_kill=True, confidence=0.9)
        self.assertEqual(r.project_id, "p1")

    def test_recommendation_attributes(self):
        r = KillRecommendation(recommendation_id="r1", project_id="p1", should_kill=True, confidence=0.9)
        self.assertTrue(r.should_kill)

    def test_recommendation_should_kill(self):
        r = KillRecommendation(recommendation_id="r1", project_id="p1", should_kill=False, confidence=0.5)
        self.assertFalse(r.should_kill)

    def test_recommendation_with_values(self):
        r = KillRecommendation(recommendation_id="r1", project_id="p1", should_kill=True, confidence=0.9, primary_reasons=["budget"])
        self.assertIn("budget", r.primary_reasons)

    # PortfolioManager
    def test_add_project(self):
        p = PortfolioManager()
        result = p.add_project({"name": "P1"})
        self.assertIsInstance(result, str)

    def test_add_project_id(self):
        p = PortfolioManager()
        pid = p.add_project({"project_id": "p1"})
        self.assertEqual(pid, "p1")

    def test_remove_project(self):
        p = PortfolioManager()
        pid = p.add_project({"name": "P1"})
        result = p.remove_project(pid)
        self.assertTrue(result)

    def test_remove_project_not_found(self):
        p = PortfolioManager()
        result = p.remove_project("missing")
        self.assertFalse(result)

    def test_get_portfolio_summary(self):
        p = PortfolioManager()
        p.add_project({"name": "P1", "score": 80})
        result = p.get_portfolio_summary()
        self.assertIsInstance(result, PortfolioSummary)

    def test_optimize_portfolio(self):
        p = PortfolioManager()
        p.add_project({"name": "P1", "score": 80})
        result = p.optimize_portfolio()
        self.assertIsInstance(result, PortfolioOptimization)

    # PortfolioSummary
    def test_create_summary(self):
        s = PortfolioSummary(portfolio_id="pf1", total_projects=5, active_projects=3, total_budget=1000.0, total_spent=500.0, total_remaining=500.0, avg_project_score=75.0, risk_level="medium", top_project_id="p1", bottom_project_id="p2")
        self.assertEqual(s.portfolio_id, "pf1")

    def test_summary_attributes(self):
        s = PortfolioSummary(portfolio_id="pf1", total_projects=5, active_projects=3, total_budget=1000.0, total_spent=500.0, total_remaining=500.0, avg_project_score=75.0, risk_level="medium", top_project_id="p1", bottom_project_id="p2")
        self.assertEqual(s.total_projects, 5)

    def test_summary_risk(self):
        s = PortfolioSummary(portfolio_id="pf1", total_projects=5, active_projects=3, total_budget=1000.0, total_spent=500.0, total_remaining=500.0, avg_project_score=75.0, risk_level="medium", top_project_id="p1", bottom_project_id="p2")
        self.assertEqual(s.risk_level, "medium")

    def test_summary_with_values(self):
        s = PortfolioSummary(portfolio_id="pf1", total_projects=5, active_projects=3, total_budget=1000.0, total_spent=500.0, total_remaining=500.0, avg_project_score=75.0, risk_level="medium", top_project_id="p1", bottom_project_id="p2")
        self.assertEqual(s.top_project_id, "p1")

    # PortfolioOptimization
    def test_create_optimization(self):
        o = PortfolioOptimization(optimization_id="o1")
        self.assertEqual(o.optimization_id, "o1")

    def test_optimization_attributes(self):
        o = PortfolioOptimization(optimization_id="o1")
        self.assertIsInstance(o.recommended_additions, list)

    def test_optimization_budget(self):
        o = PortfolioOptimization(optimization_id="o1", budget_reallocation={"p1": 100.0})
        self.assertIn("p1", o.budget_reallocation)

    def test_optimization_with_values(self):
        o = PortfolioOptimization(optimization_id="o1", expected_return_improvement=0.1, expected_risk_reduction=0.05)
        self.assertEqual(o.expected_return_improvement, 0.1)


# ---------------------------------------------------------------------------
# autonomous_growth (~50 tests)
# ---------------------------------------------------------------------------
class TestAutonomousGrowth(unittest.TestCase):
    # UABrain
    def test_optimize_campaigns(self):
        b = UABrain()
        result = b.optimize_campaigns([{"id": "c1", "cpi": 1.0, "roas": 2.0, "channel": "meta", "installs": 1000}])
        self.assertIsInstance(result, list)

    def test_optimize_campaigns_count(self):
        b = UABrain()
        result = b.optimize_campaigns([{"id": "c1", "cpi": 1.0, "roas": 2.0, "channel": "meta", "installs": 1000}])
        self.assertEqual(len(result), 1)

    def test_optimize_good_performance(self):
        b = UABrain()
        result = b.optimize_campaigns([{"id": "c1", "cpi": 1.0, "roas": 2.0, "channel": "meta", "installs": 1000}])
        self.assertGreater(result[0].budget_change_pct, 0)

    def test_optimize_poor_performance(self):
        b = UABrain()
        result = b.optimize_campaigns([{"id": "c1", "cpi": 3.0, "roas": 0.5, "channel": "meta", "installs": 100}])
        self.assertLess(result[0].budget_change_pct, 0)

    def test_allocate_budget(self):
        b = UABrain()
        result = b.allocate_budget(1000, {"meta": 2.0, "google": 1.0})
        self.assertIsInstance(result, dict)

    def test_allocate_budget_sum(self):
        b = UABrain()
        result = b.allocate_budget(1000, {"meta": 1.0, "google": 1.0})
        self.assertAlmostEqual(sum(result.values()), 1000.0, places=1)

    def test_analyze_performance(self):
        b = UABrain()
        result = b.analyze_performance({"cpi": 1.5, "roas": 1.5, "retention_d1": 0.35})
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)

    def test_suggest_scaling(self):
        b = UABrain()
        result = b.suggest_scaling([{"id": "c1", "roas": 2.0, "installs": 2000, "budget": 1000}])
        self.assertIsInstance(result, list)

    # CampaignOptimization
    def test_create_optimization(self):
        o = CampaignOptimization(campaign_id="c1", channel="meta", budget_change_pct=10.0, bid_change_pct=5.0, target_cpi=1.0, expected_installs=1000)
        self.assertEqual(o.campaign_id, "c1")

    def test_optimization_attributes(self):
        o = CampaignOptimization(campaign_id="c1", channel="meta", budget_change_pct=10.0, bid_change_pct=5.0, target_cpi=1.0, expected_installs=1000)
        self.assertEqual(o.channel, "meta")

    def test_optimization_defaults(self):
        o = CampaignOptimization(campaign_id="c1", channel="meta", budget_change_pct=10.0, bid_change_pct=5.0, target_cpi=1.0, expected_installs=1000)
        self.assertEqual(o.notes, "")

    def test_optimization_with_values(self):
        o = CampaignOptimization(campaign_id="c1", channel="meta", budget_change_pct=10.0, bid_change_pct=5.0, target_cpi=1.0, expected_installs=1000, notes="test")
        self.assertEqual(o.notes, "test")

    # UARecommendation
    def test_create_recommendation(self):
        r = UARecommendation(recommendation_id="r1", priority="high", action="scale", expected_impact=0.1, confidence=0.8)
        self.assertEqual(r.recommendation_id, "r1")

    def test_recommendation_attributes(self):
        r = UARecommendation(recommendation_id="r1", priority="high", action="scale", expected_impact=0.1, confidence=0.8)
        self.assertEqual(r.priority, "high")

    def test_recommendation_defaults(self):
        r = UARecommendation(recommendation_id="r1", priority="high", action="scale", expected_impact=0.1, confidence=0.8)
        self.assertEqual(r.details, {})

    def test_recommendation_with_values(self):
        r = UARecommendation(recommendation_id="r1", priority="high", action="scale", expected_impact=0.1, confidence=0.8, details={"key": "val"})
        self.assertEqual(r.details["key"], "val")

    # CreativeBrain
    def test_generate_creative_concepts(self):
        b = CreativeBrain()
        result = b.generate_creative_concepts({"target_audiences": ["casual"]}, 3)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_generate_concepts_count(self):
        b = CreativeBrain()
        result = b.generate_creative_concepts({}, 5)
        self.assertEqual(len(result), 5)

    def test_evaluate_creative(self):
        b = CreativeBrain()
        result = b.evaluate_creative({"id": "c1", "ctr": 0.05, "cvr": 0.06, "engagement_rate": 0.1})
        self.assertIsInstance(result, CreativeEvaluation)

    def test_evaluate_creative_scores(self):
        b = CreativeBrain()
        result = b.evaluate_creative({"id": "c1", "ctr": 0.05, "cvr": 0.06, "engagement_rate": 0.1})
        self.assertGreater(result.overall_score, 0)

    def test_predict_ctr(self):
        b = CreativeBrain()
        result = b.predict_ctr({"has_video": True, "headline": "Play Free", "format": "playable", "historical_ctr": 0.02})
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_get_winning_patterns(self):
        b = CreativeBrain()
        result = b.get_winning_patterns()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    # CreativeConcept
    def test_create_concept(self):
        c = CreativeConcept(concept_id="c1", theme="fantasy", format="video", headline="H1", description="D1", cta_text="Play", target_audience="casual")
        self.assertEqual(c.concept_id, "c1")

    def test_concept_attributes(self):
        c = CreativeConcept(concept_id="c1", theme="fantasy", format="video", headline="H1", description="D1", cta_text="Play", target_audience="casual")
        self.assertEqual(c.theme, "fantasy")

    def test_concept_defaults(self):
        c = CreativeConcept(concept_id="c1", theme="fantasy", format="video", headline="H1", description="D1", cta_text="Play", target_audience="casual")
        self.assertEqual(c.tags, [])

    def test_concept_with_values(self):
        c = CreativeConcept(concept_id="c1", theme="fantasy", format="video", headline="H1", description="D1", cta_text="Play", target_audience="casual", predicted_ctr=0.05)
        self.assertEqual(c.predicted_ctr, 0.05)

    # CreativeEvaluation
    def test_create_evaluation(self):
        e = CreativeEvaluation(creative_id="c1", overall_score=8.0, ctr_score=7.0, cvr_score=6.0, engagement_score=5.0)
        self.assertEqual(e.creative_id, "c1")

    def test_evaluation_attributes(self):
        e = CreativeEvaluation(creative_id="c1", overall_score=8.0, ctr_score=7.0, cvr_score=6.0, engagement_score=5.0)
        self.assertEqual(e.overall_score, 8.0)

    def test_evaluation_defaults(self):
        e = CreativeEvaluation(creative_id="c1", overall_score=8.0, ctr_score=7.0, cvr_score=6.0, engagement_score=5.0)
        self.assertEqual(e.strengths, [])

    def test_evaluation_with_values(self):
        e = CreativeEvaluation(creative_id="c1", overall_score=8.0, ctr_score=7.0, cvr_score=6.0, engagement_score=5.0, strengths=["good"])
        self.assertIn("good", e.strengths)

    # ASOBrain
    def test_optimize_keywords(self):
        b = ASOBrain()
        result = b.optimize_keywords(["puzzle", "game"], ["rpg", "adventure"])
        self.assertIsInstance(result, list)

    def test_optimize_keywords_count(self):
        b = ASOBrain()
        result = b.optimize_keywords(["puzzle"], ["rpg"])
        self.assertGreater(len(result), 0)

    def test_optimize_metadata(self):
        b = ASOBrain()
        result = b.optimize_metadata({"title": "Game", "subtitle": "Fun", "description": "A game"})
        self.assertIsInstance(result, list)

    def test_analyze_ranking(self):
        b = ASOBrain()
        result = b.analyze_ranking("puzzle", [{"keyword": "puzzle", "rank": 10}])
        self.assertIsInstance(result, dict)

    def test_analyze_ranking_trend(self):
        b = ASOBrain()
        result = b.analyze_ranking("puzzle", [{"keyword": "puzzle", "rank": 10}, {"keyword": "puzzle", "rank": 8}])
        self.assertEqual(result["trend"], "improving")

    def test_suggest_changes(self):
        b = ASOBrain()
        result = b.suggest_changes({"screenshots": ["s1"], "video_preview": False})
        self.assertIsInstance(result, list)

    # ASORecommendation
    def test_create_recommendation(self):
        r = ASORecommendation(recommendation_id="r1", category="title", priority="high", action="extend", expected_impact="+5%")
        self.assertEqual(r.recommendation_id, "r1")

    def test_recommendation_attributes(self):
        r = ASORecommendation(recommendation_id="r1", category="title", priority="high", action="extend", expected_impact="+5%")
        self.assertEqual(r.category, "title")

    def test_recommendation_defaults(self):
        r = ASORecommendation(recommendation_id="r1", category="title", priority="high", action="extend", expected_impact="+5%")
        self.assertEqual(r.details, {})

    def test_recommendation_with_values(self):
        r = ASORecommendation(recommendation_id="r1", category="title", priority="high", action="extend", expected_impact="+5%", details={"key": "val"})
        self.assertEqual(r.details["key"], "val")

    # KeywordOptimization
    def test_create_keyword_opt(self):
        k = KeywordOptimization(keyword="puzzle", current_rank=10, target_rank=5, search_volume=1000, difficulty=0.5, opportunity_score=80.0)
        self.assertEqual(k.keyword, "puzzle")

    def test_keyword_opt_attributes(self):
        k = KeywordOptimization(keyword="puzzle", current_rank=10, target_rank=5, search_volume=1000, difficulty=0.5, opportunity_score=80.0)
        self.assertEqual(k.current_rank, 10)

    def test_keyword_opt_defaults(self):
        k = KeywordOptimization(keyword="puzzle", current_rank=10, target_rank=5, search_volume=1000, difficulty=0.5, opportunity_score=80.0)
        self.assertEqual(k.suggestions, [])

    def test_keyword_opt_with_values(self):
        k = KeywordOptimization(keyword="puzzle", current_rank=10, target_rank=5, search_volume=1000, difficulty=0.5, opportunity_score=80.0, suggestions=["a"])
        self.assertIn("a", k.suggestions)

    # MonetizationBrain
    def test_optimize_iap(self):
        b = MonetizationBrain()
        result = b.optimize_iap([{"name": "whales", "avg_spend": 50.0}])
        self.assertIsInstance(result, list)

    def test_optimize_iap_count(self):
        b = MonetizationBrain()
        result = b.optimize_iap([{"name": "new", "avg_spend": 0.0}, {"name": "mid", "avg_spend": 3.0}])
        self.assertEqual(len(result), 2)

    def test_optimize_ads(self):
        b = MonetizationBrain()
        result = b.optimize_ads({"ecpm": 2.0, "fill_rate": 0.8})
        self.assertIsInstance(result, list)

    def test_optimize_ads_recommendations(self):
        b = MonetizationBrain()
        result = b.optimize_ads({"ecpm": 2.0, "fill_rate": 0.8})
        self.assertGreater(len(result), 0)

    def test_analyze_arpu(self):
        b = MonetizationBrain()
        result = b.analyze_arpu([{"revenue": 10.0, "is_active_today": 1, "segment": "a"}])
        self.assertIsInstance(result, dict)
        self.assertIn("arpu", result)

    def test_suggest_offers(self):
        b = MonetizationBrain()
        result = b.suggest_offers({"level": 10, "days_since_purchase": 10, "in_game_currency": 50})
        self.assertIsInstance(result, list)

    # MonetizationRecommendation
    def test_create_mon_rec(self):
        r = MonetizationRecommendation(recommendation_id="r1", type="iap", priority="high", action="bundle", expected_revenue_lift=0.1)
        self.assertEqual(r.recommendation_id, "r1")

    def test_mon_rec_attributes(self):
        r = MonetizationRecommendation(recommendation_id="r1", type="iap", priority="high", action="bundle", expected_revenue_lift=0.1)
        self.assertEqual(r.type, "iap")

    def test_mon_rec_defaults(self):
        r = MonetizationRecommendation(recommendation_id="r1", type="iap", priority="high", action="bundle", expected_revenue_lift=0.1)
        self.assertEqual(r.details, {})

    def test_mon_rec_with_values(self):
        r = MonetizationRecommendation(recommendation_id="r1", type="iap", priority="high", action="bundle", expected_revenue_lift=0.1, details={"price": 4.99})
        self.assertEqual(r.details["price"], 4.99)

    # RevenueOptimization
    def test_create_rev_opt(self):
        r = RevenueOptimization(segment="whales", current_arpu=5.0, target_arpu=10.0)
        self.assertEqual(r.segment, "whales")

    def test_rev_opt_attributes(self):
        r = RevenueOptimization(segment="whales", current_arpu=5.0, target_arpu=10.0)
        self.assertEqual(r.current_arpu, 5.0)

    def test_rev_opt_defaults(self):
        r = RevenueOptimization(segment="whales", current_arpu=5.0, target_arpu=10.0)
        self.assertEqual(r.timeline_days, 30)

    def test_rev_opt_with_values(self):
        r = RevenueOptimization(segment="whales", current_arpu=5.0, target_arpu=10.0, tactics=["a"])
        self.assertIn("a", r.tactics)

    # ExperimentEngine
    def test_create_experiment(self):
        e = ExperimentEngine()
        result = e.create_experiment("H1")
        self.assertIsInstance(result, Experiment)

    def test_run_experiment(self):
        e = ExperimentEngine()
        exp = e.create_experiment("H1")
        result = e.run_experiment(exp.experiment_id)
        self.assertEqual(result.status, "running")

    def test_get_results(self):
        e = ExperimentEngine()
        exp = e.create_experiment("H1")
        result = e.get_results(exp.experiment_id)
        self.assertIsInstance(result, ExperimentResult)

    def test_conclude_experiment(self):
        e = ExperimentEngine()
        exp = e.create_experiment("H1")
        result = e.conclude_experiment(exp.experiment_id)
        self.assertIsInstance(result, ExperimentResult)

    def test_experiment_status(self):
        e = ExperimentEngine()
        exp = e.create_experiment("H1")
        self.assertEqual(exp.status, "created")

    def test_experiment_variants(self):
        e = ExperimentEngine()
        exp = e.create_experiment("H1", variants=["A", "B"])
        self.assertEqual(len(exp.variants), 2)

    # Experiment
    def test_create_experiment(self):
        e = Experiment(experiment_id="e1", hypothesis="H1", status="created", variants=["A"], metric="ctr")
        self.assertEqual(e.experiment_id, "e1")

    def test_experiment_attributes(self):
        e = Experiment(experiment_id="e1", hypothesis="H1", status="created", variants=["A"], metric="ctr")
        self.assertEqual(e.hypothesis, "H1")

    def test_experiment_defaults(self):
        e = Experiment(experiment_id="e1", hypothesis="H1", status="created", variants=["A"], metric="ctr")
        self.assertEqual(e.sample_size, 1000)

    def test_experiment_with_values(self):
        e = Experiment(experiment_id="e1", hypothesis="H1", status="created", variants=["A"], metric="ctr", sample_size=500)
        self.assertEqual(e.sample_size, 500)

    # ExperimentResult
    def test_create_result(self):
        r = ExperimentResult(experiment_id="e1", variant_results={})
        self.assertEqual(r.experiment_id, "e1")

    def test_result_attributes(self):
        r = ExperimentResult(experiment_id="e1", variant_results={})
        self.assertEqual(r.confidence_level, 0.95)

    def test_result_defaults(self):
        r = ExperimentResult(experiment_id="e1", variant_results={})
        self.assertIsNone(r.winner)

    def test_result_with_values(self):
        r = ExperimentResult(experiment_id="e1", variant_results={}, winner="A", is_significant=True)
        self.assertTrue(r.is_significant)

    # GrowthLoop
    def test_detect_issues(self):
        g = GrowthLoop()
        result = g.detect_issues({"dau": 1000, "dau_last_week": 1200, "cpi": 3.0, "cpi_target": 2.0, "arpu": 0.3, "arpu_target": 0.5})
        self.assertIsInstance(result, list)

    def test_detect_issues_dau(self):
        g = GrowthLoop()
        result = g.detect_issues({"dau": 1000, "dau_last_week": 1200})
        self.assertGreater(len(result), 0)

    def test_propose_experiments(self):
        g = GrowthLoop()
        issues = g.detect_issues({"dau": 1000, "dau_last_week": 1200})
        result = g.propose_experiments(issues)
        self.assertIsInstance(result, list)

    def test_propose_experiments_count(self):
        g = GrowthLoop()
        issues = g.detect_issues({"dau": 1000, "dau_last_week": 1200})
        result = g.propose_experiments(issues)
        self.assertEqual(len(result), len(issues))

    def test_execute_experiments(self):
        g = GrowthLoop()
        issues = g.detect_issues({"dau": 1000, "dau_last_week": 1200})
        exps = g.propose_experiments(issues)
        result = g.execute_experiments(exps)
        self.assertIsInstance(result, list)

    def test_learn_and_update(self):
        g = GrowthLoop()
        result = g.learn_and_update([{"experiment_id": "e1", "is_winner": True, "hypothesis": "H1", "category": "retention", "confidence": 0.9}])
        self.assertIsInstance(result, list)

    # GrowthIssue
    def test_create_issue(self):
        i = GrowthIssue(issue_id="i1", category="retention", severity="high", description="DAU drop")
        self.assertEqual(i.issue_id, "i1")

    def test_issue_attributes(self):
        i = GrowthIssue(issue_id="i1", category="retention", severity="high", description="DAU drop")
        self.assertEqual(i.severity, "high")

    def test_issue_defaults(self):
        i = GrowthIssue(issue_id="i1", category="retention", severity="high", description="DAU drop")
        self.assertEqual(i.affected_metrics, [])

    def test_issue_with_values(self):
        i = GrowthIssue(issue_id="i1", category="retention", severity="high", description="DAU drop", affected_metrics=["dau"])
        self.assertIn("dau", i.affected_metrics)

    # GrowthExperiment
    def test_create_growth_exp(self):
        e = GrowthExperiment(experiment_id="e1", issue_id="i1", hypothesis="H1", action="A1", expected_outcome="out")
        self.assertEqual(e.experiment_id, "e1")

    def test_growth_exp_attributes(self):
        e = GrowthExperiment(experiment_id="e1", issue_id="i1", hypothesis="H1", action="A1", expected_outcome="out")
        self.assertEqual(e.hypothesis, "H1")

    def test_growth_exp_defaults(self):
        e = GrowthExperiment(experiment_id="e1", issue_id="i1", hypothesis="H1", action="A1", expected_outcome="out")
        self.assertEqual(e.status, "proposed")

    def test_growth_exp_with_values(self):
        e = GrowthExperiment(experiment_id="e1", issue_id="i1", hypothesis="H1", action="A1", expected_outcome="+5%")
        self.assertEqual(e.expected_outcome, "+5%")

    # GrowthLearning
    def test_create_learning(self):
        l = GrowthLearning(learning_id="l1", experiment_id="e1", insight="I1")
        self.assertEqual(l.learning_id, "l1")

    def test_learning_attributes(self):
        l = GrowthLearning(learning_id="l1", experiment_id="e1", insight="I1")
        self.assertEqual(l.insight, "I1")

    def test_learning_defaults(self):
        l = GrowthLearning(learning_id="l1", experiment_id="e1", insight="I1")
        self.assertEqual(l.confidence, 0.0)

    def test_learning_with_values(self):
        l = GrowthLearning(learning_id="l1", experiment_id="e1", insight="I1", confidence=0.9)
        self.assertEqual(l.confidence, 0.9)


# ---------------------------------------------------------------------------
# company_memory_v2 (~40 tests)
# ---------------------------------------------------------------------------
class TestCompanyMemoryV2(unittest.TestCase):
    # ExperienceMemory
    def test_record_experience(self):
        m = ExperienceMemory()
        r = ExperienceRecord(experience_id="", description="desc", outcome="success")
        result = m.record_experience(r)
        self.assertIsInstance(result, str)

    def test_record_returns_id(self):
        m = ExperienceMemory()
        r = ExperienceRecord(experience_id="", description="desc", outcome="success")
        result = m.record_experience(r)
        self.assertTrue(result.startswith("exp_"))

    def test_get_experiences(self):
        m = ExperienceMemory()
        m.record_experience(ExperienceRecord(experience_id="", description="desc", outcome="success"))
        result = m.get_experiences()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_get_experiences_query(self):
        m = ExperienceMemory()
        m.record_experience(ExperienceRecord(experience_id="", description="hello world", outcome="success"))
        result = m.get_experiences("hello")
        self.assertEqual(len(result), 1)

    def test_get_success_patterns(self):
        m = ExperienceMemory()
        m.record_experience(ExperienceRecord(experience_id="", description="desc", outcome="success"))
        result = m.get_success_patterns()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_get_success_patterns_empty(self):
        m = ExperienceMemory()
        result = m.get_success_patterns()
        self.assertEqual(result, [])

    # ExperienceRecord
    def test_create_record(self):
        r = ExperienceRecord(experience_id="e1", description="desc", outcome="success")
        self.assertEqual(r.experience_id, "e1")

    # ExperienceRecord attributes
    def test_record_description(self):
        r = ExperienceRecord(experience_id="e1", description="desc", outcome="success")
        self.assertEqual(r.description, "desc")

    def test_record_outcome(self):
        r = ExperienceRecord(experience_id="e1", description="desc", outcome="win")
        self.assertEqual(r.outcome, "win")

    def test_record_tags(self):
        r = ExperienceRecord(experience_id="e1", description="desc", outcome="success", tags=["t1"])
        self.assertIn("t1", r.tags)

    def test_record_timestamp(self):
        r = ExperienceRecord(experience_id="e1", description="desc", outcome="success", timestamp="2026-01-01")
        self.assertEqual(r.timestamp, "2026-01-01")

    # FailureMemory
    def test_failure_memory_record(self):
        m = FailureMemory()
        f = FailureRecord(failure_id="", description="d", root_cause="c", impact="high")
        result = m.record_failure(f)
        self.assertIsInstance(result, str)

    def test_failure_memory_record_id(self):
        m = FailureMemory()
        f = FailureRecord(failure_id="", description="d", root_cause="c", impact="high")
        result = m.record_failure(f)
        self.assertTrue(result.startswith("fail_"))

    def test_failure_memory_get_failures(self):
        m = FailureMemory()
        m.record_failure(FailureRecord(failure_id="", description="d", root_cause="c", impact="high"))
        result = m.get_failures()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_failure_memory_get_lessons(self):
        m = FailureMemory()
        m.record_failure(FailureRecord(failure_id="", description="d", root_cause="c", impact="high", lessons=["l1"]))
        result = m.get_lessons()
        self.assertIn("l1", result)

    def test_failure_memory_get_lessons_empty(self):
        m = FailureMemory()
        result = m.get_lessons()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    # FailureRecord
    def test_failure_record_root_cause(self):
        f = FailureRecord(failure_id="f1", description="d", root_cause="c", impact="high")
        self.assertEqual(f.root_cause, "c")

    def test_failure_record_impact(self):
        f = FailureRecord(failure_id="f1", description="d", root_cause="c", impact="low")
        self.assertEqual(f.impact, "low")

    def test_failure_record_lessons(self):
        f = FailureRecord(failure_id="f1", description="d", root_cause="c", impact="high", lessons=["l1", "l2"])
        self.assertEqual(len(f.lessons), 2)

    # StrategyMemory
    def test_strategy_memory_record(self):
        m = StrategyMemory()
        s = MemStrategyRecord(strategy_id="", name="s1", context="ctx", expected_outcome="win")
        result = m.record_strategy(s)
        self.assertIsInstance(result, str)

    def test_strategy_memory_record_id(self):
        m = StrategyMemory()
        s = MemStrategyRecord(strategy_id="", name="s1", context="ctx", expected_outcome="win")
        result = m.record_strategy(s)
        self.assertTrue(result.startswith("strat_"))

    def test_strategy_memory_get_strategies(self):
        m = StrategyMemory()
        m.record_strategy(MemStrategyRecord(strategy_id="", name="s1", context="ctx", expected_outcome="win"))
        result = m.get_strategies()
        self.assertEqual(len(result), 1)

    def test_strategy_memory_get_best_strategy(self):
        m = StrategyMemory()
        m.record_strategy(MemStrategyRecord(strategy_id="", name="s1", context="ua scaling", expected_outcome="win", success_rate=0.9, tags=["ua"]))
        result = m.get_best_strategy("ua")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "s1")

    def test_strategy_memory_get_best_strategy_none(self):
        m = StrategyMemory()
        result = m.get_best_strategy("missing")
        self.assertIsNone(result)

    # StrategyRecord
    def test_mem_strategy_record_name(self):
        s = MemStrategyRecord(strategy_id="s1", name="s1", context="ctx", expected_outcome="win")
        self.assertEqual(s.name, "s1")

    def test_mem_strategy_record_success_rate(self):
        s = MemStrategyRecord(strategy_id="s1", name="s1", context="ctx", expected_outcome="win", success_rate=0.5)
        self.assertEqual(s.success_rate, 0.5)

    def test_mem_strategy_record_tags(self):
        s = MemStrategyRecord(strategy_id="s1", name="s1", context="ctx", expected_outcome="win", tags=["t1"])
        self.assertIn("t1", s.tags)

    # CompetitorMemory
    def test_competitor_memory_record(self):
        m = CompetitorMemory()
        c = CompetitorRecord(name="CompA", market_share=0.1)
        m.record_competitor("CompA", c)
        self.assertEqual(len(m.get_all_competitors()), 1)

    def test_competitor_memory_get_competitor(self):
        m = CompetitorMemory()
        c = CompetitorRecord(name="CompA", market_share=0.1)
        m.record_competitor("CompA", c)
        result = m.get_competitor("CompA")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "CompA")

    def test_competitor_memory_get_all(self):
        m = CompetitorMemory()
        m.record_competitor("A", CompetitorRecord(name="A", market_share=0.1))
        m.record_competitor("B", CompetitorRecord(name="B", market_share=0.2))
        result = m.get_all_competitors()
        self.assertEqual(len(result), 2)

    # CompetitorRecord
    def test_competitor_record_market_share(self):
        c = CompetitorRecord(name="C1", market_share=0.25)
        self.assertEqual(c.market_share, 0.25)

    def test_competitor_record_strengths(self):
        c = CompetitorRecord(name="C1", market_share=0.1, strengths=["s1"])
        self.assertIn("s1", c.strengths)

    def test_competitor_record_weaknesses(self):
        c = CompetitorRecord(name="C1", market_share=0.1, weaknesses=["w1"])
        self.assertIn("w1", c.weaknesses)

    def test_competitor_record_last_updated(self):
        c = CompetitorRecord(name="C1", market_share=0.1, last_updated="2026-01-01")
        self.assertEqual(c.last_updated, "2026-01-01")

    # CausalMemory
    def test_causal_memory_record(self):
        m = CausalMemory()
        m.record_cause_effect("a", "b", 0.8)
        self.assertEqual(len(m.find_causes("b")), 1)

    def test_causal_memory_find_causes(self):
        m = CausalMemory()
        m.record_cause_effect("x", "y", 0.5)
        result = m.find_causes("y")
        self.assertIsInstance(result, list)

    def test_causal_memory_find_effects(self):
        m = CausalMemory()
        m.record_cause_effect("x", "y", 0.5)
        result = m.find_effects("x")
        self.assertIsInstance(result, list)

    def test_causal_memory_get_causal_chain(self):
        m = CausalMemory()
        m.record_cause_effect("a", "b", 0.8)
        m.record_cause_effect("b", "c", 0.9)
        result = m.get_causal_chain("a")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_causal_memory_strength_clamped(self):
        m = CausalMemory()
        m.record_cause_effect("a", "b", 1.5)
        result = m.find_causes("b")[0]
        self.assertEqual(result.strength, 1.0)

    # CausalLink
    def test_causal_link_create(self):
        link = CausalLink(cause="a", effect="b", strength=0.5)
        self.assertEqual(link.cause, "a")
        self.assertEqual(link.effect, "b")

    def test_causal_link_strength(self):
        link = CausalLink(cause="a", effect="b", strength=0.3)
        self.assertEqual(link.strength, 0.3)


# ---------------------------------------------------------------------------
# autonomous_research (~100 tests)
# ---------------------------------------------------------------------------
class TestAutonomousResearch(unittest.TestCase):
    # PaperReader
    def test_read_paper_returns_summary(self):
        pr = PaperReader()
        paper = {"title": "Test", "authors": ["A"], "abstract": "abs"}
        result = pr.read_paper(paper)
        self.assertIsInstance(result, PaperSummary)

    def test_read_paper_title(self):
        pr = PaperReader()
        result = pr.read_paper({"title": "My Paper", "authors": [], "abstract": ""})
        self.assertEqual(result.title, "My Paper")

    def test_summarize_returns_list(self):
        pr = PaperReader()
        pr.read_paper({"title": "T", "authors": [], "abstract": ""})
        result = pr.summarize()
        self.assertIsInstance(result, list)

    def test_extract_insights_returns_list(self):
        pr = PaperReader()
        result = pr.extract_insights()
        self.assertIsInstance(result, list)

    def test_get_key_findings_returns_list(self):
        pr = PaperReader()
        result = pr.get_key_findings()
        self.assertIsInstance(result, list)

    # PaperSummary
    def test_paper_summary_authors(self):
        ps = PaperSummary(title="t", authors=["a1", "a2"], abstract="abs")
        self.assertEqual(len(ps.authors), 2)

    def test_paper_summary_key_points(self):
        ps = PaperSummary(title="t", authors=[], abstract="abs", key_points=["p1"])
        self.assertIn("p1", ps.key_points)

    def test_paper_summary_publication_date(self):
        ps = PaperSummary(title="t", authors=[], abstract="abs", publication_date=datetime.now())
        self.assertIsNotNone(ps.publication_date)

    def test_paper_summary_doi(self):
        ps = PaperSummary(title="t", authors=[], abstract="abs", doi="10.1234")
        self.assertEqual(ps.doi, "10.1234")

    # ResearchInsight
    def test_research_insight_topic(self):
        ri = ResearchInsight(topic="AI", finding="f")
        self.assertEqual(ri.topic, "AI")

    def test_research_insight_confidence(self):
        ri = ResearchInsight(topic="AI", finding="f", confidence=0.8)
        self.assertEqual(ri.confidence, 0.8)

    def test_research_insight_action_items(self):
        ri = ResearchInsight(topic="AI", finding="f", action_items=["a1"])
        self.assertIn("a1", ri.action_items)

    # MarketReporter
    def test_generate_daily_report(self):
        mr = MarketReporter()
        result = mr.generate_daily_report()
        self.assertIsInstance(result, MarketReport)

    def test_generate_daily_report_type(self):
        mr = MarketReporter()
        result = mr.generate_daily_report()
        self.assertEqual(result.report_type, "daily")

    def test_generate_weekly_report(self):
        mr = MarketReporter()
        result = mr.generate_weekly_report()
        self.assertIsInstance(result, MarketReport)

    def test_generate_weekly_report_type(self):
        mr = MarketReporter()
        result = mr.generate_weekly_report()
        self.assertEqual(result.report_type, "weekly")

    def test_get_market_updates(self):
        mr = MarketReporter()
        result = mr.get_market_updates()
        self.assertIsInstance(result, list)

    def test_get_market_updates_count(self):
        mr = MarketReporter()
        result = mr.get_market_updates()
        self.assertGreater(len(result), 0)

    def test_get_key_metrics(self):
        mr = MarketReporter()
        result = mr.get_key_metrics()
        self.assertIsInstance(result, dict)

    def test_get_key_metrics_has_revenue(self):
        mr = MarketReporter()
        result = mr.get_key_metrics()
        self.assertIn("global_gaming_revenue_usd_b", result)

    # MarketReport
    def test_market_report_highlights(self):
        mr = MarketReporter()
        r = mr.generate_daily_report()
        self.assertIsInstance(r.highlights, list)

    def test_market_report_updates(self):
        mr = MarketReporter()
        r = mr.generate_daily_report()
        self.assertIsInstance(r.updates, list)

    def test_market_report_key_metrics(self):
        mr = MarketReporter()
        r = mr.generate_daily_report()
        self.assertIsInstance(r.key_metrics, dict)

    def test_market_report_generated_at(self):
        mr = MarketReporter()
        r = mr.generate_daily_report()
        self.assertIsInstance(r.generated_at, datetime)

    # MarketUpdate
    def test_market_update_headline(self):
        mu = MarketUpdate(headline="H", category="c", summary="s", source="src")
        self.assertEqual(mu.headline, "H")

    def test_market_update_impact(self):
        mu = MarketUpdate(headline="H", category="c", summary="s", source="src", impact="positive")
        self.assertEqual(mu.impact, "positive")

    def test_market_update_related_tickers(self):
        mu = MarketUpdate(headline="H", category="c", summary="s", source="src", related_tickers=["AAPL"])
        self.assertIn("AAPL", mu.related_tickers)

    def test_market_update_timestamp(self):
        mu = MarketUpdate(headline="H", category="c", summary="s", source="src")
        self.assertIsInstance(mu.timestamp, datetime)

    # CompetitorWatcher
    def test_watch_returns_analysis(self):
        cw = CompetitorWatcher()
        result = cw.watch("Rival")
        self.assertIsInstance(result, CompetitorAnalysis)

    def test_watch_adds_watched(self):
        cw = CompetitorWatcher()
        cw.watch("Rival")
        self.assertEqual(len(cw._watched), 1)

    def test_get_latest_moves(self):
        cw = CompetitorWatcher()
        result = cw.get_latest_moves()
        self.assertIsInstance(result, list)

    def test_get_latest_moves_count(self):
        cw = CompetitorWatcher()
        result = cw.get_latest_moves()
        self.assertGreater(len(result), 0)

    def test_analyze_strategy_existing(self):
        cw = CompetitorWatcher()
        cw.watch("Rival")
        result = cw.analyze_strategy("Rival")
        self.assertIsInstance(result, CompetitorAnalysis)

    def test_analyze_strategy_new(self):
        cw = CompetitorWatcher()
        result = cw.analyze_strategy("Unknown")
        self.assertIsInstance(result, CompetitorAnalysis)

    def test_get_threat_level(self):
        cw = CompetitorWatcher()
        result = cw.get_threat_level("Rival")
        self.assertIsInstance(result, ThreatLevel)

    # CompetitorMove
    def test_competitor_move_competitor(self):
        cm = CompetitorMove(competitor="C", action="a", description="d")
        self.assertEqual(cm.competitor, "C")

    def test_competitor_move_category(self):
        cm = CompetitorMove(competitor="C", action="a", description="d", category="product")
        self.assertEqual(cm.category, "product")

    def test_competitor_move_expected_impact(self):
        cm = CompetitorMove(competitor="C", action="a", description="d", expected_impact="high")
        self.assertEqual(cm.expected_impact, "high")

    # CompetitorAnalysis
    def test_competitor_analysis_threat_level(self):
        ca = CompetitorAnalysis(competitor="C", threat_level=ThreatLevel.HIGH)
        self.assertEqual(ca.threat_level, ThreatLevel.HIGH)

    def test_competitor_analysis_strengths(self):
        ca = CompetitorAnalysis(competitor="C", threat_level=ThreatLevel.LOW, strengths=["s1"])
        self.assertIn("s1", ca.strengths)

    def test_competitor_analysis_recommended_response(self):
        ca = CompetitorAnalysis(competitor="C", threat_level=ThreatLevel.LOW, recommended_response="monitor")
        self.assertEqual(ca.recommended_response, "monitor")

    # ThreatLevel
    def test_threat_level_low(self):
        self.assertEqual(ThreatLevel.LOW.value, "low")

    def test_threat_level_critical(self):
        self.assertEqual(ThreatLevel.CRITICAL.value, "critical")

    # TechnologyTracker
    def test_track_technology(self):
        tt = TechnologyTracker()
        result = tt.track_technology("AI")
        self.assertIsInstance(result, TechTrend)

    def test_track_technology_name(self):
        tt = TechnologyTracker()
        result = tt.track_technology("AI")
        self.assertEqual(result.technology, "AI")

    def test_get_tech_trends(self):
        tt = TechnologyTracker()
        result = tt.get_tech_trends()
        self.assertIsInstance(result, list)

    def test_get_tech_trends_count(self):
        tt = TechnologyTracker()
        result = tt.get_tech_trends()
        self.assertGreater(len(result), 0)

    def test_assess_impact(self):
        tt = TechnologyTracker()
        result = tt.assess_impact("AI")
        self.assertIsInstance(result, TechAssessment)

    def test_assess_impact_technology(self):
        tt = TechnologyTracker()
        result = tt.assess_impact("AI")
        self.assertEqual(result.technology, "AI")

    def test_get_recommendations(self):
        tt = TechnologyTracker()
        result = tt.get_recommendations()
        self.assertIsInstance(result, list)

    def test_get_recommendations_count(self):
        tt = TechnologyTracker()
        result = tt.get_recommendations()
        self.assertGreater(len(result), 0)

    # TechTrend
    def test_tech_trend_direction(self):
        tt = TechTrend(technology="t", trend_direction="rising", maturity="early")
        self.assertEqual(tt.trend_direction, "rising")

    def test_tech_trend_adoption_rate(self):
        tt = TechTrend(technology="t", trend_direction="rising", maturity="early", adoption_rate=0.5)
        self.assertEqual(tt.adoption_rate, 0.5)

    def test_tech_trend_key_players(self):
        tt = TechTrend(technology="t", trend_direction="rising", maturity="early", key_players=["p1"])
        self.assertIn("p1", tt.key_players)

    # TechAssessment
    def test_tech_assessment_impact_level(self):
        ta = TechAssessment(technology="t", impact_level=ImpactLevel.SIGNIFICANT)
        self.assertEqual(ta.impact_level, ImpactLevel.SIGNIFICANT)

    def test_tech_assessment_investment_recommended(self):
        ta = TechAssessment(technology="t", impact_level=ImpactLevel.MODERATE, investment_recommended=True)
        self.assertTrue(ta.investment_recommended)

    def test_tech_assessment_overall_score(self):
        ta = TechAssessment(technology="t", impact_level=ImpactLevel.MINIMAL, overall_score=5.0)
        self.assertEqual(ta.overall_score, 5.0)

    # ImpactLevel
    def test_impact_level_minimal(self):
        self.assertEqual(ImpactLevel.MINIMAL.value, "minimal")

    def test_impact_level_transformative(self):
        self.assertEqual(ImpactLevel.TRANSFORMATIVE.value, "transformative")

    # ReportGenerator
    def test_generate_ceo_report(self):
        rg = ReportGenerator()
        result = rg.generate_ceo_report()
        self.assertIsInstance(result, CEOReport)

    def test_generate_ceo_report_title(self):
        rg = ReportGenerator()
        result = rg.generate_ceo_report()
        self.assertEqual(result.title, "Weekly Executive Intelligence Brief")

    def test_generate_strategy_report(self):
        rg = ReportGenerator()
        result = rg.generate_strategy_report()
        self.assertIsInstance(result, StrategyReport)

    def test_generate_strategy_report_period(self):
        rg = ReportGenerator()
        result = rg.generate_strategy_report()
        self.assertEqual(result.period, "Q2 2026")

    def test_generate_risk_report(self):
        rg = ReportGenerator()
        result = rg.generate_risk_report()
        self.assertIsInstance(result, RiskReport)

    def test_generate_risk_report_overall_risk(self):
        rg = ReportGenerator()
        result = rg.generate_risk_report()
        self.assertEqual(result.overall_risk_level, "medium")

    def test_get_all_reports(self):
        rg = ReportGenerator()
        rg.generate_ceo_report()
        result = rg.get_all_reports()
        self.assertIsInstance(result, dict)

    def test_get_all_reports_has_ceo(self):
        rg = ReportGenerator()
        rg.generate_ceo_report()
        result = rg.get_all_reports()
        self.assertIn("ceo", result)

    # CEOReport
    def test_ceo_report_top_priorities(self):
        rg = ReportGenerator()
        r = rg.generate_ceo_report()
        self.assertIsInstance(r.top_priorities, list)

    def test_ceo_report_financial_snapshot(self):
        rg = ReportGenerator()
        r = rg.generate_ceo_report()
        self.assertIsInstance(r.financial_snapshot, dict)

    def test_ceo_report_generated_at(self):
        rg = ReportGenerator()
        r = rg.generate_ceo_report()
        self.assertIsInstance(r.generated_at, datetime)

    # StrategyReport
    def test_strategy_report_market_opportunities(self):
        rg = ReportGenerator()
        r = rg.generate_strategy_report()
        self.assertIsInstance(r.market_opportunities, list)

    def test_strategy_report_long_term_outlook(self):
        rg = ReportGenerator()
        r = rg.generate_strategy_report()
        self.assertIsInstance(r.long_term_outlook, str)

    # RiskReport
    def test_risk_report_risk_categories(self):
        rg = ReportGenerator()
        r = rg.generate_risk_report()
        self.assertIsInstance(r.risk_categories, dict)

    def test_risk_report_top_risks(self):
        rg = ReportGenerator()
        r = rg.generate_risk_report()
        self.assertIsInstance(r.top_risks, list)

    def test_risk_report_mitigation_strategies(self):
        rg = ReportGenerator()
        r = rg.generate_risk_report()
        self.assertIsInstance(r.mitigation_strategies, list)


def count_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    total = 0
    for test_suite in suite:
        for test_case in test_suite:
            total += 1
    return total


if __name__ == "__main__":
    print("=" * 80)
    print("V7.0 Intelligence Layer - Release Gate")
    print("=" * 80)
    
    total_tests = count_tests()
    print(f"\nTotal test cases: {total_tests}")
    print()
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]))
    
    print("\n" + "=" * 80)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Results: {passed}/{result.testsRun} PASS")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped)}")
    print("=" * 80)
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
            print(f"    {traceback.split(chr(10))[0]}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
            print(f"    {traceback.split(chr(10))[0]}")
    
    print(f"\nStatus: {'PASS' if result.wasSuccessful() else 'FAIL'}")
    
    sys.exit(0 if result.wasSuccessful() else 1)

