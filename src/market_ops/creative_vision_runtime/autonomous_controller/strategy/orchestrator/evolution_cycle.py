"""E11.9 — Evolution Cycle。

核心执行循环：一次完整的自主进化周期。

流程：
  1. Detect Opportunity
  2. Decision (是否启动)
  3. Generate Strategy
  4. Execute Strategy
  5. Evaluate Result
  6. Learn (Memory + Knowledge)
  7. Complete

这是 E11 系统从"被调用式进化"升级为"自主进化循环"的关键模块。
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionAction,
    EvolutionCycle,
    EvolutionCycleResult,
    EvolutionCycleStatus,
    EvolutionDecision,
    EvolutionOpportunity,
)
from .opportunity_detector import OpportunityDetector
from .decision_engine import DecisionEngine
from .lifecycle_manager import LifecycleManager

logger = logging.getLogger(__name__)


class EvolutionCycleRunner:
    """进化周期执行器。

    执行一次完整的自主进化周期。

    依赖：
      - StrategyPlanner (E11.8.1)
      - StrategyExecutor (E11.8.2)
      - EvaluationEngine (E11.8.3)
      - MemoryEngine (E11.7.4)
      - KnowledgeEngine (E11.7.5)
      - LifecycleManager

    Attributes:
        detector:          机会检测器
        decision_engine:   决策引擎
        lifecycle:         生命周期管理器
        strategy_planner:  策略规划器
        strategy_executor: 策略执行器
        evaluation_engine: 评估引擎
        memory_engine:     记忆引擎
        knowledge_engine:  知识引擎
    """

    def __init__(
        self,
        detector: OpportunityDetector | None = None,
        decision_engine: DecisionEngine | None = None,
        lifecycle: LifecycleManager | None = None,
        strategy_planner: Any = None,
        strategy_executor: Any = None,
        evaluation_engine: Any = None,
        memory_engine: Any = None,
        knowledge_engine: Any = None,
    ) -> None:
        self._detector = detector or OpportunityDetector()
        self._decision_engine = decision_engine or DecisionEngine()
        self._lifecycle = lifecycle or LifecycleManager()
        self._strategy_planner = strategy_planner
        self._strategy_executor = strategy_executor
        self._evaluation_engine = evaluation_engine
        self._memory_engine = memory_engine
        self._knowledge_engine = knowledge_engine

    # ── 主入口：run_cycle ────────────────────────────────

    def run_cycle(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
        force: bool = False,
    ) -> EvolutionCycleResult:
        """执行一次完整进化周期。

        Args:
            market_signal: 市场信号
            knowledge:     知识图谱数据
            population:    种群状态
            budget:        预算状态
            force:         强制运行（跳过决策）

        Returns:
            EvolutionCycleResult
        """
        cycle = EvolutionCycle()
        cycle.status = EvolutionCycleStatus.DETECTING

        # 注册周期
        if not self._lifecycle.register_cycle(cycle):
            cycle.status = EvolutionCycleStatus.CANCELLED
            cycle.trigger_reason = "Max active cycles reached"
            return EvolutionCycleResult(
                cycle=cycle,
                success=False,
                summary="CANCELLED: max active cycles",
            )

        try:
            # Step 1: Detect
            self._lifecycle.transition(cycle, EvolutionCycleStatus.DETECTING)
            opportunity = self._detector.detect_top(
                market_signal, knowledge, population
            )

            if not opportunity and not force:
                cycle.status = EvolutionCycleStatus.CANCELLED
                cycle.trigger_reason = "No opportunity detected"
                self._lifecycle.transition(cycle, EvolutionCycleStatus.CANCELLED)
                return EvolutionCycleResult(
                    cycle=cycle,
                    success=True,
                    summary="No evolution needed",
                )

            # Step 2: Decide
            cycle.opportunity_score = opportunity.score if opportunity else 0.0
            cycle.trigger_reason = opportunity.type.value if opportunity else "forced"

            if not force:
                decision = self._decision_engine.decide(
                    opportunity,
                    budget=budget,
                    active_cycles=self._lifecycle.get_active_cycle_count(),
                )
                cycle.decision = decision

                if decision.action != EvolutionAction.START_EVOLUTION:
                    cycle.status = EvolutionCycleStatus.CANCELLED
                    cycle.trigger_reason = f"Decision: {decision.action.value}"
                    self._lifecycle.transition(cycle, EvolutionCycleStatus.CANCELLED)
                    return EvolutionCycleResult(
                        cycle=cycle,
                        success=True,
                        summary=f"Decision: {decision.action.value}",
                    )
            else:
                cycle.decision = EvolutionDecision(
                    action=EvolutionAction.START_EVOLUTION,
                    reason="Forced run",
                    confidence=1.0,
                )

            # Step 3: Plan
            self._lifecycle.transition(cycle, EvolutionCycleStatus.PLANNING)
            strategies = self._plan(cycle, market_signal, knowledge, population)

            if not strategies:
                cycle.status = EvolutionCycleStatus.FAILED
                self._lifecycle.transition(cycle, EvolutionCycleStatus.FAILED)
                return EvolutionCycleResult(
                    cycle=cycle,
                    success=False,
                    summary="No strategies generated",
                )

            cycle.strategy_id = strategies[0].strategy_id if hasattr(strategies[0], 'strategy_id') else ""

            # Step 4: Execute
            self._lifecycle.transition(cycle, EvolutionCycleStatus.EXECUTING)
            execution_result = self._execute(cycle, strategies)
            cycle.execution_id = execution_result.plan_id if hasattr(execution_result, 'plan_id') else ""

            # Step 5: Evaluate
            self._lifecycle.transition(cycle, EvolutionCycleStatus.EVALUATING)
            evaluation = self._evaluate(cycle, strategies, market_signal)

            # Step 6: Learn
            self._lifecycle.transition(cycle, EvolutionCycleStatus.LEARNING)
            self._learn(cycle, evaluation, strategies)

            # Step 7: Complete
            self._lifecycle.transition(cycle, EvolutionCycleStatus.COMPLETED)

            summary = (
                f"COMPLETED: {len(strategies)} strategies, "
                f"evaluation: {evaluation.status.value if hasattr(evaluation, 'status') else 'N/A'}"
            )

            return EvolutionCycleResult(
                cycle=cycle,
                success=True,
                strategies=list(strategies),
                execution=execution_result,
                evaluation=evaluation,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Cycle {cycle.cycle_id} failed: {e}")
            self._lifecycle.transition(cycle, EvolutionCycleStatus.FAILED)
            return EvolutionCycleResult(
                cycle=cycle,
                success=False,
                summary=f"FAILED: {e}",
            )

    # ── 内部方法 ─────────────────────────────────────────

    def _plan(
        self,
        cycle: EvolutionCycle,
        market_signal: dict[str, Any] | None,
        knowledge: dict[str, Any] | None,
        population: dict[str, Any] | None,
    ) -> list[Any]:
        """生成策略。"""
        if self._strategy_planner is None:
            logger.warning("No strategy_planner configured")
            return []

        try:
            return self._strategy_planner.plan(
                feedback=market_signal,
                knowledge=knowledge,
                population=population,
            )
        except Exception as e:
            logger.error(f"Strategy planning failed: {e}")
            return []

    def _execute(
        self,
        cycle: EvolutionCycle,
        strategies: list[Any],
    ) -> Any:
        """执行策略。"""
        if self._strategy_executor is None or not strategies:
            return None

        try:
            return self._strategy_executor.execute(strategies[0])
        except Exception as e:
            logger.error(f"Strategy execution failed: {e}")
            return None

    def _evaluate(
        self,
        cycle: EvolutionCycle,
        strategies: list[Any],
        market_signal: dict[str, Any] | None,
    ) -> Any:
        """评估结果。"""
        if self._evaluation_engine is None:
            return None

        try:
            # 使用当前指标作为 after
            before = market_signal.get("previous_metrics", {}) if market_signal else {}
            after = market_signal.get("metrics", {}) if market_signal else {}

            if not before or not after:
                return None

            strategy = strategies[0] if strategies else None
            return self._evaluation_engine.evaluate(
                before=before,
                after=after,
                strategy=strategy,
            )
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return None

    def _learn(
        self,
        cycle: EvolutionCycle,
        evaluation: Any,
        strategies: list[Any],
    ) -> None:
        """学习：写入记忆和知识图谱。"""
        # Memory
        if self._memory_engine and evaluation:
            try:
                strategy = strategies[0] if strategies else None
                fitness_before = 50.0
                fitness_after = 50.0 + (
                    evaluation.score if hasattr(evaluation, 'score') else 0
                )
                self._memory_engine.remember(
                    genome_id=strategy.strategy_id if strategy else "unknown",
                    mutation_type=(
                        strategy.strategy_type.value
                        if strategy and hasattr(strategy, 'strategy_type')
                        else "unknown"
                    ),
                    fitness_before=fitness_before,
                    fitness_after=fitness_after,
                )
            except Exception as e:
                logger.error(f"Memory storage failed: {e}")

        # Knowledge
        if self._knowledge_engine and evaluation:
            try:
                # 从 memory 获取最新记录并更新知识
                if self._memory_engine:
                    records = self._memory_engine.get_all()
                    if records:
                        self._knowledge_engine.ingest_batch(records[-1:])
            except Exception as e:
                logger.error(f"Knowledge update failed: {e}")

    # ── 属性 ────────────────────────────────────────────

    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    def __repr__(self) -> str:
        return f"EvolutionCycleRunner(lifecycle={self._lifecycle})"