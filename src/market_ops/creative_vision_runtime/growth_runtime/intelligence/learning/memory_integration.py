"""E13.7.5 Learning Memory Integration — 学习记忆整合器.

Day 7.4.5:
  将 LearningExperience + LearningReward + AttributionResult 写入
  ExperienceStore / PatternStore / DecisionMemory，形成完整的
  Observe → Decide → Execute → Measure → Attribute → Learn → Improve 闭环。

核心流程:
  LearningExperience
        +
  LearningReward
        +
  AttributionResult
        |
        v
  LearningMemoryIntegrator
        |
        +--> ExperienceStore      (store_learning_experience)
        |
        +--> PatternStore         (update_patterns)
        |
        +--> DecisionMemory       (update_decision_memory)
        |
        v
  LearningResult                 (lessons + recommendations + next_action)

设计原则:
  - 不修改 ExperienceStore / PatternStore / DecisionMemory 接口
  - 作为桥接层，将新模型 (Day 7.4.3/4) 转换为现有存储模型
  - 返回 LearningResult 标记各存储是否更新成功
  - 支持 retrieve_similar 跨三个 Memory 检索相似经验
"""

from __future__ import annotations

import time
from typing import Any

from .models.learning_models import (
    AttributionResult,
    LearningExperience,
    LearningResult,
    LearningReward,
)


# ═══════════════════════════════════════════════════════════════
# LearningMemoryIntegrator
# ═══════════════════════════════════════════════════════════════


class LearningMemoryIntegrator:
    """学习记忆整合器 — 将学习结果写入三个 Memory 系统.

    用法:
        integrator = LearningMemoryIntegrator(
            experience_store=exp_store,
            pattern_store=pat_store,
            decision_memory=dec_memory,
        )
        result = integrator.integrate(experience, reward, attribution)

        # 也支持延迟注入 Memory 引用
        integrator = LearningMemoryIntegrator()
        integrator.set_experience_store(exp_store)
        result = integrator.integrate(experience, reward, attribution)
    """

    def __init__(
        self,
        experience_store: Any = None,
        pattern_store: Any = None,
        decision_memory: Any = None,
    ) -> None:
        """初始化整合器.

        Args:
            experience_store: ExperienceStore 实例 (可选)
            pattern_store: PatternStore 实例 (可选)
            decision_memory: DecisionMemory 实例 (可选)
        """
        self._experience_store = experience_store
        self._pattern_store = pattern_store
        self._decision_memory = decision_memory

    # ── Setter ───────────────────────────────────────────────

    def set_experience_store(self, store: Any) -> None:
        """设置 ExperienceStore."""
        self._experience_store = store

    def set_pattern_store(self, store: Any) -> None:
        """设置 PatternStore."""
        self._pattern_store = store

    def set_decision_memory(self, memory: Any) -> None:
        """设置 DecisionMemory."""
        self._decision_memory = memory

    # ── Public API ───────────────────────────────────────────

    def integrate(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> LearningResult:
        """统一入口 — 将学习结果写入所有 Memory.

        Args:
            experience: 学习经验
            reward: 奖励信号
            attribution: 归因结果

        Returns:
            LearningResult: 标记各 Memory 更新状态 + lessons + recommendations
        """
        start = time.perf_counter()

        # ── 1. 写入 ExperienceStore ──
        experience_stored = self._store_learning_experience(experience, reward, attribution)

        # ── 2. 更新 PatternStore ──
        pattern_updated = self._update_patterns(experience, reward, attribution)

        # ── 3. 更新 DecisionMemory ──
        memory_updated = self._update_decision_memory(experience, reward, attribution)

        # ── 4. 生成 lessons ──
        lessons = self._generate_lessons(experience, reward, attribution)

        # ── 5. 生成 recommendations ──
        recommendations = self._generate_recommendations(experience, reward, attribution)

        # ── 6. 判定 next_action ──
        next_action = self._determine_next_action(reward, attribution)

        # ── 7. 计算 learning_quality ──
        learning_quality = self._compute_learning_quality(
            experience_stored, pattern_updated, memory_updated, reward
        )

        # ── 8. pattern_impact ──
        pattern_impact = self._build_pattern_impact(attribution, pattern_updated)

        elapsed = (time.perf_counter() - start) * 1000

        return LearningResult(
            learning_id=experience.learning_id,
            decision_id=experience.decision_id,
            memory_updated=memory_updated,
            experience_stored=experience_stored,
            pattern_updated=pattern_updated,
            evolution_triggered=False,
            consolidation_triggered=False,
            lessons=lessons,
            recommendations=recommendations,
            next_action=next_action,
            pattern_impact=pattern_impact,
            learning_quality=round(learning_quality, 4),
            cycle_duration_ms=round(elapsed, 2),
            metadata={
                "integration_source": "learning_memory_integrator",
                "primary_factor": attribution.primary_factor,
                "reward_level": reward.reward_level,
            },
        )

    def store_learning(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> LearningResult:
        """store_learning — integrate 的别名."""
        return self.integrate(experience, reward, attribution)

    def retrieve_similar(
        self,
        context: dict[str, Any] | None = None,
        action_type: str = "",
        limit: int = 10,
    ) -> dict[str, Any]:
        """跨三个 Memory 检索相似经验.

        Args:
            context: 搜索上下文 (opportunity_type, action_type, audience_segment 等)
            action_type: 动作类型
            limit: 各 Memory 返回数量上限

        Returns:
            dict: {
                "experiences": list[dict],
                "patterns": list[dict],
                "decisions": list[dict],
            }
        """
        ctx = context or {}

        result: dict[str, Any] = {
            "experiences": [],
            "patterns": [],
            "decisions": [],
        }

        # ── ExperienceStore ──
        if self._experience_store is not None:
            try:
                exps = self._experience_store.get_by_action_type(
                    action_type or ctx.get("action_type", ""),
                    limit=limit,
                )
                result["experiences"] = [
                    {
                        "experience_id": e.experience_id,
                        "action_type": e.action_type,
                        "reward": e.reward,
                        "confidence": e.confidence,
                        "timestamp": e.timestamp,
                    }
                    for e in exps
                ]
            except Exception:
                pass

        # ── PatternStore ──
        if self._pattern_store is not None:
            try:
                patterns = self._pattern_store.get_by_action_type(
                    action_type or ctx.get("action_type", ""),
                    limit=limit,
                )
                result["patterns"] = [
                    {
                        "pattern_id": p.pattern_id,
                        "dimension": p.dimension.value if hasattr(p.dimension, "value") else str(p.dimension),
                        "score": p.score,
                        "confidence": p.confidence,
                        "success_rate": p.performance.success_rate,
                    }
                    for p in patterns
                ]
            except Exception:
                pass

        # ── DecisionMemory ──
        if self._decision_memory is not None:
            try:
                decisions = self._decision_memory.find_similar(
                    opportunity_type=ctx.get("opportunity_type", ""),
                    limit=limit,
                )
                result["decisions"] = [
                    {
                        "experience_id": d.experience_id,
                        "decision_id": d.decision_id,
                        "strategy_name": d.strategy_name,
                        "result": d.result,
                        "confidence": d.confidence,
                        "created_at": d.created_at,
                    }
                    for d in decisions
                ]
            except Exception:
                pass

        return result

    # ── Private: Store ───────────────────────────────────────

    def _store_learning_experience(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> bool:
        """将 LearningExperience 转换为 GrowthExperience 写入 ExperienceStore."""
        if self._experience_store is None:
            return False

        try:
            # 构建 GrowthExperience
            # 将 reward [-1,1] 映射到 [0,1]
            normalized_reward = (reward.total_reward + 1.0) / 2.0

            grobject = _build_growth_experience(
                experience=experience,
                normalized_reward=round(normalized_reward, 4),
                confidence=reward.confidence,
                attribution=attribution,
            )
            self._experience_store.store(grobject)
            return True
        except Exception:
            return False

    def _update_patterns(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> bool:
        """根据 Attribution 更新 PatternStore 中的相关模式."""
        if self._pattern_store is None:
            return False

        try:
            pattern = _build_pattern_memory(
                experience=experience,
                reward=reward,
                attribution=attribution,
            )
            self._pattern_store.store(pattern)
            return True
        except Exception:
            return False

    def _update_decision_memory(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> bool:
        """将决策结果写入 DecisionMemory."""
        if self._decision_memory is None:
            return False

        try:
            # 查找已有决策记录
            existing = self._decision_memory.get_by_decision(experience.decision_id)
            if existing is not None:
                # 更新结果
                result_str = "success" if reward.total_reward > 0.15 else (
                    "failure" if reward.total_reward < -0.15 else "partial"
                )
                metrics = {
                    "total_reward": reward.total_reward,
                    "business_reward": reward.business_reward,
                    "execution_reward": reward.execution_reward,
                    "safety_reward": reward.safety_reward,
                    "efficiency_reward": reward.efficiency_reward,
                    "primary_factor": attribution.primary_factor,
                    "creative_contribution": attribution.creative_contribution,
                    "strategy_contribution": attribution.strategy_contribution,
                }
                self._decision_memory.record_outcome(
                    experience.decision_id,
                    result_str,
                    metrics,
                    reason=f"Primary factor: {attribution.primary_factor}",
                )
            return True
        except Exception:
            return False

    # ── Private: Lessons & Recommendations ───────────────────

    def _generate_lessons(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> list[str]:
        """从 reward + attribution 生成经验教训."""
        lessons: list[str] = []

        # 成功/失败基准
        if reward.total_reward > 0.5:
            lessons.append(
                f"Strategy '{experience.strategy_name}' was highly effective "
                f"(total_reward={reward.total_reward:+.2f})"
            )
        elif reward.total_reward > 0.15:
            lessons.append(
                f"Strategy '{experience.strategy_name}' showed moderate positive results "
                f"(total_reward={reward.total_reward:+.2f})"
            )
        elif reward.total_reward >= -0.15:
            lessons.append(
                f"Strategy '{experience.strategy_name}' had neutral impact "
                f"(total_reward={reward.total_reward:+.2f})"
            )
        elif reward.total_reward >= -0.5:
            lessons.append(
                f"Strategy '{experience.strategy_name}' needs adjustment "
                f"(total_reward={reward.total_reward:+.2f})"
            )
        else:
            lessons.append(
                f"Strategy '{experience.strategy_name}' should be abandoned "
                f"(total_reward={reward.total_reward:+.2f})"
            )

        # 归因洞察
        if attribution.primary_factor == "creative":
            lessons.append(
                f"Creative was the primary driver "
                f"(contribution={attribution.creative_contribution:+.2f})"
            )
        elif attribution.primary_factor == "strategy":
            lessons.append(
                f"Strategy selection was the primary driver "
                f"(contribution={attribution.strategy_contribution:+.2f})"
            )
        elif attribution.primary_factor == "audience":
            lessons.append(
                f"Audience targeting was the primary driver "
                f"(contribution={attribution.audience_contribution:+.2f})"
            )
        elif attribution.primary_factor == "timing":
            lessons.append(
                f"Market timing was the primary driver "
                f"(contribution={attribution.timing_contribution:+.2f})"
            )

        # 安全洞察
        if reward.safety_reward < 0:
            lessons.append(
                f"Safety concern detected (safety_reward={reward.safety_reward:+.2f})"
            )

        # 效率洞察
        if reward.efficiency_reward < 0:
            lessons.append(
                f"Efficiency issue (efficiency_reward={reward.efficiency_reward:+.2f})"
            )

        return lessons

    def _generate_recommendations(
        self,
        experience: LearningExperience,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> list[str]:
        """从 reward + attribution 生成改进建议."""
        recommendations: list[str] = []

        if reward.total_reward > 0.5:
            recommendations.append(
                f"Reinforce strategy '{experience.strategy_name}' — "
                f"scale up with confidence"
            )
        elif reward.total_reward > 0.15:
            recommendations.append(
                f"Continue strategy '{experience.strategy_name}' with minor adjustments"
            )
        elif reward.total_reward >= -0.15:
            recommendations.append(
                f"Observe strategy '{experience.strategy_name}' — "
                f"collect more data before deciding"
            )
        elif reward.total_reward >= -0.5:
            recommendations.append(
                f"Adjust strategy '{experience.strategy_name}' — "
                f"focus on {attribution.primary_factor} optimization"
            )
        else:
            recommendations.append(
                f"Abandon strategy '{experience.strategy_name}' — "
                f"negative results across all dimensions"
            )

        # 具体维度建议
        if attribution.creative_contribution < 0:
            recommendations.append(
                "Improve creative quality — CTR/CVR underperforming"
            )
        if attribution.strategy_contribution < 0:
            recommendations.append(
                "Re-evaluate strategy logic — low historical success rate"
            )
        if attribution.audience_contribution < 0:
            recommendations.append(
                "Refine audience targeting — low audience match"
            )
        if attribution.timing_contribution < 0:
            recommendations.append(
                "Optimize launch timing — poor market window"
            )

        return recommendations

    def _determine_next_action(
        self,
        reward: LearningReward,
        attribution: AttributionResult,
    ) -> str:
        """根据 reward 判定下一步动作."""
        if reward.total_reward > 0.5:
            return "reinforce"
        elif reward.total_reward > 0.15:
            return "adjust"
        elif reward.total_reward >= -0.15:
            return "observe"
        elif reward.total_reward >= -0.5:
            return "adjust"
        else:
            return "abandon"

    def _compute_learning_quality(
        self,
        experience_stored: bool,
        pattern_updated: bool,
        memory_updated: bool,
        reward: LearningReward,
    ) -> float:
        """计算学习质量评分.

        基于:
          - Memory 写入成功率 (每个占 0.2)
          - Reward 置信度 (占 0.4)
        """
        storage_score = (
            (0.2 if experience_stored else 0.0)
            + (0.2 if pattern_updated else 0.0)
            + (0.2 if memory_updated else 0.0)
        )
        confidence_score = reward.confidence * 0.4
        return storage_score + confidence_score

    def _build_pattern_impact(
        self,
        attribution: AttributionResult,
        pattern_updated: bool,
    ) -> dict[str, Any]:
        """构建 Pattern 影响描述."""
        return {
            "pattern_updated": pattern_updated,
            "primary_factor": attribution.primary_factor,
            "creative_contribution": attribution.creative_contribution,
            "strategy_contribution": attribution.strategy_contribution,
            "audience_contribution": attribution.audience_contribution,
            "timing_contribution": attribution.timing_contribution,
            "attribution_confidence": attribution.confidence,
        }


# ═══════════════════════════════════════════════════════════════
# Bridge Helpers — 将新模型转换为现有存储模型
# ═══════════════════════════════════════════════════════════════


def _build_growth_experience(
    experience: LearningExperience,
    normalized_reward: float,
    confidence: float,
    attribution: AttributionResult,
) -> Any:
    """将 LearningExperience 转换为 GrowthExperience.

    动态导入避免循环依赖。
    """
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        ExperienceCategory,
        ExperienceContext,
        ExperienceOutcome,
        GrowthExperience,
    )

    outcome_level = _map_outcome_level(experience)
    is_success = experience.outcome.is_successful

    return GrowthExperience(
        experience_id=experience.learning_id,
        context=ExperienceContext(
            opportunity_type=experience.context.get("opportunity_type", ""),
            entity_id=experience.context.get("entity_id", ""),
            product_id=experience.context.get("product_id", ""),
            date=experience.created_at[:10] if experience.created_at else "",
        ),
        action_id=experience.execution_id,
        action_type=experience.action_type,
        action_params={
            "decision_id": experience.decision_id,
            "strategy_name": experience.strategy_name,
            "primary_factor": attribution.primary_factor,
        },
        outcome=ExperienceOutcome(
            success=is_success,
            outcome_level=outcome_level,
            actual_reward=normalized_reward,
        ),
        reward=normalized_reward,
        confidence=confidence,
        category=_infer_experience_category(experience),
        tags=[
            experience.action_type,
            attribution.primary_factor,
            f"reward:{experience.reward.reward_level if experience.reward else 'none'}",
        ],
        metadata={
            "learning_id": experience.learning_id,
            "decision_id": experience.decision_id,
            "total_reward": experience.reward.total_reward if experience.reward else 0.0,
            "attribution_primary": attribution.primary_factor,
        },
    )


def _build_pattern_memory(
    experience: LearningExperience,
    reward: LearningReward,
    attribution: AttributionResult,
) -> Any:
    """将 LearningExperience + Reward + Attribution 转换为 PatternMemory."""
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        PatternAction,
        PatternCondition,
        PatternMemory,
        PatternMiningDimension,
        PatternPerformance,
        PatternQuality,
    )

    perf = PatternPerformance(
        samples=1,
        success_count=1 if reward.total_reward > 0 else 0,
        success_rate=1.0 if reward.total_reward > 0 else 0.0,
        avg_reward=round((reward.total_reward + 1.0) / 2.0, 4),
        quality=PatternQuality.STRONG if reward.total_reward > 0.3 else (
            PatternQuality.RELIABLE if reward.total_reward > -0.3 else PatternQuality.WEAK
        ),
    )

    condition = PatternCondition(
        opportunity_type=experience.context.get("opportunity_type", ""),
        action_type=experience.action_type,
        category="creative",
        audience_segment=experience.context.get("audience_segment", ""),
        signal_types=[],
        dna_genes={},
    )

    action = PatternAction(
        action_type=experience.action_type,
        params_template={
            "strategy_name": experience.strategy_name,
            "primary_factor": attribution.primary_factor,
        },
    )

    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        score=reward.confidence * perf.success_rate,
        confidence=reward.confidence,
        tags=[
            experience.action_type,
            attribution.primary_factor,
            reward.reward_level,
        ],
        source_experience_ids=[experience.learning_id],
        metadata={
            "decision_id": experience.decision_id,
            "business_reward": reward.business_reward,
            "creative_contribution": attribution.creative_contribution,
            "strategy_contribution": attribution.strategy_contribution,
        },
    )
    pattern.compute_score()
    return pattern


def _map_outcome_level(experience: LearningExperience) -> Any:
    """将 LearningExperience 映射到 ExperienceOutcomeLevel."""
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        ExperienceOutcomeLevel,
    )

    if experience.outcome.is_successful:
        improvement = experience.outcome.improvement_score
        if improvement > 0.3:
            return ExperienceOutcomeLevel.STRONG_SUCCESS
        return ExperienceOutcomeLevel.SUCCESS
    else:
        return ExperienceOutcomeLevel.FAILURE


def _infer_experience_category(experience: LearningExperience) -> Any:
    """从 action_type 推断经验类别."""
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        ExperienceCategory,
    )

    at = experience.action_type.lower()
    if "creative" in at or "asset" in at or "material" in at:
        return ExperienceCategory.CREATIVE
    if "audience" in at or "targeting" in at or "segment" in at:
        return ExperienceCategory.AUDIENCE
    if "budget" in at or "bid" in at or "spend" in at:
        return ExperienceCategory.BUDGET
    return ExperienceCategory.CREATIVE


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════


__all__ = [
    "LearningMemoryIntegrator",
]