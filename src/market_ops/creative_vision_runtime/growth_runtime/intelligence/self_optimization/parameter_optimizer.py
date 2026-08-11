"""E15.3.4 Parameter Optimizer — 参数优化器.

自动调整系统参数，连接 Risk Engine、Action Selection、Reasoning 等模块。

可调参数:
  - Risk Engine:    medium_threshold, high_threshold, approval_threshold
  - Action Selection: reward_weight, confidence_weight, risk_weight, memory_weight, cost_weight
  - Reasoning:      confidence_threshold, hypothesis_confidence_min
  - Memory:         similarity_threshold, retrieval_top_k

用法:
    optimizer = ParameterOptimizer()
    actions = optimizer.optimize(opportunities, current_params)
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .models import (
    OptimizationAction,
    OptimizationArea,
    OptimizationOpportunity,
    OptimizationResult,
    OptimizationStatus,
    OptimizationPolicy,
)


# ═══════════════════════════════════════════════════════════════
# Parameter Registry
# ═══════════════════════════════════════════════════════════════

# 可调参数注册表: area → {parameter: {min, max, step, default}}
PARAMETER_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {
    "risk_engine": {
        "medium_threshold": {"min": 0.30, "max": 0.70, "step": 0.05, "default": 0.50},
        "high_threshold": {"min": 0.60, "max": 0.90, "step": 0.05, "default": 0.75},
        "approval_threshold": {"min": 0.40, "max": 0.80, "step": 0.05, "default": 0.60},
    },
    "action_selection": {
        "reward_weight": {"min": 0.20, "max": 0.60, "step": 0.05, "default": 0.45},
        "confidence_weight": {"min": 0.10, "max": 0.40, "step": 0.05, "default": 0.20},
        "risk_weight": {"min": 0.05, "max": 0.30, "step": 0.05, "default": 0.15},
        "memory_weight": {"min": 0.05, "max": 0.30, "step": 0.05, "default": 0.15},
        "cost_weight": {"min": 0.01, "max": 0.15, "step": 0.01, "default": 0.05},
        "blocking_confidence": {"min": 0.10, "max": 0.40, "step": 0.05, "default": 0.20},
    },
    "reasoning": {
        "confidence_threshold": {"min": 0.50, "max": 0.90, "step": 0.05, "default": 0.70},
        "hypothesis_confidence_min": {"min": 0.40, "max": 0.80, "step": 0.05, "default": 0.60},
    },
    "memory": {
        "similarity_threshold": {"min": 0.60, "max": 0.95, "step": 0.05, "default": 0.85},
        "retrieval_top_k": {"min": 3, "max": 20, "step": 1, "default": 10},
        "experience_weight": {"min": 0.50, "max": 2.00, "step": 0.10, "default": 1.00},
    },
    "planning": {
        "template_match_threshold": {"min": 0.50, "max": 0.90, "step": 0.05, "default": 0.70},
        "max_daily_increase": {"min": 0.10, "max": 0.50, "step": 0.05, "default": 0.20},
    },
}


# ═══════════════════════════════════════════════════════════════
# Parameter Optimizer
# ═══════════════════════════════════════════════════════════════


class ParameterOptimizer:
    """E15.3.4 参数优化器 — 自动调整系统参数.

    根据优化机会，生成参数调整方案。

    用法:
        optimizer = ParameterOptimizer()
        actions = optimizer.optimize(opportunities, current_params)
    """

    def __init__(
        self,
        policy: OptimizationPolicy | None = None,
        param_registry: dict[str, dict[str, dict[str, Any]]] | None = None,
    ):
        self._policy = policy or OptimizationPolicy()
        self._registry = copy.deepcopy(param_registry) if param_registry else copy.deepcopy(PARAMETER_REGISTRY)
        self._actions: list[OptimizationAction] = []
        self._results: list[OptimizationResult] = []
        self._cooldowns: dict[str, int] = {}  # parameter → cycles remaining
        self._applied_params: dict[str, Any] = {}  # parameter → current value

    # ── Optimize ────────────────────────────────────────────────

    def optimize(
        self,
        opportunities: list[OptimizationOpportunity],
        current_params: dict[str, Any] | None = None,
    ) -> list[OptimizationAction]:
        """根据优化机会生成参数调整动作.

        Args:
            opportunities:  优化机会列表
            current_params: 当前参数值

        Returns:
            list[OptimizationAction]: 优化动作列表
        """
        if current_params:
            self._applied_params.update(current_params)

        actions: list[OptimizationAction] = []
        for opp in opportunities:
            if not opp.is_actionable():
                continue
            action = self._generate_action(opp)
            if action:
                actions.append(action)
                self._actions.append(action)

        # 按优先级排序，限制每周期动作数
        actions.sort(key=lambda a: self._get_priority(a.area))
        return actions[:self._policy.max_actions_per_cycle]

    def _generate_action(self, opp: OptimizationOpportunity) -> OptimizationAction | None:
        """为单个机会生成优化动作."""
        area_key = opp.area.value
        params = self._registry.get(area_key, {})

        if not params:
            return None

        # 选择最相关的参数
        target_param = self._select_target_param(opp, params)
        if target_param is None:
            return None

        # 检查冷却
        if self._is_in_cooldown(target_param):
            return None

        param_info = params[target_param]
        old_value = self._applied_params.get(target_param, param_info["default"])

        # 计算新值
        new_value = self._compute_new_value(opp, target_param, old_value, param_info)

        return OptimizationAction(
            opportunity_id=opp.opportunity_id,
            area=opp.area,
            parameter=target_param,
            old_value=old_value,
            new_value=new_value,
            reason=opp.problem,
            risk_level=self._assess_risk(opp, target_param),
            status=OptimizationStatus.PROPOSED,
        )

    def _select_target_param(
        self, opp: OptimizationOpportunity, params: dict[str, dict[str, Any]]
    ) -> str | None:
        """选择目标参数."""
        # 匹配问题描述中的关键词
        problem_lower = opp.problem.lower()
        for param_name in params:
            if param_name.replace("_", " ") in problem_lower.replace("_", " "):
                return param_name

        # 回退到第一个参数
        return next(iter(params), None)

    def _compute_new_value(
        self,
        opp: OptimizationOpportunity,
        param_name: str,
        old_value: Any,
        param_info: dict[str, Any],
    ) -> Any:
        """计算参数新值."""
        step = param_info["step"]
        min_val = param_info["min"]
        max_val = param_info["max"]

        if isinstance(old_value, int):
            # 整数参数
            if "increase" in opp.problem.lower() or "too_low" in opp.problem.lower():
                new_val = min(old_value + step, int(max_val))
            elif "decrease" in opp.problem.lower() or "too_high" in opp.problem.lower():
                new_val = max(old_value - step, int(min_val))
            else:
                # 根据置信度决定方向
                direction = 1 if opp.expected_gain > 0.05 else -1
                new_val = old_value + direction * step
                new_val = max(int(min_val), min(int(max_val), new_val))
        else:
            # 浮点参数
            if "increase" in opp.problem.lower() or "too_low" in opp.problem.lower():
                new_val = min(old_value + step, max_val)
            elif "decrease" in opp.problem.lower() or "too_high" in opp.problem.lower():
                new_val = max(old_value - step, min_val)
            else:
                direction = 1 if opp.expected_gain > 0.05 else -1
                new_val = old_value + direction * step
                new_val = max(min_val, min(max_val, new_val))

        return round(new_val, 4) if isinstance(new_val, float) else new_val

    def _assess_risk(self, opp: OptimizationOpportunity, param_name: str) -> str:
        """评估调整风险."""
        if opp.confidence < 0.6:
            return "high"
        if opp.confidence < 0.75:
            return "medium"
        return "low"

    def _get_priority(self, area: OptimizationArea) -> int:
        """获取优化领域优先级."""
        priority_map = {
            OptimizationArea.DECISION_ACCURACY: 1,
            OptimizationArea.EXECUTION_SUCCESS: 1,
            OptimizationArea.RISK_ENGINE: 2,
            OptimizationArea.ACTION_SELECTION: 2,
            OptimizationArea.REASONING: 3,
            OptimizationArea.MEMORY: 3,
            OptimizationArea.LEARNING: 3,
            OptimizationArea.PLANNING: 4,
            OptimizationArea.WORKFLOW: 4,
        }
        return priority_map.get(area, 5)

    # ── Apply / Revert ──────────────────────────────────────────

    def apply_action(self, action_id: str) -> bool:
        """应用优化动作."""
        for action in self._actions:
            if action.action_id == action_id:
                action.status = OptimizationStatus.APPLIED
                action.applied_at = datetime.now(timezone.utc).isoformat()
                self._applied_params[action.parameter] = action.new_value
                self._set_cooldown(action.parameter)
                return True
        return False

    def revert_action(self, action_id: str) -> bool:
        """回滚优化动作."""
        for action in self._actions:
            if action.action_id == action_id:
                action.status = OptimizationStatus.REVERTED
                self._applied_params[action.parameter] = action.old_value
                return True
        return False

    def evaluate_action(
        self, action_id: str, before_metric: float, after_metric: float
    ) -> OptimizationResult | None:
        """评估优化动作效果."""
        action = None
        for a in self._actions:
            if a.action_id == action_id:
                action = a
                break
        if action is None:
            return None

        improvement = after_metric - before_metric
        result = OptimizationResult(
            action_id=action_id,
            area=action.area,
            parameter=action.parameter,
            old_value=action.old_value,
            new_value=action.new_value,
            before_metric=before_metric,
            after_metric=after_metric,
            improvement=improvement,
            is_successful=improvement > 0,
            observation=f"Parameter '{action.parameter}' changed from {action.old_value} to {action.new_value}: "
            f"metric {'improved' if improvement > 0 else 'declined'} by {abs(improvement):.4f}",
        )
        action.status = OptimizationStatus.EVALUATED
        self._results.append(result)
        return result

    # ── Cooldown ────────────────────────────────────────────────

    def _is_in_cooldown(self, param_name: str) -> bool:
        return self._cooldowns.get(param_name, 0) > 0

    def _set_cooldown(self, param_name: str) -> None:
        self._cooldowns[param_name] = self._policy.cooldown_cycles

    def tick_cooldowns(self) -> None:
        """推进冷却周期."""
        for param in list(self._cooldowns):
            if self._cooldowns[param] > 0:
                self._cooldowns[param] -= 1

    # ── Query ───────────────────────────────────────────────────

    def get_actions(self) -> list[OptimizationAction]:
        return list(self._actions)

    def get_results(self) -> list[OptimizationResult]:
        return list(self._results)

    def get_applied_params(self) -> dict[str, Any]:
        return dict(self._applied_params)

    def get_summary(self) -> dict[str, Any]:
        actions = self.get_actions()
        results = self.get_results()
        return {
            "total_actions": len(actions),
            "applied": len([a for a in actions if a.status == OptimizationStatus.APPLIED]),
            "reverted": len([a for a in actions if a.status == OptimizationStatus.REVERTED]),
            "evaluated": len([a for a in actions if a.status == OptimizationStatus.EVALUATED]),
            "successful_results": len([r for r in results if r.is_successful]),
            "applied_params": self.get_applied_params(),
            "cooldowns": dict(self._cooldowns),
        }

    def reset(self) -> None:
        """重置优化器."""
        self._actions.clear()
        self._results.clear()
        self._cooldowns.clear()
        self._applied_params.clear()


__all__ = ["PARAMETER_REGISTRY", "ParameterOptimizer"]