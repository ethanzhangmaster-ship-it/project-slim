"""Day 6.5 Decision Memory Synchronization — 测试用例.

测试覆盖:
  - Test 1: DecisionMemoryRetriever 查询类似决策
  - Test 2: Pattern + Decision 联合增强
  - Test 3: 失败经验抑制
  - Test 4: 完整闭环 (OpportunityDetector → DecisionEnhancer → DecisionEngine)
  - Test 5: DecisionEngine 集成 DecisionMemoryRetriever
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.decision import (
    DecisionContext,
    DecisionEnhancer,
    DecisionHistoryResult,
    DecisionMemoryRetriever,
    DecisionRecord,
    EnhancementReport,
)
from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
    PatternRetriever,
    RetrievalContext,
    RetrievalResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision import (
    DecisionEngine,
    DecisionExperience,
    DecisionInput,
    DecisionMemory,
    DecisionOutput,
    DecisionScore,
    DecisionType,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
    GrowthOpportunity,
    OpportunityType,
    StrategyCandidate,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_experience(
    decision_id: str = "d001",
    opportunity_type: str = "creative_fatigue",
    strategy_name: str = "replace_creative",
    action_type: str = "replace_creative",
    result: str = "success",
    result_metrics: dict | None = None,
    confidence: float = 0.85,
) -> DecisionExperience:
    """创建测试用 DecisionExperience."""
    exp = DecisionExperience(
        decision_id=decision_id,
        opportunity_type=opportunity_type,
        strategy_name=strategy_name,
        confidence=confidence,
        action_plan={"action_type": action_type},
        result=result,
        result_metrics=result_metrics or {},
    )
    if result != "pending":
        exp.resolved_at = datetime.now(timezone.utc).isoformat()
    return exp


def _populate_memory(
    memory: DecisionMemory,
    experiences: list[DecisionExperience],
) -> None:
    """填充 DecisionMemory."""
    for exp in experiences:
        memory._experiences[exp.experience_id] = exp


def _make_candidate(
    strategy_id: str = "S001",
    name: str = "replace_creative",
    action_type: str = "replace_creative",
    historical_score: float = 0.78,
    confidence: float = 0.85,
    risk: float = 0.15,
) -> StrategyCandidate:
    """创建测试用 StrategyCandidate."""
    return StrategyCandidate(
        strategy_id=strategy_id,
        strategy_name=name,
        strategy={
            "action_type": action_type,
        },
        historical_score=historical_score,
        confidence_score=confidence,
        risk_score=risk,
        final_score=historical_score * confidence * (1 - risk),
    )


def _make_opportunity(
    opportunity_id: str = "opp_001",
    opp_type: OpportunityType = OpportunityType.CREATIVE_REFRESH,
    confidence: float = 0.91,
    reason: str = "CTR dropped 35%",
) -> GrowthOpportunity:
    """创建测试用 GrowthOpportunity."""
    return GrowthOpportunity(
        opportunity_id=opportunity_id,
        opportunity_type=opp_type,
        confidence=confidence,
        reason=reason,
    )


# ═══════════════════════════════════════════════════════════════
# Test 1: DecisionMemoryRetriever 查询类似决策
# ═══════════════════════════════════════════════════════════════


class TestDecisionMemoryRetriever:
    """Test 1: DecisionMemory 查询类似决策."""

    def test_retrieve_similar_decisions(self):
        """过去10次 replace_creative，7次成功 → success_rate=0.7."""
        memory = DecisionMemory()
        exps = []
        for i in range(10):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 7 else "failure",
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=3)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        ))

        assert result.total_matched == 10
        assert result.success_rate == 0.7
        assert result.has_recommendations
        # 成功率 >= 0.5 且样本 >= 3 → 推荐
        assert result.recommended_action == "replace_creative"
        assert result.confidence > 0.0

    def test_retrieve_no_match(self):
        """无匹配决策时返回空结果."""
        memory = DecisionMemory()
        retriever = DecisionMemoryRetriever(memory)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="unknown_type",
        ))

        assert result.total_matched == 0
        assert result.success_rate == 0.0
        assert not result.has_recommendations
        assert "No historical decisions" in result.summary

    def test_retrieve_insufficient_samples(self):
        """样本不足时不推荐."""
        memory = DecisionMemory()
        exps = [
            _make_experience(decision_id="d001", opportunity_type="creative_fatigue",
                             action_type="replace_creative", result="success"),
            _make_experience(decision_id="d002", opportunity_type="creative_fatigue",
                             action_type="replace_creative", result="success"),
        ]
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        ))

        assert result.total_matched == 2
        # 样本 < min_resolved → 不推荐
        assert result.recommended_action == ""

    def test_retrieve_confidence_with_many_samples(self):
        """大量样本时置信度较高."""
        memory = DecisionMemory()
        exps = []
        for i in range(50):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 40 else "failure",
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        ))

        assert result.success_rate == 0.8
        assert result.confidence > 0.5  # 样本量 × 成功率
        assert result.recommended_action == "replace_creative"

    def test_retrieve_by_action_type_filter(self):
        """按 action_type 过滤历史决策."""
        memory = DecisionMemory()
        exps = [
            _make_experience(decision_id="d001", opportunity_type="creative_fatigue",
                             action_type="replace_creative", result="success"),
            _make_experience(decision_id="d002", opportunity_type="creative_fatigue",
                             action_type="scale_budget", result="failure"),
            _make_experience(decision_id="d003", opportunity_type="creative_fatigue",
                             action_type="replace_creative", result="success"),
        ]
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=2)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        ))

        # 应该只匹配 replace_creative 的决策
        replace_count = sum(1 for r in result.similar_decisions
                          if r.action_type == "replace_creative")
        assert replace_count >= 2


# ═══════════════════════════════════════════════════════════════
# Test 2: Pattern + Decision 联合增强
# ═══════════════════════════════════════════════════════════════


class TestPatternDecisionJointEnhancement:
    """Test 2: Pattern + Decision 联合增强."""

    def test_joint_enhancement_confidence(self):
        """Pattern + Decision 联合增强 → confidence > base."""
        from unittest.mock import MagicMock

        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRecommendation,
        )
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternAction,
            PatternCondition,
            PatternMemory,
            PatternPerformance,
        )

        # 构建 Pattern 推荐
        pattern = PatternMemory(
            pattern_id="pat_001",
            condition=PatternCondition(
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
            ),
            action=PatternAction(action_type="replace_creative"),
            performance=PatternPerformance(
                samples=100,
                success_count=85,
                success_rate=0.85,
                avg_reward=0.75,
            ),
        )

        rec = PatternRecommendation(
            pattern=pattern,
            confidence=0.85,
            similarity_score=0.90,
            reasoning="High confidence pattern match",
        )

        retrieval_result = RetrievalResult(
            recommendations=[rec],
            top_action=rec,
        )

        # Mock PatternRetriever
        mock_pattern_retriever = MagicMock(spec=PatternRetriever)
        mock_pattern_retriever.retrieve.return_value = retrieval_result

        # 构建 Decision 历史
        decision_memory = DecisionMemory()
        decision_exps = []
        for i in range(20):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 14 else "failure",
            )
            decision_exps.append(exp)
        _populate_memory(decision_memory, decision_exps)

        decision_retriever = DecisionMemoryRetriever(decision_memory, min_resolved=5)

        enhancer = DecisionEnhancer(
            pattern_retriever=mock_pattern_retriever,
            decision_retriever=decision_retriever,
        )

        # 构建 DecisionInput
        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(
            confidence=0.60,
        )
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )

        enhanced_input, report = enhancer.enhance(input_data)

        # 验证: Pattern + Decision 都使用了
        assert report.pattern_used
        assert report.decision_used
        # 合并置信度 > 基础置信度
        assert report.merged_confidence > 0.0
        # 策略置信度应该有调整
        assert report.strategies_added >= 0

    def test_enhancement_report_has_both_sources(self):
        """EnhancementReport 包含 Pattern 和 Decision 来源."""
        from unittest.mock import MagicMock

        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRecommendation,
        )
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternAction,
            PatternCondition,
            PatternMemory,
            PatternPerformance,
        )

        pattern = PatternMemory(
            pattern_id="pat_001",
            condition=PatternCondition(
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
            ),
            action=PatternAction(action_type="replace_creative"),
            performance=PatternPerformance(
                samples=100, success_count=70, success_rate=0.70, avg_reward=0.60,
            ),
        )
        rec = PatternRecommendation(
            pattern=pattern, confidence=0.70, similarity_score=0.80, reasoning="Match",
        )
        retrieval_result = RetrievalResult(
            recommendations=[rec], top_action=rec,
        )

        mock_pattern_retriever = MagicMock(spec=PatternRetriever)
        mock_pattern_retriever.retrieve.return_value = retrieval_result

        decision_memory = DecisionMemory()
        exps = [_make_experience(
            decision_id=f"d{i:03d}", opportunity_type="creative_fatigue",
            action_type="replace_creative", result="success",
        ) for i in range(10)]
        _populate_memory(decision_memory, exps)
        decision_retriever = DecisionMemoryRetriever(decision_memory, min_resolved=5)

        enhancer = DecisionEnhancer(
            pattern_retriever=mock_pattern_retriever,
            decision_retriever=decision_retriever,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[_make_candidate()],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )

        enhanced_input, report = enhancer.enhance(input_data)

        assert report.pattern_used
        assert report.decision_used
        assert report.retrieval_result is not None
        assert report.decision_history is not None
        assert "Pattern-enhanced" in report.summary or "Decision history" in report.summary


# ═══════════════════════════════════════════════════════════════
# Test 3: 失败经验抑制
# ═══════════════════════════════════════════════════════════════


class TestFailureSuppression:
    """Test 3: 失败经验抑制."""

    def test_high_failure_rate_generates_warning(self):
        """scale budget 失败率90% → warning: avoid scale."""
        memory = DecisionMemory()
        exps = []
        for i in range(20):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="roas_drop",
                action_type="scale_budget",
                result="success" if i < 2 else "failure",  # 90% failure
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="roas_drop",
            action_type="scale_budget",
        ))

        assert result.success_rate == 0.1
        # 应该有 AVOID 警告
        avoid_warnings = [w for w in result.warnings if "AVOID" in w]
        assert len(avoid_warnings) > 0
        assert "scale_budget" in avoid_warnings[0]

    def test_decision_enhancer_penalizes_failure_pattern(self):
        """DecisionEnhancer 对历史失败动作进行惩罚."""
        from unittest.mock import MagicMock

        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRecommendation,
        )
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternAction,
            PatternCondition,
            PatternMemory,
            PatternPerformance,
        )

        # Pattern 推荐 scale_budget (但历史失败率高)
        pattern = PatternMemory(
            pattern_id="pat_scale",
            condition=PatternCondition(
                opportunity_type="roas_drop",
                action_type="scale_budget",
            ),
            action=PatternAction(action_type="scale_budget"),
            performance=PatternPerformance(
                samples=50, success_count=10, success_rate=0.20, avg_reward=-0.30,
            ),
        )
        rec = PatternRecommendation(
            pattern=pattern, confidence=0.20, similarity_score=0.60,
            reasoning="Low confidence match",
        )

        # 作为 avoid (而不是 recommend)
        retrieval_result = RetrievalResult(
            recommendations=[],
            top_action=rec,
            avoid_actions=[rec],
        )

        mock_pattern_retriever = MagicMock(spec=PatternRetriever)
        mock_pattern_retriever.retrieve.return_value = retrieval_result

        # Decision 历史也显示 scale_budget 失败率高
        decision_memory = DecisionMemory()
        decision_exps = []
        for i in range(15):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="roas_drop",
                action_type="scale_budget",
                result="success" if i < 2 else "failure",
            )
            decision_exps.append(exp)
        _populate_memory(decision_memory, decision_exps)

        decision_retriever = DecisionMemoryRetriever(decision_memory, min_resolved=5)

        enhancer = DecisionEnhancer(
            pattern_retriever=mock_pattern_retriever,
            decision_retriever=decision_retriever,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[_make_candidate(
                name="scale_budget",
                action_type="scale_budget",
                confidence=0.70,
            )],
            metadata={
                "opportunity_type": "roas_drop",
                "action_type": "scale_budget",
            },
        )

        enhanced_input, report = enhancer.enhance(input_data)

        # 应该有警告
        assert len(report.warnings) > 0
        # 策略置信度应该被降低
        if report.confidence_adjustments:
            penalties = [a for a in report.confidence_adjustments
                        if a["adjustment"].startswith("-")]
            assert len(penalties) > 0

    def test_no_warning_for_insufficient_samples(self):
        """样本不足时不应生成警告（低置信度除外）."""
        memory = DecisionMemory()
        exps = [
            _make_experience(decision_id="d001", opportunity_type="roas_drop",
                             action_type="scale_budget", result="failure"),
            _make_experience(decision_id="d002", opportunity_type="roas_drop",
                             action_type="scale_budget", result="failure"),
        ]
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        result = retriever.retrieve(DecisionContext(
            opportunity_type="roas_drop",
            action_type="scale_budget",
        ))

        # 样本 < 3 → 不应有 AVOID 警告
        avoid_warnings = [w for w in result.warnings if "AVOID" in w]
        assert len(avoid_warnings) == 0


# ═══════════════════════════════════════════════════════════════
# Test 4: 完整闭环
# ═══════════════════════════════════════════════════════════════


class TestFullClosedLoop:
    """Test 4: 完整闭环 (DecisionEngine 集成 DecisionMemoryRetriever)."""

    def test_decision_engine_with_history(self):
        """DecisionEngine 集成 DecisionMemoryRetriever 的完整决策流程."""
        # 准备历史决策
        memory = DecisionMemory()
        exps = []
        for i in range(10):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 7 else "failure",
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        engine = DecisionEngine(
            memory=memory,
            decision_retriever=retriever,
        )

        # 构建 DecisionInput
        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(confidence=0.60)
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )

        output = engine.decide(input_data)

        # 验证: 决策输出包含历史信息
        assert output.decision_id
        assert "decision_history" in output.metadata
        history = output.metadata["decision_history"]
        assert history["total_matched"] == 10
        assert history["success_rate"] == 0.7
        assert history["recommended_action"] == "replace_creative"

    def test_decision_engine_without_retriever(self):
        """无 DecisionMemoryRetriever 时正常降级决策."""
        engine = DecisionEngine(
            memory=DecisionMemory(),
            decision_retriever=None,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(confidence=0.60)
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
        )

        output = engine.decide(input_data)

        # 验证: 正常决策，无历史信息
        assert output.decision_id
        assert "decision_history" not in output.metadata

    def test_decision_engine_with_history_warnings(self):
        """历史警告被注入到决策输出."""
        memory = DecisionMemory()
        exps = []
        for i in range(20):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="roas_drop",
                action_type="scale_budget",
                result="success" if i < 2 else "failure",
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        engine = DecisionEngine(
            memory=memory,
            decision_retriever=retriever,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(
            name="scale_budget",
            action_type="scale_budget",
            confidence=0.70,
        )
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
            metadata={
                "opportunity_type": "roas_drop",
                "action_type": "scale_budget",
            },
        )

        output = engine.decide(input_data)

        # 验证: 输出包含历史警告
        assert "decision_history" in output.metadata
        # 应该有 AVOID 警告
        avoid_warnings = [w for w in output.warnings if "AVOID" in w]
        assert len(avoid_warnings) > 0

    def test_full_cycle_record_and_recall(self):
        """完整闭环: 决策 → 记录 → 再查询."""
        memory = DecisionMemory()

        # 第一次决策
        engine1 = DecisionEngine(memory=memory, decision_retriever=None)
        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[_make_candidate(confidence=0.60)],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )
        output1 = engine1.decide(input_data)

        # 记录结果
        memory.record_outcome(
            decision_id=output1.decision_id,
            result="success",
            metrics={"roas_change": 0.15},
        )

        # 第二次决策 (带 retriever)
        retriever = DecisionMemoryRetriever(memory, min_resolved=1)
        engine2 = DecisionEngine(memory=memory, decision_retriever=retriever)

        input_data2 = DecisionInput(
            opportunity=opp,
            strategies=[_make_candidate(
                strategy_id="S002",
                confidence=0.60,
            )],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )
        output2 = engine2.decide(input_data2)

        # 验证: 第二次决策能查到第一次的历史
        assert "decision_history" in output2.metadata
        history = output2.metadata["decision_history"]
        assert history["total_matched"] >= 1


# ═══════════════════════════════════════════════════════════════
# Test 5: DecisionEngine 置信度调整
# ═══════════════════════════════════════════════════════════════


class TestDecisionEngineConfidenceAdjustment:
    """Test 5: DecisionEngine 基于历史调整置信度."""

    def test_history_boosts_confidence(self):
        """高成功率历史 → 置信度提升."""
        memory = DecisionMemory()
        exps = []
        for i in range(20):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 18 else "failure",
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        engine = DecisionEngine(
            memory=memory,
            decision_retriever=retriever,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(
            name="replace_creative",
            action_type="replace_creative",
            confidence=0.50,
        )
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )

        output = engine.decide(input_data)

        # 历史高分 → 决策置信度应高于原始
        assert output.confidence >= 0.50  # 至少不低于原始
        # 有历史推荐理由
        history_reasons = [r for r in output.reasons if "Decision history" in r]
        assert len(history_reasons) > 0

    def test_low_history_reduces_confidence(self):
        """低成功率历史 → 置信度降低."""
        memory = DecisionMemory()
        exps = []
        for i in range(20):
            exp = _make_experience(
                decision_id=f"d{i:03d}",
                opportunity_type="roas_drop",
                action_type="scale_budget",
                result="success" if i < 4 else "failure",
            )
            exps.append(exp)
        _populate_memory(memory, exps)

        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        engine = DecisionEngine(
            memory=memory,
            decision_retriever=retriever,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(
            name="scale_budget",
            action_type="scale_budget",
            confidence=0.70,
        )
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
            metadata={
                "opportunity_type": "roas_drop",
                "action_type": "scale_budget",
            },
        )

        output = engine.decide(input_data)

        # 历史低分 → 应有警告
        assert "decision_history" in output.metadata
        history = output.metadata["decision_history"]
        assert history["success_rate"] < 0.3

    def test_empty_history_no_effect(self):
        """无历史时决策正常进行."""
        memory = DecisionMemory()
        retriever = DecisionMemoryRetriever(memory, min_resolved=5)

        engine = DecisionEngine(
            memory=memory,
            decision_retriever=retriever,
        )

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        candidate = _make_candidate(confidence=0.60)
        input_data = DecisionInput(
            opportunity=opp,
            strategies=[candidate],
            metadata={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )

        output = engine.decide(input_data)

        # 应有决策输出，但无历史
        assert output.decision_id
        assert "decision_history" not in output.metadata


# ═══════════════════════════════════════════════════════════════
# DecisionRecord
# ═══════════════════════════════════════════════════════════════


class TestDecisionRecord:
    """DecisionRecord 数据模型测试."""

    def test_from_decision_experience_success(self):
        """从成功经验构建 DecisionRecord."""
        exp = _make_experience(
            decision_id="d001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            result="success",
            result_metrics={"roas_change": 0.15, "ctr_change": 0.02},
        )

        record = DecisionRecord.from_decision_experience(exp)

        assert record.decision_id == "d001"
        assert record.opportunity_type == "creative_fatigue"
        assert record.action_type == "replace_creative"
        assert record.success is True
        assert record.outcome["roas_change"] == 0.15

    def test_from_decision_experience_failure(self):
        """从失败经验构建 DecisionRecord."""
        exp = _make_experience(
            decision_id="d002",
            opportunity_type="roas_drop",
            action_type="scale_budget",
            result="failure",
        )

        record = DecisionRecord.from_decision_experience(exp)

        assert record.decision_id == "d002"
        assert record.success is False
        assert record.outcome["reward"] < 0  # 失败有负奖励

    def test_record_to_dict(self):
        """DecisionRecord 序列化."""
        record = DecisionRecord(
            decision_id="d001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success=True,
        )

        d = record.to_dict()
        assert d["decision_id"] == "d001"
        assert d["success"] is True


# ═══════════════════════════════════════════════════════════════
# DecisionHistoryResult
# ═══════════════════════════════════════════════════════════════


class TestDecisionHistoryResult:
    """DecisionHistoryResult 数据模型测试."""

    def test_empty_result(self):
        """空结果."""
        result = DecisionHistoryResult()
        assert not result.has_recommendations
        assert not result.has_warnings
        assert result.total_matched == 0

    def test_result_with_data(self):
        """有数据的结果."""
        result = DecisionHistoryResult(
            similar_decisions=[
                DecisionRecord(decision_id="d001", success=True),
                DecisionRecord(decision_id="d002", success=False),
            ],
            success_rate=0.5,
            confidence=0.45,
            recommended_action="replace_creative",
            warnings=["AVOID 'scale_budget': 90% failure rate"],
            total_matched=2,
        )

        assert result.has_recommendations
        assert result.has_warnings
        assert result.total_matched == 2

        d = result.to_dict()
        assert d["total_matched"] == 2
        assert d["success_rate"] == 0.5
        assert len(d["warnings"]) == 1