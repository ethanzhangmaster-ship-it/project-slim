"""E13.7 Real Execution Models — 真实执行层数据模型.

定义与外部平台交互的模型:
  - ExecutionMode: 执行模式 (MOCK / DRY_RUN / REAL / APPROVAL_REQUIRED)
  - APIRequest: 标准化 API 请求
  - APIResponse: 标准化 API 响应
  - RealExecutionResult: 真实执行结果 (扩展 ExecutionResult)
  - VerificationResult: 验证结果 (Adjust 等)
  - AdapterMetrics: 适配器执行指标

连接:
  E13.7 Real Executors → APIRequest → External Platform → APIResponse → RealExecutionResult
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Execution Mode
# ═══════════════════════════════════════════════════════════════


class ExecutionMode(str, Enum):
    """执行模式 — 控制 Executor 的行为.

    | Mode              | 说明                              |
    |-------------------|----------------------------------|
    | MOCK              | 模拟执行 (返回假数据)               |
    | DRY_RUN           | 干运行 (校验但不执行)               |
    | REAL              | 真实执行 (调用外部 API)             |
    | APPROVAL_REQUIRED | 需要审批后才能真实执行               |
    """
    MOCK = "mock"
    DRY_RUN = "dry_run"
    REAL = "real"
    APPROVAL_REQUIRED = "approval_required"


class PlatformType(str, Enum):
    """目标平台类型."""
    META = "meta"
    GOOGLE_ADS = "google_ads"
    ASA = "asa"
    MAX = "max"
    ADJUST = "adjust"
    LOVART = "lovart"
    INTERNAL = "internal"


# ═══════════════════════════════════════════════════════════════
# API Request / Response
# ═══════════════════════════════════════════════════════════════


@dataclass
class APIRequest:
    """标准化 API 请求 — 封装对外部平台的调用.

    Attributes:
        request_id: 请求唯一标识
        platform: 目标平台
        method: HTTP 方法 (GET/POST/PATCH/DELETE)
        endpoint: API 端点路径
        parameters: 请求参数
        body: 请求体
        action_type: 关联的动作类型
        action_id: 关联的动作 ID
        retry_count: 重试次数
        max_retries: 最大重试次数
        timeout_seconds: 超时时间
        created_at: 创建时间
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    platform: PlatformType = PlatformType.META
    method: str = "POST"
    endpoint: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    action_type: str = ""
    action_id: str = ""
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class APIResponse:
    """标准化 API 响应 — 封装外部平台的返回.

    Attributes:
        request_id: 关联的请求 ID
        status_code: HTTP 状态码
        success: 是否成功
        data: 响应数据
        error_code: 错误码
        error_message: 错误信息
        rate_limit_remaining: 剩余速率限制
        latency_ms: 响应延迟 (毫秒)
        platform_id: 平台返回的实体 ID
        raw_response: 原始响应
        responded_at: 响应时间
    """
    request_id: str = ""
    status_code: int = 0
    success: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    rate_limit_remaining: int = -1
    latency_ms: float = 0.0
    platform_id: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    responded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    @property
    def is_retryable(self) -> bool:
        return self.status_code in {429, 500, 502, 503, 504}


# ═══════════════════════════════════════════════════════════════
# Real Execution Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class RealExecutionResult:
    """真实执行结果 — 包含 API 调用痕迹和验证状态.

    Attributes:
        result_id: 结果唯一标识
        action_id: 关联的动作 ID
        action_type: 动作类型
        platform: 目标平台
        mode: 执行模式
        success: 是否成功
        api_request: API 请求
        api_response: API 响应
        platform_entity_id: 平台返回的实体 ID (campaign_id / creative_id)
        platform_entity_url: 平台实体链接
        verified: 是否已验证
        verification_result: 验证结果 (Adjust 等)
        error_message: 错误信息
        retry_count: 重试次数
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: str = ""
    platform: PlatformType = PlatformType.META
    mode: ExecutionMode = ExecutionMode.MOCK
    success: bool = False
    api_request: APIRequest | None = None
    api_response: APIResponse | None = None
    platform_entity_id: str = ""
    platform_entity_url: str = ""
    verified: bool = False
    verification_result: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    retry_count: int = 0
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "platform": self.platform.value,
            "mode": self.mode.value,
            "success": self.success,
            "platform_entity_id": self.platform_entity_id,
            "platform_entity_url": self.platform_entity_url,
            "verified": self.verified,
            "verification_result": self.verification_result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @property
    def duration_ms(self) -> float:
        if self.api_response:
            return self.api_response.latency_ms
        return 0.0


# ═══════════════════════════════════════════════════════════════
# Verification Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class VerificationResult:
    """验证结果 — 通过 Adjust 等渠道验证执行结果.

    Attributes:
        verification_id: 验证唯一标识
        execution_result_id: 关联的执行结果 ID
        platform: 目标平台
        platform_entity_id: 平台实体 ID
        verified: 是否验证通过
        metrics: 验证指标 (spend, impressions, clicks, installs, revenue, ROAS)
        data_available: 数据是否可用
        confidence: 验证置信度
        reason: 验证结果说明
        verified_at: 验证时间
        metadata: 扩展元数据
    """
    verification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_result_id: str = ""
    platform: PlatformType = PlatformType.META
    platform_entity_id: str = ""
    verified: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    data_available: bool = False
    confidence: float = 0.0
    reason: str = ""
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "execution_result_id": self.execution_result_id,
            "platform": self.platform.value,
            "platform_entity_id": self.platform_entity_id,
            "verified": self.verified,
            "metrics": self.metrics,
            "data_available": self.data_available,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "verified_at": self.verified_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Adapter Metrics
# ═══════════════════════════════════════════════════════════════


@dataclass
class AdapterMetrics:
    """适配器执行指标 — 统计和监控.

    Attributes:
        adapter_name: 适配器名称
        platform: 目标平台
        total_requests: 总请求数
        success_count: 成功数
        failure_count: 失败数
        mock_count: 模拟执行数
        dry_run_count: 干运行数
        real_count: 真实执行数
        total_latency_ms: 总延迟
        avg_latency_ms: 平均延迟
        rate_limit_hits: 速率限制触发次数
        last_execution_at: 最近执行时间
        last_error: 最近错误
    """
    adapter_name: str = ""
    platform: PlatformType = PlatformType.META
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    mock_count: int = 0
    dry_run_count: int = 0
    real_count: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    rate_limit_hits: int = 0
    last_execution_at: str = ""
    last_error: str = ""

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "platform": self.platform.value,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "mock_count": self.mock_count,
            "dry_run_count": self.dry_run_count,
            "real_count": self.real_count,
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "rate_limit_hits": self.rate_limit_hits,
            "success_rate": round(self.success_rate, 4),
            "last_execution_at": self.last_execution_at,
            "last_error": self.last_error,
        }

    def record(self, result: RealExecutionResult) -> None:
        """记录一次执行结果."""
        self.total_requests += 1
        if result.success:
            self.success_count += 1
        else:
            self.failure_count += 1
            self.last_error = result.error_message

        if result.mode == ExecutionMode.MOCK:
            self.mock_count += 1
        elif result.mode == ExecutionMode.DRY_RUN:
            self.dry_run_count += 1
        elif result.mode == ExecutionMode.REAL:
            self.real_count += 1

        if result.duration_ms > 0:
            self.total_latency_ms += result.duration_ms
            self.avg_latency_ms = self.total_latency_ms / self.total_requests

        if result.api_response and result.api_response.is_rate_limited:
            self.rate_limit_hits += 1

        self.last_execution_at = datetime.now(timezone.utc).isoformat()