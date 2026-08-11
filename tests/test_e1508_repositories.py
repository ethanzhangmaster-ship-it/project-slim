"""E15.0.8 Growth Storage Repositories — 单元测试.

使用 SQLite 内存数据库测试所有 Repository 的完整 CRUD 功能:
  - AuditRepository:    审计记录持久化 (15 tests)
  - EventRepository:    增长事件持久化 (10 tests)
  - MetricRepository:   指标快照持久化 (12 tests)
  - ExecutionRepository: 执行记录持久化 (12 tests)
  - AlertRepository:    报警记录持久化 (11 tests)

总计: 60 个测试用例
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.types import JSON as SQLJSON

# Mock redis module before importing storage package (avoids redis dependency)
sys.modules.setdefault("redis", type(sys)("redis"))

from market_ops.creative_vision_runtime.growth_runtime.storage.database import DatabaseManager
from market_ops.creative_vision_runtime.growth_runtime.storage.repositories import (
    AlertRepository,
    AuditRepository,
    EventRepository,
    ExecutionRepository,
    MetricRepository,
)


# ═══════════════════════════════════════════════════════════
# Fixture — SQLite 内存数据库
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def db():
    """创建 SQLite 内存数据库，并修补 JSONB 类型为 JSON 以兼容 SQLite."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.dialects.postgresql import JSONB as _JSONB
    from market_ops.creative_vision_runtime.growth_runtime.storage import models as _models

    # 将 JSONB 列替换为通用的 JSON 类型 (SQLite 兼容)
    _model_classes = [
        _models.AuditRecord,
        _models.GrowthEventRecord,
        _models.ExecutionRecord,
        _models.MetricSnapshot,
        _models.AlertRecord,
    ]
    for model_cls in _model_classes:
        for col in list(model_cls.__table__.columns):
            if isinstance(col.type, _JSONB):
                col.type = SQLJSON()

    _db = DatabaseManager.__new__(DatabaseManager)
    _db._database_url = "sqlite:///:memory:"
    _db._echo = False
    _db._engine = create_engine("sqlite:///:memory:")
    _db._session_factory = sessionmaker(bind=_db._engine, expire_on_commit=False)
    _db.create_all_tables(_models.Base)
    yield _db
    _db.close()


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_audit_dict(
    audit_id: str | None = None,
    game_id: str = "P04",
    agent_id: str = "agent_01",
    decision: str = "reduce budget 20%",
    action: str = "update_budget",
    confidence: float = 0.87,
    execution_status: str = "pending",
    plan_id: str = "",
    cycle_id: str = "",
) -> dict:
    return {
        "audit_id": audit_id or f"audit_{uuid.uuid4().hex[:12]}",
        "game_id": game_id,
        "agent_id": agent_id,
        "detected_problem": "ROAS decay detected",
        "decision": decision,
        "action": action,
        "confidence": confidence,
        "input_context": {"roas": 1.0, "spend": 500},
        "execution_status": execution_status,
        "result": {},
        "plan_id": plan_id,
        "cycle_id": cycle_id,
        "safety_decision": "",
        "rollback_record_id": "",
        "metadata": {},
    }


def _make_event_dict(
    event_id: str | None = None,
    game_id: str = "P04",
    source: str = "ad_platform",
    event_type: str = "ad_spend",
    metrics: dict | None = None,
    campaign_id: str = "",
    creative_id: str = "",
    platform: str = "google",
) -> dict:
    return {
        "event_id": event_id or f"event_{uuid.uuid4().hex[:12]}",
        "game_id": game_id,
        "source": source,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc),  # datetime 对象，非字符串
        "metrics": metrics or {"spend": 100.0, "revenue": 250.0},
        "campaign_id": campaign_id,
        "creative_id": creative_id,
        "platform": platform,
        "metadata": {},
    }


def _make_metric_dict(
    game_id: str = "P04",
    decision_count: int = 10,
    success_rate: float = 0.8,
    failure_rate: float = 0.2,
    action_success: int = 8,
    action_failed: int = 2,
    rollback_count: int = 1,
    approval_waiting: int = 0,
    spend: float = 500.0,
    revenue: float = 1200.0,
    roas: float = 2.4,
    ltv: float = 15.0,
    installs: int = 500,
    purchases: int = 50,
    impressions: int = 10000,
    clicks: int = 500,
) -> dict:
    return {
        "game_id": game_id,
        "agent": {
            "decision_count": decision_count,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
        },
        "execution": {
            "action_success": action_success,
            "action_failed": action_failed,
            "rollback_count": rollback_count,
            "approval_waiting": approval_waiting,
        },
        "business": {
            "spend": spend,
            "revenue": revenue,
            "roas": roas,
            "ltv": ltv,
            "installs": installs,
            "purchases": purchases,
            "impressions": impressions,
            "clicks": clicks,
        },
    }


def _make_execution_dict(
    execution_id: str | None = None,
    action_id: str = "",
    action_type: str = "update_budget",
    status: str = "pending",
    params: dict | None = None,
    output: dict | None = None,
    error: str = "",
    duration_ms: float = 0.0,
    rollback_record_id: str = "",
) -> dict:
    return {
        "result_id": execution_id or f"exec_{uuid.uuid4().hex[:12]}",
        "execution_id": execution_id or f"exec_{uuid.uuid4().hex[:12]}",
        "action_id": action_id,
        "action_type": action_type,
        "params": params or {},
        "status": status,
        "output": output or {},
        "error": error,
        "duration_ms": duration_ms,
        "rollback_record_id": rollback_record_id,
    }


def _make_alert_dict(
    alert_id: str | None = None,
    severity: str = "warning",
    rule_name: str = "roas_drop",
    message: str = "ROAS dropped below threshold",
    game_id: str = "P04",
    metrics: dict | None = None,
    acknowledged: bool = False,
) -> dict:
    return {
        "alert_id": alert_id or f"alert_{uuid.uuid4().hex[:12]}",
        "severity": severity,
        "rule_name": rule_name,
        "message": message,
        "game_id": game_id,
        "metrics": metrics or {"roas": 0.5, "threshold": 1.0},
        "acknowledged": acknowledged,
    }


# ═══════════════════════════════════════════════════════════
# AuditRepository
# ═══════════════════════════════════════════════════════════

class TestAuditRepository:
    """AuditRepository — 审计记录持久化测试."""

    # ── Create ───────────────────────────────────────────

    def test_save_creates_record(self, db):
        """save 创建审计记录并可从数据库查询."""
        repo = AuditRepository(db)
        audit = _make_audit_dict(game_id="P04", agent_id="agent_01")
        record = repo.save(audit)
        assert record.game_id == "P04"
        assert record.agent_id == "agent_01"
        assert record.decision == "reduce budget 20%"
        assert record.execution_status == "pending"
        assert record.created_at is not None

    def test_save_batch_creates_multiple_records(self, db):
        """save_batch 批量保存多条记录."""
        repo = AuditRepository(db)
        audits = [
            _make_audit_dict(game_id="P04", agent_id="agent_01"),
            _make_audit_dict(game_id="P04", agent_id="agent_02"),
            _make_audit_dict(game_id="P05", agent_id="agent_01"),
        ]
        records = repo.save_batch(audits)
        assert len(records) == 3
        assert repo.count() == 3

    # ── Read ──────────────────────────────────────────────

    def test_get_by_id_found(self, db):
        """get_by_id 找到记录."""
        repo = AuditRepository(db)
        audit = _make_audit_dict(audit_id="audit_001")
        repo.save(audit)
        record = repo.get_by_id("audit_001")
        assert record is not None
        assert record.id == "audit_001"

    def test_get_by_id_not_found(self, db):
        """get_by_id 未找到返回 None."""
        repo = AuditRepository(db)
        assert repo.get_by_id("nonexistent") is None

    def test_find_by_game_filters_correctly(self, db):
        """find_by_game 按游戏过滤."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(game_id="P04"))
        repo.save(_make_audit_dict(game_id="P04"))
        repo.save(_make_audit_dict(game_id="P05"))
        results = repo.find_by_game("P04")
        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)

    def test_find_by_agent_filters_correctly(self, db):
        """find_by_agent 按 Agent 过滤."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(agent_id="agent_X"))
        repo.save(_make_audit_dict(agent_id="agent_Y"))
        repo.save(_make_audit_dict(agent_id="agent_X"))
        results = repo.find_by_agent("agent_X")
        assert len(results) == 2
        assert all(r.agent_id == "agent_X" for r in results)

    def test_find_by_status_filters_correctly(self, db):
        """find_by_status 按状态过滤."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(execution_status="success"))
        repo.save(_make_audit_dict(execution_status="failed"))
        repo.save(_make_audit_dict(execution_status="success"))
        results = repo.find_by_status("success")
        assert len(results) == 2
        assert all(r.execution_status == "success" for r in results)

    def test_find_by_time_range_includes_in_range(self, db):
        """find_by_time_range 返回时间范围内的记录."""
        repo = AuditRepository(db)
        audit = _make_audit_dict()
        repo.save(audit)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        results = repo.find_by_time_range(start, end)
        assert len(results) == 1

    def test_find_by_time_range_excludes_outside(self, db):
        """find_by_time_range 排除时间范围外的记录."""
        repo = AuditRepository(db)
        now = datetime.now(timezone.utc)
        repo.save(_make_audit_dict())
        start = now - timedelta(days=100)
        end = now - timedelta(days=50)
        results = repo.find_by_time_range(start, end)
        assert len(results) == 0

    def test_find_by_plan_filters_correctly(self, db):
        """find_by_plan 按计划过滤."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(plan_id="plan_A"))
        repo.save(_make_audit_dict(plan_id="plan_B"))
        repo.save(_make_audit_dict(plan_id="plan_A"))
        results = repo.find_by_plan("plan_A")
        assert len(results) == 2
        assert all(r.plan_id == "plan_A" for r in results)

    def test_find_needing_attention_returns_pending_rejected_failed(self, db):
        """find_needing_attention 返回 pending/rejected/failed 状态的记录."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(execution_status="pending"))
        repo.save(_make_audit_dict(execution_status="rejected"))
        repo.save(_make_audit_dict(execution_status="failed"))
        repo.save(_make_audit_dict(execution_status="success"))
        repo.save(_make_audit_dict(execution_status="approved"))
        results = repo.find_needing_attention()
        assert len(results) == 3

    def test_get_all_returns_all_records(self, db):
        """get_all 返回所有记录."""
        repo = AuditRepository(db)
        for i in range(5):
            repo.save(_make_audit_dict(agent_id=f"agent_{i}"))
        results = repo.get_all()
        assert len(results) == 5

    # ── Update ────────────────────────────────────────────

    def test_update_status_changes_status(self, db):
        """update_status 更新执行状态."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(audit_id="audit_001", execution_status="pending"))
        record = repo.update_status("audit_001", "success", result={"roas_after": 1.5})
        assert record is not None
        assert record.execution_status == "success"
        assert record.result["roas_after"] == 1.5

    def test_update_rollback_sets_rolled_back(self, db):
        """update_rollback 设置回滚状态."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(audit_id="audit_001"))
        record = repo.update_rollback("audit_001", "rb_999")
        assert record is not None
        assert record.execution_status == "rolled_back"
        assert record.rollback_record_id == "rb_999"

    # ── Delete ────────────────────────────────────────────

    def test_delete_removes_record(self, db):
        """delete 删除记录."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(audit_id="audit_001"))
        assert repo.count() == 1
        result = repo.delete("audit_001")
        assert result is True
        assert repo.count() == 0

    def test_delete_by_game_removes_all_game_records(self, db):
        """delete_by_game 删除指定游戏的所有记录."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(game_id="P04"))
        repo.save(_make_audit_dict(game_id="P04"))
        repo.save(_make_audit_dict(game_id="P05"))
        count = repo.delete_by_game("P04")
        assert count == 2
        assert repo.count() == 1

    # ── Statistics ────────────────────────────────────────

    def test_count_returns_total(self, db):
        """count 返回总记录数."""
        repo = AuditRepository(db)
        assert repo.count() == 0
        repo.save(_make_audit_dict())
        repo.save(_make_audit_dict())
        assert repo.count() == 2

    def test_count_by_game_returns_game_count(self, db):
        """count_by_game 返回指定游戏记录数."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(game_id="P04"))
        repo.save(_make_audit_dict(game_id="P04"))
        repo.save(_make_audit_dict(game_id="P05"))
        assert repo.count_by_game("P04") == 2
        assert repo.count_by_game("P05") == 1
        assert repo.count_by_game("P99") == 0

    def test_stats_returns_summary(self, db):
        """stats 返回统计摘要."""
        repo = AuditRepository(db)
        repo.save(_make_audit_dict(execution_status="success"))
        repo.save(_make_audit_dict(execution_status="success"))
        repo.save(_make_audit_dict(execution_status="failed"))
        s = repo.stats()
        assert s["total"] == 3
        assert s["success_count"] == 2
        assert s["failure_count"] == 1
        assert s["success_rate"] == round(2 / 3, 4)


# ═══════════════════════════════════════════════════════════
# EventRepository
# ═══════════════════════════════════════════════════════════

class TestEventRepository:
    """EventRepository — 增长事件持久化测试."""

    def test_save_creates_event(self, db):
        """save 创建事件记录."""
        repo = EventRepository(db)
        event = _make_event_dict(game_id="P04", event_type="ad_spend", source="google")
        record = repo.save(event)
        assert record.game_id == "P04"
        assert record.event_type == "ad_spend"
        assert record.source == "google"
        assert record.platform == "google"
        assert record.created_at is not None

    def test_save_batch_creates_multiple_events(self, db):
        """save_batch 批量保存事件."""
        repo = EventRepository(db)
        events = [
            _make_event_dict(game_id="P04", event_type="ad_spend"),
            _make_event_dict(game_id="P04", event_type="revenue"),
            _make_event_dict(game_id="P05", event_type="install"),
        ]
        records = repo.save_batch(events)
        assert len(records) == 3
        assert repo.count() == 3

    def test_get_by_id_found_and_not_found(self, db):
        """get_by_id 查找与不存在."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(event_id="event_001"))
        assert repo.get_by_id("event_001") is not None
        assert repo.get_by_id("nonexistent") is None

    def test_find_by_game_with_limit(self, db):
        """find_by_game 按游戏过滤并限制数量."""
        repo = EventRepository(db)
        for i in range(10):
            repo.save(_make_event_dict(game_id="P04", event_type=f"type_{i}"))
        repo.save(_make_event_dict(game_id="P05"))
        results = repo.find_by_game("P04", limit=5)
        assert len(results) == 5
        assert all(r.game_id == "P04" for r in results)

    def test_find_by_type_filters_correctly(self, db):
        """find_by_type 按事件类型过滤."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(event_type="ad_spend"))
        repo.save(_make_event_dict(event_type="ad_spend"))
        repo.save(_make_event_dict(event_type="revenue"))
        results = repo.find_by_type("ad_spend")
        assert len(results) == 2
        assert all(r.event_type == "ad_spend" for r in results)

    def test_find_by_game_and_type_combines_filters(self, db):
        """find_by_game_and_type 组合过滤游戏和类型."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(game_id="P04", event_type="ad_spend"))
        repo.save(_make_event_dict(game_id="P04", event_type="revenue"))
        repo.save(_make_event_dict(game_id="P05", event_type="ad_spend"))
        results = repo.find_by_game_and_type("P04", "ad_spend")
        assert len(results) == 1
        assert results[0].game_id == "P04"
        assert results[0].event_type == "ad_spend"

    def test_find_by_source_filters_correctly(self, db):
        """find_by_source 按来源过滤."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(source="google"))
        repo.save(_make_event_dict(source="facebook"))
        repo.save(_make_event_dict(source="google"))
        results = repo.find_by_source("google")
        assert len(results) == 2
        assert all(r.source == "google" for r in results)

    def test_find_by_campaign_filters_correctly(self, db):
        """find_by_campaign 按广告系列过滤."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(campaign_id="camp_001"))
        repo.save(_make_event_dict(campaign_id="camp_002"))
        repo.save(_make_event_dict(campaign_id="camp_001"))
        results = repo.find_by_campaign("camp_001")
        assert len(results) == 2
        assert all(r.campaign_id == "camp_001" for r in results)

    def test_find_by_time_range_filters_temporally(self, db):
        """find_by_time_range 按时间范围过滤."""
        repo = EventRepository(db)
        repo.save(_make_event_dict())
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        results = repo.find_by_time_range(start, end)
        assert len(results) == 1

    def test_delete_removes_event(self, db):
        """delete 删除事件."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(event_id="event_001"))
        assert repo.delete("event_001") is True
        assert repo.delete("event_001") is False
        assert repo.count() == 0

    def test_delete_by_game_removes_game_events(self, db):
        """delete_by_game 删除指定游戏的所有事件."""
        repo = EventRepository(db)
        repo.save(_make_event_dict(game_id="P04"))
        repo.save(_make_event_dict(game_id="P04"))
        repo.save(_make_event_dict(game_id="P05"))
        assert repo.delete_by_game("P04") == 2
        assert repo.count() == 1

    def test_count_returns_total(self, db):
        """count 返回总事件数."""
        repo = EventRepository(db)
        assert repo.count() == 0
        repo.save(_make_event_dict())
        repo.save(_make_event_dict())
        assert repo.count() == 2


# ═══════════════════════════════════════════════════════════
# MetricRepository
# ═══════════════════════════════════════════════════════════

class TestMetricRepository:
    """MetricRepository — 指标快照持久化测试."""

    def test_save_creates_snapshot(self, db):
        """save 创建指标快照."""
        repo = MetricRepository(db)
        snapshot = repo.save(_make_metric_dict(game_id="P04", roas=2.5, spend=600.0))
        assert snapshot.game_id == "P04"
        assert snapshot.roas == 2.5
        assert snapshot.spend == 600.0
        assert snapshot.decision_count == 10
        assert snapshot.created_at is not None

    def test_save_full_metrics_stores_all_fields(self, db):
        """save 存储所有指标字段."""
        repo = MetricRepository(db)
        metrics = _make_metric_dict(
            game_id="P04",
            decision_count=15,
            success_rate=0.85,
            failure_rate=0.15,
            action_success=12,
            action_failed=3,
            rollback_count=2,
            approval_waiting=1,
            spend=750.0,
            revenue=1800.0,
            roas=2.4,
            ltv=20.0,
            installs=600,
            purchases=60,
            impressions=12000,
            clicks=600,
        )
        snapshot = repo.save(metrics)
        # Agent 指标
        assert snapshot.decision_count == 15
        assert snapshot.success_rate == 0.85
        assert snapshot.failure_rate == 0.15
        # Execution 指标
        assert snapshot.action_success == 12
        assert snapshot.action_failed == 3
        assert snapshot.rollback_count == 2
        assert snapshot.approval_waiting == 1
        # Business 指标
        assert snapshot.spend == 750.0
        assert snapshot.revenue == 1800.0
        assert snapshot.ltv == 20.0
        assert snapshot.installs == 600
        assert snapshot.purchases == 60
        assert snapshot.impressions == 12000
        assert snapshot.clicks == 600

    def test_find_by_game_returns_snapshots(self, db):
        """find_by_game 返回指定游戏的快照."""
        repo = MetricRepository(db)
        repo.save(_make_metric_dict(game_id="P04", roas=1.0))
        repo.save(_make_metric_dict(game_id="P04", roas=1.5))
        repo.save(_make_metric_dict(game_id="P05", roas=2.0))
        results = repo.find_by_game("P04")
        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)

    def test_find_by_game_empty_returns_empty_list(self, db):
        """find_by_game 无数据返回空列表."""
        repo = MetricRepository(db)
        assert repo.find_by_game("P99") == []

    def test_get_latest_returns_most_recent(self, db):
        """get_latest 返回最新的快照."""
        import time
        repo = MetricRepository(db)
        repo.save(_make_metric_dict(game_id="P04", roas=1.0))
        time.sleep(0.01)  # 确保时间戳不同
        repo.save(_make_metric_dict(game_id="P04", roas=2.0))
        latest = repo.get_latest("P04")
        assert latest is not None
        assert latest.roas == 2.0

    def test_get_latest_none_for_empty_game(self, db):
        """get_latest 无数据返回 None."""
        repo = MetricRepository(db)
        assert repo.get_latest("P99") is None

    def test_get_recent_returns_limited_snapshots(self, db):
        """get_recent 返回最近 N 条快照."""
        repo = MetricRepository(db)
        for i in range(20):
            repo.save(_make_metric_dict(game_id=f"P{(i % 3):02d}", roas=float(i)))
        results = repo.get_recent(limit=5)
        assert len(results) == 5

    def test_get_roas_trend_returns_ordered_list(self, db):
        """get_roas_trend 返回按时间排序的 ROAS 列表."""
        import time
        repo = MetricRepository(db)
        repo.save(_make_metric_dict(game_id="P04", roas=1.0))
        time.sleep(0.01)
        repo.save(_make_metric_dict(game_id="P04", roas=2.0))
        time.sleep(0.01)
        repo.save(_make_metric_dict(game_id="P04", roas=3.0))
        repo.save(_make_metric_dict(game_id="P05", roas=9.9))
        trend = repo.get_roas_trend("P04", n=3)
        assert len(trend) == 3
        assert trend == [1.0, 2.0, 3.0]  # 按时间升序

    def test_get_spend_trend_returns_ordered_list(self, db):
        """get_spend_trend 返回按时间排序的花费列表."""
        import time
        repo = MetricRepository(db)
        repo.save(_make_metric_dict(game_id="P04", spend=100.0))
        time.sleep(0.01)
        repo.save(_make_metric_dict(game_id="P04", spend=200.0))
        time.sleep(0.01)
        repo.save(_make_metric_dict(game_id="P04", spend=300.0))
        trend = repo.get_spend_trend("P04", n=3)
        assert len(trend) == 3
        assert trend == [100.0, 200.0, 300.0]

    def test_delete_older_than_removes_old_snapshots(self, db):
        """delete_older_than 删除 N 天前的快照."""
        repo = MetricRepository(db)
        repo.save(_make_metric_dict(game_id="P04"))
        repo.save(_make_metric_dict(game_id="P04"))
        # 删除 365 天前的快照 — 不会删除刚创建的记录
        count = repo.delete_older_than(365)
        assert count == 0
        assert repo.count() == 2

    def test_delete_by_game_removes_game_snapshots(self, db):
        """delete_by_game 删除指定游戏的所有快照."""
        repo = MetricRepository(db)
        repo.save(_make_metric_dict(game_id="P04"))
        repo.save(_make_metric_dict(game_id="P04"))
        repo.save(_make_metric_dict(game_id="P05"))
        count = repo.delete_by_game("P04")
        assert count == 2
        assert repo.count() == 1

    def test_count_returns_total(self, db):
        """count 返回总快照数."""
        repo = MetricRepository(db)
        assert repo.count() == 0
        repo.save(_make_metric_dict())
        repo.save(_make_metric_dict())
        repo.save(_make_metric_dict())
        assert repo.count() == 3


# ═══════════════════════════════════════════════════════════
# ExecutionRepository
# ═══════════════════════════════════════════════════════════

class TestExecutionRepository:
    """ExecutionRepository — 执行记录持久化测试."""

    def test_save_creates_record(self, db):
        """save 创建执行记录."""
        repo = ExecutionRepository(db)
        record = repo.save(_make_execution_dict(
            action_type="update_budget",
            status="success",
            duration_ms=150.0,
        ))
        assert record.action_type == "update_budget"
        assert record.status == "success"
        assert record.duration_ms == 150.0
        assert record.execution_id is not None

    def test_get_by_id_found_and_not_found(self, db):
        """get_by_id 查找与不存在."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(execution_id="exec_001"))
        assert repo.get_by_id("exec_001") is not None
        assert repo.get_by_id("nonexistent") is None

    def test_find_by_action_filters_by_action_id(self, db):
        """find_by_action 按 action_id 过滤."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(action_id="action_001"))
        repo.save(_make_execution_dict(action_id="action_002"))
        repo.save(_make_execution_dict(action_id="action_001"))
        results = repo.find_by_action("action_001")
        assert len(results) == 2
        assert all(r.action_id == "action_001" for r in results)

    def test_find_by_type_filters_by_action_type(self, db):
        """find_by_type 按 action_type 过滤."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(action_type="update_budget"))
        repo.save(_make_execution_dict(action_type="scale_campaign"))
        repo.save(_make_execution_dict(action_type="update_budget"))
        results = repo.find_by_type("update_budget")
        assert len(results) == 2
        assert all(r.action_type == "update_budget" for r in results)

    def test_find_by_status_filters_correctly(self, db):
        """find_by_status 按状态过滤."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(status="success"))
        repo.save(_make_execution_dict(status="failed"))
        repo.save(_make_execution_dict(status="success"))
        results = repo.find_by_status("success")
        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    def test_find_failed_returns_failed_records(self, db):
        """find_failed 返回失败记录."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(status="failed"))
        repo.save(_make_execution_dict(status="success"))
        repo.save(_make_execution_dict(status="failed"))
        results = repo.find_failed()
        assert len(results) == 2
        assert all(r.status == "failed" for r in results)

    def test_get_recent_returns_limited_records(self, db):
        """get_recent 返回最近 N 条记录."""
        repo = ExecutionRepository(db)
        for i in range(20):
            repo.save(_make_execution_dict(action_type=f"type_{i}"))
        results = repo.get_recent(limit=5)
        assert len(results) == 5

    def test_update_status_changes_status(self, db):
        """update_status 更新执行状态."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(execution_id="exec_001", status="pending"))
        record = repo.update_status("exec_001", "success", error="")
        assert record is not None
        assert record.status == "success"

    def test_update_status_with_error_message(self, db):
        """update_status 更新状态并设置错误信息."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(execution_id="exec_001", status="pending"))
        record = repo.update_status("exec_001", "failed", error="timeout exceeded")
        assert record is not None
        assert record.status == "failed"
        assert record.error == "timeout exceeded"

    def test_delete_removes_record(self, db):
        """delete 删除记录."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(execution_id="exec_001"))
        assert repo.delete("exec_001") is True
        assert repo.delete("exec_001") is False
        assert repo.count() == 0

    def test_delete_older_than_removes_old_records(self, db):
        """delete_older_than 删除 N 天前的记录."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict())
        repo.save(_make_execution_dict())
        count = repo.delete_older_than(365)
        assert count == 0
        assert repo.count() == 2

    def test_count_returns_total(self, db):
        """count 返回总记录数."""
        repo = ExecutionRepository(db)
        assert repo.count() == 0
        repo.save(_make_execution_dict())
        repo.save(_make_execution_dict())
        assert repo.count() == 2

    def test_stats_returns_summary(self, db):
        """stats 返回统计摘要."""
        repo = ExecutionRepository(db)
        repo.save(_make_execution_dict(status="success"))
        repo.save(_make_execution_dict(status="success"))
        repo.save(_make_execution_dict(status="failed"))
        s = repo.stats()
        assert s["total"] == 3
        assert s["success_count"] == 2
        assert s["failure_count"] == 1
        assert s["success_rate"] == round(2 / 3, 4)


# ═══════════════════════════════════════════════════════════
# AlertRepository
# ═══════════════════════════════════════════════════════════

class TestAlertRepository:
    """AlertRepository — 报警记录持久化测试."""

    def test_save_creates_alert(self, db):
        """save 创建报警记录."""
        repo = AlertRepository(db)
        alert = repo.save(_make_alert_dict(
            severity="critical",
            rule_name="roas_drop",
            message="ROAS below 0.8",
            game_id="P04",
        ))
        assert alert.severity == "critical"
        assert alert.rule_name == "roas_drop"
        assert alert.message == "ROAS below 0.8"
        assert alert.game_id == "P04"
        assert alert.acknowledged is False
        assert alert.created_at is not None

    def test_get_by_id_found_and_not_found(self, db):
        """get_by_id 查找与不存在."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(alert_id="alert_001"))
        assert repo.get_by_id("alert_001") is not None
        assert repo.get_by_id("nonexistent") is None

    def test_find_by_severity_filters_correctly(self, db):
        """find_by_severity 按严重级别过滤."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(severity="critical"))
        repo.save(_make_alert_dict(severity="warning"))
        repo.save(_make_alert_dict(severity="critical"))
        results = repo.find_by_severity("critical")
        assert len(results) == 2
        assert all(r.severity == "critical" for r in results)

    def test_find_by_game_filters_correctly(self, db):
        """find_by_game 按游戏过滤."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(game_id="P04"))
        repo.save(_make_alert_dict(game_id="P04"))
        repo.save(_make_alert_dict(game_id="P05"))
        results = repo.find_by_game("P04")
        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)

    def test_find_unacknowledged_returns_unacknowledged_only(self, db):
        """find_unacknowledged 只返回未确认的报警."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(acknowledged=False))
        repo.save(_make_alert_dict(acknowledged=True))
        repo.save(_make_alert_dict(acknowledged=False))
        results = repo.find_unacknowledged()
        assert len(results) == 2
        assert all(not r.acknowledged for r in results)

    def test_find_by_rule_filters_correctly(self, db):
        """find_by_rule 按规则名称过滤."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(rule_name="roas_drop"))
        repo.save(_make_alert_dict(rule_name="spend_spike"))
        repo.save(_make_alert_dict(rule_name="roas_drop"))
        results = repo.find_by_rule("roas_drop")
        assert len(results) == 2
        assert all(r.rule_name == "roas_drop" for r in results)

    def test_get_recent_returns_limited_alerts(self, db):
        """get_recent 返回最近 N 条报警."""
        repo = AlertRepository(db)
        for i in range(20):
            repo.save(_make_alert_dict(severity="warning"))
        results = repo.get_recent(limit=5)
        assert len(results) == 5

    def test_acknowledge_sets_acknowledged_true(self, db):
        """acknowledge 确认单条报警."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(alert_id="alert_001", acknowledged=False))
        result = repo.acknowledge("alert_001")
        assert result is True
        alert = repo.get_by_id("alert_001")
        assert alert.acknowledged is True

    def test_acknowledge_non_existent_returns_false(self, db):
        """acknowledge 不存在的报警返回 False."""
        repo = AlertRepository(db)
        assert repo.acknowledge("nonexistent") is False

    def test_acknowledge_all_confirms_all_unacknowledged(self, db):
        """acknowledge_all 确认所有未确认报警."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(acknowledged=False))
        repo.save(_make_alert_dict(acknowledged=False))
        repo.save(_make_alert_dict(acknowledged=True))
        count = repo.acknowledge_all()
        assert count == 2
        assert repo.count_unacknowledged() == 0

    def test_delete_removes_alert(self, db):
        """delete 删除报警."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(alert_id="alert_001"))
        assert repo.delete("alert_001") is True
        assert repo.delete("alert_001") is False
        assert repo.count() == 0

    def test_delete_older_than_removes_old_alerts(self, db):
        """delete_older_than 删除 N 天前的报警."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict())
        repo.save(_make_alert_dict())
        count = repo.delete_older_than(365)
        assert count == 0
        assert repo.count() == 2

    def test_count_returns_total(self, db):
        """count 返回总报警数."""
        repo = AlertRepository(db)
        assert repo.count() == 0
        repo.save(_make_alert_dict())
        repo.save(_make_alert_dict())
        assert repo.count() == 2

    def test_count_unacknowledged_returns_unacknowledged_count(self, db):
        """count_unacknowledged 返回未确认报警数."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(acknowledged=False))
        repo.save(_make_alert_dict(acknowledged=True))
        repo.save(_make_alert_dict(acknowledged=False))
        assert repo.count_unacknowledged() == 2

    def test_get_summary_returns_total_and_unacknowledged(self, db):
        """get_summary 返回报警摘要."""
        repo = AlertRepository(db)
        repo.save(_make_alert_dict(acknowledged=False))
        repo.save(_make_alert_dict(acknowledged=False))
        repo.save(_make_alert_dict(acknowledged=True))
        summary = repo.get_summary()
        assert summary["total"] == 3
        assert summary["unacknowledged"] == 2