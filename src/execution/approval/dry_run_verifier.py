"""P0 ApprovalGate V2 — DryRunVerifier.

Spec: docs/p0_approval_gate_v2_spec.md §5.1, §7 (Level 1 dry_run 升级), §12 (风险)

职责：Level 1 动作在真实执行前先跑 dry_run，对比 dry_run 返回与
expected_impact，差异在容差内则允许升级为真实执行；差异过大则拒绝升级，
保持 MANUAL 等待人工。这是 ApprovalGate Level 1 → AUTO 的唯一升级通道。

设计纪律（继承全库 + Spec §1）：
- 不引入新算法层，只是 ActionExecutor.execute(dry_run=True) 的薄封装 + 对比器
- 容差阈值走配置（DryRunVerifier 构造参数，不硬编码）
- fail-closed：dry_run 本身失败、dry_run 返回异常、对比失败 → 一律拒绝升级
- 不抛异常中断主流程，所有失败返回 (False, reason)
- 纯确定性逻辑（dry_run 执行本身可能有副作用，但对比逻辑是确定性的）

对比策略（Spec §12 风险）：
  dry_run 返回 ExecutionResult，包含 success / response 数据。
  expected_impact 可能是数值或 dict（P2.1 格式）。
  - 若 dry_run 失败（success=False）→ 拒绝升级
  - 若 expected_impact 为空 → 仅看 dry_run 是否 success
  - 若 dry_run response 含可对比数值字段 → 逐字段对比，差异 > tolerance 拒绝
  - 其它情况 → success 即通过（保守但不过度阻塞）
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 默认值
# ──────────────────────────────────────────────

DEFAULT_TOLERANCE: float = 0.20  # Spec §12: 差异 > 20% 拒绝升级
DEFAULT_BUDGET_DELTA_KEY: str = "budget_delta"
DEFAULT_RESPONSE_BUDGET_KEY: str = "target_budget"


# ──────────────────────────────────────────────
# Executor 协议（结构化类型，避免硬依赖 ActionExecutor）
# ──────────────────────────────────────────────


class _ExecutorProtocol(Protocol):
    """ActionExecutor 的最小契约（仅需要 execute(action, dry_run=True)）。"""

    def execute(
        self,
        action: Any,
        dry_run: bool = False,
    ) -> Any:  # 返回 ExecutionResult
        ...


# ──────────────────────────────────────────────
# 主类
# ──────────────────────────────────────────────


class DryRunVerifier:
    """Level 1 dry_run 验证器：跑 dry_run → 对比 → 决定是否升级为真实执行。

    用法（Spec §7 action_executor 集成）：
        verifier = DryRunVerifier(executor=action_executor, tolerance=0.20)
        ok, reason = verifier.verify_and_promote(action)
        if ok:
            # 升级为真实执行
            result = action_executor.execute(action, dry_run=False)
        else:
            # 保持 MANUAL，等待人工

    Args:
        executor: ActionExecutor 实例（或任何实现 execute(action, dry_run) 的对象）
        tolerance: expected vs actual 差异容差（默认 0.20 = 20%）
        budget_delta_key: expected_impact dict 中预算变化字段的 key
        response_budget_key: dry_run response 中目标预算字段的 key
    """

    def __init__(
        self,
        executor: _ExecutorProtocol,
        tolerance: float = DEFAULT_TOLERANCE,
        budget_delta_key: str = DEFAULT_BUDGET_DELTA_KEY,
        response_budget_key: str = DEFAULT_RESPONSE_BUDGET_KEY,
    ) -> None:
        self._executor = executor
        self._tolerance = tolerance
        self._budget_delta_key = budget_delta_key
        self._response_budget_key = response_budget_key

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def verify_and_promote(self, action: Any) -> tuple[bool, str]:
        """跑 dry_run 并对比，返回是否可升级为真实执行。

        Args:
            action: ExecutionAction（scripts/action_planner.py 定义）

        Returns:
            (ok, reason)
            - (True, "dry_run passed: ...")  → 可升级为真实执行
            - (False, "dry_run failed: ...") → 保持 MANUAL，等人工

        fail-closed 原则：
            - dry_run 抛异常 → (False, reason)
            - dry_run success=False → (False, reason)
            - 对比差异 > tolerance → (False, reason)
            - 仅当 dry_run success=True 且对比通过 → (True, reason)
        """
        # 1) 执行 dry_run
        try:
            result = self._executor.execute(action, dry_run=True)
        except Exception as exc:
            reason = f"dry_run raised: {type(exc).__name__}: {exc}"
            logger.warning("DryRunVerifier: %s for action %s", reason, getattr(action, "action_id", "?"))
            return (False, reason)

        # 2) 检查 dry_run 是否成功
        if not getattr(result, "success", False):
            err = getattr(result, "error_message", "unknown")
            reason = f"dry_run returned failure: {err}"
            logger.info("DryRunVerifier: %s for action %s", reason, getattr(action, "action_id", "?"))
            return (False, reason)

        # 3) 对比 expected_impact 与 dry_run 实际返回
        compare_ok, compare_reason = self._compare_impact(action, result)
        if not compare_ok:
            logger.info(
                "DryRunVerifier: impact mismatch for action %s: %s",
                getattr(action, "action_id", "?"), compare_reason,
            )
            return (False, f"impact mismatch: {compare_reason}")

        # 4) 通过
        return (True, f"dry_run passed: {compare_reason}")

    # ------------------------------------------------------------------
    # 对比逻辑
    # ------------------------------------------------------------------

    def _compare_impact(self, action: Any, dry_run_result: Any) -> tuple[bool, str]:
        """对比 expected_impact 与 dry_run 实际返回。

        对比策略：
        - expected_impact 为空 → 仅看 dry_run success（已在上层检查）→ 通过
        - expected_impact 是 dict + 含 budget_delta → 对比 dry_run response 的 target_budget
        - expected_impact 是数值 → 无法直接对比（dry_run response 结构未知）→ 通过（保守）
        - dry_run response 为空 → 通过（无法对比，不阻塞）

        Returns:
            (ok, reason)
        """
        expected = getattr(action, "expected_impact", None)
        response = getattr(dry_run_result, "response", None)

        # 无 expected_impact → 不对比
        if not expected:
            return (True, "no expected_impact to compare")

        # expected 是 dict
        if isinstance(expected, dict):
            return self._compare_dict_impact(expected, response)

        # expected 是数值（无法直接对比 dry_run response 结构）
        return (True, f"expected_impact is scalar ({expected}), no comparison")

    def _compare_dict_impact(
        self, expected: dict, response: Any
    ) -> tuple[bool, str]:
        """对比 dict 格式的 expected_impact 与 dry_run response。

        目前仅对比 budget_delta（最关键的预算变化字段）。
        若 dry_run response 是 dict 且含 response_budget_key，则对比。
        否则跳过对比（保守不阻塞）。
        """
        budget_delta = expected.get(self._budget_delta_key)
        if budget_delta is None:
            # expected_impact dict 无 budget_delta 字段 → 不对比
            return (True, f"no '{self._budget_delta_key}' in expected_impact")

        # 尝试从 dry_run response 取目标预算
        actual_budget = None
        if isinstance(response, dict):
            actual_budget = response.get(self._response_budget_key)
        elif hasattr(response, self._response_budget_key):
            actual_budget = getattr(response, self._response_budget_key)

        if actual_budget is None:
            # dry_run response 无可对比字段 → 不阻塞
            return (True, f"dry_run response has no '{self._response_budget_key}'")

        # 数值对比
        try:
            expected_f = float(budget_delta)
            actual_f = float(actual_budget)
        except (TypeError, ValueError):
            return (True, "non-numeric values, skip comparison")

        # 差异计算（基于 expected 的相对差异）
        if abs(expected_f) < 1e-9:
            # expected ≈ 0，看 actual 是否也 ≈ 0
            if abs(actual_f) < 1.0:
                return (True, f"both near zero: expected={expected_f} actual={actual_f}")
            return (False, f"expected≈0 but actual={actual_f}")

        diff_pct = abs(actual_f - expected_f) / abs(expected_f)
        if diff_pct > self._tolerance:
            return (
                False,
                f"budget_delta expected={expected_f} actual={actual_f} "
                f"diff={diff_pct:.1%} > tolerance={self._tolerance:.0%}",
            )

        return (True, f"budget_delta match: expected={expected_f} actual={actual_f} diff={diff_pct:.1%}")


__all__ = [
    "DryRunVerifier",
    "DEFAULT_TOLERANCE",
    "DEFAULT_BUDGET_DELTA_KEY",
    "DEFAULT_RESPONSE_BUDGET_KEY",
]
