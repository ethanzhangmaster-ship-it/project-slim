"""E11.5.1 — Autonomous Creative Controller 测试。

测试范围：
  - CycleStatus: 枚举值
  - CycleRecord: 数据模型 + 属性 + 计时 + to_dict
  - CycleResult: from_record
  - ControllerConfig: 默认值 + 验证
  - ControllerStateMachine: 状态转换 + 非法转换 + 事件处理器 + 重置
  - CycleManager: 生命周期 + 查询 + 统计 + 历史
  - AutonomousCreativeController: run_cycle + run_cycles + 错误处理
  - Full Pipeline: 完整链路 Vision → Decision → Mutation → Evolution
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.intelligence.models import (
    VisionInsight,
    WinnerVisualDNA,
    VisualPattern,
    HookAnalysis,
    CompositionAnalysis,
)
from market_ops.creative_vision_runtime.decision.models import VisionDecision
from market_ops.creative_vision_runtime.mutation.models import (
    MutationGeneChange,
    VisionMutationPlan,
)
from market_ops.creative_vision_runtime.evolution_bridge.models import (
    GenomeMutationTask,
)
from market_ops.creative_vision_runtime.intelligence.engine import (
    VisionIntelligenceEngine,
)
from market_ops.creative_vision_runtime.decision.decision_engine import (
    VisionDecisionEngine,
)
from market_ops.creative_vision_runtime.mutation.mutation_planner import (
    MutationPlanner,
)
from market_ops.creative_vision_runtime.evolution_bridge.integration_engine import (
    EvolutionIntegrationEngine,
)

from market_ops.creative_vision_runtime.autonomous_controller.models import (
    CycleStatus,
    CycleRecord,
    CycleResult,
    ControllerConfig,
)
from market_ops.creative_vision_runtime.autonomous_controller.state_machine import (
    ControllerStateMachine,
)
from market_ops.creative_vision_runtime.autonomous_controller.cycle_manager import (
    CycleManager,
)
from market_ops.creative_vision_runtime.autonomous_controller.controller import (
    AutonomousCreativeController,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_insight(
    asset_id: str = "asset_001",
    patterns: list[str] | None = None,
    winner_prob: float = 0.6,
) -> VisionInsight:
    """Create a mock VisionInsight."""
    pattern_names = patterns or ["high_contrast_opening", "bright_visual"]
    visual_patterns = [
        VisualPattern(
            name=name,
            confidence=0.8,
            category="opening",
            description=f"Pattern: {name}",
        )
        for name in pattern_names
    ]
    hook = HookAnalysis(
        opening_type="instant_reward",
        hook_strength=0.7,
        visual_transition="high",
        first_frame_brightness=0.6,
        brightness_trend="rising",
        description="Instant reward opening",
    )
    composition = CompositionAnalysis(
        composition_type="single_subject",
        subject_count=1,
        color_palette="bright_saturated",
        motion_type="fast_transition",
        avg_edge_density=0.3,
        avg_color_entropy=0.5,
        avg_saturation=0.6,
        description="Single subject with bright saturated colors",
    )
    return VisionInsight(
        creative_asset_id=asset_id,
        visual_patterns=visual_patterns,
        hook_analysis=hook,
        composition_analysis=composition,
        winner_probability=winner_prob,
        similarity_to_winners=0.4,
        summary="Test insight",
    )


def _make_winner_dna(patterns: list[str] | None = None) -> WinnerVisualDNA:
    """Create a mock WinnerVisualDNA."""
    pattern_names = patterns or ["high_contrast_opening", "bright_visual"]
    return WinnerVisualDNA(
        source_count=3,
        source_assets=["w1", "w2", "w3"],
        opening="instant_reward",
        composition="single_subject",
        color="bright_saturated",
        motion="fast_transition",
        patterns=[
            VisualPattern(name=name, confidence=0.8, category="opening", description=f"Winner: {name}")
            for name in pattern_names
        ],
        aggregated_metrics={"avg_hook_score": 0.75},
        description="Test winner DNA",
    )


def _make_genome(gid: str = "genome_001", genes: dict | None = None) -> dict:
    defaults = {
        "hook_contrast": 0.5,
        "color_brightness": 0.5,
        "color_saturation": 0.5,
        "object_density": 0.5,
        "transition_speed": 0.5,
        "reward_reveal_curve": 0.5,
    }
    if genes:
        defaults.update(genes)
    return {
        "genome_id": gid,
        "name": "Test Genome",
        "generation": 0,
        "genes": defaults,
        "parent_ids": [],
        "mutation_count": 0,
        "metadata": {},
    }


class MockFeatureStore:
    """Mock VisionFeatureStore for testing."""
    def __init__(self):
        self._records = {}

    def get(self, asset_id):
        return self._records.get(asset_id)

    def get_frames(self, feature_id):
        return []


class MockIntelligenceEngine:
    """Mock VisionIntelligenceEngine that returns pre-built insights."""
    def __init__(self, insights: dict[str, VisionInsight] | None = None, winner_dna: WinnerVisualDNA | None = None, auto_generate: bool = True):
        self._insights = insights or {}
        self._winner_dna = winner_dna
        self._auto_generate = auto_generate
        self._analyzed_count = 0

    def analyze(self, asset_id: str):
        result = self._insights.get(asset_id)
        if result is None and self._auto_generate:
            result = _make_insight(asset_id=asset_id)
        if result is not None:
            self._analyzed_count += 1
        return result

    def analyze_batch(self, asset_ids: list[str]):
        return {aid: self.analyze(aid) for aid in asset_ids}

    def extract_winner_dna(self, asset_ids: list[str]):
        return self._winner_dna or _make_winner_dna()

    @property
    def analyzed_count(self):
        return self._analyzed_count


# ═══════════════════════════════════════════════════════════
# CycleStatus
# ═══════════════════════════════════════════════════════════

class TestCycleStatus:
    """CycleStatus 枚举测试。"""

    def test_all_values(self):
        assert CycleStatus.IDLE.value == "idle"
        assert CycleStatus.ANALYZING.value == "analyzing"
        assert CycleStatus.DECIDING.value == "deciding"
        assert CycleStatus.MUTATING.value == "mutating"
        assert CycleStatus.EXECUTING.value == "executing"
        assert CycleStatus.COMPLETED.value == "completed"
        assert CycleStatus.FAILED.value == "failed"

    def test_str_equals_value(self):
        assert CycleStatus.IDLE.value == "idle"
        assert CycleStatus.COMPLETED.value == "completed"


# ═══════════════════════════════════════════════════════════
# CycleRecord
# ═══════════════════════════════════════════════════════════

class TestCycleRecord:
    """CycleRecord 数据模型测试。"""

    def test_create_default(self):
        record = CycleRecord()
        assert record.cycle_id.startswith("cycle_")
        assert record.cycle_number == 0
        assert record.status == CycleStatus.IDLE
        assert record.input_asset_ids == []
        assert record.winner_asset_ids == []
        assert record.insights == {}
        assert record.decisions == {}
        assert record.mutation_plans == {}
        assert record.mutation_tasks == {}
        assert record.mutated_genomes == {}

    def test_create_with_values(self):
        record = CycleRecord(
            cycle_number=5,
            input_asset_ids=["asset_001", "asset_002"],
            winner_asset_ids=["winner_001"],
        )
        assert record.cycle_number == 5
        assert record.asset_count == 2
        assert len(record.winner_asset_ids) == 1

    def test_asset_count(self):
        record = CycleRecord(input_asset_ids=["a", "b", "c"])
        assert record.asset_count == 3

    def test_insight_count(self):
        record = CycleRecord()
        record.insights = {"a": _make_insight("a"), "b": None, "c": _make_insight("c")}
        assert record.insight_count == 2

    def test_decision_count(self):
        record = CycleRecord()
        record.decisions = {"a": MagicMock(), "b": MagicMock()}
        assert record.decision_count == 2

    def test_plan_count(self):
        record = CycleRecord()
        record.mutation_plans = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}
        assert record.plan_count == 3

    def test_task_count(self):
        record = CycleRecord()
        record.mutation_tasks = {"a": MagicMock()}
        assert record.task_count == 1

    def test_genome_count(self):
        record = CycleRecord()
        record.mutated_genomes = {"g1": {}, "g2": {}}
        assert record.genome_count == 2

    def test_total_mutations(self):
        t1 = MagicMock()
        t1.mutation_count = 3
        t2 = MagicMock()
        t2.mutation_count = 2
        record = CycleRecord()
        record.mutation_tasks = {"a": t1, "b": t2}
        assert record.total_mutations == 5

    def test_total_mutations_no_count_attr(self):
        t = MagicMock(spec=[])  # No mutation_count attribute
        record = CycleRecord()
        record.mutation_tasks = {"a": t}
        assert record.total_mutations == 0

    def test_mark_started(self):
        record = CycleRecord()
        record.mark_started()
        assert record.status == CycleStatus.ANALYZING
        assert record.started_at != ""

    def test_mark_completed(self):
        record = CycleRecord()
        record.mark_started()
        record.mark_completed()
        assert record.is_completed is True
        assert record.completed_at != ""

    def test_mark_failed(self):
        record = CycleRecord()
        record.mark_failed("test error")
        assert record.is_failed is True
        assert record.error_message == "test error"

    def test_is_completed(self):
        record = CycleRecord()
        assert record.is_completed is False
        record.mark_completed()
        assert record.is_completed is True

    def test_is_failed(self):
        record = CycleRecord()
        assert record.is_failed is False
        record.mark_failed("e")
        assert record.is_failed is True

    def test_duration_na(self):
        record = CycleRecord()
        assert record.duration == "N/A"

    def test_duration_computed(self):
        record = CycleRecord()
        record.started_at = "2026-01-01T00:00:00"
        record.completed_at = "2026-01-01T00:00:01.500000"
        assert "1.50" in record.duration

    def test_to_dict(self):
        record = CycleRecord(
            cycle_number=1,
            input_asset_ids=["a"],
            winner_asset_ids=["w"],
        )
        record.mark_completed()
        d = record.to_dict()
        assert d["cycle_number"] == 1
        assert d["status"] == "completed"
        assert d["asset_count"] == 1

    def test_repr(self):
        record = CycleRecord(cycle_number=3, input_asset_ids=["a", "b"])
        r = repr(record)
        assert "3" in r
        assert "idle" in r


# ═══════════════════════════════════════════════════════════
# CycleResult
# ═══════════════════════════════════════════════════════════

class TestCycleResult:
    """CycleResult 测试。"""

    def test_from_record(self):
        record = CycleRecord(cycle_number=2, input_asset_ids=["a", "b", "c"])
        record.mutation_tasks = {}
        t1 = MagicMock()
        t1.mutation_count = 3
        record.mutation_tasks["a"] = t1
        record.mutated_genomes = {"g1": {}}

        result = CycleResult.from_record(record)
        assert result.cycle_number == 2
        assert result.asset_count == 3
        assert result.total_mutations == 3
        assert result.genomes_mutated == 1

    def test_from_record_default(self):
        record = CycleRecord()
        result = CycleResult.from_record(record)
        assert result.cycle_number == 0
        assert result.status == CycleStatus.IDLE

    def test_repr(self):
        result = CycleResult(cycle_number=1, total_mutations=2)
        r = repr(result)
        assert "1" in r
        assert "2" in r


# ═══════════════════════════════════════════════════════════
# ControllerConfig
# ═══════════════════════════════════════════════════════════

class TestControllerConfig:
    """ControllerConfig 测试。"""

    def test_defaults(self):
        config = ControllerConfig()
        assert config.max_cycles == 10
        assert config.min_confidence == 0.3
        assert config.auto_evolve is True
        assert config.stop_on_no_mutations is True
        assert config.stop_on_max_cycles is True

    def test_custom_values(self):
        config = ControllerConfig(
            max_cycles=5,
            min_confidence=0.5,
            auto_evolve=False,
        )
        assert config.max_cycles == 5
        assert config.min_confidence == 0.5
        assert config.auto_evolve is False

    def test_max_cycles_validation(self):
        with pytest.raises(ValueError, match="max_cycles"):
            ControllerConfig(max_cycles=0)

    def test_min_confidence_validation_low(self):
        with pytest.raises(ValueError, match="min_confidence"):
            ControllerConfig(min_confidence=-0.1)

    def test_min_confidence_validation_high(self):
        with pytest.raises(ValueError, match="min_confidence"):
            ControllerConfig(min_confidence=1.1)

    def test_to_dict(self):
        config = ControllerConfig(max_cycles=3, min_confidence=0.5)
        d = config.to_dict()
        assert d["max_cycles"] == 3
        assert d["min_confidence"] == 0.5

    def test_repr(self):
        config = ControllerConfig(max_cycles=5)
        r = repr(config)
        assert "5" in r


# ═══════════════════════════════════════════════════════════
# ControllerStateMachine
# ═══════════════════════════════════════════════════════════

class TestControllerStateMachine:
    """ControllerStateMachine 测试。"""

    def test_initial_state(self):
        sm = ControllerStateMachine()
        assert sm.current_state == CycleStatus.IDLE
        assert sm.is_idle is True
        assert sm.is_running is False
        assert sm.is_terminal is False

    def test_transition_idle_to_analyzing(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        assert sm.current_state == CycleStatus.ANALYZING

    def test_full_happy_path(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        sm.transition_to_deciding()
        sm.transition_to_mutating()
        sm.transition_to_executing()
        sm.transition_to_completed()
        assert sm.current_state == CycleStatus.COMPLETED
        assert sm.transition_count == 5

    def test_full_path_with_failure(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        sm.transition_to_failed()
        assert sm.current_state == CycleStatus.FAILED
        assert sm.is_terminal is True

    def test_transition_history(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        sm.transition_to_deciding()
        sm.transition_to_mutating()
        assert len(sm.history) == 4  # IDLE + 3 transitions
        assert sm.history[0] == CycleStatus.IDLE
        assert sm.history[1] == CycleStatus.ANALYZING

    def test_can_transition(self):
        sm = ControllerStateMachine()
        assert sm.can_transition(CycleStatus.ANALYZING) is True
        assert sm.can_transition(CycleStatus.COMPLETED) is False  # IDLE → COMPLETED invalid

    def test_can_transition_from_analyzing(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        assert sm.can_transition(CycleStatus.DECIDING) is True
        assert sm.can_transition(CycleStatus.FAILED) is True
        assert sm.can_transition(CycleStatus.IDLE) is False

    def test_can_transition_from_completed(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        sm.transition_to_deciding()
        sm.transition_to_mutating()
        sm.transition_to_executing()
        sm.transition_to_completed()
        assert sm.can_transition(CycleStatus.IDLE) is True
        assert sm.can_transition(CycleStatus.ANALYZING) is False

    def test_invalid_transition_raises(self):
        sm = ControllerStateMachine()
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(CycleStatus.COMPLETED)

    def test_invalid_transition_error_message(self):
        sm = ControllerStateMachine()
        with pytest.raises(ValueError) as exc_info:
            sm.transition(CycleStatus.DECIDING)
        assert "idle" in str(exc_info.value)
        assert "deciding" in str(exc_info.value)

    def test_reset(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        sm.transition_to_deciding()
        sm.reset()
        assert sm.current_state == CycleStatus.IDLE
        assert sm.transition_count == 2  # count preserved
        assert len(sm.history) == 1  # history reset

    def test_is_running(self):
        sm = ControllerStateMachine()
        assert sm.is_running is False
        sm.transition_to_analyzing()
        assert sm.is_running is True
        sm.transition_to_deciding()
        sm.transition_to_mutating()
        sm.transition_to_executing()
        sm.transition_to_completed()
        assert sm.is_running is False

    def test_is_terminal(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        sm.transition_to_failed()
        assert sm.is_terminal is True

    def test_event_handler(self):
        sm = ControllerStateMachine()
        handler_called = []

        def handler(state, count):
            handler_called.append((state, count))

        sm.on(CycleStatus.ANALYZING, handler)
        sm.transition_to_analyzing()
        assert len(handler_called) == 1
        assert handler_called[0][0] == CycleStatus.ANALYZING

    def test_event_handler_not_called_for_other_states(self):
        sm = ControllerStateMachine()
        handler_called = []

        def handler(state, count):
            handler_called.append(state)

        sm.on(CycleStatus.DECIDING, handler)
        sm.transition_to_analyzing()
        assert len(handler_called) == 0

    def test_event_handler_error_does_not_block(self):
        sm = ControllerStateMachine()

        def bad_handler(state, count):
            raise RuntimeError("handler error")

        sm.on(CycleStatus.ANALYZING, bad_handler)
        sm.transition_to_analyzing()  # Should not raise
        assert sm.current_state == CycleStatus.ANALYZING

    def test_get_stats(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        stats = sm.get_stats()
        assert stats["current_state"] == "analyzing"
        assert stats["transition_count"] == 1
        assert stats["is_idle"] is False
        assert stats["is_running"] is True

    def test_repr(self):
        sm = ControllerStateMachine()
        sm.transition_to_analyzing()
        r = repr(sm)
        assert "analyzing" in r
        assert "1" in r


# ═══════════════════════════════════════════════════════════
# CycleManager
# ═══════════════════════════════════════════════════════════

class TestCycleManager:
    """CycleManager 测试。"""

    def test_start_cycle(self):
        cm = CycleManager()
        record = cm.start_cycle(["asset_001", "asset_002"])
        assert record.cycle_number == 1
        assert record.status == CycleStatus.ANALYZING
        assert record.asset_count == 2
        assert cm.get_active_cycle() is not None

    def test_start_cycle_with_winners(self):
        cm = CycleManager()
        record = cm.start_cycle(["a"], ["w1", "w2"])
        assert len(record.winner_asset_ids) == 2

    def test_cannot_start_second_cycle(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        with pytest.raises(RuntimeError, match="Active cycle"):
            cm.start_cycle(["b"])

    def test_complete_cycle(self):
        cm = CycleManager()
        record = cm.start_cycle(["a"])
        completed = cm.complete_cycle()
        assert completed is not None
        assert completed.is_completed is True
        assert cm.get_active_cycle() is None

    def test_complete_no_active(self):
        cm = CycleManager()
        assert cm.complete_cycle() is None

    def test_fail_cycle(self):
        cm = CycleManager()
        record = cm.start_cycle(["a"])
        failed = cm.fail_cycle("test error")
        assert failed is not None
        assert failed.is_failed is True
        assert failed.error_message == "test error"

    def test_fail_no_active(self):
        cm = CycleManager()
        assert cm.fail_cycle("error") is None

    def test_get_cycle_by_id(self):
        cm = CycleManager()
        record = cm.start_cycle(["a"])
        found = cm.get_cycle(record.cycle_id)
        assert found is not None
        assert found.cycle_id == record.cycle_id

    def test_get_cycle_by_id_not_found(self):
        cm = CycleManager()
        assert cm.get_cycle("nonexistent") is None

    def test_get_cycle_by_number(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        cm.complete_cycle()
        cm.start_cycle(["b"])
        cm.complete_cycle()

        found = cm.get_cycle_by_number(2)
        assert found is not None
        assert found.cycle_number == 2

    def test_get_cycle_by_number_not_found(self):
        cm = CycleManager()
        assert cm.get_cycle_by_number(99) is None

    def test_get_history(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        cm.complete_cycle()
        cm.start_cycle(["b"])
        cm.fail_cycle("error")

        history = cm.get_history()
        assert len(history) == 2

    def test_get_all_cycles(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        all_cycles = cm.get_all_cycles()
        assert len(all_cycles) == 1

    def test_get_recent_results(self):
        cm = CycleManager()
        for i in range(3):
            cm.start_cycle(["a"])
            cm.complete_cycle()

        results = cm.get_recent_results(2)
        assert len(results) == 2

    def test_total_cycles(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        cm.complete_cycle()
        cm.start_cycle(["b"])
        cm.fail_cycle("e")
        assert cm.total_cycles == 2

    def test_completed_count(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        cm.complete_cycle()
        cm.start_cycle(["b"])
        cm.fail_cycle("e")
        assert cm.completed_count == 1
        assert cm.failed_count == 1

    def test_total_mutations(self):
        cm = CycleManager()
        r1 = cm.start_cycle(["a"])
        t = MagicMock()
        t.mutation_count = 5
        r1.mutation_tasks = {"a": t}
        cm.complete_cycle()

        r2 = cm.start_cycle(["b"])
        t2 = MagicMock()
        t2.mutation_count = 3
        r2.mutation_tasks = {"b": t2}
        cm.complete_cycle()

        assert cm.total_mutations == 8

    def test_get_stats(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        cm.complete_cycle()

        stats = cm.get_stats()
        assert stats["total_cycles"] == 1
        assert stats["completed_count"] == 1
        assert stats["failed_count"] == 0

    def test_repr(self):
        cm = CycleManager()
        cm.start_cycle(["a"])
        cm.complete_cycle()
        r = repr(cm)
        assert "total=1" in r
        assert "completed=1" in r


# ═══════════════════════════════════════════════════════════
# AutonomousCreativeController
# ═══════════════════════════════════════════════════════════

class TestAutonomousCreativeController:
    """AutonomousCreativeController 测试。"""

    def test_run_cycle_single_asset(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        # Replace with mock
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(["asset_001"], genomes)

        assert record.is_completed is True
        assert record.insight_count == 1
        assert record.decision_count == 1
        assert record.plan_count == 1
        assert record.task_count == 1
        assert record.genome_count == 1

    def test_run_cycle_multiple_assets(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {
            "asset_001": _make_genome(gid="asset_001"),
            "asset_002": _make_genome(gid="asset_002"),
        }
        record = controller.run_cycle(["asset_001", "asset_002"], genomes)

        assert record.is_completed is True
        assert record.insight_count == 2
        assert record.decision_count == 2
        assert record.plan_count == 2

    def test_run_cycle_with_winners(self):
        intelligence = MockIntelligenceEngine(
            winner_dna=_make_winner_dna(["high_contrast_opening"])
        )
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(
            ["asset_001"], genomes, winner_asset_ids=["winner_001"]
        )

        assert record.is_completed is True
        assert record.winner_dna is not None

    def test_run_cycle_genome_is_mutated(self):
        # Provide insight with a pattern that differs from winner DNA to trigger mutation
        intelligence = MockIntelligenceEngine(
            insights={
                "asset_001": _make_insight(
                    "asset_001",
                    patterns=["high_contrast_opening"],
                ),
            },
            winner_dna=_make_winner_dna(["bright_visual"]),  # Different pattern → triggers mutation
        )
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        original_genome = _make_genome(gid="asset_001")
        genomes = {"asset_001": original_genome}
        record = controller.run_cycle(
            ["asset_001"], genomes, winner_asset_ids=["winner_001"]
        )

        mutated = record.mutated_genomes.get("asset_001")
        assert mutated is not None
        # Genome should have been mutated (different from original)
        assert mutated["mutation_count"] > 0

    def test_run_cycle_missing_insight(self):
        """Asset without insight should be skipped gracefully."""
        intelligence = MockIntelligenceEngine(auto_generate=False)  # No auto-generated insights
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(["asset_001"], genomes)

        assert record.is_completed is True
        assert record.insight_count == 0

    def test_run_cycle_no_genome_for_asset(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {}  # No genomes
        record = controller.run_cycle(["asset_001"], genomes)

        assert record.is_completed is True
        assert record.plan_count == 0

    def test_run_cycle_handles_error(self):
        """Test that errors are caught and cycle is marked as failed."""
        bad_intelligence = MagicMock()
        bad_intelligence.analyze_batch = MagicMock(side_effect=RuntimeError("Boom"))
        bad_intelligence.analyzed_count = 0

        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = bad_intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(["asset_001"], genomes)

        assert record.is_failed is True
        assert "Boom" in record.error_message

    def test_run_cycles_single(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        results = controller.run_cycles(["asset_001"], genomes)

        assert len(results) == 1
        assert results[0].is_completed is True

    def test_run_cycles_stops_on_failure(self):
        bad_intelligence = MagicMock()
        bad_intelligence.analyze_batch = MagicMock(side_effect=RuntimeError("Boom"))
        bad_intelligence.analyzed_count = 0

        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=3),
        )
        controller._intelligence = bad_intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        results = controller.run_cycles(["asset_001"], genomes)

        assert len(results) == 1  # Stopped after first failure

    def test_get_current_state(self):
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
        )
        assert controller.get_current_state() == CycleStatus.IDLE

        controller._intelligence = MockIntelligenceEngine()
        genomes = {"asset_001": _make_genome(gid="asset_001")}
        controller.run_cycle(["asset_001"], genomes)

        assert controller.get_current_state() == CycleStatus.COMPLETED

    def test_get_cycle_history(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        controller.run_cycle(["asset_001"], genomes)

        history = controller.get_cycle_history()
        assert len(history) == 1

    def test_get_active_cycle(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        controller.run_cycle(["asset_001"], genomes)

        # After completion, no active cycle
        assert controller.get_active_cycle() is None

    def test_get_stats(self):
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        controller.run_cycle(["asset_001"], genomes)

        stats = controller.get_stats()
        assert "state_machine" in stats
        assert "cycle_manager" in stats
        assert "config" in stats

    def test_repr(self):
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
        )
        r = repr(controller)
        assert "idle" in r

    def test_default_engines_created(self):
        """When optional engines are not provided, defaults should be created."""
        controller = AutonomousCreativeController(
            intelligence_engine=MockIntelligenceEngine(),
        )
        assert controller._decision is not None
        assert controller._planner is not None
        assert controller._evolution is not None


# ═══════════════════════════════════════════════════════════
# Full Pipeline Integration
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路集成测试：Vision → Decision → Mutation → Evolution。"""

    def test_full_pipeline_with_real_engines(self):
        """使用真实引擎测试完整链路（Mock Intelligence）。"""
        intelligence = MockIntelligenceEngine(
            insights={
                "asset_001": _make_insight(
                    "asset_001",
                    patterns=["high_contrast_opening", "bright_visual"],
                ),
            },
            winner_dna=_make_winner_dna(["high_contrast_opening"]),
        )

        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        # Inject mock intelligence
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(
            ["asset_001"], genomes, winner_asset_ids=["winner_001"]
        )

        assert record.is_completed is True
        assert record.insight_count == 1
        assert record.decision_count == 1
        assert record.plan_count >= 0
        assert record.mutated_genomes.get("asset_001") is not None

    def test_multiple_assets_full_pipeline(self):
        """Multiple assets through the full pipeline."""
        intelligence = MockIntelligenceEngine(
            insights={
                "asset_001": _make_insight("asset_001", patterns=["high_contrast_opening"]),
                "asset_002": _make_insight("asset_002", patterns=["bright_visual"]),
            },
            winner_dna=_make_winner_dna(["high_contrast_opening"]),
        )

        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {
            "asset_001": _make_genome(gid="asset_001"),
            "asset_002": _make_genome(gid="asset_002"),
        }
        record = controller.run_cycle(
            ["asset_001", "asset_002"], genomes, winner_asset_ids=["w1"]
        )

        assert record.is_completed is True
        assert record.insight_count == 2
        assert record.decision_count == 2
        assert record.genome_count == 2

    def test_cycle_record_contains_all_intermediate_results(self):
        """CycleRecord should contain all intermediate pipeline results."""
        intelligence = MockIntelligenceEngine(
            insights={"asset_001": _make_insight("asset_001")},
            winner_dna=_make_winner_dna(),
        )

        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(
            ["asset_001"], genomes, winner_asset_ids=["w1"]
        )

        # Check all intermediate results are populated
        assert "asset_001" in record.insights
        assert record.winner_dna is not None
        assert "asset_001" in record.decisions
        assert "asset_001" in record.mutation_tasks
        assert "asset_001" in record.mutated_genomes

    def test_cycle_record_timing(self):
        """CycleRecord should have proper timing."""
        intelligence = MockIntelligenceEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        genomes = {"asset_001": _make_genome(gid="asset_001")}
        record = controller.run_cycle(["asset_001"], genomes)

        assert record.started_at != ""
        assert record.completed_at != ""
        assert record.duration != "N/A"

    def test_genome_preserves_unrelated_genes(self):
        """Genes not targeted by mutation should be preserved."""
        intelligence = MockIntelligenceEngine(
            insights={"asset_001": _make_insight("asset_001")},
        )

        controller = AutonomousCreativeController(
            intelligence_engine=MagicMock(),
            config=ControllerConfig(max_cycles=1),
        )
        controller._intelligence = intelligence

        original_color_brightness = 0.8
        genomes = {
            "asset_001": _make_genome(
                gid="asset_001",
                genes={"color_brightness": original_color_brightness},
            ),
        }
        record = controller.run_cycle(["asset_001"], genomes)

        mutated = record.mutated_genomes["asset_001"]
        assert mutated["genes"]["color_brightness"] == original_color_brightness


# ═══════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════

class TestPackageExports:
    """包导出测试。"""

    def test_all_exports(self):
        from market_ops.creative_vision_runtime.autonomous_controller import (
            CycleStatus,
            CycleRecord,
            CycleResult,
            ControllerConfig,
            ControllerStateMachine,
            CycleManager,
            AutonomousCreativeController,
        )
        assert CycleStatus is not None
        assert CycleRecord is not None
        assert CycleResult is not None
        assert ControllerConfig is not None
        assert ControllerStateMachine is not None
        assert CycleManager is not None
        assert AutonomousCreativeController is not None

    def test_all_list(self):
        import market_ops.creative_vision_runtime.autonomous_controller as ac
        expected = [
            "CycleStatus",
            "CycleRecord",
            "CycleResult",
            "ControllerConfig",
            "ControllerStateMachine",
            "CycleManager",
            "AutonomousCreativeController",
        ]
        for name in expected:
            assert name in ac.__all__, f"{name} missing from __all__"