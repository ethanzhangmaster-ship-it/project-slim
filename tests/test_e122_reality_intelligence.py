"""E12.2 — Reality Intelligence Layer Tests。

覆盖：
  - Models: InsightType, SeverityLevel, RealityInsight, PerformanceInsight, FatigueInsight, AnomalyInsight, CombinedInsight
  - PerformanceAnalyzer: analyze / analyze_single / ROAS drop / CTR drop / CPI rise
  - FatigueDetector: detect / detect_batch / to_insights / fatigue score
  - AnomalyDetector: detect / detect_batch / spend spike / revenue drop
  - ConfidenceEngine: compute / compute_batch / is_reliable
  - RecommendationEngine: recommend / recommend_batch / to_evolution_opportunities
  - InsightEngine: analyze / deduplicate / combine / get_actionable
  - InsightBridge: to_opportunities / to_market_signal / bridge_and_enrich
  - Full Pipeline
  - Package Exports
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.reality.intelligence.models import (
    AnomalyInsight,
    CombinedInsight,
    FatigueInsight,
    InsightType,
    PerformanceInsight,
    RealityInsight,
    SeverityLevel,
    TrendInsight,
)
from market_ops.creative_vision_runtime.reality.analyzers.performance_analyzer import (
    PerformanceAnalyzer,
)
from market_ops.creative_vision_runtime.reality.analyzers.fatigue_detector import (
    FatigueDetector,
)
from market_ops.creative_vision_runtime.reality.analyzers.anomaly_detector import (
    AnomalyDetector,
)
from market_ops.creative_vision_runtime.reality.intelligence.confidence_engine import (
    ConfidenceEngine,
)
from market_ops.creative_vision_runtime.reality.intelligence.recommendation_engine import (
    RecommendationEngine,
)
from market_ops.creative_vision_runtime.reality.intelligence.insight_engine import (
    InsightEngine,
)
from market_ops.creative_vision_runtime.reality.insight_bridge import (
    InsightBridge,
)
from market_ops.creative_vision_runtime.reality.models import (
    CampaignReality,
    CreativeReality,
    RealitySnapshot,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_campaign(
    campaign_id: str = "camp_001",
    spend: float = 500.0,
    revenue_d30: float = 800.0,
    installs: int = 500,
    ctr: float = 0.03,
    cpi: float = 1.0,
    roas_d7: float = 1.0,
    roas_d30: float = 1.6,
) -> CampaignReality:
    return CampaignReality(
        campaign_id=campaign_id,
        spend=spend,
        revenue_d30=revenue_d30,
        installs=installs,
        ctr=ctr,
        cpi=cpi,
        roas_d7=roas_d7,
        roas_d30=roas_d30,
        retention_d7=0.3,
        payer_rate=0.05,
    )


def _make_creative(
    creative_id: str = "cr_001",
    dna_id: str = "dna_001",
    spend: float = 500.0,
    revenue: float = 800.0,
    roi: float = 1.6,
    ctr: float = 0.03,
    installs: int = 500,
    roas_d30: float = 1.6,
    score: float = 0.7,
) -> CreativeReality:
    return CreativeReality(
        creative_id=creative_id,
        dna_id=dna_id,
        spend=spend,
        revenue=revenue,
        roi=roi,
        ctr=ctr,
        cpi=1.0,
        installs=installs,
        payer_rate=0.05,
        ltv=1200.0,
        roas_d30=roas_d30,
        performance_score=score,
    )


def _make_snapshot(
    campaign_ids: list[str] | None = None,
    creative_ids: list[str] | None = None,
) -> RealitySnapshot:
    if campaign_ids is None:
        campaign_ids = ["camp_001"]
    if creative_ids is None:
        creative_ids = ["cr_001"]

    campaigns = [_make_campaign(cid) for cid in campaign_ids]
    creatives = [_make_creative(cid) for cid in creative_ids]

    return RealitySnapshot(
        period_start="2024-01-01",
        period_end="2024-01-07",
        campaigns=campaigns,
        creatives=creatives,
        total_spend=sum(c.spend for c in campaigns),
        total_revenue=sum(c.revenue_d30 for c in campaigns),
        total_installs=sum(c.installs for c in campaigns),
        summary="Test",
    )


# ================================================================
# Models
# ================================================================


class TestInsightType:
    def test_all_types(self):
        assert InsightType.CREATIVE_FATIGUE.value == "creative_fatigue"
        assert InsightType.PERFORMANCE_DROP.value == "performance_drop"
        assert InsightType.WINNING_PATTERN.value == "winning_pattern"
        assert InsightType.MARKET_SHIFT.value == "market_shift"
        assert InsightType.SCALE_OPPORTUNITY.value == "scale_opportunity"
        assert InsightType.DATA_ANOMALY.value == "data_anomaly"


class TestSeverityLevel:
    def test_all_levels(self):
        assert SeverityLevel.CRITICAL.value == "critical"
        assert SeverityLevel.HIGH.value == "high"
        assert SeverityLevel.MEDIUM.value == "medium"
        assert SeverityLevel.LOW.value == "low"


class TestRealityInsight:
    def test_creation_defaults(self):
        ri = RealityInsight()
        assert ri.insight_id.startswith("ri_")
        assert ri.type == InsightType.PERFORMANCE_DROP
        assert ri.severity == SeverityLevel.MEDIUM

    def test_creation_with_fields(self):
        ri = RealityInsight(
            type=InsightType.CREATIVE_FATIGUE,
            severity=SeverityLevel.HIGH,
            confidence=0.89,
            target="cr_001",
            evidence=["CTR dropped 42%"],
            recommended_action="MUTATE_HOOK",
            priority=0.91,
        )
        assert ri.type == InsightType.CREATIVE_FATIGUE
        assert ri.confidence == 0.89
        assert ri.target == "cr_001"
        assert ri.priority == 0.91

    def test_is_actionable_high(self):
        ri = RealityInsight(severity=SeverityLevel.HIGH, confidence=0.85)
        assert ri.is_actionable

    def test_is_actionable_low_confidence(self):
        ri = RealityInsight(severity=SeverityLevel.HIGH, confidence=0.6)
        assert not ri.is_actionable

    def test_is_actionable_medium(self):
        ri = RealityInsight(severity=SeverityLevel.MEDIUM, confidence=0.9)
        assert not ri.is_actionable

    def test_is_high_confidence(self):
        assert RealityInsight(confidence=0.9).is_high_confidence
        assert not RealityInsight(confidence=0.7).is_high_confidence

    def test_to_dict(self):
        ri = RealityInsight(
            type=InsightType.CREATIVE_FATIGUE,
            severity=SeverityLevel.HIGH,
            confidence=0.89,
            evidence=["CTR drop"],
        )
        d = ri.to_dict()
        assert d["type"] == "creative_fatigue"
        assert d["severity"] == "high"
        assert d["is_actionable"] is True

    def test_to_evolution_opportunity(self):
        ri = RealityInsight(
            type=InsightType.CREATIVE_FATIGUE,
            confidence=0.89,
            priority=0.91,
            evidence=["CTR drop"],
        )
        opp = ri.to_evolution_opportunity()
        assert opp["type"] == "creative_fatigue"
        assert opp["score"] == 0.91
        assert "CTR drop" in opp["evidence"]

    def test_repr(self):
        ri = RealityInsight(type=InsightType.CREATIVE_FATIGUE, confidence=0.89)
        assert "creative_fatigue" in repr(ri)
        assert "0.89" in repr(ri)


class TestPerformanceInsight:
    def test_creation(self):
        pi = PerformanceInsight(
            creative_id="cr_001",
            metric="ROAS",
            current_value=0.8,
            previous_value=1.2,
            change_pct=-0.33,
            direction=-1,
            severity=SeverityLevel.HIGH,
        )
        assert pi.creative_id == "cr_001"
        assert pi.metric == "ROAS"
        assert pi.change_pct == -0.33

    def test_to_dict(self):
        pi = PerformanceInsight(creative_id="cr_001", metric="CTR", change_pct=-0.25)
        d = pi.to_dict()
        assert d["metric"] == "CTR"
        assert d["change_pct"] == -0.25

    def test_repr(self):
        pi = PerformanceInsight(creative_id="cr_001", metric="ROAS", change_pct=-0.33)
        assert "cr_001" in repr(pi)
        assert "-33%" in repr(pi)


class TestFatigueInsight:
    def test_creation(self):
        fi = FatigueInsight(
            creative_id="cr_001",
            fatigue_score=0.85,
            ctr_decay=0.4,
            roas_decay=0.35,
            frequency=8.0,
            days_since_launch=14,
            severity=SeverityLevel.HIGH,
        )
        assert fi.fatigue_score == 0.85
        assert fi.is_fatigued
        assert fi.is_severely_fatigued

    def test_not_fatigued(self):
        fi = FatigueInsight(fatigue_score=0.3)
        assert not fi.is_fatigued
        assert not fi.is_severely_fatigued

    def test_to_dict(self):
        fi = FatigueInsight(creative_id="cr_001", fatigue_score=0.7)
        d = fi.to_dict()
        assert d["fatigue_score"] == 0.7

    def test_repr(self):
        fi = FatigueInsight(creative_id="cr_001", fatigue_score=0.85)
        assert "cr_001" in repr(fi)
        assert "0.85" in repr(fi)


class TestAnomalyInsight:
    def test_creation(self):
        ai = AnomalyInsight(
            campaign_id="camp_001",
            anomaly_type="SPEND_SURGE",
            metric="spend",
            expected_value=500.0,
            actual_value=1500.0,
            deviation_pct=2.0,
            severity=SeverityLevel.CRITICAL,
        )
        assert ai.is_significant
        assert ai.deviation_pct == 2.0

    def test_not_significant(self):
        ai = AnomalyInsight(deviation_pct=0.3)
        assert not ai.is_significant

    def test_to_dict(self):
        ai = AnomalyInsight(
            campaign_id="camp_001",
            anomaly_type="SPEND_SURGE",
            deviation_pct=2.0,
        )
        d = ai.to_dict()
        assert d["anomaly_type"] == "SPEND_SURGE"

    def test_repr(self):
        ai = AnomalyInsight(
            campaign_id="camp_001",
            anomaly_type="SPEND_SURGE",
            deviation_pct=2.0,
        )
        assert "camp_001" in repr(ai)


class TestCombinedInsight:
    def test_creation(self):
        ci = CombinedInsight(
            insights=[],
            primary_type=InsightType.CREATIVE_FATIGUE,
            aggregated_confidence=0.85,
            aggregated_priority=0.9,
            severity=SeverityLevel.HIGH,
            recommended_action="MUTATE",
        )
        assert ci.primary_type == InsightType.CREATIVE_FATIGUE
        assert ci.aggregated_confidence == 0.85

    def test_to_dict(self):
        ci = CombinedInsight(primary_type=InsightType.CREATIVE_FATIGUE)
        d = ci.to_dict()
        assert d["primary_type"] == "creative_fatigue"
        assert d["insight_count"] == 0

    def test_repr(self):
        ci = CombinedInsight(primary_type=InsightType.CREATIVE_FATIGUE)
        assert "creative_fatigue" in repr(ci)


class TestTrendInsight:
    def test_creation(self):
        ti = TrendInsight(
            trend_type="market_shift",
            metric="ROI",
            current_value=0.8,
            trend_direction=-1,
            trend_strength=0.7,
        )
        assert ti.trend_type == "market_shift"
        assert ti.trend_strength == 0.7

    def test_to_dict(self):
        ti = TrendInsight(trend_type="market_shift", metric="ROI")
        d = ti.to_dict()
        assert d["trend_type"] == "market_shift"


# ================================================================
# PerformanceAnalyzer
# ================================================================


class TestPerformanceAnalyzer:
    def test_creation(self):
        pa = PerformanceAnalyzer()
        assert pa.total_analyzed == 0

    def test_analyze_no_previous(self):
        pa = PerformanceAnalyzer()
        current = _make_snapshot(["camp_001"])
        insights = pa.analyze(current)
        assert isinstance(insights, list)

    def test_analyze_with_roas_drop(self):
        pa = PerformanceAnalyzer()
        current = _make_snapshot(["camp_001"])
        prev = _make_snapshot(["camp_001"])
        # 修改 current 的 ROAS 为下降 40%
        current.campaigns[0].roas_d7 = 0.6  # 从 1.0 降到 0.6 = -40%
        prev.campaigns[0].roas_d7 = 1.0

        insights = pa.analyze(current, prev)
        assert len(insights) >= 1
        perf = [i for i in insights if i.type == InsightType.PERFORMANCE_DROP]
        assert len(perf) >= 1

    def test_analyze_with_ctr_drop(self):
        pa = PerformanceAnalyzer()
        current = _make_snapshot(["camp_001"])
        prev = _make_snapshot(["camp_001"])
        current.campaigns[0].ctr = 0.015  # 从 0.03 降到 0.015 = -50%
        prev.campaigns[0].ctr = 0.03

        insights = pa.analyze(current, prev)
        fatigue = [i for i in insights if i.type == InsightType.CREATIVE_FATIGUE]
        assert len(fatigue) >= 1

    def test_analyze_no_significant_change(self):
        pa = PerformanceAnalyzer()
        current = _make_snapshot(["camp_001"])
        prev = _make_snapshot(["camp_001"])
        # 变化很小
        current.campaigns[0].roas_d7 = 1.05
        prev.campaigns[0].roas_d7 = 1.0

        insights = pa.analyze(current, prev)
        perf = [i for i in insights if i.type == InsightType.PERFORMANCE_DROP]
        assert len(perf) == 0

    def test_analyze_single(self):
        pa = PerformanceAnalyzer()
        current = _make_campaign("camp_001", roas_d7=0.6)
        prev = _make_campaign("camp_001", roas_d7=1.0)
        results = pa.analyze_single(current, prev)
        assert len(results) >= 3  # ROAS + CTR + CPI
        assert results[0].metric == "ROAS"
        assert results[0].direction == -1

    def test_analyze_single_no_previous(self):
        pa = PerformanceAnalyzer()
        current = _make_campaign("camp_001")
        results = pa.analyze_single(current)
        assert results == []

    def test_analyze_creative_roas_drop(self):
        pa = PerformanceAnalyzer()
        current = _make_snapshot(["camp_001"], ["cr_001"])
        prev = _make_snapshot(["camp_001"], ["cr_001"])
        current.creatives[0].roas_d30 = 0.5  # -50% from 1.6
        prev.creatives[0].roas_d30 = 1.0

        insights = pa.analyze(current, prev)
        perf = [i for i in insights if i.type == InsightType.PERFORMANCE_DROP]
        assert len(perf) >= 1

    def test_analyze_creative_ctr_drop(self):
        pa = PerformanceAnalyzer()
        current = _make_snapshot(["camp_001"], ["cr_001"])
        prev = _make_snapshot(["camp_001"], ["cr_001"])
        current.creatives[0].ctr = 0.015
        prev.creatives[0].ctr = 0.03

        insights = pa.analyze(current, prev)
        fatigue = [i for i in insights if i.type == InsightType.CREATIVE_FATIGUE]
        assert len(fatigue) >= 1

    def test_repr(self):
        pa = PerformanceAnalyzer()
        assert "PerformanceAnalyzer" in repr(pa)


# ================================================================
# FatigueDetector
# ================================================================


class TestFatigueDetector:
    def test_creation(self):
        fd = FatigueDetector()
        assert fd.total_detected == 0

    def test_detect_fatigued(self):
        fd = FatigueDetector()
        creative = _make_creative("cr_001", ctr=0.01, roas_d30=0.5)
        result = fd.detect(
            creative,
            peak_ctr=0.05,
            peak_roas=2.0,
            frequency=8.0,
            days_since_launch=14,
        )
        assert result.is_fatigued
        assert result.fatigue_score > 0.5
        assert len(result.evidence) >= 1

    def test_detect_severely_fatigued(self):
        fd = FatigueDetector()
        creative = _make_creative("cr_001", ctr=0.005, roas_d30=0.2)
        result = fd.detect(
            creative,
            peak_ctr=0.05,
            peak_roas=2.0,
            frequency=12.0,
            days_since_launch=35,
        )
        assert result.is_severely_fatigued
        assert result.fatigue_score >= 0.8

    def test_detect_not_fatigued(self):
        fd = FatigueDetector()
        creative = _make_creative("cr_001", ctr=0.045, roas_d30=1.8)
        result = fd.detect(
            creative,
            peak_ctr=0.05,
            peak_roas=2.0,
            frequency=2.0,
            days_since_launch=3,
        )
        assert not result.is_fatigued
        assert result.fatigue_score < 0.4

    def test_detect_no_peak_data(self):
        fd = FatigueDetector()
        creative = _make_creative("cr_001")
        result = fd.detect(creative)
        assert result.fatigue_score == 0.0
        assert result.evidence == []

    def test_detect_batch(self):
        fd = FatigueDetector()
        snapshot = _make_snapshot(["camp_001"], ["cr_001", "cr_002"])
        results = fd.detect_batch(snapshot)
        assert len(results) == 2

    def test_to_insights(self):
        fd = FatigueDetector()
        fi = FatigueInsight(
            creative_id="cr_001",
            fatigue_score=0.85,
            ctr_decay=0.4,
            roas_decay=0.35,
            frequency=8.0,
            severity=SeverityLevel.HIGH,
            confidence=0.8,
            evidence=["CTR decayed 40%"],
        )
        insights = fd.to_insights([fi], "snap_001")
        assert len(insights) == 1
        assert insights[0].type == InsightType.CREATIVE_FATIGUE
        assert insights[0].severity == SeverityLevel.HIGH

    def test_to_insights_not_fatigued(self):
        fd = FatigueDetector()
        fi = FatigueInsight(fatigue_score=0.3)
        insights = fd.to_insights([fi])
        assert len(insights) == 0

    def test_repr(self):
        fd = FatigueDetector()
        assert "FatigueDetector" in repr(fd)


# ================================================================
# AnomalyDetector
# ================================================================


class TestAnomalyDetector:
    def test_creation(self):
        ad = AnomalyDetector()
        assert ad.total_detected == 0

    def test_detect_spend_surge(self):
        ad = AnomalyDetector()
        campaign = _make_campaign("camp_001", spend=1500.0)
        expected = {"spend": 500.0}
        anomalies = ad.detect(campaign, expected)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "SPEND_SURGE"
        assert anomalies[0].severity == SeverityLevel.CRITICAL

    def test_detect_spend_drop(self):
        ad = AnomalyDetector()
        campaign = _make_campaign("camp_001", spend=200.0)
        expected = {"spend": 500.0}
        anomalies = ad.detect(campaign, expected)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "SPEND_DROP"

    def test_detect_revenue_drop(self):
        ad = AnomalyDetector()
        campaign = _make_campaign("camp_001", revenue_d30=200.0)
        expected = {"revenue": 500.0}
        anomalies = ad.detect(campaign, expected)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "REVENUE_DROP"

    def test_detect_no_anomaly(self):
        ad = AnomalyDetector()
        campaign = _make_campaign("camp_001", spend=550.0)
        expected = {"spend": 500.0}
        anomalies = ad.detect(campaign, expected)
        assert len(anomalies) == 0

    def test_detect_low_spend_skipped(self):
        ad = AnomalyDetector()
        campaign = _make_campaign("camp_001", spend=50.0)
        expected = {"spend": 500.0}
        anomalies = ad.detect(campaign, expected)
        assert len(anomalies) == 0

    def test_detect_batch(self):
        ad = AnomalyDetector()
        snapshot = _make_snapshot(["camp_001", "camp_002"])
        expected_map = {
            "camp_001": {"spend": 500.0},
            "camp_002": {"spend": 500.0},
        }
        snapshot.campaigns[0].spend = 1500.0
        anomalies = ad.detect_batch(snapshot, expected_map)
        assert len(anomalies) == 1

    def test_to_insights(self):
        ad = AnomalyDetector()
        ai = AnomalyInsight(
            campaign_id="camp_001",
            anomaly_type="SPEND_SURGE",
            metric="spend",
            expected_value=500.0,
            actual_value=1500.0,
            deviation_pct=2.0,
            severity=SeverityLevel.CRITICAL,
            confidence=0.85,
        )
        insights = ad.to_insights([ai], "snap_001")
        assert len(insights) == 1
        assert insights[0].type == InsightType.DATA_ANOMALY

    def test_to_insights_not_significant(self):
        ad = AnomalyDetector()
        ai = AnomalyInsight(deviation_pct=0.3)
        insights = ad.to_insights([ai])
        assert len(insights) == 0

    def test_repr(self):
        ad = AnomalyDetector()
        assert "AnomalyDetector" in repr(ad)


# ================================================================
# ConfidenceEngine
# ================================================================


class TestConfidenceEngine:
    def test_creation(self):
        ce = ConfidenceEngine()
        assert ce.total_computed == 0

    def test_compute_with_high_quality(self):
        ce = ConfidenceEngine()
        ri = RealityInsight(
            severity=SeverityLevel.HIGH,
            confidence=0.8,
            priority=0.9,
            evidence=["e1", "e2", "e3"],
        )
        conf = ce.compute(ri, data_quality=0.9, signal_strength=0.9)
        assert conf > 0.7

    def test_compute_with_low_quality(self):
        ce = ConfidenceEngine()
        ri = RealityInsight(
            severity=SeverityLevel.LOW,
            priority=0.2,
            evidence=["e1"],
        )
        conf = ce.compute(ri, data_quality=0.3, signal_strength=0.3)
        assert conf < 0.5

    def test_compute_auto_estimate(self):
        ce = ConfidenceEngine()
        ri = RealityInsight(
            severity=SeverityLevel.HIGH,
            priority=0.9,
            evidence=["e1", "e2", "e3"],
        )
        conf = ce.compute(ri)
        assert conf > 0.5

    def test_compute_batch(self):
        ce = ConfidenceEngine()
        ris = [
            RealityInsight(severity=SeverityLevel.HIGH, priority=0.9, evidence=["e1", "e2"]),
            RealityInsight(severity=SeverityLevel.LOW, priority=0.2, evidence=["e1"]),
        ]
        confs = ce.compute_batch(ris)
        assert len(confs) == 2
        assert confs[0] > confs[1]

    def test_is_reliable(self):
        ce = ConfidenceEngine()
        assert ce.is_reliable(0.8)
        assert not ce.is_reliable(0.6)

    def test_is_highly_reliable(self):
        ce = ConfidenceEngine()
        assert ce.is_highly_reliable(0.9)
        assert not ce.is_highly_reliable(0.8)

    def test_with_historical_accuracy(self):
        ce = ConfidenceEngine(historical_accuracy=0.8)
        ri = RealityInsight(severity=SeverityLevel.HIGH, priority=0.9, evidence=["e1", "e2", "e3"])
        conf = ce.compute(ri, data_quality=0.9, signal_strength=0.9)
        # 历史准确率会提升置信度
        assert conf > 0.75

    def test_repr(self):
        ce = ConfidenceEngine()
        assert "ConfidenceEngine" in repr(ce)


# ================================================================
# RecommendationEngine
# ================================================================


class TestRecommendationEngine:
    def test_creation(self):
        re = RecommendationEngine()
        assert re.total_recommended == 0

    def test_recommend_fatigue(self):
        re = RecommendationEngine()
        ri = RealityInsight(
            type=InsightType.CREATIVE_FATIGUE,
            severity=SeverityLevel.HIGH,
            confidence=0.89,
            target="cr_001",
            priority=0.91,
            evidence=["CTR dropped"],
        )
        rec = re.recommend(ri)
        assert rec["action"] == "MUTATE_CREATIVE"
        assert "hook" in rec["genes"]
        assert "visual" in rec["genes"]
        assert rec["priority"] == 0.91

    def test_recommend_performance_drop(self):
        re = RecommendationEngine()
        ri = RealityInsight(
            type=InsightType.PERFORMANCE_DROP,
            severity=SeverityLevel.HIGH,
            confidence=0.85,
            target="cr_001",
        )
        rec = re.recommend(ri)
        assert rec["action"] == "EVALUATE_AND_MUTATE"
        assert "hook" in rec["genes"]

    def test_recommend_winning_pattern(self):
        re = RecommendationEngine()
        ri = RealityInsight(
            type=InsightType.WINNING_PATTERN,
            severity=SeverityLevel.HIGH,
            confidence=0.9,
            target="cr_001",
        )
        rec = re.recommend(ri)
        assert rec["action"] == "SCALE_CREATIVE"

    def test_recommend_data_anomaly(self):
        re = RecommendationEngine()
        ri = RealityInsight(
            type=InsightType.DATA_ANOMALY,
            severity=SeverityLevel.HIGH,
            confidence=0.8,
            target="camp_001",
        )
        rec = re.recommend(ri)
        assert rec["action"] == "VERIFY_AND_MONITOR"
        assert rec["genes"] == []

    def test_recommend_batch_sorted(self):
        re = RecommendationEngine()
        ris = [
            RealityInsight(type=InsightType.CREATIVE_FATIGUE, severity=SeverityLevel.HIGH, confidence=0.9, target="cr_001", priority=0.9),
            RealityInsight(type=InsightType.PERFORMANCE_DROP, severity=SeverityLevel.MEDIUM, confidence=0.7, target="cr_002", priority=0.5),
        ]
        recs = re.recommend_batch(ris)
        assert len(recs) == 2
        assert recs[0]["priority"] >= recs[1]["priority"]

    def test_recommend_from_combined(self):
        re = RecommendationEngine()
        ci = CombinedInsight(
            primary_type=InsightType.CREATIVE_FATIGUE,
            aggregated_confidence=0.85,
            aggregated_priority=0.9,
            recommended_action="MUTATE",
        )
        rec = re.recommend_from_combined(ci)
        assert rec["action"] == "MUTATE"
        assert rec["target"] == "ALL"

    def test_to_evolution_opportunities(self):
        re = RecommendationEngine()
        recommendations = [
            {
                "action": "MUTATE_CREATIVE",
                "target": "cr_001",
                "priority": 0.9,
                "genes": ["hook"],
                "confidence": 0.85,
                "reason": "Fatigue detected",
            },
        ]
        opps = re.to_evolution_opportunities(recommendations)
        assert len(opps) == 1
        assert opps[0]["type"] == "MUTATE_CREATIVE"
        assert opps[0]["score"] == 0.9

    def test_repr(self):
        re = RecommendationEngine()
        assert "RecommendationEngine" in repr(re)


# ================================================================
# InsightEngine
# ================================================================


class TestInsightEngine:
    def test_creation(self):
        engine = InsightEngine()
        assert engine.total_analyzed == 0
        assert engine.performance_analyzer is not None
        assert engine.fatigue_detector is not None
        assert engine.anomaly_detector is not None

    def test_analyze_no_issues(self):
        engine = InsightEngine()
        current = _make_snapshot(["camp_001"], ["cr_001"])
        combined = engine.analyze(current)
        assert isinstance(combined, CombinedInsight)

    def test_analyze_with_performance_drop(self):
        engine = InsightEngine()
        current = _make_snapshot(["camp_001"], ["cr_001"])
        prev = _make_snapshot(["camp_001"], ["cr_001"])
        current.campaigns[0].roas_d7 = 0.5
        prev.campaigns[0].roas_d7 = 1.0
        current.creatives[0].roas_d30 = 0.5
        prev.creatives[0].roas_d30 = 1.0

        combined = engine.analyze(current, prev)
        assert len(combined.insights) >= 1

    def test_analyze_with_fatigue(self):
        engine = InsightEngine()
        current = _make_snapshot(["camp_001"], ["cr_001"])
        peak_data = {
            "cr_001": {
                "peak_ctr": 0.05,
                "peak_roas": 2.0,
                "frequency": 8.0,
                "days_since_launch": 14,
            },
        }
        current.creatives[0].ctr = 0.01
        current.creatives[0].roas_d30 = 0.5

        combined = engine.analyze(current, peak_data=peak_data)
        assert len(combined.insights) >= 1
        fatigue = [i for i in combined.insights if i.type == InsightType.CREATIVE_FATIGUE]
        assert len(fatigue) >= 1

    def test_analyze_with_anomaly(self):
        engine = InsightEngine()
        current = _make_snapshot(["camp_001"], ["cr_001"])
        expected_map = {"camp_001": {"spend": 500.0}}
        current.campaigns[0].spend = 1500.0

        combined = engine.analyze(current, expected_map=expected_map)
        assert len(combined.insights) >= 1
        anomaly = [i for i in combined.insights if i.type == InsightType.DATA_ANOMALY]
        assert len(anomaly) >= 1

    def test_deduplicate(self):
        engine = InsightEngine()
        ri1 = RealityInsight(
            type=InsightType.CREATIVE_FATIGUE,
            target="cr_001",
            confidence=0.8,
            priority=0.7,
        )
        ri2 = RealityInsight(
            type=InsightType.CREATIVE_FATIGUE,
            target="cr_001",
            confidence=0.9,
            priority=0.85,
        )
        deduped = engine._deduplicate([ri1, ri2])
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.9

    def test_get_actionable_insights(self):
        engine = InsightEngine()
        ci = CombinedInsight(insights=[
            RealityInsight(severity=SeverityLevel.HIGH, confidence=0.85, priority=0.9),
            RealityInsight(severity=SeverityLevel.LOW, confidence=0.5, priority=0.3),
        ])
        actionable = engine.get_actionable_insights(ci)
        assert len(actionable) == 1

    def test_get_top_insights(self):
        engine = InsightEngine()
        ci = CombinedInsight(insights=[
            RealityInsight(priority=0.3),
            RealityInsight(priority=0.9),
            RealityInsight(priority=0.6),
        ])
        top = engine.get_top_insights(ci, n=2)
        assert len(top) == 2
        assert top[0].priority == 0.9

    def test_repr(self):
        engine = InsightEngine()
        assert "InsightEngine" in repr(engine)


# ================================================================
# InsightBridge
# ================================================================


class TestInsightBridge:
    def test_creation(self):
        bridge = InsightBridge()
        assert bridge.total_bridged == 0

    def test_to_opportunities(self):
        bridge = InsightBridge()
        ris = [
            RealityInsight(
                type=InsightType.CREATIVE_FATIGUE,
                severity=SeverityLevel.HIGH,
                confidence=0.85,
                target="cr_001",
                priority=0.9,
                evidence=["CTR dropped"],
            ),
            RealityInsight(
                type=InsightType.PERFORMANCE_DROP,
                severity=SeverityLevel.HIGH,
                confidence=0.8,
                target="cr_002",
                priority=0.85,
                evidence=["ROAS dropped"],
            ),
        ]
        opps = bridge.to_opportunities(ris)
        assert len(opps) == 2
        assert opps[0]["type"] == "creative_fatigue"

    def test_to_opportunities_filters_non_actionable(self):
        bridge = InsightBridge()
        ris = [
            RealityInsight(
                severity=SeverityLevel.LOW,
                confidence=0.5,
                priority=0.2,
            ),
        ]
        opps = bridge.to_opportunities(ris)
        assert len(opps) == 0

    def test_to_market_signal(self):
        bridge = InsightBridge()
        ci = CombinedInsight(
            insights=[
                RealityInsight(type=InsightType.CREATIVE_FATIGUE, priority=0.9),
                RealityInsight(type=InsightType.PERFORMANCE_DROP, priority=0.8),
            ],
            primary_type=InsightType.CREATIVE_FATIGUE,
            aggregated_confidence=0.85,
            aggregated_priority=0.9,
            severity=SeverityLevel.HIGH,
        )
        signal = bridge.to_market_signal(ci)
        assert "metrics" in signal
        assert "trends" in signal
        assert "usage_count" in signal
        assert signal["trends"]["CTR"] == -0.25

    def test_bridge_and_enrich(self):
        bridge = InsightBridge()
        ci = CombinedInsight(
            insights=[
                RealityInsight(
                    type=InsightType.CREATIVE_FATIGUE,
                    severity=SeverityLevel.HIGH,
                    confidence=0.85,
                    target="cr_001",
                    priority=0.9,
                    evidence=["CTR dropped"],
                ),
            ],
            primary_type=InsightType.CREATIVE_FATIGUE,
            aggregated_confidence=0.85,
            aggregated_priority=0.9,
            severity=SeverityLevel.HIGH,
        )
        result = bridge.bridge_and_enrich(ci)
        assert "opportunities" in result
        assert "market_signal" in result
        assert "summary" in result
        assert len(result["opportunities"]) == 1

    def test_repr(self):
        bridge = InsightBridge()
        assert "InsightBridge" in repr(bridge)


# ================================================================
# Full Pipeline
# ================================================================


class TestFullPipeline:
    def test_analyze_to_bridge(self):
        """完整管线：Snapshot → Analyzers → InsightEngine → InsightBridge → Opportunities。"""
        # 1. 创建数据（高数据量确保置信度足够）
        current = _make_snapshot(["camp_001"], ["cr_001"])
        prev = _make_snapshot(["camp_001"], ["cr_001"])
        # 高 installs → 高置信度
        current.campaigns[0].installs = 5000
        current.campaigns[0].roas_d7 = 0.5
        prev.campaigns[0].roas_d7 = 1.0
        current.creatives[0].installs = 5000
        current.creatives[0].ctr = 0.01
        prev.creatives[0].ctr = 0.03

        peak_data = {
            "cr_001": {
                "peak_ctr": 0.05,
                "peak_roas": 2.0,
                "frequency": 8.0,
                "days_since_launch": 14,
            },
        }

        # 2. 分析
        engine = InsightEngine()
        combined = engine.analyze(current, prev, peak_data=peak_data)

        assert len(combined.insights) >= 1

        # 3. 桥接
        bridge = InsightBridge()
        result = bridge.bridge_and_enrich(combined)

        assert len(result["opportunities"]) >= 1
        assert "market_signal" in result

    def test_recommendation_to_evolution(self):
        """推荐 → E11 格式。"""
        re = RecommendationEngine()
        bridge = InsightBridge()

        ris = [
            RealityInsight(
                type=InsightType.CREATIVE_FATIGUE,
                severity=SeverityLevel.HIGH,
                confidence=0.89,
                target="cr_001",
                priority=0.91,
            ),
        ]
        recs = re.recommend_batch(ris)
        opps = re.to_evolution_opportunities(recs)
        assert len(opps) == 1
        assert opps[0]["type"] == "MUTATE_CREATIVE"


# ================================================================
# Package Exports
# ================================================================


class TestPackageExports:
    def test_models_imports(self):
        from market_ops.creative_vision_runtime.reality import (
            InsightType,
            SeverityLevel,
            RealityInsight,
            PerformanceInsight,
            FatigueInsight,
            AnomalyInsight,
            TrendInsight,
            CombinedInsight,
        )
        assert InsightType is not None
        assert SeverityLevel is not None
        assert RealityInsight is not None
        assert PerformanceInsight is not None
        assert FatigueInsight is not None
        assert AnomalyInsight is not None
        assert TrendInsight is not None
        assert CombinedInsight is not None

    def test_analyzers_imports(self):
        from market_ops.creative_vision_runtime.reality import (
            PerformanceAnalyzer,
            FatigueDetector,
            AnomalyDetector,
        )
        assert PerformanceAnalyzer is not None
        assert FatigueDetector is not None
        assert AnomalyDetector is not None

    def test_intelligence_imports(self):
        from market_ops.creative_vision_runtime.reality import (
            ConfidenceEngine,
            RecommendationEngine,
            InsightEngine,
        )
        assert ConfidenceEngine is not None
        assert RecommendationEngine is not None
        assert InsightEngine is not None

    def test_bridge_imports(self):
        from market_ops.creative_vision_runtime.reality import InsightBridge
        assert InsightBridge is not None

    def test_analyzers_subpackage(self):
        from market_ops.creative_vision_runtime.reality.analyzers import (
            PerformanceAnalyzer,
            FatigueDetector,
            AnomalyDetector,
        )
        assert PerformanceAnalyzer is not None

    def test_intelligence_subpackage(self):
        from market_ops.creative_vision_runtime.reality.intelligence import (
            InsightType,
            InsightEngine,
            ConfidenceEngine,
            RecommendationEngine,
        )
        assert InsightEngine is not None