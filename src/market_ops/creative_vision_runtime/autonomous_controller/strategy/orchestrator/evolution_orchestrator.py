"""E11.9 — Evolution Orchestrator。

核心入口：自主进化循环的总控。

功能：
  - run():         执行单次进化周期
  - run_loop():    循环执行（直到无机会或达到上限）
  - get_status():  获取当前状态

这是 E11 系统从 Evolution Framework 升级为 Autonomous Evolution Controller 的顶层模块。
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionCycleResult,
    EvolutionCycleStatus,
)
from .opportunity_detector import OpportunityDetector
from .decision_engine import DecisionEngine
from .lifecycle_manager import LifecycleManager
from .evolution_cycle import EvolutionCycleRunner

logger = logging.getLogger(__name__)

MAX_LOOP_ITERATIONS = 10


class EvolutionOrchestrator:
    """自主进化编排器。

    组合所有 E11 模块，提供自主进化循环的总入口。

    Attributes:
        detector:          机会检测器
        decision_engine:   决策引擎
        lifecycle:         生命周期管理器
        cycle_runner:      周期执行器
        max_iterations:    最大循环次数
    """

    def __init__(
        self,
        detector: OpportunityDetector | None = None,
        decision_engine: DecisionEngine | None = None,
        lifecycle: LifecycleManager | None = None,
        cycle_runner: EvolutionCycleRunner | None = None,
        strategy_planner: Any = None,
        strategy_executor: Any = None,
        evaluation_engine: Any = None,
        memory_engine: Any = None,
        knowledge_engine: Any = None,
        max_iterations: int = MAX_LOOP_ITERATIONS,
    ) -> None:
        self._lifecycle = lifecycle or LifecycleManager()
        self._detector = detector or OpportunityDetector()
        self._decision_engine = decision_engine or DecisionEngine()

        self._cycle_runner = cycle_runner or EvolutionCycleRunner(
            detector=self._detector,
            decision_engine=self._decision_engine,
            lifecycle=self._lifecycle,
            strategy_planner=strategy_planner,
            strategy_executor=strategy_executor,
            evaluation_engine=evaluation_engine,
            memory_engine=memory_engine,
            knowledge_engine=knowledge_engine,
        )

        self._max_iterations = max_iterations
        self._results: list[EvolutionCycleResult] = []

    # ── 主入口 ──────────────────────────────────────────

    def run(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
        force: bool = False,
    ) -> EvolutionCycleResult:
        """执行一次自主进化周期。

        Args:
            market_signal: 市场信号
            knowledge:     知识图谱数据
            population:    种群状态
            budget:        预算状态
            force:         强制运行

        Returns:
            EvolutionCycleResult
        """
        if not self._lifecycle.can_start_new() and not force:
            return EvolutionCycleResult(
                success=False,
                summary="CANCELLED: max active cycles",
            )

        result = self._cycle_runner.run_cycle(
            market_signal=market_signal,
            knowledge=knowledge,
            population=population,
            budget=budget,
            force=force,
        )

        self._results.append(result)
        return result

    def run_loop(
        self,
        market_signal: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
    ) -> list[EvolutionCycleResult]:
        """循环执行，直到无机会或达到上限。

        每次循环后重新检测机会，自动决定是否继续。

        Returns:
            EvolutionCycleResult 列表
        """
        results: list[EvolutionCycleResult] = []

        for i in range(self._max_iterations):
            if not self._lifecycle.can_start_new():
                logger.info(f"Loop stopped: max active cycles reached")
                break

            result = self.run(
                market_signal=market_signal,
                knowledge=knowledge,
                population=population,
                budget=budget,
            )

            results.append(result)

            if result.cycle and result.cycle.status in (
                EvolutionCycleStatus.CANCELLED,
                EvolutionCycleStatus.FAILED,
            ):
                # 如果取消或失败，不再继续
                if result.cycle.status == EvolutionCycleStatus.FAILED:
                    logger.warning(f"Loop stopped: cycle {result.cycle.cycle_id} failed")
                    break
                # CANCELLED 表示无机会，正常退出
                break

        return results

    # ── 状态查询 ─────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """获取编排器状态。"""
        stats = self._lifecycle.get_stats()
        return {
            "lifecycle": stats,
            "total_runs": len(self._results),
            "last_result": self._results[-1].to_dict() if self._results else None,
            "can_start_new": self._lifecycle.can_start_new(),
        }

    def get_results(self) -> list[EvolutionCycleResult]:
        return list(self._results)

    def reset(self) -> None:
        """重置编排器状态。"""
        self._results = []
        self._lifecycle = LifecycleManager(
            max_active=self._lifecycle._max_active,
        )

    # ── 属性 ────────────────────────────────────────────

    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    @property
    def cycle_runner(self) -> EvolutionCycleRunner:
        return self._cycle_runner

    def __repr__(self) -> str:
        return (
            f"EvolutionOrchestrator("
            f"runs={len(self._results)}, "
            f"lifecycle={self._lifecycle})"
        )