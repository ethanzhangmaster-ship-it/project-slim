"""E13.7.4.3 Alert Manager — 告警管理.

管理健康监控产生的告警:
  - 创建告警
  - 发送告警 (预留 Slack / Email / 企业微信 接口)
  - 解决告警
  - 查询告警历史
  - 告警去重

E15.0.8 升级: 支持 StorageService 持久化到 PostgreSQL.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from .health_models import (
    Alert,
    AlertLevel,
    AlertType,
    HealthEvaluation,
    HealthSnapshot,
    HealthStatus,
)

if TYPE_CHECKING:
    from ...storage.service import StorageService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Alert Manager
# ═══════════════════════════════════════════════════════════════


class AlertManager:
    """告警管理器.

    管理健康监控告警的完整生命周期:
      - 创建 / 发送 / 解决
      - 去重 (同类型告警不重复发送)
      - 查询和历史

    使用方式:
        >>> manager = AlertManager()
        >>> alert = manager.create_alert(
        ...     level=AlertLevel.CRITICAL,
        ...     alert_type=AlertType.EXECUTION_FAILURE,
        ...     message="执行成功率低于阈值",
        ... )
        >>> manager.send(alert)
        >>> manager.resolve(alert.alert_id)

    E15.0.8 持久化:
        manager = AlertManager(storage=storage)
        manager.create_alert(...)  # 自动双写 (内存 + PostgreSQL)
    """

    def __init__(
        self,
        max_active: int = 100,
        max_history: int = 500,
        dedup_window_minutes: int = 30,
        storage: "StorageService | None" = None,
    ):
        self._max_active = max_active
        self._max_history = max_history
        self._dedup_window_minutes = dedup_window_minutes
        self._storage = storage
        self._active: dict[str, Alert] = {}
        self._history: list[Alert] = []

    # ── Properties ──────────────────────────────────────────

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def active_alerts(self) -> list[Alert]:
        return list(self._active.values())

    @property
    def unresolved_count(self) -> int:
        return len([a for a in self._active.values() if not a.is_resolved])

    # ── Create ──────────────────────────────────────────────

    def create_alert(
        self,
        level: AlertLevel,
        alert_type: AlertType,
        message: str,
        source: str = "health_monitor",
        snapshot: HealthSnapshot | None = None,
    ) -> Alert | None:
        """创建告警 (带去重).

        Args:
            level: 告警级别
            alert_type: 告警类型
            message: 告警消息
            source: 告警来源
            snapshot: 关联健康快照

        Returns:
            Alert 或 None (如果去重过滤)
        """
        # 去重: 同类型活跃告警不重复创建
        if self._is_duplicate(alert_type):
            return None

        alert = Alert(
            level=level,
            alert_type=alert_type,
            message=message,
            source=source,
            snapshot=snapshot,
        )

        # 容量检查
        if len(self._active) >= self._max_active:
            oldest = sorted(self._active.values(), key=lambda a: a.created_at)[0]
            self._archive(oldest)

        self._active[alert.alert_id] = alert

        # E15.0.8: 持久化到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.alerts.save(self._alert_to_dict(alert))
            except Exception as e:
                logger.warning(f"Failed to persist alert to PostgreSQL: {e}")

        return alert

    def create_from_evaluation(self, evaluation: HealthEvaluation) -> Alert | None:
        """从健康评估自动创建告警.

        Args:
            evaluation: 健康评估结果

        Returns:
            Alert 或 None
        """
        if not evaluation.requires_alert:
            return None

        level = AlertLevel.WARNING
        if evaluation.status == HealthStatus.SAFE_MODE:
            level = AlertLevel.CRITICAL
            alert_type = AlertType.SAFE_MODE_ACTIVATED
        elif evaluation.status == HealthStatus.FAILED:
            level = AlertLevel.CRITICAL
            alert_type = AlertType.EXECUTION_FAILURE
        elif evaluation.status == HealthStatus.DEGRADED:
            alert_type = AlertType.TOOL_FAILURE
        elif evaluation.status == HealthStatus.WARNING:
            alert_type = AlertType.DECISION_DRIFT
        else:
            return None

        message = f"Agent 健康状态变为 {evaluation.status.value}"

        if evaluation.snapshot.errors:
            message += f": {evaluation.snapshot.errors[0]}"
        elif evaluation.snapshot.warnings:
            message += f": {evaluation.snapshot.warnings[0]}"

        return self.create_alert(
            level=level,
            alert_type=alert_type,
            message=message,
            snapshot=evaluation.snapshot,
        )

    # ── Send ────────────────────────────────────────────────

    def send(self, alert: Alert) -> bool:
        """发送告警.

        预留通知渠道: Slack, Email, 企业微信, Dashboard.

        Args:
            alert: 告警对象

        Returns:
            bool: 是否发送成功
        """
        # 当前: 记录日志 (未来扩展通知渠道)
        return True

    def send_all(self) -> int:
        """发送所有未发送告警.

        Returns:
            int: 发送数量
        """
        count = 0
        for alert in self._active.values():
            if not alert.is_resolved and self.send(alert):
                count += 1
        return count

    # ── Resolve ─────────────────────────────────────────────

    def resolve(self, alert_id: str, note: str = "") -> bool:
        """解决告警.

        Args:
            alert_id: 告警 ID
            note: 解决备注

        Returns:
            bool: 是否成功
        """
        alert = self._active.get(alert_id)
        if alert is None:
            return False
        alert.resolve(note)
        self._archive(alert)

        # E15.0.8: 持久化到 PostgreSQL
        if self._storage is not None:
            try:
                self._storage.alerts.acknowledge(alert_id)
            except Exception as e:
                logger.warning(f"Failed to acknowledge alert in PostgreSQL: {e}")

        return True

    def resolve_all(self, note: str = "") -> int:
        """解决所有活跃告警."""
        count = 0
        for alert in list(self._active.values()):
            if self.resolve(alert.alert_id, note):
                count += 1
        return count

    def resolve_by_type(self, alert_type: AlertType, note: str = "") -> int:
        """解决指定类型的所有告警."""
        count = 0
        for alert in list(self._active.values()):
            if alert.alert_type == alert_type and not alert.is_resolved:
                if self.resolve(alert.alert_id, note):
                    count += 1
        return count

    # ── Query ───────────────────────────────────────────────

    def get_alert(self, alert_id: str) -> Alert | None:
        """获取告警."""
        return self._active.get(alert_id)

    def get_active(self) -> list[Alert]:
        """获取所有活跃告警."""
        return [a for a in self._active.values() if not a.is_resolved]

    def get_by_type(self, alert_type: AlertType) -> list[Alert]:
        """获取指定类型告警."""
        return [a for a in self._active.values() if a.alert_type == alert_type]

    def get_critical(self) -> list[Alert]:
        """获取所有严重告警."""
        return [a for a in self._active.values() if a.level == AlertLevel.CRITICAL]

    def get_history(self, limit: int = 50, offset: int = 0) -> list[Alert]:
        """获取历史告警."""
        return self._history[offset : offset + limit]

    def get_stats(self) -> dict[str, Any]:
        """获取告警统计."""
        type_counts: dict[str, int] = {}
        level_counts: dict[str, int] = {}
        for a in self._active.values():
            type_counts[a.alert_type.value] = type_counts.get(a.alert_type.value, 0) + 1
            level_counts[a.level.value] = level_counts.get(a.level.value, 0) + 1

        return {
            "active_count": self.active_count,
            "unresolved_count": self.unresolved_count,
            "history_count": len(self._history),
            "by_type": type_counts,
            "by_level": level_counts,
        }

    # ── Internal ────────────────────────────────────────────

    def _alert_to_dict(self, alert: Alert) -> dict[str, Any]:
        """将 Alert 模型转换为 AlertRepository 所需的 dict 格式."""
        return {
            "alert_id": alert.alert_id,
            "severity": alert.level.value,
            "rule_name": alert.alert_type.value,
            "message": alert.message,
            "game_id": "",
            "metrics": alert.snapshot.to_dict() if alert.snapshot else {},
            "acknowledged": alert.is_resolved,
        }

    def _is_duplicate(self, alert_type: AlertType) -> bool:
        """检查是否重复告警 (同类型且未解决)."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self._dedup_window_minutes)
        for alert in self._active.values():
            if alert.alert_type == alert_type and not alert.is_resolved:
                try:
                    created = datetime.fromisoformat(alert.created_at)
                    if created > cutoff:
                        return True
                except Exception:
                    pass
        return False

    def _archive(self, alert: Alert) -> None:
        """归档告警."""
        if alert.alert_id in self._active:
            del self._active[alert.alert_id]
        self._history.append(alert)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def reset(self) -> None:
        """重置告警管理器."""
        self._active.clear()
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_alert_manager(
    max_active: int = 100,
    max_history: int = 500,
) -> AlertManager:
    """创建告警管理器的工厂函数."""
    return AlertManager(
        max_active=max_active,
        max_history=max_history,
    )