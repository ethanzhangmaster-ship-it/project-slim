"""E15.0.8 SQLAlchemy ORM Models — PostgreSQL 表定义.

模型:
  - AuditRecord:      审计记录 (替代 AuditStore._records)
  - GrowthEventRecord: 增长事件 (替代 UnifiedGrowthEvent 内存列表)
  - ExecutionRecord:   执行记录 (替代 Worker 内存历史)
  - MetricSnapshot:    指标快照 (替代 MetricsCollector._snapshots)
  - AlertRecord:       报警记录 (替代 AlertManager._alerts)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类."""
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════
# Audit Record
# ═══════════════════════════════════════════════════════════════


class AuditRecord(Base):
    """审计记录 — 持久化 GrowthDecisionAudit.

    替代: AuditStore._records (内存列表)
    """

    __tablename__ = "growth_audit_records"

    id: Mapped[str] = mapped_column(
        String(48), primary_key=True, default=_new_uuid,
    )
    game_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    detected_problem: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    decision: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    input_context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    execution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True,
    )
    result: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    plan_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    cycle_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    safety_decision: Mapped[str] = mapped_column(
        String(32), nullable=False, default="",
    )
    rollback_record_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"AuditRecord(id={self.id}, game={self.game_id}, "
            f"status={self.execution_status}, confidence={self.confidence})"
        )


# ═══════════════════════════════════════════════════════════════
# Growth Event
# ═══════════════════════════════════════════════════════════════


class GrowthEventRecord(Base):
    """增长事件记录 — 持久化 UnifiedGrowthEvent.

    替代: UnifiedGrowthEvent 内存列表
    """

    __tablename__ = "growth_events"

    event_id: Mapped[str] = mapped_column(
        String(48), primary_key=True, default=_new_uuid,
    )
    game_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="internal",
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True,
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    campaign_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    creative_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    platform: Mapped[str] = mapped_column(
        String(32), nullable=False, default="",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"GrowthEventRecord(event_id={self.event_id}, game={self.game_id}, "
            f"type={self.event_type}, source={self.source})"
        )


# ═══════════════════════════════════════════════════════════════
# Execution Record
# ═══════════════════════════════════════════════════════════════


class ExecutionRecord(Base):
    """执行记录 — 持久化 ProductionWorker 执行历史.

    替代: ProductionWorker._results (内存列表)
    """

    __tablename__ = "growth_execution_records"

    execution_id: Mapped[str] = mapped_column(
        String(48), primary_key=True, default=_new_uuid,
    )
    action_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True,
    )
    output: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    error: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    duration_ms: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    rollback_record_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"ExecutionRecord(id={self.execution_id}, type={self.action_type}, "
            f"status={self.status}, duration={self.duration_ms:.0f}ms)"
        )


# ═══════════════════════════════════════════════════════════════
# Metric Snapshot
# ═══════════════════════════════════════════════════════════════


class MetricSnapshot(Base):
    """指标快照 — 持久化 GrowthMetrics 快照.

    替代: MetricsCollector._snapshots (内存列表)
    """

    __tablename__ = "growth_metric_snapshots"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    game_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )
    # Agent 指标
    decision_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    success_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    failure_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    # Execution 指标
    action_success: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    action_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    rollback_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    approval_waiting: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    # Business 指标
    spend: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    revenue: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    roas: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    ltv: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    installs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    purchases: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    impressions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    clicks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True,
    )

    def __repr__(self) -> str:
        return (
            f"MetricSnapshot(id={self.id}, game={self.game_id}, "
            f"roas={self.roas:.2f}, spend={self.spend:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
# Alert Record
# ═══════════════════════════════════════════════════════════════


class AlertRecord(Base):
    """报警记录 — 持久化 Alert.

    替代: AlertManager._alerts (内存列表)
    """

    __tablename__ = "growth_alerts"

    alert_id: Mapped[str] = mapped_column(
        String(48), primary_key=True, default=_new_uuid,
    )
    severity: Mapped[str] = mapped_column(
        String(32), nullable=False, default="info", index=True,
    )
    rule_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    game_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True,
    )
    metrics_data: Mapped[dict] = mapped_column(
        "metrics", JSONB, nullable=False, default=dict,
    )
    acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True,
    )

    def __repr__(self) -> str:
        return (
            f"AlertRecord(id={self.alert_id}, severity={self.severity}, "
            f"rule={self.rule_name}, ack={self.acknowledged})"
        )


# ═══════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "Base",
    "AuditRecord",
    "GrowthEventRecord",
    "ExecutionRecord",
    "MetricSnapshot",
    "AlertRecord",
]