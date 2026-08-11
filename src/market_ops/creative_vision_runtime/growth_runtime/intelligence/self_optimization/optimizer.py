"""E15.3.4 Self Optimizer — 自我优化主入口.

整合性能监控、策略评估、参数优化、学习优化和自我诊断，
形成完整的自我优化闭环。

完整闭环:
  Execution Data
      ↓
  Performance Monitor
      ↓
  Self Diagnosis
      ↓
  Optimization Planner
      ↓
  Parameter Optimizer
      ↓
  Apply Improvement
      ↓
  Measure Result
      ↺

用法:
    optimizer = SelfOptimizer()
    optimizer.record_metrics({"decision_accuracy": 0.72})
    optimizer.record_strategy("creative_refresh", success=True, reward=0.8)
    actions = optimizer.run_cycle()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .learning_optimizer import LearningOptimizer
from .models import (
    MetricSeverity,
    OptimizationAction,
    OptimizationArea,
    OptimizationMetric,
    OptimizationOpportunity,
    OptimizationPolicy,
    OptimizationResult,
    OptimizationStatus,
    StrategyPerformance,
    SystemDiagnosis,
    TrendDirection,
)
from .parameter_optimizer import ParameterOptimizer
from .performance_monitor import PerformanceMonitor
from .self_diagnosis import SelfDiagnosisEngine
from .strategy_evaluator import StrategyEvaluator


# ═══════════════════════════════════════════════════════════════
# Self Optimizer
# ═══════════════════════════════════════════════════════════════


class SelfOptimizer:
    """E15.3.4 自我优化器 — 主入口.

    整合所有自我优化组件，提供完整的优化闭环。

    用法:
        optimizer = SelfOptimizer()

        # 记录指标
        optimizer.record_metrics({"decision_accuracy": 0.72,
                                   "execution_success_rate": 0.81})

        # 记录策略结果
        optimizer.record_strategy("creative_refresh", success=True, reward=0.8)

        # 运行优化周期
        actions = optimizer.run_cycle()
    """

    def __init__(
        self,
        policy: OptimizationPolicy | None = None,
        monitor: PerformanceMonitor | None = None,
        strategy_evaluator: StrategyEvaluator | None = None,
        diagnosis: SelfDiagnosisEngine | None = None,
        param_optimizer: ParameterOptimizer | None = None,
        learning_optimizer: LearningOptimizer | None = None,
    ):
        self._policy = policy or OptimizationPolicy()
        self._monitor = monitor or PerformanceMonitor()
        self._strategy_evaluator = strategy_evaluator or StrategyEvaluator(
            degradation_threshold=self._policy.degradation_threshold
        )
        self._diagnosis = diagnosis or SelfDiagnosisEngine()
        self._param_optimizer = param_optimizer or ParameterOptimizer(policy=self._policy)
        self._learning_optimizer = learning_optimizer or LearningOptimizer(policy=self._policy)

        self._cycle_count: int = 0
        self._history: list[dict[str, Any]] = []

    # ── Properties ──────────────────────────────────────────────

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def monitor(self) -> PerformanceMonitor:
        return self._monitor

    @property
    def strategy_evaluator(self) -> StrategyEvaluator:
        return self._strategy_evaluator

    @property
    def diagnosis(self) -> SelfDiagnosisEngine:
        return self._diagnosis

    @property
    def param_optimizer(self) -> ParameterOptimizer:
        return self._param_optimizer

    # ── Record Data ─────────────────────────────────────────────

    def record_metrics(
        self, metrics: dict[str, float], source: str = ""
    ) -> list[OptimizationMetric]:
        """记录系统指标."""
        return self._monitor.record_batch(metrics, source)

    def record_strategy(
        self,
        strategy_name: str,
        success: bool,
        reward: float = 0.0,
    ) -> StrategyPerformance:
        """记录策略执行结果."""
        return self._strategy_evaluator.record_outcome(strategy_name, success, reward)

    def record_learning_stats(self, memory_stats: dict[str, Any]) -> list[OptimizationOpportunity]:
        """记录学习统计数据."""
        return self._learning_optimizer.analyze(memory_stats)

    # ── Run Cycle ───────────────────────────────────────────────

    def run_cycle(self) -> dict[str, Any]:
        """运行一次完整优化周期.

        Returns:
            dict: 周期结果
                {
                    "cycle": int,
                    "metrics": list,
                    "diagnosis": dict,
                    "opportunities": list,
                    "actions": list,
                    "applied": list,
                }
        """
        self._cycle_count += 1
        self._param_optimizer.tick_cooldowns()

        # Step 1: 收集指标
        metrics = self._monitor.collect_metrics()
        strategy_performances = list(self._strategy_evaluator.evaluate_all().values())

        # Step 2: 自我诊断
        diagnosis = self._diagnosis.diagnose(metrics, strategy_performances)

        # Step 3: 生成优化机会
        opportunities = self._diagnosis.generate_opportunities(diagnosis)
        # 加入策略评估的优化机会
        opportunities.extend(self._strategy_evaluator.detect_opportunities())

        # 去重
        opportunities = self._deduplicate_opportunities(opportunities)

        # Step 4: 生成优化动作
        actions = self._param_optimizer.optimize(opportunities)

        # Step 5: 应用低风险动作
        applied = []
        for action in actions:
            if action.risk_level == "low" and self._param_optimizer.apply_action(action.action_id):
                applied.append(action)

        # 记录历史
        cycle_result = {
            "cycle": self._cycle_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics_count": len(metrics),
            "degraded_metrics": len(self._monitor.get_degraded()),
            "diagnosis": diagnosis.to_dict(),
            "opportunities_count": len(opportunities),
            "actions_count": len(actions),
            "applied_count": len(applied),
            "actions": [a.to_dict() for a in actions],
            "applied": [a.to_dict() for a in applied],
        }
        self._history.append(cycle_result)

        return cycle_result

    def _deduplicate_opportunities(
        self, opportunities: list[OptimizationOpportunity]
    ) -> list[OptimizationOpportunity]:
        """去重优化机会."""
        seen: set[str] = set()
        result = []
        for opp in opportunities:
            key = f"{opp.area.value}:{opp.problem}"
            if key not in seen:
                seen.add(key)
                result.append(opp)
        return result

    # ── Evaluate Optimizations ──────────────────────────────────

    def evaluate_optimization(
        self, action_id: str, before_metric: float, after_metric: float
    ) -> OptimizationResult | None:
        """评估优化效果."""
        return self._param_optimizer.evaluate_action(action_id, before_metric, after_metric)

    def revert_optimization(self, action_id: str) -> bool:
        """回滚优化."""
        return self._param_optimizer.revert_action(action_id)

    # ── Query ───────────────────────────────────────────────────

    def get_metrics(self) -> list[OptimizationMetric]:
        return self._monitor.collect_metrics()

    def get_degraded_metrics(self) -> list[OptimizationMetric]:
        return self._monitor.get_degraded()

    def get_strategies(self) -> dict[str, StrategyPerformance]:
        return self._strategy_evaluator.evaluate_all()

    def get_degraded_strategies(self) -> list[StrategyPerformance]:
        return self._strategy_evaluator.get_degraded_strategies()

    def get_latest_diagnosis(self) -> SystemDiagnosis | None:
        return self._diagnosis.get_latest_diagnosis()

    def get_applied_params(self) -> dict[str, Any]:
        return self._param_optimizer.get_applied_params()

    def get_cycle_history(self) -> list[dict[str, Any]]:
        return list(self._history)

    # ── Summary ─────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """获取自我优化器完整摘要."""
        return {
            "cycle_count": self._cycle_count,
            "monitor": self._monitor.get_summary(),
            "strategies": self._strategy_evaluator.get_summary(),
            "diagnosis": self._diagnosis.get_summary(),
            "param_optimizer": self._param_optimizer.get_summary(),
            "learning_optimizer": self._learning_optimizer.get_summary(),
            "policy": self._policy.to_dict(),
            "history": self._history[-10:],  # 最近 10 个周期
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self) -> None:
        """重置所有组件."""
        self._monitor.reset()
        self._strategy_evaluator.reset()
        self._diagnosis.reset()
        self._param_optimizer.reset()
        self._learning_optimizer.reset()
        self._cycle_count = 0
        self._history.clear()


__all__ = ["SelfOptimizer"]