"""E15.0.4 Health Checker — 系统健康检查.

检查:
  - Agent 状态
  - Connector 状态 (Meta / Adjust / MAX)
  - 数据库状态
  - API 状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class HealthStatus(str, Enum):
    """健康状态."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """组件健康状态."""
    component: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0
    last_checked: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_checked": self.last_checked,
            "metadata": self.metadata,
        }


@dataclass
class HealthReport:
    """健康检查报告."""
    overall: HealthStatus = HealthStatus.UNKNOWN
    components: list[ComponentHealth] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    uptime_seconds: float = 0.0

    @property
    def is_healthy(self) -> bool:
        return self.overall == HealthStatus.HEALTHY

    @property
    def unhealthy_components(self) -> list[ComponentHealth]:
        return [c for c in self.components if c.status == HealthStatus.UNHEALTHY]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "is_healthy": self.is_healthy,
            "checked_at": self.checked_at,
            "uptime_seconds": self.uptime_seconds,
            "components": [c.to_dict() for c in self.components],
            "unhealthy_count": len(self.unhealthy_components),
        }


class HealthChecker:
    """健康检查器 — 检查系统各组件状态.

    用法:
        checker = HealthChecker()
        checker.register("agent", check_agent_fn)
        checker.register("meta_connector", check_meta_fn)
        checker.register("adjust_connector", check_adjust_fn)
        report = checker.check_all()
    """

    def __init__(self):
        self._checks: dict[str, Callable[[], ComponentHealth]] = {}
        self._started_at: str = datetime.now(timezone.utc).isoformat()
        self._last_report: HealthReport | None = None

    # ── Registration ─────────────────────────────────────────

    def register(self, component: str, check_fn: Callable[[], ComponentHealth]) -> None:
        """注册组件健康检查.

        check_fn 签名: def check_fn() -> ComponentHealth
        """
        self._checks[component] = check_fn

    def unregister(self, component: str) -> bool:
        return self._checks.pop(component, None) is not None

    @property
    def registered_components(self) -> list[str]:
        return list(self._checks.keys())

    # ── Check ────────────────────────────────────────────────

    def check(self, component: str) -> ComponentHealth:
        """检查单个组件."""
        if component not in self._checks:
            return ComponentHealth(
                component=component,
                status=HealthStatus.UNKNOWN,
                message=f"No check registered for {component}",
            )

        try:
            start = datetime.now(timezone.utc)
            result = self._checks[component]()
            result.last_checked = datetime.now(timezone.utc).isoformat()
            result.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return result
        except Exception as e:
            return ComponentHealth(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e}",
                last_checked=datetime.now(timezone.utc).isoformat(),
            )

    def check_all(self) -> HealthReport:
        """检查所有组件.

        Returns:
            HealthReport: 健康检查报告
        """
        components: list[ComponentHealth] = []
        for name in self._checks:
            components.append(self.check(name))

        # 计算整体健康状态
        if not components:
            overall = HealthStatus.UNKNOWN
        elif any(c.status == HealthStatus.UNHEALTHY for c in components):
            overall = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        uptime = 0.0
        try:
            start = datetime.fromisoformat(self._started_at)
            uptime = (datetime.now(timezone.utc) - start).total_seconds()
        except (ValueError, TypeError):
            pass

        report = HealthReport(
            overall=overall,
            components=components,
            uptime_seconds=uptime,
        )
        self._last_report = report
        return report

    def check_agent(self, is_running: bool, error_count: int = 0) -> ComponentHealth:
        """检查 Agent 状态."""
        if not is_running:
            return ComponentHealth(
                component="agent",
                status=HealthStatus.UNHEALTHY,
                message="Agent is not running",
            )
        if error_count > 5:
            return ComponentHealth(
                component="agent",
                status=HealthStatus.DEGRADED,
                message=f"Agent has {error_count} errors",
            )
        return ComponentHealth(
            component="agent",
            status=HealthStatus.HEALTHY,
            message="Agent is running normally",
        )

    def check_connector(
        self,
        name: str,
        is_connected: bool,
        last_sync: str = "",
        error: str = "",
    ) -> ComponentHealth:
        """检查连接器状态."""
        if not is_connected:
            return ComponentHealth(
                component=f"{name}_connector",
                status=HealthStatus.UNHEALTHY,
                message=f"{name} connector is disconnected",
                metadata={"error": error},
            )
        return ComponentHealth(
            component=f"{name}_connector",
            status=HealthStatus.HEALTHY,
            message=f"{name} connector is connected",
            metadata={"last_sync": last_sync},
        )

    def check_database(self, is_connected: bool, latency_ms: float = 0.0) -> ComponentHealth:
        """检查数据库状态."""
        if not is_connected:
            return ComponentHealth(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message="Database connection failed",
            )
        if latency_ms > 1000:
            return ComponentHealth(
                component="database",
                status=HealthStatus.DEGRADED,
                message=f"Database latency high: {latency_ms:.0f}ms",
                latency_ms=latency_ms,
            )
        return ComponentHealth(
            component="database",
            status=HealthStatus.HEALTHY,
            message="Database is healthy",
            latency_ms=latency_ms,
        )

    def check_api(self, name: str, is_available: bool, status_code: int = 200) -> ComponentHealth:
        """检查 API 状态."""
        if not is_available:
            return ComponentHealth(
                component=f"{name}_api",
                status=HealthStatus.UNHEALTHY,
                message=f"{name} API is unavailable",
            )
        if status_code >= 500:
            return ComponentHealth(
                component=f"{name}_api",
                status=HealthStatus.DEGRADED,
                message=f"{name} API returned {status_code}",
            )
        return ComponentHealth(
            component=f"{name}_api",
            status=HealthStatus.HEALTHY,
            message=f"{name} API is available",
        )

    # ── Report ───────────────────────────────────────────────

    def get_last_report(self) -> HealthReport | None:
        return self._last_report

    def get_summary(self) -> dict[str, Any]:
        """获取健康摘要."""
        report = self._last_report
        if not report:
            return {"status": "no_report"}

        return {
            "overall": report.overall.value,
            "is_healthy": report.is_healthy,
            "checked_at": report.checked_at,
            "components": {
                c.component: c.status.value for c in report.components
            },
            "unhealthy": [c.component for c in report.unhealthy_components],
        }

    def reset(self) -> None:
        self._last_report = None
        self._started_at = datetime.now(timezone.utc).isoformat()