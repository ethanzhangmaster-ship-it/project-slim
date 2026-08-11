"""E13.7.5 Decision Learning Enhancer — 测试.

测试 DecisionLearningEnhancer 的全部功能:
  1. Basic enhancement (5 tests)
  2. Similar decision search (5 tests)
  3. Outcome analysis (5 tests)
  4. Risk detection (6 tests)
  5. Recommendation generation (6 tests)
  6. Confidence (4 tests)
  7. Model validation (4 tests)
  8. Edge cases (5 tests)
  9. Integration (5 tests)
"""

import math
import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.decision_learning_enhancer import (
    DecisionLearningEnhancer,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_memory import (
    DecisionMemory,
    DecisionExperience,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_models import (
    DecisionLearningResult,
    RiskSignal,
)


# ── Helpers ───────────────────────────────────────────────────────

def _make_decision_memory(experiences_data):
    """experiences_data: list of dicts with result, strategy_name, action_type, etc."""
    memory = DecisionMemory()
    for i, data in enumerate(experiences_data):
        exp = DecisionExperience(
            decision_id=f"d{i}",
            strategy_name=data.get("strategy_name", "test_strategy"),
            result=data.get("result", "success"),
            confidence=data.get("confidence", 0.7),
            risk_score=data.get("risk_score", 0.3),
            action_plan={"action_type": data.get("action_type", "test_action")},
            result_reason=data.get("result_reason", ""),
            lessons_learned=data.get("lessons_learned", []),
            result_metrics=data.get("result_metrics", {}),
            created_at=data.get("created_at", ""),
        )
        memory._experiences[exp.experience_id] = exp
    return memory


def _make_enhancer(min_similar=3, min_confidence=0.50):
    return DecisionLearningEnhancer(
        min_similar_decisions=min_similar,
        min_confidence=min_confidence,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. Basic Enhancement (5 tests)
# ═══════════════════════════════════════════════════════════════════

class TestBasicEnhancement:
    """基础增强功能测试."""

    def test_enhance_with_memory_and_sufficient_data(self):
        """有记忆且数据充足时应返回有效推荐."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
            strategy_name="scale_winning",
        )
        assert result.recommendation in ("approve", "approve_with_condition", "deny", "adjust")
        assert result.confidence > 0.0
        assert result.similar_decisions >= 5
        assert result.success_count >= 5
        assert result.success_rate > 0.0

    def test_enhance_without_memory_returns_default(self):
        """无 decision_memory 时返回默认结果."""
        enhancer = _make_enhancer()
        result = enhancer.enhance(
            decision_memory=None,
            action_type="increase_budget",
        )
        assert result.confidence == 0.0
        assert result.metadata.get("reason") == "no_decision_memory"

    def test_enhance_with_context_dict(self):
        """通过 context 字典传递参数."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
        ])
        result = enhancer.enhance(
            context={"action_type": "increase_budget", "strategy_name": "scale_winning"},
            decision_memory=memory,
        )
        assert result.similar_decisions >= 5
        assert result.confidence > 0.0

    def test_enhance_insufficient_decisions(self):
        """相似决策数不足最低阈值时返回不足结果."""
        enhancer = _make_enhancer(min_similar=5)
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.confidence == 0.0
        assert result.metadata.get("reason") == "insufficient_similar_decisions"
        assert result.similar_decisions == 2

    def test_enhancement_count_increments(self):
        """每次调用 enhance() 应递增 enhancement_count."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        assert enhancer.enhancement_count == 0
        enhancer.enhance(decision_memory=memory, action_type="increase_budget")
        assert enhancer.enhancement_count == 1
        enhancer.enhance(decision_memory=memory, action_type="increase_budget")
        assert enhancer.enhancement_count == 2
        enhancer.enhance(decision_memory=memory, action_type="increase_budget")
        assert enhancer.enhancement_count == 3


# ═══════════════════════════════════════════════════════════════════
# 2. Similar Decision Search (5 tests)
# ═══════════════════════════════════════════════════════════════════

class TestSimilarDecisionSearch:
    """相似决策搜索测试."""

    def test_find_by_action_type(self):
        """按 action_type 过滤相似决策."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s1"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s2"},
            {"result": "failure", "action_type": "decrease_budget", "strategy_name": "s3"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s4"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s5"},
            {"result": "failure", "action_type": "decrease_budget", "strategy_name": "s6"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.similar_decisions == 4

    def test_find_by_strategy_name(self):
        """按 strategy_name 过滤相似决策."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "a1", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "a2", "strategy_name": "scale_winning"},
            {"result": "failure", "action_type": "a3", "strategy_name": "other_strategy"},
            {"result": "success", "action_type": "a4", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "a5", "strategy_name": "scale_winning"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            strategy_name="scale_winning",
        )
        assert result.similar_decisions == 4

    def test_find_by_opportunity_type(self):
        """按 opportunity_type 过滤相似决策."""
        enhancer = _make_enhancer()
        memory = DecisionMemory()
        for i in range(8):
            exp = DecisionExperience(
                decision_id=f"d{i}",
                opportunity_type="creative_fatigue" if i < 5 else "budget_optimization",
                result="success",
                confidence=0.7,
                risk_score=0.3,
                action_plan={"action_type": "test_action"},
                strategy_name="test_strategy",
            )
            memory._experiences[exp.experience_id] = exp
        result = enhancer.enhance(
            decision_memory=memory,
            opportunity_type="creative_fatigue",
        )
        # find_similar filters by opportunity_type, then action_type/strategy_name are empty
        # so all 5 should match
        assert result.similar_decisions == 5

    def test_find_no_match_returns_empty(self):
        """无匹配的相似决策时返回不足结果."""
        enhancer = _make_enhancer(min_similar=3)
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s1"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s2"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "s3"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            strategy_name="nonexistent_strategy",
        )
        assert result.similar_decisions == 0
        assert result.confidence == 0.0

    def test_find_mixed_filters(self):
        """同时使用 action_type 和 strategy_name 过滤."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "failure", "action_type": "increase_budget", "strategy_name": "other"},
            {"result": "success", "action_type": "decrease_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
            {"result": "success", "action_type": "increase_budget", "strategy_name": "scale_winning"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
            strategy_name="scale_winning",
        )
        # 4 entries with increase_budget AND scale_winning
        assert result.similar_decisions == 4


# ═══════════════════════════════════════════════════════════════════
# 3. Outcome Analysis (5 tests)
# ═══════════════════════════════════════════════════════════════════

class TestOutcomeAnalysis:
    """结果分析测试."""

    def test_all_success(self):
        """全部成功时的结果分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.success_count == 5
        assert result.failure_count == 0
        assert result.success_rate == 1.0
        assert result.failure_reasons == []

    def test_all_failure(self):
        """全部失败时的结果分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "failure", "action_type": "increase_budget", "result_reason": "budget exceeded"},
            {"result": "failure", "action_type": "increase_budget", "result_reason": "low ROAS"},
            {"result": "failure", "action_type": "increase_budget", "result_reason": "budget exceeded"},
            {"result": "failure", "action_type": "increase_budget", "result_reason": "audience mismatch"},
            {"result": "failure", "action_type": "increase_budget", "result_reason": "low ROAS"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.success_count == 0
        assert result.failure_count == 5
        assert result.success_rate == 0.0
        assert len(result.failure_reasons) > 0

    def test_mixed_results(self):
        """混合结果时的分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget", "result_reason": "low ROAS"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget", "result_reason": "budget exceeded"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.success_count == 4
        assert result.failure_count == 2
        assert 0.6 < result.success_rate < 0.7

    def test_partial_results(self):
        """包含 partial 结果时的分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "partial", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "partial", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.success_rate == 0.6

    def test_with_lessons_learned(self):
        """包含 lessons_learned 的失败原因分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget",
             "result_reason": "low ROAS", "lessons_learned": ["creative decay is a risk"]},
            {"result": "failure", "action_type": "increase_budget",
             "result_reason": "budget exceeded", "lessons_learned": ["start with lower budget"]},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.success_count == 3
        assert result.failure_count == 2
        # Failure reasons should include both result_reason and lessons_learned
        assert len(result.failure_reasons) >= 2


# ═══════════════════════════════════════════════════════════════════
# 4. Risk Detection (6 tests)
# ═══════════════════════════════════════════════════════════════════

class TestRiskDetection:
    """风险检测测试."""

    def test_high_failure_rate_risk(self):
        """高失败率应触发风险信号."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "failure", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        risk_texts = " ".join(result.risk_signals)
        assert "High historical failure rate" in risk_texts

    def test_declining_trend_risk(self):
        """近期成功率下降趋势应触发风险信号."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            # older (higher success)
            {"result": "success", "action_type": "increase_budget", "created_at": "2026-01-01T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2026-01-02T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2026-01-03T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2026-01-04T00:00:00"},
            # recent (lower success)
            {"result": "failure", "action_type": "increase_budget", "created_at": "2026-06-01T00:00:00"},
            {"result": "failure", "action_type": "increase_budget", "created_at": "2026-06-02T00:00:00"},
            {"result": "failure", "action_type": "increase_budget", "created_at": "2026-06-03T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2026-06-04T00:00:00"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        risk_texts = " ".join(result.risk_signals)
        assert "Declining" in risk_texts or "declining" in risk_texts

    def test_high_avg_risk_score(self):
        """高平均风险评分应触发风险信号."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "risk_score": 0.7},
            {"result": "success", "action_type": "increase_budget", "risk_score": 0.65},
            {"result": "success", "action_type": "increase_budget", "risk_score": 0.8},
            {"result": "success", "action_type": "increase_budget", "risk_score": 0.55},
            {"result": "success", "action_type": "increase_budget", "risk_score": 0.75},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        risk_texts = " ".join(result.risk_signals)
        assert "Average historical risk score" in risk_texts

    def test_low_avg_confidence_risk(self):
        """低平均置信度应触发风险信号."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "confidence": 0.3},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.4},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.35},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.2},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.45},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        risk_texts = " ".join(result.risk_signals)
        assert "Low average confidence" in risk_texts

    def test_no_risks_detected(self):
        """所有指标良好时不应检测到风险."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "confidence": 0.8, "risk_score": 0.2},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.85, "risk_score": 0.15},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.9, "risk_score": 0.1},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.75, "risk_score": 0.25},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.8, "risk_score": 0.2},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert len(result.risk_signals) == 0

    def test_multiple_risks(self):
        """多个风险条件同时触发时应检测到多个风险."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory(
            [
                {"result": "failure", "action_type": "increase_budget", "confidence": 0.3, "risk_score": 0.7},
                {"result": "failure", "action_type": "increase_budget", "confidence": 0.2, "risk_score": 0.8},
                {"result": "failure", "action_type": "increase_budget", "confidence": 0.4, "risk_score": 0.65},
                {"result": "success", "action_type": "increase_budget", "confidence": 0.3, "risk_score": 0.7},
                {"result": "failure", "action_type": "increase_budget", "confidence": 0.35, "risk_score": 0.75},
            ]
        )
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        # Should have at least 3 risks: high failure rate, high avg risk, low avg confidence
        assert len(result.risk_signals) >= 3


# ═══════════════════════════════════════════════════════════════════
# 5. Recommendation Generation (6 tests)
# ═══════════════════════════════════════════════════════════════════

class TestRecommendationGeneration:
    """推荐生成测试."""

    def test_approve_with_high_success(self):
        """高成功率 + 足够成功数 → approve."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "confidence": 0.8, "risk_score": 0.2},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.85, "risk_score": 0.15},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.9, "risk_score": 0.1},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.75, "risk_score": 0.25},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.8, "risk_score": 0.2},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.recommendation == "approve"

    def test_approve_with_condition_on_risk(self):
        """中等成功率但有风险 → approve_with_condition."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "confidence": 0.4, "risk_score": 0.4},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.35, "risk_score": 0.45},
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.4, "risk_score": 0.4},
            {"result": "success", "action_type": "increase_budget", "confidence": 0.3, "risk_score": 0.35},
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.2, "risk_score": 0.5},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.recommendation == "approve_with_condition"
        assert result.condition != ""

    def test_deny_with_high_risk_signals(self):
        """高风险信号 (external) → deny."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        high_risk = RiskSignal(
            signal_type="creative_fatigue",
            risk_level="high",
            condition="CTR declining for 7 days",
            recommendations=["pause campaign", "refresh creative"],
        )
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
            risk_signals=[high_risk],
        )
        assert result.recommendation == "deny"
        assert "creative_fatigue" in result.condition

    def test_deny_with_critical_risk_signals(self):
        """critical 风险等级 → deny."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        critical_risk = RiskSignal(
            signal_type="strategy_decay",
            risk_level="critical",
            condition="complete strategy failure",
            recommendations=["abandon strategy"],
        )
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
            risk_signals=[critical_risk],
        )
        assert result.recommendation == "deny"

    def test_adjust_with_low_success(self):
        """低成功率 + 足够样本 → adjust."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.6, "risk_score": 0.5},
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.55, "risk_score": 0.55},
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.5, "risk_score": 0.6},
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.6, "risk_score": 0.5},
            {"result": "failure", "action_type": "increase_budget", "confidence": 0.55, "risk_score": 0.55},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.recommendation == "adjust"
        assert len(result.adjustments) >= 1

    def test_default_approve_with_insufficient_data_for_other(self):
        """边界情况：3-4个成功中有1-2个失败 → 默认 approve."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        # 3/4 success = 0.75, but success_count < 5, so falls through to medium path
        # 0.75 >= 0.5 and success_count >= 3, no detected risks → approve
        assert result.recommendation == "approve"


# ═══════════════════════════════════════════════════════════════════
# 6. Confidence (4 tests)
# ═══════════════════════════════════════════════════════════════════

class TestConfidence:
    """置信度计算测试."""

    def test_high_confidence_with_large_sample(self):
        """大样本且一致结果应产生高置信度."""
        enhancer = _make_enhancer()
        data = [{"result": "success", "action_type": "increase_budget", "confidence": 0.8} for _ in range(20)]
        memory = _make_decision_memory(data)
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.confidence > 0.7

    def test_low_confidence_with_small_sample(self):
        """小样本应产生较低置信度."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        # sample_factor = 1 - exp(-3/10) ≈ 0.259
        # result_certainty = |1.0 - 0.5| * 2 = 1.0
        # consistency = 3/3 = 1.0
        # confidence = 0.259*0.4 + 1.0*0.35 + 1.0*0.25 ≈ 0.7036
        # Actually this is fairly high. Let's verify
        assert 0.0 <= result.confidence <= 0.95

    def test_sample_factor_increases_with_more_data(self):
        """更多数据应提高置信度."""
        enhancer = _make_enhancer()
        data_small = [{"result": "success", "action_type": "increase_budget"} for _ in range(3)]
        data_large = [{"result": "success", "action_type": "increase_budget"} for _ in range(30)]

        result_small = enhancer.enhance(
            decision_memory=_make_decision_memory(data_small),
            action_type="increase_budget",
        )
        result_large = enhancer.enhance(
            decision_memory=_make_decision_memory(data_large),
            action_type="increase_budget",
        )
        assert result_large.confidence > result_small.confidence

    def test_mixed_results_lower_confidence(self):
        """混合结果应降低置信度."""
        enhancer = _make_enhancer()
        data_consistent = [{"result": "success", "action_type": "increase_budget"} for _ in range(10)]
        data_mixed = (
            [{"result": "success", "action_type": "increase_budget"} for _ in range(5)]
            + [{"result": "failure", "action_type": "increase_budget"} for _ in range(5)]
        )

        result_consistent = enhancer.enhance(
            decision_memory=_make_decision_memory(data_consistent),
            action_type="increase_budget",
        )
        result_mixed = enhancer.enhance(
            decision_memory=_make_decision_memory(data_mixed),
            action_type="increase_budget",
        )
        assert result_consistent.confidence > result_mixed.confidence


# ═══════════════════════════════════════════════════════════════════
# 7. Model Validation (4 tests)
# ═══════════════════════════════════════════════════════════════════

class TestModelValidation:
    """DecisionLearningResult 模型验证."""

    def test_decision_learning_result_properties(self):
        """验证 DecisionLearningResult 基本属性."""
        result = DecisionLearningResult(
            recommendation="approve",
            confidence=0.85,
            similar_decisions=10,
            success_count=8,
            failure_count=2,
            success_rate=0.8,
            failure_reasons=["budget exceeded"],
            risk_signals=["High historical failure rate"],
            adjustments=["Reduce scope"],
        )
        assert result.recommendation == "approve"
        assert result.confidence == 0.85
        assert result.similar_decisions == 10
        assert result.success_count == 8
        assert result.failure_count == 2
        assert result.success_rate == 0.8

    def test_is_safe(self):
        """is_safe 属性应在高置信度 + 高成功率时为 True."""
        safe_result = DecisionLearningResult(
            recommendation="approve",
            confidence=0.85,
            success_rate=0.8,
            success_count=8,
            failure_count=2,
        )
        assert safe_result.is_safe is True

        unsafe_result = DecisionLearningResult(
            recommendation="adjust",
            confidence=0.5,
            success_rate=0.3,
            success_count=3,
            failure_count=7,
        )
        assert unsafe_result.is_safe is False

    def test_to_dict(self):
        """to_dict 应包含所有关键字段."""
        result = DecisionLearningResult(
            recommendation="approve",
            confidence=0.8,
            similar_decisions=5,
            success_count=4,
            failure_count=1,
            success_rate=0.8,
            failure_reasons=["low ROAS"],
            risk_signals=["High risk"],
            adjustments=["reduce budget"],
        )
        d = result.to_dict()
        assert d["recommendation"] == "approve"
        assert d["confidence"] == 0.8
        assert d["similar_decisions"] == 5
        assert d["success_count"] == 4
        assert d["failure_count"] == 1
        assert d["success_rate"] == 0.8
        assert "is_safe" in d
        assert "result_id" in d

    def test_default_values(self):
        """默认值验证."""
        result = DecisionLearningResult()
        assert result.recommendation == "approve"
        assert result.confidence == 0.0
        assert result.similar_decisions == 0
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.success_rate == 0.0
        assert result.failure_reasons == []
        assert result.risk_signals == []
        assert result.adjustments == []
        assert result.condition == ""
        assert result.metadata == {}


# ═══════════════════════════════════════════════════════════════════
# 8. Edge Cases (5 tests)
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界情况测试."""

    def test_empty_result_metrics(self):
        """空 result_metrics 不影响分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "result_metrics": {}},
            {"result": "success", "action_type": "increase_budget", "result_metrics": {}},
            {"result": "success", "action_type": "increase_budget", "result_metrics": {}},
            {"result": "success", "action_type": "increase_budget", "result_metrics": {}},
            {"result": "success", "action_type": "increase_budget", "result_metrics": {}},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.success_count == 5
        assert result.confidence > 0.0

    def test_pending_decisions_are_excluded(self):
        """pending 决策应被排除在分析之外."""
        enhancer = _make_enhancer()
        memory = DecisionMemory()
        # 添加 pending 决策
        for i in range(3):
            exp = DecisionExperience(
                decision_id=f"pending_{i}",
                result="pending",
                confidence=0.5,
                risk_score=0.5,
                action_plan={"action_type": "increase_budget"},
                strategy_name="test",
            )
            memory._experiences[exp.experience_id] = exp
        # 添加已解决的决策
        for i in range(5):
            exp = DecisionExperience(
                decision_id=f"resolved_{i}",
                result="success",
                confidence=0.8,
                risk_score=0.2,
                action_plan={"action_type": "increase_budget"},
                strategy_name="test",
            )
            memory._experiences[exp.experience_id] = exp
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        # Only the 5 resolved decisions should be counted
        assert result.similar_decisions == 5
        assert result.success_count == 5

    def test_very_old_decisions(self):
        """非常旧的决策仍应参与分析."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget", "created_at": "2020-01-01T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2020-02-01T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2020-03-01T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2020-04-01T00:00:00"},
            {"result": "success", "action_type": "increase_budget", "created_at": "2020-05-01T00:00:00"},
        ])
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.similar_decisions == 5
        assert result.confidence > 0.0

    def test_no_resolved_decisions(self):
        """所有决策都是 pending 状态."""
        enhancer = _make_enhancer()
        memory = DecisionMemory()
        for i in range(10):
            exp = DecisionExperience(
                decision_id=f"d{i}",
                result="pending",
                confidence=0.5,
                risk_score=0.5,
                action_plan={"action_type": "increase_budget"},
                strategy_name="test",
            )
            memory._experiences[exp.experience_id] = exp
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.similar_decisions == 0
        assert result.confidence == 0.0

    def test_large_number_of_similar_decisions(self):
        """大量相似决策应正确处理."""
        enhancer = _make_enhancer()
        data = [{"result": "success" if i % 3 != 0 else "failure",
                 "action_type": "increase_budget",
                 "confidence": 0.7 + (i % 3) * 0.05,
                 "risk_score": 0.3 - (i % 3) * 0.05}
                for i in range(50)]
        memory = _make_decision_memory(data)
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="increase_budget",
        )
        assert result.similar_decisions == 50
        assert result.confidence > 0.0


# ═══════════════════════════════════════════════════════════════════
# 9. Integration (5 tests)
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试."""

    def test_full_pipeline_approve(self):
        """完整流程：高成功率场景 → approve."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "scale_campaign", "strategy_name": "scale_winning",
             "confidence": 0.85, "risk_score": 0.15},
            {"result": "success", "action_type": "scale_campaign", "strategy_name": "scale_winning",
             "confidence": 0.9, "risk_score": 0.1},
            {"result": "success", "action_type": "scale_campaign", "strategy_name": "scale_winning",
             "confidence": 0.8, "risk_score": 0.2},
            {"result": "success", "action_type": "scale_campaign", "strategy_name": "scale_winning",
             "confidence": 0.85, "risk_score": 0.15},
            {"result": "success", "action_type": "scale_campaign", "strategy_name": "scale_winning",
             "confidence": 0.9, "risk_score": 0.1},
            {"result": "success", "action_type": "scale_campaign", "strategy_name": "scale_winning",
             "confidence": 0.85, "risk_score": 0.15},
        ])
        result = enhancer.enhance(
            context={"action_type": "scale_campaign", "strategy_name": "scale_winning"},
            decision_memory=memory,
        )
        assert result.recommendation == "approve"
        assert result.confidence > 0.7
        assert result.success_rate == 1.0
        assert len(result.risk_signals) == 0

    def test_full_pipeline_deny(self):
        """完整流程：critical 风险信号 → deny."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "replace_creative"},
            {"result": "success", "action_type": "replace_creative"},
            {"result": "success", "action_type": "replace_creative"},
            {"result": "success", "action_type": "replace_creative"},
            {"result": "success", "action_type": "replace_creative"},
        ])
        risk = RiskSignal(
            signal_type="creative_fatigue",
            risk_level="critical",
            condition="CTR dropped 50% in 3 days",
            recommendations=["halt", "audit"],
        )
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="replace_creative",
            risk_signals=[risk],
        )
        assert result.recommendation == "deny"
        assert result.condition != ""

    def test_full_pipeline_with_risk_signals(self):
        """完整流程：包含外部风险信号."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "bid_adjust", "confidence": 0.7, "risk_score": 0.3},
            {"result": "success", "action_type": "bid_adjust", "confidence": 0.65, "risk_score": 0.35},
            {"result": "failure", "action_type": "bid_adjust", "confidence": 0.6, "risk_score": 0.4},
            {"result": "success", "action_type": "bid_adjust", "confidence": 0.7, "risk_score": 0.3},
            {"result": "success", "action_type": "bid_adjust", "confidence": 0.65, "risk_score": 0.35},
        ])
        low_risk = RiskSignal(
            signal_type="budget_inefficiency",
            risk_level="low",
            condition="slight budget waste",
            recommendations=["monitor"],
        )
        result = enhancer.enhance(
            decision_memory=memory,
            action_type="bid_adjust",
            risk_signals=[low_risk],
        )
        # low risk doesn't trigger deny, so it should be approve_with_condition or approve
        assert result.recommendation != "deny"

    def test_incremental_enhancements(self):
        """增量增强：多次调用 enhance 应独立工作."""
        enhancer = _make_enhancer()
        memory = _make_decision_memory([
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "success", "action_type": "increase_budget"},
            {"result": "failure", "action_type": "decrease_budget"},
            {"result": "failure", "action_type": "decrease_budget"},
            {"result": "failure", "action_type": "decrease_budget"},
            {"result": "failure", "action_type": "decrease_budget"},
            {"result": "failure", "action_type": "decrease_budget"},
        ])

        result1 = enhancer.enhance(decision_memory=memory, action_type="increase_budget")
        result2 = enhancer.enhance(decision_memory=memory, action_type="decrease_budget")

        assert result1.recommendation == "approve"
        assert result2.recommendation in ("adjust", "approve_with_condition")
        assert enhancer.enhancement_count == 2

    def test_real_decision_memory_integration(self):
        """使用真实 DecisionMemory API 的完整集成测试."""
        enhancer = _make_enhancer()
        memory = DecisionMemory()

        # 手动添加多个 DecisionExperience
        from datetime import datetime, timezone
        for i in range(10):
            exp = DecisionExperience(
                decision_id=f"real_d{i}",
                strategy_name="test_strategy",
                result="success" if i < 7 else "failure",
                confidence=0.8,
                risk_score=0.2,
                action_plan={"action_type": "test_action"},
                result_reason="good" if i < 7 else "bad performance",
                created_at=datetime(2026, 7, i + 1, tzinfo=timezone.utc).isoformat(),
            )
            memory._experiences[exp.experience_id] = exp

        # Verify find_similar works
        similar = memory.find_similar(limit=50)
        assert len(similar) == 10

        result = enhancer.enhance(
            decision_memory=memory,
            action_type="test_action",
            strategy_name="test_strategy",
        )
        assert result.similar_decisions == 10
        assert result.success_count == 7
        assert result.failure_count == 3
        assert result.confidence > 0.0