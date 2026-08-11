"""E12.5.5 — Meta Learning Controller。

核心编排器 —— 管理完整的自我学习循环。

流程:
  Create Cycle → Collect History → Mine Patterns → Update Knowledge
  → Generate Strategies → Execute → Evaluate → Learn → Next Cycle

集成:
  - E12.5.1 Experience Memory
  - E12.5.2 Pattern Mining
  - E12.5.3 Knowledge Graph
  - E12.5.4 Meta Strategy Optimizer
  - E11.9 Evolution Orchestrator
"""

from __future__ import annotations

from typing import Any

from ..experience_store import ExperienceStore
from ..pattern_miner.pattern_miner import PatternExtractor
from ..pattern_miner.gene_analyzer import GeneAnalyzer
from ..pattern_miner.pattern_ranker import PatternRanker
from ..knowledge_graph.graph_store import GraphStore
from ..knowledge_graph.node_builder import NodeBuilder
from ..knowledge_graph.relationship_engine import RelationshipEngine
from ..strategy_optimizer.meta_optimizer import MetaOptimizer
from .cycle_manager import CycleManager
from .knowledge_updater import KnowledgeUpdater
from .learning_scheduler import LearningScheduler
from .strategy_feedback import StrategyFeedbackCollector
from .models import (
    LearningSchedule,
    LearningSummary,
    LoopMetrics,
    MetaCycleStatus,
    MetaLearningCycle,
    MetaLearningResult,
    TriggerReason,
)


class MetaLearningController:
    """元学习控制器 —— E12.5.5 核心编排器。

    管理从数据收集到知识更新的完整自主学习循环。

    Usage:
        >>> controller = MetaLearningController()
        >>> result = controller.run_cycle("p04")
        >>> # 连续运行
        >>> controller.run_loop("p04", max_cycles=5)
    """

    def __init__(
        self,
        experience_store: ExperienceStore | None = None,
        graph_store: GraphStore | None = None,
        scheduler: LearningScheduler | None = None,
        cycle_manager: CycleManager | None = None,
        knowledge_updater: KnowledgeUpdater | None = None,
        feedback_collector: StrategyFeedbackCollector | None = None,
        meta_optimizer: MetaOptimizer | None = None,
        schedule: LearningSchedule | None = None,
    ) -> None:
        self.experience_store = experience_store or ExperienceStore()
        self.graph_store = graph_store or GraphStore()
        self.scheduler = scheduler or LearningScheduler(schedule)
        self.cycle_manager = cycle_manager or CycleManager()
        self.knowledge_updater = knowledge_updater or KnowledgeUpdater()
        self.feedback_collector = feedback_collector or StrategyFeedbackCollector()
        self.meta_optimizer = meta_optimizer or MetaOptimizer()

        # 运行时状态
        self._metrics = LoopMetrics()
        self._start_time = None

    # ── Run Cycle ──────────────────────────────────────────

    def run_cycle(
        self,
        product_id: str,
        experiment_count: int = 0,
        total_spend: float = 0.0,
        trigger_reason: TriggerReason = TriggerReason.SCHEDULED,
    ) -> MetaLearningResult:
        """运行一次完整的学习周期。

        Collect → Mine → Update → Optimize → Execute → Evaluate → Learn

        Args:
            product_id:       产品 ID
            experiment_count: 当前实验数
            total_spend:      总花费
            trigger_reason:   触发原因

        Returns:
            MetaLearningResult
        """
        import time
        start = time.time()

        # 1. Create Cycle
        cycle = self.cycle_manager.create_cycle(product_id, trigger_reason)
        self.cycle_manager.advance(cycle)  # CREATED → COLLECTING

        try:
            # 2. Collect History
            cycle.status = MetaCycleStatus.COLLECTING
            experiences = self.experience_store.query_all()
            if not experiences:
                cycle.mark_completed("No experiences to learn from")
                return MetaLearningResult(cycle=cycle, success=True)

            cycle.experiments_analyzed = len(experiences)

            # 3. Mine Patterns
            self.cycle_manager.advance(cycle)  # → MINING
            cycle.status = MetaCycleStatus.MINING

            gene_analyzer = GeneAnalyzer()
            pattern_extractor = PatternExtractor()
            pattern_ranker = PatternRanker()

            # 提取基因
            extracted_genes_list = []
            for exp in experiences:
                genes = gene_analyzer.extract_genes(exp)
                extracted_genes_list.extend(genes)

            # 聚类 Pattern（使用 extract 方法）
            patterns = pattern_extractor.extract(experiences)
            # 排名
            ranked_patterns = pattern_ranker.rank(patterns)
            cycle.patterns_discovered = len(ranked_patterns)

            # 4. Update Knowledge
            self.cycle_manager.advance(cycle)  # → OPTIMIZING
            cycle.status = MetaCycleStatus.OPTIMIZING

            node_builder = NodeBuilder()
            relationship_engine = RelationshipEngine()

            # 构建/更新 Graph
            nodes, edges = node_builder.build_full_graph_from_patterns(ranked_patterns)
            for node in nodes:
                self.graph_store.add_node(node)
            for edge in edges:
                self.graph_store.add_edge(edge)

            cycle.knowledge_updates = len(nodes) + len(edges)

            # 5. Generate Strategies
            result = self.meta_optimizer.optimize(
                patterns=ranked_patterns,
                knowledge_nodes=nodes,
                knowledge_edges=edges,
                target_product=product_id,
                total_count=10,
            )
            cycle.strategies_generated = len(result.strategies)

            # 6. Execute (模拟——实际由 E11.9 执行)
            self.cycle_manager.advance(cycle)  # → EXECUTING
            cycle.status = MetaCycleStatus.EXECUTING

            for strategy in result.strategies:
                feedback = self.feedback_collector.collect(
                    strategy,
                    actual_gain=strategy.performance_impact * 0.9,  # 模拟 90% 达成
                    success=True,
                    cycle_id=cycle.cycle_id,
                )
                self.feedback_collector.update_strategy_score(strategy, feedback)

            cycle.feedbacks_collected = len(result.strategies)

            # 7. Evaluate & Learn
            self.cycle_manager.advance(cycle)  # → LEARNING
            cycle.status = MetaCycleStatus.LEARNING

            # 计算学习增益
            accuracy = self.feedback_collector.get_overall_accuracy()
            cycle.learning_gain = min(1.0, accuracy if accuracy > 0 else 0.5)

            # 8. Complete
            summary = LearningSummary(
                cycle_id=cycle.cycle_id,
                total_experiments=cycle.experiments_analyzed,
                total_patterns=cycle.patterns_discovered,
                total_strategies=cycle.strategies_generated,
                total_feedbacks=cycle.feedbacks_collected,
                average_prediction_accuracy=accuracy,
                strategies_improved=cycle.strategies_generated,
                knowledge_improved=cycle.knowledge_updates,
                overall_learning_gain=cycle.learning_gain,
                summary_text=(
                    f"Cycle {cycle.cycle_number}: "
                    f"Analyzed {cycle.experiments_analyzed} experiments, "
                    f"discovered {cycle.patterns_discovered} patterns, "
                    f"generated {cycle.strategies_generated} strategies. "
                    f"Learning gain: {cycle.learning_gain:.2f}"
                ),
            )

            self.cycle_manager.complete(cycle, summary.summary_text)

            # 更新指标
            self._update_metrics(cycle, time.time() - start)

            return MetaLearningResult(
                cycle=cycle,
                strategies=result.strategies,
                feedbacks=self.feedback_collector.get_feedbacks(""),
                summary=summary,
                metrics=self._metrics,
                success=True,
            )

        except Exception as e:
            self.cycle_manager.fail(cycle, str(e))
            return MetaLearningResult(
                cycle=cycle,
                success=False,
            )

    # ── Run Loop ───────────────────────────────────────────

    def run_loop(
        self,
        product_id: str,
        max_cycles: int = 10,
        experiment_count: int = 50,
        total_spend: float = 5000.0,
    ) -> list[MetaLearningResult]:
        """运行连续学习循环。

        Args:
            product_id:       产品 ID
            max_cycles:       最大循环次数
            experiment_count: 每轮实验数
            total_spend:      每轮花费

        Returns:
            MetaLearningResult 列表
        """
        results: list[MetaLearningResult] = []

        for i in range(max_cycles):
            trigger = self.scheduler.check(
                experiment_count=experiment_count * (i + 1),
                total_spend=total_spend * (i + 1),
                days_since_last=7.0,
            )

            if not trigger.should_trigger:
                continue

            result = self.run_cycle(
                product_id=product_id,
                experiment_count=experiment_count * (i + 1),
                total_spend=total_spend * (i + 1),
                trigger_reason=trigger.reason,
            )
            results.append(result)

            if not result.success:
                break

        return results

    def should_run(self, product_id: str) -> bool:
        """判断是否应该运行学习周期。

        Args:
            product_id: 产品 ID

        Returns:
            True if should run
        """
        last_cycle = self.cycle_manager.get_last_completed(product_id)
        experiences = self.experience_store.query_all()

        trigger = self.scheduler.check_from_state(
            experiment_count=len(experiences),
            total_spend=5000.0,
            last_cycle=last_cycle.end_time if last_cycle else None,
        )

        return trigger.should_trigger

    # ── Metrics ────────────────────────────────────────────

    def _update_metrics(self, cycle: MetaLearningCycle, duration: float) -> None:
        """更新循环指标。"""
        self._metrics.total_cycles += 1
        if cycle.is_successful:
            self._metrics.successful_cycles += 1
        else:
            self._metrics.failed_cycles += 1

        self._metrics.total_patterns_mined += cycle.patterns_discovered
        self._metrics.total_knowledge_updated += cycle.knowledge_updates
        self._metrics.total_strategies_generated += cycle.strategies_generated

        # 更新平均学习增益
        old_gain = self._metrics.average_learning_gain
        n = self._metrics.total_cycles
        self._metrics.average_learning_gain = (
            old_gain * (n - 1) + cycle.learning_gain
        ) / n

        # 更新平均周期时长
        old_duration = self._metrics.average_cycle_duration
        self._metrics.average_cycle_duration = (
            old_duration * (n - 1) + duration
        ) / n

    def get_metrics(self) -> LoopMetrics:
        """获取循环指标。"""
        return self._metrics

    def get_status(self) -> dict[str, Any]:
        """获取控制器状态。"""
        return {
            "metrics": self._metrics.to_dict(),
            "cycle_stats": self.cycle_manager.get_stats(),
            "feedback_summary": self.feedback_collector.get_summary(),
            "graph_stats": self.graph_store.get_stats(),
        }

    def reset(self) -> None:
        """重置控制器。"""
        self._metrics = LoopMetrics()
        self.cycle_manager.clear()
        self.feedback_collector.clear()
        self.graph_store.clear()

    def __repr__(self) -> str:
        return (
            f"MetaLearningController(cycles={self._metrics.total_cycles}, "
            f"gain={self._metrics.average_learning_gain:.2f})"
        )