"""Growth Loop V2 — ActionExecutor.

动作执行器：将 ActionPlanner 生成的 ExecutionAction 转化为真实的平台操作。

数据流:
  ExecutionAction (待执行动作)
    + PlatformAdapter (平台适配器)
      ↓
  SafetyGate 检查 → State Machine 流转 → PlatformAdapter 执行
      ↓
  ExecutionResult (执行结果 → OutcomeEvaluator 消费)

执行状态机:
  PENDING → SAFETY_CHECK → APPROVED → EXECUTING → COMPLETED
                                              ↓
                                          FAILED → ROLLBACK → ROLLED_BACK

安全机制:
  - ApprovalLevel 0 (自动): 低风险自动通过
  - ApprovalLevel 1 (确认): 中风险需要确认
  - ApprovalLevel 2 (审批): 高风险需要审批
  - dry_run=True: 模拟执行，不调用真实 API

不是 Agent，是 Engine。与 DiagnosticEngine / ActionPlanner 同级。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from scripts.action_planner import ActionStatus, ActionType, ExecutionAction

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 状态机
# ──────────────────────────────────────────────


class ActionExecutionStatus(str, Enum):
    """执行状态机状态。"""

    PENDING = "pending"
    SAFETY_CHECK = "safety_check"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


# 状态流转规则
_VALID_TRANSITIONS: dict[str, list[str]] = {
    ActionExecutionStatus.PENDING.value: [
        ActionExecutionStatus.SAFETY_CHECK.value,
        ActionExecutionStatus.SKIPPED.value,
    ],
    ActionExecutionStatus.SAFETY_CHECK.value: [
        ActionExecutionStatus.APPROVED.value,
        ActionExecutionStatus.PENDING.value,  # 拒绝 → 返回
    ],
    ActionExecutionStatus.APPROVED.value: [
        ActionExecutionStatus.EXECUTING.value,
    ],
    ActionExecutionStatus.EXECUTING.value: [
        ActionExecutionStatus.COMPLETED.value,
        ActionExecutionStatus.FAILED.value,
    ],
    ActionExecutionStatus.FAILED.value: [
        ActionExecutionStatus.ROLLED_BACK.value,
    ],
}


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


@dataclass
class ExecutionResult:
    """执行结果 — ActionExecutor 输出。

    Attributes:
        result_id:    结果 ID
        action_id:    对应动作 ID
        strategy_id:  策略 ID (全链路追溯)
        hypothesis_id: 假设 ID (全链路追溯)
        diagnosis_id: 诊断 ID (全链路追溯)
        signal_id:    信号 ID (全链路追溯)
        status:       最终状态
        success:      是否成功
        platform_response: 平台原始响应
        actual_budget: 实际执行后的预算 (如果是 update_budget)
        error_message: 错误信息
        rollback_performed: 是否执行了回滚
        execution_time_ms: 执行耗时 (毫秒)
        dry_run:      是否为 dry-run 模式
        executed_at:  执行时间
    """

    result_id: str = ""
    action_id: str = ""
    strategy_id: str = ""
    hypothesis_id: str = ""
    diagnosis_id: str = ""
    signal_id: str = ""

    status: ActionExecutionStatus = ActionExecutionStatus.PENDING
    success: bool = False

    platform_response: dict[str, Any] = field(default_factory=dict)
    actual_budget: float | None = None
    error_message: str = ""
    rollback_performed: bool = False

    execution_time_ms: int = 0
    dry_run: bool = False
    executed_at: str = ""

    def __post_init__(self) -> None:
        if not self.result_id:
            self.result_id = f"res_{uuid4().hex[:12]}"
        if not self.executed_at:
            self.executed_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ActionExecutionStatus.COMPLETED,
            ActionExecutionStatus.ROLLED_BACK,
            ActionExecutionStatus.SKIPPED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "strategy_id": self.strategy_id,
            "hypothesis_id": self.hypothesis_id,
            "diagnosis_id": self.diagnosis_id,
            "signal_id": self.signal_id,
            "status": self.status.value,
            "success": self.success,
            "platform_response": self.platform_response,
            "actual_budget": self.actual_budget,
            "error_message": self.error_message,
            "rollback_performed": self.rollback_performed,
            "execution_time_ms": self.execution_time_ms,
            "dry_run": self.dry_run,
            "executed_at": self.executed_at,
            "is_terminal": self.is_terminal,
        }


# ──────────────────────────────────────────────
# PlatformAdapter 抽象
# ──────────────────────────────────────────────


class PlatformAdapter(ABC):
    """平台适配器 — 抽象接口。

    子类实现具体平台 (MetaAds, GoogleAds 等)。
    MockPlatformAdapter 用于测试。
    """

    @abstractmethod
    def execute(self, action: ExecutionAction) -> dict[str, Any]:
        """执行动作并返回平台响应。

        Args:
            action: 待执行的 ExecutionAction

        Returns:
            平台响应 dict，包含 status, data 等
        """
        ...

    @abstractmethod
    def verify(
        self, action: ExecutionAction, response: dict[str, Any]
    ) -> bool:
        """验证执行结果是否符合预期。

        Args:
            action: 已执行的动作
            response: execute() 返回的平台响应

        Returns:
            是否验证通过
        """
        ...

    @abstractmethod
    def rollback(
        self, action: ExecutionAction, response: dict[str, Any]
    ) -> dict[str, Any]:
        """回滚执行结果。

        Args:
            action: 需回滚的动作
            response: 原执行的平台响应

        Returns:
            回滚结果
        """
        ...


class MockPlatformAdapter(PlatformAdapter):
    """Mock 平台适配器 — 用于测试和开发。

    默认模拟成功执行，可通过 fail_action_types 配置特定类型失败。
    """

    def __init__(
        self,
        fail_action_types: set[ActionType] | None = None,
        response_delay_ms: int = 0,
    ) -> None:
        self._fail_types = fail_action_types or set()
        self._delay = response_delay_ms
        self._executed: list[dict[str, Any]] = []

    def execute(self, action: ExecutionAction) -> dict[str, Any]:
        """模拟执行。"""
        self._executed.append({
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "adset_id": action.adset_id,
            "parameters": action.parameters,
        })

        if action.action_type in self._fail_types:
            return {"status": "error", "message": "Mock execution failure"}

        if action.action_type == ActionType.UPDATE_BUDGET:
            return {
                "status": "ok",
                "message": "Budget updated successfully",
                "data": {
                    "adset_id": action.adset_id,
                    "budget": action.parameters.get("target_budget"),
                },
            }
        if action.action_type == ActionType.PAUSE_CAMPAIGN:
            return {
                "status": "ok",
                "message": "Campaign paused successfully",
                "data": {"adset_id": action.adset_id, "status": "paused"},
            }
        if action.action_type == ActionType.RESUME_CAMPAIGN:
            return {
                "status": "ok",
                "message": "Campaign resumed successfully",
                "data": {"adset_id": action.adset_id, "status": "active"},
            }

        return {"status": "ok", "message": "No action taken"}

    def verify(
        self, action: ExecutionAction, response: dict[str, Any]
    ) -> bool:
        """模拟验证。"""
        return response.get("status") == "ok"

    def rollback(
        self, action: ExecutionAction, response: dict[str, Any]
    ) -> dict[str, Any]:
        """模拟回滚。"""
        if action.action_type == ActionType.UPDATE_BUDGET:
            original = action.parameters.get("current_budget", 0.0)
            return {
                "status": "ok",
                "message": "Rolled back successfully",
                "data": {
                    "adset_id": action.adset_id,
                    "budget": original,  # 恢复到原始预算
                },
            }
        if action.action_type == ActionType.PAUSE_CAMPAIGN:
            return {
                "status": "ok",
                "message": "Campaign resumed (rollback of pause)",
                "data": {"adset_id": action.adset_id, "status": "active"},
            }
        return {"status": "ok", "message": "Rollback noop"}

    @property
    def executed_count(self) -> int:
        return len(self._executed)


# ──────────────────────────────────────────────
# SafetyGate
# ──────────────────────────────────────────────


class SafetyGate:
    """安全门控 — 执行前检查。

    检查项:
      1. 动作是否为 NOOP (跳过)
      2. 是否缺少必要字段 (adset_id)
      3. 审批等级检查
      4. 预算安全边界
    """

    # 审批等级: 0=自动通过, 1=需要确认, 2=需要审批
    APPROVAL_AUTO = 0
    APPROVAL_CONFIRM = 1
    APPROVAL_REQUIRED = 2

    def __init__(
        self,
        auto_approve_max_level: int = 0,
        min_budget: float = 20.0,
        max_budget_reduce_pct: float = 0.50,
        max_budget_increase_pct: float = 0.30,
    ) -> None:
        self._auto_max = auto_approve_max_level
        self._min_budget = min_budget
        self._max_reduce = max_budget_reduce_pct
        self._max_increase = max_budget_increase_pct

    def check(
        self, action: ExecutionAction
    ) -> tuple[bool, str]:
        """检查动作是否可以执行。

        Returns:
            (passed, reason): 通过状态和原因
        """
        # NOOP → 跳过
        if action.action_type == ActionType.NOOP:
            return (False, "NOOP action — no execution needed")

        # SKIPPED 状态 → 跳过
        if action.status == ActionStatus.SKIPPED:
            return (False, "Action status is SKIPPED")

        # 缺少 adset_id → 跳过
        if not action.adset_id:
            return (False, "Missing adset_id — cannot execute")

        # 审批等级检查
        if action.approval_level > self._auto_max:
            return (
                False,
                f"Approval level {action.approval_level} > auto-approve "
                f"max {self._auto_max} — requires manual approval",
            )

        # 预算安全检查 (仅 UPDATE_BUDGET)
        if action.action_type == ActionType.UPDATE_BUDGET:
            target = action.parameters.get("target_budget", 0.0)
            current = action.parameters.get("current_budget", 0.0)

            # 最低预算
            if target < self._min_budget:
                return (
                    False,
                    f"Target budget ${target:.2f} < minimum ${self._min_budget:.2f}",
                )

            # 最大降幅
            if current > 0:
                reduce_pct = (current - target) / current
                if reduce_pct > self._max_reduce:
                    return (
                        False,
                        f"Budget reduce {reduce_pct:.1%} > max "
                        f"{self._max_reduce:.0%}",
                    )

                # 最大升幅
                increase_pct = (target - current) / current
                if increase_pct > self._max_increase:
                    return (
                        False,
                        f"Budget increase {increase_pct:.1%} > max "
                        f"{self._max_increase:.0%}",
                    )

        return (True, "Safety check passed")


# ──────────────────────────────────────────────
# ActionExecutor 核心
# ──────────────────────────────────────────────


class ActionExecutor:
    """动作执行器 — 将 ExecutionAction 转化为真实平台操作。

    使用方式:
        adapter = MockPlatformAdapter()
        executor = ActionExecutor(adapter)
        result = executor.execute(action)

        # 批量执行
        results = executor.execute_batch(actions)

        # Dry-run 模式
        result = executor.execute(action, dry_run=True)
    """

    def __init__(
        self,
        adapter: PlatformAdapter | None = None,
        safety_gate: SafetyGate | None = None,
        reality_scores: dict[str, Any] | None = None,
        game_id_resolver: Callable[[str], str] | None = None,
    ) -> None:
        """初始化。

        Args:
            adapter: 平台适配器。为 None 时使用 MockPlatformAdapter。
            safety_gate: 安全门控。为 None 时使用默认配置。
            reality_scores: RealityGate 可信分字典 {game_id: RealityScore}。
                为 None 时不进行 RealityGate 检查 (向后兼容)。
            game_id_resolver: creative_id → game_id 解析函数。
                为 None 时 RealityGate 检查跳过 (无法解析 game_id)。
        """
        self._adapter = adapter or MockPlatformAdapter()
        self._safety_gate = safety_gate or SafetyGate()
        self._reality_scores = reality_scores
        self._game_id_resolver = game_id_resolver
        self._results: list[ExecutionResult] = []

    def execute(
        self,
        action: ExecutionAction,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """执行单个动作。

        流程:
          1. SafetyGate 检查
          2. 状态流转: PENDING → SAFETY_CHECK → APPROVED
          3. PlatformAdapter.execute()
          4. PlatformAdapter.verify()
          5. 失败时 PlatformAdapter.rollback()
          6. 返回 ExecutionResult

        Args:
            action: 待执行的动作
            dry_run: 是否为 dry-run 模式 (模拟执行，不调用真实 API)

        Returns:
            ExecutionResult
        """
        import time

        start_time = time.time()
        current_status = ActionExecutionStatus.PENDING

        # ── Step 0: Reality Gate (数据可信度门控) ──
        # 在 SafetyGate 之前检查: 数据不可信时禁止执行
        gate_reason = self._check_reality_gate(action)
        if gate_reason is not None:
            result = ExecutionResult(
                action_id=action.action_id,
                strategy_id=action.strategy_id,
                hypothesis_id=action.hypothesis_id,
                diagnosis_id=action.diagnosis_id,
                signal_id=action.signal_id,
                status=ActionExecutionStatus.SKIPPED,
                success=False,
                error_message=f"RealityGate blocked: {gate_reason}",
                dry_run=dry_run,
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
            self._results.append(result)
            logger.info(
                "ActionExecutor: %s blocked by RealityGate — %s",
                action.action_id, gate_reason,
            )
            return result

        # ── Step 1: Safety Gate ──
        current_status = ActionExecutionStatus.SAFETY_CHECK
        passed, reason = self._safety_gate.check(action)

        if not passed:
            result = ExecutionResult(
                action_id=action.action_id,
                strategy_id=action.strategy_id,
                hypothesis_id=action.hypothesis_id,
                diagnosis_id=action.diagnosis_id,
                signal_id=action.signal_id,
                status=ActionExecutionStatus.SKIPPED,
                success=False,
                error_message=f"Safety check failed: {reason}",
                dry_run=dry_run,
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
            self._results.append(result)
            logger.info(
                "ActionExecutor: %s skipped — %s",
                action.action_id, reason,
            )
            return result

        # ── Step 2: Approve ──
        current_status = ActionExecutionStatus.APPROVED

        # ── Step 3: Execute ──
        current_status = ActionExecutionStatus.EXECUTING

        try:
            if dry_run:
                # Dry-run: 模拟成功响应
                response = self._dry_run_execute(action)
            else:
                response = self._adapter.execute(action)
        except Exception as exc:
            logger.error(
                "ActionExecutor: execution failed for %s: %s",
                action.action_id, exc,
            )
            return self._handle_execution_failure(
                action, dry_run, start_time, str(exc)
            )

        # ── Step 4: Verify ──
        if not dry_run:
            verified = self._adapter.verify(action, response)
            if not verified:
                return self._handle_execution_failure(
                    action, dry_run, start_time, "Verification failed"
                )

        # ── Step 5: Complete ──
        current_status = ActionExecutionStatus.COMPLETED
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 提取实际预算 (如果是 UPDATE_BUDGET)
        actual_budget = None
        if action.action_type == ActionType.UPDATE_BUDGET:
            data = response.get("data", {})
            actual_budget = data.get("budget")

        result = ExecutionResult(
            action_id=action.action_id,
            strategy_id=action.strategy_id,
            hypothesis_id=action.hypothesis_id,
            diagnosis_id=action.diagnosis_id,
            signal_id=action.signal_id,
            status=current_status,
            success=True,
            platform_response=response,
            actual_budget=actual_budget,
            dry_run=dry_run,
            execution_time_ms=elapsed_ms,
        )
        self._results.append(result)
        logger.info(
            "ActionExecutor: %s completed in %dms (dry_run=%s)",
            action.action_id, elapsed_ms, dry_run,
        )
        return result

    def execute_batch(
        self,
        actions: list[ExecutionAction],
        dry_run: bool = False,
    ) -> list[ExecutionResult]:
        """批量执行。

        Args:
            actions: 动作列表
            dry_run: 是否为 dry-run 模式

        Returns:
            ExecutionResult 列表
        """
        results = []
        for action in actions:
            result = self.execute(action, dry_run=dry_run)
            results.append(result)
        return results

    def _check_reality_gate(
        self, action: ExecutionAction
    ) -> str | None:
        """RealityGate 数据可信度门控检查。

        在 SafetyGate 之前执行: 如果数据可信度不足 (composite < 0.5)，
        禁止执行任何正向动作，降级为 SKIPPED。

        Returns:
            None: 门控通过 (或未配置 RealityGate)
            str: 门控拒绝原因 (包含 RealityScore 详情)
        """
        # 未配置 reality_scores 或 game_id_resolver → 跳过
        if self._reality_scores is None or self._game_id_resolver is None:
            return None

        # NOOP 不需要门控
        if action.action_type == ActionType.NOOP:
            return None

        # 解析 creative_id → game_id
        game_id = self._game_id_resolver(action.creative_id)
        if not game_id:
            # 无法解析 game_id, 允许通过 (不阻塞未知 creative)
            return None

        # 查找 RealityScore
        score = self._reality_scores.get(game_id)
        if score is None:
            # 无该游戏的可信分记录, 允许通过
            return None

        # 提取 composite 分数
        composite = score.composite if hasattr(score, "composite") else float(score)

        # BLOCKED 区间 (composite < 0.5): 禁止执行
        if composite < 0.5:
            return (
                f"game={game_id} composite={composite:.3f} < 0.5 "
                f"(BLOCKED) — 数据不可信，禁止自动执行"
            )

        # APPROVE 区间 (0.5 ≤ composite < 0.8): 降级为需人工审批
        # 如果动作的 approval_level 已 >= 1 (需确认), 不额外阻塞
        if composite < 0.8 and action.approval_level < 1:
            return (
                f"game={game_id} composite={composite:.3f} 在 APPROVE 区间 "
                f"— 需人工审批 (approval_level={action.approval_level})"
            )

        # EXECUTE 区间 (composite >= 0.8): 允许自动执行
        return None

    def _dry_run_execute(
        self, action: ExecutionAction
    ) -> dict[str, Any]:
        """Dry-run 模拟执行。"""
        if action.action_type == ActionType.UPDATE_BUDGET:
            return {
                "status": "ok",
                "message": "[DRY-RUN] Budget would be updated",
                "data": {
                    "adset_id": action.adset_id,
                    "budget": action.parameters.get("target_budget"),
                },
            }
        if action.action_type == ActionType.PAUSE_CAMPAIGN:
            return {
                "status": "ok",
                "message": "[DRY-RUN] Campaign would be paused",
                "data": {"adset_id": action.adset_id, "status": "paused"},
            }
        if action.action_type == ActionType.RESUME_CAMPAIGN:
            return {
                "status": "ok",
                "message": "[DRY-RUN] Campaign would be resumed",
                "data": {"adset_id": action.adset_id, "status": "active"},
            }
        return {"status": "ok", "message": "[DRY-RUN] No action"}

    def _handle_execution_failure(
        self,
        action: ExecutionAction,
        dry_run: bool,
        start_time: float,
        error: str,
    ) -> ExecutionResult:
        """处理执行失败：尝试回滚。"""
        import time

        elapsed_ms = int((time.time() - start_time) * 1000)
        rollback_performed = False

        # 尝试回滚
        if not dry_run and action.action_type != ActionType.NOOP:
            try:
                rollback_response = self._adapter.rollback(action, {})
                rollback_performed = rollback_response.get("status") == "ok"
                logger.info(
                    "ActionExecutor: rollback %s for %s",
                    "succeeded" if rollback_performed else "failed",
                    action.action_id,
                )
            except Exception as exc:
                logger.error(
                    "ActionExecutor: rollback failed for %s: %s",
                    action.action_id, exc,
                )

        result = ExecutionResult(
            action_id=action.action_id,
            strategy_id=action.strategy_id,
            hypothesis_id=action.hypothesis_id,
            diagnosis_id=action.diagnosis_id,
            signal_id=action.signal_id,
            status=ActionExecutionStatus.ROLLED_BACK if rollback_performed
                   else ActionExecutionStatus.FAILED,
            success=False,
            error_message=error,
            rollback_performed=rollback_performed,
            dry_run=dry_run,
            execution_time_ms=elapsed_ms,
        )
        self._results.append(result)
        return result

    @property
    def results(self) -> list[ExecutionResult]:
        """获取所有执行结果。"""
        return list(self._results)

    def get_result(self, action_id: str) -> ExecutionResult | None:
        """获取指定动作的执行结果。"""
        for r in self._results:
            if r.action_id == action_id:
                return r
        return None
