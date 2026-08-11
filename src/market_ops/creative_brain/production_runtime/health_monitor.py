"""V4.4 Health Monitor — real-time service health monitoring.

Monitors: Retriever, Embedding, Validation, Reasoning, GPU, Facebook API.
Any anomaly detected immediately.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .schemas import HealthReport, HealthStatus


class HealthMonitor:
    """Real-time health monitoring for all services."""

    def __init__(self, check_interval: float = 30.0,
                 timeout: float = 5.0,
                 max_consecutive_failures: int = 3) -> None:
        self._check_interval = check_interval
        self._timeout = timeout
        self._max_consecutive_failures = max_consecutive_failures
        self._services: dict[str, dict[str, Any]] = {}  # service_name → {check_fn, ...}
        self._reports: dict[str, HealthReport] = {}
        self._health_history: list[dict[str, Any]] = []

    def register_service(self, service_name: str,
                         check_fn: Callable[[], bool],
                         **metadata: Any) -> None:
        """Register a service for health monitoring.

        Args:
            service_name: Unique service name.
            check_fn: Callable returning True if healthy.
            **metadata: Additional service metadata.
        """
        self._services[service_name] = {
            "check_fn": check_fn,
            "metadata": metadata,
        }
        self._reports[service_name] = HealthReport(
            service_name=service_name,
            status=HealthStatus.HEALTHY,
            last_check=0.0,
        )

    def unregister_service(self, service_name: str) -> None:
        """Remove a service from monitoring."""
        self._services.pop(service_name, None)
        self._reports.pop(service_name, None)

    def check_service(self, service_name: str) -> HealthReport:
        """Check health of a single service.

        Returns:
            Updated HealthReport.
        """
        if service_name not in self._services:
            return HealthReport(
                service_name=service_name,
                status=HealthStatus.DOWN,
                message="Service not registered",
                last_check=time.time(),
            )

        svc = self._services[service_name]
        report = self._reports[service_name]

        start = time.time()
        try:
            healthy = svc["check_fn"]()
            response_time = time.time() - start

            if healthy:
                report.consecutive_failures = 0
                if report.status == HealthStatus.UNHEALTHY:
                    report.status = HealthStatus.DEGRADED
                elif report.status == HealthStatus.DOWN:
                    report.status = HealthStatus.DEGRADED
                else:
                    report.status = HealthStatus.HEALTHY
                report.message = "OK"
            else:
                report.consecutive_failures += 1
                report.status = self._evaluate_status(report.consecutive_failures)
                report.message = "Health check returned False"
                report.error_count += 1
        except Exception as e:
            response_time = time.time() - start
            report.consecutive_failures += 1
            report.status = self._evaluate_status(report.consecutive_failures)
            report.message = str(e)
            report.error_count += 1

        report.last_check = time.time()
        report.response_time = response_time

        self._health_history.append({
            "service": service_name,
            "status": report.status.value,
            "response_time": response_time,
            "timestamp": report.last_check,
        })

        return report

    def check_all(self) -> list[HealthReport]:
        """Check health of all registered services."""
        results = []
        for name in self._services:
            report = self.check_service(name)
            results.append(report)
        return results

    def get_report(self, service_name: str) -> HealthReport | None:
        """Get latest health report for a service."""
        return self._reports.get(service_name)

    def get_all_reports(self) -> list[HealthReport]:
        """Get all latest health reports."""
        return list(self._reports.values())

    def get_unhealthy_services(self) -> list[HealthReport]:
        """Get all services that are not healthy."""
        return [
            r for r in self._reports.values()
            if r.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.DOWN)
        ]

    def get_down_services(self) -> list[HealthReport]:
        """Get all down services."""
        return [r for r in self._reports.values() if r.status == HealthStatus.DOWN]

    def get_summary(self) -> dict[str, Any]:
        """Get health summary across all services."""
        reports = self.get_all_reports()
        status_counts = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "down": 0,
        }
        for r in reports:
            status_counts[r.status.value] += 1

        return {
            "total_services": len(reports),
            "status_counts": status_counts,
            "overall_healthy": status_counts["down"] == 0 and status_counts["unhealthy"] == 0,
            "unhealthy_services": [r.service_name for r in self.get_unhealthy_services()],
            "last_check": max((r.last_check for r in reports), default=0.0),
        }

    def get_history(self, service_name: str | None = None,
                    limit: int = 50) -> list[dict[str, Any]]:
        """Get health check history, optionally filtered by service."""
        if service_name:
            return [h for h in self._health_history if h["service"] == service_name][-limit:]
        return self._health_history[-limit:]

    def _evaluate_status(self, consecutive_failures: int) -> HealthStatus:
        """Determine health status based on consecutive failures."""
        if consecutive_failures >= self._max_consecutive_failures * 2:
            return HealthStatus.DOWN
        elif consecutive_failures >= self._max_consecutive_failures:
            return HealthStatus.UNHEALTHY
        elif consecutive_failures > 0:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_services(self) -> list[str]:
        """Get all registered service names."""
        return list(self._services.keys())