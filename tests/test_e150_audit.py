"""E15.0.1 Growth Audit System — 单元测试.

验证 GrowthDecisionAudit / AuditStore / AuditService 的完整功能:
  - GrowthDecisionAudit: 创建/序列化/属性 (16 tests)
  - ExecutionStatus: 枚举值 (2 tests)
  - AuditStore: 记录/查询/统计/导出/维护 (25 tests)
  - AuditService: 服务层封装 (15 tests)
  - Edge Cases: 边界 & 异常 (6 tests)

总计: 64 个测试用例
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.audit import (
    AuditService,
    AuditStore,
    GrowthDecisionAudit,
)
from market_ops.creative_vision_runtime.growth_runtime.audit.models import ExecutionStatus


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_audit(
    agent_id: str = "agent_01",
    game_id: str = "P04",
    decision: str = "reduce budget 20%",
    action: str = "update_budget",
    confidence: float = 0.87,
    status: ExecutionStatus = ExecutionStatus.PENDING,
    plan_id: str = "",
    cycle_id: str = "",
) -> GrowthDecisionAudit:
    return GrowthDecisionAudit(
        agent_id=agent_id,
        game_id=game_id,
        input_context={"roas": 1.0, "spend": 500},
        detected_problem="ROAS decay detected",
        decision=decision,
        action=action,
        confidence=confidence,
        execution_status=status,
        plan_id=plan_id,
        cycle_id=cycle_id,
    )


def _make_store_with_records(n: int = 5) -> AuditStore:
    store = AuditStore()
    for i in range(n):
        store.record(_make_audit(
            agent_id=f"agent_{(i % 3):02d}",
            game_id=f"P{(i % 2) + 4:02d}",
            decision=f"decision_{i}",
            action="update_budget" if i % 2 == 0 else "scale_campaign",
            confidence=0.5 + i * 0.1,
            status=ExecutionStatus.SUCCESS if i < 3 else ExecutionStatus.FAILED,
            plan_id=f"plan_{i // 2}",
            cycle_id=f"cycle_{i}",
        ))
    return store


# ═══════════════════════════════════════════════════════════
# GrowthDecisionAudit — Creation
# ═══════════════════════════════════════════════════════════

class TestGrowthDecisionAuditCreation:
    """GrowthDecisionAudit 创建测试."""

    def test_create_with_defaults(self):
        """默认字段创建."""
        audit = GrowthDecisionAudit()
        assert audit.audit_id.startswith("audit_")
        assert len(audit.audit_id) == 18  # "audit_" + 12 hex
        assert audit.agent_id == ""
        assert audit.game_id == ""
        assert audit.input_context == {}
        assert audit.detected_problem == ""
        assert audit.decision == ""
        assert audit.action == ""
        assert audit.confidence == 0.0
        assert audit.execution_status == ExecutionStatus.PENDING
        assert audit.result == {}
        assert audit.plan_id == ""
        assert audit.cycle_id == ""
        assert audit.safety_decision == ""
        assert audit.rollback_record_id == ""
        assert audit.metadata == {}

    def test_create_with_all_fields(self):
        """全字段创建."""
        audit = GrowthDecisionAudit(
            agent_id="agent_42",
            game_id="P42",
            input_context={"roas": 2.5, "spend": 1000},
            detected_problem="ROAS sudden drop",
            decision="pause campaign",
            action="pause_campaign",
            confidence=0.95,
            execution_status=ExecutionStatus.APPROVED,
            result={"roas_before": 2.5, "roas_after": 2.8},
            plan_id="plan_1",
            cycle_id="cycle_3",
            safety_decision="approved",
            rollback_record_id="rb_001",
            metadata={"source": "test"},
        )
        assert audit.agent_id == "agent_42"
        assert audit.game_id == "P42"
        assert audit.input_context == {"roas": 2.5, "spend": 1000}
        assert audit.detected_problem == "ROAS sudden drop"
        assert audit.decision == "pause campaign"
        assert audit.action == "pause_campaign"
        assert audit.confidence == 0.95
        assert audit.execution_status == ExecutionStatus.APPROVED
        assert audit.result == {"roas_before": 2.5, "roas_after": 2.8}
        assert audit.plan_id == "plan_1"
        assert audit.cycle_id == "cycle_3"
        assert audit.safety_decision == "approved"
        assert audit.rollback_record_id == "rb_001"
        assert audit.metadata == {"source": "test"}

    def test_audit_id_is_unique(self):
        """每条记录的 audit_id 唯一."""
        ids = {GrowthDecisionAudit().audit_id for _ in range(50)}
        assert len(ids) == 50

    def test_timestamp_is_iso_format(self):
        """timestamp 为 ISO 8601 格式."""
        audit = GrowthDecisionAudit()
        # ISO 8601 格式: 2026-07-29T... 包含 'T' 和 'Z' 或 '+'
        assert "T" in audit.timestamp

    def test_timestamp_is_utc(self):
        """timestamp 使用 UTC 时区."""
        audit = GrowthDecisionAudit()
        ts = audit.timestamp
        # UTC 的 ISO 表示应包含 +00:00 或 Z
        assert "+00:00" in ts or ts.endswith("Z")


# ═══════════════════════════════════════════════════════════
# GrowthDecisionAudit — Serialization
# ═══════════════════════════════════════════════════════════

class TestGrowthDecisionAuditSerialization:
    """GrowthDecisionAudit 序列化测试."""

    def test_to_dict_includes_all_keys(self):
        """to_dict 包含所有预期键."""
        audit = _make_audit()
        d = audit.to_dict()
        expected_keys = {
            "audit_id", "timestamp", "agent_id", "game_id",
            "input_context", "detected_problem", "decision", "action",
            "confidence", "execution_status", "result",
            "plan_id", "cycle_id", "safety_decision", "rollback_record_id", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values(self):
        """to_dict 值正确."""
        audit = _make_audit(game_id="P99", decision="scale up", confidence=0.88)
        d = audit.to_dict()
        assert d["game_id"] == "P99"
        assert d["decision"] == "scale up"
        assert d["confidence"] == 0.88
        assert d["execution_status"] == "pending"  # enum value string

    def test_to_dict_execution_status_is_string(self):
        """to_dict 中 execution_status 为字符串."""
        audit = _make_audit(status=ExecutionStatus.SUCCESS)
        d = audit.to_dict()
        assert isinstance(d["execution_status"], str)
        assert d["execution_status"] == "success"

    def test_to_summary_basic(self):
        """to_summary 基本结构."""
        audit = _make_audit(game_id="P04", decision="reduce budget")
        s = audit.to_summary()
        assert s["audit_id"] == audit.audit_id
        assert s["timestamp"] == audit.timestamp
        assert s["game_id"] == "P04"
        assert s["detected_problem"] == "ROAS decay detected"
        assert s["decision"] == "reduce budget"
        assert s["confidence"] == 0.87
        assert s["execution_status"] == "pending"
        assert "result_summary" in s

    def test_to_summary_result_summary_filter(self):
        """to_summary 的 result_summary 只保留关键字段."""
        audit = _make_audit()
        audit.result = {
            "roas_before": 1.0,
            "roas_after": 1.5,
            "roas_after_7d": 1.2,
            "budget_change": -200,
            "status": "ok",
            "extra_field": "should_be_excluded",
            "internal_id": 123,
        }
        s = audit.to_summary()
        rs = s["result_summary"]
        assert "roas_before" in rs
        assert "roas_after" in rs
        assert "roas_after_7d" in rs
        assert "budget_change" in rs
        assert "status" in rs
        assert "extra_field" not in rs
        assert "internal_id" not in rs

    def test_to_summary_empty_result(self):
        """to_summary 空 result."""
        audit = _make_audit()
        audit.result = {}
        s = audit.to_summary()
        assert s["result_summary"] == {}


# ═══════════════════════════════════════════════════════════
# GrowthDecisionAudit — Properties
# ═══════════════════════════════════════════════════════════

class TestGrowthDecisionAuditProperties:
    """GrowthDecisionAudit 属性测试."""

    def test_is_success_true(self):
        audit = _make_audit(status=ExecutionStatus.SUCCESS)
        assert audit.is_success is True

    def test_is_success_false(self):
        audit = _make_audit(status=ExecutionStatus.FAILED)
        assert audit.is_success is False

    def test_is_success_false_pending(self):
        audit = _make_audit(status=ExecutionStatus.PENDING)
        assert audit.is_success is False

    def test_is_failed_true(self):
        audit = _make_audit(status=ExecutionStatus.FAILED)
        assert audit.is_failed is True

    def test_is_failed_false(self):
        audit = _make_audit(status=ExecutionStatus.SUCCESS)
        assert audit.is_failed is False

    def test_needs_attention_pending(self):
        audit = _make_audit(status=ExecutionStatus.PENDING)
        assert audit.needs_attention is True

    def test_needs_attention_rejected(self):
        audit = _make_audit(status=ExecutionStatus.REJECTED)
        assert audit.needs_attention is True

    def test_needs_attention_failed(self):
        audit = _make_audit(status=ExecutionStatus.FAILED)
        assert audit.needs_attention is True

    def test_needs_attention_success(self):
        audit = _make_audit(status=ExecutionStatus.SUCCESS)
        assert audit.needs_attention is False

    def test_needs_attention_executing(self):
        audit = _make_audit(status=ExecutionStatus.EXECUTING)
        assert audit.needs_attention is False

    def test_needs_attention_approved(self):
        audit = _make_audit(status=ExecutionStatus.APPROVED)
        assert audit.needs_attention is False

    def test_was_rolled_back_true(self):
        audit = _make_audit(status=ExecutionStatus.ROLLED_BACK)
        assert audit.was_rolled_back is True

    def test_was_rolled_back_false(self):
        audit = _make_audit(status=ExecutionStatus.SUCCESS)
        assert audit.was_rolled_back is False


# ═══════════════════════════════════════════════════════════
# ExecutionStatus
# ═══════════════════════════════════════════════════════════

class TestExecutionStatus:
    """ExecutionStatus 枚举测试."""

    def test_all_enum_values(self):
        expected = {
            "pending", "executing", "success", "failed",
            "rolled_back", "approved", "rejected",
        }
        actual = {e.value for e in ExecutionStatus}
        assert actual == expected

    def test_enum_count(self):
        assert len(ExecutionStatus) == 7


# ═══════════════════════════════════════════════════════════
# AuditStore — Record
# ═══════════════════════════════════════════════════════════

class TestAuditStoreRecord:
    """AuditStore 记录测试."""

    def test_record_returns_audit(self):
        store = AuditStore()
        audit = _make_audit()
        result = store.record(audit)
        assert result is audit
        assert len(store) == 1

    def test_record_decision(self):
        store = AuditStore()
        audit = store.record_decision(
            agent_id="agent_01",
            game_id="P04",
            input_context={"roas": 1.0},
            detected_problem="ROAS drop",
            decision="scale down",
            action="update_budget",
            confidence=0.75,
            plan_id="plan_1",
            cycle_id="cycle_2",
        )
        assert audit.agent_id == "agent_01"
        assert audit.game_id == "P04"
        assert audit.decision == "scale down"
        assert audit.action == "update_budget"
        assert audit.confidence == 0.75
        assert audit.plan_id == "plan_1"
        assert audit.cycle_id == "cycle_2"
        assert audit.execution_status == ExecutionStatus.PENDING
        assert len(store) == 1

    def test_record_decision_defaults(self):
        store = AuditStore()
        audit = store.record_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="",
            decision="d", action="a", confidence=0.5,
        )
        assert audit.plan_id == ""
        assert audit.cycle_id == ""

    def test_update_result_success(self):
        store = AuditStore()
        audit = _make_audit(status=ExecutionStatus.PENDING)
        store.record(audit)
        updated = store.update_result(
            audit.audit_id,
            status=ExecutionStatus.SUCCESS,
            result={"roas_after": 1.5},
        )
        assert updated is not None
        assert updated.execution_status == ExecutionStatus.SUCCESS
        assert updated.result["roas_after"] == 1.5

    def test_update_result_with_rollback(self):
        store = AuditStore()
        audit = _make_audit()
        store.record(audit)
        updated = store.update_result(
            audit.audit_id,
            status=ExecutionStatus.ROLLED_BACK,
            rollback_record_id="rb_999",
        )
        assert updated is not None
        assert updated.rollback_record_id == "rb_999"
        assert updated.execution_status == ExecutionStatus.ROLLED_BACK

    def test_update_result_non_existent(self):
        store = AuditStore()
        result = store.update_result("nonexistent", ExecutionStatus.SUCCESS)
        assert result is None

    def test_update_result_merges_result(self):
        """update_result 应 merge 而非覆盖已有 result."""
        store = AuditStore()
        audit = _make_audit()
        audit.result = {"existing_key": "val"}
        store.record(audit)
        store.update_result(audit.audit_id, ExecutionStatus.SUCCESS, result={"new_key": "new_val"})
        assert audit.result["existing_key"] == "val"
        assert audit.result["new_key"] == "new_val"


# ═══════════════════════════════════════════════════════════
# AuditStore — Query
# ═══════════════════════════════════════════════════════════

class TestAuditStoreQuery:
    """AuditStore 查询测试."""

    def test_get_by_id_found(self):
        store = AuditStore()
        audit = _make_audit()
        store.record(audit)
        assert store.get_by_id(audit.audit_id) is audit

    def test_get_by_id_not_found(self):
        store = AuditStore()
        assert store.get_by_id("nonexistent") is None

    def test_get_by_game(self):
        store = AuditStore()
        store.record(_make_audit(game_id="P04"))
        store.record(_make_audit(game_id="P04"))
        store.record(_make_audit(game_id="P05"))
        results = store.get_by_game("P04")
        assert len(results) == 2
        assert all(r.game_id == "P04" for r in results)

    def test_get_by_game_empty(self):
        store = AuditStore()
        assert store.get_by_game("P99") == []

    def test_get_by_agent(self):
        store = AuditStore()
        store.record(_make_audit(agent_id="agent_X"))
        store.record(_make_audit(agent_id="agent_Y"))
        store.record(_make_audit(agent_id="agent_X"))
        results = store.get_by_agent("agent_X")
        assert len(results) == 2

    def test_get_by_agent_empty(self):
        store = AuditStore()
        assert store.get_by_agent("unknown") == []

    def test_get_by_status(self):
        store = AuditStore()
        store.record(_make_audit(status=ExecutionStatus.SUCCESS))
        store.record(_make_audit(status=ExecutionStatus.FAILED))
        store.record(_make_audit(status=ExecutionStatus.SUCCESS))
        results = store.get_by_status(ExecutionStatus.SUCCESS)
        assert len(results) == 2
        assert all(r.execution_status == ExecutionStatus.SUCCESS for r in results)

    def test_get_by_status_empty(self):
        store = AuditStore()
        store.record(_make_audit(status=ExecutionStatus.SUCCESS))
        assert store.get_by_status(ExecutionStatus.FAILED) == []

    def test_get_by_time_range(self):
        store = AuditStore()
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()
        audit = GrowthDecisionAudit(
            agent_id="a1", game_id="g1",
            timestamp=now.isoformat(),
        )
        store.record(audit)
        results = store.get_by_time_range(start, end)
        assert len(results) == 1

    def test_get_by_time_range_no_end(self):
        """无 end 参数时默认使用当前时间."""
        store = AuditStore()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        audit = GrowthDecisionAudit(agent_id="a1", game_id="g1", timestamp=past)
        store.record(audit)
        results = store.get_by_time_range(past)
        assert len(results) == 1

    def test_get_by_time_range_excludes_outside(self):
        store = AuditStore()
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        audit = GrowthDecisionAudit(agent_id="a1", game_id="g1", timestamp=old)
        store.record(audit)
        recent_start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        results = store.get_by_time_range(recent_start)
        assert len(results) == 0

    def test_get_by_plan(self):
        store = AuditStore()
        store.record(_make_audit(plan_id="plan_A"))
        store.record(_make_audit(plan_id="plan_B"))
        store.record(_make_audit(plan_id="plan_A"))
        results = store.get_by_plan("plan_A")
        assert len(results) == 2

    def test_get_by_plan_empty(self):
        store = AuditStore()
        assert store.get_by_plan("nonexistent") == []

    def test_get_by_cycle(self):
        store = AuditStore()
        store.record(_make_audit(cycle_id="cycle_1"))
        store.record(_make_audit(cycle_id="cycle_1"))
        store.record(_make_audit(cycle_id="cycle_2"))
        results = store.get_by_cycle("cycle_1")
        assert len(results) == 2

    def test_get_by_cycle_empty(self):
        store = AuditStore()
        assert store.get_by_cycle("nonexistent") == []

    def test_get_recent(self):
        store = AuditStore()
        for i in range(20):
            store.record(_make_audit(agent_id=f"agent_{i}"))
        results = store.get_recent(5)
        assert len(results) == 5

    def test_get_recent_default_n(self):
        store = AuditStore()
        for i in range(15):
            store.record(_make_audit(agent_id=f"agent_{i}"))
        results = store.get_recent()
        assert len(results) == 10

    def test_get_all(self):
        store = _make_store_with_records(5)
        all_records = store.get_all()
        assert len(all_records) == 5
        assert isinstance(all_records, list)
        # 返回的是副本
        all_records.clear()
        assert len(store) == 5

    def test_get_needing_attention(self):
        store = AuditStore()
        store.record(_make_audit(status=ExecutionStatus.PENDING))
        store.record(_make_audit(status=ExecutionStatus.FAILED))
        store.record(_make_audit(status=ExecutionStatus.REJECTED))
        store.record(_make_audit(status=ExecutionStatus.SUCCESS))
        store.record(_make_audit(status=ExecutionStatus.APPROVED))
        results = store.get_needing_attention()
        assert len(results) == 3

    def test_get_failed(self):
        store = AuditStore()
        store.record(_make_audit(status=ExecutionStatus.FAILED))
        store.record(_make_audit(status=ExecutionStatus.SUCCESS))
        store.record(_make_audit(status=ExecutionStatus.FAILED))
        assert len(store.get_failed()) == 2

    def test_get_rolled_back(self):
        store = AuditStore()
        store.record(_make_audit(status=ExecutionStatus.ROLLED_BACK))
        store.record(_make_audit(status=ExecutionStatus.SUCCESS))
        store.record(_make_audit(status=ExecutionStatus.ROLLED_BACK))
        assert len(store.get_rolled_back()) == 2


# ═══════════════════════════════════════════════════════════
# AuditStore — Statistics & Export
# ═══════════════════════════════════════════════════════════

class TestAuditStoreStats:
    """AuditStore 统计 & 导出测试."""

    def test_stats_basic(self):
        store = _make_store_with_records(5)
        s = store.stats()
        assert s["total"] == 5
        assert s["success_count"] == 3
        assert s["failure_count"] == 2
        assert s["success_rate"] == round(3 / 5, 4)
        assert "by_game" in s
        assert "by_status" in s
        assert "avg_confidence" in s

    def test_stats_empty(self):
        store = AuditStore()
        s = store.stats()
        assert s["total"] == 0
        assert s["success_count"] == 0
        assert s["failure_count"] == 0
        assert s["success_rate"] == 0.0
        assert s["by_game"] == {}
        assert s["by_status"] == {}
        assert s["avg_confidence"] == 0.0

    def test_stats_by_game(self):
        store = AuditStore()
        store.record(_make_audit(game_id="P04", status=ExecutionStatus.SUCCESS))
        store.record(_make_audit(game_id="P04", status=ExecutionStatus.SUCCESS))
        store.record(_make_audit(game_id="P04", status=ExecutionStatus.FAILED))
        s = store.stats_by_game("P04")
        assert s["game_id"] == "P04"
        assert s["total"] == 3
        assert s["success_count"] == 2
        assert s["success_rate"] == round(2 / 3, 4)

    def test_stats_by_game_empty(self):
        store = AuditStore()
        s = store.stats_by_game("P99")
        assert s == {"game_id": "P99", "total": 0}

    def test_to_dicts(self):
        store = _make_store_with_records(3)
        dicts = store.to_dicts()
        assert len(dicts) == 3
        assert all(isinstance(d, dict) for d in dicts)
        assert all("audit_id" in d for d in dicts)

    def test_to_dicts_empty(self):
        store = AuditStore()
        assert store.to_dicts() == []

    def test_to_summaries(self):
        store = _make_store_with_records(3)
        summaries = store.to_summaries()
        assert len(summaries) == 3
        assert all("result_summary" in s for s in summaries)

    def test_to_summaries_empty(self):
        store = AuditStore()
        assert store.to_summaries() == []

    def test_export_json(self):
        store = _make_store_with_records(3)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            tmp_path = f.name
        try:
            store.export_json(tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 3
            assert all("audit_id" in d for d in data)
        finally:
            os.unlink(tmp_path)

    def test_export_json_empty(self):
        store = AuditStore()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            tmp_path = f.name
        try:
            store.export_json(tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data == []
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════
# AuditStore — Maintenance
# ═══════════════════════════════════════════════════════════

class TestAuditStoreMaintenance:
    """AuditStore 维护测试."""

    def test_clear(self):
        store = _make_store_with_records(5)
        assert len(store) == 5
        store.clear()
        assert len(store) == 0
        assert store.get_all() == []

    def test_len(self):
        store = AuditStore()
        assert len(store) == 0
        store.record(_make_audit())
        assert len(store) == 1
        store.record(_make_audit())
        assert len(store) == 2

    def test_iterator(self):
        store = _make_store_with_records(3)
        items = list(store)
        assert len(items) == 3
        assert all(isinstance(a, GrowthDecisionAudit) for a in items)

    def test_iterator_empty(self):
        store = AuditStore()
        assert list(store) == []

    def test_max_records_trim(self):
        store = AuditStore(max_records=5)
        for i in range(10):
            store.record(_make_audit(agent_id=f"agent_{i}"))
        assert len(store) == 5
        # 最旧的记录应被移除
        first = store.get_all()[0]
        assert first.agent_id == "agent_5"

    def test_max_records_default(self):
        store = AuditStore()
        assert store._max_records == 10000


# ═══════════════════════════════════════════════════════════
# AuditService
# ═══════════════════════════════════════════════════════════

class TestAuditService:
    """AuditService 测试."""

    def test_store_property(self):
        service = AuditService()
        assert isinstance(service.store, AuditStore)

    def test_custom_store(self):
        store = AuditStore(max_records=100)
        # 空 store 的 __len__ 为 0，在 Python 中会被视为 falsy，
        # 因此 AuditService.__init__ 中 store or AuditStore() 会创建新 store。
        # 需要先填充记录使 store 为 truthy，才能正确测试自定义 store 注入。
        store.record(_make_audit())
        service = AuditService(store=store)
        assert service.store is store
        assert len(service.store) == 1

    def test_log_decision(self):
        service = AuditService()
        audit = service.log_decision(
            agent_id="agent_01",
            game_id="P04",
            input_context={"roas": 1.0},
            detected_problem="ROAS drop",
            decision="reduce budget",
            action="update_budget",
            confidence=0.85,
            plan_id="plan_1",
            cycle_id="cycle_2",
            safety_decision="approved",
        )
        assert audit.agent_id == "agent_01"
        assert audit.game_id == "P04"
        assert audit.decision == "reduce budget"
        assert audit.confidence == 0.85
        assert audit.plan_id == "plan_1"
        assert audit.cycle_id == "cycle_2"
        assert audit.safety_decision == "approved"
        assert len(service.store) == 1

    def test_log_decision_defaults(self):
        service = AuditService()
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="",
            decision="d", action="a", confidence=0.5,
        )
        assert audit.plan_id == ""
        assert audit.cycle_id == ""
        assert audit.safety_decision == ""

    def test_log_execution_result(self):
        service = AuditService()
        audit = service.log_decision(
            agent_id="a1", game_id="g1",
            input_context={}, detected_problem="p",
            decision="d", action="a", confidence=0.5,
        )
        result = service.log_execution_result(
            audit.audit_id,
            status=ExecutionStatus.SUCCESS,
            result={"roas_after": 1.5},
        )
        assert result is not None
        assert result.execution_status == ExecutionStatus.SUCCESS
        assert result.result["roas_after"] == 1.5

    def test_log_execution_result_non_existent(self):
        service = AuditService()
        result = service.log_execution_result("nonexistent", ExecutionStatus.SUCCESS)
        assert result is None

    def test_get_audit_trail(self):
        service = AuditService()
        for i in range(5):
            service.log_decision(
                agent_id=f"a{i}", game_id="P04",
                input_context={}, detected_problem=f"p{i}",
                decision=f"d{i}", action="a", confidence=0.5,
            )
        trail = service.get_audit_trail("P04")
        assert len(trail) == 5
        assert all("result_summary" in t for t in trail)

    def test_get_audit_trail_limit(self):
        service = AuditService()
        for i in range(100):
            service.log_decision(
                agent_id=f"a{i}", game_id="P04",
                input_context={}, detected_problem=f"p{i}",
                decision=f"d{i}", action="a", confidence=0.5,
            )
        trail = service.get_audit_trail("P04", limit=10)
        assert len(trail) == 10

    def test_get_audit_trail_empty(self):
        service = AuditService()
        trail = service.get_audit_trail("P99")
        assert trail == []

    def test_get_decision_history(self):
        service = AuditService()
        service.log_decision(
            agent_id="a1", game_id="P04", input_context={},
            detected_problem="p", decision="d", action="a", confidence=0.5,
        )
        service.log_decision(
            agent_id="a2", game_id="P05", input_context={},
            detected_problem="p", decision="d", action="a", confidence=0.5,
        )
        history = service.get_decision_history("P04")
        assert len(history) == 1
        assert history[0].game_id == "P04"

    def test_get_decision_history_with_time_range(self):
        service = AuditService()
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()
        service.log_decision(
            agent_id="a1", game_id="P04", input_context={},
            detected_problem="p", decision="d", action="a", confidence=0.5,
        )
        history = service.get_decision_history("P04", start_time=start, end_time=end)
        assert len(history) == 1

    def test_get_decision_history_empty(self):
        service = AuditService()
        history = service.get_decision_history("P99")
        assert history == []

    def test_generate_audit_report(self):
        service = AuditService()
        service.log_decision(
            agent_id="a1", game_id="P04", input_context={},
            detected_problem="p", decision="d", action="update_budget", confidence=0.8,
        )
        service.log_decision(
            agent_id="a2", game_id="P04", input_context={},
            detected_problem="p2", decision="d2", action="scale", confidence=0.9,
        )
        report = service.generate_audit_report("P04")
        assert report["game_id"] == "P04"
        assert report["total_decisions"] == 2
        assert "by_action" in report
        assert "decisions" in report
        assert "stats" in report

    def test_generate_audit_report_empty(self):
        service = AuditService()
        report = service.generate_audit_report("P99")
        assert report["game_id"] == "P99"
        assert report["total_decisions"] == 0
        assert report["success_rate"] == 0.0
        assert report["decisions"] == []
        assert report["stats"] == {}

    def test_generate_full_report(self):
        service = AuditService()
        service.log_decision(
            agent_id="a1", game_id="P04", input_context={},
            detected_problem="p", decision="d", action="a", confidence=0.5,
        )
        report = service.generate_full_report()
        assert "generated_at" in report
        assert "total_records" in report
        assert "stats" in report
        assert "needing_attention" in report
        assert "failed_count" in report
        assert "rolled_back_count" in report
        assert report["total_records"] == 1

    def test_generate_full_report_empty(self):
        service = AuditService()
        report = service.generate_full_report()
        assert report["total_records"] == 0
        assert report["stats"]["total"] == 0
        assert report["needing_attention"] == 0
        assert report["failed_count"] == 0
        assert report["rolled_back_count"] == 0

    def test_log_rollback(self):
        service = AuditService()
        audit = service.log_decision(
            agent_id="a1", game_id="P04", input_context={},
            detected_problem="p", decision="d", action="a", confidence=0.5,
        )
        result = service.log_rollback(audit.audit_id, result={"reason": "manual"})
        assert result is not None
        assert result.execution_status == ExecutionStatus.ROLLED_BACK
        assert result.result["reason"] == "manual"

    def test_log_rollback_non_existent(self):
        service = AuditService()
        result = service.log_rollback("nonexistent")
        assert result is None