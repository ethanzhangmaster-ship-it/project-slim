"""E12.3 — Reality Prediction Layer 测试。

覆盖:
  - Models: PredictionType, RiskLevel, RealityPrediction, RealityHistoryPoint
  - FatiguePredictor: CTR下降, ROAS下降, Frequency增长, 正常, 无数据
  - ROASPredictor: 上升趋势, 下降趋势, 平稳, 数据不足
  - PredictionEngine: 批量预测, 风险排序, 单创意预测
"""

import pytest

from market_ops.creative_vision_runtime.reality.prediction import (
    FatiguePredictor,
    PredictionEngine,
    PredictionResult,
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
    ROASPredictor,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_history_point(
    date: str = "2026-01-01",
    creative_id: str = "creative_001",
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
        date=date,
        creative_id=creative_id,
        ctr=ctr,
        cvr=cvr,
        roas=roas,
        spend=spend,
        revenue=revenue,
        frequency=frequency,
        impressions=impressions,
        installs=installs,
    )


def make_declining_history(
    creative_id: str = "creative_001",
    days: int = 14,
    start_ctr: float = 0.035,
    end_ctr: float = 0.018,
    start_roas: float = 1.2,
    end_roas: float = 0.6,
    start_freq: float = 1.5,
    end_freq: float = 5.1,
) -> list[RealityHistoryPoint]:
    """生成持续下降的历史数据。"""
    points = []
    for i in range(days):
        t = i / (days - 1) if days > 1 else 0
        points.append(
            make_history_point(
                date=f"2026-01-{i+1:02d}",
                creative_id=creative_id,
                ctr=start_ctr + (end_ctr - start_ctr) * t,
                roas=start_roas + (end_roas - start_roas) * t,
                frequency=start_freq + (end_freq - start_freq) * t,
            )
        )
    return points


def make_improving_history(
    creative_id: str = "creative_002",
    days: int = 14,
) -> list[RealityHistoryPoint]:
    """生成持续改善的历史数据。"""
    points = []
    for i in range(days):
        t = i / (days - 1) if days > 1 else 0
        points.append(
            make_history_point(
                date=f"2026-01-{i+1:02d}",
                creative_id=creative_id,
                ctr=0.02 + 0.015 * t,
                roas=0.6 + 0.6 * t,
                frequency=1.0 + 2.0 * t,
            )
        )
    return points


def make_stable_history(
    creative_id: str = "creative_003",
    days: int = 14,
) -> list[RealityHistoryPoint]:
    """生成稳定的历史数据。"""
    points = []
    for i in range(days):
        points.append(
            make_history_point(
                date=f"2026-01-{i+1:02d}",
                creative_id=creative_id,
                ctr=0.03,
                roas=1.0,
                frequency=2.0,
            )
        )
    return points


# ═══════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════


class TestPredictionType:
    """PredictionType 枚举测试。"""

    def test_all_types(self):
        types = list(PredictionType)
        assert len(types) == 4

    def test_fatigue_risk_value(self):
        assert PredictionType.CREATIVE_FATIGUE_RISK.value == "creative_fatigue_risk"

    def test_roas_decay_value(self):
        assert PredictionType.ROAS_DECAY_RISK.value == "roas_decay_risk"

    def test_scale_opportunity_value(self):
        assert PredictionType.SCALE_OPPORTUNITY.value == "scale_opportunity"

    def test_budget_burn_value(self):
        assert PredictionType.BUDGET_BURN_RISK.value == "budget_burn_risk"


class TestRiskLevel:
    """RiskLevel 枚举测试。"""

    def test_all_levels(self):
        levels = list(RiskLevel)
        assert len(levels) == 4

    def test_ordering(self):
        assert RiskLevel.CRITICAL.value == "critical"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.LOW.value == "low"


class TestRealityHistoryPoint:
    """RealityHistoryPoint 测试。"""

    def test_creation(self):
        point = make_history_point()
        assert point.date == "2026-01-01"
        assert point.creative_id == "creative_001"
        assert point.ctr == 0.03

    def test_to_dict(self):
        point = make_history_point()
        d = point.to_dict()
        assert d["date"] == "2026-01-01"
        assert d["ctr"] == 0.03

    def test_repr(self):
        point = make_history_point()
        r = repr(point)
        assert "RealityHistoryPoint" in r
        assert "2026-01-01" in r


class TestRealityPrediction:
    """RealityPrediction 测试。"""

    def test_creation_defaults(self):
        p = RealityPrediction()
        assert p.prediction_id.startswith("rp_")
        assert p.horizon_days == 7
        assert p.risk_level == RiskLevel.LOW

    def test_is_actionable_critical(self):
        p = RealityPrediction(
            risk_level=RiskLevel.CRITICAL,
            probability=0.8,
        )
        assert p.is_actionable is True

    def test_is_actionable_high_confidence(self):
        p = RealityPrediction(
            risk_level=RiskLevel.HIGH,
            probability=0.75,
        )
        assert p.is_actionable is True

    def test_is_not_actionable_low_prob(self):
        p = RealityPrediction(
            risk_level=RiskLevel.HIGH,
            probability=0.6,
        )
        assert p.is_actionable is False

    def test_is_not_actionable_medium(self):
        p = RealityPrediction(
            risk_level=RiskLevel.MEDIUM,
            probability=0.9,
        )
        assert p.is_actionable is False

    def test_delta(self):
        p = RealityPrediction(current_value=0.5, predicted_value=0.8)
        assert p.delta == pytest.approx(0.3)

    def test_delta_pct(self):
        p = RealityPrediction(current_value=0.5, predicted_value=0.8)
        assert p.delta_pct == pytest.approx(0.6)

    def test_delta_pct_zero_current(self):
        p = RealityPrediction(current_value=0.0, predicted_value=0.8)
        assert p.delta_pct == 0.0

    def test_to_dict(self):
        p = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c001",
            current_value=0.5,
            predicted_value=0.8,
            probability=0.85,
            risk_level=RiskLevel.HIGH,
        )
        d = p.to_dict()
        assert d["prediction_type"] == "creative_fatigue_risk"
        assert d["risk_level"] == "high"
        assert d["is_actionable"] is True

    def test_to_evolution_opportunity(self):
        p = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c001",
            probability=0.85,
            evidence=["CTR dropping"],
            recommended_action="MUTATE_HOOK",
        )
        opp = p.to_evolution_opportunity()
        assert opp["type"] == "creative_fatigue_risk"
        assert opp["score"] == 0.85
        assert opp["metadata"]["target_id"] == "c001"

    def test_repr(self):
        p = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c001",
            current_value=0.5,
            predicted_value=0.8,
            probability=0.85,
        )
        r = repr(p)
        assert "creative_fatigue_risk" in r
        assert "c001" in r


# ═══════════════════════════════════════════════════════════
# FatiguePredictor
# ═══════════════════════════════════════════════════════════


class TestFatiguePredictor:
    """FatiguePredictor 测试。"""

    def test_creation(self):
        p = FatiguePredictor()
        assert p is not None

    def test_predict_ctr_decline(self):
        """CTR 下降 → 疲劳预测。"""
        history = [
            make_history_point(date="2026-01-01", ctr=0.035, roas=1.0, frequency=1.0),
            make_history_point(date="2026-01-07", ctr=0.018, roas=1.0, frequency=1.0),
        ]
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK
        assert pred.probability > 0.3  # CTR dropped ~48%

    def test_predict_roas_decline(self):
        """ROAS 下降 → 疲劳预测。"""
        history = [
            make_history_point(date="2026-01-01", ctr=0.03, roas=1.2, frequency=1.0),
            make_history_point(date="2026-01-07", ctr=0.03, roas=0.6, frequency=1.0),
        ]
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK
        assert pred.probability > 0.3

    def test_predict_frequency_growth(self):
        """频次增长 → 压力升高。"""
        history = [
            make_history_point(date="2026-01-01", ctr=0.03, roas=1.0, frequency=1.5),
            make_history_point(date="2026-01-07", ctr=0.03, roas=1.0, frequency=5.1),
        ]
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.metadata["frequency_pressure"] > 0.3

    def test_predict_combined_fatigue(self):
        """CTR + ROAS + Frequency 都恶化 → 高疲劳。"""
        history = make_declining_history(days=14)
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK
        assert pred.probability > 0.5

    def test_predict_healthy_creative(self):
        """正常创意 → 低疲劳。"""
        history = [
            make_history_point(date="2026-01-01", ctr=0.03, roas=1.0, frequency=1.0),
            make_history_point(date="2026-01-07", ctr=0.032, roas=1.1, frequency=1.2),
        ]
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.risk_level == RiskLevel.LOW

    def test_predict_insufficient_data(self):
        """数据不足 → None。"""
        history = [make_history_point()]
        pred = FatiguePredictor().predict(history)
        assert pred is None

    def test_predict_empty_data(self):
        """空数据 → None。"""
        pred = FatiguePredictor().predict([])
        assert pred is None

    def test_predict_batch(self):
        """批量预测。"""
        history = {
            "c001": make_declining_history("c001", days=7),
            "c002": make_stable_history("c002", days=7),
        }
        preds = FatiguePredictor().predict_batch(history)
        assert len(preds) == 2
        # c001 应该排在 c002 前面
        assert preds[0].target_id == "c001"
        assert preds[0].probability > preds[1].probability

    def test_predict_recommend_action_mutate_hook(self):
        """CTR 下降为主 → MUTATE_HOOK。"""
        history = [
            make_history_point(date="2026-01-01", ctr=0.035, roas=1.0, frequency=1.0),
            make_history_point(date="2026-01-07", ctr=0.015, roas=0.9, frequency=1.0),
        ]
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert "MUTATE" in pred.recommended_action

    def test_predict_evidence(self):
        """证据列表非空。"""
        history = make_declining_history(days=14)
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert len(pred.evidence) > 0

    def test_predict_metadata_size(self):
        """metadata 包含关键字段。"""
        history = make_declining_history(days=7)
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert "ctr_decay" in pred.metadata
        assert "roas_decay" in pred.metadata
        assert "frequency_pressure" in pred.metadata
        assert "velocity" in pred.metadata
        assert "data_points" in pred.metadata

    def test_predict_risk_level_critical(self):
        """严重疲劳 → CRITICAL。"""
        history = [
            make_history_point(date="2026-01-01", ctr=0.04, roas=1.5, frequency=1.0),
            make_history_point(date="2026-01-14", ctr=0.01, roas=0.3, frequency=6.0),
        ]
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)

    def test_predict_risk_level(self):
        """p.predict 返回合理的 risk_level。"""
        history = make_declining_history(days=14)
        pred = FatiguePredictor().predict(history)
        assert pred is not None
        assert pred.risk_level in RiskLevel

    def test_repr(self):
        p = FatiguePredictor()
        assert repr(p) == "FatiguePredictor()"


# ═══════════════════════════════════════════════════════════
# ROASPredictor
# ═══════════════════════════════════════════════════════════


class TestROASPredictor:
    """ROASPredictor 测试。"""

    def test_creation(self):
        p = ROASPredictor()
        assert p is not None

    def test_predict_declining_trend(self):
        """ROAS 下降趋势 → ROAS_DECAY_RISK。"""
        history = [
            make_history_point(date="2026-01-01", roas=1.0),
            make_history_point(date="2026-01-07", roas=0.8),
            make_history_point(date="2026-01-14", roas=0.6),
        ]
        pred = ROASPredictor().predict(history, horizon_days=7)
        assert pred is not None
        assert pred.prediction_type == PredictionType.ROAS_DECAY_RISK
        assert pred.predicted_value < pred.current_value

    def test_predict_improving_trend(self):
        """ROAS 上升趋势 → SCALE_OPPORTUNITY。"""
        history = make_improving_history(days=10)
        pred = ROASPredictor().predict(history, horizon_days=7)
        assert pred is not None
        assert pred.prediction_type == PredictionType.SCALE_OPPORTUNITY
        assert pred.predicted_value > pred.current_value

    def test_predict_stable(self):
        """ROAS 稳定 → 低风险。"""
        history = make_stable_history(days=7)
        pred = ROASPredictor().predict(history, horizon_days=7)
        assert pred is not None
        assert pred.risk_level == RiskLevel.LOW

    def test_predict_insufficient_data(self):
        """数据不足 → None。"""
        history = [make_history_point()]
        pred = ROASPredictor().predict(history)
        assert pred is None

    def test_predict_empty_data(self):
        """空数据 → None。"""
        pred = ROASPredictor().predict([])
        assert pred is None

    def test_predict_extrapolation(self):
        """线性外推正确。"""
        # ROAS 每天下降 0.05
        history = [
            make_history_point(date=f"2026-01-{i+1:02d}", roas=1.0 - 0.05 * i)
            for i in range(10)
        ]
        pred = ROASPredictor().predict(history, horizon_days=7)
        assert pred is not None
        # 预测值应该接近 1.0 - 0.05 * (9 + 7) = 0.2
        assert 0.15 <= pred.predicted_value <= 0.3

    def test_predict_metadata(self):
        """metadata 包含回归参数。"""
        history = [
            make_history_point(date="2026-01-01", roas=1.0),
            make_history_point(date="2026-01-14", roas=0.5),
        ]
        pred = ROASPredictor().predict(history)
        assert pred is not None
        assert "slope" in pred.metadata
        assert "r_squared" in pred.metadata
        assert "data_points" in pred.metadata

    def test_predict_r_squared_perfect(self):
        """完美线性 → R²=1.0。"""
        history = [
            make_history_point(date="2026-01-01", roas=1.0),
            make_history_point(date="2026-01-02", roas=0.8),
            make_history_point(date="2026-01-03", roas=0.6),
        ]
        pred = ROASPredictor().predict(history)
        assert pred is not None
        assert pred.metadata["r_squared"] == 1.0

    def test_predict_batch(self):
        """批量预测。"""
        history = {
            "c001": make_declining_history("c001", days=7),
            "c002": make_improving_history("c002", days=7),
        }
        preds = ROASPredictor().predict_batch(history)
        assert len(preds) == 2

    def test_predict_recommend_action_decline(self):
        """严重下降 → PAUSE_AND_MUTATE。"""
        history = [
            make_history_point(date="2026-01-01", roas=1.5),
            make_history_point(date="2026-01-07", roas=0.3),
        ]
        pred = ROASPredictor().predict(history)
        assert pred is not None
        assert "MUTATE" in pred.recommended_action or "PAUSE" in pred.recommended_action

    def test_predict_recommend_action_improve(self):
        """改善 → INCREASE_BUDGET。"""
        history = make_improving_history(days=7)
        pred = ROASPredictor().predict(history)
        assert pred is not None
        assert pred.recommended_action == "INCREASE_BUDGET"

    def test_predict_evidence(self):
        """证据列表非空。"""
        history = make_declining_history(days=7)
        pred = ROASPredictor().predict(history)
        assert pred is not None
        assert len(pred.evidence) > 0

    def test_predict_risk_level_critical(self):
        """快速下降 → CRITICAL。"""
        history = [
            make_history_point(date="2026-01-01", roas=2.0),
            make_history_point(date="2026-01-07", roas=0.5),
        ]
        pred = ROASPredictor().predict(history)
        assert pred is not None
        assert pred.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)

    def test_repr(self):
        p = ROASPredictor()
        assert repr(p) == "ROASPredictor()"


# ═══════════════════════════════════════════════════════════
# PredictionEngine
# ═══════════════════════════════════════════════════════════


class TestPredictionEngine:
    """PredictionEngine 测试。"""

    def test_creation(self):
        engine = PredictionEngine()
        assert engine is not None
        assert engine.fatigue_predictor is not None
        assert engine.roas_predictor is not None

    def test_predict(self):
        """完整预测流程。"""
        history = {
            "c001": make_declining_history("c001", days=14),
            "c002": make_improving_history("c002", days=10),
        }
        result = PredictionEngine().predict(history)
        assert isinstance(result, PredictionResult)
        assert len(result.predictions) >= 2  # fatigue + ROAS for each

    def test_predict_ranking(self):
        """预测结果按风险排序。"""
        history = {
            "high_risk": make_declining_history("high_risk", days=14),
            "low_risk": make_stable_history("low_risk", days=7),
        }
        result = PredictionEngine().predict(history)
        if len(result.predictions) >= 2:
            # 第一个应该是风险最高的
            first_risk = result.predictions[0].risk_level
            assert first_risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)

    def test_predict_actionable(self):
        """actionable 过滤正确。"""
        history = {
            "c001": make_declining_history("c001", days=14),
        }
        result = PredictionEngine().predict(history)
        for p in result.actionable:
            assert p.is_actionable is True
            assert p.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            assert p.probability >= 0.7

    def test_predict_single_creative(self):
        """单创意预测。"""
        history = make_declining_history(days=14)
        preds = PredictionEngine().predict_single_creative(history)
        assert len(preds) >= 1

    def test_get_critical_risks(self):
        """获取 CRITICAL 风险。"""
        history = {
            "c001": make_declining_history("c001", days=14),
        }
        result = PredictionEngine().predict(history)
        engine = PredictionEngine()
        critical = engine.get_critical_risks(result.predictions)
        for p in critical:
            assert p.risk_level == RiskLevel.CRITICAL

    def test_get_by_type(self):
        """按类型筛选。"""
        history = {
            "c001": make_declining_history("c001", days=14),
        }
        result = PredictionEngine().predict(history)
        engine = PredictionEngine()
        fatigue = engine.get_by_type(
            result.predictions, PredictionType.CREATIVE_FATIGUE_RISK
        )
        for p in fatigue:
            assert p.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK

    def test_summary(self):
        """摘要非空。"""
        history = {
            "c001": make_declining_history("c001", days=14),
        }
        result = PredictionEngine().predict(history)
        assert len(result.summary) > 0

    def test_top_risks(self):
        """top_risks 限制数量。"""
        history = {
            f"c{i:03d}": make_declining_history(f"c{i:03d}", days=7)
            for i in range(5)
        }
        result = PredictionEngine().predict(history)
        assert len(result.top_risks) <= 10

    def test_repr(self):
        engine = PredictionEngine()
        r = repr(engine)
        assert "PredictionEngine" in r


# ═══════════════════════════════════════════════════════════
# PredictionResult
# ═══════════════════════════════════════════════════════════


class TestPredictionResult:
    """PredictionResult 测试。"""

    def test_creation(self):
        result = PredictionResult()
        assert result.predictions == []
        assert result.actionable == []
        assert result.summary == ""

    def test_repr(self):
        result = PredictionResult(
            predictions=[
                RealityPrediction(
                    prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                    risk_level=RiskLevel.CRITICAL,
                ),
            ],
            actionable=[],
            summary="test",
        )
        r = repr(result)
        assert "PredictionResult" in r
        assert "total=1" in r


# ═══════════════════════════════════════════════════════════
# Integration
# ═══════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试。"""

    def test_full_pipeline(self):
        """完整 E12.3 流程。"""
        history = {
            "fatiguing": make_declining_history("fatiguing", days=14),
            "improving": make_improving_history("improving", days=10),
            "stable": make_stable_history("stable", days=7),
        }

        engine = PredictionEngine()
        result = engine.predict(history, horizon_days=7)

        # 至少 3 个预测（每个 creative 至少 fatigue）
        assert len(result.predictions) >= 3
        assert len(result.summary) > 0

        # Fatigue predictions
        fatigue = engine.get_by_type(
            result.predictions, PredictionType.CREATIVE_FATIGUE_RISK
        )
        assert len(fatigue) >= 1

    def test_predictions_have_ids(self):
        """所有预测都有唯一 ID。"""
        history = make_declining_history(days=7)
        engine = PredictionEngine()
        preds = engine.predict_single_creative(history)
        ids = {p.prediction_id for p in preds}
        assert len(ids) == len(preds)

    def test_actionable_items_are_high_priority(self):
        """actionable 预测都是高优先级。"""
        history = {
            "c001": make_declining_history("c001", days=14),
        }
        result = PredictionEngine().predict(history)
        for p in result.actionable:
            assert p.probability >= 0.7
            assert p.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)


# ═══════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════


class TestPackageExports:
    """包导出测试。"""

    def test_prediction_type_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            PredictionType,
        )
        assert PredictionType is not None

    def test_risk_level_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import RiskLevel
        assert RiskLevel is not None

    def test_reality_history_point_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            RealityHistoryPoint,
        )
        assert RealityHistoryPoint is not None

    def test_reality_prediction_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            RealityPrediction,
        )
        assert RealityPrediction is not None

    def test_fatigue_predictor_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            FatiguePredictor,
        )
        assert FatiguePredictor is not None

    def test_roas_predictor_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            ROASPredictor,
        )
        assert ROASPredictor is not None

    def test_prediction_engine_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            PredictionEngine,
        )
        assert PredictionEngine is not None

    def test_prediction_result_import(self):
        from market_ops.creative_vision_runtime.reality.prediction import (
            PredictionResult,
        )
        assert PredictionResult is not None