"""E15.0.4 Production Worker — 动作执行器.

执行 GrowthAction，支持:
  - 同步/异步执行
  - 执行结果追踪
  - 错误处理
  - 回滚支持

E15.0.8 升级: 支持 StorageService 持久化执行记录到 PostgreSQL.
E15.0.9 升级: 支持 ExecutionRouter 统一路由到平台适配器.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.service import StorageService
    from ..execution.adapter_router import ExecutionRouter
    from ..execution.adapter_base import AdapterExecutionResult
    from ..execution.growth_action import GrowthAction as E15GrowthAction

logger = logging.getLogger(__name__)


class WorkerState(str, Enum):
    """Worker 状态."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"


class ExecutionStatus(str, Enum):
    """执行状态."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ExecutionResult:
    """执行结果."""
    result_id: str = field(default_factory=lambda: f"result_{uuid.uuid4().hex[:12]}")
    action_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0
    rollback_record_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "rollback_record_id": self.rollback_record_id,
            "timestamp": self.timestamp,
        }


class ProductionWorker:
    """生产 Worker — 执行 GrowthAction.

    用法:
        worker = ProductionWorker()
        worker.register_executor("update_budget", my_executor_fn)
        result = worker.execute(action)

    E15.0.8 持久化:
        worker = ProductionWorker(storage=storage)
        result = worker.execute(...)  # 自动双写 (内存 + PostgreSQL)
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        storage: "StorageService | None" = None,
        router: "ExecutionRouter | None" = None,
    ):
        self._max_concurrent = max_concurrent
        self._storage = storage
        self._router = router
        self._state: WorkerState = WorkerState.IDLE
        self._executors: dict[str, Any] = {}
        self._results: list[ExecutionResult] = []
        self._active_count: int = 0
        self._total_executed: int = 0
        self._total_success: int = 0
        self._total_failed: int = 0

    # ── Properties ───────────────────────────────────────────

    @property
    def state(self) -> WorkerState:
        return self._state

    @property
    def is_idle(self) -> bool:
        return self._state == WorkerState.IDLE

    @property
    def is_available(self) -> bool:
        return self._active_count < self._max_concurrent

    @property
    def success_rate(self) -> float:
        total = self._total_success + self._total_failed
        if total == 0:
            return 1.0
        return self._total_success / total

    # ── Executor Registration ────────────────────────────────

    def register_executor(self, action_type: str, executor: Any) -> None:
        """注册动作执行器.

        executor 签名: def executor(params: dict) -> dict
        """
        self._executors[action_type] = executor

    def unregister_executor(self, action_type: str) -> bool:
        return self._executors.pop(action_type, None) is not None

    @property
    def registered_actions(self) -> list[str]:
        return list(self._executors.keys())

    # ── Execute ──────────────────────────────────────────────

    def execute(
        self,
        action_type: str,
        params: dict[str, Any] | None = None,
        action_id: str = "",
    ) -> ExecutionResult:
        """执行一个动作.

        Args:
            action_type: 动作类型
            params:      动作参数
            action_id:   动作 ID

        Returns:
            ExecutionResult
        """
        params = params or {}

        if not self.is_available:
            return ExecutionResult(
                action_id=action_id,
                status=ExecutionStatus.FAILED,
                error="Worker at max capacity",
            )

        if action_type not in self._executors:
            return ExecutionResult(
                action_id=action_id,
                status=ExecutionStatus.FAILED,
                error=f"No executor registered for action type: {action_type}",
            )

        self._state = WorkerState.BUSY
        self._active_count += 1
        self._total_executed += 1

        start_time = datetime.now(timezone.utc)

        try:
            executor = self._executors[action_type]
            output = executor(params)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result = ExecutionResult(
                action_id=action_id,
                status=ExecutionStatus.SUCCESS,
                output=output if isinstance(output, dict) else {"result": output},
                duration_ms=duration,
            )
            self._total_success += 1
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result = ExecutionResult(
                action_id=action_id,
                status=ExecutionStatus.FAILED,
                error=str(e),
                duration_ms=duration,
            )
            self._total_failed += 1

        self._results.append(result)
        self._active_count -= 1

        if self._active_count == 0:
            self._state = WorkerState.IDLE

        # E15.0.8: 持久化执行记录到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.executions.save(self._result_to_dict(result, action_type, params))
            except Exception as e:
                logger.warning(f"Failed to persist execution result to PostgreSQL: {e}")

        return result

    def execute_batch(
        self,
        actions: list[dict[str, Any]],
    ) -> list[ExecutionResult]:
        """批量执行动作.

        Args:
            actions: [{"action_type": str, "params": dict, "action_id": str}, ...]

        Returns:
            ExecutionResult 列表
        """
        results: list[ExecutionResult] = []
        for action in actions:
            result = self.execute(
                action_type=action.get("action_type", ""),
                params=action.get("params", {}),
                action_id=action.get("action_id", ""),
            )
            results.append(result)
        return results

    # ── Results ──────────────────────────────────────────────

    def get_results(self, limit: int = 50) -> list[ExecutionResult]:
        return self._results[-limit:]

    def get_failed(self) -> list[ExecutionResult]:
        return [r for r in self._results if r.status == ExecutionStatus.FAILED]

    def get_by_action(self, action_id: str) -> ExecutionResult | None:
        for r in reversed(self._results):
            if r.action_id == action_id:
                return r
        return None

    # ── E15.0.9: ExecutionRouter 集成 ────────────────────────

    def execute_via_router(
        self,
        action: "E15GrowthAction",
    ) -> "AdapterExecutionResult":
        """E15.0.9: 通过 ExecutionRouter 执行 GrowthAction.

        将动作路由到正确的平台适配器 (Meta / Google Play / Creative / Adjust)，
        自动经过 Safety Governor → Adapter → External API 完整链路。

        Args:
            action: E15.0.9 GrowthAction

        Returns:
            AdapterExecutionResult: 统一执行结果
        """
        if self._router is None:
            from ..execution.adapter_base import AdapterExecutionResult
            return AdapterExecutionResult.failure_result(
                action,
                error="No ExecutionRouter configured",
            )

        if not self.is_available:
            from ..execution.adapter_base import AdapterExecutionResult
            return AdapterExecutionResult.failure_result(
                action,
                error="Worker at max capacity",
            )

        self._state = WorkerState.BUSY
        self._active_count += 1
        self._total_executed += 1

        try:
            result = self._router.execute(action)
            if result.success:
                self._total_success += 1
            else:
                self._total_failed += 1

            # E15.0.8: 持久化执行记录到 PostgreSQL
            if self._storage is not None:
                try:
                    self._storage.executions.save({
                        "result_id": result.execution_id,
                        "execution_id": result.execution_id,
                        "action_id": result.action_id,
                        "action_type": result.action_type.value,
                        "params": action.parameters,
                        "status": result.status.value,
                        "output": result.to_dict(),
                        "error": result.error,
                        "duration_ms": 0,
                        "rollback_record_id": "",
                    })
                except Exception as e:
                    logger.warning(f"Failed to persist execution result: {e}")

            return result

        except Exception as e:
            self._total_failed += 1
            from ..execution.adapter_base import AdapterExecutionResult
            return AdapterExecutionResult.failure_result(
                action, error=str(e),
            )
        finally:
            self._active_count -= 1
            if self._active_count == 0:
                self._state = WorkerState.IDLE

    def rollback_via_router(
        self,
        action: "E15GrowthAction",
        result: "AdapterExecutionResult",
    ) -> "AdapterExecutionResult":
        """E15.0.9: 通过 ExecutionRouter 回滚动作."""
        if self._router is None:
            from ..execution.adapter_base import AdapterExecutionResult
            return AdapterExecutionResult.failure_result(
                action, error="No ExecutionRouter configured",
            )
        return self._router.rollback(action, result)

    # ── Statistics ───────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "active_count": self._active_count,
            "max_concurrent": self._max_concurrent,
            "total_executed": self._total_executed,
            "total_success": self._total_success,
            "total_failed": self._total_failed,
            "success_rate": self.success_rate,
            "registered_actions": self.registered_actions,
            "recent_results": [r.to_dict() for r in self._results[-5:]],
        }

    def reset(self) -> None:
        self._state = WorkerState.IDLE
        self._results.clear()
        self._active_count = 0
        self._total_executed = 0
        self._total_success = 0
        self._total_failed = 0

    def _result_to_dict(
        self, result: ExecutionResult, action_type: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """将 ExecutionResult 转换为 ExecutionRepository 所需的 dict 格式."""
        return {
            "result_id": result.result_id,
            "execution_id": result.result_id,
            "action_id": result.action_id,
            "action_type": action_type,
            "params": params,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "rollback_record_id": result.rollback_record_id,
        }