"""E11.5.3 — Feedback Engine。

统一入口：Performance → Fitness → Learning → EvolutionFeedback。

完整链路：
  Raw Experiment Data
    → PerformanceCollector.collect()
    → PerformanceSignal
    → Evaluator.evaluate()
    → FitnessScore
    → LearningEngine.generate()
    → LearningSignal
    → EvolutionFeedback
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    PerformanceSignal,
    FitnessScore,
    LearningSignal,
    EvolutionFeedback,
    LearningDirection,
)
from .performance_collector import PerformanceCollector
from .evaluator import Evaluator
from .learning_engine import LearningEngine

logger = logging.getLogger(__name__)


class FeedbackEngine:
    """反馈引擎。

    统一入口，串联 Performance → Fitness → Learning 的完整链路。

    Attributes:
        collector: PerformanceCollector
        evaluator: Evaluator
        learner:   LearningEngine
        process_count: 已处理次数
    """

    def __init__(
        self,
        collector: PerformanceCollector | None = None,
        evaluator: Evaluator | None = None,
        learner: LearningEngine | None = None,
    ) -> None:
        self._collector = collector or PerformanceCollector()
        self._evaluator = evaluator or Evaluator()
        self._learner = learner or LearningEngine()
        self._process_count: int = 0

    # ── 核心接口：process ──────────────────────────────

    def process(
        self,
        experiment_result: dict[str, Any],
    ) -> EvolutionFeedback:
        """处理单条实验数据，生成反馈。

        完整链路：
          experiment_result → collect → evaluate → generate → EvolutionFeedback

        Args:
            experiment_result: 原始实验数据

        Returns:
            EvolutionFeedback
        """
        # 1. 收集
        performance = self._collector.collect(experiment_result)

        # 2. 评估
        fitness = self._evaluator.evaluate(performance)

        # 3. 学习
        learning = self._learner.generate(fitness, performance)

        # 4. 组装反馈
        feedback = EvolutionFeedback(
            genome_id=fitness.genome_id,
            fitness=fitness,
            learning_signal=learning,
        )

        self._process_count += 1
        return feedback

    def process_batch(
        self,
        experiment_results: list[dict[str, Any]],
    ) -> list[EvolutionFeedback]:
        """批量处理实验数据。"""
        return [self.process(r) for r in experiment_results]

    # ── 子流程 ─────────────────────────────────────────

    def collect_and_evaluate(
        self,
        experiment_results: list[dict[str, Any]],
    ) -> list[FitnessScore]:
        """仅收集 + 评估，不生成学习信号。"""
        signals = self._collector.collect_batch(experiment_results)
        return self._evaluator.evaluate_batch(signals)

    def evaluate_only(
        self,
        signals: list[PerformanceSignal],
    ) -> list[FitnessScore]:
        """仅评估（已有 PerformanceSignal）。"""
        return self._evaluator.evaluate_batch(signals)

    # ── 连接 Controller ────────────────────────────────

    def get_learning_signals(
        self,
        feedbacks: list[EvolutionFeedback],
    ) -> list[LearningSignal]:
        """提取所有学习信号。"""
        return [
            f.learning_signal
            for f in feedbacks
            if f.learning_signal is not None
        ]

    def get_evolution_candidates(
        self,
        feedbacks: list[EvolutionFeedback],
    ) -> list[EvolutionFeedback]:
        """获取需要进化的反馈（MUTATE 或 IMPROVE）。"""
        return [f for f in feedbacks if f.needs_evolution]

    def get_retirement_candidates(
        self,
        feedbacks: list[EvolutionFeedback],
    ) -> list[EvolutionFeedback]:
        """获取需要退役的反馈。"""
        return [
            f
            for f in feedbacks
            if f.learning_signal is not None
            and f.learning_signal.should_retire
        ]

    def get_winners(
        self,
        feedbacks: list[EvolutionFeedback],
    ) -> list[EvolutionFeedback]:
        """获取 Winner 反馈。"""
        return [f for f in feedbacks if f.is_winner]

    # ── Stats ──────────────────────────────────────────

    @property
    def process_count(self) -> int:
        return self._process_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "process_count": self._process_count,
            "collected": self._collector.collected_count,
            "evaluated": self._evaluator.evaluate_count,
            "learning_generated": self._learner.generate_count,
            "top_genome": self._evaluator.get_stats().get("top_genome"),
            "top_score": self._evaluator.get_stats().get("top_score"),
        }

    def reset(self) -> None:
        self._process_count = 0
        self._collector.reset()
        self._evaluator.reset()
        self._learner.reset()

    def __repr__(self) -> str:
        return (
            f"FeedbackEngine(processed={self._process_count}, "
            f"collected={self._collector.collected_count})"
        )