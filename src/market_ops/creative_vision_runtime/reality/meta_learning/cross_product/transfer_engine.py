"""E12.6.4 — Transfer Engine。

知识迁移决策引擎。

判断是否应该将 source product 的成功模式迁移到 target product。

决策逻辑:
  1. 相似度检查 → 相似度 >= 0.50 才考虑迁移
  2. 置信度检查 → 模式置信度 >= 0.50
  3. 风险检查 → 低风险直接 ALLOW，中风险 MODIFY，高风险 DENY
  4. 生成突变策略建议
"""

from __future__ import annotations

from .models import (
    ProductProfile,
    SimilarityResult,
    TransferAction,
    TransferDecision,
    TransferRisk,
    UniversalPattern,
)


class TransferEngine:
    """知识迁移决策引擎。

    判断是否迁移成功模式到目标产品。
    """

    # 阈值
    SIMILARITY_THRESHOLD = 0.50
    CONFIDENCE_THRESHOLD = 0.50
    HIGH_SIMILARITY = 0.70
    LOW_RISK_SIMILARITY = 0.80

    def __init__(
        self,
        similarity_threshold: float | None = None,
        confidence_threshold: float | None = None,
    ) -> None:
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.SIMILARITY_THRESHOLD
        )
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self.CONFIDENCE_THRESHOLD
        )

    def evaluate(
        self,
        similarity: SimilarityResult,
        pattern: UniversalPattern,
        source_profile: ProductProfile | None = None,
        target_profile: ProductProfile | None = None,
    ) -> TransferDecision:
        """评估是否应该迁移知识。

        Args:
            similarity:      产品相似度
            pattern:         通用模式
            source_profile:  来源产品画像
            target_profile:  目标产品画像

        Returns:
            TransferDecision
        """
        reasons: list[str] = []

        # 1. 相似度检查
        if similarity.total_similarity < self.similarity_threshold:
            reasons.append(
                f"Similarity too low: {similarity.total_similarity:.2f} "
                f"< threshold {self.similarity_threshold}"
            )
            return TransferDecision(
                source_product=similarity.source_product,
                target_product=similarity.target_product,
                pattern_id=pattern.pattern_id,
                action=TransferAction.DENY,
                confidence=similarity.total_similarity,
                risk_level=TransferRisk.HIGH,
                similarity_score=similarity.total_similarity,
                mutation_strategy="no_transfer",
                reasons=reasons,
            )

        # 2. 置信度检查
        if pattern.confidence < self.confidence_threshold:
            reasons.append(
                f"Pattern confidence too low: {pattern.confidence:.2f} "
                f"< threshold {self.confidence_threshold}"
            )
            return TransferDecision(
                source_product=similarity.source_product,
                target_product=similarity.target_product,
                pattern_id=pattern.pattern_id,
                action=TransferAction.DENY,
                confidence=pattern.confidence,
                risk_level=TransferRisk.MEDIUM,
                similarity_score=similarity.total_similarity,
                mutation_strategy="no_transfer",
                reasons=reasons,
            )

        # 3. 确定风险等级
        risk_level = self._determine_risk(similarity, pattern)

        # 4. 确定动作
        if risk_level == TransferRisk.HIGH:
            action = TransferAction.DENY
            reasons.append(
                f"High transfer risk: similarity={similarity.total_similarity:.2f}, "
                f"pattern confidence={pattern.confidence:.2f}"
            )
        elif risk_level == TransferRisk.MEDIUM:
            action = TransferAction.MODIFY
            reasons.append(
                f"Medium transfer risk: modifying strategy for safe transfer"
            )
        else:
            action = TransferAction.ALLOW
            reasons.append(
                f"Low transfer risk: similarity={similarity.total_similarity:.2f}, "
                f"pattern confidence={pattern.confidence:.2f}"
            )

        # 5. 生成突变策略
        mutation_strategy = self._generate_strategy(
            similarity, pattern, action
        )

        # 6. 计算预期提升
        expected_uplift = self._estimate_uplift(
            similarity.total_similarity, pattern.performance_gain, pattern.confidence
        )

        # 7. 计算决策置信度
        decision_confidence = (
            similarity.total_similarity * 0.50
            + pattern.confidence * 0.50
        )

        return TransferDecision(
            source_product=similarity.source_product,
            target_product=similarity.target_product,
            pattern_id=pattern.pattern_id,
            action=action,
            confidence=round(decision_confidence, 4),
            risk_level=risk_level,
            similarity_score=similarity.total_similarity,
            expected_uplift=round(expected_uplift, 4),
            mutation_strategy=mutation_strategy,
            reasons=reasons,
        )

    def _determine_risk(
        self,
        similarity: SimilarityResult,
        pattern: UniversalPattern,
    ) -> TransferRisk:
        """确定转移风险等级。

        风险判断:
          - 高相似度 (>0.80) + 高置信度 (>0.70) → LOW
          - 中相似度 (0.50-0.80) → MEDIUM
          - 低相似度 → HIGH
        """
        if similarity.total_similarity >= self.LOW_RISK_SIMILARITY and pattern.confidence >= 0.70:
            return TransferRisk.LOW
        elif similarity.total_similarity >= self.HIGH_SIMILARITY:
            return TransferRisk.MEDIUM
        else:
            return TransferRisk.MEDIUM

    def _generate_strategy(
        self,
        similarity: SimilarityResult,
        pattern: UniversalPattern,
        action: TransferAction,
    ) -> str:
        """生成突变策略建议。

        根据相似度和动作生成具体策略。
        """
        if action == TransferAction.DENY:
            return "no_transfer"

        if similarity.total_similarity >= 0.90:
            return "direct_copy"
        elif similarity.total_similarity >= 0.80:
            return "replace_character_only"
        elif similarity.dna_similarity >= 0.60:
            return "adapt_to_genre"
        else:
            return "adapt_with_modification"

    def _estimate_uplift(
        self,
        similarity: float,
        pattern_gain: float,
        pattern_confidence: float,
    ) -> float:
        """估算预期性能提升。

        公式: uplift = pattern_gain × similarity × confidence × discount_factor

        discount_factor = 0.7（跨产品迁移通常有折扣）
        """
        discount = 0.70
        return pattern_gain * similarity * pattern_confidence * discount

    def evaluate_batch(
        self,
        similarity_results: list[SimilarityResult],
        pattern: UniversalPattern,
        source_profiles: dict[str, ProductProfile] | None = None,
        target_profiles: dict[str, ProductProfile] | None = None,
    ) -> list[TransferDecision]:
        """批量评估多个目标产品的迁移决策。

        Args:
            similarity_results: 相似度结果列表
            pattern:            通用模式
            source_profiles:    来源产品画像字典
            target_profiles:    目标产品画像字典

        Returns:
            TransferDecision 列表
        """
        decisions: list[TransferDecision] = []
        for sim in similarity_results:
            src = source_profiles.get(sim.source_product) if source_profiles else None
            tgt = target_profiles.get(sim.target_product) if target_profiles else None
            decision = self.evaluate(sim, pattern, src, tgt)
            decisions.append(decision)
        return decisions

    def is_transferable(
        self,
        similarity: SimilarityResult,
        pattern: UniversalPattern,
    ) -> bool:
        """快速判断是否可迁移。"""
        return (
            similarity.total_similarity >= self.similarity_threshold
            and pattern.confidence >= self.confidence_threshold
        )

    def __repr__(self) -> str:
        return (
            f"TransferEngine(sim_threshold={self.similarity_threshold}, "
            f"conf_threshold={self.confidence_threshold})"
        )