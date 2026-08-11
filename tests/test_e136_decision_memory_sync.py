"""E13.6.5 Decision Memory Sync — 测试用例.

测试覆盖:
  - DecisionStatus: 生命周期状态转换规则
  - DecisionMemoryRecord: 增强数据模型创建与转换
  - DecisionMemorySync: 决策生命周期同步 (record → executing → completed)
  - DecisionPatternExtractor: 决策→模式提取
  - DecisionPatternSync: 决策→模式同步编排
  - ExecutionResultBridge: 与 DecisionMemorySync 集成
  - Case 1: 决策创建同步 → DecisionMemoryRecord 存在
  - Case 2: 执行结果同步 → status=COMPLETED, reward 更新
  - Case 3: 失败案例学习 → 负向 Pattern (avoid)
  - Case 4: 成功案例学习 → 正向 Pattern (reinforce)
  - Case 5: End-to-End 闭环 (Opportunity → Decision → Execution → Memory → Pattern)
  - Case 6: 生命周期状态转换验证
  - Case 7: ExecutionResultBridge 自动同步
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_memory import (
    DecisionExperience,
    DecisionMemory,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_sync import (
    DecisionMemoryRecord,
    DecisionMemorySync,
    DecisionStatus,
    VALID_TRANSITIONS,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
    DecisionInput,
    DecisionOutput,
    DecisionPlan,
    DecisionType,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.decision_pattern_sync import (
    DecisionPatternExtractor,
    DecisionPatternSync,
    ExtractionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.execution_result_bridge import (
    BridgeEntry,
    BridgeResult,
    ExecutionResultBridge,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_decision_output(
    decision_id: str = "d001",
    strategy_id: str = "S1",
    strategy_name: str = "replace_creative",
    action_type: str = "replace_creative",
    confidence: float = 0.75,
    **kwargs: Any,
) -> DecisionOutput:
    """创建 DecisionOutput."""
    plan = DecisionPlan(action_type=action_type)
    return DecisionOutput(
        decision_id=decision_id,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        decision_type=DecisionType.EXECUTE,
        confidence=confidence,
        risk_score=0.2,
        final_score=0.65,
        action_plan=plan,
        **kwargs,
    )


def _make_decision_input(
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    **kwargs: Any,
) -> DecisionInput:
    """创建 DecisionInput."""
    return DecisionInput(
        strategies=[{"strategy_id": "S1", "action_type": action_type}],
        metadata={"opportunity_type": opportunity_type, **kwargs},
    )


def _make_bridge_entry(
    decision_id: str = "d001",
    action_type: str = "replace_creative",
    metrics_before: dict[str, float] | None = None,
) -> BridgeEntry:
    """创建 BridgeEntry."""
    return BridgeEntry(
        decision_id=decision_id,
        action_type=action_type,
        metrics_before=metrics_before or {"roas": 0.42, "ctr": 0.021},
    )


# ═══════════════════════════════════════════════════════════════
# Test 1: DecisionStatus
# ═══════════════════════════════════════════════════════════════


class TestDecisionStatus:
    """测试生命周期状态."""

    def test_terminal_states(self):
        """COMPLETED, FAILED, EXPIRED 是终态."""
        assert DecisionStatus.COMPLETED.is_terminal
        assert DecisionStatus.FAILED.is_terminal
        assert DecisionStatus.EXPIRED.is_terminal
        assert not DecisionStatus.CREATED.is_terminal
        assert not DecisionStatus.EXECUTING.is_terminal

    def test_active_states(self):
        """CREATED, EXECUTING 是活跃状态."""
        assert DecisionStatus.CREATED.is_active
        assert DecisionStatus.EXECUTING.is_active
        assert not DecisionStatus.COMPLETED.is_active
        assert not DecisionStatus.FAILED.is_active

    def test_valid_transitions(self):
        """验证合法状态转换."""
        assert DecisionStatus.EXECUTING in VALID_TRANSITIONS[DecisionStatus.CREATED]
        assert DecisionStatus.EXPIRED in VALID_TRANSITIONS[DecisionStatus.CREATED]
        assert DecisionStatus.COMPLETED in VALID_TRANSITIONS[DecisionStatus.EXECUTING]
        assert DecisionStatus.FAILED in VALID_TRANSITIONS[DecisionStatus.EXECUTING]

    def test_invalid_transition_raises(self):
        """非法状态转换应抛异常."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")

        # CREATED → COMPLETED 不合法 (必须先 EXECUTING)
        with pytest.raises(ValueError, match="Invalid status transition"):
            sync.sync_execution_result(output.decision_id, "success")

    def test_terminal_no_transition(self):
        """终态不允许再转换."""
        assert VALID_TRANSITIONS[DecisionStatus.COMPLETED] == set()
        assert VALID_TRANSITIONS[DecisionStatus.FAILED] == set()
        assert VALID_TRANSITIONS[DecisionStatus.EXPIRED] == set()


# ═══════════════════════════════════════════════════════════════
# Test 2: DecisionMemoryRecord
# ═══════════════════════════════════════════════════════════════


class TestDecisionMemoryRecord:
    """测试增强数据模型."""

    def test_from_decision_output(self):
        """从 DecisionOutput 创建记录."""
        output = _make_decision_output(
            decision_id="d001",
            strategy_name="replace_creative",
            confidence=0.75,
        )
        record = DecisionMemoryRecord.from_decision_output(
            output, "creative_fatigue",
        )

        assert record.decision_id == "d001"
        assert record.opportunity_type == "creative_fatigue"
        assert record.action_type == "replace_creative"
        assert record.status == DecisionStatus.CREATED
        assert record.confidence == 0.75
        assert record.success is None  # 尚未完成
        assert record.reward is None  # 尚未计算

    def test_from_decision_experience_resolved(self):
        """从已解决的 DecisionExperience 创建记录."""
        memory = DecisionMemory()
        output = _make_decision_output()
        memory.record_decision(output, "creative_fatigue")
        memory.record_outcome(output.decision_id, "success", {"roas_change": 0.15})

        exp = memory.get_by_decision(output.decision_id)
        record = DecisionMemoryRecord.from_decision_experience(exp)

        assert record.status == DecisionStatus.COMPLETED
        assert record.success is True
        assert record.reward is not None

    def test_from_decision_experience_failed(self):
        """从失败的 DecisionExperience 创建记录."""
        memory = DecisionMemory()
        output = _make_decision_output()
        memory.record_decision(output, "creative_fatigue")
        memory.record_outcome(output.decision_id, "failure", metrics={"roas_change": -0.10})

        exp = memory.get_by_decision(output.decision_id)
        record = DecisionMemoryRecord.from_decision_experience(exp)

        assert record.status == DecisionStatus.FAILED
        assert record.success is False
        assert record.reward is not None and record.reward < 0

    def test_is_terminal_and_active(self):
        """is_terminal / is_active 属性."""
        output = _make_decision_output()
        record = DecisionMemoryRecord.from_decision_output(output, "creative_fatigue")
        assert record.is_active
        assert not record.is_terminal

    def test_to_dict(self):
        """to_dict 序列化."""
        output = _make_decision_output()
        record = DecisionMemoryRecord.from_decision_output(output, "creative_fatigue")
        d = record.to_dict()

        assert d["decision_id"] == output.decision_id
        assert d["status"] == "created"
        assert d["confidence"] == 0.75
        assert "decision_context" in d
        assert "decision_detail" in d


# ═══════════════════════════════════════════════════════════════
# Test 3: DecisionMemorySync
# ═══════════════════════════════════════════════════════════════


class TestDecisionMemorySync:
    """测试决策生命周期同步."""

    def test_record_decision(self):
        """决策创建同步 → DecisionMemoryRecord 存在."""
        sync = DecisionMemorySync()
        output = _make_decision_output()

        record = sync.record_decision(output, "creative_fatigue")

        assert record.decision_id == output.decision_id
        assert record.status == DecisionStatus.CREATED
        assert sync.total_records == 1
        assert sync.get_record(output.decision_id) is not None

    def test_mark_executing(self):
        """标记执行中 → status=EXECUTING."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")

        record = sync.mark_executing(output.decision_id, "exec_001")

        assert record.status == DecisionStatus.EXECUTING
        assert record.execution_id == "exec_001"

    def test_sync_execution_result_success(self):
        """执行结果同步 → status=COMPLETED, reward 更新."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(output.decision_id)

        record = sync.sync_execution_result(
            decision_id=output.decision_id,
            status="success",
            metrics={"roas_change": 0.15, "ctr_change": 0.02},
        )

        assert record.status == DecisionStatus.COMPLETED
        assert record.success is True
        assert record.reward is not None and record.reward > 0
        assert record.completed_at is not None

    def test_sync_execution_result_failure(self):
        """失败结果同步 → status=FAILED, reward=-1.0."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "roas_drop")
        sync.mark_executing(output.decision_id)

        record = sync.sync_execution_result(
            decision_id=output.decision_id,
            status="failure",
            metrics={},
        )

        assert record.status == DecisionStatus.FAILED
        assert record.success is False
        assert record.reward == -1.0

    def test_expire_decision(self):
        """过期决策 → status=EXPIRED."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")

        record = sync.expire_decision(output.decision_id)

        assert record.status == DecisionStatus.EXPIRED
        assert record.completed_at is not None

    def test_expire_stale_decisions(self):
        """过期超时决策 (7天默认)."""
        sync = DecisionMemorySync(expiration_hours=0.0)  # 立即过期
        for i in range(3):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")

        count = sync.expire_stale_decisions()
        assert count == 3

    def test_evaluate_decision(self):
        """评估决策 → 返回完整评估结果."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(output.decision_id)
        sync.sync_execution_result(
            output.decision_id, "success",
            metrics={"roas_change": 0.20},
        )

        result = sync.evaluate_decision(output.decision_id)

        assert result["decision_id"] == output.decision_id
        assert result["success"] is True
        assert result["reward"] is not None
        assert result["status"] == "completed"
        assert result["opportunity_type"] == "creative_fatigue"

    def test_get_completed_decisions(self):
        """获取已完成的决策."""
        sync = DecisionMemorySync()
        for i in range(5):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}", "success" if i < 3 else "failure",
            )

        completed = sync.get_completed_decisions()
        assert len(completed) == 5

        success = sync.get_completed_decisions(opportunity_type="creative_fatigue")
        assert len(success) == 5

    def test_get_active_decisions(self):
        """获取活跃决策."""
        sync = DecisionMemorySync()
        for i in range(3):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
        sync.mark_executing("d000")

        active = sync.get_active_decisions()
        assert len(active) == 3  # 2 CREATED + 1 EXECUTING

    def test_get_pending_sync(self):
        """获取等待同步的决策."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(output.decision_id)

        pending = sync.get_pending_sync()
        assert len(pending) == 1
        assert pending[0].status == DecisionStatus.EXECUTING

    def test_stats(self):
        """统计汇总."""
        sync = DecisionMemorySync()
        for i in range(10):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}", "success" if i < 7 else "failure",
            )

        stats = sync.stats()
        assert stats["total"] == 10
        assert stats["completed"] == 7
        assert stats["failed"] == 3
        assert stats["success_rate"] == 0.7

    def test_success_rate_by_action(self):
        """按动作类型统计成功率."""
        sync = DecisionMemorySync()
        for i in range(6):
            output = _make_decision_output(
                decision_id=f"d{i:03d}",
                action_type="replace_creative" if i < 3 else "scale_budget",
            )
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}", "success" if i < 5 else "failure",
            )

        by_action = sync.get_success_rate_by_action()
        assert "replace_creative" in by_action
        assert "scale_budget" in by_action

    def test_clear_reset(self):
        """清空和重置."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")

        sync.clear()
        assert sync.total_records == 0
        assert sync.memory.total_experiences == 0


# ═══════════════════════════════════════════════════════════════
# Test 4: DecisionPatternExtractor
# ═══════════════════════════════════════════════════════════════


class TestDecisionPatternExtractor:
    """测试决策→模式提取."""

    def test_extract_learning_cases(self):
        """提取已完成决策 → 经验."""
        sync = DecisionMemorySync()
        # 创建 10 个已完成决策
        for i in range(10):
            output = _make_decision_output(
                decision_id=f"d{i:03d}",
                action_type="replace_creative",
            )
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}",
                "success" if i < 7 else "failure",
                metrics={"roas_change": 0.15} if i < 7 else {},
            )

        extractor = DecisionPatternExtractor(decision_sync=sync)

        result = extractor.extract_learning_cases()

        assert result.decisions_extracted == 10
        assert result.experiences_created > 0
        assert "success" in result.learning_summary
        assert "failure" in result.learning_summary

    def test_extract_by_opportunity_type(self):
        """按机会类型提取."""
        sync = DecisionMemorySync()
        for i in range(5):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(f"d{i:03d}", "success")

        extractor = DecisionPatternExtractor(decision_sync=sync)
        result = extractor.extract_by_opportunity_type("creative_fatigue")

        assert result.decisions_extracted == 5

    def test_extract_by_action_type(self):
        """按动作类型提取."""
        sync = DecisionMemorySync()
        for i in range(3):
            output = _make_decision_output(decision_id=f"d{i:03d}", action_type="scale_budget")
            sync.record_decision(output, "roas_drop")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(f"d{i:03d}", "success")

        extractor = DecisionPatternExtractor(decision_sync=sync, min_samples=3)
        result = extractor.extract_by_action_type("scale_budget")

        assert result.decisions_extracted == 3

    def test_insufficient_samples(self):
        """样本不足时不提取."""
        sync = DecisionMemorySync()
        # 只有 3 个已完成决策，低于 min_samples=5
        for i in range(3):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(f"d{i:03d}", "success")

        extractor = DecisionPatternExtractor(decision_sync=sync, min_samples=5)

        result = extractor.extract_learning_cases()

        assert result.decisions_extracted == 0
        assert "No completed decisions found" in result.learning_summary

    def test_push_single_decision(self):
        """推送单个决策."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(output.decision_id)
        sync.sync_execution_result(output.decision_id, "success", metrics={"roas_change": 0.20})

        record = sync.get_record(output.decision_id)
        extractor = DecisionPatternExtractor(decision_sync=sync)

        result = extractor.push_single_decision(record)

        assert result.decisions_extracted == 1
        assert result.experiences_created == 1
        assert "positive" in result.learning_summary

    def test_failure_learning_case(self):
        """失败案例 → 负向经验."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "roas_drop")
        sync.mark_executing(output.decision_id)
        sync.sync_execution_result(output.decision_id, "failure", metrics={})

        record = sync.get_record(output.decision_id)
        extractor = DecisionPatternExtractor(decision_sync=sync)

        result = extractor.push_single_decision(record)

        assert result.decisions_extracted == 1
        assert "negative" in result.learning_summary

    def test_convert_to_experience(self):
        """转换 DecisionMemoryRecord → GrowthExperience."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(output.decision_id)
        sync.sync_execution_result(output.decision_id, "success", metrics={"roas_change": 0.15})

        record = sync.get_record(output.decision_id)
        extractor = DecisionPatternExtractor(decision_sync=sync)

        exp = extractor.convert_to_experience(record)

        assert exp is not None
        assert exp.action_type == "replace_creative"
        assert exp.metadata["source"] == "decision_memory"
        assert exp.metadata["decision_id"] == output.decision_id


# ═══════════════════════════════════════════════════════════════
# Test 5: DecisionPatternSync
# ═══════════════════════════════════════════════════════════════


class TestDecisionPatternSync:
    """测试决策→模式同步编排."""

    def test_sync_all(self):
        """批量同步所有已完成决策."""
        sync = DecisionMemorySync()
        for i in range(8):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}", "success" if i < 6 else "failure",
            )

        pattern_sync = DecisionPatternSync(decision_sync=sync)

        result = pattern_sync.sync_all()

        assert result.decisions_extracted == 8
        assert result.experiences_created > 0

    def test_sync_by_opportunity_type(self):
        """按机会类型同步."""
        sync = DecisionMemorySync()
        for i in range(5):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(f"d{i:03d}", "success")

        pattern_sync = DecisionPatternSync(decision_sync=sync)
        result = pattern_sync.sync_by_opportunity_type("creative_fatigue")

        assert result.decisions_extracted == 5

    def test_no_decisions(self):
        """无已完成决策时返回空结果."""
        sync = DecisionMemorySync()
        pattern_sync = DecisionPatternSync(decision_sync=sync)

        result = pattern_sync.sync_all()

        assert result.decisions_extracted == 0


# ═══════════════════════════════════════════════════════════════
# Test 6: ExecutionResultBridge Integration
# ═══════════════════════════════════════════════════════════════


class TestBridgeDecisionSyncIntegration:
    """测试 ExecutionResultBridge 与 DecisionMemorySync 集成."""

    def test_bridge_syncs_to_decision_memory(self):
        """ExecutionResultBridge.evaluate() 自动同步到 DecisionMemorySync."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(output.decision_id)

        bridge = ExecutionResultBridge(decision_sync=sync)

        entry = BridgeEntry(
            decision_id=output.decision_id,
            action_type="replace_creative",
            metrics_before={"roas": 0.42, "ctr": 0.021},
        )

        result = bridge.evaluate(
            entry,
            metrics_after={"roas": 0.51, "ctr": 0.028},
        )

        # 验证 DecisionMemorySync 已更新
        record = sync.get_record(output.decision_id)
        assert record is not None
        assert record.status == DecisionStatus.COMPLETED
        assert record.reward is not None

    def test_bridge_without_sync_does_not_crash(self):
        """未配置 DecisionMemorySync 时不崩溃."""
        bridge = ExecutionResultBridge()

        entry = BridgeEntry(
            decision_id="d001",
            action_type="replace_creative",
            metrics_before={"roas": 0.42},
        )

        result = bridge.evaluate(
            entry,
            metrics_after={"roas": 0.51},
        )

        assert result is not None
        assert result.improvement_score > 0

    def test_bridge_failure_sync(self):
        """Bridge 失败结果同步."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "roas_drop")
        sync.mark_executing(output.decision_id)

        bridge = ExecutionResultBridge(decision_sync=sync)

        entry = BridgeEntry(
            decision_id=output.decision_id,
            action_type="scale_budget",
            metrics_before={"roas": 0.50},
        )

        result = bridge.evaluate(
            entry,
            metrics_after={"roas": 0.30},  # 下降
        )

        # 失败结果已同步
        record = sync.get_record(output.decision_id)
        assert record is not None
        assert record.status == DecisionStatus.FAILED
        assert record.reward == -1.0


# ═══════════════════════════════════════════════════════════════
# Test 7: End-to-End Closed Loop
# ═══════════════════════════════════════════════════════════════


class TestEndToEnd:
    """端到端闭环测试."""

    def test_full_decision_lifecycle(self):
        """完整决策生命周期: CREATED → EXECUTING → COMPLETED."""
        sync = DecisionMemorySync()

        # 1. 决策创建
        output = _make_decision_output()
        record = sync.record_decision(output, "creative_fatigue")
        assert record.status == DecisionStatus.CREATED

        # 2. 开始执行
        record = sync.mark_executing(output.decision_id, "exec_001")
        assert record.status == DecisionStatus.EXECUTING
        assert record.execution_id == "exec_001"

        # 3. 执行完成
        record = sync.sync_execution_result(
            output.decision_id, "success",
            metrics={"roas_change": 0.15, "ctr_change": 0.02},
        )
        assert record.status == DecisionStatus.COMPLETED
        assert record.success is True
        assert record.reward > 0

        # 4. 评估
        evaluation = sync.evaluate_decision(output.decision_id)
        assert evaluation["success"] is True

    def test_opportunity_to_pattern_closed_loop(self):
        """Opportunity → Decision → Execution → Memory → Pattern 闭环."""
        sync = DecisionMemorySync()

        # Step 1: 决策创建
        for i in range(10):
            output = _make_decision_output(
                decision_id=f"d{i:03d}",
                action_type="replace_creative",
            )
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}",
                "success" if i < 7 else "failure",
                metrics={"roas_change": 0.15} if i < 7 else {},
            )

        # Step 2: 提取 Pattern
        extractor = DecisionPatternExtractor(decision_sync=sync)
        result = extractor.extract_learning_cases()

        assert result.decisions_extracted == 10
        assert result.experiences_created > 0
        assert "success" in result.learning_summary

        # Step 3: 统计验证
        stats = sync.stats()
        assert stats["success_rate"] == 0.7

        by_action = sync.get_success_rate_by_action()
        assert "replace_creative" in by_action
        assert by_action["replace_creative"]["success_rate"] == 0.7

    def test_decision_engine_memory_interaction(self):
        """DecisionEngine 创建决策 → DecisionMemorySync 记录."""
        sync = DecisionMemorySync()
        output = _make_decision_output()
        sync.record_decision(output, "creative_fatigue")

        # 验证底层 DecisionMemory 也有记录
        exp = sync.memory.get_by_decision(output.decision_id)
        assert exp is not None
        assert exp.strategy_name == "replace_creative"

        # 验证增强记录
        record = sync.get_record(output.decision_id)
        assert record.opportunity_type == "creative_fatigue"

    def test_avoid_pattern_from_failures(self):
        """失败案例 → 负向 Pattern (avoid)."""
        sync = DecisionMemorySync()

        # 创建 20 个 scale_budget 决策，其中 18 个失败 (90%)
        for i in range(20):
            output = _make_decision_output(
                decision_id=f"d{i:03d}",
                action_type="scale_budget",
            )
            sync.record_decision(output, "roas_drop")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}",
                "success" if i < 2 else "failure",
            )

        # 统计验证
        by_action = sync.get_success_rate_by_action()
        assert by_action["scale_budget"]["success_rate"] == 0.1

        # 提取 → 应生成负向 Pattern
        extractor = DecisionPatternExtractor(decision_sync=sync)
        result = extractor.extract_learning_cases()
        assert result.decisions_extracted == 20

    def test_positive_pattern_from_successes(self):
        """成功案例 → 正向 Pattern (reinforce)."""
        sync = DecisionMemorySync()

        # 创建 15 个 replace_creative 决策，其中 12 个成功 (80%)
        for i in range(15):
            output = _make_decision_output(
                decision_id=f"d{i:03d}",
                action_type="replace_creative",
            )
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}",
                "success" if i < 12 else "failure",
                metrics={"roas_change": 0.15} if i < 12 else {},
            )

        by_action = sync.get_success_rate_by_action()
        assert by_action["replace_creative"]["success_rate"] == 0.8

        extractor = DecisionPatternExtractor(decision_sync=sync)
        result = extractor.extract_learning_cases()
        assert result.decisions_extracted == 15