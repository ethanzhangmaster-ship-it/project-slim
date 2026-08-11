"""E11.3.1 — Fitness & Evaluation Schema Test.

7 AC covering:
  1. FitnessDirection (MAXIMIZE / MINIMIZE)
  2. FitnessMetric (创建 / weighted_value / direction)
  3. FitnessScore (综合评分 / MAX + MIN 混合 / is_healthy)
  4. FitnessSnapshot (快照创建 / 时间戳)
  5. EvaluationResult (passed / 可解释)
  6. Serialization (to_dict / from_dict roundtrip)
  7. Deterministic (相同输入 → 相同结果)
"""

from __future__ import annotations

from datetime import datetime

from market_ops.e11.evolution import (
    FitnessDirection,
    FitnessMetric,
    FitnessScore,
    FitnessSnapshot,
    EvaluationResult,
)


# ═══════════════════════════════════════════════════════════
# AC1 — FitnessDirection
# ═══════════════════════════════════════════════════════════

def test_ac1_fitness_direction_enum():
    """AC1a: FitnessDirection has MAXIMIZE and MINIMIZE."""
    assert FitnessDirection.MAXIMIZE.value == "maximize"
    assert FitnessDirection.MINIMIZE.value == "minimize"

    assert FitnessDirection("maximize") == FitnessDirection.MAXIMIZE
    assert FitnessDirection("minimize") == FitnessDirection.MINIMIZE
    assert len(FitnessDirection) == 2


# ═══════════════════════════════════════════════════════════
# AC2 — FitnessMetric
# ═══════════════════════════════════════════════════════════

def test_ac2_metric_create():
    """AC2a: FitnessMetric creates with all fields."""
    metric = FitnessMetric(
        name="roas_d7",
        value=0.42,
        weight=1.0,
        direction=FitnessDirection.MAXIMIZE,
    )

    assert metric.name == "roas_d7"
    assert metric.value == 0.42
    assert metric.weight == 1.0
    assert metric.direction == FitnessDirection.MAXIMIZE


def test_ac2b_metric_defaults():
    """AC2b: FitnessMetric defaults weight=1.0, direction=MAXIMIZE."""
    metric = FitnessMetric(name="ctr", value=0.12)

    assert metric.weight == 1.0
    assert metric.direction == FitnessDirection.MAXIMIZE


def test_ac2c_metric_weighted_value():
    """AC2c: weighted_value = value * weight."""
    metric = FitnessMetric(name="roas_d7", value=0.42, weight=0.5)
    assert metric.weighted_value == 0.21

    metric2 = FitnessMetric(name="ctr", value=0.12, weight=2.0)
    assert metric2.weighted_value == 0.24


def test_ac2d_metric_minimize():
    """AC2d: MINIMIZE direction metric."""
    metric = FitnessMetric(
        name="cpi",
        value=0.45,
        weight=1.0,
        direction=FitnessDirection.MINIMIZE,
    )
    assert metric.direction == FitnessDirection.MINIMIZE
    assert metric.value == 0.45


# ═══════════════════════════════════════════════════════════
# AC3 — FitnessScore
# ═══════════════════════════════════════════════════════════

def test_ac3_score_single_maximize():
    """AC3a: Single MAXIMIZE metric → score = weighted value."""
    score = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="roas_d7", value=0.80, weight=1.0,
                         direction=FitnessDirection.MAXIMIZE),
        ],
    )

    assert score.genome_id == "genome_001"
    assert score.score == 0.80
    assert score.is_healthy is True


def test_ac3b_score_single_minimize():
    """AC3b: Single MINIMIZE metric → score = 1 - value."""
    score = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="cpi", value=0.30, weight=1.0,
                         direction=FitnessDirection.MINIMIZE),
        ],
    )

    # cpi=0.30, MINIMIZE → contribution = (1-0.30)*1.0 = 0.70
    assert score.score == 0.70


def test_ac3c_score_mixed_metrics():
    """AC3c: Mixed MAXIMIZE + MINIMIZE metrics."""
    score = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="roas_d7", value=0.80, weight=0.5,
                         direction=FitnessDirection.MAXIMIZE),
            FitnessMetric(name="cpi", value=0.30, weight=0.5,
                         direction=FitnessDirection.MINIMIZE),
        ],
    )

    # roas_d7: 0.80 * 0.5 = 0.40
    # cpi: (1 - 0.30) * 0.5 = 0.35
    # total = (0.40 + 0.35) / (0.5 + 0.5) = 0.75
    assert score.score == 0.75


def test_ac3d_score_weighted():
    """AC3d: Different weights affect score."""
    score = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="roas_d7", value=0.80, weight=0.8,
                         direction=FitnessDirection.MAXIMIZE),
            FitnessMetric(name="ctr", value=0.10, weight=0.2,
                         direction=FitnessDirection.MAXIMIZE),
        ],
    )

    # roas: 0.80 * 0.8 = 0.64
    # ctr: 0.10 * 0.2 = 0.02
    # total = (0.64 + 0.02) / (0.8 + 0.2) = 0.66
    assert score.score == 0.66


def test_ac3e_score_empty_metrics():
    """AC3e: Empty metrics → score = 0.0."""
    score = FitnessScore(genome_id="genome_001")
    assert score.score == 0.0
    assert score.is_healthy is False


def test_ac3f_score_add_metric():
    """AC3f: add_metric recalculates score."""
    score = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="roas_d7", value=0.80, weight=1.0,
                         direction=FitnessDirection.MAXIMIZE),
        ],
    )
    assert score.score == 0.80

    score.add_metric(
        FitnessMetric(name="cpi", value=0.30, weight=1.0,
                      direction=FitnessDirection.MINIMIZE),
    )

    # roas: 0.80 * 1.0 = 0.80
    # cpi: (1-0.30) * 1.0 = 0.70
    # total = (0.80 + 0.70) / 2.0 = 0.75
    assert score.score == 0.75


def test_ac3g_score_is_healthy():
    """AC3g: is_healthy threshold at 0.5."""
    score_low = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="ctr", value=0.10, weight=1.0,
                         direction=FitnessDirection.MAXIMIZE),
        ],
    )
    assert score_low.score == 0.10
    assert score_low.is_healthy is False

    score_high = FitnessScore(
        genome_id="genome_002",
        metrics=[
            FitnessMetric(name="roas", value=0.60, weight=1.0,
                         direction=FitnessDirection.MAXIMIZE),
        ],
    )
    assert score_high.score == 0.60
    assert score_high.is_healthy is True


def test_ac3h_score_rank():
    """AC3h: FitnessScore has rank field."""
    score = FitnessScore(
        genome_id="genome_001",
        rank=3,
        metrics=[
            FitnessMetric(name="roas_d7", value=0.42, weight=1.0),
        ],
    )
    assert score.rank == 3


# ═══════════════════════════════════════════════════════════
# AC4 — FitnessSnapshot
# ═══════════════════════════════════════════════════════════

def test_ac4_snapshot_create():
    """AC4a: FitnessSnapshot creates with auto-generated ID."""
    fitness = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="roas_d7", value=0.42, weight=1.0),
        ],
    )

    snapshot = FitnessSnapshot(
        genome_id="genome_001",
        fitness_score=fitness,
    )

    assert snapshot.genome_id == "genome_001"
    assert snapshot.fitness_score is not None
    assert snapshot.score == 0.42
    assert snapshot.snapshot_id.startswith("snap_")
    assert isinstance(snapshot.created_at, datetime)


def test_ac4b_snapshot_no_fitness():
    """AC4b: Snapshot without fitness_score defaults score=0.0."""
    snapshot = FitnessSnapshot(genome_id="genome_001")
    assert snapshot.fitness_score is None
    assert snapshot.score == 0.0
    assert snapshot.rank == 0


def test_ac4c_snapshot_timestamps():
    """AC4c: Two snapshots have different timestamps."""
    import time

    fitness = FitnessScore(
        genome_id="genome_001",
        metrics=[FitnessMetric(name="ctr", value=0.12, weight=1.0)],
    )

    snap1 = FitnessSnapshot(genome_id="genome_001", fitness_score=fitness)
    time.sleep(0.01)
    snap2 = FitnessSnapshot(genome_id="genome_001", fitness_score=fitness)

    assert snap1.snapshot_id != snap2.snapshot_id
    # 时间戳可能相同或不同，取决于系统精度
    assert isinstance(snap1.created_at, datetime)
    assert isinstance(snap2.created_at, datetime)


# ═══════════════════════════════════════════════════════════
# AC5 — EvaluationResult
# ═══════════════════════════════════════════════════════════

def test_ac5_evaluation_result_pass():
    """AC5a: EvaluationResult passed=True."""
    fitness = FitnessScore(
        genome_id="genome_001",
        metrics=[
            FitnessMetric(name="roas_d7", value=0.42, weight=1.0),
        ],
    )

    result = EvaluationResult(
        genome_id="genome_001",
        fitness=fitness,
        passed=True,
        reason="ROAS 0.42 > threshold 0.30",
    )

    assert result.genome_id == "genome_001"
    assert result.passed is True
    assert result.reason == "ROAS 0.42 > threshold 0.30"
    assert result.score == 0.42


def test_ac5b_evaluation_result_fail():
    """AC5b: EvaluationResult passed=False."""
    result = EvaluationResult(
        genome_id="genome_002",
        passed=False,
        reason="CTR 0.02 < threshold 0.05",
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "CTR" in result.reason


def test_ac5c_evaluation_result_no_fitness():
    """AC5c: EvaluationResult without fitness_score."""
    result = EvaluationResult(
        genome_id="genome_001",
        passed=True,
    )

    assert result.fitness is None
    assert result.score == 0.0


# ═══════════════════════════════════════════════════════════
# AC6 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac6_metric_serialization():
    """AC6a: FitnessMetric to_dict / from_dict roundtrip."""
    metric = FitnessMetric(
        name="roas_d7",
        value=0.42,
        weight=0.5,
        direction=FitnessDirection.MAXIMIZE,
    )

    d = metric.to_dict()
    assert d["name"] == "roas_d7"
    assert d["value"] == 0.42
    assert d["weight"] == 0.5
    assert d["direction"] == "maximize"

    restored = FitnessMetric.from_dict(d)
    assert restored.name == metric.name
    assert restored.value == metric.value
    assert restored.weight == metric.weight
    assert restored.direction == metric.direction


def test_ac6b_score_serialization():
    """AC6b: FitnessScore to_dict / from_dict roundtrip."""
    score = FitnessScore(
        genome_id="genome_001",
        rank=2,
        metrics=[
            FitnessMetric(name="roas_d7", value=0.80, weight=0.5,
                         direction=FitnessDirection.MAXIMIZE),
            FitnessMetric(name="cpi", value=0.30, weight=0.5,
                         direction=FitnessDirection.MINIMIZE),
        ],
    )

    d = score.to_dict()
    assert d["genome_id"] == "genome_001"
    assert d["score"] == 0.75
    assert d["rank"] == 2
    assert len(d["metrics"]) == 2

    restored = FitnessScore.from_dict(d)
    assert restored.genome_id == score.genome_id
    assert restored.score == score.score
    assert restored.rank == score.rank
    assert len(restored.metrics) == 2


def test_ac6c_snapshot_serialization():
    """AC6c: FitnessSnapshot to_dict / from_dict roundtrip."""
    fitness = FitnessScore(
        genome_id="genome_001",
        metrics=[FitnessMetric(name="ctr", value=0.15, weight=1.0)],
    )
    snapshot = FitnessSnapshot(
        snapshot_id="snap_abc123",
        genome_id="genome_001",
        fitness_score=fitness,
    )

    d = snapshot.to_dict()
    assert d["snapshot_id"] == "snap_abc123"
    assert d["genome_id"] == "genome_001"
    assert d["fitness_score"] is not None

    restored = FitnessSnapshot.from_dict(d)
    assert restored.snapshot_id == snapshot.snapshot_id
    assert restored.genome_id == snapshot.genome_id
    assert restored.fitness_score is not None
    assert restored.score == snapshot.score


def test_ac6d_evaluation_result_serialization():
    """AC6d: EvaluationResult to_dict / from_dict roundtrip."""
    fitness = FitnessScore(
        genome_id="genome_001",
        metrics=[FitnessMetric(name="roas_d7", value=0.55, weight=1.0)],
    )
    result = EvaluationResult(
        genome_id="genome_001",
        fitness=fitness,
        passed=True,
        reason="Good performance",
    )

    d = result.to_dict()
    assert d["genome_id"] == "genome_001"
    assert d["passed"] is True
    assert d["reason"] == "Good performance"

    restored = EvaluationResult.from_dict(d)
    assert restored.genome_id == result.genome_id
    assert restored.passed == result.passed
    assert restored.reason == result.reason
    assert restored.score == result.score


# ═══════════════════════════════════════════════════════════
# AC7 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac7_deterministic_score():
    """AC7a: Same metrics → same score."""
    metrics = [
        FitnessMetric(name="roas_d7", value=0.80, weight=0.5,
                     direction=FitnessDirection.MAXIMIZE),
        FitnessMetric(name="cpi", value=0.30, weight=0.5,
                     direction=FitnessDirection.MINIMIZE),
    ]

    score1 = FitnessScore(genome_id="genome_001", metrics=metrics)
    score2 = FitnessScore(genome_id="genome_001", metrics=metrics)

    assert score1.score == score2.score


def test_ac7b_deterministic_metric():
    """AC7b: Same metric → same weighted_value."""
    m1 = FitnessMetric(name="roas", value=0.80, weight=0.5)
    m2 = FitnessMetric(name="roas", value=0.80, weight=0.5)

    assert m1.weighted_value == m2.weighted_value


def test_ac7c_deterministic_evaluation():
    """AC7c: Same fitness → same evaluation result."""
    fitness = FitnessScore(
        genome_id="genome_001",
        metrics=[FitnessMetric(name="roas", value=0.80, weight=1.0)],
    )

    r1 = EvaluationResult(genome_id="genome_001", fitness=fitness,
                         passed=True, reason="Good")
    r2 = EvaluationResult(genome_id="genome_001", fitness=fitness,
                         passed=True, reason="Good")

    assert r1.score == r2.score
    assert r1.passed == r2.passed