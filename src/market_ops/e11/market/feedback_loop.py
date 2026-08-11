"""E11.5.4 Feedback Loop Controller — 进化反馈闭环控制器。

E11 的最终闭环层，将 Market Feedback 到 Evolution 的完整链路
串联为自动化 Evolution Feedback Loop。

角色定位：
  - FeedbackLoopController: 实时市场反馈驱动（单次事件 → 实时更新种群）
  - EvolutionOrchestrator: 批量多代进化（多代循环 → 收敛 + 断点）
  - 两者互补：Controller 处理实时信号，Orchestrator 处理批量进化

完整流程：
  PerformanceFeedback
      → MarketSignalProcessor
      → FitnessEngine
      → EvolutionBridge
      → Population Update
      → Selection
      → Next Generation

控制策略：
  - 正常: Fitness ↑ → 继续下一代
  - 失败: 连续 Fitness ↓ → 回滚
  - 收敛: N代无提升 → 停止

数据流：
  PerformanceFeedback → FeedbackLoopController.process_feedback() → FeedbackLoopState
"""

from __future__ import annotations

from typing import Any

from ..genome.schema import CreativeGenome
from ..evolution.population_schema import GenomePopulation
from ..evolution.orchestrator_schema import EvolutionConfig
from ..evolution.convergence_detector import ConvergenceDetector, ConvergenceConfig
from ..evolution.generation_schema import EvolutionHistory, GenerationRecord
from .feedback_schema import PerformanceFeedback
from .market_signal_schema import MarketSignal
from .signal_processor import MarketSignalProcessor
from .fitness_schema import GenomeFitness, FitnessHistory
from .fitness_engine import FitnessEngine
from .feedback_loop_schema import (
    LoopStatus,
    EvolutionFeedbackEvent,
    FeedbackLoopState,
    EvolutionEventStore,
)
from .evolution_bridge import EvolutionBridge


class FeedbackLoopController:
    """进化反馈闭环控制器。

    将 Market Feedback 到 Evolution 的完整链路串联为自动化闭环。

    Usage:
        controller = FeedbackLoopController()
        state = controller.process_feedback(
            feedback=performance_feedback,
            population=population,
            genome=genome,
        )
        # state.status → LoopStatus.EVOLVING
        # state.best_fitness → 0.91
    """

    def __init__(
        self,
        signal_processor: MarketSignalProcessor | None = None,
        fitness_engine: FitnessEngine | None = None,
        evolution_bridge: EvolutionBridge | None = None,
        convergence_config: ConvergenceConfig | None = None,
    ) -> None:
        self._signal_processor = signal_processor or MarketSignalProcessor()
        self._fitness_engine = fitness_engine or FitnessEngine()
        self._evolution_bridge = evolution_bridge or EvolutionBridge()
        self._convergence_detector = ConvergenceDetector(
            convergence_config or ConvergenceConfig()
        )
        self._event_store = EvolutionEventStore()
        self._loop_state: FeedbackLoopState | None = None
        self._population_history: dict[str, GenomePopulation] = {}

    # ── 主入口 ────────────────────────────────────────

    def process_feedback(
        self,
        feedback: PerformanceFeedback,
        population: GenomePopulation,
        genome: CreativeGenome,
        config: EvolutionConfig | None = None,
    ) -> FeedbackLoopState:
        """处理一次市场反馈，驱动进化循环。

        Args:
            feedback: PerformanceFeedback 实例
            population: 当前种群
            genome: 关联的 CreativeGenome
            config: 进化配置

        Returns:
            FeedbackLoopState
        """
        # 初始化或更新循环状态
        if self._loop_state is None:
            self._loop_state = FeedbackLoopState(
                generation=population.generation,
                population_id=population.population_id,
            )
        self._loop_state.start()

        try:
            # 1. 生成 MarketSignal
            signal = self._signal_processor.process(
                feedback, genome_id=genome.genome_id,
            )
            self._record_event(
                genome=genome,
                fitness_score=signal.quality_score,
                action="signal_generated",
                details={"signal_id": signal.signal_id},
            )

            # 2. 计算 Fitness
            fitness = self._fitness_engine.evaluate(signal)
            self._record_event(
                genome=genome,
                fitness_score=fitness.fitness_score,
                action="fitness_evaluated",
                details={
                    "fitness_id": fitness.fitness_id,
                    "monetization": fitness.monetization_score,
                    "retention": fitness.retention_score,
                    "acquisition": fitness.acquisition_score,
                },
            )

            # 3. 更新 Genome
            self._fitness_engine.update_genome(genome, fitness)
            self._record_event(
                genome=genome,
                fitness_score=fitness.fitness_score,
                action="genome_updated",
            )

            # 4. 应用反馈到种群
            self._evolution_bridge.apply_feedback(population, genome, fitness)
            self._record_event(
                genome=genome,
                fitness_score=fitness.fitness_score,
                action="population_updated",
                details={"population_size": population.size},
            )

            # 5. 记录适应度历史
            self._fitness_engine.record_fitness(genome, fitness)

            # 6. 选择精英
            if config:
                self._evolution_bridge.mark_elite(
                    population,
                    top_k=config.elite_count,
                    min_score=config.min_fitness_threshold,
                )
                self._record_event(
                    genome=genome,
                    fitness_score=fitness.fitness_score,
                    action="elite_marked",
                    details={"elite_count": config.elite_count},
                )

            # 7. 更新循环状态
            best = population.best_member
            self._loop_state.processed_count += 1
            self._loop_state.best_fitness = max(
                self._loop_state.best_fitness,
                fitness.fitness_score,
            )
            if best and best.score >= self._loop_state.best_fitness:
                self._loop_state.best_genome_id = best.genome_id

            self._loop_state.last_action = "feedback_processed"
            self._loop_state.evolve()

            # 8. 保存种群快照
            self._population_history[str(population.generation)] = population

            self._loop_state.complete()

        except Exception:
            self._loop_state.fail()
            raise

        return self._loop_state

    # ── 代管理 ────────────────────────────────────────

    def advance_generation(
        self,
        population: GenomePopulation,
    ) -> FeedbackLoopState:
        """推进到下一代。

        Args:
            population: 当前种群

        Returns:
            更新后的 FeedbackLoopState
        """
        self._evolution_bridge.advance_generation(population)

        if self._loop_state:
            self._loop_state.generation = population.generation
            self._loop_state.evolve()

        return self._loop_state or FeedbackLoopState()

    def select_survivors(
        self,
        population: GenomePopulation,
        elite_count: int = 5,
        min_fitness: float = 0.3,
    ) -> list[str]:
        """执行选择，返回幸存者 Genome ID 列表。

        Args:
            population: GenomePopulation
            elite_count: 精英数量
            min_fitness: 最低适应度

        Returns:
            幸存者 genome_id 列表
        """
        result = self._evolution_bridge.select_survivors(
            population, elite_count=elite_count, min_fitness=min_fitness,
        )
        return result.survivor_ids

    # ── 回滚 ──────────────────────────────────────────

    def should_rollback(
        self,
        current_fitness: float,
        degradation_threshold: float = 0.1,
    ) -> bool:
        """判断是否需要回滚。

        当适应度下降超过阈值时触发。

        Args:
            current_fitness: 当前适应度
            degradation_threshold: 下降阈值

        Returns:
            是否应回滚
        """
        if self._loop_state is None:
            return False
        return (self._loop_state.best_fitness - current_fitness) > degradation_threshold

    def rollback(
        self,
        population: GenomePopulation,
        previous_best_fitness: float,
        previous_best_genome_id: str,
    ) -> bool:
        """执行回滚。

        Args:
            population: 当前种群
            previous_best_fitness: 之前的最佳适应度
            previous_best_genome_id: 之前的最佳 Genome ID

        Returns:
            是否成功
        """
        return self._evolution_bridge.rollback_to_best(
            population, previous_best_fitness, previous_best_genome_id,
        )

    # ── 收敛检测 ──────────────────────────────────────

    def check_convergence(
        self,
        history: EvolutionHistory,
    ) -> dict[str, Any]:
        """检测进化是否收敛。

        Args:
            history: 进化历史

        Returns:
            收敛检测结果
        """
        return self._convergence_detector.detect(history)

    def is_converged(self, history: EvolutionHistory) -> bool:
        """便捷方法：是否已收敛。"""
        return self._convergence_detector.is_converged(history)

    # ── 事件查询 ──────────────────────────────────────

    @property
    def event_store(self) -> EvolutionEventStore:
        return self._event_store

    @property
    def timeline(self) -> list[EvolutionFeedbackEvent]:
        return self._event_store.get_timeline()

    def get_events_by_generation(self, generation: int) -> list[EvolutionFeedbackEvent]:
        return self._event_store.get_by_generation(generation)

    def get_events_by_genome(self, genome_id: str) -> list[EvolutionFeedbackEvent]:
        return self._event_store.get_by_genome(genome_id)

    # ── 状态查询 ──────────────────────────────────────

    @property
    def loop_state(self) -> FeedbackLoopState | None:
        return self._loop_state

    @property
    def best_score(self) -> float:
        return self._loop_state.best_fitness if self._loop_state else 0.0

    def reset(self) -> None:
        """重置控制器状态。"""
        self._loop_state = None
        self._event_store.clear()
        self._population_history.clear()

    # ── 内部方法 ──────────────────────────────────────

    def _record_event(
        self,
        genome: CreativeGenome,
        fitness_score: float,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> EvolutionFeedbackEvent:
        event = EvolutionFeedbackEvent(
            genome_id=genome.genome_id,
            fitness_score=fitness_score,
            generation=self._loop_state.generation if self._loop_state else 0,
            action=action,
            details=details or {},
        )
        self._event_store.add_event(event)
        return event

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_state": self._loop_state.to_dict() if self._loop_state else None,
            "events": self._event_store.to_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"FeedbackLoopController(gen={self._loop_state.generation if self._loop_state else 0}, "
            f"events={self._event_store.event_count})"
        )