"""E15.0.8 Storage Service — 统一持久化入口.

Agent 不关心底层存储 (Postgres / Redis / 文件)，通过 StorageService 统一访问。

用法:
    db = DatabaseManager()
    db.connect()
    redis = RedisStateManager()
    redis.connect()

    storage = StorageService(db=db, redis=redis)
    storage.save_audit(audit_dict)
    storage.save_event(event_dict)
    storage.save_metric(metrics_dict)
    storage.save_execution(execution_dict)
    storage.save_alert(alert_dict)
"""

from __future__ import annotations

from typing import Any

from .database import DatabaseManager
from .redis_state import RedisStateManager
from .repositories.audit_repository import AuditRepository
from .repositories.event_repository import EventRepository
from .repositories.metric_repository import MetricRepository
from .repositories.execution_repository import ExecutionRepository
from .repositories.alert_repository import AlertRepository


class StorageService:
    """统一存储服务 — E15.0.8 核心入口.

    属性:
        db:            DatabaseManager
        redis:         RedisStateManager
        audit:         AuditRepository
        events:        EventRepository
        metrics:       MetricRepository
        executions:    ExecutionRepository
        alerts:        AlertRepository
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        redis: RedisStateManager | None = None,
    ):
        self._db = db
        self._redis = redis

        # Lazy-init repositories
        self._audit_repo: AuditRepository | None = None
        self._event_repo: EventRepository | None = None
        self._metric_repo: MetricRepository | None = None
        self._execution_repo: ExecutionRepository | None = None
        self._alert_repo: AlertRepository | None = None

    # ── Properties ───────────────────────────────────────────

    @property
    def db(self) -> DatabaseManager:
        if self._db is None:
            raise RuntimeError("DatabaseManager not set")
        return self._db

    @property
    def redis(self) -> RedisStateManager:
        if self._redis is None:
            raise RuntimeError("RedisStateManager not set")
        return self._redis

    @property
    def audit(self) -> AuditRepository:
        if self._audit_repo is None:
            self._audit_repo = AuditRepository(self.db)
        return self._audit_repo

    @property
    def events(self) -> EventRepository:
        if self._event_repo is None:
            self._event_repo = EventRepository(self.db)
        return self._event_repo

    @property
    def metrics(self) -> MetricRepository:
        if self._metric_repo is None:
            self._metric_repo = MetricRepository(self.db)
        return self._metric_repo

    @property
    def executions(self) -> ExecutionRepository:
        if self._execution_repo is None:
            self._execution_repo = ExecutionRepository(self.db)
        return self._execution_repo

    @property
    def alerts(self) -> AlertRepository:
        if self._alert_repo is None:
            self._alert_repo = AlertRepository(self.db)
        return self._alert_repo

    # ── Convenience Methods ──────────────────────────────────

    def save_audit(self, audit: dict[str, Any]) -> Any:
        return self.audit.save(audit)

    def save_event(self, event: dict[str, Any]) -> Any:
        return self.events.save(event)

    def save_metric(self, metrics: dict[str, Any]) -> Any:
        return self.metrics.save(metrics)

    def save_execution(self, execution: dict[str, Any]) -> Any:
        return self.executions.save(execution)

    def save_alert(self, alert: dict[str, Any]) -> Any:
        return self.alerts.save(alert)

    # ── Runtime State ────────────────────────────────────────

    def acquire_scheduler_lock(self, name: str = "default", ttl: int = 3600) -> bool:
        return self.redis.acquire_scheduler_lock(name, ttl)

    def release_scheduler_lock(self, name: str = "default") -> bool:
        return self.redis.release_scheduler_lock(name)

    def set_cooldown(self, campaign_id: str, action: str, ttl_days: int = 7) -> None:
        self.redis.set_cooldown(campaign_id, action, ttl_days)

    def is_in_cooldown(self, campaign_id: str) -> bool:
        return self.redis.is_in_cooldown(campaign_id)

    def send_heartbeat(self, status: str = "running") -> None:
        self.redis.send_heartbeat(status)

    # ── Health ───────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """全存储健康检查."""
        db_health = self.db.health_check() if self._db else {"status": "not_configured"}
        redis_health = self.redis.health_check() if self._redis else {"status": "not_configured"}
        return {
            "database": db_health,
            "redis": redis_health,
            "overall": (
                "healthy"
                if db_health.get("status") == "healthy"
                and redis_health.get("status") == "healthy"
                else "degraded"
            ),
        }

    def close(self) -> None:
        """关闭所有连接."""
        if self._db:
            self._db.close()
        if self._redis:
            self._redis.close()

    def __repr__(self) -> str:
        return (
            f"StorageService(db={'connected' if self._db and self._db.is_connected else 'no'}, "
            f"redis={'connected' if self._redis and self._redis.is_connected else 'no'})"
        )


__all__ = ["StorageService"]