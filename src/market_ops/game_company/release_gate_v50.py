import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import Mock, patch

from company_os import CEOBrain, CompanyGoal, ResourceAllocator, DecisionBoard, CompanyMemory
from market_discovery import TrendScanner, CompetitorAnalyzer, KeywordMiner, MarketGapDetector, OpportunityScore
from product_agent import ConceptGenerator, GDDBuilder, MechanicDesigner, EconomyDesigner, RetentionPredictor, FeaturePlanner
from development_agent import UnityAgent, CodeGenerator, AssetGenerator, BuildManager, QAAgent
from monetization_agent import IAPOptimizer, AdOptimizer, EconomySimulator, OfferGenerator, PricingAgent
from creative_factory import VideoGenerator, ScreenshotGenerator, IconGenerator, CreativeEvaluator, CreativeEvolution
from company_simulator import UserSimulator, EconomySimulator as CompanyEconomySimulator, UASimulator, RevenueForecast, RiskEngine
from launch_agent import BuildPipeline, StoreSubmitter, ASOOptimizer, UALauncher, LaunchMonitor
from autonomous_learning import FailureAnalysis, StrategyEvolution, CompanyMemory as LearningCompanyMemory, MetaLearning


class TestCompanyOS(unittest.TestCase):
    def test_ceo_brain_make_strategy(self):
        ceo = CEOBrain()
        context = {
            "target_arr": 10_000_000,
            "timeline": 12,
            "resources": {"developers": 2, "ua_budget": 5000},
            "existing_data": {"p04": True},
        }
        strategy = ceo.make_strategy(context)
        self.assertIsNotNone(strategy)
        self.assertTrue(len(strategy.projects) > 0)

    def test_ceo_brain_make_strategy_with_arr_5m(self):
        ceo = CEOBrain()
        context = {"target_arr": 5_000_000, "timeline": 12}
        strategy = ceo.make_strategy(context)
        self.assertIsNotNone(strategy)

    def test_ceo_brain_make_strategy_no_data(self):
        ceo = CEOBrain()
        context = {"target_arr": 10_000_000}
        strategy = ceo.make_strategy(context)
        self.assertIsNotNone(strategy)

    def test_company_goal_set_goal(self):
        goal = CompanyGoal()
        result = goal.set_goal(10_000_000, 12)
        self.assertEqual(result.target_arr, 10_000_000)
        self.assertEqual(result.timeline_months, 12)

    def test_company_goal_set_goal_short_timeline(self):
        goal = CompanyGoal()
        result = goal.set_goal(10_000_000, 6)
        self.assertEqual(result.timeline_months, 6)

    def test_company_goal_set_goal_large_arr(self):
        goal = CompanyGoal()
        result = goal.set_goal(100_000_000, 24)
        self.assertEqual(result.target_arr, 100_000_000)

    def test_company_goal_track_progress(self):
        goal = CompanyGoal()
        goal.set_goal(10_000_000, 12)
        progress = goal.track_progress(5_000_000, 6)
        self.assertEqual(progress.current_arr, 5_000_000)
        self.assertEqual(progress.months_completed, 6)

    def test_resource_allocator_allocate(self):
        allocator = ResourceAllocator()
        projects = [{"name": "Project A"}, {"name": "Project B"}]
        resources = {"developers": 4, "budget": 100000}
        allocation = allocator.allocate(projects, resources)
        self.assertTrue(len(allocation.allocations) == 2)

    def test_resource_allocator_allocate_imbalanced(self):
        allocator = ResourceAllocator()
        projects = [{"name": "P1", "priority": "high"}, {"name": "P2", "priority": "low"}]
        resources = {"developers": 3}
        allocation = allocator.allocate(projects, resources)
        self.assertIsNotNone(allocation)

    def test_resource_allocator_allocate_no_budget(self):
        allocator = ResourceAllocator()
        projects = [{"name": "Project A"}]
        resources = {"developers": 1}
        allocation = allocator.allocate(projects, resources)
        self.assertIsNotNone(allocation)

    def test_decision_board_resolve(self):
        board = DecisionBoard()
        conflict = {"issue": "resource_allocation", "options": ["A", "B"], "context": {}}
        consensus = board.resolve(conflict)
        self.assertIsNotNone(consensus)
        self.assertTrue(len(consensus.decision) > 0)

    def test_decision_board_resolve_different_issue(self):
        board = DecisionBoard()
        conflict = {"issue": "project_priority", "options": ["High", "Low"], "context": {}}
        consensus = board.resolve(conflict)
        self.assertIsNotNone(consensus)

    def test_decision_board_resolve_unknown_issue(self):
        board = DecisionBoard()
        conflict = {"issue": "unknown", "options": ["X", "Y"], "context": {}}
        consensus = board.resolve(conflict)
        self.assertIsNotNone(consensus)

    def test_company_memory_store(self):
        mem = CompanyMemory()
        entry = mem.store("strategy", {"id": "s1", "name": "Strategy A"}, 0.8)
        self.assertEqual(entry.type, "strategy")
        self.assertEqual(entry.importance, 0.8)

    def test_company_memory_store_success(self):
        mem = CompanyMemory()
        entry = mem.store("success", {"project": "Game X"}, 0.9)
        self.assertEqual(entry.type, "success")

    def test_company_memory_store_failure(self):
        mem = CompanyMemory()
        entry = mem.store("failure", {"project": "Game Y"}, 0.7)
        self.assertEqual(entry.type, "failure")

    def test_company_memory_retrieve(self):
        mem = CompanyMemory()
        mem.store("strategy", {"id": "s1"})
        mem.store("success", {"id": "s2"})
        entries = mem.retrieve()
        self.assertTrue(len(entries) >= 2)

    def test_company_memory_retrieve_type(self):
        mem = CompanyMemory()
        mem.store("strategy", {"id": "s1"})
        mem.store("success", {"id": "s2"})
        strategies = mem.retrieve("strategy")
        self.assertTrue(len(strategies) >= 1)


class TestMarketDiscovery(unittest.TestCase):
    def test_trend_scanner_scan(self):
        scanner = TrendScanner()
        trends = scanner.scan(["app_store"])
        self.assertTrue(len(trends) > 0)

    def test_trend_scanner_scan_all(self):
        scanner = TrendScanner()
        trends = scanner.scan()
        self.assertTrue(len(trends) >= 5)

    def test_trend_scanner_scan_meta(self):
        scanner = TrendScanner()
        trends = scanner.scan(["meta_ads"])
        self.assertTrue(len(trends) > 0)

    def test_trend_scanner_scan_tiktok(self):
        scanner = TrendScanner()
        trends = scanner.scan(["tiktok"])
        self.assertTrue(len(trends) > 0)

    def test_trend_scanner_get_trends(self):
        scanner = TrendScanner()
        scanner.scan(["app_store"])
        all_trends = scanner.get_trends()
        self.assertTrue(len(all_trends) > 0)

    def test_trend_scanner_get_trends_by_type(self):
        scanner = TrendScanner()
        scanner.scan(["app_store"])
        trends = scanner.get_trends_by_type("merge")
        self.assertIsInstance(trends, list)

    def test_competitor_analyzer_analyze(self):
        analyzer = CompetitorAnalyzer()
        result = analyzer.analyze("Merge Game", ["US"])
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_competitor_analyzer_analyze_europe(self):
        analyzer = CompetitorAnalyzer()
        result = analyzer.analyze("Match 3", ["DE", "FR"])
        self.assertIsNotNone(result)

    def test_competitor_analyzer_get_competitors(self):
        analyzer = CompetitorAnalyzer()
        analyzer.analyze("Merge Game", ["US"])
        competitors = analyzer.get_competitors("Merge Game")
        self.assertIsInstance(competitors, list)

    def test_keyword_miner_mine(self):
        miner = KeywordMiner()
        keywords = miner.mine("merge puzzle", ["US"])
        self.assertTrue(len(keywords) > 0)

    def test_keyword_miner_mine_japan(self):
        miner = KeywordMiner()
        keywords = miner.mine("puzzle", ["JP"])
        self.assertTrue(len(keywords) > 0)

    def test_keyword_miner_mine_de(self):
        miner = KeywordMiner()
        keywords = miner.mine("match", ["DE"])
        self.assertTrue(len(keywords) > 0)

    def test_keyword_miner_get_keywords(self):
        miner = KeywordMiner()
        miner.mine("merge", ["US"])
        keywords = miner.get_keywords("merge")
        self.assertIsInstance(keywords, list)

    def test_market_gap_detector_detect(self):
        detector = MarketGapDetector()
        opportunities = detector.detect(["merge", "decoration"])
        self.assertTrue(len(opportunities) > 0)

    def test_market_gap_detector_detect_simulation(self):
        detector = MarketGapDetector()
        opportunities = detector.detect(["simulation", "city"])
        self.assertTrue(len(opportunities) > 0)

    def test_market_gap_detector_detect_arcade(self):
        detector = MarketGapDetector()
        opportunities = detector.detect(["arcade", "runner"])
        self.assertTrue(len(opportunities) > 0)

    def test_opportunity_score_score(self):
        scorer = OpportunityScore()
        opportunity = {
            "genre": "Merge",
            "region": "US",
            "competition": "medium",
            "keyword_gap": "high",
            "trend_score": 85,
        }
        result = scorer.score(opportunity)
        self.assertTrue(result.opportunity_score >= 60)
        self.assertTrue(result.opportunity_score <= 100)

    def test_opportunity_score_score_high_competition(self):
        scorer = OpportunityScore()
        opportunity = {"competition": "high", "keyword_gap": "low", "trend_score": 50}
        result = scorer.score(opportunity)
        self.assertTrue(result.opportunity_score >= 0)

    def test_opportunity_score_score_perfect(self):
        scorer = OpportunityScore()
        opportunity = {"competition": "low", "keyword_gap": "high", "trend_score": 95}
        result = scorer.score(opportunity)
        self.assertTrue(result.opportunity_score >= 80)

    def test_opportunity_score_ranked(self):
        scorer = OpportunityScore()
        opps = [
            {"genre": "A", "competition": "medium", "keyword_gap": "high", "trend_score": 85},
            {"genre": "B", "competition": "high", "keyword_gap": "low", "trend_score": 60},
        ]
        ranked = scorer.rank(opps)
        self.assertTrue(ranked[0].opportunity_score >= ranked[1].opportunity_score)


class TestProductAgent(unittest.TestCase):
    def test_concept_generator_generate(self):
        generator = ConceptGenerator()
        opportunity = {"genre": "Merge", "audience": "Female 25-44", "opportunity_score": 87}
        concept = generator.generate(opportunity)
        self.assertIsNotNone(concept)
        self.assertTrue(len(concept.name) > 0)

    def test_concept_generator_generate_simulation(self):
        generator = ConceptGenerator()
        opportunity = {"genre": "Simulation", "audience": "Male 18-34"}
        concept = generator.generate(opportunity)
        self.assertIsNotNone(concept)

    def test_concept_generator_generate_decoration(self):
        generator = ConceptGenerator()
        opportunity = {"genre": "Decoration", "opportunity_score": 90}
        concept = generator.generate(opportunity)
        self.assertIsNotNone(concept)

    def test_concept_generator_generate_low_score(self):
        generator = ConceptGenerator()
        opportunity = {"genre": "Match 3", "opportunity_score": 40}
        concept = generator.generate(opportunity)
        self.assertIsNotNone(concept)

    def test_gdd_builder_build(self):
        builder = GDDBuilder()
        concept = {"name": "Test Game", "genre": "Merge", "core_loop": ["Play", "Win", "Repeat"]}
        gdd = builder.build(concept)
        self.assertIsNotNone(gdd)
        self.assertTrue(len(gdd.game_name) > 0)

    def test_gdd_builder_build_simulation(self):
        builder = GDDBuilder()
        concept = {"name": "City Builder", "genre": "Simulation", "core_loop": ["Build", "Manage", "Expand"]}
        gdd = builder.build(concept)
        self.assertIsNotNone(gdd)

    def test_gdd_builder_build_empty(self):
        builder = GDDBuilder()
        concept = {"name": "Game"}
        gdd = builder.build(concept)
        self.assertIsNotNone(gdd)

    def test_mechanic_designer_design(self):
        designer = MechanicDesigner()
        mechanics = designer.design("Merge")
        self.assertTrue(len(mechanics) > 0)

    def test_mechanic_designer_design_match3(self):
        designer = MechanicDesigner()
        mechanics = designer.design("Match 3")
        self.assertTrue(len(mechanics) > 0)

    def test_mechanic_designer_design_simulation(self):
        designer = MechanicDesigner()
        mechanics = designer.design("Simulation")
        self.assertTrue(len(mechanics) > 0)

    def test_economy_designer_design(self):
        designer = EconomyDesigner()
        economy = designer.design("Merge")
        self.assertIsNotNone(economy)

    def test_economy_designer_design_with_params(self):
        designer = EconomyDesigner()
        economy = designer.design("Merge", target_arpdau=0.2)
        self.assertIsNotNone(economy)

    def test_economy_designer_design_simulation(self):
        designer = EconomyDesigner()
        economy = designer.design("Simulation")
        self.assertIsNotNone(economy)

    def test_retention_predictor_predict(self):
        predictor = RetentionPredictor()
        prediction = predictor.predict("Merge")
        self.assertIsNotNone(prediction)
        self.assertTrue(prediction.d1 >= 0)
        self.assertTrue(prediction.d30 <= 1)

    def test_retention_predictor_predict_match3(self):
        predictor = RetentionPredictor()
        prediction = predictor.predict("Match 3")
        self.assertIsNotNone(prediction)

    def test_retention_predictor_predict_simulation(self):
        predictor = RetentionPredictor()
        prediction = predictor.predict("Simulation")
        self.assertIsNotNone(prediction)

    def test_retention_predictor_predict_custom(self):
        predictor = RetentionPredictor()
        prediction = predictor.predict("Arcade", features=["social", "progression"])
        self.assertIsNotNone(prediction)

    def test_feature_planner_plan(self):
        planner = FeaturePlanner()
        features = planner.plan("Merge", ["core", "retention"])
        self.assertTrue(len(features.features) > 0)

    def test_feature_planner_plan_full(self):
        planner = FeaturePlanner()
        features = planner.plan("Merge", ["core", "retention", "monetization", "social"])
        self.assertTrue(len(features.features) >= 4)

    def test_feature_planner_plan_simulation(self):
        planner = FeaturePlanner()
        features = planner.plan("Simulation", ["core"])
        self.assertTrue(len(features.features) > 0)


class TestDevelopmentAgent(unittest.TestCase):
    def test_unity_agent_create_project(self):
        agent = UnityAgent()
        gdd = {"game_name": "Test Game", "genre": "Merge"}
        project = agent.create_project(gdd)
        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Test Game")

    def test_unity_agent_create_project_simulation(self):
        agent = UnityAgent()
        gdd = {"game_name": "City Game", "genre": "Simulation"}
        project = agent.create_project(gdd)
        self.assertIsNotNone(project)

    def test_unity_agent_create_project_object(self):
        agent = UnityAgent()
        class MockGDD:
            game_name = "Mock Game"
            genre = "Match 3"
        project = agent.create_project(MockGDD())
        self.assertIsNotNone(project)

    def test_code_generator_generate(self):
        generator = CodeGenerator()
        code = generator.generate("Merge")
        self.assertTrue(len(code.code) > 0)

    def test_code_generator_generate_simulation(self):
        generator = CodeGenerator()
        code = generator.generate("Simulation")
        self.assertTrue(len(code.code) > 0)

    def test_code_generator_generate_multiple(self):
        generator = CodeGenerator()
        code = generator.generate("Merge", count=5)
        self.assertEqual(len(code), 5)

    def test_asset_generator_generate(self):
        generator = AssetGenerator()
        assets = generator.generate("Merge", ["sprites", "ui"])
        self.assertTrue(len(assets) > 0)

    def test_asset_generator_generate_full(self):
        generator = AssetGenerator()
        assets = generator.generate("Merge", ["sprites", "ui", "audio", "particles"])
        self.assertTrue(len(assets) >= 4)

    def test_asset_generator_generate_simulation(self):
        generator = AssetGenerator()
        assets = generator.generate("Simulation", ["buildings"])
        self.assertTrue(len(assets) > 0)

    def test_build_manager_build(self):
        manager = BuildManager()
        project = {"name": "Test", "scenes": ["Main"], "scripts": ["a", "b"]}
        build = manager.build(project, "android")
        self.assertIsNotNone(build)

    def test_build_manager_build_ios(self):
        manager = BuildManager()
        project = {"name": "Test", "scenes": ["Main"]}
        build = manager.build(project, "ios")
        self.assertIsNotNone(build)

    def test_build_manager_build_all(self):
        manager = BuildManager()
        project = {"name": "Test"}
        builds = manager.build_all(project)
        self.assertEqual(len(builds), 2)

    def test_qa_agent_test(self):
        agent = QAAgent()
        project = {"name": "Test"}
        report = agent.test(project)
        self.assertIsNotNone(report)

    def test_qa_agent_test_with_issues(self):
        agent = QAAgent()
        project = {"name": "Test", "known_issues": ["Crash on start"]}
        report = agent.test(project)
        self.assertIsNotNone(report)

    def test_qa_agent_test_full(self):
        agent = QAAgent()
        project = {"name": "Test"}
        report = agent.test_full(project)
        self.assertIsNotNone(report)


class TestMonetizationAgent(unittest.TestCase):
    def test_iap_optimizer_optimize(self):
        optimizer = IAPOptimizer()
        products = optimizer.optimize("Merge")
        self.assertTrue(len(products.products) > 0)

    def test_iap_optimizer_optimize_simulation(self):
        optimizer = IAPOptimizer()
        products = optimizer.optimize("Simulation")
        self.assertTrue(len(products.products) > 0)

    def test_iap_optimizer_optimize_custom(self):
        optimizer = IAPOptimizer()
        products = optimizer.optimize("Merge", target_ltv=5.0)
        self.assertTrue(len(products.products) > 0)

    def test_ad_optimizer_optimize(self):
        optimizer = AdOptimizer()
        config = optimizer.optimize("Merge")
        self.assertIsNotNone(config)

    def test_ad_optimizer_optimize_simulation(self):
        optimizer = AdOptimizer()
        config = optimizer.optimize("Simulation")
        self.assertIsNotNone(config)

    def test_ad_optimizer_optimize_high_retention(self):
        optimizer = AdOptimizer()
        config = optimizer.optimize("Merge", retention_score=0.8)
        self.assertIsNotNone(config)

    def test_economy_simulator_simulate(self):
        simulator = EconomySimulator()
        game_data = {"d30": 0.09, "arpdau": 0.15, "cpi": 2.5}
        result = simulator.simulate(game_data, 50000)
        self.assertIsNotNone(result)
        self.assertTrue(result.total_revenue > 0)

    def test_economy_simulator_simulate_high_budget(self):
        simulator = EconomySimulator()
        game_data = {"d30": 0.1, "arpdau": 0.2}
        result = simulator.simulate(game_data, 100000)
        self.assertTrue(result.total_revenue > 0)

    def test_economy_simulator_simulate_low_retention(self):
        simulator = EconomySimulator()
        game_data = {"d30": 0.03, "arpdau": 0.05}
        result = simulator.simulate(game_data, 50000)
        self.assertIsNotNone(result)

    def test_offer_generator_generate(self):
        generator = OfferGenerator()
        offers = generator.generate("Merge")
        self.assertTrue(len(offers) > 0)

    def test_offer_generator_generate_event(self):
        generator = OfferGenerator()
        offers = generator.generate_event("Merge", "Christmas")
        self.assertTrue(len(offers) > 0)

    def test_offer_generator_generate_anniversary(self):
        generator = OfferGenerator()
        offers = generator.generate_event("Merge", "Anniversary")
        self.assertTrue(len(offers) > 0)

    def test_pricing_agent_price(self):
        agent = PricingAgent()
        prices = agent.price("Merge", ["US", "JP", "DE"])
        self.assertTrue(len(prices) > 0)

    def test_pricing_agent_price_single(self):
        agent = PricingAgent()
        prices = agent.price("Merge", ["US"])
        self.assertTrue(len(prices) >= 1)

    def test_pricing_agent_price_emerging(self):
        agent = PricingAgent()
        prices = agent.price("Merge", ["BR", "IN"])
        self.assertTrue(len(prices) >= 1)


class TestCreativeFactory(unittest.TestCase):
    def test_video_generator_generate(self):
        generator = VideoGenerator()
        concept = {"name": "Test Game", "genre": "Merge", "core_loop": ["Merge", "Reward"]}
        videos = generator.generate(concept, 3)
        self.assertEqual(len(videos), 3)

    def test_video_generator_generate_single(self):
        generator = VideoGenerator()
        concept = {"name": "Test"}
        videos = generator.generate(concept, 1)
        self.assertEqual(len(videos), 1)

    def test_video_generator_generate_object(self):
        generator = VideoGenerator()
        class MockConcept:
            name = "Mock"
            genre = "Simulation"
            core_loop = ["Build", "Manage"]
        videos = generator.generate(MockConcept(), 2)
        self.assertEqual(len(videos), 2)

    def test_screenshot_generator_generate(self):
        generator = ScreenshotGenerator()
        concept = {"name": "Test", "genre": "Merge"}
        screenshots = generator.generate(concept, 5)
        self.assertEqual(len(screenshots), 5)

    def test_screenshot_generator_generate_3(self):
        generator = ScreenshotGenerator()
        concept = {"name": "Test"}
        screenshots = generator.generate(concept, 3)
        self.assertEqual(len(screenshots), 3)

    def test_icon_generator_generate(self):
        generator = IconGenerator()
        concept = {"name": "Test", "genre": "Merge"}
        icons = generator.generate(concept, 3)
        self.assertEqual(len(icons), 3)

    def test_icon_generator_generate_single(self):
        generator = IconGenerator()
        concept = {"name": "Test"}
        icons = generator.generate(concept, 1)
        self.assertEqual(len(icons), 1)

    def test_creative_evaluator_evaluate(self):
        evaluator = CreativeEvaluator()
        creative = {"video_id": "v1", "platform": "meta"}
        data = {"ctr": 0.03, "cvr": 0.025}
        evaluation = evaluator.evaluate(creative, data)
        self.assertIsNotNone(evaluation)

    def test_creative_evaluator_evaluate_high_performance(self):
        evaluator = CreativeEvaluator()
        creative = {"video_id": "v1"}
        data = {"ctr": 0.05, "cvr": 0.04}
        evaluation = evaluator.evaluate(creative, data)
        self.assertTrue(evaluation.score >= 80)

    def test_creative_evaluator_evaluate_low_performance(self):
        evaluator = CreativeEvaluator()
        creative = {"video_id": "v1"}
        data = {"ctr": 0.01, "cvr": 0.01}
        evaluation = evaluator.evaluate(creative, data)
        self.assertTrue(evaluation.score < 60)

    def test_creative_evaluator_rank(self):
        evaluator = CreativeEvaluator()
        creatives = [
            {"video_id": "v1"},
            {"video_id": "v2"},
        ]
        data = [{"ctr": 0.05}, {"ctr": 0.02}]
        ranked = evaluator.rank(creatives, data)
        self.assertTrue(len(ranked) == 2)

    def test_creative_evolution_evolve(self):
        evolution = CreativeEvolution()
        creative = {"video_id": "v1"}
        performance = {"ctr": 0.025, "cvr": 0.022}
        result = evolution.evolve(creative, performance)
        self.assertIsNotNone(result)
        self.assertTrue(len(result.improvements) > 0)

    def test_creative_evolution_evolve_high_performance(self):
        evolution = CreativeEvolution()
        creative = {"video_id": "v1"}
        performance = {"ctr": 0.05, "cvr": 0.04}
        result = evolution.evolve(creative, performance)
        self.assertIsNotNone(result)

    def test_creative_evolution_evolve_low_performance(self):
        evolution = CreativeEvolution()
        creative = {"video_id": "v1"}
        performance = {"ctr": 0.01, "cvr": 0.01}
        result = evolution.evolve(creative, performance)
        self.assertTrue(len(result.improvements) >= 2)


class TestCompanySimulator(unittest.TestCase):
    def test_user_simulator_simulate(self):
        simulator = UserSimulator()
        game_data = {"cpi": 2.5, "d1": 0.4, "d7": 0.2, "d30": 0.09}
        result = simulator.simulate(game_data, 50000)
        self.assertIsNotNone(result)
        self.assertTrue(result.total_users > 0)

    def test_user_simulator_simulate_high_budget(self):
        simulator = UserSimulator()
        game_data = {"cpi": 2.0}
        result = simulator.simulate(game_data, 100000)
        self.assertTrue(result.total_users > 0)

    def test_user_simulator_simulate_low_cpi(self):
        simulator = UserSimulator()
        game_data = {"cpi": 1.0}
        result = simulator.simulate(game_data, 50000)
        self.assertTrue(result.total_users > 0)

    def test_company_economy_simulator_simulate(self):
        simulator = CompanyEconomySimulator()
        game_data = {"d30": 0.09, "arpdau": 0.15, "cpi": 2.5}
        result = simulator.simulate(game_data, 50000)
        self.assertIsNotNone(result)
        self.assertTrue(result.ltv > 0)

    def test_company_economy_simulator_simulate_high_revenue(self):
        simulator = CompanyEconomySimulator()
        game_data = {"d30": 0.25, "arpdau": 0.5, "cpi": 1.5}
        result = simulator.simulate(game_data, 50000)
        self.assertTrue(result.roi > 0)

    def test_company_economy_simulator_simulate_low_revenue(self):
        simulator = CompanyEconomySimulator()
        game_data = {"d30": 0.03, "arpdau": 0.05}
        result = simulator.simulate(game_data, 50000)
        self.assertIsNotNone(result)

    def test_ua_simulator_simulate(self):
        simulator = UASimulator()
        result = simulator.simulate("meta", 50000)
        self.assertIsNotNone(result)
        self.assertTrue(result.installs > 0)

    def test_ua_simulator_simulate_google(self):
        simulator = UASimulator()
        result = simulator.simulate("google", 50000)
        self.assertIsNotNone(result)

    def test_ua_simulator_simulate_tiktok(self):
        simulator = UASimulator()
        result = simulator.simulate("tiktok", 50000)
        self.assertIsNotNone(result)

    def test_ua_simulator_simulate_all(self):
        simulator = UASimulator()
        results = simulator.simulate_all_platforms(50000)
        self.assertEqual(len(results), 4)

    def test_revenue_forecast_forecast(self):
        forecast = RevenueForecast()
        game_data = {"d30": 0.09, "arpdau": 0.15, "cpi": 2.5}
        result = forecast.forecast(game_data, 50000, 90)
        self.assertIsNotNone(result)
        self.assertTrue(result.total_revenue > 0)

    def test_revenue_forecast_forecast_180_days(self):
        forecast = RevenueForecast()
        game_data = {"d30": 0.1, "arpdau": 0.2}
        result = forecast.forecast(game_data, 50000, 180)
        self.assertTrue(result.days == 180)

    def test_revenue_forecast_forecast_high_confidence(self):
        forecast = RevenueForecast()
        game_data = {"d30": 0.15, "arpdau": 0.3}
        result = forecast.forecast(game_data, 50000, 90)
        self.assertTrue(result.confidence > 0.7)

    def test_risk_engine_assess(self):
        engine = RiskEngine()
        game_data = {"d30": 0.09, "arpdau": 0.15}
        market_data = {"competition": "medium", "trend_score": 85}
        assessment = engine.assess(game_data, market_data)
        self.assertIsNotNone(assessment)
        self.assertTrue(assessment.risk_score >= 0)

    def test_risk_engine_assess_high_risk(self):
        engine = RiskEngine()
        game_data = {"d30": 0.02, "arpdau": 0.03, "payback_days": 200, "roi": 20}
        market_data = {"competition": "high", "trend_score": 40}
        assessment = engine.assess(game_data, market_data)
        self.assertEqual(assessment.overall_risk, "high")

    def test_risk_engine_assess_low_risk(self):
        engine = RiskEngine()
        game_data = {"d30": 0.15, "arpdau": 0.3, "payback_days": 60, "roi": 150}
        market_data = {"competition": "low", "trend_score": 95}
        assessment = engine.assess(game_data, market_data)
        self.assertEqual(assessment.overall_risk, "low")


class TestLaunchAgent(unittest.TestCase):
    def test_build_pipeline_build(self):
        pipeline = BuildPipeline()
        project = {"scripts": ["a", "b", "c"]}
        result = pipeline.build(project, "android")
        self.assertEqual(result.status, "success")

    def test_build_pipeline_build_failure(self):
        pipeline = BuildPipeline()
        project = {"scripts": ["a"]}
        result = pipeline.build(project, "android")
        self.assertEqual(result.status, "failed")

    def test_build_pipeline_build_ios(self):
        pipeline = BuildPipeline()
        project = {"scripts": ["a", "b", "c"]}
        result = pipeline.build(project, "ios")
        self.assertIsNotNone(result)

    def test_build_pipeline_build_all(self):
        pipeline = BuildPipeline()
        project = {"scripts": ["a", "b", "c"]}
        results = pipeline.build_all(project)
        self.assertEqual(len(results), 2)

    def test_store_submitter_submit(self):
        submitter = StoreSubmitter()
        app_data = {"icon": "icon.png", "screenshots": ["s1.png"]}
        result = submitter.submit(app_data, "app_store")
        self.assertEqual(result.status, "approved")

    def test_store_submitter_submit_no_icon(self):
        submitter = StoreSubmitter()
        app_data = {"screenshots": ["s1.png"]}
        result = submitter.submit(app_data, "app_store")
        self.assertEqual(result.status, "rejected")

    def test_store_submitter_submit_no_screenshots(self):
        submitter = StoreSubmitter()
        app_data = {"icon": "icon.png"}
        result = submitter.submit(app_data, "app_store")
        self.assertEqual(result.status, "rejected")

    def test_store_submitter_submit_all(self):
        submitter = StoreSubmitter()
        app_data = {"icon": "icon.png", "screenshots": ["s1.png"]}
        results = submitter.submit_all(app_data)
        self.assertEqual(len(results), 2)

    def test_aso_optimizer_optimize(self):
        optimizer = ASOOptimizer()
        game_data = {"name": "Test", "genre": "Merge"}
        keywords = ["merge", "puzzle", "game"]
        result = optimizer.optimize(game_data, keywords)
        self.assertIsNotNone(result)
        self.assertTrue(len(result.keywords) > 0)

    def test_aso_optimizer_optimize_long_keywords(self):
        optimizer = ASOOptimizer()
        game_data = {"name": "Long Game Name", "genre": "Simulation"}
        keywords = ["a" * 20, "b" * 15, "c" * 25, "d" * 10] * 5
        result = optimizer.optimize(game_data, keywords)
        self.assertTrue(len(result.keywords) <= 10)

    def test_ua_launcher_launch(self):
        launcher = UALauncher()
        result = launcher.launch("meta", 50000, ["v1", "v2"])
        self.assertEqual(result.status, "running")
        self.assertTrue(result.installs > 0)

    def test_ua_launcher_launch_google(self):
        launcher = UALauncher()
        result = launcher.launch("google", 50000, ["v1"])
        self.assertIsNotNone(result)

    def test_ua_launcher_launch_all(self):
        launcher = UALauncher()
        results = launcher.launch_all(50000, ["v1"])
        self.assertEqual(len(results), 4)

    def test_launch_monitor_monitor(self):
        monitor = LaunchMonitor()
        metrics = {"cpi": 2.3, "roas": 1.5, "installs": 500}
        result = monitor.monitor("launch_001", metrics)
        self.assertEqual(result.status, "healthy")

    def test_launch_monitor_monitor_high_cpi(self):
        monitor = LaunchMonitor()
        metrics = {"cpi": 5.0, "roas": 0.8, "installs": 50}
        result = monitor.monitor("launch_001", metrics)
        self.assertTrue(len(result.recommendations) > 0)

    def test_launch_monitor_get_summary(self):
        monitor = LaunchMonitor()
        metrics = {"cpi": 2.0}
        monitor.monitor("launch_001", metrics)
        summary = monitor.get_summary("launch_001")
        self.assertIsNotNone(summary)

    def test_launch_monitor_get_summary_not_found(self):
        monitor = LaunchMonitor()
        summary = monitor.get_summary("nonexistent")
        self.assertEqual(summary["status"], "no_data")


class TestAutonomousLearning(unittest.TestCase):
    def test_failure_analysis_analyze(self):
        analysis = FailureAnalysis()
        project_data = {"project_id": "p1"}
        performance_data = {"d1": 0.2, "d7": 0.08, "d30": 0.02}
        result = analysis.analyze(project_data, performance_data)
        self.assertIsNotNone(result)
        self.assertTrue(len(result.recommendations) > 0)

    def test_failure_analysis_analyze_retention(self):
        analysis = FailureAnalysis()
        project_data = {"project_id": "p1"}
        performance_data = {"d1": 0.2, "d30": 0.02}
        result = analysis.analyze(project_data, performance_data)
        self.assertEqual(result.failure_type, "retention")

    def test_failure_analysis_analyze_ua(self):
        analysis = FailureAnalysis()
        project_data = {"project_id": "p1"}
        performance_data = {"cpi": 6.0}
        result = analysis.analyze(project_data, performance_data)
        self.assertEqual(result.failure_type, "user_acquisition")

    def test_failure_analysis_analyze_monetization(self):
        analysis = FailureAnalysis()
        project_data = {"project_id": "p1"}
        performance_data = {"arpdau": 0.03}
        result = analysis.analyze(project_data, performance_data)
        self.assertEqual(result.failure_type, "monetization")

    def test_strategy_evolution_evolve(self):
        evolution = StrategyEvolution()
        strategy = {
            "strategy_id": "s1",
            "budget_allocation": {"dev": 0.4, "ua": 0.4},
            "timeline": {"prototype": 4},
            "regions": ["US"],
        }
        performance_data = {"roas": 2.5}
        result = evolution.evolve(strategy, performance_data)
        self.assertIsNotNone(result)
        self.assertTrue(len(result.changes) > 0)

    def test_strategy_evolution_evolve_no_changes(self):
        evolution = StrategyEvolution()
        strategy = {"strategy_id": "s1", "regions": ["US", "UK", "CA"]}
        performance_data = {"roas": 1.0, "d30": 0.1}
        result = evolution.evolve(strategy, performance_data)
        self.assertIsNotNone(result)

    def test_strategy_evolution_evolve_multiple_changes(self):
        evolution = StrategyEvolution()
        strategy = {"strategy_id": "s1", "regions": ["US"], "timeline": {"prototype": 6}}
        performance_data = {"roas": 3.0, "d30": 0.03}
        result = evolution.evolve(strategy, performance_data)
        self.assertTrue(len(result.changes) >= 2)

    def test_learning_company_memory_store(self):
        mem = LearningCompanyMemory()
        entry = mem.store("success", {"project": "Game X"}, 0.9)
        self.assertEqual(entry.type, "success")

    def test_learning_company_memory_get_success_patterns(self):
        mem = LearningCompanyMemory()
        mem.store("success", {"project": "Game X"})
        patterns = mem.get_success_patterns()
        self.assertTrue(len(patterns) >= 1)

    def test_learning_company_memory_get_failed_patterns(self):
        mem = LearningCompanyMemory()
        mem.store("failure", {"project": "Game Y"})
        patterns = mem.get_failed_patterns()
        self.assertTrue(len(patterns) >= 1)

    def test_learning_company_memory_get_best_strategies(self):
        mem = LearningCompanyMemory()
        mem.store("strategy", {"strategy_id": "s1", "success_rate": 0.8})
        mem.store("strategy", {"strategy_id": "s2", "success_rate": 0.9})
        strategies = mem.get_best_strategies(2)
        self.assertTrue(len(strategies) >= 1)

    def test_meta_learning_learn(self):
        learning = MetaLearning()
        history = [
            {"genre": "Merge", "success": True, "regions": ["US"], "revenue": 100000, "arpdau": 0.25},
            {"genre": "Match 3", "success": False, "regions": ["US"], "revenue": 30000, "arpdau": 0.12},
        ]
        insights = learning.learn(history)
        self.assertTrue(len(insights) > 0)

    def test_meta_learning_learn_no_insights(self):
        learning = MetaLearning()
        history = [
            {"genre": "Unknown", "success": False, "regions": ["XX"], "revenue": 1000, "arpdau": 0.05},
        ]
        insights = learning.learn(history)
        self.assertIsInstance(insights, list)

    def test_meta_learning_learn_multiple_genres(self):
        learning = MetaLearning()
        history = [
            {"genre": "Merge", "success": True, "regions": ["US"], "revenue": 100000, "arpdau": 0.25},
            {"genre": "Simulation", "success": True, "regions": ["DE"], "revenue": 80000, "arpdau": 0.30},
            {"genre": "Arcade", "success": True, "regions": ["JP"], "revenue": 70000, "arpdau": 0.28},
        ]
        insights = learning.learn(history)
        self.assertTrue(len(insights) >= 2)


class TestIntegration(unittest.TestCase):
    def test_full_company_os_flow(self):
        ceo = CEOBrain()
        goal = CompanyGoal()
        allocator = ResourceAllocator()
        
        goal.set_goal(10_000_000, 12)
        strategy = ceo.make_strategy({"target_arr": 10_000_000})
        allocation = allocator.allocate(strategy.projects, {"developers": 2})
        
        self.assertIsNotNone(strategy)
        self.assertIsNotNone(allocation)

    def test_full_market_discovery_flow(self):
        scanner = TrendScanner()
        analyzer = CompetitorAnalyzer()
        miner = KeywordMiner()
        detector = MarketGapDetector()
        scorer = OpportunityScore()
        
        trends = scanner.scan(["app_store"])
        competitors = analyzer.analyze("Merge", ["US"])
        keywords = miner.mine("merge", ["US"])
        gaps = detector.detect(["merge"])
        score_result = scorer.score({"genre": "Merge", "competition": "medium", "keyword_gap": "high", "trend_score": 85})
        
        self.assertTrue(len(trends) > 0)
        self.assertTrue(len(keywords) > 0)
        self.assertTrue(score_result.opportunity_score >= 60)

    def test_full_product_flow(self):
        generator = ConceptGenerator()
        builder = GDDBuilder()
        predictor = RetentionPredictor()
        
        opportunity = {"genre": "Merge", "opportunity_score": 87}
        concept = generator.generate(opportunity)
        gdd = builder.build(concept)
        prediction = predictor.predict("Merge")
        
        self.assertIsNotNone(concept)
        self.assertIsNotNone(gdd)
        self.assertIsNotNone(prediction)

    def test_full_simulator_flow(self):
        user_sim = UserSimulator()
        eco_sim = CompanyEconomySimulator()
        ua_sim = UASimulator()
        forecast = RevenueForecast()
        risk = RiskEngine()
        
        user_result = user_sim.simulate({"cpi": 2.5, "d1": 0.4}, 50000)
        eco_result = eco_sim.simulate({"d30": 0.09, "arpdau": 0.15}, 50000)
        ua_result = ua_sim.simulate("meta", 50000)
        forecast_result = forecast.forecast({"d30": 0.09}, 50000, 90)
        risk_result = risk.assess({"d30": 0.09}, {"competition": "medium"})
        
        self.assertIsNotNone(user_result)
        self.assertIsNotNone(eco_result)
        self.assertIsNotNone(ua_result)
        self.assertIsNotNone(forecast_result)
        self.assertIsNotNone(risk_result)

    def test_full_launch_flow(self):
        pipeline = BuildPipeline()
        submitter = StoreSubmitter()
        aso = ASOOptimizer()
        launcher = UALauncher()
        monitor = LaunchMonitor()
        
        build = pipeline.build({"scripts": ["a", "b", "c"]}, "android")
        submit = submitter.submit({"icon": "i.png", "screenshots": ["s.png"]})
        optimize = aso.optimize({"name": "Test"}, ["test", "game"])
        launch = launcher.launch("meta", 10000, ["v1"])
        monitor_result = monitor.monitor(launch.launch_id, {"cpi": 2.0})
        
        self.assertEqual(build.status, "success")
        self.assertEqual(submit.status, "approved")
        self.assertIsNotNone(optimize)
        self.assertIsNotNone(launch)
        self.assertIsNotNone(monitor_result)

    def test_full_learning_flow(self):
        failure = FailureAnalysis()
        evolution = StrategyEvolution()
        memory = LearningCompanyMemory()
        meta = MetaLearning()
        
        analysis = failure.analyze({"project_id": "p1"}, {"d1": 0.2})
        evolve = evolution.evolve({"strategy_id": "s1"}, {"roas": 2.5})
        memory.store("success", {"project": "Game X"})
        insights = meta.learn([{"genre": "Merge", "success": True, "revenue": 100000}])
        
        self.assertIsNotNone(analysis)
        self.assertIsNotNone(evolve)
        self.assertTrue(len(insights) >= 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
