"""E13.7 Real Execution Layer — 适配器组件.

将 E13.6 执行引擎从模拟执行升级为真实执行，连接 Meta Ads API、
Creative Evolution Engine 和 Adjust 数据验证。

模块:
  - adapter_models: 数据模型 (ExecutionMode, APIRequest/Response, RealExecutionResult)
  - meta_executor: Meta Ads 真实执行器
  - creative_executor: 创意生产执行器
  - adjust_verifier: Adjust 验证器
  - execution_policy: 执行策略管理
  - executor_gateway: 统一执行网关

连接:
  E13.5 Decision Engine → E13.6.2 Action Planner → E13.7 ExecutorGateway → Executor → Platform API
"""

from .adapter_models import (
    APIRequest,
    APIResponse,
    AdapterMetrics,
    ExecutionMode,
    PlatformType,
    RealExecutionResult,
    VerificationResult,
)
from .meta_executor import MetaAPIClient, MetaExecutor
from .creative_executor import CreativeAsset, CreativeExecutor, CreativeGenerationClient
from .adjust_verifier import AdjustDataClient, AdjustVerifier, VerificationConfig
from .execution_policy import (
    ACTION_RISK_MAP,
    ActionRiskLevel,
    DegradeReason,
    ExecutionPolicy,
    PolicyDecision,
    PolicyEngine,
    PolicyMode,
    create_conservative_policy,
    create_development_policy,
    create_full_auto_policy,
    create_safe_real_policy,
    create_testing_policy,
)
from .executor_gateway import (
    ACTION_PLATFORM_MAP,
    ExecutorGateway,
    GatewayResult,
    GatewayResultStatus,
)

__all__ = [
    # ── Models ──
    "APIRequest",
    "APIResponse",
    "AdapterMetrics",
    "ExecutionMode",
    "PlatformType",
    "RealExecutionResult",
    "VerificationResult",
    # ── Meta Executor ──
    "MetaAPIClient",
    "MetaExecutor",
    # ── Creative Executor ──
    "CreativeAsset",
    "CreativeExecutor",
    "CreativeGenerationClient",
    # ── Adjust Verifier ──
    "AdjustDataClient",
    "AdjustVerifier",
    "VerificationConfig",
    # ── Execution Policy ──
    "ACTION_RISK_MAP",
    "ActionRiskLevel",
    "DegradeReason",
    "ExecutionPolicy",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyMode",
    "create_conservative_policy",
    "create_development_policy",
    "create_full_auto_policy",
    "create_safe_real_policy",
    "create_testing_policy",
    # ── Executor Gateway ──
    "ACTION_PLATFORM_MAP",
    "ExecutorGateway",
    "GatewayResult",
    "GatewayResultStatus",
]