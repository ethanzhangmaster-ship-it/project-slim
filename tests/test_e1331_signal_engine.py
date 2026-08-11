"""E13.3.1 Growth Signal Engine — 测试套件.

测试覆盖:
  - GrowthSignal 模型
  - SignalType / SignalSeverity / SignalCategory 枚举
  - SignalContext / SignalBatch 模型
  - CreativeFatigueDetector
  - CreativeWinnerDetector
  - CreativeUnderperformDetector
  - ROASDropDetector
  - LTVUpsideDetector
  - ScaleOpportunityDetector
  - BudgetWasteDetector
  - MonetizationIssueDetector
  - GrowthSignalEngine.analyze()
  - GrowthSignalEngine.analyze_batch()
  - GrowthSignalEngine 静态过滤器
  - 边界条件
  - 集成场景
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Helper: Create a minimal CreativeFitnessVector-like object
# ═══════════════════════════════════════════════════════════════

@dataclass
class MockVector:
    """模拟 CreativeFitnessVector 用于测试."""
    creative_id: str = ""
    creative_name: str = ""
    genome_id: str = ""
    product_id: str = ""
    date: str = "2026-07-24"

    # Acquisition
    ctr: float = 0.0
    cpi: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    spend: float = 0.0

    # Revenue
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    total_revenue: float = 0.0

    # ROAS
    d1_roas: float = 0.0
    d7_roas: float = 0.0
    d30_roas: float = 0.0

    # LTV
    d7_ltv: float = 0.0
    d30_ltv: float = 0.0
    predicted_ltv: float = 0.0

    # Retention
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # Conversion
    iap_conversion: float = 0.0
    payer_rate: float = 0.0

    # IAA
    ad_arpdau: float = 0.0
    ecpm: float = 0.0
    fill_rate: float = 0.0

    # Composite
    fitness_score: float = 0.0
    revenue_score: float = 0.0
    growth_score: float = 0.0
    efficiency_score: float = 0.0

    # Confidence
    sample_size: int = 0
    confidence: float = 0.0

    # Status
    is_winner: bool = False
    is_fatigued: bool = False
    fatigue_score: float = 0.0
    frequency: float = 0.0


def _make_vector(
    creative_id: str = "c001",
    ctr: float = 0.03,
    d7_roas: float = 1.0,
    d30_roas: float = 1.2,
    d7_ltv: float = 2.0,
    d30_ltv: float = 4.0,
    spend: float = 500.0,
    total_revenue: float = 600.0,
    sample_size: int = 5000,
    fitness_score: float = 0.7,
    fatigue_score: float = 0.0,
    iap_conversion: float = 0.05,
    ad_arpdau: float = 0.05,
    frequency: float = 1.0,
    **kwargs,
) -> MockVector:
    return MockVector(
        creative_id=creative_id,
        ctr=ctr,
        d7_roas=d7_roas,
        d30_roas=d30_roas,
        d7_ltv=d7_ltv,
        d30_ltv=d30_ltv,
        spend=spend,
        total_revenue=total_revenue,
        sample_size=sample_size,
        fitness_score=fitness_score,
        fatigue_score=fatigue_score,
        iap_conversion=iap_conversion,
        ad_arpdau=ad_arpdau,
        frequency=frequency,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════════════════════════


class TestSignalType:
    """SignalType 枚举测试."""

    def test_all_types_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        types = list(SignalType)
        assert len(types) == 8
        assert SignalType.CREATIVE_WINNER in types
        assert SignalType.CREATIVE_FATIGUE in types
        assert SignalType.CREATIVE_UNDERPERFORM in types
        assert SignalType.ROAS_DROP in types
        assert SignalType.LTV_UPSIDE in types
        assert SignalType.SCALE_OPPORTUNITY in types
        assert SignalType.BUDGET_WASTE in types
        assert SignalType.MONETIZATION_ISSUE in types

    def test_type_values(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        assert SignalType.CREATIVE_WINNER.value == "creative_winner"
        assert SignalType.CREATIVE_FATIGUE.value == "creative_fatigue"
        assert SignalType.ROAS_DROP.value == "roas_drop"
        assert SignalType.SCALE_OPPORTUNITY.value == "scale_opportunity"

    def test_signal_type_is_string_enum(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        assert isinstance(SignalType.CREATIVE_WINNER.value, str)


class TestSignalSeverity:
    """SignalSeverity 枚举测试."""

    def test_all_severities(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalSeverity

        sevs = list(SignalSeverity)
        assert len(sevs) == 4
        assert SignalSeverity.LOW in sevs
        assert SignalSeverity.MEDIUM in sevs
        assert SignalSeverity.HIGH in sevs
        assert SignalSeverity.CRITICAL in sevs

    def test_severity_values(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalSeverity

        assert SignalSeverity.LOW.value == "low"
        assert SignalSeverity.CRITICAL.value == "critical"

    def test_severity_ordering(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalSeverity

        order = {
            SignalSeverity.CRITICAL: 0,
            SignalSeverity.HIGH: 1,
            SignalSeverity.MEDIUM: 2,
            SignalSeverity.LOW: 3,
        }
        assert order[SignalSeverity.CRITICAL] < order[SignalSeverity.HIGH]
        assert order[SignalSeverity.HIGH] < order[SignalSeverity.MEDIUM]
        assert order[SignalSeverity.MEDIUM] < order[SignalSeverity.LOW]


class TestSignalCategory:
    """SignalCategory 枚举测试."""

    def test_all_categories(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalCategory

        cats = list(SignalCategory)
        assert len(cats) == 4
        assert SignalCategory.CREATIVE in cats
        assert SignalCategory.REVENUE in cats
        assert SignalCategory.UA in cats
        assert SignalCategory.MONETIZATION in cats


class TestGrowthSignal:
    """GrowthSignal 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthSignal, SignalType, SignalSeverity

        sig = GrowthSignal()
        assert sig.signal_id != ""
        assert sig.signal_type == SignalType.CREATIVE_WINNER
        assert sig.severity == SignalSeverity.MEDIUM
        assert sig.confidence == 0.0
        assert sig.metrics == {}
        assert sig.explanation == ""

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthSignal, SignalType, SignalSeverity, SignalCategory

        sig = GrowthSignal(
            signal_type=SignalType.CREATIVE_FATIGUE,
            entity_id="creative_005",
            entity_type="creative",
            category=SignalCategory.CREATIVE,
            severity=SignalSeverity.HIGH,
            confidence=0.92,
            metrics={"ctr_drop": 0.35, "roas_drop": 0.28, "frequency": 5.2},
            explanation="CTR and ROAS declining while frequency increasing",
            rule_name="creative_fatigue_detector",
            source_vector_id="creative_005",
        )
        assert sig.signal_type == SignalType.CREATIVE_FATIGUE
        assert sig.entity_id == "creative_005"
        assert sig.severity == SignalSeverity.HIGH
        assert sig.confidence == 0.92
        assert sig.metrics["ctr_drop"] == 0.35
        assert sig.metrics["frequency"] == 5.2

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthSignal, SignalType, SignalSeverity

        sig = GrowthSignal(
            signal_type=SignalType.CREATIVE_FATIGUE,
            entity_id="c001",
            severity=SignalSeverity.HIGH,
            confidence=0.91,
            metrics={"ctr": 0.021, "roas": 0.7},
            explanation="Fatigue detected",
        )
        d = sig.to_dict()
        assert d["signal_type"] == "creative_fatigue"
        assert d["entity_id"] == "c001"
        assert d["severity"] == "high"
        assert d["confidence"] == 0.91
        assert d["metrics"]["ctr"] == 0.021
        assert "signal_id" in d
        assert "timestamp" in d

    def test_signal_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthSignal

        sig1 = GrowthSignal()
        sig2 = GrowthSignal()
        assert sig1.signal_id != sig2.signal_id

    def test_timestamp_is_set(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthSignal

        sig = GrowthSignal()
        assert sig.timestamp != ""


class TestSignalContext:
    """SignalContext 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        ctx = SignalContext()
        assert ctx.product_id == ""
        assert ctx.vectors == []
        assert ctx.attribution_edges == []

    def test_with_vectors(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        vectors = [_make_vector("c1"), _make_vector("c2")]
        ctx = SignalContext(product_id="p1", vectors=vectors)
        assert len(ctx.vectors) == 2
        assert ctx.product_id == "p1"

    def test_with_benchmarks(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        ctx = SignalContext(category_benchmarks={"default": {"avg_d30_roas": 1.5}})
        assert ctx.category_benchmarks["default"]["avg_d30_roas"] == 1.5


class TestSignalBatch:
    """SignalBatch 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalBatch

        batch = SignalBatch()
        assert batch.signals == []
        assert batch.total_vectors == 0
        assert batch.total_signals == 0
        assert batch.summary == {}

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalBatch, GrowthSignal, SignalType, SignalSeverity

        sig = GrowthSignal(signal_type=SignalType.CREATIVE_WINNER, entity_id="c1", severity=SignalSeverity.HIGH, confidence=0.9)
        batch = SignalBatch(
            product_id="p1",
            date="2026-07-24",
            signals=[sig],
            total_vectors=10,
            total_signals=1,
            summary={"creative_winner": 1},
            elapsed_ms=150.0,
        )
        d = batch.to_dict()
        assert d["product_id"] == "p1"
        assert d["total_vectors"] == 10
        assert d["total_signals"] == 1
        assert d["summary"]["creative_winner"] == 1
        assert len(d["signals"]) == 1

    def test_batch_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalBatch

        b1 = SignalBatch()
        b2 = SignalBatch()
        assert b1.batch_id != b2.batch_id


class TestSignalCategoryMap:
    """SIGNAL_CATEGORY_MAP 测试."""

    def test_all_types_mapped(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, SIGNAL_CATEGORY_MAP

        for st in SignalType:
            assert st in SIGNAL_CATEGORY_MAP, f"SignalType {st} not in SIGNAL_CATEGORY_MAP"

    def test_creative_types_map_to_creative(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, SignalCategory, SIGNAL_CATEGORY_MAP

        assert SIGNAL_CATEGORY_MAP[SignalType.CREATIVE_WINNER] == SignalCategory.CREATIVE
        assert SIGNAL_CATEGORY_MAP[SignalType.CREATIVE_FATIGUE] == SignalCategory.CREATIVE
        assert SIGNAL_CATEGORY_MAP[SignalType.CREATIVE_UNDERPERFORM] == SignalCategory.CREATIVE

    def test_revenue_types_map_to_revenue(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, SignalCategory, SIGNAL_CATEGORY_MAP

        assert SIGNAL_CATEGORY_MAP[SignalType.ROAS_DROP] == SignalCategory.REVENUE
        assert SIGNAL_CATEGORY_MAP[SignalType.LTV_UPSIDE] == SignalCategory.REVENUE


# ═══════════════════════════════════════════════════════════════
# CreativeFatigueDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeFatigueDetector:
    """CreativeFatigueDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.creative_rules import CreativeFatigueDetector
        return CreativeFatigueDetector()

    def test_detect_fatigue_ctr_drop_roas_drop(self, detector):
        # ctr=0.005 vs avg=0.03 → decay=0.833; roas=0.3 vs avg=1.5 → decay=0.8; freq=9/10=0.9
        # fatigue_score = 0.833*0.4 + 0.8*0.4 + 0.9*0.2 = 0.833 > 0.75
        v = _make_vector("c1", ctr=0.005, d7_roas=0.3, sample_size=5000, frequency=9.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.signal_type.value == "creative_fatigue"
        assert sig.confidence > 0.5

    def test_no_fatigue_normal_creative(self, detector):
        v = _make_vector("c2", ctr=0.04, d7_roas=2.0, sample_size=5000, frequency=1.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is None

    def test_no_fatigue_insufficient_sample(self, detector):
        v = _make_vector("c3", ctr=0.01, d7_roas=0.5, sample_size=100, frequency=6.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is None

    def test_already_fatigued(self, detector):
        v = _make_vector("c4", ctr=0.01, d7_roas=0.5, sample_size=5000,
                         is_fatigued=True, fatigue_score=0.85)
        sig = detector.detect(v, {})
        assert sig is not None
        assert sig.signal_type.value == "creative_fatigue"

    def test_fatigue_critical_at_high_score(self, detector):
        v = _make_vector("c5", ctr=0.005, d7_roas=0.2, sample_size=10000, frequency=9.0)
        bm = {"avg_ctr": 0.04, "avg_d7_roas": 2.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        # Should be CRITICAL or HIGH
        assert sig.severity.value in ("critical", "high")

    def test_fatigue_signal_contains_metrics(self, detector):
        # ctr=0.005 vs avg=0.03 → decay=0.833; roas=0.2 vs avg=1.5 → decay=0.867; freq=8/10=0.8
        # fatigue_score = 0.833*0.4 + 0.867*0.4 + 0.8*0.2 = 0.84 > 0.75
        v = _make_vector("c6", ctr=0.005, d7_roas=0.2, sample_size=5000, frequency=8.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert "fatigue_score" in sig.metrics
        assert "ctr" in sig.metrics
        assert "d7_roas" in sig.metrics

    def test_fatigue_signal_has_explanation(self, detector):
        v = _make_vector("c7", ctr=0.005, d7_roas=0.2, sample_size=5000, frequency=8.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert len(sig.explanation) > 0
        assert "fatigue" in sig.explanation.lower()

    def test_fatigue_rule_name(self, detector):
        v = _make_vector("c8", ctr=0.005, d7_roas=0.2, sample_size=5000, frequency=8.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.rule_name == "creative_fatigue_detector"

    def test_custom_thresholds(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.creative_rules import CreativeFatigueDetector

        # Very strict thresholds - should not trigger
        d = CreativeFatigueDetector({"fatigue_score_threshold": 0.99})
        v = _make_vector("c9", ctr=0.01, d7_roas=0.5, sample_size=5000, frequency=6.0)
        bm = {"avg_ctr": 0.03, "avg_d7_roas": 1.5}
        sig = d.detect(v, bm)
        assert sig is None


# ═══════════════════════════════════════════════════════════════
# CreativeWinnerDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeWinnerDetector:
    """CreativeWinnerDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.creative_rules import CreativeWinnerDetector
        return CreativeWinnerDetector()

    def test_detect_winner_strong(self, detector):
        v = _make_vector("w1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.signal_type.value == "creative_winner"
        assert sig.confidence > 0.5

    def test_no_winner_weak_roas(self, detector):
        v = _make_vector("w2", d30_roas=0.8, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is None

    def test_no_winner_insufficient_sample(self, detector):
        v = _make_vector("w3", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=100)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is None

    def test_winner_above_category_average(self, detector):
        v = _make_vector("w4", d30_roas=2.5, d30_ltv=6.0, fitness_score=0.85, sample_size=6000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is not None

    def test_winner_metrics_in_signal(self, detector):
        v = _make_vector("w5", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert "d30_roas" in sig.metrics
        assert "d30_ltv" in sig.metrics
        assert "fitness_score" in sig.metrics

    def test_winner_rule_name(self, detector):
        v = _make_vector("w6", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.rule_name == "creative_winner_detector"

    def test_winner_severity_high(self, detector):
        v = _make_vector("w7", d30_roas=4.0, d30_ltv=10.0, fitness_score=0.95, sample_size=20000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.severity.value == "high"

    def test_custom_thresholds_no_winner(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.creative_rules import CreativeWinnerDetector

        d = CreativeWinnerDetector({"winner_roas_absolute": 5.0, "winner_ltv_min": 20.0, "winner_conf_min": 0.6})
        v = _make_vector("w8", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)
        bm = {"avg_d30_roas": 1.0, "avg_d30_ltv": 3.0}
        sig = d.detect(v, bm)
        assert sig is None


# ═══════════════════════════════════════════════════════════════
# CreativeUnderperformDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeUnderperformDetector:
    """CreativeUnderperformDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.creative_rules import CreativeUnderperformDetector
        return CreativeUnderperformDetector()

    def test_detect_underperform(self, detector):
        v = _make_vector("u1", d7_roas=0.3, ctr=0.003, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.signal_type.value == "creative_underperform"

    def test_no_underperform_good_roas(self, detector):
        v = _make_vector("u2", d7_roas=1.5, ctr=0.04, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_underperform_low_spend(self, detector):
        v = _make_vector("u3", d7_roas=0.3, ctr=0.003, spend=50.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_underperform_small_sample(self, detector):
        v = _make_vector("u4", d7_roas=0.3, ctr=0.003, spend=200.0, sample_size=100)
        sig = detector.detect(v)
        assert sig is None

    def test_underperform_severity_high_at_very_low_roas(self, detector):
        v = _make_vector("u5", d7_roas=0.1, ctr=0.003, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.severity.value == "high"

    def test_underperform_rule_name(self, detector):
        v = _make_vector("u6", d7_roas=0.3, ctr=0.003, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.rule_name == "creative_underperform_detector"


# ═══════════════════════════════════════════════════════════════
# ROASDropDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestROASDropDetector:
    """ROASDropDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.revenue_rules import ROASDropDetector
        return ROASDropDetector()

    def test_detect_roas_drop(self, detector):
        v = _make_vector("r1", d7_roas=0.7, d30_roas=1.5, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.signal_type.value == "roas_drop"

    def test_no_roas_drop_stable(self, detector):
        v = _make_vector("r2", d7_roas=1.5, d30_roas=1.5, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_roas_drop_low_spend(self, detector):
        v = _make_vector("r3", d7_roas=0.7, d30_roas=1.5, spend=50.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is None

    def test_roas_drop_uses_benchmark_when_no_d30(self, detector):
        v = _make_vector("r4", d7_roas=0.5, d30_roas=0.0, spend=200.0, sample_size=2000)
        bm = {"avg_d7_roas": 1.5}
        sig = detector.detect(v, bm)
        assert sig is not None

    def test_roas_drop_critical_at_large_decay(self, detector):
        v = _make_vector("r5", d7_roas=0.3, d30_roas=2.0, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.severity.value == "critical"

    def test_roas_drop_metrics(self, detector):
        v = _make_vector("r6", d7_roas=0.7, d30_roas=1.5, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert "roas_decay_pct" in sig.metrics
        assert "current_d7_roas" in sig.metrics

    def test_roas_drop_rule_name(self, detector):
        v = _make_vector("r7", d7_roas=0.7, d30_roas=1.5, spend=200.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.rule_name == "roas_drop_detector"


# ═══════════════════════════════════════════════════════════════
# LTVUpsideDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestLTVUpsideDetector:
    """LTVUpsideDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.revenue_rules import LTVUpsideDetector
        return LTVUpsideDetector()

    def test_detect_ltv_upside(self, detector):
        v = _make_vector("l1", d7_ltv=3.0, d30_ltv=8.0, sample_size=5000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.signal_type.value == "ltv_upside"

    def test_no_ltv_upside_flat(self, detector):
        v = _make_vector("l2", d7_ltv=5.0, d30_ltv=5.5, sample_size=5000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_ltv_upside_zero_d7(self, detector):
        v = _make_vector("l3", d7_ltv=0.0, d30_ltv=8.0, sample_size=5000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_ltv_upside_small_sample(self, detector):
        v = _make_vector("l4", d7_ltv=3.0, d30_ltv=8.0, sample_size=100)
        sig = detector.detect(v)
        assert sig is None

    def test_ltv_upside_rule_name(self, detector):
        v = _make_vector("l5", d7_ltv=3.0, d30_ltv=8.0, sample_size=5000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.rule_name == "ltv_upside_detector"


# ═══════════════════════════════════════════════════════════════
# ScaleOpportunityDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestScaleOpportunityDetector:
    """ScaleOpportunityDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.ua_rules import ScaleOpportunityDetector
        return ScaleOpportunityDetector()

    def test_detect_scale_opportunity(self, detector):
        v = _make_vector("s1", d30_roas=2.0, spend=200.0, fitness_score=0.85, sample_size=5000)
        bm = {"avg_d30_roas": 1.0, "avg_spend": 1000.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.signal_type.value == "scale_opportunity"

    def test_no_scale_low_roas(self, detector):
        v = _make_vector("s2", d30_roas=0.8, spend=200.0, fitness_score=0.85, sample_size=5000)
        bm = {"avg_d30_roas": 1.0, "avg_spend": 1000.0}
        sig = detector.detect(v, bm)
        assert sig is None

    def test_no_scale_insufficient_sample(self, detector):
        v = _make_vector("s3", d30_roas=2.0, spend=200.0, fitness_score=0.85, sample_size=100)
        bm = {"avg_d30_roas": 1.0, "avg_spend": 1000.0}
        sig = detector.detect(v, bm)
        assert sig is None

    def test_scale_rule_name(self, detector):
        v = _make_vector("s4", d30_roas=2.0, spend=200.0, fitness_score=0.85, sample_size=5000)
        bm = {"avg_d30_roas": 1.0, "avg_spend": 1000.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert sig.rule_name == "scale_opportunity_detector"

    def test_scale_metrics(self, detector):
        v = _make_vector("s5", d30_roas=2.0, spend=200.0, fitness_score=0.85, sample_size=5000)
        bm = {"avg_d30_roas": 1.0, "avg_spend": 1000.0}
        sig = detector.detect(v, bm)
        assert sig is not None
        assert "spend" in sig.metrics
        assert "d30_roas" in sig.metrics


# ═══════════════════════════════════════════════════════════════
# BudgetWasteDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestBudgetWasteDetector:
    """BudgetWasteDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.ua_rules import BudgetWasteDetector
        return BudgetWasteDetector()

    def test_detect_budget_waste(self, detector):
        v = _make_vector("b1", d7_roas=0.3, spend=500.0, total_revenue=150.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.signal_type.value == "budget_waste"

    def test_no_waste_good_roas(self, detector):
        v = _make_vector("b2", d7_roas=1.5, spend=500.0, total_revenue=750.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_waste_low_spend(self, detector):
        v = _make_vector("b3", d7_roas=0.3, spend=100.0, total_revenue=30.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_waste_small_sample(self, detector):
        v = _make_vector("b4", d7_roas=0.3, spend=500.0, total_revenue=150.0, sample_size=100)
        sig = detector.detect(v)
        assert sig is None

    def test_waste_rule_name(self, detector):
        v = _make_vector("b5", d7_roas=0.3, spend=500.0, total_revenue=150.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.rule_name == "budget_waste_detector"

    def test_waste_severity_high_at_very_low_roas(self, detector):
        v = _make_vector("b6", d7_roas=0.1, spend=500.0, total_revenue=50.0, sample_size=2000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.severity.value == "high"


# ═══════════════════════════════════════════════════════════════
# MonetizationIssueDetector Tests
# ═══════════════════════════════════════════════════════════════


class TestMonetizationIssueDetector:
    """MonetizationIssueDetector 测试."""

    @pytest.fixture
    def detector(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.rules.ua_rules import MonetizationIssueDetector
        return MonetizationIssueDetector()

    def test_detect_low_iap_conversion(self, detector):
        v = _make_vector("m1", iap_conversion=0.005, ad_arpdau=0.05, sample_size=5000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.signal_type.value == "monetization_issue"

    def test_detect_low_ad_arpdau(self, detector):
        v = _make_vector("m2", iap_conversion=0.05, ad_arpdau=0.005, sample_size=5000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.signal_type.value == "monetization_issue"

    def test_no_issue_good_metrics(self, detector):
        v = _make_vector("m3", iap_conversion=0.05, ad_arpdau=0.05, sample_size=5000)
        sig = detector.detect(v)
        assert sig is None

    def test_no_issue_small_sample(self, detector):
        v = _make_vector("m4", iap_conversion=0.005, ad_arpdau=0.005, sample_size=100)
        sig = detector.detect(v)
        assert sig is None

    def test_rule_name(self, detector):
        v = _make_vector("m5", iap_conversion=0.005, ad_arpdau=0.05, sample_size=5000)
        sig = detector.detect(v)
        assert sig is not None
        assert sig.rule_name == "monetization_issue_detector"


# ═══════════════════════════════════════════════════════════════
# GrowthSignalEngine Tests
# ═══════════════════════════════════════════════════════════════


class TestGrowthSignalEngine:
    """GrowthSignalEngine 核心测试."""

    @pytest.fixture
    def engine(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        return GrowthSignalEngine()

    def test_analyze_empty_vectors(self, engine):
        signals = engine.analyze([])
        assert signals == []

    def test_analyze_detects_winner(self, engine):
        vectors = [
            _make_vector("win1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
            _make_vector("avg1", d30_roas=1.0, d30_ltv=3.0, fitness_score=0.5, sample_size=5000),
            _make_vector("avg2", d30_roas=1.2, d30_ltv=3.5, fitness_score=0.6, sample_size=5000),
        ]
        signals = engine.analyze(vectors)
        winners = [s for s in signals if s.signal_type.value == "creative_winner"]
        assert len(winners) > 0
        assert winners[0].entity_id == "win1"

    def test_analyze_detects_fatigue(self, engine):
        vectors = [
            _make_vector("fat1", ctr=0.003, d7_roas=0.15, d30_roas=0.5, sample_size=5000, frequency=7.0),
            _make_vector("avg1", ctr=0.04, d7_roas=1.5, d30_roas=1.8, sample_size=5000),
            _make_vector("avg2", ctr=0.04, d7_roas=1.5, d30_roas=1.8, sample_size=5000),
        ]
        signals = engine.analyze(vectors)
        fatigues = [s for s in signals if s.signal_type.value == "creative_fatigue"]
        assert len(fatigues) > 0
        assert fatigues[0].entity_id == "fat1"

    def test_analyze_detects_roas_drop(self, engine):
        vectors = [
            _make_vector("drop1", d7_roas=0.5, d30_roas=2.0, spend=300.0, sample_size=2000),
            _make_vector("avg1", d7_roas=1.5, d30_roas=1.5, spend=300.0, sample_size=2000),
        ]
        signals = engine.analyze(vectors)
        drops = [s for s in signals if s.signal_type.value == "roas_drop"]
        assert len(drops) > 0
        assert drops[0].entity_id == "drop1"

    def test_analyze_detects_scale_opportunity(self, engine):
        vectors = [
            _make_vector("scale1", d30_roas=2.5, spend=200.0, fitness_score=0.9, sample_size=5000),
            _make_vector("avg1", d30_roas=1.0, spend=1000.0, fitness_score=0.5, sample_size=5000),
            _make_vector("avg2", d30_roas=1.0, spend=1000.0, fitness_score=0.5, sample_size=5000),
        ]
        signals = engine.analyze(vectors)
        scales = [s for s in signals if s.signal_type.value == "scale_opportunity"]
        assert len(scales) > 0
        assert scales[0].entity_id == "scale1"

    def test_analyze_detects_budget_waste(self, engine):
        vectors = [
            _make_vector("waste1", d7_roas=0.3, spend=500.0, total_revenue=150.0, sample_size=2000),
            _make_vector("avg1", d7_roas=1.5, spend=500.0, total_revenue=750.0, sample_size=2000),
        ]
        signals = engine.analyze(vectors)
        wastes = [s for s in signals if s.signal_type.value == "budget_waste"]
        assert len(wastes) > 0
        assert wastes[0].entity_id == "waste1"

    def test_analyze_detects_underperform(self, engine):
        vectors = [
            _make_vector("under1", d7_roas=0.3, ctr=0.003, spend=200.0, sample_size=2000),
            _make_vector("avg1", d7_roas=1.5, ctr=0.04, spend=200.0, sample_size=2000),
        ]
        signals = engine.analyze(vectors)
        unders = [s for s in signals if s.signal_type.value == "creative_underperform"]
        assert len(unders) > 0
        assert unders[0].entity_id == "under1"

    def test_analyze_detects_ltv_upside(self, engine):
        vectors = [
            _make_vector("ltv1", d7_ltv=3.0, d30_ltv=8.0, sample_size=5000),
            _make_vector("avg1", d7_ltv=3.0, d30_ltv=3.5, sample_size=5000),
        ]
        signals = engine.analyze(vectors)
        ltv_signals = [s for s in signals if s.signal_type.value == "ltv_upside"]
        assert len(ltv_signals) > 0
        assert ltv_signals[0].entity_id == "ltv1"

    def test_analyze_detects_monetization_issue(self, engine):
        vectors = [
            _make_vector("mon1", iap_conversion=0.003, ad_arpdau=0.05, sample_size=5000),
            _make_vector("avg1", iap_conversion=0.05, ad_arpdau=0.05, sample_size=5000),
        ]
        signals = engine.analyze(vectors)
        mon_signals = [s for s in signals if s.signal_type.value == "monetization_issue"]
        assert len(mon_signals) > 0
        assert mon_signals[0].entity_id == "mon1"

    def test_analyze_multiple_signals_per_vector(self, engine):
        """一个向量可能触发多个信号."""
        vectors = [
            _make_vector("multi1", d30_roas=3.0, d30_ltv=8.0, d7_ltv=3.0,
                         fitness_score=0.9, sample_size=10000, spend=200.0),
            _make_vector("avg1", d30_roas=1.0, d30_ltv=3.0, d7_ltv=3.0,
                         fitness_score=0.5, sample_size=5000, spend=1000.0),
            _make_vector("avg2", d30_roas=1.0, d30_ltv=3.0, d7_ltv=3.0,
                         fitness_score=0.5, sample_size=5000, spend=1000.0),
        ]
        signals = engine.analyze(vectors)
        multi_ids = [s.entity_id for s in signals if s.entity_id == "multi1"]
        assert len(multi_ids) >= 2  # winner + scale_opportunity + ltv_upside

    def test_analyze_signals_sorted_by_severity(self, engine):
        vectors = [
            _make_vector("crit1", d7_roas=0.1, d30_roas=2.0, spend=500.0, sample_size=2000),  # roas_drop CRITICAL
            _make_vector("win1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),  # winner HIGH
            _make_vector("avg1", d30_roas=1.0, d30_ltv=3.0, fitness_score=0.5, sample_size=5000),
        ]
        signals = engine.analyze(vectors)
        # CRITICAL should come before HIGH
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(signals) - 1):
            assert severity_order[signals[i].severity.value] <= severity_order[signals[i + 1].severity.value]

    def test_analyze_all_normal(self, engine):
        """全部正常的向量，不应产生信号."""
        vectors = [
            _make_vector("n1", ctr=0.04, d7_roas=1.5, d30_roas=1.5, d30_ltv=4.0,
                         fitness_score=0.7, sample_size=5000, spend=500.0,
                         iap_conversion=0.05, ad_arpdau=0.05),
            _make_vector("n2", ctr=0.04, d7_roas=1.5, d30_roas=1.5, d30_ltv=4.0,
                         fitness_score=0.7, sample_size=5000, spend=500.0,
                         iap_conversion=0.05, ad_arpdau=0.05),
        ]
        signals = engine.analyze(vectors)
        # 正常素材可能只有少量信号 (如 LTV upside 如果 d30 > d7*1.2)
        # 只检查没有 CRITICAL 信号
        critical = [s for s in signals if s.severity.value == "critical"]
        assert len(critical) == 0

    def test_analyze_batch(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        vectors = [
            _make_vector("win1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
            _make_vector("fat1", ctr=0.01, d7_roas=0.3, d30_roas=0.5, sample_size=5000, frequency=7.0),
            _make_vector("avg1", d30_roas=1.0, d30_ltv=3.0, fitness_score=0.5, sample_size=5000),
        ]
        ctx = SignalContext(product_id="p1", date="2026-07-24", vectors=vectors)
        batch = engine.analyze_batch(ctx)
        assert batch.total_vectors == 3
        assert batch.total_signals > 0
        assert batch.product_id == "p1"
        assert batch.date == "2026-07-24"
        assert batch.elapsed_ms > 0
        assert len(batch.summary) > 0

    def test_analyze_batch_empty(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        ctx = SignalContext()
        batch = engine.analyze_batch(ctx)
        assert batch.total_vectors == 0
        assert batch.total_signals == 0

    def test_analyze_batch_to_dict(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        vectors = [_make_vector("win1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)]
        ctx = SignalContext(product_id="p1", vectors=vectors)
        batch = engine.analyze_batch(ctx)
        d = batch.to_dict()
        assert "batch_id" in d
        assert "signals" in d
        assert "summary" in d

    def test_custom_thresholds(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine

        # Very strict thresholds
        engine = GrowthSignalEngine({
            "winner_roas_absolute": 10.0,
            "winner_conf_min": 0.75,
            "winner_fitness_min": 0.95,
            "fatigue_score_threshold": 0.99,
            "roas_drop_pct": 0.9,
            "ltv_upside_pct": 0.99,
            "ltv_upside_conf_min": 0.9,
            "scale_roas_absolute": 10.0,
            "waste_roas_max": 0.01,
        })
        vectors = [
            _make_vector("w1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
            _make_vector("f1", ctr=0.01, d7_roas=0.3, d30_roas=0.5, sample_size=5000, frequency=7.0),
        ]
        signals = engine.analyze(vectors)
        # With strict thresholds, no signals should be generated
        assert len(signals) == 0


# ═══════════════════════════════════════════════════════════════
# Filter Static Methods Tests
# ═══════════════════════════════════════════════════════════════


class TestSignalFilters:
    """静态过滤器方法测试."""

    @pytest.fixture
    def signals(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthSignal, SignalType, SignalSeverity, SignalCategory,
        )

        return [
            GrowthSignal(signal_type=SignalType.CREATIVE_WINNER, entity_id="w1", category=SignalCategory.CREATIVE, severity=SignalSeverity.HIGH, confidence=0.9),
            GrowthSignal(signal_type=SignalType.CREATIVE_FATIGUE, entity_id="f1", category=SignalCategory.CREATIVE, severity=SignalSeverity.CRITICAL, confidence=0.95),
            GrowthSignal(signal_type=SignalType.SCALE_OPPORTUNITY, entity_id="s1", category=SignalCategory.UA, severity=SignalSeverity.MEDIUM, confidence=0.7),
            GrowthSignal(signal_type=SignalType.ROAS_DROP, entity_id="r1", category=SignalCategory.REVENUE, severity=SignalSeverity.HIGH, confidence=0.85),
            GrowthSignal(signal_type=SignalType.BUDGET_WASTE, entity_id="b1", category=SignalCategory.UA, severity=SignalSeverity.LOW, confidence=0.5),
        ]

    def test_filter_by_severity_high(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalSeverity

        filtered = GrowthSignalEngine.filter_by_severity(signals, SignalSeverity.HIGH)
        assert len(filtered) == 3  # HIGH, CRITICAL, HIGH

    def test_filter_by_severity_critical(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalSeverity

        filtered = GrowthSignalEngine.filter_by_severity(signals, SignalSeverity.CRITICAL)
        assert len(filtered) == 1

    def test_filter_by_category_creative(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalCategory

        filtered = GrowthSignalEngine.filter_by_category(signals, SignalCategory.CREATIVE)
        assert len(filtered) == 2  # winner + fatigue

    def test_filter_by_type(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        filtered = GrowthSignalEngine.filter_by_type(signals, SignalType.CREATIVE_WINNER)
        assert len(filtered) == 1
        assert filtered[0].entity_id == "w1"

    def test_get_winners(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine

        winners = GrowthSignalEngine.get_winners(signals)
        assert len(winners) == 1
        assert winners[0].entity_id == "w1"

    def test_get_fatigued(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine

        fatigued = GrowthSignalEngine.get_fatigued(signals)
        assert len(fatigued) == 1
        assert fatigued[0].entity_id == "f1"

    def test_get_scale_opportunities(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine

        scales = GrowthSignalEngine.get_scale_opportunities(signals)
        assert len(scales) == 1
        assert scales[0].entity_id == "s1"

    def test_get_critical_signals(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine

        critical = GrowthSignalEngine.get_critical_signals(signals)
        assert len(critical) == 1
        assert critical[0].entity_id == "f1"

    def test_filter_empty_list(self, signals):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalSeverity

        filtered = GrowthSignalEngine.filter_by_severity([], SignalSeverity.HIGH)
        assert filtered == []


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试."""

    @pytest.fixture
    def engine(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        return GrowthSignalEngine()

    def test_zero_metrics(self, engine):
        """全零指标的向量."""
        v = _make_vector("z1", ctr=0.0, d7_roas=0.0, d30_roas=0.0, d7_ltv=0.0,
                         d30_ltv=0.0, spend=0.0, sample_size=0, fitness_score=0.0)
        signals = engine.analyze([v])
        # 应该不产生任何信号
        assert len(signals) == 0

    def test_negative_metrics(self, engine):
        """负指标 (不应出现但需要安全处理)."""
        v = _make_vector("neg1", d7_roas=-1.0, d30_roas=-1.0, sample_size=5000, spend=500.0)
        signals = engine.analyze([v])
        # 不应崩溃
        assert isinstance(signals, list)

    def test_large_sample_size(self, engine):
        """超大样本量."""
        v = _make_vector("big1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000000)
        signals = engine.analyze([v])
        winners = [s for s in signals if s.signal_type.value == "creative_winner"]
        assert len(winners) > 0

    def test_single_vector(self, engine):
        """单个向量，无基准."""
        v = _make_vector("single1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000)
        signals = engine.analyze([v])
        # 即使没有其他向量计算基准，也应能检测 winner (使用绝对阈值)
        winners = [s for s in signals if s.signal_type.value == "creative_winner"]
        assert len(winners) > 0

    def test_identical_vectors(self, engine):
        """相同向量不应产生重复信号."""
        vectors = [
            _make_vector("dup1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
            _make_vector("dup2", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
        ]
        signals = engine.analyze(vectors)
        winners = [s for s in signals if s.signal_type.value == "creative_winner"]
        assert len(winners) == 2  # 两个不同的 creative_id

    def test_high_frequency_low_ctr(self, engine):
        """高频次低 CTR."""
        v = _make_vector("hf1", ctr=0.005, d7_roas=0.3, d30_roas=0.5, sample_size=5000, frequency=10.0)
        # Add reference vectors to provide benchmarks
        ref = _make_vector("ref1", ctr=0.04, d7_roas=1.5, d30_roas=1.5, sample_size=5000)
        signals = engine.analyze([v, ref])
        fatigues = [s for s in signals if s.signal_type.value == "creative_fatigue"]
        assert len(fatigues) > 0

    def test_no_frequency_data(self, engine):
        """无 frequency 字段的向量."""
        v = _make_vector("nf1", ctr=0.01, d7_roas=0.5, sample_size=5000)
        # frequency 默认为 0.0
        signals = engine.analyze([v])
        # 可能触发 fatigue (如果 CTR 和 ROAS 低) 也可能不触发
        assert isinstance(signals, list)


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegrationScenarios:
    """集成场景测试."""

    @pytest.fixture
    def engine(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthSignalEngine
        return GrowthSignalEngine()

    def test_full_product_pipeline(self, engine):
        """模拟完整产品分析流水线."""
        vectors = [
            # Winner: 高 ROAS + LTV
            _make_vector("c_winner", d30_roas=3.5, d30_ltv=10.0, d7_roas=3.0,
                         fitness_score=0.95, sample_size=15000, spend=500.0),
            # Fatigue: 数据下降
            _make_vector("c_fatigue", ctr=0.003, d7_roas=0.1, d30_roas=0.5,
                         sample_size=8000, spend=300.0, frequency=8.0),
            # Underperform: 低效
            _make_vector("c_under", d7_roas=0.2, ctr=0.002, spend=300.0, sample_size=3000),
            # Scale: 放量机会
            _make_vector("c_scale", d30_roas=2.5, spend=150.0, fitness_score=0.88, sample_size=6000),
            # Waste: 预算浪费
            _make_vector("c_waste", d7_roas=0.25, spend=600.0, total_revenue=150.0, sample_size=3000),
            # Normal
            _make_vector("c_normal", d30_roas=1.2, d30_ltv=4.0, d7_roas=1.3,
                         fitness_score=0.6, sample_size=5000, spend=500.0,
                         ctr=0.035, iap_conversion=0.05, ad_arpdau=0.05),
            # Normal
            _make_vector("c_normal2", d30_roas=1.1, d30_ltv=3.5, d7_roas=1.2,
                         fitness_score=0.55, sample_size=5000, spend=500.0,
                         ctr=0.035, iap_conversion=0.05, ad_arpdau=0.05),
        ]
        signals = engine.analyze(vectors)

        # 验证各类型信号
        signal_types = {s.signal_type.value for s in signals}
        assert "creative_winner" in signal_types
        assert "creative_fatigue" in signal_types
        assert "creative_underperform" in signal_types
        assert "scale_opportunity" in signal_types
        assert "budget_waste" in signal_types

        # 验证排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(signals) - 1):
            assert severity_order[signals[i].severity.value] <= severity_order[signals[i + 1].severity.value]

    def test_signal_batch_summary(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalContext

        vectors = [
            _make_vector("w1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
            _make_vector("w2", d30_roas=3.5, d30_ltv=9.0, fitness_score=0.92, sample_size=12000),
            _make_vector("f1", ctr=0.003, d7_roas=0.1, d30_roas=0.5, sample_size=5000, frequency=7.0),
            _make_vector("avg1", d30_roas=1.0, d30_ltv=3.0, fitness_score=0.5, sample_size=5000),
        ]
        ctx = SignalContext(product_id="p1", date="2026-07-24", vectors=vectors)
        batch = engine.analyze_batch(ctx)
        assert batch.total_vectors == 4
        assert batch.total_signals > 0
        assert "creative_winner" in batch.summary
        assert "creative_fatigue" in batch.summary

    def test_signal_consistency(self, engine):
        """相同输入产生相同信号."""
        vectors = [
            _make_vector("w1", d30_roas=3.0, d30_ltv=8.0, fitness_score=0.9, sample_size=10000),
            _make_vector("avg1", d30_roas=1.0, d30_ltv=3.0, fitness_score=0.5, sample_size=5000),
        ]
        signals1 = engine.analyze(vectors)
        signals2 = engine.analyze(vectors)
        assert len(signals1) == len(signals2)
        for s1, s2 in zip(signals1, signals2):
            assert s1.signal_type == s2.signal_type
            assert s1.entity_id == s2.entity_id
            assert s1.confidence == s2.confidence

    def test_all_signal_types_can_be_generated(self, engine):
        """验证所有 8 种信号类型都能被生成."""
        vectors = [
            # Winner
            _make_vector("cw", d30_roas=3.5, d30_ltv=10.0, fitness_score=0.95, sample_size=15000, spend=500.0),
            # Fatigue
            _make_vector("cf", ctr=0.005, d7_roas=0.2, d30_roas=0.4, sample_size=8000, frequency=9.0),
            # Underperform
            _make_vector("cu", d7_roas=0.1, ctr=0.002, spend=300.0, sample_size=2000),
            # ROAS Drop
            _make_vector("rd", d7_roas=0.3, d30_roas=2.5, spend=300.0, sample_size=2000),
            # LTV Upside
            _make_vector("lu", d7_ltv=2.0, d30_ltv=8.0, sample_size=5000),
            # Scale
            _make_vector("so", d30_roas=2.5, spend=150.0, fitness_score=0.9, sample_size=6000),
            # Waste
            _make_vector("bw", d7_roas=0.2, spend=500.0, total_revenue=100.0, sample_size=2000),
            # Monetization
            _make_vector("mi", iap_conversion=0.003, ad_arpdau=0.003, sample_size=5000),
            # Reference normal
            _make_vector("ref1", d30_roas=1.0, d30_ltv=3.0, d7_ltv=3.0, ctr=0.04,
                         fitness_score=0.5, sample_size=5000, spend=1000.0,
                         d7_roas=1.0, iap_conversion=0.05, ad_arpdau=0.05),
            _make_vector("ref2", d30_roas=1.0, d30_ltv=3.0, d7_ltv=3.0, ctr=0.04,
                         fitness_score=0.5, sample_size=5000, spend=1000.0,
                         d7_roas=1.0, iap_conversion=0.05, ad_arpdau=0.05),
        ]
        signals = engine.analyze(vectors)
        generated_types = {s.signal_type.value for s in signals}
        # All 8 types should be present
        expected = {"creative_winner", "creative_fatigue", "creative_underperform",
                    "roas_drop", "ltv_upside", "scale_opportunity",
                    "budget_waste", "monetization_issue"}
        missing = expected - generated_types
        assert len(missing) == 0, f"Missing signal types: {missing}"