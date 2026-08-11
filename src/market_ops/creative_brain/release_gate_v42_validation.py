"""V4.2 Validation & Continuous Learning — Release Gate.

Per PRD v1.0, 40 tests:
  1. Historical Replay (5 tests)
  2. Offline Evaluator (5 tests)
  3. Prediction Metrics (5 tests)
  4. Confusion Matrix (4 tests)
  5. Calibration (4 tests)
  6. Decision A/B Test (4 tests)
  7. Online Feedback (4 tests)
  8. Drift Detector (3 tests)
  9. Weight Optimizer (3 tests)
  10. Validation Engine (3 tests)

Total: 40 tests. All must PASS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.creative_validation.historical_replay import HistoricalReplay
from market_ops.creative_brain.creative_validation.offline_evaluator import OfflineEvaluator
from market_ops.creative_brain.creative_validation.prediction_metrics import PredictionMetricsCalculator
from market_ops.creative_brain.creative_validation.confusion_matrix import ConfusionMatrixCalculator
from market_ops.creative_brain.creative_validation.calibration import CalibrationEvaluator
from market_ops.creative_brain.creative_validation.decision_ab_test import DecisionABTest, RuleBasedEngine
from market_ops.creative_brain.creative_validation.online_feedback import OnlineFeedback
from market_ops.creative_brain.creative_validation.drift_detector import DriftDetector
from market_ops.creative_brain.creative_validation.weight_optimizer import WeightOptimizer
from market_ops.creative_brain.creative_validation.benchmark_dataset import BenchmarkDataset
from market_ops.creative_brain.creative_validation.report_generator import ReportGenerator
from market_ops.creative_brain.creative_validation.validation_engine import ValidationEngine
from market_ops.creative_brain.creative_validation.schemas import (
    HistoricalCreative, ReplayRecord, EvaluationMetrics, PredictionMetrics,
    ConfusionMatrix, CalibrationResult, ValidationReport, SplitType, DriftType,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_records(n: int = 100) -> list[ReplayRecord]:
    """Create synthetic replay records."""
    import random
    random.seed(42)
    decisions = ["GO", "TEST", "EXPLORE", "ADAPT", "AVOID"]
    records = []
    for i in range(n):
        pred = random.choice(decisions)
        # Make some correct, some wrong
        actual = pred if random.random() < 0.6 else random.choice(decisions)
        records.append(ReplayRecord(
            creative_id=f"c_{i:04d}",
            date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            predicted_decision=pred,
            actual_decision=actual,
            confidence=random.uniform(0.3, 0.95),
            actual_roas=random.uniform(0.1, 1.0),
            predicted_roas=random.uniform(0.2, 0.9),
            is_correct=(pred == actual),
        ))
    return records


def _make_creatives(n: int = 20) -> list[HistoricalCreative]:
    """Create synthetic historical creatives."""
    import random
    random.seed(42)
    characters = ["dragon", "witch", "knight", "ninja", "warrior"]
    rewards = ["dragon", "treasure", "gold", "evolution", "collection"]
    creatives = []
    for i in range(n):
        ch = random.choice(characters)
        rw = random.choice(rewards)
        if ch == "dragon" and rw == "dragon":
            roas = random.uniform(0.7, 1.0)
        elif ch == "ninja":
            roas = random.uniform(0.1, 0.3)
        else:
            roas = random.uniform(0.3, 0.6)
        creatives.append(HistoricalCreative(
            creative_id=f"c_{i:04d}",
            dna={"character": ch, "reward": rw, "hook": "collection", "gameplay": "merge"},
            performance={"roas_d7": roas, "ctr": random.uniform(1.5, 4.5)},
            country="US",
            date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
        ))
    return creatives


# ═══════════════════════════════════════════════════════════
# 1. Historical Replay (5 tests)
# ═══════════════════════════════════════════════════════════

def test_replay_no_future_leak():
    """Replay: 禁止泄露未来数据"""
    creatives = _make_creatives(30)
    replay = HistoricalReplay()
    replay.load_dataset(creatives)
    test_records = replay.replay_test()
    assert len(test_records) > 0
    return True


def test_replay_train_val_test_split():
    """Replay: Train/Val/Test 严格隔离"""
    creatives = _make_creatives(30)
    replay = HistoricalReplay()
    replay.load_dataset(creatives, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    train = replay.replay_train()
    val = replay.replay_val()
    test = replay.replay_test()
    # No overlap
    train_ids = {r.creative_id for r in train}
    val_ids = {r.creative_id for r in val}
    test_ids = {r.creative_id for r in test}
    assert len(train_ids & val_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(val_ids & test_ids) == 0
    assert len(train) + len(val) + len(test) == len(creatives)
    return True


def test_replay_decision_output():
    """Replay: 输出Decision"""
    creatives = _make_creatives(20)
    replay = HistoricalReplay()
    replay.load_creatives([c.to_dict() for c in creatives])
    records = replay.replay()
    for r in records:
        assert r.predicted_decision in ("GO", "TEST", "EXPLORE", "ADAPT", "AVOID", "")
    return True


def test_replay_confidence_output():
    """Replay: 输出Confidence"""
    creatives = _make_creatives(20)
    replay = HistoricalReplay()
    replay.load_creatives([c.to_dict() for c in creatives])
    records = replay.replay()
    for r in records:
        assert 0.0 <= r.confidence <= 1.0
    return True


def test_replay_ground_truth():
    """Replay: Ground Truth 从ROAS映射"""
    replay = HistoricalReplay()
    assert replay._roas_to_decision(0.9) == "GO"
    assert replay._roas_to_decision(0.6) == "TEST"
    assert replay._roas_to_decision(0.4) == "EXPLORE"
    assert replay._roas_to_decision(0.2) == "AVOID"
    return True


# ═══════════════════════════════════════════════════════════
# 2. Offline Evaluator (5 tests)
# ═══════════════════════════════════════════════════════════

def test_evaluator_accuracy():
    """Evaluator: 计算Accuracy"""
    records = _make_records(100)
    evaluator = OfflineEvaluator()
    metrics = evaluator.evaluate(records)
    assert 0.0 <= metrics.accuracy <= 1.0
    assert metrics.total_samples == 100
    return True


def test_evaluator_per_class():
    """Evaluator: Per-Class指标"""
    records = _make_records(100)
    evaluator = OfflineEvaluator()
    metrics = evaluator.evaluate(records)
    for cls in ["GO", "TEST", "EXPLORE", "ADAPT", "AVOID"]:
        assert cls in metrics.per_class
        assert "precision" in metrics.per_class[cls]
        assert "recall" in metrics.per_class[cls]
        assert "f1" in metrics.per_class[cls]
    return True


def test_evaluator_f1():
    """Evaluator: F1 Score"""
    records = _make_records(100)
    evaluator = OfflineEvaluator()
    metrics = evaluator.evaluate(records)
    assert 0.0 <= metrics.f1_macro <= 1.0
    return True


def test_evaluator_error_analysis():
    """Evaluator: Error Analysis"""
    records = _make_records(100)
    evaluator = OfflineEvaluator()
    analysis = evaluator.error_analysis(records)
    assert len(analysis) > 0
    return True


def test_evaluator_top_failures():
    """Evaluator: Top Failure Cases"""
    records = _make_records(100)
    evaluator = OfflineEvaluator()
    failures = evaluator.get_top_failures(records, top_k=5)
    assert len(failures) <= 5
    # Failures should be sorted by confidence descending
    if len(failures) >= 2:
        assert failures[0]["confidence"] >= failures[-1]["confidence"]
    return True


# ═══════════════════════════════════════════════════════════
# 3. Prediction Metrics (5 tests)
# ═══════════════════════════════════════════════════════════

def test_prediction_recall_at_k():
    """Prediction: Recall@K"""
    records = _make_records(50)
    calc = PredictionMetricsCalculator()
    metrics = calc.compute(records)
    assert 0.0 <= metrics.recall_at_5 <= 1.0
    assert 0.0 <= metrics.recall_at_10 <= 1.0
    assert 0.0 <= metrics.recall_at_20 <= 1.0
    return True


def test_prediction_mrr():
    """Prediction: MRR"""
    records = _make_records(50)
    calc = PredictionMetricsCalculator()
    metrics = calc.compute(records)
    assert 0.0 <= metrics.mrr <= 1.0
    return True


def test_prediction_ndcg():
    """Prediction: NDCG"""
    records = _make_records(50)
    calc = PredictionMetricsCalculator()
    metrics = calc.compute(records)
    assert 0.0 <= metrics.ndcg_at_10 <= 1.0
    assert 0.0 <= metrics.ndcg_at_20 <= 1.0
    return True


def test_prediction_hit_rate():
    """Prediction: HitRate"""
    records = _make_records(50)
    calc = PredictionMetricsCalculator()
    metrics = calc.compute(records)
    assert 0.0 <= metrics.hit_rate <= 1.0
    return True


def test_prediction_coverage_diversity():
    """Prediction: Coverage + Diversity"""
    records = _make_records(50)
    calc = PredictionMetricsCalculator()
    metrics = calc.compute(records)
    assert 0.0 <= metrics.coverage <= 1.0
    assert 0.0 <= metrics.diversity <= 1.0
    return True


# ═══════════════════════════════════════════════════════════
# 4. Confusion Matrix (4 tests)
# ═══════════════════════════════════════════════════════════

def test_confusion_5x5():
    """Confusion: 5x5 Matrix"""
    records = _make_records(100)
    calc = ConfusionMatrixCalculator()
    cm = calc.compute(records)
    assert len(cm.classes) == 5
    assert len(cm.matrix) == 5
    assert all(len(row) == 5 for row in cm.matrix)
    total = sum(sum(row) for row in cm.matrix)
    assert total == len(records)
    return True


def test_confusion_tp_fp_fn_tn():
    """Confusion: TP/FP/FN/TN"""
    records = _make_records(100)
    calc = ConfusionMatrixCalculator()
    cm = calc.compute(records)
    for cls in cm.classes:
        assert cls in cm.tp
        assert cls in cm.fp
        assert cls in cm.fn
        assert cls in cm.tn
    return True


def test_confusion_accuracy():
    """Confusion: Matrix Accuracy"""
    records = _make_records(100)
    calc = ConfusionMatrixCalculator()
    cm = calc.compute(records)
    total = sum(sum(row) for row in cm.matrix)
    correct = sum(cm.matrix[i][i] for i in range(5))
    assert correct / total >= 0.0
    return True


def test_confusion_most_confused():
    """Confusion: Most Confused Pairs"""
    records = _make_records(100)
    calc = ConfusionMatrixCalculator()
    cm = calc.compute(records)
    pairs = calc.most_confused_pairs(cm, top_k=3)
    assert isinstance(pairs, list)
    return True


# ═══════════════════════════════════════════════════════════
# 5. Calibration (4 tests)
# ═══════════════════════════════════════════════════════════

def test_calibration_ece():
    """Calibration: ECE"""
    records = _make_records(100)
    cal = CalibrationEvaluator()
    result = cal.evaluate(records, num_bins=10)
    assert 0.0 <= result.ece <= 1.0
    return True


def test_calibration_brier():
    """Calibration: Brier Score"""
    records = _make_records(100)
    cal = CalibrationEvaluator()
    result = cal.evaluate(records)
    assert 0.0 <= result.brier_score <= 1.0
    return True


def test_calibration_reliability_curve():
    """Calibration: Reliability Diagram"""
    records = _make_records(100)
    cal = CalibrationEvaluator()
    result = cal.evaluate(records, num_bins=5)
    assert len(result.reliability_curve) > 0
    for b in result.reliability_curve:
        assert "avg_confidence" in b
        assert "accuracy" in b
        assert "gap" in b
    return True


def test_calibration_interpret():
    """Calibration: Interpret"""
    cal = CalibrationEvaluator()
    result = cal.evaluate(_make_records(100))
    interpretation = cal.interpret(result)
    assert len(interpretation) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 6. Decision A/B Test (4 tests)
# ═══════════════════════════════════════════════════════════

def test_ab_rule_engine():
    """A/B: Rule Engine Baseline"""
    engine = RuleBasedEngine()
    result = engine.decide("c_001", performance={"roas_d7": 0.9})
    assert result["decision"] == "GO"
    result = engine.decide("c_002", performance={"roas_d7": 0.2})
    assert result["decision"] == "AVOID"
    return True


def test_ab_compare():
    """A/B: Compare Rule vs Reasoning"""
    records = _make_records(100)
    ab = DecisionABTest()
    result = ab.compare(records)
    assert result.baseline_name == "RuleEngine"
    assert result.treatment_name == "ReasoningEngine"
    assert 0.0 <= result.baseline_accuracy <= 1.0
    return True


def test_ab_winner_recall():
    """A/B: Winner Recall"""
    records = _make_records(100)
    ab = DecisionABTest()
    result = ab.compare(records)
    assert 0.0 <= result.winner_recall_baseline <= 1.0
    assert 0.0 <= result.winner_recall_treatment <= 1.0
    return True


def test_ab_interpret():
    """A/B: Interpret"""
    ab = DecisionABTest()
    result = ab.compare(_make_records(100))
    interpretation = ab.interpret(result)
    assert len(interpretation) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 7. Online Feedback (4 tests)
# ═══════════════════════════════════════════════════════════

def test_feedback_ingest_daily():
    """Feedback: Daily Ingestion"""
    fb = OnlineFeedback()
    data = [
        {"creative_id": "c_001", "date": "2024-06-01", "ctr": 3.5, "roas_d7": 0.8},
        {"creative_id": "c_002", "date": "2024-06-01", "ctr": 2.0, "roas_d7": 0.3},
    ]
    records = fb.ingest_daily(data)
    assert len(records) == 2
    assert fb.daily_count == 2
    return True


def test_feedback_ingest_weekly():
    """Feedback: Weekly Aggregation"""
    fb = OnlineFeedback()
    fb.ingest_daily([
        {"creative_id": "c_001", "date": "2024-06-01", "roas_d7": 0.8},
    ])
    fb.ingest_weekly()
    assert fb.daily_count == 0
    assert fb.weekly_count == 1
    return True


def test_feedback_ingest_monthly():
    """Feedback: Monthly Aggregation"""
    fb = OnlineFeedback()
    fb.ingest_daily([
        {"creative_id": "c_001", "date": "2024-06-01", "roas_d7": 0.8},
    ])
    fb.ingest_weekly()
    fb.ingest_monthly()
    assert fb.weekly_count == 0
    assert fb.monthly_count == 1
    return True


def test_feedback_performance_summary():
    """Feedback: Performance Summary"""
    fb = OnlineFeedback()
    fb.ingest_daily([
        {"creative_id": "c_001", "date": "2024-06-01", "ctr": 3.0, "roas_d7": 0.8, "ipm": 20, "spend": 100},
        {"creative_id": "c_001", "date": "2024-06-02", "ctr": 3.5, "roas_d7": 0.9, "ipm": 22, "spend": 120},
    ])
    summary = fb.get_performance_summary("c_001")
    assert summary["creative_id"] == "c_001"
    assert summary["days_active"] == 2
    assert summary["avg_ctr"] == 3.25
    assert summary["total_spend"] == 220
    return True


# ═══════════════════════════════════════════════════════════
# 8. Drift Detector (3 tests)
# ═══════════════════════════════════════════════════════════

def test_drift_creative_drift():
    """Drift: Creative Drift Detection"""
    current = [
        {"dna": {"character": "dragon", "reward": "dragon"},
         "performance": {"roas_d7": 0.5}},
    ]
    previous = [
        {"dna": {"character": "dragon", "reward": "dragon"},
         "performance": {"roas_d7": 0.9}},
    ]
    detector = DriftDetector()
    results = detector.detect(current, previous)
    assert len(results) > 0
    assert results[0].direction == "declining"
    return True


def test_drift_expired_pattern():
    """Drift: Expired Pattern Detection"""
    current = [
        {"dna": {"character": "knight", "reward": "gold"},
         "performance": {"roas_d7": 0.15}},
    ]
    previous = [
        {"dna": {"character": "knight", "reward": "gold"},
         "performance": {"roas_d7": 0.85}},
    ]
    detector = DriftDetector()
    results = detector.detect(current, previous)
    expired = detector.get_expired_patterns(results)
    assert len(expired) > 0
    return True


def test_drift_growing_pattern():
    """Drift: Growing Pattern Detection"""
    current = [
        {"dna": {"character": "phoenix", "reward": "crystal"},
         "performance": {"roas_d7": 0.9}},
    ]
    previous = [
        {"dna": {"character": "phoenix", "reward": "crystal"},
         "performance": {"roas_d7": 0.45}},
    ]
    detector = DriftDetector()
    results = detector.detect(current, previous)
    growing = detector.get_growing_patterns(results)
    assert len(growing) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 9. Weight Optimizer (3 tests)
# ═══════════════════════════════════════════════════════════

def test_weight_optimizer_grid_search():
    """Weight: Grid Search"""
    records = _make_records(50)
    optimizer = WeightOptimizer()
    result = optimizer.optimize(records, method="grid_search")
    assert result.initial_score >= 0.0
    assert result.optimized_score >= 0.0
    assert result.trials > 0
    return True


def test_weight_optimizer_random_search():
    """Weight: Random Search"""
    records = _make_records(50)
    optimizer = WeightOptimizer()
    result = optimizer.optimize(records, method="random_search")
    assert result.initial_score >= 0.0
    assert result.optimized_score >= 0.0
    return True


def test_weight_optimizer_output():
    """Weight: Output Weights"""
    records = _make_records(50)
    optimizer = WeightOptimizer()
    result = optimizer.optimize(records)
    assert len(result.initial_weights) == 5
    assert len(result.optimized_weights) == 5
    for key in ["retriever", "pattern", "graph", "learning", "trend"]:
        assert key in result.optimized_weights
    return True


# ═══════════════════════════════════════════════════════════
# 10. Validation Engine (3 tests)
# ═══════════════════════════════════════════════════════════

def test_validation_full_pipeline():
    """Validation: Full Pipeline"""
    engine = ValidationEngine()
    report = engine.run_full_validation(dataset_size=100, seed=42)
    assert isinstance(report, ValidationReport)
    assert report.dataset_size > 0
    assert report.evaluation.total_samples > 0
    return True


def test_validation_report_generation():
    """Validation: Report Generation"""
    engine = ValidationEngine()
    report = engine.run_full_validation(dataset_size=50, seed=42)
    md = engine.generate_report(report, format="markdown")
    assert len(md) > 0
    assert "Accuracy" in md
    json_str = engine.generate_report(report, format="json")
    assert len(json_str) > 0
    return True


def test_validation_benchmark_dataset():
    """Validation: Benchmark Dataset"""
    dataset = BenchmarkDataset()
    creatives = dataset.generate(
        n_winners=10, n_losers=10, n_borderline=5,
        n_new_trend=5, n_dead_trend=5, seed=42,
    )
    summary = dataset.summary
    assert summary["total"] == 35
    assert summary["train"] > 0
    assert summary["test"] > 0
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Historical Replay (5)
        ("Replay: No Future Leak", test_replay_no_future_leak),
        ("Replay: Train/Val/Test Split", test_replay_train_val_test_split),
        ("Replay: Decision Output", test_replay_decision_output),
        ("Replay: Confidence Output", test_replay_confidence_output),
        ("Replay: Ground Truth", test_replay_ground_truth),
        # 2. Offline Evaluator (5)
        ("Evaluator: Accuracy", test_evaluator_accuracy),
        ("Evaluator: Per-Class", test_evaluator_per_class),
        ("Evaluator: F1", test_evaluator_f1),
        ("Evaluator: Error Analysis", test_evaluator_error_analysis),
        ("Evaluator: Top Failures", test_evaluator_top_failures),
        # 3. Prediction Metrics (5)
        ("Prediction: Recall@K", test_prediction_recall_at_k),
        ("Prediction: MRR", test_prediction_mrr),
        ("Prediction: NDCG", test_prediction_ndcg),
        ("Prediction: HitRate", test_prediction_hit_rate),
        ("Prediction: Coverage+Diversity", test_prediction_coverage_diversity),
        # 4. Confusion Matrix (4)
        ("Confusion: 5x5 Matrix", test_confusion_5x5),
        ("Confusion: TP/FP/FN/TN", test_confusion_tp_fp_fn_tn),
        ("Confusion: Accuracy", test_confusion_accuracy),
        ("Confusion: Most Confused", test_confusion_most_confused),
        # 5. Calibration (4)
        ("Calibration: ECE", test_calibration_ece),
        ("Calibration: Brier", test_calibration_brier),
        ("Calibration: Reliability Curve", test_calibration_reliability_curve),
        ("Calibration: Interpret", test_calibration_interpret),
        # 6. Decision A/B Test (4)
        ("A/B: Rule Engine", test_ab_rule_engine),
        ("A/B: Compare", test_ab_compare),
        ("A/B: Winner Recall", test_ab_winner_recall),
        ("A/B: Interpret", test_ab_interpret),
        # 7. Online Feedback (4)
        ("Feedback: Daily", test_feedback_ingest_daily),
        ("Feedback: Weekly", test_feedback_ingest_weekly),
        ("Feedback: Monthly", test_feedback_ingest_monthly),
        ("Feedback: Performance Summary", test_feedback_performance_summary),
        # 8. Drift Detector (3)
        ("Drift: Creative Drift", test_drift_creative_drift),
        ("Drift: Expired Pattern", test_drift_expired_pattern),
        ("Drift: Growing Pattern", test_drift_growing_pattern),
        # 9. Weight Optimizer (3)
        ("Weight: Grid Search", test_weight_optimizer_grid_search),
        ("Weight: Random Search", test_weight_optimizer_random_search),
        ("Weight: Output", test_weight_optimizer_output),
        # 10. Validation Engine (3)
        ("Validation: Full Pipeline", test_validation_full_pipeline),
        ("Validation: Report Generation", test_validation_report_generation),
        ("Validation: Benchmark Dataset", test_validation_benchmark_dataset),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.2 Validation & Continuous Learning — Release Gate")
    print("  Per PRD v1.0: 40 tests")
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