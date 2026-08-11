"""P2.2 Execution Provider Layer — ExecutionResult（执行结果）。

一个 Provider 执行一次 ExecutionRequest 后产出的不可变结果。
核心安全字段 ``real_api_called``：

- DRY_RUN / SIMULATION：永远 False（本层绝不在非生产模式触碰外部系统）
- PRODUCTION：只要真正尝试了外部 API 调用（无论成功失败）即为 True
  —— 这是 E17 全局「真实调用」纪律在 P2 层的落点，用于全链路验收。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# 执行结果状态常量
STATUS_SUCCESS = "success"          # 真实/模拟执行成功
STATUS_DRY_RUN = "dry_run"          # 仅生成请求未触外部系统
STATUS_BLOCKED = "blocked"          # 被安全门拦截，未执行
STATUS_FAILED = "failed"            # 真实调用失败
STATUS_PENDING_APPROVAL = "pending_approval"  # 生产模式待人工审批


@dataclass
class ExecutionResult:
    """一次执行动作的交付物。

    Fields（与用户契约一致）：
        request_id   : 对应 ExecutionRequest.request_id
        provider     : 落地执行的 Provider 标识（如 "max" / "meta" / "play"）
        status       : STATUS_* 之一
        real_api_called : 是否真正尝试了外部 API（见模块 docstring）
        before_state : 执行前状态快照（DRY_RUN 为期望前态，可空）
        after_state  : 执行后状态快照（DRY_RUN 为期望后态 / 真实响应）
        error        : 失败原因（成功为 None）
        timestamp    : ISO UTC 时间戳
    """

    request_id: str
    provider: str
    status: str
    real_api_called: bool
    before_state: Dict[str, Any] = field(default_factory=dict)
    after_state: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # 便捷判定
    # ------------------------------------------------------------------
    @property
    def ok(self) -> bool:
        return self.status in (STATUS_SUCCESS, STATUS_DRY_RUN)

    @property
    def executed(self) -> bool:
        """是否真正落地（生产成功）了动作。"""
        return self.status == STATUS_SUCCESS

    def is_real(self) -> bool:
        return self.real_api_called

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "status": self.status,
            "real_api_called": self.real_api_called,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionResult":
        return cls(
            request_id=d.get("request_id", ""),
            provider=d.get("provider", ""),
            status=d.get("status", STATUS_BLOCKED),
            real_api_called=bool(d.get("real_api_called", False)),
            before_state=d.get("before_state") or {},
            after_state=d.get("after_state") or {},
            error=d.get("error"),
            timestamp=d.get("timestamp", ""),
        )


__all__ = [
    "STATUS_SUCCESS",
    "STATUS_DRY_RUN",
    "STATUS_BLOCKED",
    "STATUS_FAILED",
    "STATUS_PENDING_APPROVAL",
    "ExecutionResult",
]
