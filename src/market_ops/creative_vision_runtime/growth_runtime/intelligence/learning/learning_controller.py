"""E13.7.5 Learning Loop Controller — 自主学习控制器.

Day 7.5.4:
  编排完整学习闭环: Knowledge Extraction → Pattern Prediction → Decision Enhancement → Memory Update.
  这是系统第一次拥有"自主学习控制器"。

核心流程:
  Context
      |
      v
  LearningLoopController.run_cycle()
      |
      +--> Step 1: retrieve_experiences()     → 从记忆系统检索经验
      |
      +--> Step 2: extract_knowledge()        → 提取结构化知识
      |
      +--> Step 3: predict_patterns()         → 预测最佳模式
      |
      +--> Step 4: enhance_decision()         → 增强决策
      |
      +--> Step 5: update_memory()            → 更新记忆
      |
      v
  LearningCycleResult (knowledge + prediction + decision_enhancement)

设计原则:
  - 编排层, 不实现具体算法
  - 每个步骤可选 (fail-safe: 某步骤失败不阻断整体)
  - 输出完整的循环结果报告
"""

from __future__ import annotations

import math
from typing import Any

from .decision_learning_enhancer import DecisionLearningEnhancer
from .learning_knowledge_extractor import LearningKnowledgeExtractor
from .memory_integration import LearningMemoryIntegrator
from .models.learning_models import (
    DecisionLearningResult,
    LearningCycleResult,
    LearningExperience,
    LearningKnowledge,
    LearningReward,
    PatternPrediction,
)


class LearningLoopController:
    """自主学习控制器 — 编排完整学习闭环.

    用法:
        controller = LearningLoopController(
            extractor=LearningKnowledgeExtractor(),
            predictor=PatternPredictor(),
            decision_enhancer=DecisionLearningEnhancer(),
            integrator=LearningMemoryIntegrator(),
        )
        result = controller.run_cycle(
            context={"game": "Merge Witch", "country": "US"},
            decision_memory=decision_memory,
        )
    """

    def __init__(
        self,
        extractor: LearningKnowledgeExtractor | None = None,
        predictor: Any = None,  # PatternPredictor
        decision_enhancer: DecisionLearningEnhancer | None = None,
        integrator: LearningMemoryIntegrator | None = None,
    ) -> None:
        """初始化控制器.

        Args:
            extractor: 知识提取器
            predictor: 模式预测器
            decision_enhancer: 决策学习增强器
            integrator: 记忆整合器
        """
        self._extractor = extractor or LearningKnowledgeExtractor()
        self._predictor = predictor  # PatternPredictor (optional)
        self._decision_enhancer = decision_enhancer or DecisionLearningEnhancer()
        self._integrator = integrator  # LearningMemoryIntegrator (optional)
        self._cycle_count: int = 0

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # ── Public API: run_cycle ───────────────────────────────────

    def run_cycle(
        self,
        context: dict[str, Any] | None = None,
        experiences: list[LearningExperience] | None = None,
        rewards: list[LearningReward] | None = None,
        decision_memory: Any = None,
        experience_store: Any = None,
        pattern_store: Any = None,
    ) -> LearningCycleResult:
        """执行一次完整学习循环.

        Args:
            context: 当前上下文 (game, country, creative, spend, ...)
            experiences: 学习经验列表 (可选, 如果提供则直接使用)
            rewards: 奖励列表 (可选)
            decision_memory: DecisionMemory 实例
            experience_store: ExperienceStore 实例
            pattern_store: PatternStore 实例

        Returns:
            LearningCycleResult: 完整循环结果
        """
        self._cycle_count += 1
        ctx = context or {}
        actions: list[str] = []
        updates: dict[str, Any] = {}

        knowledge: LearningKnowledge | None = None
        prediction: PatternPrediction | None = None
        decision_learning: DecisionLearningResult | None = None

        # ── Step 1: 检索经验 (如果未提供, 尝试从记忆系统获取) ──
        exps = experiences or []
        rews = rewards or []
        if not exps and self._integrator is not None:
            try:
                retrieved = self._integrator.retrieve_similar(
                    context=ctx,
                    limit=50,
                )
                if retrieved:
                    exps = retrieved.get("experiences", [])
                    actions.append("retrieved_experiences")
                    updates["retrieved_experiences"] = len(exps)
            except Exception:
                pass

        # ── Step 2: 提取知识 ──
        if exps:
            try:
                knowledge = self._extractor.extract(
                    experiences=exps,
                    rewards=rews if rews else None,
                )
                actions.append("knowledge_extracted")
                updates["knowledge"] = {
                    "patterns": knowledge.pattern_count,
                    "strategies": knowledge.strategy_count,
                    "warnings": knowledge.warning_count,
                    "confidence": knowledge.confidence,
                }
            except Exception:
                knowledge = None

        # ── Step 3: 预测模式 ──
        if knowledge is not None and self._predictor is not None:
            try:
                prediction = self._predictor.predict(
                    context=ctx,
                    knowledge=knowledge,
                )
                actions.append("pattern_predicted")
                updates["prediction"] = {
                    "recommended_pattern": prediction.recommended_pattern,
                    "expected_roas": prediction.expected_roas,
                    "confidence": prediction.confidence,
                }
            except Exception:
                prediction = None

        # ── Step 4: 增强决策 ──
        if decision_memory is not None:
            try:
                decision_learning = self._decision_enhancer.enhance(
                    context=ctx,
                    decision_memory=decision_memory,
                    risk_signals=knowledge.warnings if knowledge else None,
                )
                actions.append("decision_enhanced")
                updates["decision_learning"] = {
                    "recommendation": decision_learning.recommendation,
                    "confidence": decision_learning.confidence,
                    "success_rate": decision_learning.success_rate,
                }
            except Exception:
                decision_learning = None

        # ── Step 5: 更新记忆 (如果有新经验和整合器) ──
        if exps and self._integrator is not None and experience_store is not None:
            try:
                for exp in exps:
                    if hasattr(exp, "reward") and exp.reward is not None:
                        self._integrator.integrate(
                            experience=exp,
                            reward=exp.reward,
                            attribution=getattr(exp, "attribution", None),
                        )
                actions.append("memory_updated")
                updates["memory_updated"] = len(exps)
            except Exception:
                pass

        # ── 计算循环置信度 ──
        cycle_conf = self._compute_cycle_confidence(knowledge, prediction, decision_learning)

        # ── 生成改进建议 ──
        improvements = self._generate_improvements(knowledge, prediction, decision_learning)

        # ── 下一轮建议 ──
        next_recommendations = self._generate_next_cycle_recommendations(
            knowledge, prediction, decision_learning
        )

        return LearningCycleResult(
            knowledge=knowledge,
            prediction=prediction,
            decision_learning=decision_learning,
            cycle_confidence=round(cycle_conf, 4),
            actions_taken=actions,
            memory_updates=updates,
            improvements=improvements,
            next_cycle_recommendations=next_recommendations,
            metadata={
                "cycle_number": self._cycle_count,
                "context_keys": list(ctx.keys()),
                "experiences_used": len(exps),
            },
        )

    # ── Confidence ──────────────────────────────────────────────

    def _compute_cycle_confidence(
        self,
        knowledge: LearningKnowledge | None,
        prediction: PatternPrediction | None,
        decision_learning: DecisionLearningResult | None,
    ) -> float:
        """计算循环整体置信度."""
        components = []

        if knowledge is not None:
            components.append((knowledge.confidence, 0.30))
        if prediction is not None:
            components.append((prediction.confidence, 0.35))
        if decision_learning is not None:
            components.append((decision_learning.confidence, 0.35))

        if not components:
            return 0.0

        confidence = sum(conf * weight for conf, weight in components)
        return round(min(0.95, max(0.0, confidence)), 4)

    # ── Improvements ────────────────────────────────────────────

    def _generate_improvements(
        self,
        knowledge: LearningKnowledge | None,
        prediction: PatternPrediction | None,
        decision_learning: DecisionLearningResult | None,
    ) -> list[str]:
        """从循环结果中识别改进点."""
        improvements: list[str] = []

        if knowledge is not None:
            if knowledge.has_critical_risks:
                improvements.append("Critical risks detected — prioritize risk mitigation")
            if not knowledge.has_strong_patterns:
                improvements.append("No strong patterns found — increase sample size and testing")

        if prediction is not None:
            if prediction.confidence < 0.5:
                improvements.append("Low prediction confidence — gather more context data")
            if prediction.risk_level == "high":
                improvements.append("High prediction risk — consider escalation")

        if decision_learning is not None:
            if decision_learning.failure_count > decision_learning.success_count:
                improvements.append("Historical failure rate exceeds success rate — review strategy")
            if decision_learning.recommendation == "deny":
                improvements.append("Decision denied by history — re-evaluate approach")

        if not improvements:
            improvements.append("System operating normally — continue monitoring")

        return improvements

    # ── Next Cycle Recommendations ──────────────────────────────

    def _generate_next_cycle_recommendations(
        self,
        knowledge: LearningKnowledge | None,
        prediction: PatternPrediction | None,
        decision_learning: DecisionLearningResult | None,
    ) -> list[str]:
        """生成下一轮循环建议."""
        recs: list[str] = []

        if knowledge is None:
            recs.append("Collect more learning experiences before next cycle")
        elif knowledge.confidence < 0.5:
            recs.append("Increase sample size to improve knowledge confidence")

        if prediction is not None and prediction.is_strong:
            recs.append("Strong prediction — execute recommended pattern")
        elif prediction is not None and prediction.is_actionable:
            recs.append("Actionable prediction — test with controlled budget")

        if decision_learning is not None:
            if decision_learning.is_safe:
                recs.append("Safe to proceed — schedule next cycle in 7 days")
            elif decision_learning.recommendation == "adjust":
                recs.append("Adjust strategy before next cycle — re-run after changes")

        if not recs:
            recs.append("Continue standard learning cycle")

        return recs

    # ── Convenience: 快速循环 ───────────────────────────────────

    def quick_cycle(
        self,
        context: dict[str, Any] | None = None,
        decision_memory: Any = None,
    ) -> dict[str, Any]:
        """快速循环 — 仅做知识提取和决策增强, 返回简化结果.

        Args:
            context: 当前上下文
            decision_memory: DecisionMemory 实例

        Returns:
            dict: 简化结果 {recommendation, confidence, risks}
        """
        result = self.run_cycle(
            context=context,
            decision_memory=decision_memory,
        )
        return {
            "recommendation": (
                result.decision_learning.recommendation
                if result.decision_learning else "insufficient_data"
            ),
            "confidence": result.cycle_confidence,
            "risks": (
                result.decision_learning.risk_signals
                if result.decision_learning else []
            ),
            "improvements": result.improvements,
        }


__all__ = [
    "LearningLoopController",
]