"""P2.2 Execution Provider Layer — 包入口。

对外暴露 Provider 契约、三个真实执行器（MAX / Meta / Play）、Provider Router，
以及把 P2.1 CapabilityRegistry 升级为 Action->Capability->Provider 的默认装配。
"""
from __future__ import annotations

from typing import Any, List, Optional

from ..models import ExecutionAction
from ..registry import CapabilityRegistry, Permission
from .base import BaseExecutionProvider, ExecutionProvider
from .max import MaxExecutionProvider
from .meta import MetaExecutionProvider
from .play import JsonlReleaseStore, PlayExecutionProvider, ReleaseTask
from .result import (
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_PENDING_APPROVAL,
    STATUS_SUCCESS,
    ExecutionResult,
)
from .router import (
    AllowAllRealityGate,
    ApprovalStore,
    InMemoryApprovalStore,
    JsonlApprovalStore,
    P1_7RealityGate,
    ProductionApprovalGate,
    ProviderRouter,
    RealityGatePort,
)

# Action -> Provider + 权限 的默认装配（在 P2.1 CapabilityRegistry 基础上扩展）。
# 权限含义（见 P2.1 registry）：AUTO=低风险可自动；APPROVAL=强制人工。
# 注意：生产审批门另设 allowlist（DISABLE_NETWORK / CREATE_INVESTIGATION 免审）。
DEFAULT_CAPABILITIES = [
    # MAX：关停僵尸网络（validated 优化，低风险）-> AUTO
    {"action": ExecutionAction.DISABLE_NETWORK, "provider": "max",
     "permission": Permission.AUTO},
    # MAX：改瀑布流涉及配置，风险较高 -> 强制人工
    {"action": ExecutionAction.UPDATE_WATERFALL, "provider": "max",
     "permission": Permission.APPROVAL},
    # Meta：暂停系列（买量止损，需人工确认）-> 强制人工
    {"action": ExecutionAction.PAUSE_CAMPAIGN, "provider": "meta",
     "permission": Permission.APPROVAL},
    # Play：发布工单（本就不真发布，仅生成工单，需人工后台落子）-> 强制人工
    {"action": ExecutionAction.CREATE_RELEASE, "provider": "play",
     "permission": Permission.APPROVAL},
]


def build_default_registry() -> CapabilityRegistry:
    """构造 Action->Capability->Provider 默认注册表。"""
    reg = CapabilityRegistry()
    reg.register_many(DEFAULT_CAPABILITIES)
    return reg


def build_default_providers(
    *,
    max_client: Any = None,
    meta_kwargs: Optional[dict] = None,
    play_kwargs: Optional[dict] = None,
) -> List[ExecutionProvider]:
    """构造三个默认 Provider 实例。"""
    providers: List[ExecutionProvider] = [
        MaxExecutionProvider(client=max_client),
        MetaExecutionProvider(**(meta_kwargs or {})),
        PlayExecutionProvider(**(play_kwargs or {})),
    ]
    return providers


def build_execution_router(
    *,
    registry: Optional[CapabilityRegistry] = None,
    providers: Optional[List[ExecutionProvider]] = None,
    approval_store: Optional[ApprovalStore] = None,
    reality_gate: Optional[RealityGatePort] = None,
    audit_trail: Any = None,
    authorization_gate: Any = None,
    max_client: Any = None,
    meta_kwargs: Optional[dict] = None,
    play_kwargs: Optional[dict] = None,
) -> ProviderRouter:
    """一键装配 ExecutionRequest -> Provider 的路由链。

    - 审批门默认使用 InMemoryApprovalStore（测试/单机可用），
      生产可换 JsonlApprovalStore 落盘复核
    - P2.3：传入 authorization_gate（src.execution.approval.AuthorizationGate）
      后，生产审批改走完整审批工作流（ExecutionAuthorization + Rule1~4）
    - 真实审计门默认 AllowAll（放开），接 P1.7 时传入 P1_7RealityGate
    - max_client / meta_kwargs / play_kwargs 透传给默认 Provider 构造
    """
    reg = registry or build_default_registry()
    provs = providers or build_default_providers(
        max_client=max_client, meta_kwargs=meta_kwargs, play_kwargs=play_kwargs
    )
    gate = ProductionApprovalGate(store=approval_store)
    rgate = reality_gate or AllowAllRealityGate()
    return ProviderRouter(
        reg,
        provs,
        approval_gate=gate,
        reality_gate=rgate,
        audit_trail=audit_trail,
        authorization_gate=authorization_gate,
    )


__all__ = [
    # base
    "ExecutionProvider",
    "BaseExecutionProvider",
    # result
    "ExecutionResult",
    "STATUS_SUCCESS",
    "STATUS_DRY_RUN",
    "STATUS_BLOCKED",
    "STATUS_FAILED",
    "STATUS_PENDING_APPROVAL",
    # providers
    "MaxExecutionProvider",
    "MetaExecutionProvider",
    "PlayExecutionProvider",
    "ReleaseTask",
    "JsonlReleaseStore",
    # router
    "ProviderRouter",
    "ProductionApprovalGate",
    "ApprovalStore",
    "InMemoryApprovalStore",
    "JsonlApprovalStore",
    "RealityGatePort",
    "AllowAllRealityGate",
    "P1_7RealityGate",
    # assembly
    "DEFAULT_CAPABILITIES",
    "build_default_registry",
    "build_default_providers",
    "build_execution_router",
]
