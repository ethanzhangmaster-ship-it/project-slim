"""V4.4 Alert Manager — multi-channel alerting system.

Supports: Slack, Email, Discord, WeChat (企业微信).
Alert levels: INFO, WARNING, CRITICAL.
Alert lifecycle: created → acknowledged → resolved.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .schemas import Alert, AlertLevel


class AlertManager:
    """Multi-channel alert manager."""

    def __init__(self, enabled: bool = True,
                 min_level: AlertLevel = AlertLevel.WARNING) -> None:
        self.enabled = enabled
        self.min_level = min_level
        self._alerts: list[Alert] = []
        self._channels: dict[str, Callable[[Alert], None]] = {}
        self._active_alerts: dict[str, Alert] = {}
        self._alert_history: list[dict[str, Any]] = []

    def register_channel(self, name: str,
                         handler: Callable[[Alert], None]) -> None:
        """Register an alert notification channel.

        Args:
            name: Channel name (slack, email, discord, wechat, etc.).
            handler: Callable that receives an Alert and sends it.
        """
        self._channels[name] = handler

    def unregister_channel(self, name: str) -> None:
        """Remove an alert channel."""
        self._channels.pop(name, None)

    def get_channels(self) -> list[str]:
        """Get all registered channel names."""
        return list(self._channels.keys())

    def send_alert(self, level: AlertLevel, service: str,
                   message: str, **metadata: Any) -> Alert:
        """Create and send an alert.

        Args:
            level: Alert severity level.
            service: Source service name.
            message: Alert message.
            **metadata: Additional alert metadata.

        Returns:
            The created Alert.
        """
        alert = Alert(
            alert_id=str(uuid.uuid4())[:8],
            level=level,
            service=service,
            message=message,
            timestamp=time.time(),
        )

        self._alerts.append(alert)
        self._active_alerts[alert.alert_id] = alert

        # Only send if enabled and level meets minimum
        if self.enabled and self._should_send(level):
            self._dispatch(alert)

        self._alert_history.append({
            "alert_id": alert.alert_id,
            "level": level.value,
            "service": service,
            "message": message,
            "timestamp": alert.timestamp,
            "action": "created",
        })

        return alert

    def info(self, service: str, message: str, **metadata: Any) -> Alert:
        """Send an INFO level alert."""
        return self.send_alert(AlertLevel.INFO, service, message, **metadata)

    def warning(self, service: str, message: str, **metadata: Any) -> Alert:
        """Send a WARNING level alert."""
        return self.send_alert(AlertLevel.WARNING, service, message, **metadata)

    def critical(self, service: str, message: str, **metadata: Any) -> Alert:
        """Send a CRITICAL level alert."""
        return self.send_alert(AlertLevel.CRITICAL, service, message, **metadata)

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert.

        Returns:
            True if the alert was found and acknowledged.
        """
        alert = self._active_alerts.get(alert_id)
        if alert is None:
            return False
        alert.acknowledged = True
        self._alert_history.append({
            "alert_id": alert_id,
            "timestamp": time.time(),
            "action": "acknowledged",
        })
        return True

    def resolve(self, alert_id: str) -> bool:
        """Resolve an alert.

        Returns:
            True if the alert was found and resolved.
        """
        alert = self._active_alerts.get(alert_id)
        if alert is None:
            return False
        alert.resolved = True
        alert.acknowledged = True
        self._active_alerts.pop(alert_id, None)
        self._alert_history.append({
            "alert_id": alert_id,
            "timestamp": time.time(),
            "action": "resolved",
        })
        return True

    def get_active_alerts(self) -> list[Alert]:
        """Get all unresolved alerts."""
        return [
            a for a in self._active_alerts.values()
            if not a.resolved
        ]

    def get_alerts_by_level(self, level: AlertLevel) -> list[Alert]:
        """Get alerts filtered by level."""
        return [a for a in self._alerts if a.level == level]

    def get_alerts_by_service(self, service: str) -> list[Alert]:
        """Get alerts filtered by service."""
        return [a for a in self._alerts if a.service == service]

    def get_summary(self) -> dict[str, Any]:
        """Get alert summary."""
        active = self.get_active_alerts()
        critical_count = sum(1 for a in active if a.level == AlertLevel.CRITICAL)
        warning_count = sum(1 for a in active if a.level == AlertLevel.WARNING)
        info_count = sum(1 for a in active if a.level == AlertLevel.INFO)

        return {
            "total_active": len(active),
            "critical": critical_count,
            "warning": warning_count,
            "info": info_count,
            "total_ever": len(self._alerts),
            "channels": self.get_channels(),
            "enabled": self.enabled,
        }

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get alert history."""
        return self._alert_history[-limit:]

    def clear_resolved(self) -> int:
        """Remove all resolved alerts from active tracking.

        Returns:
            Number of alerts cleared.
        """
        before = len(self._active_alerts)
        self._active_alerts = {
            k: v for k, v in self._active_alerts.items()
            if not v.resolved
        }
        return before - len(self._active_alerts)

    def _dispatch(self, alert: Alert) -> None:
        """Dispatch alert to all registered channels."""
        for channel_name, handler in self._channels.items():
            try:
                handler(alert)
            except Exception:
                pass  # Channel delivery failure should not block other channels

    def _should_send(self, level: AlertLevel) -> bool:
        """Check if an alert level should be sent based on minimum."""
        level_priority = {
            AlertLevel.INFO: 0,
            AlertLevel.WARNING: 1,
            AlertLevel.CRITICAL: 2,
        }
        return level_priority.get(level, 0) >= level_priority.get(self.min_level, 0)

    # ── Convenience channel handlers ──────────────────────

    @staticmethod
    def log_channel_handler(alert: Alert) -> None:
        """Simple handler that logs alerts to console."""
        print(f"[{alert.level.value.upper()}] [{alert.service}] {alert.message}")

    @staticmethod
    def file_channel_handler(filepath: str) -> Callable[[Alert], None]:
        """Create a handler that writes alerts to a file.

        Args:
            filepath: Path to the alert log file.

        Returns:
            Handler function.
        """
        def _handler(alert: Alert) -> None:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(
                    f"{alert.timestamp} [{alert.level.value}] "
                    f"[{alert.service}] {alert.message}\n"
                )
        return _handler