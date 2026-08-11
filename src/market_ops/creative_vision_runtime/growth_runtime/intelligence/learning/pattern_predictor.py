"""E13.7.5 Pattern Predictor — 模式预测引擎.

Day 7.5.2:
  从 LearningKnowledge + PatternStore 中预测给定上下文的最佳模式，
  从"查历史模式"升级为"预测未来模式效果"。

核心流程:
  Context (game, country, creative, spend, ...)
              |
              v
  PatternPredictor.predict(context)
              |
              +--> _match_context()  → 上下文匹配
              |
              +--> _score_patterns() → 模式评分
              |
              +--> _estimate_roas()  → ROAS 预估
              |
              +--> _assess_risk()    → 风险评估
              |
              v
  PatternPrediction (recommended_pattern + expected_roas + confidence)

设计原则:
  - 纯基于知识数据，不产生副作用
  - 多维上下文匹配 (game, country, creative, audience, spend)
  - 确定性可解释的预测逻辑
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .models.learning_models import (
    LearnedPattern,
    LearningKnowledge,
    PatternPrediction,
    RiskSignal,
    StrategyInsight,
)


class PatternPredictor:
    """模式预测器 — 给定上下文预测最佳模式和预期效果.

    用法:
        predictor = PatternPredictor()
        prediction = predictor.predict(
            context={"game": "Merge Witch", "country": "US", "creative": "female_character"},
            knowledge=knowledge_from_extractor,
        )
    """

    def __init__(
        self,
        min_match_score: float = 0.15,
        min_prediction_confidence: float = 0.50,
    ) -> None:
        """初始化预测器.

        Args:
            min_match_score: 最小上下文匹配分数
            min_prediction_confidence: 最小预测置信度阈值
        """
        self._min_match_score = min_match_score
        self._min_prediction_confidence = min_prediction_confidence
        self._prediction_count: int = 0

    @property
    def prediction_count(self) -> int:
        return self._prediction_count

    # ── Public API ───────────────────────────────────────────────

    def predict(
        self,
        context: dict[str, Any] | None = None,
        knowledge: LearningKnowledge | None = None,
        action_type: str = "",
    ) -> PatternPrediction:
        """预测给定上下文下的最佳模式.

        Args:
            context: 上下文信息 (game, country, creative, audience, spend, ...)
            knowledge: 从历史经验中提取的知识
            action_type: 动作类型过滤 (可选)

        Returns:
            PatternPrediction: 模式预测结果
        """
        self._prediction_count += 1
        ctx = context or {}

        if knowledge is None or not knowledge.patterns:
            return PatternPrediction(
                confidence=0.0,
                context_match_score=0.0,
                risk_level="medium",
                metadata={"reason": "no_knowledge_available"},
            )

        # 1. 匹配上下文
        matched = self._match_context(ctx, knowledge, action_type)
        if not matched:
            return PatternPrediction(
                confidence=0.0,
                context_match_score=0.0,
                risk_level="medium",
                metadata={"reason": "no_context_match"},
            )

        # 2. 评分排序
        scored = self._score_patterns(matched, ctx)
        if not scored:
            return PatternPrediction(
                confidence=0.0,
                context_match_score=self._compute_context_match(ctx, knowledge),
                risk_level="medium",
                metadata={"reason": "no_patterns_above_threshold"},
            )

        best_pattern, best_score = scored[0]

        # 3. ROAS 预估
        expected_roas = self._estimate_roas(best_pattern, knowledge)

        # 4. 风险评估
        risk_level, risk_recommendations = self._assess_risk(ctx, knowledge)

        # 5. 综合建议
        recommendations = self._generate_recommendations(best_pattern, knowledge, risk_level)

        # 6. 置信度
        confidence = self._compute_prediction_confidence(best_pattern, scored, ctx, knowledge)

        return PatternPrediction(
            recommended_pattern=f"{best_pattern.dimension}|{best_pattern.condition}",
            expected_roas=round(expected_roas, 4),
            expected_success_rate=round(best_pattern.success_rate, 4),
            confidence=round(confidence, 4),
            matched_patterns=[p for p, _ in scored[:5]],
            context_match_score=round(self._compute_context_match(ctx, knowledge), 4),
            risk_level=risk_level,
            recommendations=recommendations,
            metadata={
                "total_patterns": len(knowledge.patterns),
                "matched_count": len(matched),
                "context_fields": list(ctx.keys()),
            },
        )

    # ── Context Matching ────────────────────────────────────────

    def _match_context(
        self,
        context: dict[str, Any],
        knowledge: LearningKnowledge,
        action_type: str = "",
    ) -> list[LearnedPattern]:
        """将上下文与知识中的模式匹配."""
        matched: list[tuple[LearnedPattern, float]] = []

        for pattern in knowledge.patterns:
            score = self._pattern_context_score(pattern, context, action_type)
            if score >= self._min_match_score:
                matched.append((pattern, score))

        # 按匹配分排序
        matched.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in matched]

    def _pattern_context_score(
        self,
        pattern: LearnedPattern,
        context: dict[str, Any],
        action_type: str = "",
    ) -> float:
        """计算单个模式与上下文的匹配度."""
        score = 0.0
        fields = 0

        # 维度匹配
        if "dimension" in context and context["dimension"] == pattern.dimension:
            score += 0.3
            fields += 1

        # 条件关键词匹配
        condition_lower = pattern.condition.lower()
        context_fields = {
            "game": 0.15,
            "country": 0.15,
            "creative": 0.2,
            "audience": 0.15,
            "spend": 0.1,
        }
        for field, weight in context_fields.items():
            if field in context:
                val = str(context[field]).lower()
                if val in condition_lower:
                    score += weight
                    fields += 1

        # 元数据匹配
        meta = pattern.metadata
        if "action_types" in meta:
            meta_types = [str(t).lower() for t in meta["action_types"]]
            if action_type.lower() in meta_types:
                score += 0.15
                fields += 1

        # 策略名匹配
        if "strategy_names" in meta:
            for sn in meta["strategy_names"]:
                if str(sn).lower() in condition_lower:
                    score += 0.1
                    fields += 1
                    break

        # 规则化: 至少匹配1个字段才有效
        if fields == 0:
            return 0.0

        return min(0.95, score)

    def _compute_context_match(
        self,
        context: dict[str, Any],
        knowledge: LearningKnowledge,
    ) -> float:
        """计算整体上下文匹配度."""
        if not knowledge.patterns or not context:
            return 0.0

        scores = [
            self._pattern_context_score(p, context)
            for p in knowledge.patterns
        ]
        return sum(scores) / len(scores) if scores else 0.0

    # ── Pattern Scoring ─────────────────────────────────────────

    def _score_patterns(
        self,
        patterns: list[LearnedPattern],
        context: dict[str, Any],
    ) -> list[tuple[LearnedPattern, float]]:
        """对模式进行综合评分.

        评分公式:
          score = confidence × 0.35 + sample_factor × 0.25
                + success_rate × 0.25 + impact_bonus × 0.15
        """
        scored: list[tuple[LearnedPattern, float]] = []

        for p in patterns:
            sample_factor = 1.0 - math.exp(-p.sample_count / 10.0)
            impact_bonus = 0.3 if p.impact == "positive" else (-0.3 if p.impact == "negative" else 0.0)

            score = (
                p.confidence * 0.35
                + sample_factor * 0.25
                + p.success_rate * 0.25
                + (0.5 + impact_bonus) * 0.15
            )
            score = round(min(0.95, max(0.0, score)), 4)

            if score >= self._min_prediction_confidence * 0.5:
                scored.append((p, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ── ROAS Estimation ─────────────────────────────────────────

    def _estimate_roas(
        self,
        best_pattern: LearnedPattern,
        knowledge: LearningKnowledge,
    ) -> float:
        """预估 ROAS.

        基于:
          - 模式平均奖励
          - 策略有效性
          - 风险信号影响
        """
        base_roas = 1.0 + best_pattern.avg_reward * 0.5

        # 策略加成
        strategy_bonus = 0.0
        for strategy in knowledge.strategies:
            if strategy.strategy_name in str(best_pattern.metadata.get("strategy_names", [])):
                strategy_bonus = max(strategy_bonus, strategy.avg_effectiveness * 0.3)
        base_roas += strategy_bonus

        # 风险折扣
        risk_discount = 0.0
        for risk in knowledge.warnings:
            if risk.risk_level in ("high", "critical"):
                risk_discount = max(risk_discount, abs(risk.avg_impact) * 0.2)
        base_roas -= risk_discount

        return round(max(0.5, min(2.5, base_roas)), 4)

    # ── Risk Assessment ─────────────────────────────────────────

    def _assess_risk(
        self,
        context: dict[str, Any],
        knowledge: LearningKnowledge,
    ) -> tuple[str, list[str]]:
        """评估预测风险."""
        recommendations: list[str] = []

        high_risks = [r for r in knowledge.warnings if r.risk_level in ("high", "critical")]
        medium_risks = [r for r in knowledge.warnings if r.risk_level == "medium"]

        if high_risks:
            for r in high_risks:
                recommendations.extend(r.recommendations[:2])
            return "high", recommendations

        if medium_risks:
            for r in medium_risks:
                recommendations.extend(r.recommendations[:1])
            return "medium", recommendations

        return "low", ["Proceed with standard monitoring"]

    # ── Recommendations ─────────────────────────────────────────

    def _generate_recommendations(
        self,
        best_pattern: LearnedPattern,
        knowledge: LearningKnowledge,
        risk_level: str,
    ) -> list[str]:
        """生成执行建议."""
        recs: list[str] = []

        if best_pattern.impact == "positive":
            recs.append(f"Leverage pattern: {best_pattern.condition}")
            if best_pattern.confidence >= 0.7:
                recs.append("High confidence — suitable for direct execution")
            else:
                recs.append("Moderate confidence — consider A/B testing first")
        elif best_pattern.impact == "negative":
            recs.append(f"Avoid pattern: {best_pattern.condition}")
            recs.append("Consider alternative creative/strategy approaches")
        else:
            recs.append(f"Pattern neutral: {best_pattern.condition} — monitor closely")

        # 策略建议
        strong_strategies = [s for s in knowledge.strategies if s.avg_effectiveness > 0.3]
        if strong_strategies:
            recs.append(f"Top strategy: {strong_strategies[0].strategy_name}")

        if risk_level == "high":
            recs.append("HIGH RISK: Consider escalation or reduced spend")

        return recs

    # ── Confidence ──────────────────────────────────────────────

    def _compute_prediction_confidence(
        self,
        best_pattern: LearnedPattern,
        scored: list[tuple[LearnedPattern, float]],
        context: dict[str, Any],
        knowledge: LearningKnowledge,
    ) -> float:
        """计算预测整体置信度."""
        # 模式置信度
        pattern_conf = best_pattern.confidence

        # 样本充足度
        sample_factor = 1.0 - math.exp(-best_pattern.sample_count / 15.0)

        # 上下文匹配度
        context_match = self._compute_context_match(context, knowledge)

        # 知识质量
        knowledge_conf = knowledge.confidence

        # 风险折扣
        risk_discount = 0.0
        high_risks = sum(1 for r in knowledge.warnings if r.risk_level in ("high", "critical"))
        if high_risks > 0:
            risk_discount = min(0.3, high_risks * 0.1)

        confidence = (
            pattern_conf * 0.35
            + sample_factor * 0.20
            + context_match * 0.20
            + knowledge_conf * 0.15
            + (1.0 - risk_discount) * 0.10
        )

        return round(min(0.95, max(0.0, confidence)), 4)


__all__ = [
    "PatternPredictor",
]