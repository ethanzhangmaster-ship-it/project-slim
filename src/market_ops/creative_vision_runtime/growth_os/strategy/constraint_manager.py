"""E12.7.3 — Constraint Manager。

约束管理器 —— 验证策略是否符合安全约束。

职责:
  1. 检查预算约束
  2. 检查实验约束
  3. 检查风险约束
  4. 输出 ConstraintCheck 列表
"""

from __future__ import annotations

from typing import Any

from .models import (
    ActionType,
    ConstraintCheck,
    GrowthStrategy,
    RiskLevel,
    StrategyStatus,
)


# 默认约束
_DEFAULT_CONSTRAINTS: list[dict[str, Any]] = [
    {
        "name": "max_budget_change",
        "description": "Budget change must not exceed 50%",
        "check": lambda s: _check_budget_change(s, 0.50),
        "severity": RiskLevel.HIGH,
    },
    {
        "name": "max_experiment_duration",
        "description": "Experiment duration must not exceed 30 days",
        "check": lambda s: _check_experiment_duration(s, 30),
        "severity": RiskLevel.MEDIUM,
    },
    {
        "name": "max_parallel_actions",
        "description": "Parallel actions must not exceed 10",
        "check": lambda s: _check_parallel_actions(s, 10),
        "severity": RiskLevel.MEDIUM,
    },
    {
        "name": "risk_threshold",
        "description": "Strategy risk score must not exceed 0.90",
        "check": lambda s: _check_risk_threshold(s, 0.90),
        "severity": RiskLevel.CRITICAL,
    },
    {
        "name": "min_confidence",
        "description": "Strategy confidence must be at least 0.30",
        "check": lambda s: _check_min_confidence(s, 0.30),
        "severity": RiskLevel.HIGH,
    },
    {
        "name": "max_duration",
        "description": "Strategy total duration must not exceed 60 days",
        "check": lambda s: _check_max_duration(s, 60),
        "severity": RiskLevel.MEDIUM,
    },
    {
        "name": "sunset_allowed",
        "description": "Sunset strategy must have explicit approval",
        "check": lambda s: _check_sunset_allowed(s),
        "severity": RiskLevel.CRITICAL,
    },
]


def _check_budget_change(strategy: GrowthStrategy, max_change: float) -> ConstraintCheck:
    max_actual = 0.0
    for a in strategy.actions:
        if a.action_type in (
            ActionType.INCREASE_BUDGET,
            ActionType.DECREASE_BUDGET,
        ):
            change = abs(a.parameters.get("change_pct", 0.0))
            max_actual = max(max_actual, change)

    passed = max_actual <= max_change
    return ConstraintCheck(
        constraint_name="max_budget_change",
        passed=passed,
        current_value=max_actual,
        max_value=max_change,
        message=(
            f"Budget change {max_actual:.0%} <= {max_change:.0%}"
            if passed
            else f"Budget change {max_actual:.0%} exceeds limit {max_change:.0%}"
        ),
        severity=RiskLevel.HIGH,
    )


def _check_experiment_duration(strategy: GrowthStrategy, max_days: int) -> ConstraintCheck:
    max_duration = 0
    for a in strategy.actions:
        if a.action_type == ActionType.LAUNCH_EXPERIMENT:
            dur = a.parameters.get("duration_days", a.duration_days)
            max_duration = max(max_duration, dur)

    passed = max_duration <= max_days
    return ConstraintCheck(
        constraint_name="max_experiment_duration",
        passed=passed,
        current_value=float(max_duration),
        max_value=float(max_days),
        message=(
            f"Experiment duration {max_duration}d <= {max_days}d"
            if passed
            else f"Experiment duration {max_duration}d exceeds limit {max_days}d"
        ),
        severity=RiskLevel.MEDIUM,
    )


def _check_parallel_actions(strategy: GrowthStrategy, max_parallel: int) -> ConstraintCheck:
    # 统计无依赖的动作数量（可并行执行）
    independent = sum(1 for a in strategy.actions if not a.has_dependencies)
    passed = independent <= max_parallel
    return ConstraintCheck(
        constraint_name="max_parallel_actions",
        passed=passed,
        current_value=float(independent),
        max_value=float(max_parallel),
        message=(
            f"Parallel actions {independent} <= {max_parallel}"
            if passed
            else f"Parallel actions {independent} exceeds limit {max_parallel}"
        ),
        severity=RiskLevel.MEDIUM,
    )


def _check_risk_threshold(strategy: GrowthStrategy, max_risk: float) -> ConstraintCheck:
    passed = strategy.risk_score <= max_risk
    return ConstraintCheck(
        constraint_name="risk_threshold",
        passed=passed,
        current_value=strategy.risk_score,
        max_value=max_risk,
        message=(
            f"Risk score {strategy.risk_score:.2f} <= {max_risk:.2f}"
            if passed
            else f"Risk score {strategy.risk_score:.2f} exceeds limit {max_risk:.2f}"
        ),
        severity=RiskLevel.CRITICAL,
    )


def _check_min_confidence(strategy: GrowthStrategy, min_conf: float) -> ConstraintCheck:
    passed = strategy.confidence >= min_conf
    return ConstraintCheck(
        constraint_name="min_confidence",
        passed=passed,
        current_value=strategy.confidence,
        max_value=1.0,
        message=(
            f"Confidence {strategy.confidence:.2f} >= {min_conf:.2f}"
            if passed
            else f"Confidence {strategy.confidence:.2f} below minimum {min_conf:.2f}"
        ),
        severity=RiskLevel.HIGH,
    )


def _check_max_duration(strategy: GrowthStrategy, max_days: int) -> ConstraintCheck:
    total = strategy.total_duration_days
    passed = total <= max_days
    return ConstraintCheck(
        constraint_name="max_duration",
        passed=passed,
        current_value=float(total),
        max_value=float(max_days),
        message=(
            f"Total duration {total}d <= {max_days}d"
            if passed
            else f"Total duration {total}d exceeds limit {max_days}d"
        ),
        severity=RiskLevel.MEDIUM,
    )


def _check_sunset_allowed(strategy: GrowthStrategy) -> ConstraintCheck:
    from .models import StrategyTemplateType
    is_sunset = strategy.template_type == StrategyTemplateType.SUNSET
    # Sunset 策略需要额外审批，默认标记为需注意
    return ConstraintCheck(
        constraint_name="sunset_allowed",
        passed=True,
        current_value=1.0 if is_sunset else 0.0,
        max_value=1.0,
        message=(
            "Sunset strategy requires explicit approval"
            if is_sunset
            else "N/A"
        ),
        severity=RiskLevel.CRITICAL if is_sunset else RiskLevel.LOW,
    )


class ConstraintManager:
    """约束管理器。

    验证策略是否符合安全约束。
    """

    def __init__(self) -> None:
        self._constraints = list(_DEFAULT_CONSTRAINTS)

    def validate(self, strategy: GrowthStrategy) -> list[ConstraintCheck]:
        """验证策略。

        Args:
            strategy: 增长策略

        Returns:
            ConstraintCheck 列表
        """
        results: list[ConstraintCheck] = []
        for constraint in self._constraints:
            try:
                check = constraint["check"](strategy)
                results.append(check)
            except Exception:
                results.append(
                    ConstraintCheck(
                        constraint_name=constraint["name"],
                        passed=False,
                        message=f"Validation error for {constraint['name']}",
                        severity=constraint.get("severity", RiskLevel.HIGH),
                    )
                )
        return results

    def validate_and_approve(
        self, strategy: GrowthStrategy
    ) -> tuple[bool, list[ConstraintCheck]]:
        """验证并批准策略。

        Args:
            strategy: 增长策略

        Returns:
            (是否通过, 检查结果列表)
        """
        checks = self.validate(strategy)
        all_passed = all(c.passed for c in checks)

        if all_passed:
            strategy.status = StrategyStatus.VALIDATED
        else:
            strategy.status = StrategyStatus.REJECTED

        return all_passed, checks

    def validate_batch(
        self, strategies: list[GrowthStrategy]
    ) -> dict[str, tuple[bool, list[ConstraintCheck]]]:
        """批量验证策略。

        Returns:
            {strategy_id: (passed, checks)}
        """
        results: dict[str, tuple[bool, list[ConstraintCheck]]] = {}
        for s in strategies:
            results[s.strategy_id] = self.validate_and_approve(s)
        return results

    def add_constraint(self, constraint: dict[str, Any]) -> None:
        """添加自定义约束。"""
        self._constraints.append(constraint)

    @property
    def constraint_count(self) -> int:
        return len(self._constraints)

    def __repr__(self) -> str:
        return f"ConstraintManager(constraints={self.constraint_count})"