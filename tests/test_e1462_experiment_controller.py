"""E14.6.2 Evolution Experiment Controller — 集成测试.

验证 ExperimentController 的进化实验管理能力:
  - 数据模型: ExperimentGroup / ExperimentConfig / Experiment / ExperimentResult / ExperimentReport (25 tests)
  - 枚举: ExperimentStatus / GroupType / PlatformType (10 tests)
  - 实验创建: create_experiment / create_experiment_from_execution / create_experiment_batch (15 tests)
  - 状态管理: start / pause / resume / complete / fail / invalid transitions (15 tests)
  - 结果记录: record_result / record_results_batch (10 tests)
  - 适应度计算: compute_fitness / winner determination (15 tests)
  - 平台部署: deploy_to_platform / collect_platform_results (10 tests)
  - 查询与统计 (10 tests)
  - 回归 (E14.5.x + E14.6.1) (10 tests)

总计: 120 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.experiment_controller import (
    ExperimentController,
    Experiment,
    ExperimentGroup,
    ExperimentConfig,
    ExperimentResult,
    ExperimentReport,
    ExperimentStatus,
    GroupType,
    PlatformType,
    VALID_TRANSITIONS,
    create_experiment_controller,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.decision_executor import (
    DecisionExecutor,
    EvolutionAction,
    ExecutionResult,
    ActionType,
    ActionStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_planner import (
    EvolutionPlan,
    EvolutionGoal,
    GeneMutationPlan,
)
from market_ops.e11.evolution.fitness_schema import FitnessScore, FitnessMetric, FitnessDirection
from market_ops.e11.evolution.population_manager import PopulationManager


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def controller():
    """创建默认 ExperimentController."""
    return ExperimentController()


@pytest.fixture
def experiment(controller):
    """创建测试用 Experiment."""
    return controller.create_experiment(
        name="Hook Mutation Test #001",
        hypothesis="rescue hook 提升 CTR +15%",
        control_genomes=["genome_control_001"],
        variant_genomes=["genome_v1", "genome_v2", "genome_v3"],
        config=ExperimentConfig(budget_total=500, duration_days=7),
        tags=["hook", "mutation"],
    )


@pytest.fixture
def running_experiment(controller, experiment):
    """启动后的实验."""
    controller.start_experiment(experiment.experiment_id)
    return experiment


@pytest.fixture
def experiment_with_results(controller, running_experiment):
    """已有结果的实验."""
    exp_id = running_experiment.experiment_id
    controller.record_result(exp_id, "genome_control_001", {
        "ctr": 0.025, "cvr": 0.04, "roas": 0.35, "cpi": 2.5, "payer_rate": 0.04,
    }, sample_size=5000)
    controller.record_result(exp_id, "genome_v1", {
        "ctr": 0.032, "cvr": 0.05, "roas": 0.48, "cpi": 2.2, "payer_rate": 0.05,
    }, sample_size=5000)
    controller.record_result(exp_id, "genome_v2", {
        "ctr": 0.028, "cvr": 0.043, "roas": 0.38, "cpi": 2.4, "payer_rate": 0.042,
    }, sample_size=5000)
    controller.record_result(exp_id, "genome_v3", {
        "ctr": 0.035, "cvr": 0.06, "roas": 0.55, "cpi": 2.0, "payer_rate": 0.06,
    }, sample_size=5000)
    return running_experiment


@pytest.fixture
def execution_result():
    """创建测试用 ExecutionResult."""
    return ExecutionResult(
        action_id="action_001",
        status=ActionStatus.SUCCESS,
        genome_ids=["genome_a", "genome_b", "genome_c", "genome_d"],
        population_id="pop_test",
    )


# ═══════════════════════════════════════════════════════════
# 1. 模型 Tests — ExperimentGroup (5 tests)
# ═══════════════════════════════════════════════════════════

class TestExperimentGroup:
    """ExperimentGroup 模型测试."""

    def test_create_control_group(self):
        """创建对照组."""
        g = ExperimentGroup(group_type=GroupType.CONTROL, genome_ids=["g1", "g2"])
        assert g.group_type == GroupType.CONTROL
        assert g.genome_ids == ["g1", "g2"]
        assert g.genome_count == 2

    def test_create_variant_group(self):
        """创建实验组."""
        g = ExperimentGroup(group_type=GroupType.VARIANT, genome_ids=["g3"], budget=100.0)
        assert g.group_type == GroupType.VARIANT
        assert g.genome_count == 1
        assert g.budget == 100.0

    def test_empty_group(self):
        """空组."""
        g = ExperimentGroup()
        assert g.genome_count == 0
        assert g.budget == 0.0

    def test_to_dict(self):
        """序列化."""
        g = ExperimentGroup(
            group_type=GroupType.CONTROL,
            genome_ids=["g1"],
            budget=100.0,
            expected_impact="baseline",
        )
        d = g.to_dict()
        assert d["group_type"] == "control"
        assert d["genome_ids"] == ["g1"]
        assert d["budget"] == 100.0
        assert d["genome_count"] == 1

    def test_from_dict(self):
        """反序列化."""
        data = {"group_type": "variant", "genome_ids": ["g1", "g2"], "budget": 50.0}
        g = ExperimentGroup.from_dict(data)
        assert g.group_type == GroupType.VARIANT
        assert g.genome_ids == ["g1", "g2"]
        assert g.budget == 50.0


# ═══════════════════════════════════════════════════════════
# 2. 模型 Tests — ExperimentConfig (5 tests)
# ═══════════════════════════════════════════════════════════

class TestExperimentConfig:
    """ExperimentConfig 模型测试."""

    def test_default_config(self):
        """默认配置."""
        c = ExperimentConfig()
        assert c.budget_total == 500.0
        assert c.duration_days == 7
        assert c.min_sample_size == 5000
        assert c.platform == PlatformType.INTERNAL

    def test_custom_config(self):
        """自定义配置."""
        c = ExperimentConfig(
            budget_total=1000,
            duration_days=14,
            platform=PlatformType.META_ADS,
        )
        assert c.budget_total == 1000
        assert c.duration_days == 14
        assert c.platform == PlatformType.META_ADS

    def test_to_dict(self):
        """序列化."""
        c = ExperimentConfig(budget_total=800, platform=PlatformType.GOOGLE_ADS)
        d = c.to_dict()
        assert d["budget_total"] == 800
        assert d["platform"] == "google_ads"

    def test_from_dict(self):
        """反序列化."""
        data = {"budget_total": 600, "duration_days": 10, "platform": "meta_ads"}
        c = ExperimentConfig.from_dict(data)
        assert c.budget_total == 600
        assert c.platform == PlatformType.META_ADS

    def test_auto_start_default(self):
        """默认不自动启动."""
        c = ExperimentConfig()
        assert c.auto_start is False
        assert c.auto_complete is False


# ═══════════════════════════════════════════════════════════
# 3. 模型 Tests — Experiment (5 tests)
# ═══════════════════════════════════════════════════════════

class TestExperimentModel:
    """Experiment 模型测试."""

    def test_create_experiment_default(self):
        """默认创建."""
        exp = Experiment(name="Test")
        assert exp.name == "Test"
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.total_genomes == 0

    def test_total_genomes(self):
        """计算总基因组数."""
        exp = Experiment(
            name="Test",
            control_group=ExperimentGroup(
                group_type=GroupType.CONTROL,
                genome_ids=["g1", "g2"],
            ),
            variant_groups=[
                ExperimentGroup(genome_ids=["g3"]),
                ExperimentGroup(genome_ids=["g4", "g5"]),
            ],
        )
        assert exp.total_genomes == 5

    def test_all_genome_ids(self):
        """获取所有基因组 ID."""
        exp = Experiment(
            control_group=ExperimentGroup(
                group_type=GroupType.CONTROL,
                genome_ids=["c1"],
            ),
            variant_groups=[
                ExperimentGroup(genome_ids=["v1"]),
                ExperimentGroup(genome_ids=["v2"]),
            ],
        )
        ids = exp.all_genome_ids
        assert "c1" in ids
        assert "v1" in ids
        assert "v2" in ids
        assert len(ids) == 3

    def test_is_active_terminal(self):
        """活跃/终端状态."""
        exp = Experiment(name="Test")
        assert not exp.is_active
        assert not exp.is_terminal
        exp.status = ExperimentStatus.RUNNING
        assert exp.is_active
        assert not exp.is_terminal
        exp.status = ExperimentStatus.COMPLETED
        assert not exp.is_active
        assert exp.is_terminal

    def test_total_budget(self):
        """总预算计算."""
        exp = Experiment(
            control_group=ExperimentGroup(budget=100),
            variant_groups=[ExperimentGroup(budget=100), ExperimentGroup(budget=100)],
            config=ExperimentConfig(budget_total=500),
        )
        assert exp.total_budget == 300


# ═══════════════════════════════════════════════════════════
# 4. 模型 Tests — ExperimentResult (5 tests)
# ═══════════════════════════════════════════════════════════

class TestExperimentResult:
    """ExperimentResult 模型测试."""

    def test_create_result(self):
        """创建结果."""
        r = ExperimentResult(
            experiment_id="exp_001",
            genome_id="genome_001",
            group_type=GroupType.VARIANT,
            metrics={"ctr": 0.032, "roas": 0.48},
        )
        assert r.genome_id == "genome_001"
        assert r.ctr == 0.032
        assert r.roas == 0.48

    def test_property_accessors(self):
        """属性访问器."""
        r = ExperimentResult(metrics={
            "ctr": 0.03, "cvr": 0.05, "roas": 0.5,
            "cpi": 2.0, "d1_retention": 0.4, "d7_retention": 0.2,
            "d30_ltv": 5.0, "payer_rate": 0.05,
        })
        assert r.ctr == 0.03
        assert r.cvr == 0.05
        assert r.roas == 0.5
        assert r.cpi == 2.0
        assert r.d1_retention == 0.4
        assert r.d7_retention == 0.2
        assert r.d30_ltv == 5.0
        assert r.payer_rate == 0.05

    def test_missing_metrics_default_zero(self):
        """缺失指标默认 0."""
        r = ExperimentResult()
        assert r.ctr == 0.0
        assert r.roas == 0.0
        assert r.payer_rate == 0.0

    def test_score_without_fitness(self):
        """无 fitness 时 score 为 0."""
        r = ExperimentResult()
        assert r.score == 0.0

    def test_score_with_fitness(self):
        """有 fitness 时正确返回 score."""
        r = ExperimentResult(
            genome_id="g1",
            fitness_score=FitnessScore(
                genome_id="g1",
                metrics=[FitnessMetric(name="roas", value=0.5, weight=1.0)],
            ),
        )
        assert r.score > 0.0


# ═══════════════════════════════════════════════════════════
# 5. 模型 Tests — ExperimentReport (5 tests)
# ═══════════════════════════════════════════════════════════

class TestExperimentReport:
    """ExperimentReport 模型测试."""

    def test_create_report(self):
        """创建报告."""
        r = ExperimentReport(
            experiment_id="exp_001",
            experiment_name="Test",
            winner_genome_id="genome_v1",
            winner_score=0.75,
        )
        assert r.has_winner is True
        assert r.winner_genome_id == "genome_v1"

    def test_no_winner(self):
        """无 Winner."""
        r = ExperimentReport()
        assert r.has_winner is False
        assert r.winner_genome_id == ""

    def test_variant_results_filter(self):
        """过滤 Variant 结果."""
        r = ExperimentReport(results=[
            ExperimentResult(genome_id="c1", group_type=GroupType.CONTROL),
            ExperimentResult(genome_id="v1", group_type=GroupType.VARIANT),
            ExperimentResult(genome_id="v2", group_type=GroupType.VARIANT),
        ])
        assert len(r.variant_results) == 2
        assert len(r.control_results) == 1

    def test_to_dict(self):
        """序列化."""
        r = ExperimentReport(
            experiment_id="exp_001",
            experiment_name="Test",
            total_results=3,
            winner_genome_id="g1",
            winner_score=0.8,
            winner_lift=0.15,
            summary="实验成功",
        )
        d = r.to_dict()
        assert d["experiment_id"] == "exp_001"
        assert d["has_winner"] is True
        assert d["winner_lift"] == 0.15

    def test_empty_report(self):
        """空报告."""
        r = ExperimentReport()
        assert r.total_results == 0
        assert r.variant_results == []
        assert r.control_results == []
        assert r.summary == ""


# ═══════════════════════════════════════════════════════════
# 6. 枚举 Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestExperimentStatus:
    """ExperimentStatus 枚举测试."""

    def test_all_statuses(self):
        """所有状态值."""
        assert ExperimentStatus.DRAFT.value == "draft"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.PAUSED.value == "paused"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.FAILED.value == "failed"

    def test_status_count(self):
        """共 5 个状态."""
        assert len(ExperimentStatus) == 5


class TestGroupType:
    """GroupType 枚举测试."""

    def test_group_types(self):
        assert GroupType.CONTROL.value == "control"
        assert GroupType.VARIANT.value == "variant"


class TestPlatformType:
    """PlatformType 枚举测试."""

    def test_platform_types(self):
        assert PlatformType.META_ADS.value == "meta_ads"
        assert PlatformType.GOOGLE_ADS.value == "google_ads"
        assert PlatformType.TIKTOK_ADS.value == "tiktok_ads"
        assert PlatformType.INTERNAL.value == "internal"


class TestValidTransitions:
    """状态转换规则测试."""

    def test_draft_transitions(self):
        """DRAFT 可转换到 RUNNING / FAILED."""
        t = VALID_TRANSITIONS[ExperimentStatus.DRAFT]
        assert ExperimentStatus.RUNNING in t
        assert ExperimentStatus.FAILED in t
        assert ExperimentStatus.COMPLETED not in t

    def test_running_transitions(self):
        """RUNNING 可转换到 PAUSED / COMPLETED / FAILED."""
        t = VALID_TRANSITIONS[ExperimentStatus.RUNNING]
        assert ExperimentStatus.PAUSED in t
        assert ExperimentStatus.COMPLETED in t
        assert ExperimentStatus.FAILED in t
        assert ExperimentStatus.DRAFT not in t

    def test_paused_transitions(self):
        """PAUSED 可转换到 RUNNING / COMPLETED / FAILED."""
        t = VALID_TRANSITIONS[ExperimentStatus.PAUSED]
        assert ExperimentStatus.RUNNING in t
        assert ExperimentStatus.COMPLETED in t
        assert ExperimentStatus.FAILED in t

    def test_completed_no_transitions(self):
        """COMPLETED 不可再转换."""
        t = VALID_TRANSITIONS[ExperimentStatus.COMPLETED]
        assert len(t) == 0

    def test_failed_no_transitions(self):
        """FAILED 不可再转换."""
        t = VALID_TRANSITIONS[ExperimentStatus.FAILED]
        assert len(t) == 0


# ═══════════════════════════════════════════════════════════
# 7. 实验创建 Tests (15 tests)
# ═══════════════════════════════════════════════════════════

class TestCreateExperiment:
    """实验创建测试."""

    def test_create_basic_experiment(self, controller):
        """基本实验创建."""
        exp = controller.create_experiment(
            name="Basic Test",
            control_genomes=["ctrl_1"],
            variant_genomes=["v1", "v2"],
        )
        assert exp.name == "Basic Test"
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.control_group.genome_ids == ["ctrl_1"]
        assert len(exp.variant_groups) == 2

    def test_create_experiment_with_hypothesis(self, controller):
        """带假设的实验."""
        exp = controller.create_experiment(
            name="Hypothesis Test",
            hypothesis="CTR +20%",
            control_genomes=["c1"],
            variant_genomes=["v1"],
        )
        assert exp.hypothesis == "CTR +20%"

    def test_create_experiment_with_tags(self, controller):
        """带标签的实验."""
        exp = controller.create_experiment(
            name="Tagged",
            control_genomes=["c1"],
            variant_genomes=["v1"],
            tags=["hook", "visual"],
        )
        assert "hook" in exp.tags
        assert "visual" in exp.tags

    def test_create_experiment_with_config(self, controller):
        """自定义配置."""
        cfg = ExperimentConfig(budget_total=1000, duration_days=14)
        exp = controller.create_experiment(
            name="Config Test",
            control_genomes=["c1"],
            variant_genomes=["v1"],
            config=cfg,
        )
        assert exp.config.budget_total == 1000
        assert exp.config.duration_days == 14

    def test_auto_control_from_variants(self, controller):
        """无 Control 时自动从 Variant 取第一个."""
        exp = controller.create_experiment(
            name="Auto Control",
            variant_genomes=["v1", "v2", "v3"],
        )
        assert exp.control_group.genome_ids == ["v1"]
        assert len(exp.variant_groups) == 2

    def test_empty_genomes_raises(self, controller):
        """无基因组时抛异常."""
        with pytest.raises(ValueError, match="至少需要一组基因组"):
            controller.create_experiment(name="Empty")

    def test_create_experiment_from_execution(self, controller, execution_result):
        """从 ExecutionResult 创建实验."""
        exp = controller.create_experiment_from_execution(
            name="From Exec",
            execution_result=execution_result,
            hypothesis="Test hypothesis",
        )
        assert exp.control_group.genome_ids == ["genome_a"]
        assert len(exp.variant_groups) == 3
        assert exp.population_id == "pop_test"

    def test_create_experiment_from_execution_custom_control(self, controller, execution_result):
        """指定对照组."""
        exp = controller.create_experiment_from_execution(
            name="Custom Control",
            execution_result=execution_result,
            control_genome_ids=["genome_c"],
        )
        assert exp.control_group.genome_ids == ["genome_c"]
        # genome_a, genome_b, genome_d 为 variant
        all_variant_ids = []
        for g in exp.variant_groups:
            all_variant_ids.extend(g.genome_ids)
        assert "genome_c" not in all_variant_ids

    def test_create_experiment_batch(self, controller):
        """批量创建实验."""
        results = [
            ExecutionResult(genome_ids=["g1", "g2"], population_id="pop_1"),
            ExecutionResult(genome_ids=["g3", "g4"], population_id="pop_2"),
        ]
        actions = [
            EvolutionAction(action_type=ActionType.CREATE_VARIANTS),
            EvolutionAction(action_type=ActionType.MUTATE_GENE),
        ]
        exp = controller.create_experiment_batch(
            name="Batch Test",
            actions=actions,
            execution_results=results,
            hypothesis="Batch hypothesis",
        )
        assert exp.control_group.genome_ids == ["g1"]
        assert len(exp.variant_groups) == 3

    def test_batch_empty_genomes_raises(self, controller):
        """批量创建无基因组抛异常."""
        with pytest.raises(ValueError, match="无基因组"):
            controller.create_experiment_batch(
                name="Empty Batch",
                actions=[],
                execution_results=[ExecutionResult(genome_ids=[])],
            )

    def test_experiment_stored_in_controller(self, controller, experiment):
        """实验存储在 controller 中."""
        retrieved = controller.get_experiment(experiment.experiment_id)
        assert retrieved is not None
        assert retrieved.name == "Hook Mutation Test #001"

    def test_experiment_has_plan_id(self, controller):
        """实验关联 plan_id."""
        exp = controller.create_experiment(
            name="Plan Linked",
            control_genomes=["c1"],
            variant_genomes=["v1"],
            plan_id="plan_001",
        )
        assert exp.plan_id == "plan_001"

    def test_experiment_has_population_id(self, controller):
        """实验关联 population_id."""
        exp = controller.create_experiment(
            name="Pop Linked",
            control_genomes=["c1"],
            variant_genomes=["v1"],
            population_id="pop_001",
        )
        assert exp.population_id == "pop_001"

    def test_experiment_timestamps(self, experiment):
        """实验有时间戳."""
        assert experiment.created_at != ""
        assert experiment.started_at == ""
        assert experiment.completed_at == ""

    def test_group_budget_calculation(self, controller):
        """组预算计算."""
        exp = controller.create_experiment(
            name="Budget Test",
            control_genomes=["c1"],
            variant_genomes=["v1", "v2", "v3"],
            config=ExperimentConfig(budget_total=400, budget_per_group=0),
        )
        # 4 groups total (1 control + 3 variants), 400/4 = 100 each
        assert exp.control_group.budget == 100.0
        for g in exp.variant_groups:
            assert g.budget == 100.0


# ═══════════════════════════════════════════════════════════
# 8. 状态管理 Tests (15 tests)
# ═══════════════════════════════════════════════════════════

class TestStatusManagement:
    """状态管理测试."""

    def test_start_experiment(self, controller, experiment):
        """启动实验 DRAFT → RUNNING."""
        exp = controller.start_experiment(experiment.experiment_id)
        assert exp.status == ExperimentStatus.RUNNING
        assert exp.started_at != ""

    def test_pause_experiment(self, controller, running_experiment):
        """暂停实验 RUNNING → PAUSED."""
        exp = controller.pause_experiment(running_experiment.experiment_id)
        assert exp.status == ExperimentStatus.PAUSED

    def test_resume_experiment(self, controller, running_experiment):
        """恢复实验 PAUSED → RUNNING."""
        controller.pause_experiment(running_experiment.experiment_id)
        exp = controller.resume_experiment(running_experiment.experiment_id)
        assert exp.status == ExperimentStatus.RUNNING

    def test_complete_experiment(self, controller, running_experiment):
        """完成实验 RUNNING → COMPLETED."""
        exp = controller.complete_experiment(running_experiment.experiment_id)
        assert exp.status == ExperimentStatus.COMPLETED
        assert exp.completed_at != ""

    def test_complete_from_paused(self, controller, running_experiment):
        """从 PAUSED 完成 PAUSED → COMPLETED."""
        controller.pause_experiment(running_experiment.experiment_id)
        exp = controller.complete_experiment(running_experiment.experiment_id)
        assert exp.status == ExperimentStatus.COMPLETED

    def test_fail_experiment(self, controller, running_experiment):
        """失败实验 RUNNING → FAILED."""
        exp = controller.fail_experiment(running_experiment.experiment_id, "预算耗尽")
        assert exp.status == ExperimentStatus.FAILED
        assert exp.metadata["failure_reason"] == "预算耗尽"

    def test_fail_from_draft(self, controller, experiment):
        """从 DRAFT 失败."""
        exp = controller.fail_experiment(experiment.experiment_id, "配置错误")
        assert exp.status == ExperimentStatus.FAILED

    def test_invalid_transition_draft_to_complete(self, controller, experiment):
        """DRAFT → COMPLETED 非法."""
        with pytest.raises(ValueError, match="无效状态转换"):
            controller.complete_experiment(experiment.experiment_id)

    def test_invalid_transition_completed_to_running(self, controller, running_experiment):
        """COMPLETED → RUNNING 非法."""
        controller.complete_experiment(running_experiment.experiment_id)
        with pytest.raises(ValueError, match="无效状态转换"):
            controller.start_experiment(running_experiment.experiment_id)

    def test_invalid_transition_failed_to_running(self, controller, running_experiment):
        """FAILED → RUNNING 非法."""
        controller.fail_experiment(running_experiment.experiment_id)
        with pytest.raises(ValueError, match="无效状态转换"):
            controller.start_experiment(running_experiment.experiment_id)

    def test_start_already_running(self, controller, running_experiment):
        """RUNNING → RUNNING 非法."""
        with pytest.raises(ValueError, match="无效状态转换"):
            controller.start_experiment(running_experiment.experiment_id)

    def test_pause_not_running(self, controller, experiment):
        """DRAFT → PAUSED 非法."""
        with pytest.raises(ValueError, match="无效状态转换"):
            controller.pause_experiment(experiment.experiment_id)

    def test_nonexistent_experiment(self, controller):
        """不存在的实验."""
        with pytest.raises(ValueError, match="不存在"):
            controller.start_experiment("nonexistent")

    def test_complete_sets_timestamp(self, controller, running_experiment):
        """完成实验设置时间戳."""
        assert running_experiment.completed_at == ""
        controller.complete_experiment(running_experiment.experiment_id)
        assert running_experiment.completed_at != ""

    def test_fail_sets_timestamp(self, controller, running_experiment):
        """失败实验设置时间戳."""
        controller.fail_experiment(running_experiment.experiment_id)
        assert running_experiment.completed_at != ""


# ═══════════════════════════════════════════════════════════
# 9. 结果记录 Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRecordResult:
    """结果记录测试."""

    def test_record_single_result(self, controller, running_experiment):
        """记录单个结果."""
        exp_id = running_experiment.experiment_id
        r = controller.record_result(exp_id, "genome_v1", {"ctr": 0.032, "roas": 0.48})
        assert r.genome_id == "genome_v1"
        assert r.ctr == 0.032
        assert r.group_type == GroupType.VARIANT

    def test_record_control_result(self, controller, running_experiment):
        """记录对照组结果."""
        exp_id = running_experiment.experiment_id
        r = controller.record_result(exp_id, "genome_control_001", {"ctr": 0.025})
        assert r.group_type == GroupType.CONTROL

    def test_record_invalid_genome_raises(self, controller, running_experiment):
        """记录不在实验中的基因组抛异常."""
        with pytest.raises(ValueError, match="不在实验"):
            controller.record_result(running_experiment.experiment_id, "genome_unknown", {})

    def test_record_with_sample_size(self, controller, running_experiment):
        """记录带样本量."""
        r = controller.record_result(
            running_experiment.experiment_id,
            "genome_v1",
            {"ctr": 0.03},
            sample_size=10000,
        )
        assert r.sample_size == 10000

    def test_record_results_batch(self, controller, running_experiment):
        """批量记录结果."""
        exp_id = running_experiment.experiment_id
        results = controller.record_results_batch(exp_id, {
            "genome_v1": {"ctr": 0.032, "roas": 0.48},
            "genome_v2": {"ctr": 0.028, "roas": 0.38},
            "genome_control_001": {"ctr": 0.025, "roas": 0.35},
        })
        assert len(results) == 3

    def test_get_results(self, controller, experiment_with_results):
        """获取实验结果."""
        results = controller.get_results(experiment_with_results.experiment_id)
        assert len(results) == 4

    def test_get_genome_result(self, controller, experiment_with_results):
        """获取特定基因组结果."""
        r = controller.get_genome_result(
            experiment_with_results.experiment_id,
            "genome_v1",
        )
        assert r is not None
        assert r.ctr == 0.032

    def test_get_genome_result_not_found(self, controller, experiment_with_results):
        """获取不存在的基因组结果."""
        r = controller.get_genome_result(
            experiment_with_results.experiment_id,
            "genome_nonexistent",
        )
        assert r is None

    def test_duplicate_result_overwrites(self, controller, running_experiment):
        """重复记录同一基因组."""
        exp_id = running_experiment.experiment_id
        controller.record_result(exp_id, "genome_v1", {"ctr": 0.03})
        controller.record_result(exp_id, "genome_v1", {"ctr": 0.04})
        # 会追加两条记录
        results = controller.get_results(exp_id)
        v1_results = [r for r in results if r.genome_id == "genome_v1"]
        assert len(v1_results) == 2

    def test_result_has_timestamps(self, controller, running_experiment):
        """结果有时间戳."""
        r = controller.record_result(running_experiment.experiment_id, "genome_v1", {})
        assert r.created_at != ""


# ═══════════════════════════════════════════════════════════
# 10. 适应度计算 Tests (15 tests)
# ═══════════════════════════════════════════════════════════

class TestComputeFitness:
    """适应度计算测试."""

    def test_compute_fitness_basic(self, controller, experiment_with_results):
        """基本适应度计算."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        assert report.total_results == 4
        assert report.has_winner
        assert report.winner_genome_id != ""

    def test_winner_is_highest_score(self, controller, experiment_with_results):
        """Winner 是最高分基因组."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        # genome_v3 has roas=0.55, ctr=0.035, cvr=0.06, payer_rate=0.06 → highest
        assert report.winner_genome_id == "genome_v3"
        assert report.winner_score > 0

    def test_winner_lift_calculation(self, controller, experiment_with_results):
        """Winner lift 计算."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        # winner (v3) vs control avg
        assert report.winner_lift > 0

    def test_compute_fitness_empty_results(self, controller, running_experiment):
        """无结果时计算适应度."""
        report = controller.compute_fitness(running_experiment.experiment_id)
        assert report.total_results == 0
        assert not report.has_winner

    def test_fitness_score_assigned(self, controller, experiment_with_results):
        """适应度评分被赋值."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        for r in report.results:
            assert r.fitness_score is not None
            assert r.score > 0

    def test_custom_weights(self, controller, experiment_with_results):
        """自定义权重."""
        custom_w = {"roas": 0.6, "ctr": 0.1, "cvr": 0.1, "payer_rate": 0.2}
        report = controller.compute_fitness(
            experiment_with_results.experiment_id,
            weights=custom_w,
        )
        assert report.has_winner

    def test_report_stored(self, controller, experiment_with_results):
        """报告被存储."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        stored = controller.get_report(experiment_with_results.experiment_id)
        assert stored is not None
        assert stored.report_id == report.report_id

    def test_recommendations_generated(self, controller, experiment_with_results):
        """生成进化建议."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        assert len(report.recommendations) > 0

    def test_recommendations_amplify_for_high_lift(self, controller):
        """高 lift 时建议 AMPLIFY."""
        exp = controller.create_experiment(
            name="High Lift",
            control_genomes=["c1"],
            variant_genomes=["v1"],
        )
        controller.start_experiment(exp.experiment_id)
        controller.record_result(exp.experiment_id, "c1", {
            "ctr": 0.02, "roas": 0.3, "cvr": 0.03, "payer_rate": 0.03,
        })
        controller.record_result(exp.experiment_id, "v1", {
            "ctr": 0.04, "roas": 0.6, "cvr": 0.06, "payer_rate": 0.06,
        })
        report = controller.compute_fitness(exp.experiment_id)
        assert any("AMPLIFY" in rec for rec in report.recommendations)

    def test_recommendations_warning_high_ctr_low_roas(self, controller):
        """高 CTR 低 ROAS 警告."""
        exp = controller.create_experiment(
            name="CTR Only",
            control_genomes=["c1"],
            variant_genomes=["v1"],
        )
        controller.start_experiment(exp.experiment_id)
        controller.record_result(exp.experiment_id, "c1", {
            "ctr": 0.02, "roas": 0.3, "cvr": 0.03, "payer_rate": 0.03,
        })
        controller.record_result(exp.experiment_id, "v1", {
            "ctr": 0.05, "roas": 0.2, "cvr": 0.03, "payer_rate": 0.02,
        })
        report = controller.compute_fitness(exp.experiment_id)
        assert any("WARNING" in rec for rec in report.recommendations)

    def test_recommendations_insight_high_payer(self, controller):
        """高付费率洞察."""
        exp = controller.create_experiment(
            name="High Payer",
            control_genomes=["c1"],
            variant_genomes=["v1"],
        )
        controller.start_experiment(exp.experiment_id)
        controller.record_result(exp.experiment_id, "c1", {
            "ctr": 0.02, "roas": 0.3, "cvr": 0.03, "payer_rate": 0.03,
        })
        controller.record_result(exp.experiment_id, "v1", {
            "ctr": 0.03, "roas": 0.5, "cvr": 0.05, "payer_rate": 0.08,
        })
        report = controller.compute_fitness(exp.experiment_id)
        assert any("INSIGHT" in rec for rec in report.recommendations)

    def test_winner_is_marked(self, controller, experiment_with_results):
        """Winner 被标记 is_winner=True."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        winner = [r for r in report.results if r.is_winner]
        assert len(winner) == 1
        assert winner[0].genome_id == report.winner_genome_id

    def test_only_one_winner(self, controller, experiment_with_results):
        """只有一个 Winner."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        winner_count = sum(1 for r in report.results if r.is_winner)
        assert winner_count == 1

    def test_report_summary(self, controller, experiment_with_results):
        """报告摘要."""
        report = controller.compute_fitness(experiment_with_results.experiment_id)
        assert "Winner" in report.summary
        assert "genome_v3" in report.summary

    def test_fitness_with_cpi(self, controller):
        """含 CPI 的适应度计算."""
        exp = controller.create_experiment(
            name="CPI Test",
            control_genomes=["c1"],
            variant_genomes=["v1"],
        )
        controller.start_experiment(exp.experiment_id)
        controller.record_result(exp.experiment_id, "c1", {
            "ctr": 0.02, "roas": 0.3, "cvr": 0.03, "payer_rate": 0.03, "cpi": 5.0,
        })
        controller.record_result(exp.experiment_id, "v1", {
            "ctr": 0.03, "roas": 0.5, "cvr": 0.05, "payer_rate": 0.05, "cpi": 2.0,
        })
        report = controller.compute_fitness(exp.experiment_id)
        assert report.has_winner
        # v1 should win because lower CPI = higher fitness
        assert report.winner_genome_id == "v1"


# ═══════════════════════════════════════════════════════════
# 11. 平台部署 Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestPlatformDeployment:
    """平台部署测试."""

    def test_deploy_to_platform(self, controller, experiment):
        """部署到平台."""
        exp = controller.deploy_to_platform(experiment.experiment_id)
        assert len(exp.campaign_ids) > 0
        assert "platform" in exp.metadata
        assert "deployed_at" in exp.metadata

    def test_deploy_generates_campaign_ids(self, controller, experiment):
        """部署生成 campaign_id."""
        exp = controller.deploy_to_platform(experiment.experiment_id)
        # 4 genomes = 4 campaign_ids
        assert len(exp.campaign_ids) == 4

    def test_deploy_specific_platform(self, controller, experiment):
        """指定平台部署."""
        exp = controller.deploy_to_platform(
            experiment.experiment_id,
            platform=PlatformType.META_ADS,
        )
        assert exp.metadata["platform"] == "meta_ads"
        for cid in exp.campaign_ids:
            assert cid.startswith("meta_ads::")

    def test_collect_platform_results(self, controller, experiment):
        """收集平台结果."""
        exp = controller.deploy_to_platform(experiment.experiment_id)
        platform_data = {}
        for cid in exp.campaign_ids:
            platform_data[cid] = {"ctr": 0.03, "roas": 0.4}

        results = controller.collect_platform_results(
            experiment.experiment_id,
            platform_data,
        )
        assert len(results) == 4

    def test_collect_partial_results(self, controller, experiment):
        """部分收集结果."""
        exp = controller.deploy_to_platform(experiment.experiment_id)
        # 只收集前两个 campaign
        platform_data = {}
        for cid in exp.campaign_ids[:2]:
            platform_data[cid] = {"ctr": 0.03}

        results = controller.collect_platform_results(
            experiment.experiment_id,
            platform_data,
        )
        assert len(results) == 2

    def test_deploy_updates_metadata(self, controller, experiment):
        """部署更新元数据."""
        exp = controller.deploy_to_platform(
            experiment.experiment_id,
            platform=PlatformType.GOOGLE_ADS,
        )
        assert exp.metadata["platform"] == "google_ads"
        assert "deployed_at" in exp.metadata

    def test_deploy_twice_overwrites(self, controller, experiment):
        """两次部署覆盖."""
        controller.deploy_to_platform(experiment.experiment_id, PlatformType.META_ADS)
        exp = controller.deploy_to_platform(experiment.experiment_id, PlatformType.GOOGLE_ADS)
        assert exp.metadata["platform"] == "google_ads"

    def test_collect_invalid_experiment(self, controller):
        """收集不存在的实验结果."""
        with pytest.raises(ValueError, match="不存在"):
            controller.collect_platform_results("nonexistent", {})

    def test_collect_without_deploy(self, controller, experiment):
        """未部署时收集结果 (无 campaign_ids)."""
        results = controller.collect_platform_results(experiment.experiment_id, {})
        assert len(results) == 0

    def test_deploy_campaign_id_format(self, controller, experiment):
        """Campaign ID 格式."""
        exp = controller.deploy_to_platform(experiment.experiment_id, PlatformType.META_ADS)
        for cid in exp.campaign_ids:
            # format: meta_ads::genome_id::suffix
            assert "::" in cid
            assert cid.startswith("meta_ads::")


# ═══════════════════════════════════════════════════════════
# 12. 查询与统计 Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestQueryAndStats:
    """查询与统计测试."""

    def test_get_experiment(self, controller, experiment):
        """获取实验."""
        exp = controller.get_experiment(experiment.experiment_id)
        assert exp is not None
        assert exp.experiment_id == experiment.experiment_id

    def test_get_experiment_nonexistent(self, controller):
        """获取不存在的实验."""
        assert controller.get_experiment("nonexistent") is None

    def test_get_experiments_by_status(self, controller):
        """按状态获取实验."""
        e1 = controller.create_experiment("Draft 1", control_genomes=["c1"], variant_genomes=["v1"])
        e2 = controller.create_experiment("Draft 2", control_genomes=["c2"], variant_genomes=["v2"])
        controller.start_experiment(e2.experiment_id)

        drafts = controller.get_experiments_by_status(ExperimentStatus.DRAFT)
        running = controller.get_experiments_by_status(ExperimentStatus.RUNNING)
        assert len(drafts) == 1
        assert len(running) == 1

    def test_get_active_experiments(self, controller):
        """获取活跃实验."""
        e1 = controller.create_experiment("Active", control_genomes=["c1"], variant_genomes=["v1"])
        controller.start_experiment(e1.experiment_id)
        active = controller.get_active_experiments()
        assert len(active) == 1

    def test_get_draft_experiments(self, controller):
        """获取草稿实验."""
        controller.create_experiment("Draft", control_genomes=["c1"], variant_genomes=["v1"])
        drafts = controller.get_draft_experiments()
        assert len(drafts) == 1

    def test_stats(self, controller):
        """统计信息."""
        controller.create_experiment("E1", control_genomes=["c1"], variant_genomes=["v1"])
        controller.create_experiment("E2", control_genomes=["c2"], variant_genomes=["v2"])
        s = controller.stats()
        assert s["total_experiments"] == 2
        assert s["experiments_by_status"]["draft"] == 2

    def test_stats_with_active(self, controller):
        """含活跃实验的统计."""
        e1 = controller.create_experiment("E1", control_genomes=["c1"], variant_genomes=["v1"])
        controller.start_experiment(e1.experiment_id)
        s = controller.stats()
        assert s["active_experiments"] == 1

    def test_stats_with_results(self, controller, experiment_with_results):
        """含结果的统计."""
        s = controller.stats()
        assert s["total_results"] == 4

    def test_stats_with_winner(self, controller, experiment_with_results):
        """含 Winner 的统计."""
        controller.compute_fitness(experiment_with_results.experiment_id)
        s = controller.stats()
        assert s["experiments_with_winner"] == 1

    def test_reset(self, controller):
        """重置."""
        controller.create_experiment("E1", control_genomes=["c1"], variant_genomes=["v1"])
        controller.reset()
        s = controller.stats()
        assert s["total_experiments"] == 0
        assert s["total_results"] == 0


# ═══════════════════════════════════════════════════════════
# 13. 回归 Tests — E14.5.x + E14.6.1 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRegressionE14:
    """回归测试: E14.5.x + E14.6.1 集成."""

    def test_experiment_controller_defaults(self):
        """默认控制器创建."""
        ctrl = ExperimentController()
        assert ctrl.stats()["total_experiments"] == 0

    def test_factory_function(self):
        """工厂函数."""
        ctrl = create_experiment_controller()
        assert isinstance(ctrl, ExperimentController)

    def test_factory_with_custom_params(self):
        """工厂函数自定义参数."""
        config = ExperimentConfig(budget_total=1000)
        ctrl = create_experiment_controller(default_config=config)
        assert ctrl._default_config.budget_total == 1000

    def test_full_lifecycle(self, controller):
        """完整生命周期: 创建 → 启动 → 记录 → 完成 → 计算."""
        exp = controller.create_experiment(
            name="Full Lifecycle",
            control_genomes=["ctrl_1"],
            variant_genomes=["v1", "v2"],
        )
        assert exp.status == ExperimentStatus.DRAFT

        controller.start_experiment(exp.experiment_id)
        assert exp.status == ExperimentStatus.RUNNING

        controller.record_result(exp.experiment_id, "ctrl_1", {
            "ctr": 0.025, "cvr": 0.04, "roas": 0.35, "payer_rate": 0.04,
        })
        controller.record_result(exp.experiment_id, "v1", {
            "ctr": 0.032, "cvr": 0.05, "roas": 0.48, "payer_rate": 0.05,
        })
        controller.record_result(exp.experiment_id, "v2", {
            "ctr": 0.028, "cvr": 0.043, "roas": 0.38, "payer_rate": 0.042,
        })

        controller.complete_experiment(exp.experiment_id)
        assert exp.status == ExperimentStatus.COMPLETED

        report = controller.compute_fitness(exp.experiment_id)
        assert report.has_winner
        assert report.winner_genome_id == "v1"

    def test_multiple_experiments_independent(self, controller):
        """多个独立实验互不影响."""
        e1 = controller.create_experiment("E1", control_genomes=["c1"], variant_genomes=["v1"])
        e2 = controller.create_experiment("E2", control_genomes=["c2"], variant_genomes=["v2"])

        controller.start_experiment(e1.experiment_id)
        assert e1.status == ExperimentStatus.RUNNING
        assert e2.status == ExperimentStatus.DRAFT

    def test_isolated_controllers(self):
        """隔离的控制器互不影响."""
        c1 = ExperimentController()
        c2 = ExperimentController()

        c1.create_experiment("E1", control_genomes=["c1"], variant_genomes=["v1"])
        assert c1.stats()["total_experiments"] == 1
        assert c2.stats()["total_experiments"] == 0

    def test_e14_6_1_integration_create_from_execution(self, controller):
        """E14.6.1 → E14.6.2 集成: 从 ExecutionResult 创建实验."""
        executor = DecisionExecutor()
        action = EvolutionAction(
            action_type=ActionType.MUTATE_GENE,
            gene_category="hook",
            mutation_direction="rescue",
            count=3,
        )
        result = executor.execute_single_action(action, population_id="pop_test")
        assert len(result.genome_ids) >= 1

        exp = controller.create_experiment_from_execution(
            name="E14.6.1 → E14.6.2",
            execution_result=result,
            hypothesis="Integrated test",
        )
        assert exp.total_genomes > 0
        assert exp.population_id == "pop_test"

    def test_e14_6_1_integration_batch(self, controller):
        """E14.6.1 → E14.6.2 批量集成."""
        executor = DecisionExecutor()
        action1 = EvolutionAction(action_type=ActionType.CREATE_VARIANTS, gene_category="visual", count=2)
        action2 = EvolutionAction(action_type=ActionType.MUTATE_GENE, gene_category="hook", count=2)

        result1 = executor.execute_single_action(action1)
        result2 = executor.execute_single_action(action2)

        exp = controller.create_experiment_batch(
            name="Batch Integration",
            actions=[action1, action2],
            execution_results=[result1, result2],
        )
        assert exp.total_genomes > 0

    def test_serialization_roundtrip_experiment(self):
        """Experiment 序列化往返."""
        exp = Experiment(
            name="Serial Test",
            hypothesis="Test hypothesis",
            control_group=ExperimentGroup(
                group_type=GroupType.CONTROL,
                genome_ids=["c1", "c2"],
                budget=100.0,
            ),
            variant_groups=[
                ExperimentGroup(genome_ids=["v1"], budget=50.0),
            ],
            config=ExperimentConfig(budget_total=500),
            tags=["test"],
        )
        d = exp.to_dict()
        restored = Experiment.from_dict(d)
        assert restored.name == "Serial Test"
        assert restored.total_genomes == 3
        assert restored.hypothesis == "Test hypothesis"
        assert restored.control_group.genome_count == 2
        assert len(restored.variant_groups) == 1

    def test_serialization_roundtrip_result(self):
        """ExperimentResult 序列化往返."""
        r = ExperimentResult(
            experiment_id="exp_001",
            genome_id="genome_001",
            group_type=GroupType.VARIANT,
            metrics={"ctr": 0.032, "roas": 0.48},
            sample_size=5000,
            is_winner=True,
        )
        d = r.to_dict()
        restored = ExperimentResult.from_dict(d)
        assert restored.genome_id == "genome_001"
        assert restored.ctr == 0.032
        assert restored.is_winner is True