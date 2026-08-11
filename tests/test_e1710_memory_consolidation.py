"""E17.10 Memory Consolidation Pipeline — 测试用例.

Day 7.10:
  覆盖 Memory Consolidation Pipeline 层的:
    - PipelineStage 枚举
    - StageResult 模型 (properties, to_dict, edge cases)
    - ConsolidationReport 模型 (from_stages, properties, to_dict, _build_summary, edge cases)
    - MemoryConsolidationPipeline 引擎 (consolidate, consolidate_batch, fail-safe, reports, stats, reset)
    - Edge cases (empty cycle_result, no pattern_store, partial stage failures)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.memory_consolidation_models import (
    ConsolidationReport,
    PipelineStage,
    StageResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.memory_consolidation_pipeline import (
    MemoryConsolidationPipeline,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
    PatternStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternMemory,
    PatternCondition,
    PatternAction,
    PatternPerformance,
    PatternMiningDimension,
)


# ═══════════════════════════════════════════════════════════════
# Test: PipelineStage
# ═══════════════════════════════════════════════════════════════


class TestPipelineStage:
    """PipelineStage 枚举测试."""

    def test_enum_values(self):
        """验证五个阶段枚举值."""
        assert PipelineStage.EXTRACT.value == "extract"
        assert PipelineStage.COMPRESS.value == "compress"
        assert PipelineStage.REINFORCE.value == "reinforce"
        assert PipelineStage.DECAY.value == "decay"
        assert PipelineStage.UPDATE_GRAPH.value == "update_graph"

    def test_enum_count(self):
        """验证共五个阶段."""
        assert len(PipelineStage) == 5

    def test_enum_is_string(self):
        """验证是 str 枚举."""
        assert isinstance(PipelineStage.EXTRACT, str)
        assert PipelineStage.EXTRACT == "extract"

    def test_enum_identity(self):
        """验证枚举成员唯一性."""
        stages = list(PipelineStage)
        assert PipelineStage.EXTRACT in stages
        assert PipelineStage.COMPRESS in stages
        assert PipelineStage.REINFORCE in stages
        assert PipelineStage.DECAY in stages
        assert PipelineStage.UPDATE_GRAPH in stages

    def test_enum_ordering(self):
        """验证枚举顺序 (EXTRACT 第一, UPDATE_GRAPH 最后)."""
        stages = list(PipelineStage)
        assert stages[0] == PipelineStage.EXTRACT
        assert stages[-1] == PipelineStage.UPDATE_GRAPH


# ═══════════════════════════════════════════════════════════════
# Test: StageResult
# ═══════════════════════════════════════════════════════════════


class TestStageResult:
    """StageResult 模型测试."""

    def test_create_default(self):
        """默认创建."""
        sr = StageResult()
        assert sr.stage == PipelineStage.EXTRACT
        assert sr.success is True
        assert sr.duration_ms == 0.0
        assert sr.items_processed == 0
        assert sr.items_produced == 0
        assert sr.error is None
        assert sr.result_ref is None
        assert sr.metadata == {}

    def test_create_with_values(self):
        """带值创建."""
        sr = StageResult(
            stage=PipelineStage.COMPRESS,
            success=True,
            duration_ms=150.5,
            items_processed=10,
            items_produced=3,
            result_ref="ref",
            metadata={"key": "val"},
        )
        assert sr.stage == PipelineStage.COMPRESS
        assert sr.success is True
        assert sr.duration_ms == 150.5
        assert sr.items_processed == 10
        assert sr.items_produced == 3
        assert sr.result_ref == "ref"
        assert sr.metadata == {"key": "val"}

    def test_create_failed(self):
        """失败阶段."""
        sr = StageResult(
            stage=PipelineStage.REINFORCE,
            success=False,
            error="No pattern store",
        )
        assert sr.success is False
        assert sr.error == "No pattern store"

    def test_is_failed_property(self):
        """is_failed 属性."""
        sr_ok = StageResult(success=True)
        assert sr_ok.is_failed is False

        sr_fail = StageResult(success=False)
        assert sr_fail.is_failed is True

    def test_throughput_zero_duration(self):
        """吞吐量: 零耗时."""
        sr = StageResult(duration_ms=0, items_produced=5)
        assert sr.throughput == 0.0

    def test_throughput_normal(self):
        """吞吐量: 正常计算."""
        sr = StageResult(duration_ms=2000, items_produced=10)
        assert sr.throughput == 5.0  # 10 / (2000/1000) = 5.0

    def test_throughput_rounding(self):
        """吞吐量: 四舍五入."""
        sr = StageResult(duration_ms=3000, items_produced=10)
        assert sr.throughput == 3.33  # 10 / 3 = 3.333...

    def test_throughput_zero_items(self):
        """吞吐量: 零产出."""
        sr = StageResult(duration_ms=1000, items_produced=0)
        assert sr.throughput == 0.0

    def test_to_dict(self):
        """序列化."""
        sr = StageResult(
            stage=PipelineStage.COMPRESS,
            success=True,
            duration_ms=100.0,
            items_processed=5,
            items_produced=2,
            metadata={"k": "v"},
        )
        d = sr.to_dict()
        assert d["stage"] == "compress"
        assert d["success"] is True
        assert d["duration_ms"] == 100.0
        assert d["items_processed"] == 5
        assert d["items_produced"] == 2
        assert d["error"] is None
        assert d["metadata"] == {"k": "v"}

    def test_to_dict_failed(self):
        """序列化: 失败阶段."""
        sr = StageResult(
            stage=PipelineStage.DECAY,
            success=False,
            error="Timeout",
        )
        d = sr.to_dict()
        assert d["stage"] == "decay"
        assert d["success"] is False
        assert d["error"] == "Timeout"

    def test_all_stage_types(self):
        """所有阶段类型均可创建."""
        for stage in PipelineStage:
            sr = StageResult(stage=stage)
            assert sr.stage == stage
            assert sr.to_dict()["stage"] == stage.value


# ═══════════════════════════════════════════════════════════════
# Test: ConsolidationReport
# ═══════════════════════════════════════════════════════════════


class TestConsolidationReport:
    """ConsolidationReport 模型测试."""

    def test_create_default(self):
        """默认创建."""
        r = ConsolidationReport()
        assert r.report_id != ""
        assert r.cycle_number == 0
        assert r.pipeline_id == ""
        assert r.stages == []
        assert r.total_duration_ms == 0.0
        assert r.total_experiences == 0
        assert r.total_patterns == 0
        assert r.reinforced_patterns == 0
        assert r.decayed_patterns == 0
        assert r.graph_nodes_updated == 0
        assert r.graph_edges_updated == 0
        assert r.overall_success is True
        assert r.failed_stages == []
        assert r.summary == ""

    def test_is_empty_true(self):
        """空报告."""
        r = ConsolidationReport()
        assert r.is_empty is True
        assert r.stage_count == 0

    def test_is_empty_false(self):
        """非空报告."""
        r = ConsolidationReport(stages=[StageResult()])
        assert r.is_empty is False
        assert r.stage_count == 1

    def test_success_count(self):
        """成功计数."""
        r = ConsolidationReport(stages=[
            StageResult(stage=PipelineStage.EXTRACT, success=True),
            StageResult(stage=PipelineStage.COMPRESS, success=True),
            StageResult(stage=PipelineStage.REINFORCE, success=False),
        ])
        assert r.success_count == 2

    def test_failure_count(self):
        """失败计数."""
        r = ConsolidationReport(stages=[
            StageResult(stage=PipelineStage.EXTRACT, success=True),
            StageResult(stage=PipelineStage.COMPRESS, success=False),
            StageResult(stage=PipelineStage.REINFORCE, success=False),
        ])
        assert r.failure_count == 2

    def test_has_failures_true(self):
        """有失败."""
        r = ConsolidationReport(stages=[
            StageResult(success=False),
        ])
        assert r.has_failures is True

    def test_has_failures_false(self):
        """无失败."""
        r = ConsolidationReport(stages=[
            StageResult(success=True),
            StageResult(success=True),
        ])
        assert r.has_failures is False

    def test_has_changes_true(self):
        """有变化."""
        r = ConsolidationReport(total_patterns=5)
        assert r.has_changes is True

    def test_has_changes_false(self):
        """无变化."""
        r = ConsolidationReport()
        assert r.has_changes is False

    def test_has_changes_reinforced(self):
        """有强化."""
        r = ConsolidationReport(reinforced_patterns=3)
        assert r.has_changes is True

    def test_has_changes_decayed(self):
        """有衰减."""
        r = ConsolidationReport(decayed_patterns=2)
        assert r.has_changes is True

    def test_has_changes_graph(self):
        """有图谱更新."""
        r = ConsolidationReport(graph_nodes_updated=4)
        assert r.has_changes is True

    # ── from_stages ──────────────────────────────────────────────

    def test_from_stages_empty(self):
        """空阶段列表."""
        r = ConsolidationReport.from_stages([])
        assert r.stage_count == 0
        assert r.overall_success is True
        assert r.total_duration_ms == 0.0

    def test_from_stages_all_success(self):
        """全部成功."""
        stages = [
            StageResult(stage=PipelineStage.EXTRACT, duration_ms=10, items_produced=3),
            StageResult(stage=PipelineStage.COMPRESS, duration_ms=20, items_produced=2),
            StageResult(stage=PipelineStage.REINFORCE, duration_ms=15, items_produced=1),
            StageResult(stage=PipelineStage.DECAY, duration_ms=12, items_produced=4),
            StageResult(stage=PipelineStage.UPDATE_GRAPH, duration_ms=8, items_produced=5),
        ]
        r = ConsolidationReport.from_stages(stages, cycle_number=3, pipeline_id="abc123")
        assert r.cycle_number == 3
        assert r.pipeline_id == "abc123"
        assert r.stage_count == 5
        assert r.overall_success is True
        assert r.failed_stages == []
        assert r.total_duration_ms == 65.0
        assert r.total_experiences == 3
        assert r.total_patterns == 2
        assert r.reinforced_patterns == 1
        assert r.decayed_patterns == 4
        assert r.graph_nodes_updated == 5

    def test_from_stages_with_failures(self):
        """部分失败."""
        stages = [
            StageResult(stage=PipelineStage.EXTRACT, success=True, items_produced=5),
            StageResult(stage=PipelineStage.COMPRESS, success=False, error="No data"),
            StageResult(stage=PipelineStage.REINFORCE, success=False, error="Missing"),
            StageResult(stage=PipelineStage.DECAY, success=True, items_produced=2),
            StageResult(stage=PipelineStage.UPDATE_GRAPH, success=True, items_produced=3),
        ]
        r = ConsolidationReport.from_stages(stages)
        assert r.overall_success is False
        assert r.failed_stages == ["compress", "reinforce"]
        assert r.failure_count == 2
        assert r.success_count == 3

    def test_from_stages_missing_stage_types(self):
        """缺少某些阶段类型."""
        stages = [
            StageResult(stage=PipelineStage.EXTRACT, items_produced=4),
        ]
        r = ConsolidationReport.from_stages(stages)
        assert r.total_experiences == 4
        assert r.total_patterns == 0
        assert r.reinforced_patterns == 0
        assert r.decayed_patterns == 0
        assert r.graph_nodes_updated == 0

    # ── _build_summary ───────────────────────────────────────────

    def test_build_summary_success(self):
        """成功摘要."""
        summary = ConsolidationReport._build_summary(
            total_experiences=5, total_patterns=3,
            reinforced=2, decayed=1, graph_nodes=4,
            total_duration_ms=150.0, failed_count=0,
        )
        assert "COMPLETED" in summary
        assert "Experiences extracted:" in summary
        assert "5" in summary
        summary_lower = summary.lower()
        assert "pattern" in summary_lower

    def test_build_summary_with_failures(self):
        """失败摘要."""
        summary = ConsolidationReport._build_summary(
            total_experiences=0, total_patterns=0,
            reinforced=0, decayed=0, graph_nodes=0,
            total_duration_ms=50.0, failed_count=2,
        )
        assert "COMPLETED (2 failures)" in summary

    # ── to_dict ──────────────────────────────────────────────────

    def test_to_dict(self):
        """序列化."""
        r = ConsolidationReport(
            cycle_number=5,
            pipeline_id="pipe-1",
            stages=[StageResult(stage=PipelineStage.EXTRACT, items_produced=3)],
            total_duration_ms=100.0,
            total_experiences=3,
            total_patterns=2,
            reinforced_patterns=1,
            decayed_patterns=0,
            graph_nodes_updated=4,
            graph_edges_updated=6,
            summary="test summary",
        )
        d = r.to_dict()
        assert d["report_id"] == r.report_id
        assert d["cycle_number"] == 5
        assert d["pipeline_id"] == "pipe-1"
        assert len(d["stages"]) == 1
        assert d["total_duration_ms"] == 100.0
        assert d["total_experiences"] == 3
        assert d["total_patterns"] == 2
        assert d["reinforced_patterns"] == 1
        assert d["decayed_patterns"] == 0
        assert d["graph_nodes_updated"] == 4
        assert d["graph_edges_updated"] == 6
        assert d["overall_success"] is True
        assert d["summary"] == "test summary"

    def test_to_dict_with_failed_stages(self):
        """序列化: 包含失败阶段."""
        r = ConsolidationReport(
            failed_stages=["compress", "reinforce"],
            overall_success=False,
        )
        d = r.to_dict()
        assert d["overall_success"] is False
        assert d["failed_stages"] == ["compress", "reinforce"]


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def pattern_store_with_data() -> PatternStore:
    """带模式数据的 PatternStore."""
    store = PatternStore()
    condition = PatternCondition(
        opportunity_type="increase_budget",
        action_type="increase_budget",
    )
    action = PatternAction(
        action_type="increase_budget",
        expected_impact="amplify",
    )
    perf = PatternPerformance(
        samples=20,
        success_count=17,
        success_rate=0.85,
        avg_reward=0.80,
        avg_confidence=0.90,
        last_seen=datetime(2026, 7, 29, tzinfo=timezone.utc).isoformat(),
    )
    p1 = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["positive"],
        metadata={"source": "test"},
    )
    p1.compute_score()
    store.store(p1)

    condition2 = PatternCondition(
        opportunity_type="adjust_bid",
        action_type="adjust_bid",
    )
    action2 = PatternAction(
        action_type="adjust_bid",
        expected_impact="maintain",
    )
    perf2 = PatternPerformance(
        samples=10,
        success_count=6,
        success_rate=0.60,
        avg_reward=0.55,
        avg_confidence=0.65,
        last_seen=datetime(2026, 7, 25, tzinfo=timezone.utc).isoformat(),
    )
    p2 = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition2,
        action=action2,
        performance=perf2,
        tags=["neutral"],
    )
    p2.compute_score()
    store.store(p2)
    return store


@pytest.fixture
def empty_pattern_store() -> PatternStore:
    """空 PatternStore."""
    return PatternStore()


@pytest.fixture
def pipeline() -> MemoryConsolidationPipeline:
    """默认流水线 (无 pattern_store)."""
    return MemoryConsolidationPipeline()


@pytest.fixture
def pipeline_with_store(pattern_store_with_data) -> MemoryConsolidationPipeline:
    """带 pattern_store 的流水线."""
    return MemoryConsolidationPipeline(pattern_store=pattern_store_with_data)


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — Properties
# ═══════════════════════════════════════════════════════════════


class TestPipelineProperties:
    """流水线属性测试."""

    def test_initial_run_count(self, pipeline):
        """初始 run_count 为 0."""
        assert pipeline.run_count == 0

    def test_initial_last_report(self, pipeline):
        """初始 last_report 为 None."""
        assert pipeline.last_report is None

    def test_run_count_increments(self, pipeline):
        """run_count 递增."""
        # 使用 mock cycle_result
        class MockCycle:
            cycle_number = 1
        pipeline.consolidate(MockCycle())
        assert pipeline.run_count == 1

    def test_last_report_after_consolidate(self, pipeline):
        """consolidate 后 last_report 不为 None."""
        class MockCycle:
            cycle_number = 1
        pipeline.consolidate(MockCycle())
        assert pipeline.last_report is not None


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — consolidate (happy path)
# ═══════════════════════════════════════════════════════════════


class TestPipelineConsolidate:
    """consolidate 主流程测试."""

    def test_consolidate_produces_report(self, pipeline_with_store):
        """consolidate 产生报告."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        assert report is not None
        assert isinstance(report, ConsolidationReport)
        assert report.stage_count == 5

    def test_consolidate_all_stages_present(self, pipeline_with_store):
        """五个阶段全都存在."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        stage_names = [s.stage for s in report.stages]
        assert PipelineStage.EXTRACT in stage_names
        assert PipelineStage.COMPRESS in stage_names
        assert PipelineStage.REINFORCE in stage_names
        assert PipelineStage.DECAY in stage_names
        assert PipelineStage.UPDATE_GRAPH in stage_names

    def test_consolidate_cycle_number(self, pipeline_with_store):
        """传递 cycle_number."""
        class MockCycle:
            cycle_number = 42
        report = pipeline_with_store.consolidate(MockCycle())
        assert report.cycle_number == 42

    def test_consolidate_generates_pipeline_id(self, pipeline_with_store):
        """生成 pipeline_id."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        assert report.pipeline_id != ""
        assert len(report.pipeline_id) == 8

    def test_consolidate_generates_report_id(self, pipeline_with_store):
        """生成 report_id."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        assert report.report_id != ""

    def test_consolidate_stages_have_duration(self, pipeline_with_store):
        """各阶段有耗时."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        for stage in report.stages:
            assert stage.duration_ms >= 0

    def test_consolidate_report_stored(self, pipeline_with_store):
        """报告被存储."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        assert pipeline_with_store.last_report is not None
        assert len(pipeline_with_store.get_reports()) == 1

    def test_consolidate_default_cycle_number(self, pipeline_with_store):
        """无 cycle_number 时使用 run_count."""
        class MockCycle:
            pass
        report = pipeline_with_store.consolidate(MockCycle())
        assert report.cycle_number == 1


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — consolidate_batch
# ═══════════════════════════════════════════════════════════════


class TestPipelineConsolidateBatch:
    """批量 consolidate 测试."""

    def test_batch_empty(self, pipeline_with_store):
        """空列表."""
        reports = pipeline_with_store.consolidate_batch([])
        assert reports == []

    def test_batch_single(self, pipeline_with_store):
        """单个周期."""
        class MockCycle:
            cycle_number = 1
        reports = pipeline_with_store.consolidate_batch([MockCycle()])
        assert len(reports) == 1

    def test_batch_multiple(self, pipeline_with_store):
        """多个周期."""
        class MockCycle:
            def __init__(self, n):
                self.cycle_number = n
        cycles = [MockCycle(1), MockCycle(2), MockCycle(3)]
        reports = pipeline_with_store.consolidate_batch(cycles)
        assert len(reports) == 3
        assert reports[0].cycle_number == 1
        assert reports[1].cycle_number == 2
        assert reports[2].cycle_number == 3

    def test_batch_increments_run_count(self, pipeline_with_store):
        """批量执行递增 run_count."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate_batch([MockCycle(), MockCycle(), MockCycle()])
        assert pipeline_with_store.run_count == 3


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — Reports
# ═══════════════════════════════════════════════════════════════


class TestPipelineReports:
    """报告管理测试."""

    def test_get_reports_default_limit(self, pipeline_with_store):
        """默认 limit=10."""
        class MockCycle:
            cycle_number = 1
        for _ in range(5):
            pipeline_with_store.consolidate(MockCycle())
        assert len(pipeline_with_store.get_reports()) == 5

    def test_get_reports_custom_limit(self, pipeline_with_store):
        """自定义 limit."""
        class MockCycle:
            cycle_number = 1
        for _ in range(10):
            pipeline_with_store.consolidate(MockCycle())
        assert len(pipeline_with_store.get_reports(limit=3)) == 3

    def test_get_reports_zero_limit(self, pipeline_with_store):
        """limit=0 返回全部."""
        class MockCycle:
            cycle_number = 1
        for _ in range(5):
            pipeline_with_store.consolidate(MockCycle())
        assert len(pipeline_with_store.get_reports(limit=0)) == 5

    def test_get_latest_report(self, pipeline_with_store):
        """最新报告."""
        class MockCycle:
            def __init__(self, n):
                self.cycle_number = n
        pipeline_with_store.consolidate(MockCycle(1))
        pipeline_with_store.consolidate(MockCycle(2))
        assert pipeline_with_store.get_latest_report().cycle_number == 2

    def test_get_latest_report_empty(self, pipeline):
        """空流水线返回 None."""
        assert pipeline.get_latest_report() is None


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — Stats
# ═══════════════════════════════════════════════════════════════


class TestPipelineStats:
    """统计方法测试."""

    def test_stats_initial(self, pipeline):
        """初始统计."""
        stats = pipeline.get_stats()
        assert stats["run_count"] == 0
        assert stats["total_runs"] == 0
        assert stats["success_runs"] == 0
        assert stats["failure_runs"] == 0
        assert stats["pipeline_health"] == 1.0

    def test_stats_after_runs(self, pipeline_with_store):
        """运行后统计."""
        class MockCycle:
            cycle_number = 1
        for _ in range(3):
            pipeline_with_store.consolidate(MockCycle())
        stats = pipeline_with_store.get_stats()
        assert stats["run_count"] == 3
        assert stats["total_runs"] == 3

    def test_stats_health_all_success(self, pipeline_with_store):
        """全部成功时 health=1.0."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        stats = pipeline_with_store.get_stats()
        assert stats["pipeline_health"] == 1.0

    def test_stats_accumulates_totals(self, pipeline_with_store):
        """累计统计."""
        class MockCycle:
            cycle_number = 1
        for _ in range(2):
            pipeline_with_store.consolidate(MockCycle())
        stats = pipeline_with_store.get_stats()
        assert stats["total_experiences"] >= 0
        assert stats["total_patterns"] >= 0


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — Reset
# ═══════════════════════════════════════════════════════════════


class TestPipelineReset:
    """重置测试."""

    def test_reset_clears_run_count(self, pipeline_with_store):
        """重置清零 run_count."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        assert pipeline_with_store.run_count == 1
        pipeline_with_store.reset()
        assert pipeline_with_store.run_count == 0

    def test_reset_clears_reports(self, pipeline_with_store):
        """重置清零报告."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        assert len(pipeline_with_store.get_reports()) == 1
        pipeline_with_store.reset()
        assert len(pipeline_with_store.get_reports()) == 0

    def test_reset_clears_last_report(self, pipeline_with_store):
        """重置清零 last_report."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        assert pipeline_with_store.last_report is not None
        pipeline_with_store.reset()
        assert pipeline_with_store.last_report is None

    def test_reset_stats_after_reset(self, pipeline_with_store):
        """重置后统计."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        pipeline_with_store.reset()
        stats = pipeline_with_store.get_stats()
        assert stats["run_count"] == 0
        assert stats["total_runs"] == 0


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — Fail-Safe
# ═══════════════════════════════════════════════════════════════


class TestPipelineFailSafe:
    """Fail-safe 机制测试."""

    def test_no_pattern_store_compression_succeeds(self, pipeline):
        """无 pattern_store 时 extract/compress 仍成功."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        # EXTRACT 和 COMPRESS 不依赖 pattern_store，应成功
        extract_stage = _find_stage(report.stages, PipelineStage.EXTRACT)
        assert extract_stage is not None
        # extract 依赖 extractor 对象，即使没有 pattern_store 也应该成功
        assert extract_stage.success is True

    def test_no_pattern_store_reinforce_fails(self, pipeline):
        """无 pattern_store 时 reinforce 失败."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        reinforce_stage = _find_stage(report.stages, PipelineStage.REINFORCE)
        assert reinforce_stage is not None
        assert reinforce_stage.success is False
        assert reinforce_stage.error is not None

    def test_no_pattern_store_decay_fails(self, pipeline):
        """无 pattern_store 时 decay 失败."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        decay_stage = _find_stage(report.stages, PipelineStage.DECAY)
        assert decay_stage is not None
        assert decay_stage.success is False

    def test_no_pattern_store_graph_fails(self, pipeline):
        """无 pattern_store 时 update_graph 失败."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        graph_stage = _find_stage(report.stages, PipelineStage.UPDATE_GRAPH)
        assert graph_stage is not None
        assert graph_stage.success is False

    def test_reinforce_failure_does_not_block_decay(self, pipeline):
        """reinforce 失败不阻断 decay."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        decay_stage = _find_stage(report.stages, PipelineStage.DECAY)
        # 即使 reinforce 失败，decay 也应该被调用
        assert decay_stage is not None

    def test_stage_failure_preserves_successful_stages(self, pipeline):
        """失败阶段不影响成功阶段的结果."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        extract_stage = _find_stage(report.stages, PipelineStage.EXTRACT)
        assert extract_stage is not None
        assert extract_stage.success is True

    def test_failures_reflected_in_report(self, pipeline):
        """失败反映在报告中."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        assert report.has_failures is True
        assert len(report.failed_stages) == 3  # reinforce, decay, update_graph

    def test_overall_success_false_on_failures(self, pipeline):
        """有失败时 overall_success 为 False."""
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        assert report.overall_success is False


# ═══════════════════════════════════════════════════════════════
# Test: MemoryConsolidationPipeline — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestPipelineEdgeCases:
    """边界情况测试."""

    def test_consolidate_with_empty_pattern_store(self, empty_pattern_store):
        """空 PatternStore."""
        pipeline = MemoryConsolidationPipeline(pattern_store=empty_pattern_store)
        class MockCycle:
            cycle_number = 1
        report = pipeline.consolidate(MockCycle())
        assert report.stage_count == 5
        # 空 store 时 decay 应该成功 (只不过没有 pattern 可衰减)
        decay_stage = _find_stage(report.stages, PipelineStage.DECAY)
        assert decay_stage.success is True
        assert decay_stage.items_processed == 0

    def test_consolidate_multiple_runs_same_pipeline(self, pipeline_with_store):
        """同一流水线多次运行."""
        class MockCycle:
            def __init__(self, n):
                self.cycle_number = n
        for i in range(5):
            report = pipeline_with_store.consolidate(MockCycle(i))
            assert report.stage_count == 5
        assert pipeline_with_store.run_count == 5
        assert len(pipeline_with_store.get_reports()) == 5

    def test_consolidate_all_stages_success_with_store(self, pipeline_with_store):
        """有 store 时所有阶段应成功."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        for stage in report.stages:
            assert stage.success is True, f"Stage {stage.stage} failed: {stage.error}"

    def test_consolidate_summary_in_report(self, pipeline_with_store):
        """报告包含摘要."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        assert report.summary != ""
        assert "Memory Consolidation Pipeline" in report.summary

    def test_consolidate_created_at_in_report(self, pipeline_with_store):
        """报告包含创建时间."""
        class MockCycle:
            cycle_number = 1
        report = pipeline_with_store.consolidate(MockCycle())
        assert report.created_at != ""

    def test_batch_large(self, pipeline_with_store):
        """大批量."""
        class MockCycle:
            def __init__(self, n):
                self.cycle_number = n
        cycles = [MockCycle(i) for i in range(50)]
        reports = pipeline_with_store.consolidate_batch(cycles)
        assert len(reports) == 50

    def test_stats_returns_dict(self, pipeline_with_store):
        """get_stats 返回字典."""
        class MockCycle:
            cycle_number = 1
        pipeline_with_store.consolidate(MockCycle())
        stats = pipeline_with_store.get_stats()
        assert isinstance(stats, dict)
        assert "pipeline_health" in stats

    def test_pipeline_reports_are_ordered(self, pipeline_with_store):
        """报告按顺序存储."""
        class MockCycle:
            def __init__(self, n):
                self.cycle_number = n
        pipeline_with_store.consolidate(MockCycle(1))
        pipeline_with_store.consolidate(MockCycle(2))
        pipeline_with_store.consolidate(MockCycle(3))
        reports = pipeline_with_store.get_reports()
        assert reports[0].cycle_number == 1
        assert reports[1].cycle_number == 2
        assert reports[2].cycle_number == 3


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _find_stage(stages: list[StageResult], stage: PipelineStage) -> StageResult | None:
    """查找指定阶段的结果."""
    for s in stages:
        if s.stage == stage:
            return s
    return None