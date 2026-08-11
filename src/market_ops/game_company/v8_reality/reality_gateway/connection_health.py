from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import time


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    platform: str
    status: HealthStatus
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    checked_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "checked_at": self.checked_at.isoformat(),
        }


class ConnectionHealth:
    def __init__(self):
        self._health_checks: Dict[str, Callable] = {}
        self._health_history: Dict[str, List[HealthCheckResult]] = {}
        self._alert_thresholds: Dict[str, Dict[str, Any]] = {}

    def register_health_check(self, platform: str, check: Callable):
        self._health_checks[platform] = check
        if platform not in self._health_history:
            self._health_history[platform] = []

    def set_alert_threshold(self, platform: str, max_latency_ms: float = 1000, min_success_rate: float = 0.9):
        self._alert_thresholds[platform] = {
            "max_latency_ms": max_latency_ms,
            "min_success_rate": min_success_rate,
        }

    def check_platform(self, platform: str) -> HealthCheckResult:
        check = self._health_checks.get(platform)
        if not check:
            return HealthCheckResult(
                platform=platform,
                status=HealthStatus.UNKNOWN,
                error_message="No health check registered",
            )

        start_time = time.time()
        try:
            success = check()
            latency_ms = (time.time() - start_time) * 1000

            status = HealthStatus.HEALTHY if success else HealthStatus.UNHEALTHY
            if success and latency_ms > self._alert_thresholds.get(platform, {}).get("max_latency_ms", 1000):
                status = HealthStatus.DEGRADED

            result = HealthCheckResult(
                platform=platform,
                status=status,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                platform=platform,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message=str(e),
            )

        if platform not in self._health_history:
            self._health_history[platform] = []
        self._health_history[platform].append(result)
        self._health_history[platform] = self._health_history[platform][-100:]

        return result

    def check_all(self) -> Dict[str, HealthCheckResult]:
        results = {}
        for platform in self._health_checks:
            results[platform] = self.check_platform(platform)
        return results

    def get_overall_health(self) -> HealthStatus:
        results = self.check_all()
        if not results:
            return HealthStatus.UNKNOWN

        healthy_count = sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for r in results.values() if r.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY)

        if unhealthy_count > 0:
            return HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_platform_health_history(self, platform: str, hours: int = 24) -> List[HealthCheckResult]:
        if platform not in self._health_history:
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        return [r for r in self._health_history[platform] if r.checked_at >= cutoff]

    def get_platform_latency_trend(self, platform: str, hours: int = 24) -> List[Dict[str, Any]]:
        history = self.get_platform_health_history(platform, hours)
        return [{
            "timestamp": r.checked_at.isoformat(),
            "latency_ms": r.latency_ms,
            "status": r.status.value,
        } for r in history]

    def get_platform_success_rate(self, platform: str, hours: int = 24) -> float:
        history = self.get_platform_health_history(platform, hours)
        if not history:
            return 0.0

        success_count = sum(1 for r in history if r.status == HealthStatus.HEALTHY)
        return success_count / len(history)

    def get_alert_status(self, platform: str) -> Dict[str, Any]:
        thresholds = self._alert_thresholds.get(platform, {})
        success_rate = self.get_platform_success_rate(platform)
        history = self.get_platform_health_history(platform, 1)

        avg_latency = sum(r.latency_ms for r in history) / len(history) if history else 0

        alerts = []
        if success_rate < thresholds.get("min_success_rate", 0.9):
            alerts.append(f"Success rate {success_rate:.2f} below threshold")
        if avg_latency > thresholds.get("max_latency_ms", 1000):
            alerts.append(f"Avg latency {avg_latency:.1f}ms above threshold")

        return {
            "platform": platform,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "alerts": alerts,
            "status": "ok" if not alerts else "alert",
        }

    def get_all_alerts(self) -> Dict[str, Dict[str, Any]]:
        alerts = {}
        for platform in self._health_checks:
            alert_status = self.get_alert_status(platform)
            if alert_status["status"] == "alert":
                alerts[platform] = alert_status
        return alerts

    def get_stats(self) -> Dict[str, Any]:
        results = self.check_all()
        total = len(results)
        healthy = sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY)
        degraded = sum(1 for r in results.values() if r.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY)

        avg_latency = sum(r.latency_ms for r in results.values()) / total if total > 0 else 0

        return {
            "total_platforms": total,
            "healthy_platforms": healthy,
            "degraded_platforms": degraded,
            "unhealthy_platforms": unhealthy,
            "avg_latency_ms": avg_latency,
            "overall_status": self.get_overall_health().value,
        }
