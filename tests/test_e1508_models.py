"""E15.0.8 SQLAlchemy ORM Models — 单元测试.

验证所有持久化模型的完整功能:
  - AuditRecord:      创建/默认值/JSONB/更新/查询 (8 tests)
  - GrowthEventRecord: 创建/默认值/JSONB/查询 (5 tests)
  - ExecutionRecord:   创建/默认值/状态转换/查询 (6 tests)
  - MetricSnapshot:    创建/默认值/数值字段/趋势查询 (6 tests)
  - AlertRecord:       创建/默认值/确认/严重度查询 (5 tests)

总计: 30 个测试用例
使用 SQLite 内存数据库 (sqlite:///:memory:)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# Mock redis before importing storage modules to avoid ModuleNotFoundError
sys.modules.setdefault("redis", MagicMock())

# Register JSONB → JSON compilation for SQLite (JSONB is PostgreSQL-specific)
@compiles(JSONB, "sqlite")
def _compile_jsonb_on_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(type_, **kw)

from market_ops.creative_vision_runtime.growth_runtime.storage.database import DatabaseManager
from market_ops.creative_vision_runtime.growth_runtime.storage.models import (
    AlertRecord,
    AuditRecord,
    Base,
    ExecutionRecord,
    GrowthEventRecord,
    MetricSnapshot,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_audit(
    game_id: str = "P01",
    agent_id: str = "agent_01",
    detected_problem: str = "ROAS decay detected",
    decision: str = "reduce budget 20%",
    action: str = "update_budget",
    confidence: float = 0.87,
    input_context: dict | None = None,
    execution_status: str = "pending",
    result: dict | None = None,
    plan_id: str = "",
    cycle_id: str = "",
    safety_decision: str = "",
    rollback_record_id: str = "",
    metadata_: dict | None = None,
) -> AuditRecord:
    return AuditRecord(
        game_id=game_id,
        agent_id=agent_id,
        detected_problem=detected_problem,
        decision=decision,
        action=action,
        confidence=confidence,
        input_context=input_context or {"roas": 1.0, "spend": 500},
        execution_status=execution_status,
        result=result or {},
        plan_id=plan_id,
        cycle_id=cycle_id,
        safety_decision=safety_decision,
        rollback_record_id=rollback_record_id,
        metadata_=metadata_ or {},
    )


def _make_event(
    game_id: str = "P01",
    source: str = "internal",
    event_type: str = "budget_change",
    metrics: dict | None = None,
    campaign_id: str = "",
    creative_id: str = "",
    platform: str = "",
    metadata_: dict | None = None,
) -> GrowthEventRecord:
    return GrowthEventRecord(
        game_id=game_id,
        source=source,
        event_type=event_type,
        metrics=metrics or {"roas": 1.5, "spend": 300},
        campaign_id=campaign_id,
        creative_id=creative_id,
        platform=platform,
        metadata_=metadata_ or {},
    )


def _make_execution(
    action_id: str = "action_001",
    action_type: str = "update_budget",
    params: dict | None = None,
    status: str = "pending",
    output: dict | None = None,
    error: str = "",
    duration_ms: float = 0.0,
    rollback_record_id: str = "",
) -> ExecutionRecord:
    return ExecutionRecord(
        action_id=action_id,
        action_type=action_type,
        params=params or {"budget": 1000},
        status=status,
        output=output or {},
        error=error,
        duration_ms=duration_ms,
        rollback_record_id=rollback_record_id,
    )


def _make_metric(
    game_id: str = "P01",
    decision_count: int = 0,
    success_rate: float = 0.0,
    failure_rate: float = 0.0,
    action_success: int = 0,
    action_failed: int = 0,
    rollback_count: int = 0,
    approval_waiting: int = 0,
    spend: float = 0.0,
    revenue: float = 0.0,
    roas: float = 0.0,
    ltv: float = 0.0,
    installs: int = 0,
    purchases: int = 0,
    impressions: int = 0,
    clicks: int = 0,
) -> MetricSnapshot:
    return MetricSnapshot(
        game_id=game_id,
        decision_count=decision_count,
        success_rate=success_rate,
        failure_rate=failure_rate,
        action_success=action_success,
        action_failed=action_failed,
        rollback_count=rollback_count,
        approval_waiting=approval_waiting,
        spend=spend,
        revenue=revenue,
        roas=roas,
        ltv=ltv,
        installs=installs,
        purchases=purchases,
        impressions=impressions,
        clicks=clicks,
    )


def _make_alert(
    severity: str = "info",
    rule_name: str = "roas_drop",
    message: str = "ROAS dropped below threshold",
    game_id: str = "P01",
    metrics_data: dict | None = None,
    acknowledged: bool = False,
) -> AlertRecord:
    return AlertRecord(
        severity=severity,
        rule_name=rule_name,
        message=message,
        game_id=game_id,
        metrics_data=metrics_data or {"roas": 0.5, "threshold": 1.0},
        acknowledged=acknowledged,
    )


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def db() -> DatabaseManager:
    """创建内存 SQLite 数据库并初始化所有表.

    DatabaseManager.connect() 默认参数 (max_overflow, pool_recycle) 与 SQLite
    不兼容，因此直接创建 engine 和 session_factory 注入到 manager 实例中。
    """
    manager = DatabaseManager(database_url="sqlite:///:memory:")
    manager._engine = create_engine("sqlite:///:memory:", echo=False)
    manager._session_factory = sessionmaker(
        bind=manager._engine, expire_on_commit=False,
    )
    manager.create_all_tables(Base)
    yield manager
    manager.close()


# ═══════════════════════════════════════════════════════════
# AuditRecord — Creation & Defaults
# ═══════════════════════════════════════════════════════════

class TestAuditRecordCreation:
    """AuditRecord 创建与默认值测试."""

    def test_create_with_defaults(self, db):
        """默认字段创建 — 验证所有字段默认值."""
        record = AuditRecord(game_id="P01")
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.id is not None
        assert len(record.id) == 36  # UUID string
        assert record.game_id == "P01"
        assert record.agent_id == ""
        assert record.detected_problem == ""
        assert record.decision == ""
        assert record.action == ""
        assert record.confidence == 0.0
        assert record.input_context == {}
        assert record.execution_status == "pending"
        assert record.result == {}
        assert record.plan_id == ""
        assert record.cycle_id == ""
        assert record.safety_decision == ""
        assert record.rollback_record_id == ""
        assert record.metadata_ == {}
        assert record.created_at is not None
        assert record.updated_at is not None

    def test_create_with_all_fields(self, db):
        """全字段创建 — 验证所有字段值正确存储."""
        record = _make_audit(
            game_id="P42",
            agent_id="agent_42",
            detected_problem="ROAS sudden drop",
            decision="pause campaign",
            action="pause_campaign",
            confidence=0.95,
            input_context={"roas": 2.5, "spend": 1000},
            execution_status="approved",
            result={"roas_before": 2.5, "roas_after": 2.8},
            plan_id="plan_1",
            cycle_id="cycle_3",
            safety_decision="approved",
            rollback_record_id="rb_001",
            metadata_={"source": "test"},
        )
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.game_id == "P42"
        assert record.agent_id == "agent_42"
        assert record.detected_problem == "ROAS sudden drop"
        assert record.decision == "pause campaign"
        assert record.action == "pause_campaign"
        assert record.confidence == 0.95
        assert record.input_context == {"roas": 2.5, "spend": 1000}
        assert record.execution_status == "approved"
        assert record.result == {"roas_before": 2.5, "roas_after": 2.8}
        assert record.plan_id == "plan_1"
        assert record.cycle_id == "cycle_3"
        assert record.safety_decision == "approved"
        assert record.rollback_record_id == "rb_001"
        assert record.metadata_ == {"source": "test"}

    def test_id_is_unique(self, db):
        """每条记录的 id 唯一."""
        ids = set()
        with db.session() as session:
            for _ in range(50):
                record = AuditRecord(game_id="P01")
                session.add(record)
                session.flush()
                ids.add(record.id)
        assert len(ids) == 50

    def test_created_at_auto_set(self, db):
        """created_at 在插入时自动设置."""
        before = _utcnow()
        record = AuditRecord(game_id="P01")
        with db.session() as session:
            session.add(record)
            session.flush()
        after = _utcnow()

        assert record.created_at is not None
        assert before <= record.created_at <= after

    def test_updated_at_on_update(self, db):
        """updated_at 在更新时自动刷新."""
        record = AuditRecord(game_id="P01")
        with db.session() as session:
            session.add(record)
            session.flush()
            original_updated_at = record.updated_at

            record.execution_status = "success"
            session.flush()

        assert record.updated_at is not None
        assert record.updated_at >= original_updated_at


# ═══════════════════════════════════════════════════════════
# AuditRecord — JSONB & Update & Query
# ═══════════════════════════════════════════════════════════

class TestAuditRecordJSONB:
    """AuditRecord JSONB 字段序列化测试."""

    def test_jsonb_fields_roundtrip(self, db):
        """JSONB 字段 (input_context, result, metadata_) 完整往返."""
        record = _make_audit(
            input_context={"roas": 1.5, "spend": 800, "nested": {"key": "val"}},
            result={"status": "ok", "data": [1, 2, 3]},
            metadata_={"version": 2, "flags": {"valid": True}},
        )
        with db.session() as session:
            session.add(record)
            session.flush()

            # 在同一 session 中查询
            retrieved = session.get(AuditRecord, record.id)

        assert retrieved is not None
        assert retrieved.input_context == {"roas": 1.5, "spend": 800, "nested": {"key": "val"}}
        assert retrieved.result == {"status": "ok", "data": [1, 2, 3]}
        assert retrieved.metadata_ == {"version": 2, "flags": {"valid": True}}

    def test_update_execution_status(self, db):
        """更新 execution_status 字段."""
        record = _make_audit(execution_status="pending")
        with db.session() as session:
            session.add(record)
            session.flush()

            record.execution_status = "success"
            record.result = {"roas_after": 1.8}
            session.flush()

        assert record.execution_status == "success"
        assert record.result == {"roas_after": 1.8}

    def test_query_by_game_id(self, db):
        """按 game_id 查询审计记录."""
        with db.session() as session:
            session.add(_make_audit(game_id="P04"))
            session.add(_make_audit(game_id="P04"))
            session.add(_make_audit(game_id="P05"))
            session.flush()

            stmt = select(AuditRecord).where(AuditRecord.game_id == "P04")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)


# ═══════════════════════════════════════════════════════════
# GrowthEventRecord — Creation & Defaults
# ═══════════════════════════════════════════════════════════

class TestGrowthEventRecordCreation:
    """GrowthEventRecord 创建与默认值测试."""

    def test_create_with_defaults(self, db):
        """默认字段创建."""
        record = GrowthEventRecord(game_id="P01", event_type="budget_change")
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.event_id is not None
        assert len(record.event_id) == 36
        assert record.game_id == "P01"
        assert record.source == "internal"
        assert record.event_type == "budget_change"
        assert record.timestamp is not None
        assert record.metrics == {}
        assert record.campaign_id == ""
        assert record.creative_id == ""
        assert record.platform == ""
        assert record.metadata_ == {}
        assert record.created_at is not None

    def test_create_with_all_fields(self, db):
        """全字段创建."""
        record = _make_event(
            game_id="P42",
            source="facebook",
            event_type="campaign_launch",
            metrics={"impressions": 10000, "clicks": 500},
            campaign_id="camp_123",
            creative_id="creative_456",
            platform="facebook",
            metadata_={"batch": "A"},
        )
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.game_id == "P42"
        assert record.source == "facebook"
        assert record.event_type == "campaign_launch"
        assert record.metrics == {"impressions": 10000, "clicks": 500}
        assert record.campaign_id == "camp_123"
        assert record.creative_id == "creative_456"
        assert record.platform == "facebook"
        assert record.metadata_ == {"batch": "A"}


# ═══════════════════════════════════════════════════════════
# GrowthEventRecord — JSONB & Query
# ═══════════════════════════════════════════════════════════

class TestGrowthEventRecordJSONBQuery:
    """GrowthEventRecord JSONB 与查询测试."""

    def test_jsonb_fields_roundtrip(self, db):
        """JSONB 字段 (metrics, metadata_) 完整往返."""
        record = _make_event(
            metrics={"roas": 2.0, "revenue": 5000, "breakdown": {"channel": "fb"}},
            metadata_={"source_version": "1.2.3"},
        )
        with db.session() as session:
            session.add(record)
            session.flush()
            retrieved = session.get(GrowthEventRecord, record.event_id)

        assert retrieved is not None
        assert retrieved.metrics == {"roas": 2.0, "revenue": 5000, "breakdown": {"channel": "fb"}}
        assert retrieved.metadata_ == {"source_version": "1.2.3"}

    def test_query_by_event_type(self, db):
        """按 event_type 查询."""
        with db.session() as session:
            session.add(_make_event(event_type="budget_change"))
            session.add(_make_event(event_type="budget_change"))
            session.add(_make_event(event_type="campaign_launch"))
            session.flush()

            stmt = select(GrowthEventRecord).where(GrowthEventRecord.event_type == "budget_change")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.event_type == "budget_change" for r in results)

    def test_query_by_game_id(self, db):
        """按 game_id 查询."""
        with db.session() as session:
            session.add(_make_event(game_id="P04"))
            session.add(_make_event(game_id="P04"))
            session.add(_make_event(game_id="P05"))
            session.flush()

            stmt = select(GrowthEventRecord).where(GrowthEventRecord.game_id == "P04")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)


# ═══════════════════════════════════════════════════════════
# ExecutionRecord — Creation & Defaults
# ═══════════════════════════════════════════════════════════

class TestExecutionRecordCreation:
    """ExecutionRecord 创建与默认值测试."""

    def test_create_with_defaults(self, db):
        """默认字段创建."""
        record = ExecutionRecord(action_type="update_budget")
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.execution_id is not None
        assert len(record.execution_id) == 36
        assert record.action_id == ""
        assert record.action_type == "update_budget"
        assert record.params == {}
        assert record.status == "pending"
        assert record.output == {}
        assert record.error == ""
        assert record.duration_ms == 0.0
        assert record.rollback_record_id == ""
        assert record.started_at is not None
        assert record.finished_at is None

    def test_create_with_all_fields(self, db):
        """全字段创建."""
        now = _utcnow()
        record = _make_execution(
            action_id="action_042",
            action_type="scale_campaign",
            params={"campaign_id": "camp_1", "scale": 1.5},
            status="success",
            output={"new_budget": 1500},
            error="",
            duration_ms=150.5,
            rollback_record_id="rb_002",
        )
        record.finished_at = now
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.action_id == "action_042"
        assert record.action_type == "scale_campaign"
        assert record.params == {"campaign_id": "camp_1", "scale": 1.5}
        assert record.status == "success"
        assert record.output == {"new_budget": 1500}
        assert record.error == ""
        assert record.duration_ms == 150.5
        assert record.rollback_record_id == "rb_002"
        assert record.finished_at == now


# ═══════════════════════════════════════════════════════════
# ExecutionRecord — Status Transitions & Query
# ═══════════════════════════════════════════════════════════

class TestExecutionRecordStatus:
    """ExecutionRecord 状态转换与查询测试."""

    def test_status_default_pending(self, db):
        """默认 status 为 pending."""
        record = ExecutionRecord(action_type="update_budget")
        with db.session() as session:
            session.add(record)
            session.flush()
        assert record.status == "pending"

    def test_status_transition_to_success(self, db):
        """状态从 pending 转换到 success."""
        record = _make_execution(status="pending")
        with db.session() as session:
            session.add(record)
            session.flush()

            record.status = "success"
            record.output = {"result": "ok"}
            record.duration_ms = 200.0
            record.finished_at = _utcnow()
            session.flush()

        assert record.status == "success"
        assert record.output == {"result": "ok"}
        assert record.duration_ms == 200.0
        assert record.finished_at is not None

    def test_status_transition_to_failed(self, db):
        """状态从 pending 转换到 failed."""
        record = _make_execution(status="pending")
        with db.session() as session:
            session.add(record)
            session.flush()

            record.status = "failed"
            record.error = "Connection timeout"
            record.finished_at = _utcnow()
            session.flush()

        assert record.status == "failed"
        assert record.error == "Connection timeout"
        assert record.finished_at is not None

    def test_query_by_status(self, db):
        """按 status 查询."""
        with db.session() as session:
            session.add(_make_execution(status="success"))
            session.add(_make_execution(status="failed"))
            session.add(_make_execution(status="success"))
            session.flush()

            stmt = select(ExecutionRecord).where(ExecutionRecord.status == "success")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    def test_query_by_action_type(self, db):
        """按 action_type 查询."""
        with db.session() as session:
            session.add(_make_execution(action_type="update_budget"))
            session.add(_make_execution(action_type="scale_campaign"))
            session.add(_make_execution(action_type="update_budget"))
            session.flush()

            stmt = select(ExecutionRecord).where(ExecutionRecord.action_type == "update_budget")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.action_type == "update_budget" for r in results)


# ═══════════════════════════════════════════════════════════
# MetricSnapshot — Creation & Defaults
# ═══════════════════════════════════════════════════════════

class TestMetricSnapshotCreation:
    """MetricSnapshot 创建与默认值测试."""

    def test_create_with_defaults(self, db):
        """默认字段创建."""
        record = MetricSnapshot(game_id="P01")
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.id is not None
        assert isinstance(record.id, int)
        assert record.game_id == "P01"
        assert record.decision_count == 0
        assert record.success_rate == 0.0
        assert record.failure_rate == 0.0
        assert record.action_success == 0
        assert record.action_failed == 0
        assert record.rollback_count == 0
        assert record.approval_waiting == 0
        assert record.spend == 0.0
        assert record.revenue == 0.0
        assert record.roas == 0.0
        assert record.ltv == 0.0
        assert record.installs == 0
        assert record.purchases == 0
        assert record.impressions == 0
        assert record.clicks == 0
        assert record.created_at is not None

    def test_create_with_all_fields(self, db):
        """全字段创建."""
        record = _make_metric(
            game_id="P42",
            decision_count=10,
            success_rate=0.8,
            failure_rate=0.2,
            action_success=8,
            action_failed=2,
            rollback_count=1,
            approval_waiting=3,
            spend=5000.0,
            revenue=12000.0,
            roas=2.4,
            ltv=45.5,
            installs=2000,
            purchases=150,
            impressions=50000,
            clicks=3000,
        )
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.game_id == "P42"
        assert record.decision_count == 10
        assert record.success_rate == 0.8
        assert record.failure_rate == 0.2
        assert record.action_success == 8
        assert record.action_failed == 2
        assert record.rollback_count == 1
        assert record.approval_waiting == 3
        assert record.spend == 5000.0
        assert record.revenue == 12000.0
        assert record.roas == 2.4
        assert record.ltv == 45.5
        assert record.installs == 2000
        assert record.purchases == 150
        assert record.impressions == 50000
        assert record.clicks == 3000


# ═══════════════════════════════════════════════════════════
# MetricSnapshot — Numeric & Query
# ═══════════════════════════════════════════════════════════

class TestMetricSnapshotNumeric:
    """MetricSnapshot 数值字段与查询测试."""

    def test_numeric_fields_precision(self, db):
        """浮点数字段精度验证."""
        record = _make_metric(
            success_rate=0.875,
            failure_rate=0.125,
            roas=3.14159,
            ltv=12.345678,
        )
        with db.session() as session:
            session.add(record)
            session.flush()
            retrieved = session.get(MetricSnapshot, record.id)

        assert retrieved is not None
        assert retrieved.success_rate == pytest.approx(0.875)
        assert retrieved.failure_rate == pytest.approx(0.125)
        assert retrieved.roas == pytest.approx(3.14159)
        assert retrieved.ltv == pytest.approx(12.345678)

    def test_query_by_game_id(self, db):
        """按 game_id 查询."""
        with db.session() as session:
            session.add(_make_metric(game_id="P04"))
            session.add(_make_metric(game_id="P04"))
            session.add(_make_metric(game_id="P05"))
            session.flush()

            stmt = select(MetricSnapshot).where(MetricSnapshot.game_id == "P04")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)

    def test_multiple_snapshots_ordering(self, db):
        """多个快照按 created_at 排序."""
        with db.session() as session:
            for i in range(3):
                session.add(_make_metric(game_id="P04", decision_count=i))
            session.flush()

            stmt = (
                select(MetricSnapshot)
                .where(MetricSnapshot.game_id == "P04")
                .order_by(MetricSnapshot.created_at.asc())
            )
            results = session.execute(stmt).scalars().all()

        assert len(results) == 3
        assert [r.decision_count for r in results] == [0, 1, 2]

    def test_roas_computation(self, db):
        """ROAS = revenue / spend 验证."""
        record = _make_metric(spend=1000.0, revenue=2500.0, roas=2.5)
        with db.session() as session:
            session.add(record)
            session.flush()
            retrieved = session.get(MetricSnapshot, record.id)

        assert retrieved is not None
        assert retrieved.spend == 1000.0
        assert retrieved.revenue == 2500.0
        assert retrieved.roas == 2.5
        assert retrieved.roas == pytest.approx(retrieved.revenue / retrieved.spend)


# ═══════════════════════════════════════════════════════════
# AlertRecord — Creation & Defaults
# ═══════════════════════════════════════════════════════════

class TestAlertRecordCreation:
    """AlertRecord 创建与默认值测试."""

    def test_create_with_defaults(self, db):
        """默认字段创建."""
        record = AlertRecord()
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.alert_id is not None
        assert len(record.alert_id) == 36
        assert record.severity == "info"
        assert record.rule_name == ""
        assert record.message == ""
        assert record.game_id == ""
        assert record.metrics_data == {}
        assert record.acknowledged is False
        assert record.created_at is not None

    def test_create_with_all_fields(self, db):
        """全字段创建."""
        record = _make_alert(
            severity="critical",
            rule_name="budget_overspend",
            message="Daily spend exceeded limit",
            game_id="P42",
            metrics_data={"spend": 5000, "limit": 3000, "excess": 2000},
            acknowledged=True,
        )
        with db.session() as session:
            session.add(record)
            session.flush()

        assert record.severity == "critical"
        assert record.rule_name == "budget_overspend"
        assert record.message == "Daily spend exceeded limit"
        assert record.game_id == "P42"
        assert record.metrics_data == {"spend": 5000, "limit": 3000, "excess": 2000}
        assert record.acknowledged is True


# ═══════════════════════════════════════════════════════════
# AlertRecord — Acknowledge & Query
# ═══════════════════════════════════════════════════════════

class TestAlertRecordAcknowledge:
    """AlertRecord 确认与查询测试."""

    def test_acknowledge_alert(self, db):
        """确认告警 — acknowledged 从 False 变为 True."""
        record = _make_alert(acknowledged=False)
        with db.session() as session:
            session.add(record)
            session.flush()

            assert record.acknowledged is False

            record.acknowledged = True
            session.flush()

        assert record.acknowledged is True

    def test_query_by_severity(self, db):
        """按 severity 查询."""
        with db.session() as session:
            session.add(_make_alert(severity="critical"))
            session.add(_make_alert(severity="warning"))
            session.add(_make_alert(severity="critical"))
            session.flush()

            stmt = select(AlertRecord).where(AlertRecord.severity == "critical")
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.severity == "critical" for r in results)

    def test_query_unacknowledged(self, db):
        """查询未确认的告警."""
        with db.session() as session:
            session.add(_make_alert(acknowledged=False))
            session.add(_make_alert(acknowledged=True))
            session.add(_make_alert(acknowledged=False))
            session.flush()

            stmt = select(AlertRecord).where(AlertRecord.acknowledged == False)  # noqa: E712
            results = session.execute(stmt).scalars().all()

        assert len(results) == 2
        assert all(r.acknowledged is False for r in results)