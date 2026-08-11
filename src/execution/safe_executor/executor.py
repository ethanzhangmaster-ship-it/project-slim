"""P2.4.6 SafeExecutor — 安全执行编排（P2.4 的心脏）。

链路位置：
    P2.1 Contract -> P2.2 Provider -> P2.3 Approval -> **P2.4 SafeExecutor** -> Result

PRODUCTION 必经七步：
    1) Authorization Verify（Rule 1，复用 P2.3 ExecutionAuthorization）
    2) Risk Check（生产风险硬顶）
    3) Idempotency Check（Rule 2：RUNNING/ROLLED_BACK -> BLOCK；SUCCESS -> 短路）
    4) Pre Snapshot（Rule 3：失败 -> BLOCK）
    5) Provider Execute（经注入的 execute_fn，通常是 ProviderRouter.route）
    6) Post Verify（Rule 4：失败 -> 尝试回滚；Rule 5：回滚失败 -> ESCALATE）
    7) Audit（execution.started / provider.called / execution.finished / rollback.finished）

纪律：
- SafeExecutor 是控制平面，不拥有决策权（E17.3）也不拥有授权权（P2.3）
- DRY_RUN / SIMULATION 同样走完整链路，但授权/风险闸门放行、快照走降级路径
- 幂等仅约束 PRODUCTION（重复 DRY_RUN 无害）
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.execution.safe_executor.audit import ExecutionAuditLogger
from src.execution.safe_executor.idempotency import (
    ExecutionIdempotencyStore,
    IDEM_FAILED,
    IDEM_ROLLED_BACK,
    IDEM_RUNNING,
    IDEM_SUCCESS,
    IdempotencyRecord,
    InMemoryIdempotencyStore,
    VERDICT_RETURN_EXISTING as IDEM_VERDICT_RETURN_EXISTING,
    make_idempotency_key,
)
from src.execution.safe_executor.models import (
    CTX_BLOCKED,
    CTX_EXECUTING,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_SNAPSHOTTING,
    CTX_SUCCESS,
    CTX_VALIDATING,
    CTX_VERIFYING,
    SafeExecutionContext,
    SafeExecutionOutcome,
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
)
from src.execution.safe_executor.rollback import RollbackEngine
from src.execution.safe_executor.sandbox import ExecutionSandbox
from src.execution.safe_executor.snapshot import (
    InMemorySnapshotStore,
    SnapshotError,
    Snapshotter,
    SnapshotStore,
)


def _as_str(value: Any) -> str:
    return str(getattr(value, "value", value))


class SafeExecutor:
    """执行安全沙箱编排器。

    Args:
        execute_fn        : 实际执行函数 request -> ExecutionResult
                            （通常注入 ProviderRouter.route；也可直接注入 provider.execute）
        provider_resolver : request -> provider 实例（用于 snapshot_state / rollback）
        sandbox           : 闸门集合（Rule 1~3 + Post Verify）
        idempotency_store : 幂等存储（None 则跳过幂等闸门）
        snapshot_store    : 快照存储
        rollback_engine   : 回滚引擎（含 RollbackCapability 注册表）
        audit             : 执行事件审计器
    """

    def __init__(
        self,
        execute_fn: Callable[[Any], Any],
        provider_resolver: Optional[Callable[[Any], Any]] = None,
        *,
        sandbox: Optional[ExecutionSandbox] = None,
        idempotency_store: Optional[ExecutionIdempotencyStore] = None,
        snapshot_store: Optional[SnapshotStore] = None,
        rollback_engine: Optional[RollbackEngine] = None,
        audit: Optional[ExecutionAuditLogger] = None,
        strict_snapshot: bool = False,
    ) -> None:
        self.execute_fn = execute_fn
        self.provider_resolver = provider_resolver
        self.sandbox = sandbox or ExecutionSandbox()
        self.idempotency_store = idempotency_store
        self.snapshot_store = snapshot_store or InMemorySnapshotStore()
        self.snapshotter = Snapshotter(store=self.snapshot_store, strict=strict_snapshot)
        self.rollback_engine = rollback_engine or RollbackEngine()
        self.audit = audit or ExecutionAuditLogger()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def execute(self, request: Any) -> SafeExecutionOutcome:
        context = SafeExecutionContext.from_request(request)
        is_production = context.is_production

        # ---- 1) + 2) VALIDATING：授权 + 风险 --------------------------------
        context.transition(CTX_VALIDATING)

        auth_check = self.sandbox.check_authorization(request)
        if not auth_check.ok:
            return self._blocked(context, auth_check.reason)

        risk_check = self.sandbox.check_risk(request)
        if not risk_check.ok:
            return self._blocked(context, risk_check.reason)

        # ---- 3) 幂等闸门（仅 PRODUCTION）-----------------------------------
        idem_key = ""
        if is_production and self.idempotency_store is not None:
            intent = getattr(request, "intent", None)
            idem_key = make_idempotency_key(
                action=getattr(intent, "action", ""),
                target=getattr(intent, "target_id", ""),
                parameters=getattr(intent, "expected_impact", None),
            )
            idem_check, existing = self.sandbox.check_idempotency(
                self.idempotency_store, idem_key
            )
            if not idem_check.ok:
                return self._blocked(context, idem_check.reason)
            if idem_check.verdict == IDEM_VERDICT_RETURN_EXISTING:
                # 短路：返回历史结果，绝不再触碰外部系统
                context.after_state = dict(existing.result or {})
                context.transition(CTX_SUCCESS, "幂等命中：返回历史 SUCCESS 结果")
                self.audit.execution_started(context)
                self.audit.execution_finished(context, VERDICT_RETURN_EXISTING)
                return SafeExecutionOutcome(
                    context=context,
                    result=None,
                    verdict=VERDICT_RETURN_EXISTING,
                )

        # ---- 4) SNAPSHOTTING（Rule 3）--------------------------------------
        context.transition(CTX_SNAPSHOTTING)
        provider = self._resolve_provider(request)
        try:
            snapshot = self.snapshotter.take(provider, request, context.execution_id)
        except SnapshotError as exc:
            return self._blocked(context, f"Snapshot 失败（Rule 3）：{exc}")
        context.before_state = dict(snapshot)

        # ---- 5) EXECUTING ---------------------------------------------------
        self.audit.execution_started(context)
        if is_production and self.idempotency_store is not None:
            self.idempotency_store.put(
                IdempotencyRecord(
                    key=idem_key,
                    execution_id=context.execution_id,
                    status=IDEM_RUNNING,
                )
            )
        context.transition(CTX_EXECUTING)

        try:
            result = self.execute_fn(request)
        except Exception as exc:  # noqa: BLE001 — 执行异常按 Provider 失败处理
            context.transition(CTX_FAILED, f"execute_fn raised: {exc}")
            self._mark_idempotency(is_production, idem_key, context, IDEM_FAILED)
            self.audit.execution_finished(context, VERDICT_FAILED, str(exc))
            return SafeExecutionOutcome(
                context=context, result=None, verdict=VERDICT_FAILED
            )

        self.audit.provider_called(
            context,
            str(getattr(result, "provider", "")),
            bool(getattr(result, "real_api_called", False)),
        )

        # ---- 6) VERIFYING（Rule 4 / 5）--------------------------------------
        context.transition(CTX_VERIFYING)
        post_check = self.sandbox.post_verify(result)

        if post_check.ok:
            context.after_state = dict(getattr(result, "after_state", {}) or {})
            context.transition(CTX_SUCCESS)
            self._mark_idempotency(
                is_production, idem_key, context, IDEM_SUCCESS,
                result=self._result_dict(result),
            )
            self.audit.execution_finished(context, VERDICT_EXECUTED)
            return SafeExecutionOutcome(
                context=context, result=result, verdict=VERDICT_EXECUTED
            )

        if post_check.verdict == "BLOCKED":
            # Router / Provider 内部闸门拦截：从未动手，无需回滚、不占幂等
            context.transition(CTX_BLOCKED, post_check.reason)
            self._clear_running(is_production, idem_key, context)
            self.audit.execution_finished(context, VERDICT_BLOCKED, post_check.reason)
            return SafeExecutionOutcome(
                context=context, result=result, verdict=VERDICT_BLOCKED
            )

        # ---- Rule 4：Provider 失败 -> 尝试回滚 -------------------------------
        return self._handle_failure(
            context, request, result, provider, snapshot,
            is_production, idem_key, post_check.reason,
        )

    # ------------------------------------------------------------------
    # 失败处理（Rule 4 / Rule 5）
    # ------------------------------------------------------------------
    def _handle_failure(
        self,
        context: SafeExecutionContext,
        request: Any,
        result: Any,
        provider: Any,
        snapshot: Dict[str, Any],
        is_production: bool,
        idem_key: str,
        reason: str,
    ) -> SafeExecutionOutcome:
        provider_id = str(getattr(result, "provider", "")) or str(
            getattr(provider, "provider_id", "")
        )
        intent = getattr(request, "intent", None)
        plan = self.rollback_engine.build_plan(
            provider_id=provider_id,
            action=getattr(intent, "action", ""),
            snapshot=snapshot,
            execution_id=context.execution_id,
            target=getattr(intent, "target_id", ""),
        )

        if plan is None or provider is None:
            # 无回滚能力：FAILED（不算 ESCALATE——从注册表就知道不可逆）
            context.transition(CTX_FAILED, f"{reason}；无 RollbackCapability")
            self._mark_idempotency(is_production, idem_key, context, IDEM_FAILED)
            self.audit.execution_finished(context, VERDICT_FAILED, reason)
            return SafeExecutionOutcome(
                context=context, result=result, verdict=VERDICT_FAILED
            )

        rollback_result = self.rollback_engine.execute(plan, provider)
        self.audit.rollback_finished(context, rollback_result)

        if rollback_result.ok:
            context.transition(CTX_ROLLED_BACK, f"{reason}；已回滚")
            self._mark_idempotency(is_production, idem_key, context, IDEM_ROLLED_BACK)
            self.audit.execution_finished(context, VERDICT_ROLLED_BACK, reason)
            return SafeExecutionOutcome(
                context=context,
                result=result,
                verdict=VERDICT_ROLLED_BACK,
                rollback=rollback_result.to_dict(),
            )

        # Rule 5：回滚失败 -> ESCALATE
        context.transition(
            CTX_FAILED, f"{reason}；回滚失败需人工介入：{rollback_result.error}"
        )
        self._mark_idempotency(is_production, idem_key, context, IDEM_FAILED)
        self.audit.execution_finished(
            context, VERDICT_ESCALATED, rollback_result.error
        )
        return SafeExecutionOutcome(
            context=context,
            result=result,
            verdict=VERDICT_ESCALATED,
            rollback=rollback_result.to_dict(),
            escalated=True,
        )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _resolve_provider(self, request: Any) -> Any:
        if self.provider_resolver is None:
            return None
        try:
            return self.provider_resolver(request)
        except Exception:  # noqa: BLE001 — 解析失败按无 Provider 处理
            return None

    def _blocked(self, context: SafeExecutionContext, reason: str) -> SafeExecutionOutcome:
        context.transition(CTX_BLOCKED, reason)
        self.audit.execution_finished(context, VERDICT_BLOCKED, reason)
        return SafeExecutionOutcome(
            context=context, result=None, verdict=VERDICT_BLOCKED
        )

    def _mark_idempotency(
        self,
        is_production: bool,
        key: str,
        context: SafeExecutionContext,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not (is_production and self.idempotency_store is not None and key):
            return
        self.idempotency_store.put(
            IdempotencyRecord(
                key=key,
                execution_id=context.execution_id,
                status=status,
                result=result or {},
            )
        )

    def _clear_running(
        self, is_production: bool, key: str, context: SafeExecutionContext
    ) -> None:
        """BLOCKED（未动手）不应留下 RUNNING 占位：标记 FAILED 允许后续重试。"""
        self._mark_idempotency(is_production, key, context, IDEM_FAILED)

    @staticmethod
    def _result_dict(result: Any) -> Dict[str, Any]:
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return dict(result) if isinstance(result, dict) else {}


# ---------------------------------------------------------------------------
# 工厂：与 P2.2 Router / P2.3 AuthorizationGate 组装
# ---------------------------------------------------------------------------


def build_safe_executor(
    router: Any,
    *,
    idempotency_store: Optional[ExecutionIdempotencyStore] = None,
    snapshot_store: Optional[SnapshotStore] = None,
    rollback_engine: Optional[RollbackEngine] = None,
    audit: Optional[ExecutionAuditLogger] = None,
    sandbox: Optional[ExecutionSandbox] = None,
    strict_snapshot: bool = False,
) -> SafeExecutor:
    """从 P2.2 ProviderRouter 组装 SafeExecutor。

    - execute_fn = router.route（保留 Router 的注册表 / Reality Gate / 授权门）
    - provider_resolver 复用 Router 的 registry+providers 做 Provider 定位
    - idempotency_store 缺省 InMemory（生产建议 JsonlIdempotencyStore）
    """

    def _resolver(request: Any) -> Any:
        try:
            action = request.intent.action
            for pid in router.registry.providers_for(action):
                if pid in router.providers:
                    return router.providers[pid]
        except Exception:  # noqa: BLE001
            return None
        return None

    return SafeExecutor(
        execute_fn=router.route,
        provider_resolver=_resolver,
        sandbox=sandbox,
        idempotency_store=idempotency_store or InMemoryIdempotencyStore(),
        snapshot_store=snapshot_store,
        rollback_engine=rollback_engine,
        audit=audit,
        strict_snapshot=strict_snapshot,
    )


__all__ = [
    "SafeExecutor",
    "build_safe_executor",
]
