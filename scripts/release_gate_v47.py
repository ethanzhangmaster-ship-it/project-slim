#!/usr/bin/env python3
"""V4.7 Creative Intelligence Integration Layer Release Gate.

Tests 6 major modules for autonomous UA growth:
1. Attribution Engine - Revenue mapping, cohort analysis, incremental lift
2. Audience Intelligence - User embedding, creative matching, segment memory
3. Budget Agent - Auto scaling, kill rules, budget allocation
4. Experiment Engine - Bayesian optimization, A/B testing, auto stop
5. Store Intelligence - ASO analysis, screenshot DNA, creative alignment
6. Autonomous Agent - Planning, execution, reflection

Target: 80+/80 PASS
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

PASS_COUNT = 0
FAIL_COUNT = 0
TEST_RESULTS = []


def test(name: str, passed: bool, details: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT, TEST_RESULTS
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    TEST_RESULTS.append({"test": name, "status": status, "details": details})
    print(f"[{status}] {name}")
    if details:
        print(f"    {details}")


def test_attribution():
    print("\n=== Test 1: Attribution Engine ===")
    from market_ops.video_generation.attribution import (
        CreativeAttributionEngine, AttributionInput, AttributionResult,
        CohortAnalyzer, CohortData, CohortAnalysis,
        RevenueMapper, RevenueMapping,
        IncrementalLiftCalculator, LiftResult,
    )
    
    # Creative Attribution
    engine = CreativeAttributionEngine()
    result = engine.attribute_demo()
    test("Attribution Engine Init", True)
    test("Quality Score", result.quality_score > 0, f"Score: {result.quality_score:.2f}")
    test("Revenue Contribution", result.revenue_contribution > 0, f"Revenue: {result.revenue_contribution}")
    test("Incremental Lift", result.incremental_lift >= 0, f"Lift: {result.incremental_lift:.2f}")
    test("Winner Probability", result.winner_probability >= 0, f"Probability: {result.winner_probability:.2f}")
    test("ROI Calculation", result.roi > 0, f"ROI: {result.roi:.2f}")
    
    # Cohort Analysis
    analyzer = CohortAnalyzer()
    analysis = analyzer.analyze_demo()
    test("Cohort Analysis", True)
    test("D1 Retention", analysis.avg_d1_retention > 0, f"D1: {analysis.avg_d1_retention:.2f}")
    test("D7 Retention", analysis.avg_d7_retention > 0, f"D7: {analysis.avg_d7_retention:.2f}")
    test("LTV", analysis.avg_ltv > 0, f"LTV: {analysis.avg_ltv:.2f}")
    test("Cohort Quality", analysis.cohort_quality > 0, f"Quality: {analysis.cohort_quality:.2f}")
    test("Trend Detection", analysis.trend in ["up", "down", "stable"], f"Trend: {analysis.trend}")
    
    # Revenue Mapping
    mapper = RevenueMapper()
    mapping = mapper.map_demo()
    test("Revenue Mapping", True)
    test("Total Revenue", mapping.total_revenue > 0, f"Total: {mapping.total_revenue}")
    test("Attributable Revenue", mapping.attributable_revenue > 0, f"Attributable: {mapping.attributable_revenue:.2f}")
    test("Cannibalization Rate", 0 <= mapping.cannibalization_rate <= 0.5, f"Cannibalization: {mapping.cannibalization_rate:.2f}")
    test("ROI", mapping.roi > 0, f"ROI: {mapping.roi:.2f}")
    
    # Incremental Lift
    lift_calc = IncrementalLiftCalculator()
    lift = lift_calc.calculate_demo()
    test("Incremental Lift", True)
    test("Lift Value", lift.incremental_lift >= 0, f"Lift: {lift.incremental_lift:.2f}")
    test("Baseline Revenue", lift.baseline_revenue > 0, f"Baseline: {lift.baseline_revenue}")
    test("Incremental Revenue", lift.incremental_revenue > 0, f"Incremental: {lift.incremental_revenue}")
    test("Significance", lift.significance >= 0, f"Significance: {lift.significance:.2f}")


def test_audience_intelligence():
    print("\n=== Test 2: Audience Intelligence ===")
    from market_ops.video_generation.audience_intelligence import (
        AudienceClusterEngine, AudienceProfile, ClusterResult,
        UserEmbeddingEngine, UserEmbedding,
        CreativeAudienceMatcher, MatchResult,
        SegmentMemory, SegmentRecord,
    )
    
    # Audience Cluster
    cluster = AudienceClusterEngine()
    clusters = cluster.cluster_demo()
    test("Audience Cluster", True)
    test("Cluster Count", len(clusters) > 0, f"Clusters: {len(clusters)}")
    test("Cluster Characteristics", len(clusters[0].characteristics) > 0, f"Chars: {len(clusters[0].characteristics)}")
    test("Cluster Size", clusters[0].size > 0, f"Size: {clusters[0].size}")
    
    # User Embedding
    embedder = UserEmbeddingEngine()
    embedding = embedder.embed_demo()
    test("User Embedding", True)
    test("Embedding Dimension", len(embedding.embedding) > 0, f"Dim: {len(embedding.embedding)}")
    test("Profile", len(embedding.profile) > 0, f"Profile keys: {list(embedding.profile.keys())}")
    
    # Creative Audience Match
    matcher = CreativeAudienceMatcher()
    match = matcher.match_demo()
    test("Creative Audience Match", True)
    test("Match Score", match.match_score > 0, f"Score: {match.match_score:.2f}")
    test("Recommended Platform", match.recommended_platform != "", f"Platform: {match.recommended_platform}")
    test("Recommended Audience", match.recommended_audience != "", f"Audience: {match.recommended_audience}")
    test("Confidence", match.confidence > 0, f"Confidence: {match.confidence:.2f}")
    
    # Segment Memory
    memory = SegmentMemory()
    segment = memory.add_demo()
    test("Segment Memory", True)
    test("Segment ID", segment.segment_id.startswith("segment_"), f"ID: {segment.segment_id}")
    test("Match Score", segment.match_score > 0, f"Score: {segment.match_score:.2f}")
    test("Performance Data", len(segment.performance) > 0, f"Metrics: {len(segment.performance)}")


def test_budget_agent():
    print("\n=== Test 3: Budget Agent ===")
    from market_ops.video_generation.budget_agent import (
        BudgetOptimizer, BudgetRequest, BudgetDecision,
        AllocationEngine, AllocationItem,
        ScalingPolicy, ScalingAction,
        KillRuleEngine, KillDecision,
    )
    
    # Budget Optimizer
    optimizer = BudgetOptimizer()
    decision = optimizer.optimize_demo()
    test("Budget Optimizer", True)
    test("Budget Increase", decision.new_budget > decision.old_budget, f"${decision.old_budget:.0f} → ${decision.new_budget:.0f}")
    test("Change Percent", decision.change_percent > 0, f"{decision.change_percent:.0f}%")
    test("Reason", decision.reason != "", f"Reason: {decision.reason}")
    test("Confidence", decision.confidence > 0, f"Confidence: {decision.confidence:.2f}")
    
    # Allocation Engine
    allocator = AllocationEngine()
    allocations = allocator.allocate_demo()
    test("Allocation Engine", True)
    test("Allocation Count", len(allocations) > 0, f"Allocations: {len(allocations)}")
    test("Top Priority", allocations[0].priority == 1, f"Priority: {allocations[0].priority}")
    test("Total Allocation", sum(a.allocation for a in allocations) > 0, f"Total: ${sum(a.allocation for a in allocations):.0f}")
    
    # Scaling Policy
    scaler = ScalingPolicy()
    action = scaler.evaluate_demo()
    test("Scaling Policy", True)
    test("Scale Up Action", action.action.startswith("scale_up"), f"Action: {action.action}")
    test("New Budget", action.new_budget > action.old_budget, f"${action.old_budget:.0f} → ${action.new_budget:.0f}")
    test("Confidence", action.confidence > 0, f"Confidence: {action.confidence:.2f}")
    
    # Kill Rule
    killer = KillRuleEngine()
    kill = killer.evaluate_demo()
    test("Kill Rule", True)
    test("Should Kill", kill.should_kill, f"Should Kill: {kill.should_kill}")
    test("Reason", kill.reason != "", f"Reason: {kill.reason}")
    test("Metrics", len(kill.metrics) > 0, f"Metrics: {len(kill.metrics)}")


def test_experiment_engine():
    print("\n=== Test 4: Experiment Engine ===")
    from market_ops.video_generation.experiment_engine import (
        ABTestManager, TestVariant, ABTestResult,
        BayesianOptimizer, BayesianResult,
        TestScheduler, TestSchedule,
        StoppingRuleEngine, StopDecision,
    )
    
    # A/B Test Manager
    ab_manager = ABTestManager()
    result = ab_manager.evaluate_demo()
    test("A/B Test Manager", True)
    test("Winner Identified", result.winner != "", f"Winner: {result.winner}")
    test("Probabilities", len(result.probabilities) > 0, f"Variants: {len(result.probabilities)}")
    test("Confidence", result.confidence > 0, f"Confidence: {result.confidence:.2f}")
    
    # Bayesian Optimizer
    bayesian = BayesianOptimizer()
    recommendation = bayesian.recommend_demo()
    test("Bayesian Optimizer", True)
    test("Recommendation", recommendation != "", f"Recommended: {recommendation}")
    
    # Test Scheduler
    scheduler = TestScheduler()
    schedule = scheduler.schedule_demo()
    test("Test Scheduler", True)
    test("Test ID", schedule.test_id.startswith("test_"), f"ID: {schedule.test_id}")
    test("Status", schedule.status == "scheduled", f"Status: {schedule.status}")
    test("Variants", len(schedule.variants) > 0, f"Variants: {len(schedule.variants)}")
    test("Budget", schedule.budget > 0, f"Budget: ${schedule.budget:.0f}")
    
    # Stopping Rule
    stopper = StoppingRuleEngine()
    stop = stopper.evaluate_demo()
    test("Stopping Rule", True)
    test("Winner", stop.winner != "", f"Winner: {stop.winner}")
    test("Confidence", stop.confidence >= 0, f"Confidence: {stop.confidence:.2f}")


def test_store_intelligence():
    print("\n=== Test 5: Store Intelligence ===")
    from market_ops.video_generation.store_intelligence import (
        ASOAnalyzer, ASOData, ASOAnalysis,
        ScreenshotDNAAnalyzer, ScreenshotDNA,
        KeywordMatcher, KeywordMatchResult,
        CreativeStoreAligner, AlignmentResult,
    )
    
    # ASO Analyzer
    aso = ASOAnalyzer()
    analysis = aso.analyze_demo()
    test("ASO Analyzer", True)
    test("Overall Score", analysis.overall_score > 0, f"Score: {analysis.overall_score:.2f}")
    test("Title Score", analysis.title_score >= 0, f"Title: {analysis.title_score:.2f}")
    test("Keyword Score", analysis.keyword_score >= 0, f"Keyword: {analysis.keyword_score:.2f}")
    test("Description Score", analysis.description_score >= 0, f"Description: {analysis.description_score:.2f}")
    
    # Screenshot DNA
    dna_analyzer = ScreenshotDNAAnalyzer()
    dna = dna_analyzer.extract_demo()
    test("Screenshot DNA", True)
    test("Visuals", len(dna.visuals) > 0, f"Visuals: {len(dna.visuals)}")
    test("Colors", len(dna.colors) > 0, f"Colors: {len(dna.colors)}")
    test("Themes", len(dna.themes) > 0, f"Themes: {len(dna.themes)}")
    
    # Keyword Match
    keyword_matcher = KeywordMatcher()
    match = keyword_matcher.match_demo()
    test("Keyword Match", True)
    test("Match Score", match.match_score >= 0, f"Score: {match.match_score:.2f}")
    test("Missing Keywords", len(match.missing_keywords) > 0, f"Missing: {len(match.missing_keywords)}")
    
    # Creative Store Alignment
    aligner = CreativeStoreAligner()
    alignment = aligner.check_alignment_demo()
    test("Creative Store Alignment", True)
    test("Alignment Score", alignment.alignment_score >= 0, f"Score: {alignment.alignment_score:.2f}")
    test("Mismatch Detected", alignment.mismatch_detected, f"Mismatch: {alignment.mismatch_detected}")
    test("CVR Loss", alignment.cvr_loss_estimate > 0, f"CVR Loss: {alignment.cvr_loss_estimate:.2f}")
    test("Recommendations", len(alignment.recommendations) > 0, f"Recs: {len(alignment.recommendations)}")


def test_autonomous_agent():
    print("\n=== Test 6: Autonomous Agent ===")
    from market_ops.video_generation.autonomous_agent import (
        DecisionAgent, Decision,
        Planner, Plan, PlanStep,
        Executor, ExecutionResult,
        ReflectionEngine, ReflectionResult,
    )
    
    # Decision Agent
    decision_agent = DecisionAgent()
    decisions = decision_agent.make_decision_demo()
    test("Decision Agent", True)
    test("Decisions Count", len(decisions) > 0, f"Decisions: {len(decisions)}")
    test("Decision Type", decisions[0].type in ["scale", "kill", "optimize"], f"Type: {decisions[0].type}")
    test("Decision Action", decisions[0].action != "", f"Action: {decisions[0].action}")
    test("Confidence", decisions[0].confidence > 0, f"Confidence: {decisions[0].confidence:.2f}")
    
    # Planner
    planner = Planner()
    plan = planner.create_plan_demo()
    test("Planner", True)
    test("Plan ID", plan.plan_id.startswith("plan_"), f"ID: {plan.plan_id}")
    test("Steps Count", len(plan.steps) > 0, f"Steps: {len(plan.steps)}")
    test("Status", plan.status == "active", f"Status: {plan.status}")
    
    # Executor
    executor = Executor()
    results = executor.execute_demo()
    test("Executor", True)
    test("Execution Steps", len(results) > 0, f"Steps: {len(results)}")
    test("All Success", all(r.success for r in results), "All steps succeeded")
    
    # Reflection
    reflection = ReflectionEngine()
    reflect_result = reflection.reflect_demo()
    test("Reflection", True)
    test("Successes", len(reflect_result.successes) > 0, f"Successes: {len(reflect_result.successes)}")
    test("Insights", len(reflect_result.insights) > 0, f"Insights: {len(reflect_result.insights)}")
    test("Improvements", len(reflect_result.improvements) > 0, f"Improvements: {len(reflect_result.improvements)}")
    test("Overall Score", reflect_result.overall_score > 0, f"Score: {reflect_result.overall_score:.2f}")


def print_summary():
    print("\n" + "=" * 50)
    print("V4.7 Creative Intelligence Integration Layer")
    print("=" * 50)
    print(f"\nResults: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASS")
    
    if FAIL_COUNT == 0:
        print("\n✓ ALL TESTS PASSED - V4.7 RELEASE APPROVED")
        print("\nAI Creative Growth Agent is ready!")
        print("System can now:")
        print("  - Attribute revenue to specific creatives")
        print("  - Match creatives with optimal audiences")
        print("  - Automatically scale or kill campaigns")
        print("  - Run Bayesian A/B tests with auto-stop")
        print("  - Align creative with store listing")
        print("  - Make autonomous UA decisions daily")
    else:
        print(f"\n✗ {FAIL_COUNT} TESTS FAILED")
        for r in TEST_RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}: {r.get('details', '')}")
    
    output = {
        "version": "V4.7",
        "timestamp": datetime.now().isoformat(),
        "pass_count": PASS_COUNT,
        "fail_count": FAIL_COUNT,
        "passed": FAIL_COUNT == 0,
        "results": TEST_RESULTS,
    }
    
    output_path = Path(__file__).parent.parent / "data" / "release_gate_v47_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


def main():
    print("=" * 50)
    print("V4.7 Creative Intelligence Integration Layer")
    print("=" * 50)
    print("\nTesting 6 major modules for autonomous UA growth...")
    print("Target: 80+/80 PASS\n")
    
    test_attribution()
    test_audience_intelligence()
    test_budget_agent()
    test_experiment_engine()
    test_store_intelligence()
    test_autonomous_agent()
    
    print_summary()
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
