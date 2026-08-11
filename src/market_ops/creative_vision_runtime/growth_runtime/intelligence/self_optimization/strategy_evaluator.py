"""E15.3.4 Strategy Evaluator — 策略性能评估.

评估各策略/动作类型的长期效果，检测策略退化。

用法:
    evaluator = StrategyEvaluator()
    evaluator.record_outcome("creative_refresh", success=True, reward=0.8)
    perf = evaluator.evaluate_strategy("creative_refresh")
    degraded = evaluator.get_degraded_strategies()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    OptimizationOpportunity,
    OptimizationArea,
    StrategyPerformance,
    TrendDirection,
)


# ═══════════════════════════════════════════════════════════════
# Strategy Evaluator
# ═══════════════════════════════════════════════════════════════


class StrategyEvaluator:
    """E15.3.4 策略评估器 — 评估策略长期效果.

    追踪每个策略的成功率和收益趋势，检测退化。

    用法:
        evaluator = StrategyEvaluator()
        evaluator.record_outcome("creative_refresh", success=True, reward=0.8)
        perf = evaluator.evaluate_strategy("creative_refresh")
    """

    def __init__(self, degradation_threshold: float = 0.15):
        self._strategies: dict[str, StrategyPerformance] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._degradation_threshold = degradation_threshold
        self._max_history: int = 200

    # ── Record ──────────────────────────────────────────────────

    def record_outcome(
        self,
        strategy_name: str,
        success: bool,
        reward: float = 0.0,
        timestamp: str | None = None,
    ) -> StrategyPerformance:
        """记录一次策略执行结果.

        Args:
            strategy_name: 策略名称
            success:       是否成功
            reward:        收益值
            timestamp:     时间戳

        Returns:
            StrategyPerformance
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        if strategy_name not in self._strategies:
            self._strategies[strategy_name] = StrategyPerformance(
                strategy_name=strategy_name,
            )
            self._history[strategy_name] = []

        perf = self._strategies[strategy_name]
        perf.total_attempts += 1
        if success:
            perf.success_count += 1
        perf.success_rate = perf.success_count / perf.total_attempts

        # 更新平均收益
        if perf.total_attempts == 1:
            perf.avg_reward = reward
        else:
            perf.avg_reward = (perf.avg_reward * (perf.total_attempts - 1) + reward) / perf.total_attempts

        # 记录历史
        self._history[strategy_name].append({
            "success": success,
            "reward": reward,
            "timestamp": ts,
        })
        if len(self._history[strategy_name]) > self._max_history:
            self._history[strategy_name] = self._history[strategy_name][-self._max_history:]

        # 更新趋势和退化状态
        self._update_trend(perf)
        perf.evaluated_at = ts

        return perf

    # ── Evaluate ────────────────────────────────────────────────

    def evaluate_strategy(self, strategy_name: str) -> StrategyPerformance | None:
        """评估指定策略."""
        return self._strategies.get(strategy_name)

    def evaluate_all(self) -> dict[str, StrategyPerformance]:
        """评估所有策略."""
        return dict(self._strategies)

    def get_degraded_strategies(self) -> list[StrategyPerformance]:
        """获取已退化的策略列表."""
        return [p for p in self._strategies.values() if p.degraded]

    def get_top_strategies(self, n: int = 5) -> list[StrategyPerformance]:
        """获取成功率最高的策略."""
        sorted_strategies = sorted(
            self._strategies.values(),
            key=lambda p: p.success_rate,
            reverse=True,
        )
        return sorted_strategies[:n]

    def get_bottom_strategies(self, n: int = 5) -> list[StrategyPerformance]:
        """获取成功率最低的策略."""
        sorted_strategies = sorted(
            self._strategies.values(),
            key=lambda p: p.success_rate,
        )
        return sorted_strategies[:n]

    # ── Trend ───────────────────────────────────────────────────

    def _update_trend(self, perf: StrategyPerformance) -> None:
        """更新趋势和退化状态."""
        history = self._history.get(perf.strategy_name, [])
        if len(history) < 10:
            return

        # 计算近期成功率 (最近 20 条)
        recent = history[-20:]
        recent_success = sum(1 for r in recent if r["success"])
        recent_rate = recent_success / len(recent)

        # 计算历史成功率 (前 20 条)
        earlier = history[-40:-20] if len(history) >= 40 else history[:len(history)//2]
        if not earlier:
            return
        earlier_success = sum(1 for r in earlier if r["success"])
        earlier_rate = earlier_success / len(earlier)

        # 判断趋势
        if recent_rate > earlier_rate + 0.05:
            perf.recent_trend = TrendDirection.IMPROVING
        elif recent_rate < earlier_rate - 0.05:
            perf.recent_trend = TrendDirection.DECLINING
        else:
            perf.recent_trend = TrendDirection.STABLE

        # 计算退化率
        if earlier_rate > 0:
            perf.degradation_rate = max(0.0, (earlier_rate - recent_rate) / earlier_rate)

        # 判断退化
        perf.degraded = (
            perf.recent_trend == TrendDirection.DECLINING
            and perf.degradation_rate >= self._degradation_threshold
        )

    # ── Opportunities ───────────────────────────────────────────

    def detect_opportunities(self) -> list[OptimizationOpportunity]:
        """检测策略退化引发的优化机会."""
        opportunities = []
        for perf in self.get_degraded_strategies():
            opp = OptimizationOpportunity(
                area=OptimizationArea.ACTION_SELECTION,
                problem=f"Strategy '{perf.strategy_name}' degraded: success rate {perf.success_rate:.2f} (was higher)",
                evidence=[
                    f"Total attempts: {perf.total_attempts}",
                    f"Current success rate: {perf.success_rate:.2f}",
                    f"Degradation rate: {perf.degradation_rate:.2f}",
                    f"Average reward: {perf.avg_reward:.2f}",
                ],
                expected_gain=perf.degradation_rate * 0.5,
                confidence=min(0.9, 0.5 + perf.degradation_rate),
                suggested_change=f"Re-evaluate '{perf.strategy_name}' weighting or replace with alternative strategy",
                priority=1 if perf.degradation_rate > 0.3 else 2,
            )
            opportunities.append(opp)
        return opportunities

    # ── Summary ─────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """获取摘要."""
        all_strategies = self.evaluate_all()
        degraded = self.get_degraded_strategies()
        return {
            "total_strategies": len(all_strategies),
            "degraded_count": len(degraded),
            "avg_success_rate": sum(p.success_rate for p in all_strategies.values()) / len(all_strategies)
            if all_strategies else 0.0,
            "degraded": [p.to_dict() for p in degraded],
            "strategies": {k: v.to_dict() for k, v in all_strategies.items()},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self) -> None:
        """重置所有数据."""
        self._strategies.clear()
        self._history.clear()


__all__ = ["StrategyEvaluator"]