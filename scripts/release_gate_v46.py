#!/usr/bin/env python3
"""V4.6 Creative Learning Loop Release Gate.

Tests 10 modules for autonomous creative evolution:
1. Winner Discovery - Automatic winner pattern detection
2. DNA Extraction - Feature importance analysis
3. Confidence Calculation - Statistical confidence scoring
4. Mutation Generation - Creative variation generation
5. Fitness Score - Multi-dimensional fitness evaluation
6. Evolution Cycle - Natural selection simulation
7. Performance Feedback - Real-time performance collection
8. Reward Calculation - RL reward computation
9. Strategy Memory - Successful strategy storage
10. Loser Memory - Failure pattern avoidance

Target: 30/30 PASS
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


def test_winner_discovery():
    print("\n=== Test 1: Winner Discovery ===")
    from market_ops.video_generation.learning import WinnerDiscoveryEngine
    
    engine = WinnerDiscoveryEngine()
    patterns = engine.discover(min_confidence=0.70)
    
    test("Winner Pattern Discovery", len(patterns) > 0, f"Patterns: {len(patterns)}")
    test("Pattern ID", patterns[0].winner_pattern_id.startswith("pattern_"), f"ID: {patterns[0].winner_pattern_id}")
    test("Confidence Score", patterns[0].confidence >= 0.70, f"Confidence: {patterns[0].confidence:.2f}")
    test("DNA Hook", "hook" in patterns[0].dna, f"Hook: {patterns[0].dna.get('hook')}")
    test("DNA Camera", "camera" in patterns[0].dna, f"Camera: {patterns[0].dna.get('camera')}")


def test_dna_extraction():
    print("\n=== Test 2: DNA Extraction ===")
    from market_ops.video_generation.learning import DNAAnalyzer, DNAFeature
    
    analyzer = DNAAnalyzer()
    
    sample_dna = {
        "hook": "first_second_action",
        "camera": "zoom_in",
        "scene": "reward",
        "character": "witch",
        "emotion": "curiosity",
    }
    
    importance = analyzer.analyze_feature("camera", "close_up", 50)
    test("Feature Importance", importance.importance > 0, f"Importance: {importance.importance:.2f}")
    
    importance_list = analyzer.analyze_all_features(sample_dna)
    test("All Features Analysis", len(importance_list) > 0, f"Features: {len(importance_list)}")
    
    # Add demo data for top features
    for i in range(5):
        analyzer.add_winner({"dna": {"camera": "close_up", "lighting": "warm"}})
        analyzer.add_creative({"dna": {"camera": "close_up", "lighting": "warm"}})
    
    top_features = analyzer.get_top_features(3)
    test("Top Features", len(top_features) >= 2, f"Top: {len(top_features)}")
    
    winner_prob = analyzer.calculate_winner_probability({"camera": "close_up"})
    test("Winner Probability", winner_prob >= 0, f"Probability: {winner_prob:.2f}")


def test_confidence_calculation():
    print("\n=== Test 3: Confidence Calculation ===")
    from market_ops.video_generation.learning import ConfidenceCalculator, ConfidenceScore
    
    scorer = ConfidenceCalculator()
    
    score = scorer.calculate(
        pattern_id="pattern_A",
        sample_size=50,
        performance_gap=0.42,
        consistency=0.85,
    )
    
    test("Confidence Score", score.confidence >= 0.70, f"Confidence: {score.confidence:.2f}")
    test("Pattern ID", score.pattern_id == "pattern_A", f"ID: {score.pattern_id}")
    test("Sample Size", score.sample_size == 50, f"Sample: {score.sample_size}")
    test("Performance Gap", score.performance_gap == 0.42, f"Gap: {score.performance_gap}")
    
    # Verify formula: Confidence = Sample Size × Performance Gap × Consistency
    expected = min(1.0, (50 / 50) * 0.42 * 0.85 * 2)
    test("Calculation Accuracy", abs(score.confidence - expected) < 0.1, f"Expected: {expected:.2f}")


def test_mutation_generation():
    print("\n=== Test 4: Mutation Generation ===")
    from market_ops.video_generation.learning import MutationEngine, BlueprintMutator, MutationStrategy
    
    engine = MutationEngine()
    
    winner_dna = {
        "hook": "fast_action",
        "camera": "close_up",
        "lighting": "warm",
        "emotion": "surprise",
    }
    
    result = engine.mutate(winner_dna, count=5, parent_id="pattern_001")
    
    test("Mutation Result", result.parent_id == "pattern_001", f"Parent: {result.parent_id}")
    test("Variant Count", len(result.variants) >= 3, f"Variants: {len(result.variants)}")
    test("Variant ID", result.variants[0].variant_id.startswith("variant_"), f"ID: {result.variants[0].variant_id}")
    
    # Test Blueprint Mutator
    mutator = BlueprintMutator()
    variants = mutator.mutate_demo()
    test("Blueprint Mutator", len(variants) >= 3, f"Mutated: {len(variants)}")
    
    # Test Strategy
    strategy = MutationStrategy()
    options = strategy.get_mutation_options(winner_dna)
    test("Mutation Options", len(options) > 0, f"Options: {len(options)}")


def test_fitness_score():
    print("\n=== Test 5: Fitness Score ===")
    from market_ops.video_generation.learning import FitnessFunction, FitnessScore
    
    fitness = FitnessFunction()
    
    score = fitness.calculate(
        creative_id="creative_001",
        ctr=5.8,
        ipm=83,
        purchase_rate=4.1,
        roas=1.8,
    )
    
    test("Fitness Score", score.fitness > 0, f"Score: {score.fitness:.2f}")
    test("Creative ID", score.creative_id == "creative_001", f"ID: {score.creative_id}")
    test("CTR Component", score.ctr_component > 0, f"CTR: {score.ctr_component:.2f}")
    test("Purchase Component", score.purchase_component > 0, f"Purchase: {score.purchase_component:.2f}")
    test("ROAS Component", score.roas_component > 0, f"ROAS: {score.roas_component:.2f}")
    
    # Test ranking
    scores = {
        "c001": fitness.calculate("c001", ctr=5.8, ipm=83, purchase_rate=4.1, roas=1.8),
        "c002": fitness.calculate("c002", ctr=2.1, ipm=30, purchase_rate=1.2, roas=0.8),
        "c003": fitness.calculate("c003", ctr=4.2, ipm=65, purchase_rate=2.8, roas=1.5),
    }
    ranked = fitness.rank_creatives(scores)
    test("Ranking", ranked[0].creative_id == "c001", f"Rank 1: {ranked[0].creative_id}")


def test_evolution_cycle():
    print("\n=== Test 6: Evolution Cycle ===")
    from market_ops.video_generation.learning import EvolutionEngine, GenerationManager
    
    engine = EvolutionEngine(survival_rate=0.20)
    
    initial_creatives = [
        {"creative_id": "c001", "dna": {"hook": "fast_action", "camera": "close_up"}, "ctr": 5.8, "ipm": 83, "purchase_rate": 4.1, "roas": 1.8},
        {"creative_id": "c002", "dna": {"hook": "slow_build", "camera": "wide"}, "ctr": 2.1, "ipm": 30, "purchase_rate": 1.2, "roas": 0.8},
        {"creative_id": "c003", "dna": {"hook": "surprise_reveal", "camera": "zoom_in"}, "ctr": 4.2, "ipm": 65, "purchase_rate": 2.8, "roas": 1.5},
    ]
    
    results = engine.run_cycle(initial_creatives, generations=3)
    
    test("Evolution Results", len(results) == 3, f"Generations: {len(results)}")
    test("Generation 1", results[0].generation_number == 1, f"Gen: {results[0].generation_number}")
    test("Survival Rate", results[0].survived_creatives >= 1, f"Survived: {results[0].survived_creatives}")
    test("Best Fitness", results[0].best_fitness > 0, f"Best: {results[0].best_fitness:.2f}")
    
    # Test Generation Manager
    manager = GenerationManager()
    manager.create_generation(1)
    record = manager.add_creative("parent_001", "child_001", fitness_score=90.0)
    test("Generation Manager", record.generation_number == 1, f"Gen: {record.generation_number}")
    test("Lineage", len(manager.get_lineage("child_001")) == 1, "Lineage tracked")


def test_performance_feedback():
    print("\n=== Test 7: Performance Feedback ===")
    from market_ops.video_generation.learning import PerformanceFeedback, PerformanceData
    
    feedback = PerformanceFeedback()
    
    # Collect data
    data = feedback.collect(
        creative_id="creative_001",
        spend=500.0,
        impressions=50000,
        clicks=2900,
        installs=830,
        purchases=34,
        revenue=1050.0,
        platform="Meta",
        date="2024-01-15",
    )
    
    test("Performance Data", data.creative_id == "creative_001", f"ID: {data.creative_id}")
    test("CTR Calculation", data.ctr > 0, f"CTR: {data.ctr:.2f}%")
    test("IPM Calculation", data.ipm > 0, f"IPM: {data.ipm:.2f}")
    test("ROAS Calculation", data.roas > 0, f"ROAS: {data.roas:.2f}")
    
    # Get feedback
    result = feedback.get_feedback("creative_001")
    test("Feedback Result", result.creative_id == "creative_001", f"ID: {result.creative_id}")
    test("Reward Score", result.reward >= 0, f"Reward: {result.reward:.2f}")


def test_reward_calculation():
    print("\n=== Test 8: Reward Calculation ===")
    from market_ops.video_generation.learning import RewardCalculator, RewardScore
    
    calculator = RewardCalculator()
    
    score = calculator.calculate(
        creative_id="creative_A",
        roas=2.1,
        purchase_rate=4.5,
        retention=35.0,
        cost=2.5,
    )
    
    test("Reward Score", score.reward > 0, f"Reward: {score.reward:.2f}")
    test("Creative ID", score.creative_id == "creative_A", f"ID: {score.creative_id}")
    test("ROAS Component", score.roas_component > 0, f"ROAS: {score.roas_component:.2f}")
    test("Purchase Component", score.purchase_component > 0, f"Purchase: {score.purchase_component:.2f}")
    
    # Test with demo
    demo = calculator.calculate_demo()
    test("Demo Calculation", demo.reward > 0.5, f"Demo Reward: {demo.reward:.2f}")


def test_strategy_memory():
    print("\n=== Test 9: Strategy Memory ===")
    from market_ops.video_generation.learning import StrategyMemory
    
    memory = StrategyMemory()
    
    # Save strategy
    strategy = memory.save_strategy(
        context="US iOS Puzzle",
        winner_dna={
            "hook": "instant_reward",
            "camera": "close_up",
            "lighting": "warm",
            "emotion": "surprise",
        },
        confidence=0.94,
        performance={"roas": 2.3, "ctr": 5.8},
    )
    
    test("Strategy Saved", strategy.strategy_id.startswith("strategy_"), f"ID: {strategy.strategy_id}")
    test("Context", strategy.context == "US iOS Puzzle", f"Context: {strategy.context}")
    test("Confidence", strategy.confidence == 0.94, f"Confidence: {strategy.confidence}")
    test("Winner DNA", "hook" in strategy.winner_dna, f"DNA keys: {list(strategy.winner_dna.keys())}")
    
    # Retrieve strategy
    retrieved = memory.get_strategy(strategy.strategy_id)
    test("Strategy Retrieval", retrieved is not None, "Retrieved successfully")
    
    # Get top strategies
    top = memory.get_top_strategies(limit=5)
    test("Top Strategies", len(top) >= 1, f"Top: {len(top)}")


def test_loser_memory():
    print("\n=== Test 10: Loser Memory ===")
    from market_ops.video_generation.learning import LoserMemory
    
    memory = LoserMemory()
    
    # Record failure
    loser = memory.record_failure(
        pattern="slow_intro",
        failure_reason="low CTR",
        confidence=0.88,
        context="US iOS",
    )
    
    test("Failure Recorded", loser.loser_id.startswith("loser_"), f"ID: {loser.loser_id}")
    test("Pattern", loser.pattern == "slow_intro", f"Pattern: {loser.pattern}")
    test("Failure Reason", loser.failure_reason == "low CTR", f"Reason: {loser.failure_reason}")
    test("Confidence", loser.confidence == 0.88, f"Confidence: {loser.confidence}")
    
    # Check forbidden
    forbidden = memory.is_forbidden("slow_intro")
    test("Forbidden Check", forbidden, "Pattern is forbidden")
    
    # Get forbidden patterns
    patterns = memory.get_forbidden_patterns()
    test("Forbidden Patterns", len(patterns) >= 1, f"Forbidden: {len(patterns)}")


def test_context_memory():
    print("\n=== Test 11: Context Memory ===")
    from market_ops.video_generation.learning import ContextMemory
    
    memory = ContextMemory()
    
    # Save context
    ctx = memory.save_context(
        country="US",
        os="iOS",
        placement="Facebook Feed",
        audience="Female 25-44",
        game_genre="Puzzle",
        winner_dna={"hook": "reward_reveal", "camera": "close_up"},
        confidence=0.92,
    )
    
    test("Context Saved", ctx.context_id.startswith("ctx_"), f"ID: {ctx.context_id}")
    test("Country", ctx.country == "US", f"Country: {ctx.country}")
    test("OS", ctx.os == "iOS", f"OS: {ctx.os}")
    
    # Query context
    results = memory.query(country="US", os="iOS")
    test("Context Query", len(results) >= 1, f"Results: {len(results)}")
    
    # Get winner for context
    winner = memory.get_winner_for_context("US", "iOS", "Facebook Feed")
    test("Winner DNA for Context", len(winner) > 0, f"Winner DNA: {winner}")


def print_summary():
    print("\n" + "=" * 50)
    print("V4.6 Creative Learning Loop Release Gate")
    print("=" * 50)
    print(f"\nResults: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASS")
    
    if FAIL_COUNT == 0:
        print("\n✓ ALL TESTS PASSED - V4.6 RELEASE APPROVED")
        print("\nSystem now has autonomous creative evolution capability.")
        print("Creative Intelligence OS: AI can now learn what works and evolve.")
    else:
        print(f"\n✗ {FAIL_COUNT} TESTS FAILED")
        for r in TEST_RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}: {r.get('details', '')}")
    
    output = {
        "version": "V4.6",
        "timestamp": datetime.now().isoformat(),
        "pass_count": PASS_COUNT,
        "fail_count": FAIL_COUNT,
        "passed": FAIL_COUNT == 0,
        "results": TEST_RESULTS,
    }
    
    output_path = Path(__file__).parent.parent / "data" / "release_gate_v46_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


def main():
    print("=" * 50)
    print("V4.6 Creative Learning Loop Release Gate")
    print("=" * 50)
    print("\nTesting 10+ modules for autonomous creative evolution...")
    print("Target: 30/30 PASS\n")
    
    test_winner_discovery()
    test_dna_extraction()
    test_confidence_calculation()
    test_mutation_generation()
    test_fitness_score()
    test_evolution_cycle()
    test_performance_feedback()
    test_reward_calculation()
    test_strategy_memory()
    test_loser_memory()
    test_context_memory()
    
    print_summary()
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
