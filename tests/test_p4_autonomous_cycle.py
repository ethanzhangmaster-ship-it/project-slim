"""P4.2 AutonomousCycle 单元测试 — 可恢复的 11 阶段认知循环.

测试覆盖:
  1. CycleStage 枚举与 ORDER 顺序
  2. CycleState 序列化/反序列化
  3. CycleStore append-only 持久化 + 最新 revision 胜出
  4. AutonomousCycle 完整循环执行
  5. 可恢复性 (crash/restart)
  6. production 模式 approval 门禁
  7. handler 异常处理
  8. 边界场景: handler 缺失、空 handlers
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.autonomous_growth.cycle import (
    ORDER,
    AutonomousCycle,
    CycleStage,
    CycleState,
    CycleStore,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def store(tmp_path: Path) -> CycleStore:
    """临时 CycleStore."""
    return CycleStore(str(tmp_path / "cycle_state.jsonl"))


@pytest.fixture
def all_stage_handlers() -> dict:
    """覆盖所有阶段的 handlers (除 COMPLETE)."""
    handlers = {}
    for stage in ORDER[:-1]:  # 不包含 COMPLETE
        handlers[stage.value] = lambda **kw: {"stage": kw["state"].stage.value}
    return handlers


# ═══════════════════════════════════════════════════════════════
# 1. CycleStage 枚举与 ORDER
# ═══════════════════════════════════════════════════════════════


class TestCycleStage:
    """CycleStage 枚举."""

    def test_all_stages_present(self):
        """11 个阶段全部存在."""
        assert len(CycleStage) == 11

    def test_stage_values(self):
        """阶段值正确."""
        assert CycleStage.OBSERVE.value == "observe"
        assert CycleStage.UNDERSTAND.value == "understand"
        assert CycleStage.REMEMBER.value == "remember"
        assert CycleStage.DECIDE.value == "decide"
        assert CycleStage.SIMULATE.value == "simulate"
        assert CycleStage.APPROVE.value == "approve"
        assert CycleStage.EXECUTE.value == "execute"
        assert CycleStage.MEASURE.value == "measure"
        assert CycleStage.LEARN.value == "learn"
        assert CycleStage.IMPROVE.value == "improve"
        assert CycleStage.COMPLETE.value == "complete"

    def test_order_starts_with_observe(self):
        """ORDER 首个阶段是 OBSERVE."""
        assert ORDER[0] == CycleStage.OBSERVE

    def test_order_ends_with_complete(self):
        """ORDER 末尾阶段是 COMPLETE."""
        assert ORDER[-1] == CycleStage.COMPLETE

    def test_order_has_11_stages(self):
        """ORDER 包含 11 个阶段."""
        assert len(ORDER) == 11


# ═══════════════════════════════════════════════════════════════
# 2. CycleState 序列化
# ═══════════════════════════════════════════════════════════════


class TestCycleState:
    """CycleState dataclass."""

    def test_default_values(self):
        """默认值."""
        state = CycleState("cycle-1", "2026-08-10")
        assert state.stage == CycleStage.OBSERVE
        assert state.completed_stages == []
        assert state.artifacts == {}
        assert state.blocked_reason == ""
        assert state.failed_stage == ""
        assert state.revision == 0

    def test_to_dict_round_trip(self):
        """to_dict / from_dict 往返一致."""
        original = CycleState(
            cycle_id="c1", business_date="2026-08-10",
            stage=CycleStage.DECIDE, completed_stages=["observe", "understand"],
            artifacts={"observe": {"data": 1}},
            blocked_reason="", failed_stage="",
            revision=3,
        )
        data = original.to_dict()
        restored = CycleState.from_dict(data)
        assert restored.cycle_id == "c1"
        assert restored.business_date == "2026-08-10"
        assert restored.stage == CycleStage.DECIDE
        assert restored.completed_stages == ["observe", "understand"]
        assert restored.artifacts == {"observe": {"data": 1}}
        assert restored.revision == 3

    def test_from_dict_with_missing_fields(self):
        """from_dict 容忍缺失字段."""
        restored = CycleState.from_dict({"cycle_id": "c1", "business_date": "2026-08-10"})
        assert restored.stage == CycleStage.OBSERVE
        assert restored.completed_stages == []
        assert restored.artifacts == {}
        assert restored.revision == 0


# ═══════════════════════════════════════════════════════════════
# 3. CycleStore 持久化
# ═══════════════════════════════════════════════════════════════


class TestCycleStore:
    """CycleStore append-only 状态日志."""

    def test_save_creates_file(self, store: CycleStore, tmp_path: Path):
        """save 创建文件."""
        state = CycleState("c1", "2026-08-10")
        store.save(state)
        assert (tmp_path / "cycle_state.jsonl").exists()

    def test_load_returns_none_when_not_found(self, store: CycleStore):
        """load 不存在的 cycle_id 返回 None."""
        assert store.load("nonexistent") is None

    def test_load_returns_latest_revision(self, store: CycleStore):
        """load 返回最新 revision."""
        state = CycleState("c1", "2026-08-10", revision=1)
        store.save(state)
        state.revision = 5
        store.save(state)
        state.revision = 3
        store.save(state)
        loaded = store.load("c1")
        assert loaded is not None
        assert loaded.revision == 5

    def test_load_ignores_invalid_lines(self, store: CycleStore, tmp_path: Path):
        """load 容忍无效 JSON 行."""
        path = tmp_path / "cycle_state.jsonl"
        with path.open("w", encoding="utf-8") as f:
            f.write("invalid json\n")
            f.write(json.dumps({"cycle_id": "c1", "business_date": "2026-08-10",
                                "stage": "observe", "revision": 1}) + "\n")
        loaded = store.load("c1")
        assert loaded is not None
        assert loaded.revision == 1

    def test_save_appends_only(self, store: CycleStore, tmp_path: Path):
        """save 是 append-only."""
        state = CycleState("c1", "2026-08-10")
        for i in range(5):
            state.revision = i
            store.save(state)
        path = tmp_path / "cycle_state.jsonl"
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 5


# ═══════════════════════════════════════════════════════════════
# 4. AutonomousCycle 完整循环
# ═══════════════════════════════════════════════════════════════


class TestAutonomousCycleRun:
    """AutonomousCycle.run() 完整循环."""

    def test_run_completes_all_stages(self, store: CycleStore, all_stage_handlers: dict):
        """完整运行所有阶段直到 COMPLETE."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=False)
        state = cycle.run("c1", "2026-08-10")
        assert state.stage == CycleStage.COMPLETE
        assert len(state.completed_stages) == 10  # 除 COMPLETE 外的 10 个阶段
        assert state.blocked_reason == ""
        assert state.failed_stage == ""

    def test_run_records_artifacts_per_stage(self, store: CycleStore, all_stage_handlers: dict):
        """每阶段产出 artifact."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=False)
        state = cycle.run("c1", "2026-08-10")
        assert "observe" in state.artifacts
        assert "decide" in state.artifacts
        assert "learn" in state.artifacts

    def test_run_increments_revision(self, store: CycleStore, all_stage_handlers: dict):
        """每阶段推进 revision."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=False)
        state = cycle.run("c1", "2026-08-10")
        # 10 个阶段 + 完成后 = 每次保存都 revision+1
        assert state.revision >= 10


# ═══════════════════════════════════════════════════════════════
# 5. 可恢复性 (crash/restart)
# ═══════════════════════════════════════════════════════════════


class TestCycleResumability:
    """可恢复性测试."""

    def test_resume_from_saved_state(self, store: CycleStore):
        """从已保存状态恢复执行."""
        # 第一次运行: 只配置 observe handler, 到 understand 时因 handler 缺失阻塞
        cycle1 = AutonomousCycle(store, {"observe": lambda **kw: {"data": 1}}, production=False)
        state1 = cycle1.run("c1", "2026-08-10")
        assert state1.stage == CycleStage.UNDERSTAND
        assert state1.blocked_reason == "handler missing: understand"

        # 第二次运行: 补全所有 handler, 应从 understand 继续
        handlers = {stage.value: lambda **kw: {"stage": kw["state"].stage.value}
                    for stage in ORDER[:-1]}
        cycle2 = AutonomousCycle(store, handlers, production=False)
        state2 = cycle2.run("c1", "2026-08-10")
        assert state2.stage == CycleStage.COMPLETE
        assert "observe" in state2.completed_stages
        assert "understand" in state2.completed_stages

    def test_resume_preserves_artifacts(self, store: CycleStore):
        """恢复时保留已完成的 artifacts."""
        cycle1 = AutonomousCycle(store, {"observe": lambda **kw: {"value": 42}}, production=False)
        cycle1.run("c1", "2026-08-10")

        handlers = {stage.value: lambda **kw: {"stage": kw["state"].stage.value}
                    for stage in ORDER[:-1]}
        cycle2 = AutonomousCycle(store, handlers, production=False)
        state2 = cycle2.run("c1", "2026-08-10")
        assert state2.artifacts.get("observe") == {"value": 42}


# ═══════════════════════════════════════════════════════════════
# 6. production 模式 approval 门禁
# ═══════════════════════════════════════════════════════════════


class TestProductionApprovalGate:
    """production 模式 approval 门禁."""

    def test_production_blocks_without_approval(self, store: CycleStore, all_stage_handlers: dict):
        """production 模式无 approval 阻塞在 APPROVE."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=True)
        state = cycle.run("c1", "2026-08-10", approval_present=False)
        assert state.stage == CycleStage.APPROVE
        assert state.blocked_reason == "production approval missing"

    def test_production_proceeds_with_approval(self, store: CycleStore, all_stage_handlers: dict):
        """production 模式有 approval 继续执行."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=True)
        state = cycle.run("c1", "2026-08-10", approval_present=True)
        assert state.stage == CycleStage.COMPLETE

    def test_dry_run_no_approval_required(self, store: CycleStore, all_stage_handlers: dict):
        """dry_run 模式无需 approval."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=False)
        state = cycle.run("c1", "2026-08-10", approval_present=False)
        assert state.stage == CycleStage.COMPLETE

    def test_production_resume_with_approval(self, store: CycleStore, all_stage_handlers: dict):
        """production 模式阻塞后, 提供 approval 恢复."""
        cycle1 = AutonomousCycle(store, all_stage_handlers, production=True)
        state1 = cycle1.run("c1", "2026-08-10", approval_present=False)
        assert state1.stage == CycleStage.APPROVE

        cycle2 = AutonomousCycle(store, all_stage_handlers, production=True)
        state2 = cycle2.run("c1", "2026-08-10", approval_present=True)
        assert state2.stage == CycleStage.COMPLETE


# ═══════════════════════════════════════════════════════════════
# 7. handler 异常处理
# ═══════════════════════════════════════════════════════════════


class TestHandlerErrors:
    """handler 异常处理."""

    def test_handler_exception_records_failure(self, store: CycleStore):
        """handler 抛异常记录 failed_stage."""
        def failing_handler(**kw):
            raise RuntimeError("handler crashed")
        cycle = AutonomousCycle(store, {"observe": failing_handler}, production=False)
        state = cycle.run("c1", "2026-08-10")
        assert state.stage == CycleStage.OBSERVE
        assert state.failed_stage == "observe"
        assert state.blocked_reason == "RuntimeError"

    def test_handler_missing_blocks_cycle(self, store: CycleStore):
        """handler 缺失阻塞循环."""
        cycle = AutonomousCycle(store, {}, production=False)
        state = cycle.run("c1", "2026-08-10")
        assert state.stage == CycleStage.OBSERVE
        assert state.blocked_reason == "handler missing: observe"


# ═══════════════════════════════════════════════════════════════
# 8. 边界场景
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界场景."""

    def test_empty_handlers_starts_and_blocks(self, store: CycleStore):
        """空 handlers 启动后立即阻塞."""
        cycle = AutonomousCycle(store, {}, production=False)
        state = cycle.run("c1", "2026-08-10")
        assert state.blocked_reason != ""

    def test_completed_stages_no_duplicates(self, store: CycleStore, all_stage_handlers: dict):
        """completed_stages 无重复."""
        cycle = AutonomousCycle(store, all_stage_handlers, production=False)
        state = cycle.run("c1", "2026-08-10")
        assert len(state.completed_stages) == len(set(state.completed_stages))

    def test_handler_receives_state_and_artifacts(self, store: CycleStore):
        """handler 接收 state 和 artifacts 副本."""
        received = []
        def capturing_handler(**kw):
            received.append({
                "stage": kw["state"].stage.value,
                "artifacts_keys": list(kw["artifacts"].keys()),
            })
            return {"captured": True}
        handlers = {stage.value: capturing_handler for stage in ORDER[:-1]}
        cycle = AutonomousCycle(store, handlers, production=False)
        cycle.run("c1", "2026-08-10")
        assert len(received) == 10
        # 第一个 handler 不应有 artifacts
        assert received[0]["artifacts_keys"] == []
        # 后续 handler 应该有前序 artifact
        assert len(received[1]["artifacts_keys"]) >= 1
