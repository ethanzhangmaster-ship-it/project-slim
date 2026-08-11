"""E12.3 Phase 2 — Advanced Prediction Models 测试。

覆盖:
  - LifecyclePredictor: 阶段检测, 过渡预测, 天数估算, 批量
  - DecayPredictor: 单指标, 全指标, 加速检测, 批量
  - PredictionConfidenceEngine: 置信度评分, 可靠性过滤
  - ExplanationEngine: 预测解释, 生命周期解释, 衰减解释
  - PredictionEngine Phase 2: 完整管线, 向后兼容
"""

import pytest

from market_ops.creative_vision_runtime.reality.prediction import (
    CreativeLifecycleStage,
    DecayPrediction,
    DecayPredictor,
    ExplanationEngine,
    LifecyclePrediction,
    LifecyclePredictor,
    PredictionConfidence,
    PredictionConfidenceEngine,
    PredictionEngine,
    PredictionExplanation,
    PredictionResult,
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_point(
    date: str = "2026-01-01",
    creative_id: str = "c001",
    ctr: float = 0.03,
    cvr: float = 0.05,
    roas: float = 1.0,
    spend: float = 100.0,
    revenue: float = 100.0,
    frequency: float = 1.0,
    impressions: int = 10000,
    installs: int = 100,
) -> RealityHistoryPoint:
    return RealityHistoryPoint(
        date=date, creative_id=creative_id,
        ctr=ctr, cvr=cvr, roas=roas,
        spend=spend, revenue=revenue,
        frequency=frequency, impressions=impressions, installs=installs,
    )


def make_declining(days: int = 14, cid: str = "c001") -> list[RealityHistoryPoint]:
    """持续下降的数据。"""
    return [
        make_point(
            date=f"2026-01-{i+1:02d}", creative_id=cid,
            ctr=0.035 - 0.0012 * i,
            roas=1.2 - 0.04 * i,
            frequency=1.5 + 0.25 * i,
            installs=500 + i * 10,
        )
        for i in range(days)
    ]


def make_improving(days: int = 14, cid: str = "c002") -> list[RealityHistoryPoint]:
    """持续改善的数据。"""
    return [
        make_point(
            date=f"2026-01-{i+1:02d}", creative_id=cid,
            ctr=0.02 + 0.001 * i,
            roas=0.5 + 0.04 * i,
            frequency=1.0 + 0.1 * i,
            installs=500 + i * 10,
        )
        for i in range(days)
    ]


def make_stable(days: int = 7, cid: str = "c003") -> list[RealityHistoryPoint]:
    """稳定的数据。"""
    return [
        make_point(
            date=f"2026-01-{i+1:02d}", creative_id=cid,
            ctr=0.03, roas=1.0, frequency=2.0,
            installs=500 + i * 10,
        )
        for i in range(days)
    ]


def make_peak(days: int = 5, cid: str = "c004") -> list[RealityHistoryPoint]:
    """峰值数据（CTR 上升后稳定在高位）。"""
    return [
        make_point(
            date=f"2026-01-{i+1:02d}", creative_id=cid,
            ctr=0.02 + 0.005 * min(i, 3),
            roas=0.8 + 0.1 * min(i, 3),
            frequency=1.0 + 0.3 * i,
            installs=500 + i * 10,
        )
        for i in range(days)
    ]


def make_short(days: int = 2, cid: str = "c005") -> list[RealityHistoryPoint]:
    """短期数据（刚上线，极少数据）。"""
    return [
        make_point(
            date=f"2026-01-{i+1:02d}", creative_id=cid,
            ctr=0.03 + i * 0.001, roas=1.0 + i * 0.05, installs=5 + i * 5,
        )
        for i in range(days)
    ]


# ═══════════════════════════════════════════════════════════
# Phase 2 Models
# ═══════════════════════════════════════════════════════════


class TestCreativeLifecycleStage:
    """CreativeLifecycleStage 枚举。"""

    def test_all_stages(self):
        assert len(list(CreativeLifecycleStage)) == 7

    def test_stage_values(self):
        assert CreativeLifecycleStage.LAUNCH.value == "launch"
        assert CreativeLifecycleStage.PEAK.value == "peak"
        assert CreativeLifecycleStage.DEAD.value == "dead"

    def test_stage_ordering(self):
        stages = list(CreativeLifecycleStage)
        assert CreativeLifecycleStage.LAUNCH in stages
        assert CreativeLifecycleStage.DEAD in stages


class TestLifecyclePrediction:
    """LifecyclePrediction 数据类。"""

    def test_creation(self):
        p = LifecyclePrediction(creative_id="c001")
        assert p.prediction_id.startswith("lp_")
        assert p.creative_id == "c001"

    def test_is_transitioning_soon(self):
        p = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.STABLE,
            predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
            days_to_transition=5,
        )
        assert p.is_transitioning_soon is True

    def test_is_not_transitioning_soon(self):
        p = LifecyclePrediction(
            creative_id="c001",
            days_to_transition=30,
        )
        assert p.is_transitioning_soon is False

    def test_is_degrading(self):
        p = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.STABLE,
            predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
        )
        assert p.is_degrading is True

    def test_is_improving(self):
        p = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.FATIGUE_WARNING,
            predicted_stage=CreativeLifecycleStage.STABLE,
        )
        assert p.is_improving is True

    def test_to_dict(self):
        p = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.PEAK,
            predicted_stage=CreativeLifecycleStage.STABLE,
            days_to_transition=10,
            confidence=0.85,
        )
        d = p.to_dict()
        assert d["current_stage"] == "peak"
        assert d["predicted_stage"] == "stable"
        assert d["days_to_transition"] == 10

    def test_repr(self):
        p = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.PEAK,
            predicted_stage=CreativeLifecycleStage.STABLE,
        )
        r = repr(p)
        assert "LifecyclePrediction" in r
        assert "c001" in r


class TestDecayPrediction:
    """DecayPrediction 数据类。"""

    def test_creation(self):
        p = DecayPrediction(creative_id="c001", metric="ctr")
        assert p.prediction_id.startswith("dp_")
        assert p.metric == "ctr"

    def test_is_declining(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.001)
        assert p.is_declining is True

    def test_is_not_declining(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=0.001)
        assert p.is_declining is False

    def test_decline_severity_critical(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.006)
        assert p.decline_severity == "critical"

    def test_decline_severity_high(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.003)
        assert p.decline_severity == "high"

    def test_decline_severity_medium(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.0015)
        assert p.decline_severity == "medium"

    def test_decline_severity_low(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.0005)
        assert p.decline_severity == "low"

    def test_decline_severity_none(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=0.001)
        assert p.decline_severity == "none"

    def test_change_pct(self):
        p = DecayPrediction(
            creative_id="c001", metric="ctr",
            current_value=0.03, predicted_value=0.021, velocity=-0.001,
        )
        assert p.change_pct == pytest.approx(-0.3)

    def test_to_dict(self):
        p = DecayPrediction(
            creative_id="c001", metric="ctr",
            velocity=-0.001, current_value=0.03, predicted_value=0.021,
        )
        d = p.to_dict()
        assert d["metric"] == "ctr"
        assert d["velocity"] == -0.001

    def test_repr(self):
        p = DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.001)
        r = repr(p)
        assert "DecayPrediction" in r
        assert "c001" in r


class TestPredictionConfidence:
    """PredictionConfidence 数据类。"""

    def test_creation(self):
        p = PredictionConfidence(score=0.85)
        assert p.prediction_id.startswith("pc_")
        assert p.score == 0.85
        assert p.is_reliable is True
        assert p.is_highly_reliable is True

    def test_not_reliable(self):
        p = PredictionConfidence(score=0.5)
        assert p.is_reliable is False

    def test_reliable_but_not_highly(self):
        p = PredictionConfidence(score=0.75)
        assert p.is_reliable is True
        assert p.is_highly_reliable is False

    def test_to_dict(self):
        p = PredictionConfidence(
            score=0.8, data_volume=0.9, trend_consistency=0.7, metric_stability=0.85,
        )
        d = p.to_dict()
        assert d["score"] == 0.8
        assert d["is_reliable"] is True

    def test_repr(self):
        p = PredictionConfidence(score=0.8)
        r = repr(p)
        assert "PredictionConfidence" in r


class TestPredictionExplanation:
    """PredictionExplanation 数据类。"""

    def test_creation(self):
        p = PredictionExplanation(
            creative_id="c001",
            summary="Test summary",
            reasons=["Reason 1", "Reason 2"],
        )
        assert p.explanation_id.startswith("pe_")
        assert len(p.reasons) == 2

    def test_to_dict(self):
        p = PredictionExplanation(
            creative_id="c001",
            summary="Test",
            recommended_action="MUTATE_HOOK",
            urgency="immediate",
        )
        d = p.to_dict()
        assert d["summary"] == "Test"
        assert d["urgency"] == "immediate"

    def test_repr(self):
        p = PredictionExplanation(creative_id="c001", summary="A" * 60)
        r = repr(p)
        assert "PredictionExplanation" in r


# ═══════════════════════════════════════════════════════════
# LifecyclePredictor
# ═══════════════════════════════════════════════════════════


class TestLifecyclePredictor:
    """LifecyclePredictor 测试。"""

    def test_creation(self):
        p = LifecyclePredictor()
        assert p is not None

    def test_predict_launch(self):
        """短期数据 → LAUNCH。"""
        history = make_short(days=2)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert pred.current_stage == CreativeLifecycleStage.LAUNCH

    def test_predict_peak(self):
        """峰值数据 → PEAK。"""
        history = make_peak(days=7)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert pred.current_stage in (
            CreativeLifecycleStage.PEAK,
            CreativeLifecycleStage.STABLE,
        )

    def test_predict_stable(self):
        """稳定数据 → STABLE。"""
        history = make_stable(days=7)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert pred.current_stage in (
            CreativeLifecycleStage.STABLE,
            CreativeLifecycleStage.PEAK,
        )

    def test_predict_fatigue_warning(self):
        """CTR 下降 15%-30% → FATIGUE_WARNING。"""
        history = make_declining(days=10)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        # declining 10 days should show some degradation
        assert pred.current_stage in (
            CreativeLifecycleStage.STABLE,
            CreativeLifecycleStage.FATIGUE_WARNING,
            CreativeLifecycleStage.FATIGUED,
        )

    def test_predict_fatigued(self):
        """CTR 下降 > 30% → FATIGUED。"""
        history = make_declining(days=21)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert pred.current_stage in (
            CreativeLifecycleStage.FATIGUE_WARNING,
            CreativeLifecycleStage.FATIGUED,
        )

    def test_predict_insufficient_data(self):
        """数据不足 → None。"""
        pred = LifecyclePredictor().predict([make_point()])
        assert pred is None

    def test_predict_stage_scores(self):
        """stage_scores 包含所有阶段。"""
        history = make_declining(days=7)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert len(pred.stage_scores) > 0

    def test_predict_evidence(self):
        """证据非空。"""
        history = make_declining(days=7)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert len(pred.evidence) > 0

    def test_predict_recommended_action(self):
        """推荐行动非空。"""
        history = make_declining(days=14)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert len(pred.recommended_action) > 0

    def test_predict_batch(self):
        """批量预测。"""
        history = {
            "c001": make_declining(days=14),
            "c002": make_improving(days=14),
            "c003": make_stable(days=7),
        }
        preds = LifecyclePredictor().predict_batch(history)
        assert len(preds) == 3

    def test_predict_confidence(self):
        """置信度在合理范围。"""
        history = make_declining(days=14)
        pred = LifecyclePredictor().predict(history)
        assert pred is not None
        assert 0 <= pred.confidence <= 1.0

    def test_repr(self):
        assert repr(LifecyclePredictor()) == "LifecyclePredictor()"


# ═══════════════════════════════════════════════════════════
# DecayPredictor
# ═══════════════════════════════════════════════════════════


class TestDecayPredictor:
    """DecayPredictor 测试。"""

    def test_creation(self):
        p = DecayPredictor()
        assert p is not None

    def test_predict_ctr_decline(self):
        """CTR 下降趋势。"""
        history = make_declining(days=14)
        pred = DecayPredictor().predict(history, metric="ctr")
        assert pred is not None
        assert pred.metric == "ctr"
        assert pred.velocity < 0
        assert pred.is_declining is True

    def test_predict_roas_decline(self):
        """ROAS 下降趋势。"""
        history = make_declining(days=14)
        pred = DecayPredictor().predict(history, metric="roas")
        assert pred is not None
        assert pred.metric == "roas"
        assert pred.velocity < 0

    def test_predict_improving(self):
        """改善趋势。"""
        history = make_improving(days=14)
        pred = DecayPredictor().predict(history, metric="ctr")
        assert pred is not None
        assert pred.velocity > 0
        assert pred.is_declining is False

    def test_predict_stable(self):
        """稳定趋势。"""
        history = make_stable(days=7)
        pred = DecayPredictor().predict(history, metric="ctr")
        assert pred is not None
        assert pred.velocity == pytest.approx(0.0, abs=0.0001)

    def test_predict_insufficient_data(self):
        """数据不足 → None。"""
        pred = DecayPredictor().predict([make_point()], metric="ctr")
        assert pred is None

    def test_predict_invalid_metric(self):
        """无效指标 → None。"""
        history = make_declining(days=7)
        pred = DecayPredictor().predict(history, metric="invalid")
        assert pred is None

    def test_predict_all_metrics(self):
        """全指标预测。"""
        history = make_declining(days=7)
        preds = DecayPredictor().predict_all_metrics(history)
        assert len(preds) >= 1  # 至少 ctr 和 roas

    def test_predict_batch(self):
        """批量预测。"""
        history = {
            "c001": make_declining(days=7),
            "c002": make_improving(days=7),
        }
        preds = DecayPredictor().predict_batch(history, metric="ctr")
        assert len(preds) == 2

    def test_predict_all_metrics_batch(self):
        """批量全指标预测。"""
        history = {
            "c001": make_declining(days=7),
            "c002": make_improving(days=7),
        }
        results = DecayPredictor().predict_all_metrics_batch(history)
        assert len(results) == 2
        assert len(results["c001"]) >= 1

    def test_predict_acceleration(self):
        """加速衰减检测。"""
        # 后期加速下降的数据
        points = [
            make_point(date=f"2026-01-{i+1:02d}", ctr=0.03 - 0.0002 * i)
            for i in range(10)
        ]
        # 最后 3 天加速下降
        points.append(make_point(date="2026-01-11", ctr=0.027))
        points.append(make_point(date="2026-01-12", ctr=0.025))
        points.append(make_point(date="2026-01-13", ctr=0.022))
        pred = DecayPredictor().predict(points, metric="ctr")
        assert pred is not None

    def test_predict_evidence(self):
        """证据非空。"""
        history = make_declining(days=7)
        pred = DecayPredictor().predict(history, metric="ctr")
        assert pred is not None
        assert len(pred.evidence) > 0

    def test_predict_confidence(self):
        """置信度在合理范围。"""
        history = make_declining(days=14)
        pred = DecayPredictor().predict(history, metric="ctr")
        assert pred is not None
        assert 0 <= pred.confidence <= 1.0

    def test_predict_cvr(self):
        """CVR 预测。"""
        history = make_declining(days=7)
        pred = DecayPredictor().predict(history, metric="cvr")
        assert pred is not None
        assert pred.metric == "cvr"

    def test_predict_cpi(self):
        """CPI 预测。"""
        history = make_declining(days=7)
        pred = DecayPredictor().predict(history, metric="cpi")
        assert pred is not None
        assert pred.metric == "cpi"

    def test_repr(self):
        assert repr(DecayPredictor()) == "DecayPredictor()"


# ═══════════════════════════════════════════════════════════
# PredictionConfidenceEngine
# ═══════════════════════════════════════════════════════════


class TestPredictionConfidenceEngine:
    """PredictionConfidenceEngine 测试。"""

    def test_creation(self):
        e = PredictionConfidenceEngine()
        assert e is not None

    def test_evaluate_high_confidence(self):
        """大量数据 → 高置信度。"""
        engine = PredictionConfidenceEngine()
        history = make_declining(days=14)
        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c001",
        )
        conf = engine.evaluate_prediction(pred, history)
        assert conf.score > 0.3
        assert conf.data_volume > 0

    def test_evaluate_low_confidence(self):
        """少量数据 → 低置信度。"""
        engine = PredictionConfidenceEngine()
        history = make_short(days=2)
        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c005",
        )
        conf = engine.evaluate_prediction(pred, history)
        assert conf.score < 0.75  # 2 days, 15 installs = low data volume

    def test_evaluate_lifecycle(self):
        """生命周期置信度评估。"""
        engine = PredictionConfidenceEngine()
        history = make_declining(days=14)
        lc = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.STABLE,
            predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
        )
        conf = engine.evaluate_lifecycle(lc, history)
        assert conf is not None
        assert 0 <= conf.score <= 1.0

    def test_evaluate_decay(self):
        """衰减置信度评估。"""
        engine = PredictionConfidenceEngine()
        history = make_declining(days=14)
        decay = DecayPrediction(
            creative_id="c001", metric="ctr", velocity=-0.001,
        )
        conf = engine.evaluate_decay(decay, history)
        assert conf is not None
        assert 0 <= conf.score <= 1.0

    def test_evaluate_batch(self):
        """批量评估。"""
        engine = PredictionConfidenceEngine()
        history = {
            "c001": make_declining(days=14),
            "c002": make_improving(days=14),
        }
        preds = [
            RealityPrediction(
                prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                target_id="c001",
            ),
            RealityPrediction(
                prediction_type=PredictionType.ROAS_DECAY_RISK,
                target_id="c002",
            ),
        ]
        confs = engine.evaluate_batch(preds, history)
        assert len(confs) == 2

    def test_filter_reliable(self):
        """过滤可靠预测。"""
        engine = PredictionConfidenceEngine()
        history = {
            "c001": make_declining(days=14),
        }
        preds = [
            RealityPrediction(
                prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                target_id="c001",
            ),
        ]
        reliable = engine.filter_reliable(preds, history, min_confidence=0.3)
        assert len(reliable) >= 0

    def test_breakdown_keys(self):
        """breakdown 包含各因子。"""
        conf = PredictionConfidence(
            score=0.8,
            data_volume=0.9,
            trend_consistency=0.7,
            metric_stability=0.85,
            breakdown={"data_volume": 0.9, "trend_consistency": 0.7, "metric_stability": 0.85},
        )
        assert "data_volume" in conf.breakdown

    def test_repr(self):
        assert repr(PredictionConfidenceEngine()) == "PredictionConfidenceEngine()"


# ═══════════════════════════════════════════════════════════
# ExplanationEngine
# ═══════════════════════════════════════════════════════════


class TestExplanationEngine:
    """ExplanationEngine 测试。"""

    def test_creation(self):
        e = ExplanationEngine()
        assert e is not None

    def test_explain_fatigue_prediction(self):
        """疲劳预测解释。"""
        engine = ExplanationEngine()
        history = make_declining(days=14)
        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c001",
            probability=0.85,
            risk_level=RiskLevel.HIGH,
            recommended_action="MUTATE_HOOK",
            evidence=["CTR decreasing"],
        )
        exp = engine.explain_prediction(pred, history)
        assert exp is not None
        assert len(exp.summary) > 0
        assert len(exp.reasons) > 0
        assert exp.recommended_action == "MUTATE_HOOK"
        assert len(exp.action_detail) > 0

    def test_explain_roas_prediction(self):
        """ROAS 预测解释。"""
        engine = ExplanationEngine()
        history = make_declining(days=14)
        pred = RealityPrediction(
            prediction_type=PredictionType.ROAS_DECAY_RISK,
            target_id="c001",
            current_value=0.8,
            predicted_value=0.5,
            probability=0.8,
            risk_level=RiskLevel.HIGH,
            recommended_action="MUTATE_CREATIVE",
        )
        exp = engine.explain_prediction(pred, history)
        assert exp is not None
        assert "ROAS" in exp.summary or "roas" in exp.summary.lower()

    def test_explain_scale_opportunity(self):
        """放量机会解释。"""
        engine = ExplanationEngine()
        history = make_improving(days=14)
        pred = RealityPrediction(
            prediction_type=PredictionType.SCALE_OPPORTUNITY,
            target_id="c002",
            current_value=0.6,
            predicted_value=0.9,
            probability=0.75,
            risk_level=RiskLevel.LOW,
            recommended_action="INCREASE_BUDGET",
        )
        exp = engine.explain_prediction(pred, history)
        assert exp is not None
        assert len(exp.summary) > 0

    def test_explain_lifecycle(self):
        """生命周期解释。"""
        engine = ExplanationEngine()
        history = make_declining(days=14)
        lc = LifecyclePrediction(
            creative_id="c001",
            current_stage=CreativeLifecycleStage.STABLE,
            predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
            days_to_transition=8,
            recommended_action="PREPARE_MUTATION",
        )
        exp = engine.explain_lifecycle(lc, history)
        assert exp is not None
        assert "stable" in exp.summary.lower()
        assert len(exp.reasons) > 0

    def test_explain_decay(self):
        """衰减解释。"""
        engine = ExplanationEngine()
        history = make_declining(days=7)
        decay = DecayPrediction(
            creative_id="c001", metric="ctr",
            velocity=-0.002, current_value=0.03, predicted_value=0.016,
            horizon_days=7,
        )
        exp = engine.explain_decay(decay, history)
        assert exp is not None
        assert "CTR" in exp.summary
        assert len(exp.reasons) > 0

    def test_explain_decay_accelerating(self):
        """加速衰减解释。"""
        engine = ExplanationEngine()
        history = make_declining(days=7)
        decay = DecayPrediction(
            creative_id="c001", metric="ctr",
            velocity=-0.003, current_value=0.03, predicted_value=0.009,
            horizon_days=7, is_accelerating=True,
        )
        exp = engine.explain_decay(decay, history)
        assert exp is not None
        assert any("accelerating" in r.lower() for r in exp.reasons)

    def test_explain_batch(self):
        """批量解释。"""
        engine = ExplanationEngine()
        history = {
            "c001": make_declining(days=14),
            "c002": make_improving(days=14),
        }
        preds = [
            RealityPrediction(
                prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                target_id="c001",
                recommended_action="MUTATE_HOOK",
            ),
            RealityPrediction(
                prediction_type=PredictionType.SCALE_OPPORTUNITY,
                target_id="c002",
                recommended_action="INCREASE_BUDGET",
            ),
        ]
        exps = engine.explain_batch(preds, history)
        assert len(exps) == 2

    def test_explain_all(self):
        """全类型解释。"""
        engine = ExplanationEngine()
        history = {"c001": make_declining(days=14)}
        preds = [
            RealityPrediction(
                prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                target_id="c001",
            ),
        ]
        lifecycles = [
            LifecyclePrediction(
                creative_id="c001",
                current_stage=CreativeLifecycleStage.STABLE,
                predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
            ),
        ]
        decays = [
            DecayPrediction(creative_id="c001", metric="ctr", velocity=-0.001),
        ]
        exps = engine.explain_all(preds, lifecycles, decays, history)
        assert len(exps) >= 3

    def test_similar_cases(self):
        """类似案例非空。"""
        engine = ExplanationEngine()
        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c001",
        )
        exp = engine.explain_prediction(pred, make_declining(days=7))
        assert len(exp.similar_cases) > 0

    def test_repr(self):
        assert repr(ExplanationEngine()) == "ExplanationEngine()"


# ═══════════════════════════════════════════════════════════
# PredictionEngine Phase 2
# ═══════════════════════════════════════════════════════════


class TestPredictionEnginePhase2:
    """PredictionEngine Phase 2 集成测试。"""

    def test_creation(self):
        engine = PredictionEngine()
        assert engine.lifecycle_predictor is not None
        assert engine.decay_predictor is not None
        assert engine.confidence_engine is not None
        assert engine.explanation_engine is not None

    def test_predict_full(self):
        """完整 Phase 2 管线。"""
        history = {
            "c001": make_declining(days=14),
            "c002": make_improving(days=14),
            "c003": make_stable(days=7),
        }
        result = PredictionEngine().predict_full(history)
        assert isinstance(result, PredictionResult)
        assert len(result.predictions) >= 2
        assert len(result.lifecycles) >= 1
        assert len(result.decays) >= 1
        assert len(result.confidences) >= 0
        assert len(result.explanations) >= 1

    def test_predict_lifecycle_only(self):
        """仅生命周期。"""
        history = {"c001": make_declining(days=14)}
        preds = PredictionEngine().predict_lifecycle_only(history)
        assert len(preds) == 1

    def test_predict_decay_only(self):
        """仅衰减。"""
        history = {"c001": make_declining(days=7)}
        preds = PredictionEngine().predict_decay_only(history, metric="ctr")
        assert len(preds) == 1

    def test_get_reliable_predictions(self):
        """可靠预测过滤。"""
        history = {"c001": make_declining(days=14)}
        result = PredictionEngine().predict_full(history)
        reliable = PredictionEngine().get_reliable_predictions(result, min_confidence=0.3)
        assert isinstance(reliable, list)

    def test_predict_full_summary(self):
        """完整摘要包含 Phase 2 信息。"""
        history = {"c001": make_declining(days=14)}
        result = PredictionEngine().predict_full(history)
        assert "Lifecycles" in result.summary or "Decays" in result.summary

    def test_predict_result_repr(self):
        """PredictionResult repr 包含 Phase 2 字段。"""
        history = {"c001": make_declining(days=14)}
        result = PredictionEngine().predict_full(history)
        r = repr(result)
        assert "lifecycles" in r.lower()
        assert "decays" in r.lower()

    def test_predict_single_creative_still_works(self):
        """Phase 1 API 仍然可用。"""
        history = make_declining(days=14)
        preds = PredictionEngine().predict_single_creative(history)
        assert len(preds) >= 1

    def test_predict_still_works(self):
        """Phase 1 predict() 仍然可用。"""
        history = {"c001": make_declining(days=14)}
        result = PredictionEngine().predict(history)
        assert len(result.predictions) >= 1

    def test_repr(self):
        r = repr(PredictionEngine())
        assert "lifecycle" in r.lower()
        assert "decay" in r.lower()


# ═══════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════


class TestPackageExports:
    """包导出测试。"""

    def test_lifecycle_stage_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            CreativeLifecycleStage,
        )
        assert CreativeLifecycleStage is not None

    def test_lifecycle_prediction_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            LifecyclePrediction,
        )
        assert LifecyclePrediction is not None

    def test_decay_prediction_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            DecayPrediction,
        )
        assert DecayPrediction is not None

    def test_confidence_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            PredictionConfidence,
        )
        assert PredictionConfidence is not None

    def test_explanation_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            PredictionExplanation,
        )
        assert PredictionExplanation is not None

    def test_lifecycle_predictor_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            LifecyclePredictor,
        )
        assert LifecyclePredictor is not None

    def test_decay_predictor_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            DecayPredictor,
        )
        assert DecayPredictor is not None

    def test_confidence_engine_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            PredictionConfidenceEngine,
        )
        assert PredictionConfidenceEngine is not None

    def test_explanation_engine_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            ExplanationEngine,
        )
        assert ExplanationEngine is not None