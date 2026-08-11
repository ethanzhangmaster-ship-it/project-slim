"""P2.2 Execution Provider Layer — Provider Router + 生产审批门 + P1.7 真实审计门。

职责：把一份 ExecutionRequest 路由到正确的真实执行器（MAX / Meta / Play），
并在执行前按用户硬性纪律串起两道门：

    ExecutionRequest
        │
        ├─(1) 注册表已知动作 / Provider 已注册？  否则 BLOCK（未知动作禁止执行）
        ├─(2) Provider.can_execute(intent)？       否则 BLOCK
        ├─(3) P1.7 Reality Gate（真实数据可信度）  不达标 BLOCK
        └─(4) ProductionApprovalGate（生产审批门） 生产模式未审批 BLOCK
                │
                ▼
            Provider.execute -> ExecutionResult

设计要点：
- 消费 P2.1 的 CapabilityRegistry（Action -> Provider 映射）做路由，不重写注册表
- ProductionApprovalGate：mode==PRODUCTION 必须审批，**除非**动作在 allowlist
  （DISABLE_NETWORK / CREATE_INVESTIGATION，用户验收口径）
- P1.7 真实审计门：接入 src.growth_reality.validation.gate.RealityGate，
  单游戏 RealityScore < 0.5 直接 BLOCK（缺省关掉时使用 AllowAll 透传）
- 所有执行落 EP0 AuditTrail（executions.jsonl + approvals.jsonl）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from ..models import ExecutionAction, ExecutionMode, ExecutionRequest
from ..registry import CapabilityRegistry
from .base import ExecutionProvider
from .result import (
    STATUS_BLOCKED,
    STATUS_PENDING_APPROVAL,
    ExecutionResult,
)

# 生产模式免人工审批的动作白名单（用户验收口径）。
# DISABLE_NETWORK=关停僵尸网络（ validated 优化，低风险）；
# CREATE_INVESTIGATION=仅生成调查任务（无真实写动作）。
PRODUCTION_AUTO_ALLOWLIST: Tuple[ExecutionAction, ...] = (
    ExecutionAction.DISABLE_NETWORK,
    ExecutionAction.CREATE_INVESTIGATION,
)


# --------------------------------------------------------------------------- #
# 审批存储（EP0 风格，可注入）
# --------------------------------------------------------------------------- #
@runtime_checkable
class ApprovalStore(Protocol):
    """生产审批记录的可注入接口。"""

    def is_approved(self, request_id: str) -> bool:
        ...


class InMemoryApprovalStore:
    """测试 / 运行时默认审批存储（进程内集合）。"""

    def __init__(self) -> None:
        self._approved: set = set()

    def mark_approved(self, request_id: str) -> None:
        self._approved.add(request_id)

    def is_approved(self, request_id: str) -> bool:
        return request_id in self._approved


class JsonlApprovalStore:
    """EP0 风格：审批决议落盘 JSONL（append-only），可跨进程复核。"""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def record_approval(
        self, request_id: str, approver: str, note: str = ""
    ) -> None:
        rec = {
            "request_id": request_id,
            "approver": approver,
            "approved": True,
            "note": note,
            "ts": _now_iso(),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def is_approved(self, request_id: str) -> bool:
        if not self.path.exists():
            return False
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("request_id") == request_id and rec.get("approved"):
                return True
        return False


# --------------------------------------------------------------------------- #
# 生产审批门
# --------------------------------------------------------------------------- #
class ProductionApprovalGate:
    """mode==PRODUCTION 必须人工审批，allowlist 动作除外。"""

    def __init__(
        self,
        store: Optional[ApprovalStore] = None,
        allowlist: Tuple[ExecutionAction, ...] = PRODUCTION_AUTO_ALLOWLIST,
    ) -> None:
        self.store = store
        self.allowlist = set(allowlist)

    def check(self, request: ExecutionRequest) -> Tuple[bool, str]:
        if request.mode != ExecutionMode.PRODUCTION:
            return True, "非生产模式，无需审批"
        action = request.intent.action
        if action in self.allowlist:
            return True, f"动作 {action.value} 在 Production 免审批白名单"
        if self.store is not None and self.store.is_approved(request.request_id):
            return True, "已记录人工审批通过"
        return False, f"生产模式动作 {action.value} 需要人工审批（未提供批准）"


# --------------------------------------------------------------------------- #
# P1.7 真实审计门（可注入）
# --------------------------------------------------------------------------- #
@runtime_checkable
class RealityGatePort(Protocol):
    """真实数据可信度门，可注入。返回 (放行?, 原因)。"""

    def check(self, request: ExecutionRequest) -> Tuple[bool, str]:
        ...


class AllowAllRealityGate:
    """未配置 P1.7 时的透传门（默认放行，便于 DRY_RUN / 测试）。"""

    def check(self, request: ExecutionRequest) -> Tuple[bool, str]:
        return True, "未配置真实审计门，默认放行"


class P1_7RealityGate:
    """包装 P1.7 RealityGate：单游戏 RealityScore < 0.5 直接 BLOCK。

    调用方在路由前用 P1.7 RealityAuditor 算好每游戏 composite 分，注入 scores。
    """

    def __init__(self, scores: Optional[Dict[str, float]] = None) -> None:
        from src.growth_reality.validation.gate import RealityGate

        self._gate = RealityGate
        self._scores = scores or {}

    def check(self, request: ExecutionRequest) -> Tuple[bool, str]:
        score = float(self._scores.get(request.intent.target_id, 0.0))
        if self._gate.can_approve(score):
            return True, f"RealityScore={score:.2f}>=0.5，真实数据可信"
        return False, f"RealityScore={score:.2f}<0.5，真实数据不足，禁止执行"


# --------------------------------------------------------------------------- #
# Provider Router
# --------------------------------------------------------------------------- #
class ProviderRouter:
    """ExecutionRequest -> 路由 -> 双门 -> Provider.execute。"""

    def __init__(
        self,
        registry: CapabilityRegistry,
        providers: List[ExecutionProvider],
        *,
        approval_gate: Optional[ProductionApprovalGate] = None,
        reality_gate: Optional[RealityGatePort] = None,
        audit_trail: Any = None,
        authorization_gate: Any = None,
    ) -> None:
        self.registry = registry
        self.providers: Dict[str, ExecutionProvider] = {
            p.provider_id: p for p in providers
        }
        self.approval_gate = approval_gate or ProductionApprovalGate()
        self.reality_gate = reality_gate or AllowAllRealityGate()
        self.audit_trail = audit_trail
        # P2.3.6：注入 AuthorizationGate 后，生产审批改走完整审批工作流
        # （ExecutionAuthorization + Rule1~4），替代简单布尔审批门。
        self.authorization_gate = authorization_gate

    # ------------------------------------------------------------------
    # 路由
    # ------------------------------------------------------------------
    def route(self, request: ExecutionRequest) -> ExecutionResult:
        intent = request.intent

        # (1) 注册表必须登记该动作
        if not self.registry.is_known(intent.action):
            return self._blocked(
                request, f"未知动作 {intent.action.value}：未在 CapabilityRegistry 登记"
            )

        # (2) 必须有已注册的 Provider
        provider = self._resolve(intent.action)
        if provider is None:
            return self._blocked(
                request, f"动作 {intent.action.value} 无可用 Provider"
            )

        # (3) Provider 自身能力校验
        if not provider.can_execute(intent):
            return self._blocked(
                request,
                f"{provider.provider_id} 无法执行 {intent.action.value}",
            )

        # (4) P1.7 真实审计门
        ok, reason = self.reality_gate.check(request)
        if not ok:
            return self._blocked(request, f"真实审计门拦截：{reason}")

        # (5) 生产审批门
        # P2.3.6：优先走 AuthorizationGate（完整审批工作流 + Rule1~4）；
        # 未注入时向后兼容走 P2.2 ProductionApprovalGate。
        if self.authorization_gate is not None:
            ok, reason = self.authorization_gate.check(request)
        else:
            ok, reason = self.approval_gate.check(request)
        if not ok:
            # 用户验收口径：生产模式未审批 = BLOCK（无法执行）
            self._audit_block(request, provider.provider_id, reason)
            return ExecutionResult(
                request_id=request.request_id,
                provider=provider.provider_id,
                status=STATUS_BLOCKED,
                real_api_called=False,
                before_state={},
                after_state={},
                error=f"生产审批门拦截：{reason}",
            )

        # (6) 执行
        result = provider.execute(request)
        self._audit_execution(request, result)
        return result

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _resolve(self, action: ExecutionAction) -> Optional[ExecutionProvider]:
        """按注册表 Action->Provider 映射选第一个可用 Provider。"""
        for pid in self.registry.providers_for(action):
            if pid in self.providers:
                return self.providers[pid]
        return None

    def _blocked(self, request: ExecutionRequest, reason: str) -> ExecutionResult:
        self._audit_block(request, "router", reason)
        return ExecutionResult(
            request_id=request.request_id,
            provider="router",
            status=STATUS_BLOCKED,
            real_api_called=False,
            before_state={},
            after_state={},
            error=reason,
        )

    # ------------------------------------------------------------------
    # 审计
    # ------------------------------------------------------------------
    def _audit_block(self, request: ExecutionRequest, provider: str, reason: str) -> None:
        if self.audit_trail is None:
            return
        try:
            from audit.trail import ExecutionRecord

            self.audit_trail.record_execution(
                ExecutionRecord(
                    decision_id=request.intent.decision_id,
                    agent=f"provider_router:{provider}",
                    action=request.intent.action.value,
                    success=False,
                    duration_ms=0.0,
                    error=reason,
                )
            )
        except Exception:
            # 审计失败绝不能阻断主流程
            pass

    def _audit_execution(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> None:
        if self.audit_trail is None:
            return
        try:
            from audit.trail import ExecutionRecord

            self.audit_trail.record_execution(
                ExecutionRecord(
                    decision_id=request.intent.decision_id,
                    agent=f"provider_router:{result.provider}",
                    action=request.intent.action.value,
                    success=result.ok,
                    duration_ms=0.0,
                    error=result.error or "",
                )
            )
        except Exception:
            pass


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "PRODUCTION_AUTO_ALLOWLIST",
    "ApprovalStore",
    "InMemoryApprovalStore",
    "JsonlApprovalStore",
    "ProductionApprovalGate",
    "RealityGatePort",
    "AllowAllRealityGate",
    "P1_7RealityGate",
    "ProviderRouter",
]
