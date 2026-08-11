"""E15.3.2 Executor Bridge — 连接 Decision Loop 与 E15.1 Workflow.

将选中的动作通过 E15.1 Workflow Engine 执行。

流程:
  SelectedAction
      ↓
  ExecutorBridge.execute(action, context)
      ↓
  E15.1 Workflow Engine
      ↓
  ExecutionResult
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .models import DecisionCycle, CycleOutcome


# ═══════════════════════════════════════════════════════════════
# Executor Bridge
# ═══════════════════════════════════════════════════════════════


class ExecutorBridge:
    """E15.3.2 Executor 桥接器 — 连接 Decision Loop 与 E15.1 Workflow.

    将选中的动作转换为执行结果。

    用法:
        bridge = ExecutorBridge(workflow_engine)
        result = bridge.execute(action, cycle)
    """

    def __init__(self, workflow_engine: Any = None):
        """初始化.

        Args:
            workflow_engine: E15.1 Workflow Engine 实例 (可选)
        """
        self._workflow_engine = workflow_engine
        self._execution_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._execution_history: list[dict[str, Any]] = []

    # ── Properties ──────────────────────────────────────────────

    @property
    def execution_count(self) -> int:
        return self._execution_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_rate(self) -> float:
        if self._execution_count == 0:
            return 0.0
        return round(self._success_count / self._execution_count, 4)

    # ── Core: Execute ───────────────────────────────────────────

    def execute(
        self,
        action: dict[str, Any],
        cycle: DecisionCycle,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行动作.

        Args:
            action:  选中的动作
            cycle:   当前决策周期
            context: 执行上下文 (可选)

        Returns:
            dict: 执行结果
        """
        self._execution_count += 1

        if not action or action.get("action_type") == "do_nothing":
            result = {
                "execution_id": str(uuid.uuid4()),
                "action_type": "do_nothing",
                "status": "skipped",
                "message": "No action to execute",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            cycle.execution_result = result
            self._execution_history.append(result)
            return result

        try:
            # 如果有 Workflow Engine，通过它执行
            if self._workflow_engine is not None:
                result = self._execute_via_workflow(action, cycle, context)
            else:
                result = self._execute_simulated(action, cycle, context)

            cycle.execution_result = result
            self._success_count += 1
            self._execution_history.append(result)
            return result

        except Exception as e:
            self._failure_count += 1
            result = {
                "execution_id": str(uuid.uuid4()),
                "action_type": action.get("action_type", "unknown"),
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            cycle.execution_result = result
            cycle.error = str(e)
            self._execution_history.append(result)
            return result

    def _execute_via_workflow(
        self,
        action: dict[str, Any],
        cycle: DecisionCycle,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """通过 E15.1 Workflow Engine 执行."""
        try:
            wf_result = self._workflow_engine.execute_workflow(
                workflow_type=action.get("action_type", "unknown"),
                params={**action, "cycle_id": cycle.cycle_id},
                context=context or {},
            )
            return {
                "execution_id": str(uuid.uuid4()),
                "action_type": action.get("action_type", "unknown"),
                "status": "executed",
                "workflow_result": wf_result if isinstance(wf_result, dict) else {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            # Workflow 执行失败，降级为模拟执行
            return self._execute_simulated(action, cycle, context)

    def _execute_simulated(
        self,
        action: dict[str, Any],
        cycle: DecisionCycle,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """模拟执行 (当 Workflow Engine 不可用时)."""
        action_type = action.get("action_type", "unknown")
        confidence = action.get("confidence", 0.5)

        # 高置信度动作偏向成功
        simulated_success = confidence >= 0.3

        return {
            "execution_id": str(uuid.uuid4()),
            "action_type": action_type,
            "status": "executed" if simulated_success else "failed",
            "simulated": True,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def execute_batch(
        self,
        actions: list[dict[str, Any]],
        cycle: DecisionCycle,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """批量执行动作.

        Args:
            actions: 动作列表
            cycle:   当前决策周期
            context: 执行上下文

        Returns:
            list[dict]: 执行结果列表
        """
        return [self.execute(action, cycle, context) for action in actions]

    # ── Rollback ────────────────────────────────────────────────

    def rollback(
        self, cycle: DecisionCycle, reason: str = ""
    ) -> dict[str, Any]:
        """回滚执行.

        Args:
            cycle:  决策周期
            reason: 回滚原因

        Returns:
            dict: 回滚结果
        """
        result = {
            "execution_id": str(uuid.uuid4()),
            "action_type": "rollback",
            "status": "rolled_back",
            "reason": reason,
            "original_action": cycle.selected_action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cycle.execution_result = result
        self._execution_history.append(result)
        return result

    # ── Query ───────────────────────────────────────────────────

    def get_execution_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取执行历史."""
        return self._execution_history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": self.success_rate,
            "has_workflow_engine": self._workflow_engine is not None,
        }

    def reset(self) -> None:
        """重置统计."""
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._execution_history = []


__all__ = ["ExecutorBridge"]