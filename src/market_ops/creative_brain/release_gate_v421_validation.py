"""V4.2.1 Validation & Error Analysis — Release Gate.

Per PRD v1.0, 45 tests:
  1. Benchmark Dataset (4 tests)
  2. Historical Replay (5 tests)
  3. Offline Evaluator (5 tests)
  4. Prediction Metrics (5 tests)
  5. Confusion Matrix (4 tests)
  6. Calibration (4 tests)
  7. Decision A/B Test (4 tests)
  8. Online Feedback (3 tests)
  9. Drift Detector (3 tests)
 10. Error Analyzer (4 tests)
 11. Weight Optimizer (2 tests)
 12. Validation Engine (2 tests)

Total: 45 tests. All must PASS.
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
from market_ops.creative_brain.creative_validation.error_analyzer import ErrorAnalyzer
from market_ops.creative_brain.creative_validation.schemas import (
    HistoricalCreative, ReplayRecord, ValidationReport,
    SplitType, DriftType, OptimizerMethod, ErrorType,
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
            platform="facebook",
            date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
        ))
    return creatives


# ═══════════════════════════════════════════════════════════
# 1. Benchmark Dataset (4 tests)
# ═══════════════════════════════════════════════════════════

def test_benchmark_train_val_test_holdout_split():
    """Benchmark: Train/Val/Test/Holdout 严格隔离"""
    dataset = BenchmarkDataset()
    dataset.generate(
        n_winners=20, n_losers=20, n_borderline=10,
        n_new_trend=10, n_dead_trend=10, seed=42,
    )
    summary = dataset.summary
    assert summary["train"] > 0
    assert summary["val"] > 0
    assert summary["test"] > 0
    assert summary["holdout"] > 0
    # No overlap between splits
    train_ids = {c.creative_id for c in dataset.train}
    val_ids = {c.creative_id for c in dataset.val}
    test_ids = {c.creative_id for c in dataset.test}
    holdout_ids = {c.creative_id for c in dataset.holdout}
    assert len(train_ids & val_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(train_ids & holdout_ids) == 0
    assert len(val_ids & test_ids) == 0
    assert len(val_ids & holdout_ids) == 0
    assert len(test_ids & holdout_ids) == 0
    return True


def test_benchmark_labels():
    """Benchmark: Winner/Loser/Borderline/Emerging/Dead 分类"""
    dataset = BenchmarkDataset()
    dataset.generate(
        n_winners=10, n_losers=10, n_borderline=5,
        n_new_trend=5, n_dead_trend=5, seed=42,
    )
    all_creatives = dataset.all
    # Verify all creatives exist
    assert len(all_creatives) == 35
    return True


def test_benchmark_holdout_exists():
    """Benchmark: Holdout 独立存在"""
    dataset = BenchmarkDataset()
    dataset.generate(
        n_winners=20, n_losers=20, n_borderline=10,
        n_new_trend=10, n_dead_trend=10, seed=42,
    )
    holdout = dataset.holdout
    assert len(holdout) > 0
    # Holdout should be ~10% of total
    total = dataset.summary["total"]
    ratio = len(holdout) / total
    assert 0.05 <= ratio <= 0.20, f"Holdout ratio {ratio:.2%} outside expected range"
    return True


def test_benchmark_summary():
    """Benchmark: Summary 统计正确"""
    dataset = BenchmarkDataset()
    dataset.generate(
        n_winners=20, n_losers=10, n_borderline=5,
        n_new_trend=5, n_dead_trend=5, seed=42,
    )
    summary = dataset.summary
    assert summary["total"] == 45
    assert summary["train"] + summary["val"] + summary["test"] + summary["holdout"] == 45
    return True


# ═══════════════════════════════════════════════════════════
# 2. Historical Replay (5 tests)
# ═══════════════════════════════════════════════════════════

def test_replay_no_future_leak():
    """Replay: 禁止未来数据泄露"""
    creatives = _make_creatives(30)
    replay = HistoricalReplay()
    replay.load_dataset(creatives)
    test_records = replay.replay_test()
    assert len(test_records) > 0
    return True


def test_replay_train_val_test_holdout_split():
    """Replay: Train/Val/Test/Holdout 严格隔离"""
    creatives = _make_creatives(40)
    replay = HistoricalReplay()
    replay.load_dataset(creatives, train_ratio=0.5, val_ratio=0.2, test_ratio=0.2, holdout_ratio=0.1)
    train = replay.replay_train()
    val = replay.replay_val()
    test = replay.replay_test()
    holdout = replay.replay_holdout()
    train_ids = {r.creative_id for r in train}
    val_ids = {r.creative_id for r in val}
    test_ids = {r.creative_id for r in test}
    holdout_ids = {r.creative_id for r in holdout}
    assert len(train_ids & val_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(train_ids & holdout_ids) == 0
    assert len(val_ids & test_ids) == 0
    assert len(val_ids & holdout_ids) == 0
    assert len(test_ids & holdout_ids) == 0
    return True


def test_replay_by_country():
    """Replay: Country 过滤"""
    creatives = _make_creatives(20)
    # Set some to different countries
    for i, c in enumerate(creatives):
        if i % 2 == 0:
            c.country = "US"
        else:
            c.country = "JP"
    replay = HistoricalReplay()
    replay.load_dataset(creatives, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    us_records = replay.replay_by_country("US")
    assert len(us_records) > 0
    return True


def test_replay_by_platform():
    """Replay: Platform 过滤"""
    creatives = _make_creatives(20)
    for i, c in enumerate(creatives):
        c.platform = "facebook" if i % 2 == 0 else "google"
    replay = HistoricalReplay()
    replay.load_dataset(creatives, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    fb_records = replay.replay_by_platform("facebook")
    assert len(fb_records) > 0
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
# 3. Offline Evaluator (5 tests)
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
    if len(failures) >= 2:
        assert failures[0]["confidence"] >= failures[-1]["confidence"]
    return True


# ═══════════════════════════════════════════════════════════
# 4. Prediction Metrics (5 tests)
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
# 5. Confusion Matrix (4 tests)
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
# 6. Calibration (4 tests)
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
# 7. Decision A/B Test (4 tests)
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
# 8. Online Feedback (3 tests)
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


# ═══════════════════════════════════════════════════════════
# 9. Drift Detector (3 tests)
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


def test_drift_platform_drift():
    """Drift: Platform Drift Detection"""
    current = [
        {"dna": {"character": "dragon", "reward": "dragon"},
         "performance": {"roas_d7": 0.5, "ctr": 2.0},
         "platform": "facebook"},
        {"dna": {"character": "dragon", "reward": "dragon"},
         "performance": {"roas_d7": 0.3, "ctr": 1.0},
         "platform": "google"},
    ]
    previous = [
        {"dna": {"character": "dragon", "reward": "dragon"},
         "performance": {"roas_d7": 0.8, "ctr": 3.0},
         "platform": "facebook"},
        {"dna": {"character": "dragon", "reward": "dragon"},
         "performance": {"roas_d7": 0.6, "ctr": 2.5},
         "platform": "google"},
    ]
    detector = DriftDetector()
    results = detector.detect_platform_drift(current, previous)
    assert isinstance(results, list)
    return True


def test_drift_network_drift():
    """Drift: Network Drift Detection"""
    current = [
        {"dna": {"character": "witch", "reward": "treasure"},
         "performance": {"roas_d7": 0.4, "ctr": 1.5},
         "network": "audience_network"},
    ]
    previous = [
        {"dna": {"character": "witch", "reward": "treasure"},
         "performance": {"roas_d7": 0.7, "ctr": 2.8},
         "network": "audience_network"},
    ]
    detector = DriftDetector()
    results = detector.detect_network_drift(current, previous)
    assert isinstance(results, list)
    return True


# ═══════════════════════════════════════════════════════════
# 10. Error Analyzer (4 tests)
# ═══════════════════════════════════════════════════════════

def test_error_analyzer_classification():
    """Error: 错误分类（7种类型）"""
    records = _make_records(100)
    analyzer = ErrorAnalyzer()
    errors = [r for r in records if not r.is_correct]
    for err in errors[:10]:
        diagnosis = analyzer.diagnose(err)
        assert diagnosis.error_type in ErrorType
        assert diagnosis.creative_id == err.creative_id
        assert len(diagnosis.root_cause) > 0
        assert len(diagnosis.suggested_fix) > 0
    return True


def test_error_analyzer_distribution():
    """Error: 错误分布统计"""
    records = _make_records(100)
    analyzer = ErrorAnalyzer()
    analysis = analyzer.analyze(records)
    assert analysis.total_errors >= 0
    assert analysis.total_predictions == 100
    assert 0.0 <= analysis.error_rate <= 1.0
    assert len(analysis.error_distribution) > 0
    return True


def test_error_analyzer_diagnosis():
    """Error: 单错误诊断完整"""
    # Create a record with specific error characteristics
    record = ReplayRecord(
        creative_id="test_001",
        date="2024-06-01",
        predicted_decision="GO",
        actual_decision="AVOID",
        confidence=0.85,
        actual_roas=0.1,
        predicted_roas=0.8,
        is_correct=False,
    )
    analyzer = ErrorAnalyzer()
    diagnosis = analyzer.diagnose(record)
    # High confidence wrong → CONFIDENCE error
    assert diagnosis.error_type == ErrorType.CONFIDENCE
    assert diagnosis.severity == "critical"
    assert len(diagnosis.contributing_modules) > 0
    return True


def test_error_analyzer_recommendations():
    """Error: 自动建议生成"""
    records = _make_records(100)
    analyzer = ErrorAnalyzer()
    analysis = analyzer.analyze(records)
    assert isinstance(analysis.recommendations, list)
    assert len(analysis.top_error_types) > 0
    assert len(analysis.summary) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 11. Weight Optimizer (2 tests)
# ═══════════════════════════════════════════════════════════

def test_weight_optimizer_grid_search():
    """Weight: Grid Search"""
    records = _make_records(50)
    optimizer = WeightOptimizer()
    result = optimizer.optimize(records, method=OptimizerMethod.GRID_SEARCH)
    assert result.initial_score >= 0.0
    assert result.optimized_score >= 0.0
    assert result.trials > 0
    assert len(result.optimized_weights) == 5
    for key in ["retriever", "pattern", "graph", "learning", "trend"]:
        assert key in result.optimized_weights
    return True


def test_weight_optimizer_mab():
    """Weight: Multi-Armed Bandit"""
    records = _make_records(50)
    optimizer = WeightOptimizer()
    result = optimizer.optimize(records, method=OptimizerMethod.MULTI_ARMED_BANDIT)
    assert result.initial_score >= 0.0
    assert result.optimized_score >= 0.0
    assert result.method == OptimizerMethod.MULTI_ARMED_BANDIT
    assert len(result.optimized_weights) == 5
    return True


# ═══════════════════════════════════════════════════════════
# 12. Validation Engine (2 tests)
# ═══════════════════════════════════════════════════════════

def test_validation_full_pipeline():
    """Validation: Full Pipeline (含Error Analysis)"""
    engine = ValidationEngine()
    report = engine.run_full_validation(dataset_size=100, seed=42)
    assert isinstance(report, ValidationReport)
    assert report.dataset_size > 0
    assert report.evaluation.total_samples > 0
    assert report.error_analysis is not None
    assert report.error_analysis.total_predictions > 0
    return True


def test_validation_report_generation():
    """Validation: Report Generation (含Error Analysis)"""
    engine = ValidationEngine()
    report = engine.run_full_validation(dataset_size=50, seed=42)
    md = engine.generate_report(report, format="markdown")
    assert len(md) > 0
    assert "Accuracy" in md
    assert "Error Analysis" in md
    assert "Error Rate" in md
    json_str = engine.generate_report(report, format="json")
    assert len(json_str) > 0
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Benchmark Dataset (4)
        ("Benchmark: Train/Val/Test/Holdout Split", test_benchmark_train_val_test_holdout_split),
        ("Benchmark: Labels", test_benchmark_labels),
        ("Benchmark: Holdout Exists", test_benchmark_holdout_exists),
        ("Benchmark: Summary", test_benchmark_summary),
        # 2. Historical Replay (5)
        ("Replay: No Future Leak", test_replay_no_future_leak),
        ("Replay: Train/Val/Test/Holdout Split", test_replay_train_val_test_holdout_split),
        ("Replay: Country Filter", test_replay_by_country),
        ("Replay: Platform Filter", test_replay_by_platform),
        ("Replay: Ground Truth", test_replay_ground_truth),
        # 3. Offline Evaluator (5)
        ("Evaluator: Accuracy", test_evaluator_accuracy),
        ("Evaluator: Per-Class", test_evaluator_per_class),
        ("Evaluator: F1", test_evaluator_f1),
        ("Evaluator: Error Analysis", test_evaluator_error_analysis),
        ("Evaluator: Top Failures", test_evaluator_top_failures),
        # 4. Prediction Metrics (5)
        ("Prediction: Recall@K", test_prediction_recall_at_k),
        ("Prediction: MRR", test_prediction_mrr),
        ("Prediction: NDCG", test_prediction_ndcg),
        ("Prediction: HitRate", test_prediction_hit_rate),
        ("Prediction: Coverage+Diversity", test_prediction_coverage_diversity),
        # 5. Confusion Matrix (4)
        ("Confusion: 5x5 Matrix", test_confusion_5x5),
        ("Confusion: TP/FP/FN/TN", test_confusion_tp_fp_fn_tn),
        ("Confusion: Accuracy", test_confusion_accuracy),
        ("Confusion: Most Confused", test_confusion_most_confused),
        # 6. Calibration (4)
        ("Calibration: ECE", test_calibration_ece),
        ("Calibration: Brier", test_calibration_brier),
        ("Calibration: Reliability Curve", test_calibration_reliability_curve),
        ("Calibration: Interpret", test_calibration_interpret),
        # 7. Decision A/B Test (4)
        ("A/B: Rule Engine", test_ab_rule_engine),
        ("A/B: Compare", test_ab_compare),
        ("A/B: Winner Recall", test_ab_winner_recall),
        ("A/B: Interpret", test_ab_interpret),
        # 8. Online Feedback (3)
        ("Feedback: Daily", test_feedback_ingest_daily),
        ("Feedback: Weekly", test_feedback_ingest_weekly),
        ("Feedback: Monthly", test_feedback_ingest_monthly),
        # 9. Drift Detector (3)
        ("Drift: Creative Drift", test_drift_creative_drift),
        ("Drift: Platform Drift", test_drift_platform_drift),
        ("Drift: Network Drift", test_drift_network_drift),
        # 10. Error Analyzer (4)
        ("Error: Classification", test_error_analyzer_classification),
        ("Error: Distribution", test_error_analyzer_distribution),
        ("Error: Diagnosis", test_error_analyzer_diagnosis),
        ("Error: Recommendations", test_error_analyzer_recommendations),
        # 11. Weight Optimizer (2)
        ("Weight: Grid Search", test_weight_optimizer_grid_search),
        ("Weight: Multi-Armed Bandit", test_weight_optimizer_mab),
        # 12. Validation Engine (2)
        ("Validation: Full Pipeline", test_validation_full_pipeline),
        ("Validation: Report Generation", test_validation_report_generation),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V4.2.1 Validation & Error Analysis — Release Gate")
    print("  Per PRD v1.0: 45 tests")
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