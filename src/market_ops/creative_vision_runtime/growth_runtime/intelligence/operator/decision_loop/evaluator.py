"""E15.3.2 Evaluators — 决策周期评估器.

包含:
  - GoalEvaluator:        目标评估
  - OpportunityEvaluator: 机会评估
  - PerformanceEvaluator: 性能评估 (奖励计算)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    CycleOutcome,
    CycleResult,
    DecisionCycle,
    EnvironmentState,
    GoalEvaluation,
    GoalHealth,
    OpportunitySignal,
)


# ═══════════════════════════════════════════════════════════════
# Goal Evaluator
# ═══════════════════════════════════════════════════════════════


class GoalEvaluator:
    """E15.3.2 目标评估器 — 评估目标健康状态.

    判断当前目标是否健康，计算差距和紧急度。

    用法:
        evaluator = GoalEvaluator()
        evals = evaluator.evaluate(goals, metrics)
    """

    # 紧急度阈值
    URGENCY_CRITICAL_GAP = 0.5     # 差距 > 50% → critical
    URGENCY_HIGH_GAP = 0.3         # 差距 > 30% → high
    URGENCY_MEDIUM_GAP = 0.15      # 差距 > 15% → medium

    def evaluate(
        self,
        goals: list[dict[str, Any]],
        metrics: dict[str, float],
    ) -> list[GoalEvaluation]:
        """评估多个目标的健康状态.

        Args:
            goals:   目标定义列表, 每个目标包含:
                     - goal_id, name, metric, target, direction, priority
            metrics: 当前指标快照

        Returns:
            list[GoalEvaluation]: 每个目标的评估结果
        """
        results: list[GoalEvaluation] = []
        for goal in goals:
            evaluation = self.evaluate_single(goal, metrics)
            results.append(evaluation)
        return results

    def evaluate_single(
        self,
        goal: dict[str, Any],
        metrics: dict[str, float],
    ) -> GoalEvaluation:
        """评估单个目标.

        Args:
            goal:    目标定义
            metrics: 当前指标

        Returns:
            GoalEvaluation
        """
        metric_key = goal.get("metric", "")
        target = float(goal.get("target", 0))
        current = float(metrics.get(metric_key, 0))
        direction = goal.get("direction", "above")
        goal_id = str(goal.get("goal_id", ""))
        goal_name = str(goal.get("name", ""))

        # 计算差距
        gap = self._calculate_gap(current, target, direction)

        # 计算进度
        progress = self._calculate_progress(current, target, direction)

        # 判断健康状态
        health = self._determine_health(current, target, direction, gap)

        # 紧急度
        urgency = self._determine_urgency(gap, goal.get("priority", "medium"))

        # 建议
        recommendation = self._generate_recommendation(
            health, gap, metric_key, direction
        )

        return GoalEvaluation(
            goal_id=goal_id,
            goal_name=goal_name,
            metric=metric_key,
            target=target,
            current=current,
            health=health,
            gap=round(gap, 4),
            urgency=urgency,
            recommendation=recommendation,
            progress=round(progress, 4),
        )

    def _calculate_gap(
        self, current: float, target: float, direction: str
    ) -> float:
        """计算差距 (归一化).

        Returns:
            float: 差距, 正值 = 未达标, 负值 = 超额完成
        """
        if target == 0:
            return 0.0
        if direction == "above":
            return (target - current) / abs(target)
        return (current - target) / abs(target)

    def _calculate_progress(
        self, current: float, target: float, direction: str
    ) -> float:
        """计算进度 [0, 1]."""
        if target == 0:
            return 0.0
        if direction == "above":
            return round(min(1.0, max(0.0, current / target)), 4)
        return round(min(1.0, max(0.0, target / max(0.0001, current))), 4)

    def _determine_health(
        self, current: float, target: float, direction: str, gap: float
    ) -> GoalHealth:
        """判断健康状态."""
        if direction == "above":
            if current >= target:
                return GoalHealth.ACHIEVED
            if gap <= 0.05:
                return GoalHealth.ON_TRACK
            if gap <= 0.15:
                return GoalHealth.BEHIND
            return GoalHealth.FAILED
        else:
            if current <= target:
                return GoalHealth.ACHIEVED
            if gap <= 0.05:
                return GoalHealth.ON_TRACK
            if gap <= 0.15:
                return GoalHealth.BEHIND
            return GoalHealth.FAILED

    def _determine_urgency(self, gap: float, priority: str) -> str:
        """确定紧急度."""
        if gap > self.URGENCY_CRITICAL_GAP:
            return "critical"
        if gap > self.URGENCY_HIGH_GAP or priority == "high":
            return "high"
        if gap > self.URGENCY_MEDIUM_GAP:
            return "medium"
        return "low"

    def _generate_recommendation(
        self, health: GoalHealth, gap: float, metric: str, direction: str
    ) -> str:
        """生成建议."""
        if health == GoalHealth.ACHIEVED:
            return f"Goal '{metric}' achieved, consider setting new target"
        if health == GoalHealth.ON_TRACK:
            return f"Goal '{metric}' on track, continue monitoring"
        if health == GoalHealth.BEHIND:
            direction_text = "increase" if direction == "above" else "decrease"
            return (
                f"Goal '{metric}' behind by {gap:.1%}, "
                f"need to {direction_text} performance"
            )
        return (
            f"Goal '{metric}' significantly off-target (gap: {gap:.1%}), "
            f"immediate action required"
        )

    def get_summary(self, evaluations: list[GoalEvaluation]) -> dict[str, Any]:
        """获取目标评估摘要."""
        if not evaluations:
            return {
                "total": 0, "on_track": 0, "behind": 0,
                "achieved": 0, "failed": 0, "avg_gap": 0.0,
            }
        counts = {
            "total": len(evaluations),
            "on_track": sum(1 for e in evaluations if e.health == GoalHealth.ON_TRACK),
            "behind": sum(1 for e in evaluations if e.health == GoalHealth.BEHIND),
            "achieved": sum(1 for e in evaluations if e.health == GoalHealth.ACHIEVED),
            "failed": sum(1 for e in evaluations if e.health == GoalHealth.FAILED),
            "avg_gap": round(sum(e.gap for e in evaluations) / len(evaluations), 4),
            "critical_count": sum(1 for e in evaluations if e.urgency == "critical"),
            "high_count": sum(1 for e in evaluations if e.urgency == "high"),
        }
        return counts


# ═══════════════════════════════════════════════════════════════
# Opportunity Evaluator
# ═══════════════════════════════════════════════════════════════


class OpportunityEvaluator:
    """E15.3.2 机会评估器 — 从环境状态中识别机会.

    分析环境指标，发现可执行的机会信号。

    用法:
        evaluator = OpportunityEvaluator()
        opportunities = evaluator.evaluate(environment_state)
    """

    # 机会检测阈值
    CTR_BOOST_THRESHOLD = 0.3   # CTR 提升 > 30% → 扩大投放
    ROAS_BOOST_THRESHOLD = 0.2  # ROAS 提升 > 20% → 扩大预算
    FATIGUE_THRESHOLD = 0.7     # 疲劳度 > 70% → 替换创意
    SPEND_LOW_THRESHOLD = 200   # 花费 < $200 → 有投放空间

    def evaluate(self, environment: EnvironmentState) -> list[OpportunitySignal]:
        """从环境状态中评估机会.

        Args:
            environment: 环境状态

        Returns:
            list[OpportunitySignal]: 发现的机会
        """
        opportunities: list[OpportunitySignal] = []

        # 检测指标异常 → 机会
        opportunities.extend(self._detect_from_anomalies(environment))

        # 检测趋势 → 机会
        opportunities.extend(self._detect_from_trends(environment))

        # 检测已有机会信号 → 直接返回
        opportunities.extend(environment.opportunities)

        return opportunities

    def _detect_from_anomalies(
        self, environment: EnvironmentState
    ) -> list[OpportunitySignal]:
        """从异常信号检测机会."""
        results: list[OpportunitySignal] = []
        for anomaly in environment.anomalies:
            if anomaly.metric == "ctr" and anomaly.deviation > 0:
                if anomaly.deviation > self.CTR_BOOST_THRESHOLD:
                    results.append(OpportunitySignal(
                        name=f"CTR Boost: {anomaly.metric}",
                        type="SCALE_WINNER_CREATIVE",
                        confidence=min(0.95, 0.5 + anomaly.deviation),
                        description=f"CTR significantly above baseline (+{anomaly.deviation:.0%})",
                        impacted_metrics=["ctr", "roas"],
                        estimated_impact={"ctr": anomaly.deviation, "roas": anomaly.deviation * 0.5},
                    ))
            elif anomaly.metric == "roas" and anomaly.deviation > 0:
                if anomaly.deviation > self.ROAS_BOOST_THRESHOLD:
                    results.append(OpportunitySignal(
                        name=f"ROAS Boost: {anomaly.metric}",
                        type="INCREASE_BUDGET",
                        confidence=min(0.95, 0.5 + anomaly.deviation),
                        description=f"ROAS significantly above baseline (+{anomaly.deviation:.0%})",
                        impacted_metrics=["roas", "revenue"],
                        estimated_impact={"roas": anomaly.deviation},
                    ))
            elif anomaly.metric == "fatigue" and anomaly.deviation > 0:
                if anomaly.current > self.FATIGUE_THRESHOLD:
                    results.append(OpportunitySignal(
                        name=f"Creative Fatigue: {anomaly.metric}",
                        type="REPLACE_CREATIVE",
                        confidence=min(0.9, anomaly.current),
                        description=f"Creative fatigue detected ({anomaly.current:.0%})",
                        impacted_metrics=["ctr", "roas"],
                        estimated_impact={"ctr": -0.1, "roas": -0.05},
                    ))
        return results

    def _detect_from_trends(
        self, environment: EnvironmentState
    ) -> list[OpportunitySignal]:
        """从趋势信号检测机会."""
        results: list[OpportunitySignal] = []
        for trend in environment.trends:
            if trend.direction == "up" and trend.strength > 0.6:
                if trend.consecutive_periods >= 2:
                    results.append(OpportunitySignal(
                        name=f"Rising Trend: {trend.metric}",
                        type="CAPITALIZE_TREND",
                        confidence=min(0.9, trend.strength),
                        description=(
                            f"{trend.metric} trending up for "
                            f"{trend.consecutive_periods} periods"
                        ),
                        impacted_metrics=[trend.metric],
                        estimated_impact={trend.metric: trend.strength * 0.3},
                    ))
            elif trend.direction == "down" and trend.strength > 0.6:
                if trend.consecutive_periods >= 2:
                    results.append(OpportunitySignal(
                        name=f"Declining Trend: {trend.metric}",
                        type="INVESTIGATE_DECLINE",
                        confidence=min(0.9, trend.strength),
                        description=(
                            f"{trend.metric} trending down for "
                            f"{trend.consecutive_periods} periods"
                        ),
                        impacted_metrics=[trend.metric],
                        estimated_impact={trend.metric: -trend.strength * 0.3},
                    ))
        return results

    def get_top_opportunities(
        self,
        environment: EnvironmentState,
        top_n: int = 3,
    ) -> list[OpportunitySignal]:
        """获取 Top N 机会 (按置信度排序)."""
        all_opps = self.evaluate(environment)
        sorted_opps = sorted(all_opps, key=lambda o: o.confidence, reverse=True)
        return sorted_opps[:top_n]


# ═══════════════════════════════════════════════════════════════
# Performance Evaluator
# ═══════════════════════════════════════════════════════════════


class PerformanceEvaluator:
    """E15.3.2 性能评估器 — 计算周期奖励和结果.

    计算公式:
      reward = performance_gain - risk_cost - execution_cost

    用法:
        evaluator = PerformanceEvaluator()
        result = evaluator.evaluate(cycle, metrics_before, metrics_after)
    """

    def __init__(
        self,
        performance_weight: float = 0.6,
        risk_weight: float = 0.25,
        cost_weight: float = 0.15,
    ):
        self._performance_weight = performance_weight
        self._risk_weight = risk_weight
        self._cost_weight = cost_weight

    def evaluate(
        self,
        cycle: DecisionCycle,
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
    ) -> CycleResult:
        """评估周期性能.

        Args:
            cycle:          决策周期
            metrics_before: 执行前指标
            metrics_after:  执行后指标

        Returns:
            CycleResult: 周期结果
        """
        # 计算性能增益
        performance_gain = self._calculate_performance_gain(
            metrics_before, metrics_after
        )

        # 计算风险成本
        risk_cost = self._calculate_risk_cost(cycle)

        # 计算执行成本
        execution_cost = self._calculate_execution_cost(cycle)

        # 综合奖励
        reward = (
            performance_gain * self._performance_weight
            - risk_cost * self._risk_weight
            - execution_cost * self._cost_weight
        )
        reward = round(max(0.0, min(1.0, reward)), 4)

        # 确定结果
        outcome = self._determine_outcome(reward, cycle)

        # 生成摘要
        summary = self._generate_summary(outcome, reward, performance_gain)

        # 提取经验教训
        lessons = self._extract_lessons(outcome, reward, metrics_before, metrics_after)

        return CycleResult(
            cycle_id=cycle.cycle_id,
            cycle_number=cycle.cycle_number,
            outcome=outcome,
            reward=reward,
            summary=summary,
            action_taken=cycle.selected_action.get("action_type", ""),
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            lessons=lessons,
            duration_seconds=cycle.duration_seconds(),
        )

    def _calculate_performance_gain(
        self,
        before: dict[str, float],
        after: dict[str, float],
    ) -> float:
        """计算性能增益 — 基于指标变化.

        只计算正向指标 (roas, ctr, cvr, revenue, payer_rate).
        """
        positive_metrics = ["roas", "ctr", "cvr", "revenue", "payer_rate"]
        gains: list[float] = []
        for key in positive_metrics:
            b = before.get(key, 0)
            a = after.get(key, 0)
            if b > 0:
                gain = (a - b) / b
                gains.append(gain)
        if not gains:
            return 0.5
        # 平均增益, 归一化到 [0, 1]
        avg_gain = sum(gains) / len(gains)
        return max(0.0, min(1.0, 0.5 + avg_gain))

    def _calculate_risk_cost(self, cycle: DecisionCycle) -> float:
        """计算风险成本."""
        if not cycle.risk_assessments:
            return 0.0
        max_risk = max(
            (r.get("risk_score", 0) for r in cycle.risk_assessments),
            default=0.0,
        )
        return max_risk

    def _calculate_execution_cost(self, cycle: DecisionCycle) -> float:
        """计算执行成本 — 基于耗时和错误."""
        duration = cycle.duration_seconds()
        # 耗时成本: 超过 60 秒开始增加成本
        time_cost = min(0.5, max(0.0, (duration - 60) / 300))
        # 错误成本
        error_cost = 0.3 if cycle.error else 0.0
        return min(0.8, time_cost + error_cost)

    def _determine_outcome(
        self, reward: float, cycle: DecisionCycle
    ) -> CycleOutcome:
        """确定周期结果."""
        if cycle.error:
            return CycleOutcome.ERROR
        if not cycle.selected_action:
            return CycleOutcome.NO_ACTION
        if reward >= 0.5:
            return CycleOutcome.SUCCESS
        if reward >= 0.3:
            return CycleOutcome.PARTIAL
        if reward >= 0.15:
            return CycleOutcome.FAILURE
        return CycleOutcome.FAILURE

    def _generate_summary(
        self, outcome: CycleOutcome, reward: float, performance_gain: float
    ) -> str:
        """生成摘要."""
        if outcome == CycleOutcome.SUCCESS:
            return f"Action successful (reward={reward:.2f}, gain={performance_gain:.2%})"
        if outcome == CycleOutcome.PARTIAL:
            return f"Action partially successful (reward={reward:.2f})"
        if outcome == CycleOutcome.NO_ACTION:
            return "No action taken"
        if outcome == CycleOutcome.ERROR:
            return "Action failed with error"
        return f"Action failed (reward={reward:.2f})"

    def _extract_lessons(
        self,
        outcome: CycleOutcome,
        reward: float,
        before: dict[str, float],
        after: dict[str, float],
    ) -> list[str]:
        """提取经验教训."""
        lessons: list[str] = []
        if outcome == CycleOutcome.SUCCESS:
            lessons.append(f"Action achieved high reward ({reward:.2f})")
            # 分析哪些指标改善
            for key in set(before) | set(after):
                b = before.get(key, 0)
                a = after.get(key, 0)
                if a > b and b > 0:
                    lessons.append(f"Metric '{key}' improved: {b:.2f} → {a:.2f}")
        elif outcome in (CycleOutcome.FAILURE, CycleOutcome.ERROR):
            lessons.append(f"Action failed (reward={reward:.2f}), review strategy")
        elif outcome == CycleOutcome.PARTIAL:
            lessons.append(f"Action partially successful (reward={reward:.2f})")
        return lessons


__all__ = [
    "GoalEvaluator",
    "OpportunityEvaluator",
    "PerformanceEvaluator",
]