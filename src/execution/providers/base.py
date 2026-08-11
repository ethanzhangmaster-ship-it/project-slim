"""P2.2 Execution Provider Layer — Provider 契约（Protocol）。

定义所有真实世界执行器（MAX / Meta / Play ...）必须实现的接口。
本层不关心「为什么执行」（那是 E17.3 + P2.1 的事），只关心：

    ExecutionRequest ->（安全门）-> Provider.execute -> ExecutionResult

设计纪律：
- 所有 Provider 默认 DRY_RUN；仅当 request.mode == PRODUCTION 才尝试真实 API
- DRY_RUN 路径 real_api_called 必须恒 False
- PRODUCTION 路径只要发起外部调用即 real_api_called = True（成败不论）
- Provider 自身不做审批决策，审批由 ProviderRouter 的 ProductionApprovalGate 负责
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from ..models import ExecutionIntent, ExecutionRequest
from .result import (
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_SUCCESS,
    ExecutionResult,
)


@runtime_checkable
class ExecutionProvider(Protocol):
    """真实世界执行器契约。

    任何 Provider 必须暴露：
        provider_id : 唯一标识（"max" / "meta" / "play" ...）
        can_execute(intent) -> bool : 该意图是否归本 Provider 落地
        execute(request) -> ExecutionResult : 执行（守 DRY_RUN/PRODUCTION 纪律）
    """

    provider_id: str

    def can_execute(self, intent: ExecutionIntent) -> bool:
        ...

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class BaseExecutionProvider:
    """可被继承的 Provider 骨架，提供通用结果构造与模式分支。

    子类只需：
        1) 设置 ``provider_id``
        2) 实现 ``can_execute``
        3) 实现 ``_do_real``（PRODUCTION 真正调用外部系统）
    基类负责 DRY_RUN / 拦截 / 结果包装，保证 real_api_called 纪律不出错。
    """

    provider_id: str = "base"

    # 子类可重写：本 Provider 支持的动作集合
    supported_actions = ()

    # ------------------------------------------------------------------
    # 协议实现
    # ------------------------------------------------------------------
    def can_execute(self, intent: ExecutionIntent) -> bool:
        return intent.action in self.supported_actions

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        intent = request.intent
        if not self.can_execute(intent):
            return self._blocked(
                request,
                f"{self.provider_id} 不支持动作 {intent.action.value}",
            )

        # DRY_RUN / SIMULATION：只回显意图，绝不碰外部系统
        if request.mode in ("dry_run", "simulation"):
            return self._dry_run(request)

        # PRODUCTION：真正尝试外部调用
        try:
            return self._do_real(request)
        except Exception as exc:  # noqa: BLE001 — 真实调用异常须转成失败结果
            return self._failed(request, f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # 子类钩子
    # ------------------------------------------------------------------
    def _do_real(self, request: ExecutionRequest) -> ExecutionResult:
        """PRODUCTION 模式真正落地动作（子类必须实现）。"""
        raise NotImplementedError(
            f"{self.provider_id} 未实现 _do_real（PRODUCTION 执行路径）"
        )

    # ------------------------------------------------------------------
    # P2.4 Safe Executor 钩子（快照 / 回滚）
    # ------------------------------------------------------------------
    def snapshot_state(self, request: ExecutionRequest) -> Dict[str, Any]:
        """执行前状态快照（P2.4 Rule 3 的数据来源）。

        默认实现：意图回显快照（目标 / 动作 / Provider）。
        真实 Provider 应重写为「读外部系统当前状态」（只读，不写）。
        """
        intent = request.intent
        return {
            "provider": self.provider_id,
            "target_id": intent.target_id,
            "action": intent.action.value,
            "domain": intent.domain.value,
            "mode": request.mode.value,
        }

    def rollback(self, plan: Any) -> Dict[str, Any]:
        """执行回滚动作（P2.4 Rule 4）。返回 {"success": bool, ...}。

        默认实现：dry-run 式回显（success=True，不触外部系统）。
        真实 Provider 应重写为「调用外部系统执行 rollback_action」，
        并遵守 real_api_called 纪律（PRODUCTION 真调才 True）。
        """
        return {
            "success": True,
            "provider": self.provider_id,
            "rollback_action": str(getattr(plan, "rollback_action", "")),
            "restored_state": dict(getattr(plan, "snapshot", {}) or {}),
            "real_api_called": False,
        }

    # ------------------------------------------------------------------
    # 结果构造辅助
    # ------------------------------------------------------------------
    def _blocked(self, request: ExecutionRequest, reason: str) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_BLOCKED,
            real_api_called=False,
            before_state={},
            after_state={},
            error=reason,
        )

    def _dry_run(self, request: ExecutionRequest) -> ExecutionResult:
        """DRY_RUN 默认实现：回显期望后态，real_api_called 恒 False。"""
        intent = request.intent
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_DRY_RUN,
            real_api_called=False,
            before_state={"mode": "dry_run"},
            after_state={
                "intended_action": intent.action.value,
                "target_id": intent.target_id,
                "domain": intent.domain.value,
            },
        )

    def _ok(
        self,
        request: ExecutionRequest,
        after_state: Dict[str, Any],
        before_state: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_SUCCESS,
            real_api_called=True,
            before_state=before_state or {},
            after_state=after_state,
        )

    def _failed(self, request: ExecutionRequest, reason: str) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_FAILED,
            real_api_called=True,  # 已真正尝试外部调用
            before_state={},
            after_state={},
            error=reason,
        )


__all__ = [
    "ExecutionProvider",
    "BaseExecutionProvider",
]
