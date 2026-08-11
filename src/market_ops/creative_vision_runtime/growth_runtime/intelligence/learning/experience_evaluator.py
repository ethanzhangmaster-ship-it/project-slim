"""E15.3.5 Experience Evaluator — 经验质量评估.

评估每条经验的学习价值，过滤低质量经验。

评估维度:
  - Impact:     执行结果的影响力
  - Confidence: 结果的置信度
  - Novelty:    经验的新颖度
  - Reliability:数据可靠性

公式:
  Learning Value = Impact × 0.35 + Confidence × 0.30 + Novelty × 0.20 + Reliability × 0.15

用法:
    evaluator = ExperienceEvaluator()
    quality = evaluator.evaluate(experience)
    valuable = evaluator.filter_valuable(experiences)
"""

from __future__ import annotations

from typing import Any

from .models import (
    ExperienceQuality,
    ExperienceQualityLevel,
    LearningExperience,
)


# ═══════════════════════════════════════════════════════════════
# Experience Evaluator
# ═══════════════════════════════════════════════════════════════


class ExperienceEvaluator:
    """E15.3.5 经验评估器 — 评估经验质量.

    用法:
        evaluator = ExperienceEvaluator()
        quality = evaluator.evaluate(experience)
        valuable = evaluator.filter_valuable(experiences)
    """

    def __init__(
        self,
        impact_weight: float = 0.35,
        confidence_weight: float = 0.30,
        novelty_weight: float = 0.20,
        reliability_weight: float = 0.15,
        min_learning_value: float = 0.30,
    ):
        self._impact_weight = impact_weight
        self._confidence_weight = confidence_weight
        self._novelty_weight = novelty_weight
        self._reliability_weight = reliability_weight
        self._min_learning_value = min_learning_value
        self._evaluation_count: int = 0
        self._seen_contexts: list[dict[str, Any]] = []

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    # ── Evaluate ────────────────────────────────────────────────

    def evaluate(self, experience: LearningExperience) -> ExperienceQuality:
        """评估单条经验的质量.

        Args:
            experience: 学习经验

        Returns:
            ExperienceQuality
        """
        self._evaluation_count += 1

        # 1. 计算 Impact
        impact = self._calculate_impact(experience)

        # 2. 计算 Confidence
        confidence = self._calculate_confidence(experience)

        # 3. 计算 Novelty
        novelty = self._calculate_novelty(experience)

        # 4. 计算 Reliability
        reliability = self._calculate_reliability(experience)

        # 综合学习价值
        learning_value = (
            impact * self._impact_weight
            + confidence * self._confidence_weight
            + novelty * self._novelty_weight
            + reliability * self._reliability_weight
        )

        # 确定等级
        level = self._classify_level(learning_value)

        # 收集问题
        issues = self._detect_issues(impact, confidence, novelty, reliability)

        quality = ExperienceQuality(
            confidence=round(confidence, 4),
            reliability=round(reliability, 4),
            impact=round(impact, 4),
            novelty=round(novelty, 4),
            learning_value=round(learning_value, 4),
            level=level,
            issues=issues,
        )

        # 更新经验
        experience.quality = quality

        # 记录上下文
        if experience.context:
            self._seen_contexts.append(experience.context)

        return quality

    def evaluate_batch(
        self, experiences: list[LearningExperience]
    ) -> list[ExperienceQuality]:
        """批量评估."""
        return [self.evaluate(e) for e in experiences]

    # ── Impact ──────────────────────────────────────────────────

    def _calculate_impact(self, exp: LearningExperience) -> float:
        """计算影响力.

        因素:
          - 收益绝对值
          - 结果显著性
          - 是否有多个指标变化
        """
        impact = 0.0

        # 收益影响
        abs_reward = abs(exp.reward)
        if abs_reward >= 0.8:
            impact += 0.4
        elif abs_reward >= 0.5:
            impact += 0.3
        elif abs_reward >= 0.2:
            impact += 0.2
        else:
            impact += 0.1

        # 结果多样性
        result = exp.result
        if result:
            key_count = len([k for k, v in result.items() if isinstance(v, (int, float)) and abs(v) > 0])
            if key_count >= 3:
                impact += 0.3
            elif key_count >= 1:
                impact += 0.2

        # 决策置信度
        decision = exp.decision
        if decision:
            dec_confidence = decision.get("confidence", 0.0)
            if dec_confidence >= 0.8:
                impact += 0.3
            elif dec_confidence >= 0.6:
                impact += 0.2
            else:
                impact += 0.1

        return min(1.0, impact)

    # ── Confidence ──────────────────────────────────────────────

    def _calculate_confidence(self, exp: LearningExperience) -> float:
        """计算置信度.

        因素:
          - 决策置信度
          - 是否有足够证据
          - 结果是否清晰
        """
        confidence = 0.3  # 基础置信度

        # 决策置信度
        decision = exp.decision
        if decision:
            dec_conf = decision.get("confidence", 0.0)
            confidence += dec_conf * 0.4

        # 收益明确性
        if abs(exp.reward) >= 0.5:
            confidence += 0.2
        elif abs(exp.reward) >= 0.2:
            confidence += 0.1

        # 上下文完整性
        context = exp.context
        if context and len(context) >= 3:
            confidence += 0.1

        return min(1.0, confidence)

    # ── Novelty ─────────────────────────────────────────────────

    def _calculate_novelty(self, exp: LearningExperience) -> float:
        """计算新颖度.

        因素:
          - 上下文是否新颖
          - 动作是否罕见
        """
        novelty = 0.5  # 基础新颖度

        context = exp.context
        if not context or not self._seen_contexts:
            return novelty

        # 检查上下文相似度
        similar_count = 0
        for seen_ctx in self._seen_contexts[-100:]:
            similarity = self._context_similarity(context, seen_ctx)
            if similarity > 0.7:
                similar_count += 1

        if similar_count == 0:
            novelty += 0.4  # 完全新颖
        elif similar_count < 5:
            novelty += 0.2
        elif similar_count < 10:
            novelty += 0.1
        else:
            novelty -= 0.3  # 常见场景

        return max(0.0, min(1.0, novelty))

    def _context_similarity(
        self, ctx1: dict[str, Any], ctx2: dict[str, Any]
    ) -> float:
        """计算上下文相似度."""
        if not ctx1 or not ctx2:
            return 0.0
        shared_keys = set(ctx1.keys()) & set(ctx2.keys())
        if not shared_keys:
            return 0.0
        matches = sum(1 for k in shared_keys if ctx1.get(k) == ctx2.get(k))
        return matches / len(shared_keys)

    # ── Reliability ─────────────────────────────────────────────

    def _calculate_reliability(self, exp: LearningExperience) -> float:
        """计算可靠性.

        因素:
          - 上下文完整性
          - 结果一致性
          - 是否有异常值
        """
        reliability = 0.5

        # 上下文完整性
        context = exp.context
        if context and len(context) >= 5:
            reliability += 0.2
        elif context and len(context) >= 3:
            reliability += 0.1

        # 结果一致性
        result = exp.result
        if result:
            has_contradiction = self._check_contradiction(result)
            if not has_contradiction:
                reliability += 0.2

        # 标签完整性
        if exp.tags and len(exp.tags) >= 2:
            reliability += 0.1

        return min(1.0, reliability)

    def _check_contradiction(self, result: dict[str, Any]) -> bool:
        """检查结果是否有矛盾."""
        # 提取数值指标
        values = {}
        for k, v in result.items():
            if isinstance(v, str) and v.endswith("%"):
                try:
                    values[k] = float(v[:-1]) / 100
                except ValueError:
                    pass
            elif isinstance(v, (int, float)):
                values[k] = float(v)

        if len(values) < 2:
            return False

        # 检查是否有反向指标 (如 CPI 下降但 ROAS 也下降)
        # 简化版: 检查是否有正负混合
        pos = sum(1 for v in values.values() if v > 0)
        neg = sum(1 for v in values.values() if v < 0)
        return pos > 0 and neg > 0 and pos + neg > 2

    # ── Classify ────────────────────────────────────────────────

    def _classify_level(self, learning_value: float) -> ExperienceQualityLevel:
        """分类质量等级."""
        if learning_value >= 0.70:
            return ExperienceQualityLevel.HIGH
        elif learning_value >= 0.40:
            return ExperienceQualityLevel.MEDIUM
        elif learning_value >= self._min_learning_value:
            return ExperienceQualityLevel.LOW
        return ExperienceQualityLevel.NOISE

    def _detect_issues(
        self,
        impact: float,
        confidence: float,
        novelty: float,
        reliability: float,
    ) -> list[str]:
        """检测质量问题."""
        issues = []
        if impact < 0.3:
            issues.append("low_impact")
        if confidence < 0.3:
            issues.append("low_confidence")
        if novelty < 0.2:
            issues.append("low_novelty")
        if reliability < 0.3:
            issues.append("low_reliability")
        return issues

    # ── Filter ──────────────────────────────────────────────────

    def filter_valuable(
        self, experiences: list[LearningExperience]
    ) -> list[LearningExperience]:
        """过滤有价值的经验."""
        return [e for e in experiences if e.is_valuable()]

    def filter_by_level(
        self,
        experiences: list[LearningExperience],
        min_level: ExperienceQualityLevel = ExperienceQualityLevel.MEDIUM,
    ) -> list[LearningExperience]:
        """按质量等级过滤."""
        return [
            e for e in experiences
            if e.quality and e.quality.level.value >= min_level.value
        ]

    # ── Stats ───────────────────────────────────────────────────

    def get_quality_distribution(
        self, experiences: list[LearningExperience]
    ) -> dict[str, int]:
        """获取质量分布."""
        dist = {level.value: 0 for level in ExperienceQualityLevel}
        for e in experiences:
            if e.quality:
                dist[e.quality.level.value] += 1
            else:
                dist["unrated"] = dist.get("unrated", 0) + 1
        return dist

    def get_summary(self) -> dict[str, Any]:
        return {
            "evaluation_count": self._evaluation_count,
            "weights": {
                "impact": self._impact_weight,
                "confidence": self._confidence_weight,
                "novelty": self._novelty_weight,
                "reliability": self._reliability_weight,
            },
            "min_learning_value": self._min_learning_value,
        }

    def reset(self) -> None:
        self._evaluation_count = 0
        self._seen_contexts.clear()


__all__ = ["ExperienceEvaluator"]