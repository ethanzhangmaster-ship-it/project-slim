"""E15.3.5 Continuous Learning Engine — 持续学习核心引擎.

整合经验收集、评估、知识提取、模式进化和策略学习的完整流程。

流程:
    1. 收集经验 (ExperienceCollector)
    2. 评估质量 (ExperienceEvaluator)
    3. 提取知识 (KnowledgeExtractor)
    4. 进化模式 (PatternEvolutionEngine)
    5. 学习策略 (StrategyLearner)
    6. 生成反馈 (Model Improvement Feedback)

连接:
    - E15.1.5 Memory Feedback Bridge → ExperienceCollector
    - E13.4 Pattern Memory       → PatternEvolutionEngine
    - E15.3.4 Self Optimization  → StrategyLearner
    - E15.2 Reasoning Layer      → Model Improvement Feedback

用法:
    engine = ContinuousLearningEngine()
    engine.collect(action="creative_refresh", context={...}, result={...}, reward=0.74)
    result = engine.process()
    feedback = engine.generate_model_feedback()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .experience_collector import ExperienceCollector
from .experience_evaluator import ExperienceEvaluator
from .knowledge_extractor import KnowledgeExtractor
from .models import (
    ExperienceQualityLevel,
    InsightType,
    LearningInsight,
    LearningResult,
    PatternStatus,
    StrategyRecommendation,
)
from .pattern_evolution import PatternEvolutionEngine
from .strategy_learner import StrategyLearner


# ═══════════════════════════════════════════════════════════════
# Model Improvement Feedback
# ═══════════════════════════════════════════════════════════════


class ModelImprovementFeedback:
    """模型改进反馈 — 回传给各子系统的改进建议.

    反馈给:
      - Planner:         规划生成优化
      - RiskEngine:      风险预测优化
      - ActionSelector:  动作评分权重优化
      - ReasoningEngine: 假设排序优化
    """

    def __init__(self):
        self._planner_feedback: list[dict[str, Any]] = []
        self._risk_engine_feedback: list[dict[str, Any]] = []
        self._action_selector_feedback: list[dict[str, Any]] = []
        self._reasoning_engine_feedback: list[dict[str, Any]] = []

    def add_planner_feedback(
        self, insight: dict[str, Any], weight: float = 1.0
    ) -> None:
        self._planner_feedback.append({"insight": insight, "weight": weight})

    def add_risk_engine_feedback(
        self, insight: dict[str, Any], weight: float = 1.0
    ) -> None:
        self._risk_engine_feedback.append({"insight": insight, "weight": weight})

    def add_action_selector_feedback(
        self, insight: dict[str, Any], weight: float = 1.0
    ) -> None:
        self._action_selector_feedback.append({"insight": insight, "weight": weight})

    def add_reasoning_engine_feedback(
        self, insight: dict[str, Any], weight: float = 1.0
    ) -> None:
        self._reasoning_engine_feedback.append({"insight": insight, "weight": weight})

    def get_planner_feedback(self) -> list[dict[str, Any]]:
        return list(self._planner_feedback)

    def get_risk_engine_feedback(self) -> list[dict[str, Any]]:
        return list(self._risk_engine_feedback)

    def get_action_selector_feedback(self) -> list[dict[str, Any]]:
        return list(self._action_selector_feedback)

    def get_reasoning_engine_feedback(self) -> list[dict[str, Any]]:
        return list(self._reasoning_engine_feedback)

    def to_dict(self) -> dict[str, Any]:
        return {
            "planner": list(self._planner_feedback),
            "risk_engine": list(self._risk_engine_feedback),
            "action_selector": list(self._action_selector_feedback),
            "reasoning_engine": list(self._reasoning_engine_feedback),
        }

    def clear(self) -> None:
        self._planner_feedback.clear()
        self._risk_engine_feedback.clear()
        self._action_selector_feedback.clear()
        self._reasoning_engine_feedback.clear()


# ═══════════════════════════════════════════════════════════════
# Continuous Learning Engine
# ═══════════════════════════════════════════════════════════════


class ContinuousLearningEngine:
    """E15.3.5 持续学习引擎 — 自治闭环核心.

    整合所有学习组件，形成完整的持续学习流程。

    用法:
        engine = ContinuousLearningEngine()

        # 步骤 1: 收集经验
        engine.collect(action="creative_refresh", context={...}, result={...}, reward=0.74)

        # 步骤 2: 执行学习周期
        result = engine.process()

        # 步骤 3: 获取模型改进反馈
        feedback = engine.generate_model_feedback()
    """

    def __init__(
        self,
        max_experiences: int = 10000,
        min_evidence: int = 10,
        min_confidence: float = 0.50,
        min_learning_value: float = 0.30,
        impact_weight: float = 0.35,
        confidence_weight: float = 0.30,
        novelty_weight: float = 0.20,
        reliability_weight: float = 0.15,
        strategy_min_confidence: float = 0.60,
    ):
        # ── 组件初始化 ──
        self._collector = ExperienceCollector(max_experiences=max_experiences)
        self._evaluator = ExperienceEvaluator(
            impact_weight=impact_weight,
            confidence_weight=confidence_weight,
            novelty_weight=novelty_weight,
            reliability_weight=reliability_weight,
            min_learning_value=min_learning_value,
        )
        self._extractor = KnowledgeExtractor(
            min_evidence=min_evidence,
            min_confidence=min_confidence,
        )
        self._evolution = PatternEvolutionEngine()
        self._learner = StrategyLearner(min_confidence=strategy_min_confidence)

        # ── 状态追踪 ──
        self._cycle_count: int = 0
        self._results: list[LearningResult] = []
        self._model_feedback = ModelImprovementFeedback()

    # ── Properties ───────────────────────────────────────────────

    @property
    def collector(self) -> ExperienceCollector:
        return self._collector

    @property
    def evaluator(self) -> ExperienceEvaluator:
        return self._evaluator

    @property
    def extractor(self) -> KnowledgeExtractor:
        return self._extractor

    @property
    def evolution(self) -> PatternEvolutionEngine:
        return self._evolution

    @property
    def learner(self) -> StrategyLearner:
        return self._learner

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # ── Collect (Step 1) ────────────────────────────────────────

    def collect(
        self,
        action: str,
        context: dict[str, Any] | None = None,
        decision: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        reward: float = 0.0,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ):
        """收集一条执行经验.

        这是 E15.1.5 Memory Feedback Bridge 的入口。
        """
        return self._collector.collect(
            action=action,
            context=context,
            decision=decision,
            result=result,
            reward=reward,
            tags=tags,
            metadata=metadata,
            timestamp=timestamp,
        )

    def collect_from_feedback(self, feedback_data: dict[str, Any]):
        """从 Memory Feedback Bridge 收集经验."""
        return self._collector.collect_from_result(feedback_data)

    def collect_batch(self, feedback_list: list[dict[str, Any]]):
        """批量从反馈收集经验."""
        return self._collector.collect_batch(feedback_list)

    # ── Process (Step 2) ────────────────────────────────────────

    def process(self) -> LearningResult:
        """执行一次完整学习周期.

        Returns:
            LearningResult: 包含所有学习输出
        """
        self._cycle_count += 1

        # 1. 获取经验
        all_experiences = self._collector.get_experiences()

        # 2. 评估质量
        self._evaluator.evaluate_batch(all_experiences)
        valuable_experiences = self._evaluator.filter_valuable(all_experiences)

        # 3. 提取知识
        patterns = self._extractor.extract_patterns(valuable_experiences)
        insights = self._extractor.generate_insights(valuable_experiences)

        # 4. 注册并进化模式
        if patterns:
            self._evolution.register_batch(patterns)
        evolutions = self._evolution.evolve_all()

        # 5. 学习策略
        active_patterns = self._evolution.get_active_patterns()
        strategies = self._learner.learn(
            patterns=active_patterns,
            experiences=valuable_experiences,
        )

        # 6. 生成策略洞察
        strategy_insights = self._learner.generate_insights(strategies)
        all_insights = insights + strategy_insights

        # 7. 构建结果
        quality_dist = self._evaluator.get_quality_distribution(all_experiences)

        result = LearningResult(
            cycle_number=self._cycle_count,
            experiences_collected=len(all_experiences),
            experiences_evaluated=self._evaluator.evaluation_count,
            valuable_experiences=len(valuable_experiences),
            patterns_discovered=len(patterns),
            patterns_evolved=len(evolutions),
            insights=all_insights,
            strategy_recommendations=strategies,
            quality_distribution=quality_dist,
            summary=self._build_summary(
                all_experiences, valuable_experiences, patterns, evolutions, strategies
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self._results.append(result)
        return result

    def _build_summary(
        self,
        all_experiences,
        valuable_experiences,
        patterns,
        evolutions,
        strategies,
    ) -> str:
        """构建周期摘要."""
        parts = [
            f"Cycle #{self._cycle_count}",
            f"Experiences: {len(all_experiences)} collected, "
            f"{len(valuable_experiences)} valuable",
            f"Patterns: {len(patterns)} discovered, "
            f"{len(evolutions)} evolved",
            f"Active patterns: {len(self._evolution.get_active_patterns())}",
            f"Strategies: {len(strategies)} generated",
        ]
        return " | ".join(parts)

    # ── Model Feedback (Step 3) ─────────────────────────────────

    def generate_model_feedback(self) -> ModelImprovementFeedback:
        """生成模型改进反馈.

        基于最新的学习结果，为各子系统生成改进建议。

        Returns:
            ModelImprovementFeedback
        """
        self._model_feedback.clear()

        if not self._results:
            return self._model_feedback

        last_result = self._results[-1]

        # ── Planner Feedback ──
        self._generate_planner_feedback(last_result)

        # ── Risk Engine Feedback ──
        self._generate_risk_engine_feedback(last_result)

        # ── Action Selector Feedback ──
        self._generate_action_selector_feedback(last_result)

        # ── Reasoning Engine Feedback ──
        self._generate_reasoning_engine_feedback(last_result)

        return self._model_feedback

    def _generate_planner_feedback(self, result: LearningResult) -> None:
        """为 Planner 生成反馈."""
        # 从策略中提取规划建议
        for rec in result.strategy_recommendations:
            if rec.confidence >= 0.70:
                self._model_feedback.add_planner_feedback(
                    insight={
                        "type": "strategy_available",
                        "strategy": rec.strategy_name,
                        "action": rec.action,
                        "conditions": rec.conditions,
                        "expected_reward": rec.expected_reward,
                    },
                    weight=rec.confidence,
                )

        # 从洞察中提取规划建议
        for insight in result.insights:
            if "planner" in insight.affected_components:
                self._model_feedback.add_planner_feedback(
                    insight={
                        "type": "insight",
                        "description": insight.description,
                        "recommendations": insight.recommendations,
                    },
                    weight=insight.confidence,
                )

    def _generate_risk_engine_feedback(self, result: LearningResult) -> None:
        """为 Risk Engine 生成反馈."""
        # 从警告类洞察中提取风险信息
        for insight in result.insights:
            if insight.insight_type == InsightType.WARNING:
                self._model_feedback.add_risk_engine_feedback(
                    insight={
                        "type": "risk_warning",
                        "description": insight.description,
                        "recommendations": insight.recommendations,
                    },
                    weight=insight.confidence,
                )
            elif "risk_engine" in insight.affected_components:
                self._model_feedback.add_risk_engine_feedback(
                    insight={
                        "type": "risk_insight",
                        "description": insight.description,
                    },
                    weight=insight.confidence,
                )

        # 从衰减模式中提取风险
        decaying = self._evolution.get_by_status(PatternStatus.DECAYING)
        for pattern in decaying:
            self._model_feedback.add_risk_engine_feedback(
                insight={
                    "type": "pattern_decaying",
                    "pattern": pattern.name,
                    "success_rate": pattern.success_rate,
                    "decay_rate": pattern.decay_rate,
                },
                weight=0.7,
            )

    def _generate_action_selector_feedback(self, result: LearningResult) -> None:
        """为 Action Selector 生成反馈."""
        # 从策略中提取动作权重建议
        for rec in result.strategy_recommendations:
            if rec.action and rec.confidence >= 0.60:
                self._model_feedback.add_action_selector_feedback(
                    insight={
                        "type": "action_weight",
                        "action": rec.action,
                        "priority": rec.priority,
                        "expected_reward": rec.expected_reward,
                        "confidence": rec.confidence,
                    },
                    weight=rec.confidence,
                )

        # 从洞察中提取动作相关建议
        for insight in result.insights:
            if "action_selection" in insight.affected_components:
                self._model_feedback.add_action_selector_feedback(
                    insight={
                        "type": "action_insight",
                        "description": insight.description,
                        "recommendations": insight.recommendations,
                    },
                    weight=insight.confidence,
                )

    def _generate_reasoning_engine_feedback(self, result: LearningResult) -> None:
        """为 Reasoning Engine 生成反馈."""
        # 从洞察中提取假设排序建议
        for insight in result.insights:
            if insight.insight_type == InsightType.CORRELATION:
                self._model_feedback.add_reasoning_engine_feedback(
                    insight={
                        "type": "new_evidence_weight",
                        "description": insight.description,
                        "confidence": insight.confidence,
                    },
                    weight=insight.confidence,
                )

        # 从高质量模式中提取证据权重
        for pattern in self._evolution.get_active_patterns():
            if pattern.confidence >= 0.70:
                self._model_feedback.add_reasoning_engine_feedback(
                    insight={
                        "type": "hypothesis_ranking",
                        "pattern": pattern.name,
                        "success_rate": pattern.success_rate,
                        "evidence_count": pattern.evidence_count,
                    },
                    weight=pattern.confidence,
                )

    # ── Query ───────────────────────────────────────────────────

    def get_results(self) -> list[LearningResult]:
        return list(self._results)

    def get_latest_result(self) -> LearningResult | None:
        return self._results[-1] if self._results else None

    def get_stats(self) -> dict[str, Any]:
        """获取引擎统计."""
        return {
            "cycle_count": self._cycle_count,
            "collector": self._collector.get_stats(),
            "evaluator": self._evaluator.get_summary(),
            "extractor": self._extractor.get_summary(),
            "evolution": self._evolution.get_summary(),
            "learner": self._learner.get_summary(),
        }

    def get_summary(self) -> dict[str, Any]:
        """获取完整摘要."""
        stats = self.get_stats()
        latest = self.get_latest_result()
        return {
            **stats,
            "latest_result": latest.to_dict() if latest else None,
            "total_results": len(self._results),
            "model_feedback": self._model_feedback.to_dict(),
        }

    def reset(self) -> None:
        """重置引擎."""
        self._collector.reset()
        self._evaluator.reset()
        self._extractor.reset()
        self._evolution.reset()
        self._learner.reset()
        self._cycle_count = 0
        self._results.clear()
        self._model_feedback.clear()


__all__ = ["ContinuousLearningEngine", "ModelImprovementFeedback"]