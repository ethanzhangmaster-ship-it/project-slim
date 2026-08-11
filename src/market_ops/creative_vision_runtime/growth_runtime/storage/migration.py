"""E15.0.8 Migration Manager — 数据库迁移管理.

负责:
  - 自动创建表 (基于 SQLAlchemy Base.metadata)
  - 迁移状态追踪
  - 初始迁移 SQL 生成

用法:
    from market_ops.creative_vision_runtime.growth_runtime.storage import DatabaseManager
    from market_ops.creative_vision_runtime.growth_runtime.storage.models import Base
    from market_ops.creative_vision_runtime.growth_runtime.storage.migration import MigrationManager

    db = DatabaseManager()
    db.connect()
    mgr = MigrationManager(db)
    mgr.migrate(Base)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from .database import DatabaseManager

# ═══════════════════════════════════════════════════════════════
# SQL Migration Templates
# ═══════════════════════════════════════════════════════════════

INITIAL_MIGRATION_SQL = """
-- E15.0.8 Initial Growth Storage Migration
-- Creates core tables for persistent production control layer

-- Audit Records: 审计决策记录
CREATE TABLE IF NOT EXISTS growth_audit_records (
    id VARCHAR(48) PRIMARY KEY,
    game_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(64) NOT NULL DEFAULT '',
    detected_problem TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL DEFAULT '',
    action VARCHAR(64) NOT NULL DEFAULT '',
    confidence FLOAT NOT NULL DEFAULT 0.0,
    input_context JSONB NOT NULL DEFAULT '{}',
    execution_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    result JSONB NOT NULL DEFAULT '{}',
    plan_id VARCHAR(64) NOT NULL DEFAULT '',
    cycle_id VARCHAR(64) NOT NULL DEFAULT '',
    safety_decision VARCHAR(32) NOT NULL DEFAULT '',
    rollback_record_id VARCHAR(64) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_game_id ON growth_audit_records(game_id);
CREATE INDEX IF NOT EXISTS idx_audit_status ON growth_audit_records(execution_status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON growth_audit_records(created_at);

-- Growth Events: 统一增长事件
CREATE TABLE IF NOT EXISTS growth_events (
    event_id VARCHAR(48) PRIMARY KEY,
    game_id VARCHAR(64) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'internal',
    event_type VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metrics JSONB NOT NULL DEFAULT '{}',
    campaign_id VARCHAR(64) NOT NULL DEFAULT '',
    creative_id VARCHAR(64) NOT NULL DEFAULT '',
    platform VARCHAR(32) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_game_id ON growth_events(game_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON growth_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON growth_events(timestamp);

-- Execution Records: Worker执行历史
CREATE TABLE IF NOT EXISTS growth_execution_records (
    execution_id VARCHAR(48) PRIMARY KEY,
    action_id VARCHAR(64) NOT NULL DEFAULT '',
    action_type VARCHAR(64) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    output JSONB NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    duration_ms FLOAT NOT NULL DEFAULT 0.0,
    rollback_record_id VARCHAR(64) NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_exec_action_id ON growth_execution_records(action_id);
CREATE INDEX IF NOT EXISTS idx_exec_type ON growth_execution_records(action_type);
CREATE INDEX IF NOT EXISTS idx_exec_status ON growth_execution_records(status);

-- Metric Snapshots: 指标快照
CREATE TABLE IF NOT EXISTS growth_metric_snapshots (
    id BIGSERIAL PRIMARY KEY,
    game_id VARCHAR(64) NOT NULL,
    decision_count INTEGER NOT NULL DEFAULT 0,
    success_rate FLOAT NOT NULL DEFAULT 0.0,
    failure_rate FLOAT NOT NULL DEFAULT 0.0,
    action_success INTEGER NOT NULL DEFAULT 0,
    action_failed INTEGER NOT NULL DEFAULT 0,
    rollback_count INTEGER NOT NULL DEFAULT 0,
    approval_waiting INTEGER NOT NULL DEFAULT 0,
    spend FLOAT NOT NULL DEFAULT 0.0,
    revenue FLOAT NOT NULL DEFAULT 0.0,
    roas FLOAT NOT NULL DEFAULT 0.0,
    ltv FLOAT NOT NULL DEFAULT 0.0,
    installs INTEGER NOT NULL DEFAULT 0,
    purchases INTEGER NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_game_id ON growth_metric_snapshots(game_id);
CREATE INDEX IF NOT EXISTS idx_metrics_created ON growth_metric_snapshots(created_at);

-- Alerts: 报警记录
CREATE TABLE IF NOT EXISTS growth_alerts (
    alert_id VARCHAR(48) PRIMARY KEY,
    severity VARCHAR(32) NOT NULL DEFAULT 'info',
    rule_name VARCHAR(64) NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    game_id VARCHAR(64) NOT NULL DEFAULT '',
    metrics JSONB NOT NULL DEFAULT '{}',
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_severity ON growth_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_game_id ON growth_alerts(game_id);
CREATE INDEX IF NOT EXISTS idx_alerts_ack ON growth_alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON growth_alerts(created_at);

-- Migration tracking table
CREATE TABLE IF NOT EXISTS growth_migrations (
    id SERIAL PRIMARY KEY,
    version VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class MigrationManager:
    """迁移管理器 — 管理数据库 schema 变更.

    用法:
        db = DatabaseManager()
        db.connect()
        mgr = MigrationManager(db)
        mgr.migrate(Base)  # ORM 自动建表

        # 或手动执行 SQL
        mgr.execute_sql(INITIAL_MIGRATION_SQL)
    """

    CURRENT_VERSION = "001_initial_growth_storage"

    def __init__(self, db: DatabaseManager):
        self._db = db

    # ── Auto Migration (ORM) ─────────────────────────────────

    def migrate(self, base: Any) -> None:
        """基于 SQLAlchemy ORM 自动创建表."""
        base.metadata.create_all(self._db.engine)

    def rollback(self, base: Any) -> None:
        """删除所有 ORM 表."""
        base.metadata.drop_all(self._db.engine)

    # ── Manual SQL Migration ─────────────────────────────────

    def execute_sql(self, sql: str) -> None:
        """执行原始 SQL 迁移."""
        with self._db.session() as session:
            # Split by semicolons and execute each statement
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt and not stmt.startswith("--"):
                    session.execute(text(stmt))

    def apply_initial_migration(self) -> None:
        """应用初始迁移."""
        self.execute_sql(INITIAL_MIGRATION_SQL)
        self._record_migration(self.CURRENT_VERSION, "Initial Growth Storage Schema")

    # ── Migration Tracking ───────────────────────────────────

    def _record_migration(self, version: str, name: str) -> None:
        """记录迁移版本."""
        with self._db.session() as session:
            session.execute(
                text(
                    "INSERT INTO growth_migrations (version, name) "
                    "VALUES (:version, :name) "
                    "ON CONFLICT (version) DO NOTHING"
                ),
                {"version": version, "name": name},
            )

    def get_applied_migrations(self) -> list[dict[str, Any]]:
        """获取已应用的迁移列表."""
        try:
            with self._db.session() as session:
                result = session.execute(
                    text(
                        "SELECT version, name, applied_at "
                        "FROM growth_migrations "
                        "ORDER BY id"
                    )
                ).fetchall()
                return [
                    {"version": r[0], "name": r[1], "applied_at": str(r[2])}
                    for r in result
                ]
        except Exception:
            return []

    def is_migration_applied(self, version: str) -> bool:
        """检查迁移是否已应用."""
        try:
            with self._db.session() as session:
                result = session.execute(
                    text("SELECT 1 FROM growth_migrations WHERE version = :version"),
                    {"version": version},
                ).scalar()
                return result is not None
        except Exception:
            return False

    # ── Table Info ───────────────────────────────────────────

    def get_table_names(self) -> list[str]:
        """获取所有表名."""
        from sqlalchemy import inspect
        inspector = inspect(self._db.engine)
        return inspector.get_table_names()

    def get_table_count(self, table_name: str) -> int:
        """获取表行数."""
        try:
            with self._db.session() as session:
                result = session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()
                return int(result) if result is not None else 0
        except Exception:
            return 0

    def get_status(self) -> dict[str, Any]:
        """获取迁移状态."""
        tables = self.get_table_names()
        return {
            "current_version": self.CURRENT_VERSION,
            "applied_migrations": self.get_applied_migrations(),
            "tables": tables,
            "table_counts": {
                t: self.get_table_count(t)
                for t in tables
                if t != "growth_migrations"
            },
        }


__all__ = ["MigrationManager", "INITIAL_MIGRATION_SQL"]