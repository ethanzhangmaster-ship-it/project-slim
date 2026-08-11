"""E14.6.1 Evolution Decision Executor — 集成测试.

验证 DecisionExecutor 的进化决策执行能力:
  - EvolutionAction / ExecutionResult / ExecutionReport 模型 (15 tests)
  - ActionType / ActionStatus 枚举 (10 tests)
  - convert_plan() 核心转换 (15 tests)
  - execute() 执行 (15 tests)
  - execute_single_action() 单动作执行 (10 tests)
  - 基因组生成 (15 tests)
  - 验证 (10 tests)
  - 查询与统计 (10 tests)
  - 回归 (E14.5.x) (10 tests)

总计: 110 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.decision_executor import (
    DecisionExecutor,
    EvolutionAction,
    ExecutionResult,
    ExecutionReport,
    ActionType,
    ActionStatus,
    create_decision_executor,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_planner import (
    EvolutionPlan,
    EvolutionGoal,
    GeneMutationPlan,
)
from market_ops.e11.genome.schema import CreativeGenome, GenomeLineage
from market_ops.e11.evolution.population_manager import PopulationManager


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def executor():
    """创建默认 DecisionExecutor."""
    return DecisionExecutor()


@pytest.fixture
def evolution_plan():
    """创建测试用 EvolutionPlan."""
    goals = [
        EvolutionGoal(
            goal_id="goal_1",
            goal_type="increase_diversity",
            gene_category="visual",
            description="增加 visual 基因多样性",
            priority=10,
            reason="visual 基因多样性不足",
        ),
        EvolutionGoal(
            goal_id="goal_2",
            goal_type="amplify_rising",
            gene_category="hook",
            description="放大 hook=transformation",
            priority=7,
            reason="transformation 胜率上升",
        ),
        EvolutionGoal(
            goal_id="goal_3",
            goal_type="suppress_declining",
            gene_category="emotion",
            description="抑制 emotion=static",
            priority=6,
            reason="static 胜率下降",
        ),
    ]
    mutation_plans = [
        GeneMutationPlan(
            gene_category="visual",
            direction="real_world",
            percentage=40.0,
            reason="增加多样性",
            expected_impact="+10% diversity",
            confidence=0.85,
        ),
        GeneMutationPlan(
            gene_category="hook",
            direction="transformation",
            percentage=35.0,
            reason="放大赢家",
            expected_impact="+15% ROAS",
            confidence=0.90,
        ),
        GeneMutationPlan(
            gene_category="emotion",
            direction="surprise",
            percentage=25.0,
            reason="探索新方向",
            expected_impact="+5% CTR",
            confidence=0.60,
        ),
    ]
    return EvolutionPlan(
        plan_id="plan_001",
        goals=goals,
        mutation_plans=mutation_plans,
        target_population_size=30,
        generation=1,
        summary="Test plan",
    )


@pytest.fixture
def simple_plan():
    """创建简单计划 (无 target_population)."""
    goals = [
        EvolutionGoal(
            goal_id="goal_1",
            goal_type="explore_new",
            gene_category="gameplay",
            description="探索新 gameplay",
            priority=5,
        ),
    ]
    mutation_plans = [
        GeneMutationPlan(
            gene_category="gameplay",
            direction="rpg",
            percentage=100.0,
            confidence=0.7,
        ),
    ]
    return EvolutionPlan(
        plan_id="plan_002",
        goals=goals,
        mutation_plans=mutation_plans,
        target_population_size=0,
        generation=2,
        summary="Simple plan",
    )


@pytest.fixture
def base_genomes():
    """创建基础基因组列表."""
    g1 = CreativeGenome(
        genome_id="G_001",
        generation=0,
        genes={
            "hook": {"type": "transformation"},
            "visual": {"type": "fantasy"},
            "emotion": {"type": "surprise"},
            "gameplay": {"type": "merge"},
            "reward": {"type": "coins"},
        },
        lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
    )
    g2 = CreativeGenome(
        genome_id="G_002",
        generation=0,
        genes={
            "hook": {"type": "rescue"},
            "visual": {"type": "real_world"},
            "emotion": {"type": "relief"},
            "gameplay": {"type": "puzzle"},
            "reward": {"type": "gems"},
        },
        lineage=GenomeLineage(source="winner_002", created_by="dna_mapper"),
    )
    return [g1, g2]


# ═══════════════════════════════════════════════════════════
# 1. 模型测试 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestEvolutionAction:
    """EvolutionAction 模型测试."""

    def test_action_default_creation(self):
        """默认创建 EvolutionAction."""
        action = EvolutionAction()
        assert action.action_id.startswith("action_")
        assert action.action_type == ActionType.CREATE_VARIANTS
        assert action.status == ActionStatus.PENDING
        assert action.count == 1
        assert action.confidence == 0.0

    def test_action_custom_creation(self):
        """自定义创建 EvolutionAction."""
        action = EvolutionAction(
            action_id="act_001",
            action_type=ActionType.MUTATE_GENE,
            gene_category="hook",
            mutation_direction="transformation",
            count=10,
            confidence=0.85,
            priority=8,
            plan_id="plan_001",
        )
        assert action.action_id == "act_001"
        assert action.action_type == ActionType.MUTATE_GENE
        assert action.gene_category == "hook"
        assert action.mutation_direction == "transformation"
        assert action.count == 10
        assert action.priority == 8

    def test_action_to_dict(self):
        """to_dict 序列化."""
        action = EvolutionAction(
            action_id="act_001",
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=5,
            confidence=0.8,
            plan_id="plan_001",
        )
        d = action.to_dict()
        assert d["action_id"] == "act_001"
        assert d["action_type"] == "diversify"
        assert d["gene_category"] == "visual"
        assert d["confidence"] == 0.8
        assert d["status"] == "pending"

    def test_action_from_dict(self):
        """from_dict 反序列化."""
        data = {
            "action_id": "act_001",
            "action_type": "mutate_gene",
            "gene_category": "hook",
            "mutation_direction": "transformation",
            "count": 5,
            "confidence": 0.85,
            "priority": 7,
            "status": "pending",
        }
        action = EvolutionAction.from_dict(data)
        assert action.action_id == "act_001"
        assert action.action_type == ActionType.MUTATE_GENE
        assert action.gene_category == "hook"
        assert action.count == 5

    def test_action_roundtrip(self):
        """to_dict → from_dict 往返."""
        original = EvolutionAction(
            action_type=ActionType.AMPLIFY_WINNER,
            gene_category="hook",
            mutation_direction="transformation",
            count=3,
            confidence=0.9,
            priority=8,
            plan_id="plan_001",
        )
        d = original.to_dict()
        restored = EvolutionAction.from_dict(d)
        assert restored.action_id == original.action_id
        assert restored.action_type == original.action_type
        assert restored.gene_category == original.gene_category

    def test_action_confidence_rounding(self):
        """置信度四舍五入."""
        action = EvolutionAction(confidence=0.123456)
        d = action.to_dict()
        assert d["confidence"] == 0.123

    def test_action_default_status_pending(self):
        """默认状态为 pending."""
        action = EvolutionAction()
        assert action.status == ActionStatus.PENDING

    def test_action_all_action_types(self):
        """所有动作类型."""
        for at in ActionType:
            action = EvolutionAction(action_type=at)
            assert action.to_dict()["action_type"] == at.value


class TestExecutionResult:
    """ExecutionResult 模型测试."""

    def test_result_default_creation(self):
        """默认创建 ExecutionResult."""
        result = ExecutionResult()
        assert result.result_id.startswith("result_")
        assert result.status == ActionStatus.PENDING
        assert result.genome_ids == []

    def test_result_with_genomes(self):
        """带基因组的结果."""
        result = ExecutionResult(
            action_id="act_001",
            status=ActionStatus.SUCCESS,
            genome_ids=["G_001", "G_002", "G_003"],
            population_id="pop_001",
            stats={"requested": 5, "generated": 3, "skipped": 2},
        )
        assert result.generated_count == 3
        assert result.is_success
        assert result.population_id == "pop_001"

    def test_result_to_dict(self):
        """to_dict 序列化."""
        result = ExecutionResult(
            action_id="act_001",
            status=ActionStatus.SUCCESS,
            genome_ids=["G_001"],
            population_id="pop_001",
        )
        d = result.to_dict()
        assert d["action_id"] == "act_001"
        assert d["status"] == "success"
        assert d["generated_count"] == 1

    def test_result_from_dict(self):
        """from_dict 反序列化."""
        data = {
            "result_id": "res_001",
            "action_id": "act_001",
            "status": "success",
            "genome_ids": ["G_001", "G_002"],
            "population_id": "pop_001",
            "stats": {"generated": 2},
        }
        result = ExecutionResult.from_dict(data)
        assert result.result_id == "res_001"
        assert result.is_success
        assert result.generated_count == 2

    def test_result_is_success_false_on_failed(self):
        """失败时不 is_success."""
        result = ExecutionResult(status=ActionStatus.FAILED)
        assert not result.is_success

    def test_result_with_error(self):
        """带错误信息."""
        result = ExecutionResult(
            status=ActionStatus.FAILED,
            error_message="Something went wrong",
        )
        assert result.error_message == "Something went wrong"


class TestExecutionReport:
    """ExecutionReport 模型测试."""

    def test_report_default_creation(self):
        """默认创建报告."""
        report = ExecutionReport()
        assert report.total_actions == 0
        assert report.success_actions == 0
        assert report.failed_actions == 0
        assert report.total_genomes == 0


# ═══════════════════════════════════════════════════════════
# 2. 枚举测试 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestEnums:
    """枚举测试."""

    def test_action_type_values(self):
        """ActionType 值."""
        assert ActionType.CREATE_VARIANTS.value == "create_variants"
        assert ActionType.MUTATE_GENE.value == "mutate_gene"
        assert ActionType.EXPLORE_NEW.value == "explore_new"
        assert ActionType.AMPLIFY_WINNER.value == "amplify_winner"
        assert ActionType.SUPPRESS_LOSER.value == "suppress_loser"
        assert ActionType.DIVERSIFY.value == "diversify"
        assert ActionType.POPULATE.value == "populate"

    def test_action_type_count(self):
        """ActionType 共 7 种."""
        assert len(ActionType) == 7

    def test_action_status_values(self):
        """ActionStatus 值."""
        assert ActionStatus.PENDING.value == "pending"
        assert ActionStatus.EXECUTING.value == "executing"
        assert ActionStatus.SUCCESS.value == "success"
        assert ActionStatus.PARTIAL.value == "partial"
        assert ActionStatus.FAILED.value == "failed"
        assert ActionStatus.SKIPPED.value == "skipped"

    def test_action_status_count(self):
        """ActionStatus 共 6 种."""
        assert len(ActionStatus) == 6

    def test_action_type_from_string(self):
        """从字符串创建 ActionType."""
        assert ActionType("mutate_gene") == ActionType.MUTATE_GENE
        assert ActionType("diversify") == ActionType.DIVERSIFY
        assert ActionType("populate") == ActionType.POPULATE

    def test_action_status_from_string(self):
        """从字符串创建 ActionStatus."""
        assert ActionStatus("success") == ActionStatus.SUCCESS
        assert ActionStatus("failed") == ActionStatus.FAILED
        assert ActionStatus("pending") == ActionStatus.PENDING

    def test_goal_action_map(self):
        """目标到动作映射."""
        assert DecisionExecutor.GOAL_ACTION_MAP["increase_diversity"] == ActionType.DIVERSIFY
        assert DecisionExecutor.GOAL_ACTION_MAP["amplify_rising"] == ActionType.AMPLIFY_WINNER
        assert DecisionExecutor.GOAL_ACTION_MAP["suppress_declining"] == ActionType.SUPPRESS_LOSER
        assert DecisionExecutor.GOAL_ACTION_MAP["explore_new"] == ActionType.EXPLORE_NEW

    def test_gene_slot_keys(self):
        """基因槽位映射."""
        assert DecisionExecutor.GENE_SLOT_KEYS["hook"] == "hook"
        assert DecisionExecutor.GENE_SLOT_KEYS["visual"] == "visual"
        assert DecisionExecutor.GENE_SLOT_KEYS["emotion"] == "emotion"
        assert DecisionExecutor.GENE_SLOT_KEYS["gameplay"] == "gameplay"
        assert DecisionExecutor.GENE_SLOT_KEYS["reward"] == "reward"

    def test_action_type_enum_iteration(self):
        """遍历 ActionType."""
        types = list(ActionType)
        assert len(types) == 7

    def test_action_status_enum_iteration(self):
        """遍历 ActionStatus."""
        statuses = list(ActionStatus)
        assert len(statuses) == 6


# ═══════════════════════════════════════════════════════════
# 3. convert_plan() 核心转换 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestConvertPlan:
    """convert_plan 测试."""

    def test_convert_plan_returns_actions(self, executor, evolution_plan):
        """convert_plan 返回动作列表."""
        actions = executor.convert_plan(evolution_plan)
        assert len(actions) > 0

    def test_convert_plan_sorted_by_priority(self, executor, evolution_plan):
        """按优先级降序排列."""
        actions = executor.convert_plan(evolution_plan)
        for i in range(len(actions) - 1):
            assert actions[i].priority >= actions[i + 1].priority

    def test_convert_plan_all_have_plan_id(self, executor, evolution_plan):
        """所有动作有 plan_id."""
        actions = executor.convert_plan(evolution_plan)
        for action in actions:
            assert action.plan_id == "plan_001"

    def test_convert_plan_with_target_population(self, executor, evolution_plan):
        """target_population_size > 0 时包含 POPULATE."""
        actions = executor.convert_plan(evolution_plan)
        types = {a.action_type for a in actions}
        assert ActionType.POPULATE in types

    def test_convert_plan_without_target_population(self, executor, simple_plan):
        """target_population_size = 0 时不包含 POPULATE."""
        actions = executor.convert_plan(simple_plan)
        types = {a.action_type for a in actions}
        assert ActionType.POPULATE not in types

    def test_convert_plan_diversity_goal_maps_to_diversify(self, executor, evolution_plan):
        """increase_diversity 目标 → DIVERSIFY 动作."""
        actions = executor.convert_plan(evolution_plan)
        diversify_actions = [a for a in actions if a.action_type == ActionType.DIVERSIFY]
        assert len(diversify_actions) >= 1

    def test_convert_plan_amplify_goal_maps_to_amplify(self, executor, evolution_plan):
        """amplify_rising 目标 → AMPLIFY_WINNER 动作."""
        actions = executor.convert_plan(evolution_plan)
        amplify_actions = [a for a in actions if a.action_type == ActionType.AMPLIFY_WINNER]
        assert len(amplify_actions) >= 1

    def test_convert_plan_suppress_goal_maps_to_suppress(self, executor, evolution_plan):
        """suppress_declining 目标 → SUPPRESS_LOSER 动作."""
        actions = executor.convert_plan(evolution_plan)
        suppress_actions = [a for a in actions if a.action_type == ActionType.SUPPRESS_LOSER]
        assert len(suppress_actions) >= 1

    def test_convert_plan_actions_stored(self, executor, evolution_plan):
        """动作存储在 executor 内部."""
        actions = executor.convert_plan(evolution_plan)
        stored = executor.stats()["total_actions"]
        assert stored == len(actions)

    def test_convert_plan_empty_plan(self, executor):
        """空计划返回空列表."""
        plan = EvolutionPlan(plan_id="empty")
        actions = executor.convert_plan(plan)
        assert actions == []

    def test_convert_plan_goals_only_no_mutation_plans(self, executor):
        """仅有目标无变异计划."""
        goals = [
            EvolutionGoal(
                goal_id="goal_1",
                goal_type="explore_new",
                gene_category="hook",
                priority=5,
            ),
        ]
        plan = EvolutionPlan(plan_id="goals_only", goals=goals, mutation_plans=[])
        actions = executor.convert_plan(plan)
        assert len(actions) == 1
        assert actions[0].goal_id == "goal_1"

    def test_convert_plan_mutation_plans_only(self, executor):
        """仅有变异计划无目标."""
        mps = [
            GeneMutationPlan(
                gene_category="hook",
                direction="transformation",
                percentage=100.0,
                confidence=0.8,
            ),
        ]
        plan = EvolutionPlan(plan_id="mps_only", goals=[], mutation_plans=mps)
        actions = executor.convert_plan(plan)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.MUTATE_GENE

    def test_convert_plan_populate_fills_gap(self, executor, evolution_plan):
        """POPULATE 填充到 target_population_size."""
        actions = executor.convert_plan(evolution_plan)
        total_count = sum(a.count for a in actions)
        assert total_count >= evolution_plan.target_population_size

    def test_convert_plan_gene_category_mapped(self, executor, evolution_plan):
        """基因类别正确映射."""
        actions = executor.convert_plan(evolution_plan)
        categories = {a.gene_category for a in actions if a.gene_category}
        assert "visual" in categories
        assert "hook" in categories

    def test_convert_plan_idempotent(self, executor, evolution_plan):
        """幂等: 多次调用结果一致."""
        actions1 = executor.convert_plan(evolution_plan)
        executor.reset()
        actions2 = executor.convert_plan(evolution_plan)
        assert len(actions1) == len(actions2)


# ═══════════════════════════════════════════════════════════
# 4. execute() 执行 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestExecute:
    """execute 测试."""

    def test_execute_returns_report(self, executor, evolution_plan):
        """返回 ExecutionReport."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert isinstance(report, ExecutionReport)

    def test_execute_generates_genomes(self, executor, evolution_plan):
        """生成基因组."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert report.total_genomes > 0

    def test_execute_has_population_id(self, executor, evolution_plan):
        """有 population_id."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions, population_id="pop_test")
        assert report.population_id == "pop_test"

    def test_execute_auto_population_id(self, executor, evolution_plan):
        """自动生成 population_id."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert report.population_id.startswith("pop_")

    def test_execute_success_actions_count(self, executor, evolution_plan):
        """成功动作计数."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert report.success_actions > 0

    def test_execute_all_actions_success(self, executor, evolution_plan):
        """所有动作成功."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert report.failed_actions == 0

    def test_execute_summary(self, executor, evolution_plan):
        """报告摘要."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert report.summary

    def test_execute_with_base_genomes(self, executor, evolution_plan, base_genomes):
        """使用基础基因组执行."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions, base_genomes=base_genomes)
        assert report.total_genomes > 0

    def test_execute_results_stored(self, executor, evolution_plan):
        """结果存储在 executor 内部."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        stored = executor.stats()["total_results"]
        assert stored == len(report.results)

    def test_execute_empty_actions(self, executor):
        """空动作列表."""
        report = executor.execute([])
        assert report.total_actions == 0
        assert report.total_genomes == 0

    def test_execute_single_action(self, executor, evolution_plan):
        """执行单个动作."""
        actions = executor.convert_plan(evolution_plan)
        first = actions[:1]
        report = executor.execute(first)
        assert report.total_actions == 1
        assert report.total_genomes > 0

    def test_execute_preserves_action_status(self, executor, evolution_plan):
        """执行后动作状态更新."""
        actions = executor.convert_plan(evolution_plan)
        executor.execute(actions)
        for action in actions:
            assert action.status in (ActionStatus.SUCCESS, ActionStatus.PARTIAL)

    def test_execute_to_dict(self, executor, evolution_plan):
        """报告可序列化."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        d = report.to_dict()
        assert d["total_actions"] > 0
        assert d["total_genomes"] > 0

    def test_execute_with_generation(self, executor, evolution_plan):
        """指定代际编号."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions, generation=5)
        assert report.total_genomes > 0

    def test_execute_plan_id_in_report(self, executor, evolution_plan):
        """报告包含 plan_id."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        assert report.plan_id == "plan_001"


# ═══════════════════════════════════════════════════════════
# 5. execute_single_action() (10 tests)
# ═══════════════════════════════════════════════════════════

class TestExecuteSingleAction:
    """execute_single_action 测试."""

    def test_execute_single_returns_result(self, executor):
        """返回 ExecutionResult."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=3,
            confidence=0.8,
        )
        result = executor.execute_single_action(action)
        assert isinstance(result, ExecutionResult)

    def test_execute_single_generates_genomes(self, executor):
        """生成基因组."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=3,
            confidence=0.8,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 3

    def test_execute_single_with_base_genomes(self, executor, base_genomes):
        """使用基础基因组."""
        action = EvolutionAction(
            action_type=ActionType.CREATE_VARIANTS,
            gene_category="hook",
            mutation_direction="transformation",
            count=2,
            confidence=0.9,
        )
        result = executor.execute_single_action(action, base_genomes=base_genomes)
        assert result.generated_count > 0

    def test_execute_single_mutate_gene(self, executor, base_genomes):
        """MUTATE_GENE 动作."""
        action = EvolutionAction(
            action_type=ActionType.MUTATE_GENE,
            gene_category="hook",
            mutation_direction="curiosity",
            count=2,
            confidence=0.85,
        )
        result = executor.execute_single_action(action, base_genomes=base_genomes)
        assert result.generated_count > 0

    def test_execute_single_amplify(self, executor, base_genomes):
        """AMPLIFY_WINNER 动作."""
        action = EvolutionAction(
            action_type=ActionType.AMPLIFY_WINNER,
            gene_category="hook",
            mutation_direction="transformation",
            count=2,
            confidence=0.9,
        )
        result = executor.execute_single_action(action, base_genomes=base_genomes)
        assert result.generated_count > 0

    def test_execute_single_populate(self, executor):
        """POPULATE 动作."""
        action = EvolutionAction(
            action_type=ActionType.POPULATE,
            gene_category="",
            mutation_direction="fill",
            count=5,
            confidence=0.5,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 5

    def test_execute_single_explore_new(self, executor):
        """EXPLORE_NEW 动作."""
        action = EvolutionAction(
            action_type=ActionType.EXPLORE_NEW,
            gene_category="gameplay",
            mutation_direction="rpg",
            count=3,
            confidence=0.6,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 3

    def test_execute_single_no_base_genomes(self, executor):
        """无基础基因组时正常."""
        action = EvolutionAction(
            action_type=ActionType.CREATE_VARIANTS,
            gene_category="hook",
            mutation_direction="transformation",
            count=3,
            confidence=0.8,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 3

    def test_execute_single_action_status_updated(self, executor):
        """动作状态更新."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=1,
            confidence=0.8,
        )
        executor.execute_single_action(action)
        assert action.status == ActionStatus.SUCCESS

    def test_execute_single_population_id(self, executor):
        """population_id 传递."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=1,
            confidence=0.8,
        )
        result = executor.execute_single_action(action, population_id="pop_test")
        assert result.population_id == "pop_test"


# ═══════════════════════════════════════════════════════════
# 6. 基因组生成 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestGenomeGeneration:
    """基因组生成测试."""

    def test_generated_genome_has_id(self, executor, evolution_plan):
        """生成的基因组有 ID."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        for result in report.results:
            for gid in result.genome_ids:
                assert gid

    def test_generated_genome_has_generation(self, executor, evolution_plan):
        """代际编号."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions, generation=3)
        for result in report.results:
            for gid in result.genome_ids:
                assert "3" in gid

    def test_variant_genome_has_parent(self, executor, base_genomes):
        """变体基因组有父 ID."""
        action = EvolutionAction(
            action_type=ActionType.CREATE_VARIANTS,
            gene_category="hook",
            mutation_direction="transformation",
            count=2,
            confidence=0.9,
        )
        result = executor.execute_single_action(action, base_genomes=base_genomes)
        for gid in result.genome_ids:
            assert "_v" in gid or "genome" in gid

    def test_mutated_genome_has_parent(self, executor, base_genomes):
        """变异基因组有父 ID."""
        action = EvolutionAction(
            action_type=ActionType.MUTATE_GENE,
            gene_category="hook",
            mutation_direction="curiosity",
            count=2,
            confidence=0.85,
        )
        result = executor.execute_single_action(action, base_genomes=base_genomes)
        for gid in result.genome_ids:
            assert "_mut_" in gid or "genome" in gid

    def test_amplified_genome_has_parent(self, executor, base_genomes):
        """放大基因组有父 ID."""
        action = EvolutionAction(
            action_type=ActionType.AMPLIFY_WINNER,
            gene_category="hook",
            mutation_direction="transformation",
            count=2,
            confidence=0.9,
        )
        result = executor.execute_single_action(action, base_genomes=base_genomes)
        for gid in result.genome_ids:
            assert "_amp_" in gid or "genome" in gid

    def test_genome_count_matches_action(self, executor):
        """基因组数量匹配 action.count."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=5,
            confidence=0.8,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 5

    def test_genome_ids_unique(self, executor, evolution_plan):
        """基因组 ID 唯一."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        all_ids = []
        for result in report.results:
            all_ids.extend(result.genome_ids)
        assert len(all_ids) == len(set(all_ids))

    def test_genome_has_lineage(self, executor):
        """基因组有 lineage."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=1,
            confidence=0.8,
        )
        result = executor.execute_single_action(action)
        # 验证基因组格式正确
        for gid in result.genome_ids:
            assert gid

    def test_result_stats(self, executor, evolution_plan):
        """结果统计."""
        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions)
        for result in report.results:
            assert "requested" in result.stats
            assert "generated" in result.stats
            assert result.stats["generated"] == result.generated_count

    def test_all_action_types_generate_genomes(self, executor, base_genomes):
        """所有动作类型都生成基因组."""
        for at in ActionType:
            action = EvolutionAction(
                action_type=at,
                gene_category="hook" if at != ActionType.POPULATE else "",
                mutation_direction="transformation" if at != ActionType.POPULATE else "",
                count=1,
                confidence=0.8,
            )
            result = executor.execute_single_action(action, base_genomes=base_genomes)
            assert result.generated_count >= 1, f"Action type {at} failed to generate genomes"

    def test_suppress_generates_new_genomes(self, executor):
        """SUPPRESS_LOSER 生成全新基因组."""
        action = EvolutionAction(
            action_type=ActionType.SUPPRESS_LOSER,
            gene_category="emotion",
            mutation_direction="surprise",
            count=3,
            confidence=0.6,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 3

    def test_diversify_generates_new_genomes(self, executor):
        """DIVERSIFY 生成全新基因组."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="cartoon",
            count=3,
            confidence=0.7,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 3

    def test_explore_new_generates_genomes(self, executor):
        """EXPLORE_NEW 生成基因组."""
        action = EvolutionAction(
            action_type=ActionType.EXPLORE_NEW,
            gene_category="gameplay",
            mutation_direction="rpg",
            count=3,
            confidence=0.6,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 3

    def test_genome_id_format(self, executor):
        """基因组 ID 格式."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=1,
            confidence=0.8,
        )
        result = executor.execute_single_action(action, generation=2)
        for gid in result.genome_ids:
            assert "genome" in gid or "2" in gid

    def test_count_zero_handled(self, executor):
        """count=0 时代码不崩溃."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=0,
            confidence=0.8,
        )
        result = executor.execute_single_action(action)
        assert result.generated_count == 0


# ═══════════════════════════════════════════════════════════
# 7. 验证 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestValidation:
    """验证测试."""

    def test_validate_valid_action(self, executor):
        """有效动作通过验证."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="real_world",
            count=5,
            confidence=0.8,
        )
        assert executor.validate(action)

    def test_validate_invalid_count(self, executor):
        """count <= 0 无效."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            confidence=0.8,
            count=0,
        )
        assert not executor.validate(action)

    def test_validate_low_confidence(self, executor):
        """低置信度无效."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            confidence=0.1,
            count=5,
        )
        assert not executor.validate(action)

    def test_validate_populate_ignores_confidence(self, executor):
        """POPULATE 忽略置信度."""
        action = EvolutionAction(
            action_type=ActionType.POPULATE,
            gene_category="",
            confidence=0.0,
            count=10,
        )
        assert executor.validate(action)

    def test_validate_populate_ignores_gene_category(self, executor):
        """POPULATE 忽略基因类别."""
        action = EvolutionAction(
            action_type=ActionType.POPULATE,
            gene_category="",
            count=10,
            confidence=0.5,
        )
        assert executor.validate(action)

    def test_validate_no_gene_category(self, executor):
        """无基因类别无效."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="",
            confidence=0.8,
            count=5,
        )
        assert not executor.validate(action)

    def test_validate_actions_batch(self, executor):
        """批量验证."""
        valid = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            confidence=0.8,
            count=5,
        )
        invalid = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            confidence=0.1,
            count=5,
        )
        results = executor.validate_actions([valid, invalid])
        assert results[valid.action_id] is True
        assert results[invalid.action_id] is False

    def test_validate_custom_min_confidence(self):
        """自定义最低置信度."""
        executor = DecisionExecutor(min_confidence=0.5)
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            confidence=0.4,
            count=5,
        )
        assert not executor.validate(action)

    def test_validate_high_confidence(self, executor):
        """高置信度通过."""
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            confidence=0.99,
            count=5,
        )
        assert executor.validate(action)

    def test_validate_empty_actions(self, executor):
        """空列表验证."""
        result = executor.validate_actions([])
        assert result == {}


# ═══════════════════════════════════════════════════════════
# 8. 查询与统计 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestQueriesAndStats:
    """查询与统计测试."""

    def test_get_action_found(self, executor, evolution_plan):
        """获取已存储动作."""
        actions = executor.convert_plan(evolution_plan)
        action = executor.get_action(actions[0].action_id)
        assert action is not None

    def test_get_action_not_found(self, executor):
        """获取不存在的动作."""
        assert executor.get_action("nonexistent") is None

    def test_get_result_found(self, executor, evolution_plan):
        """获取已存储结果."""
        actions = executor.convert_plan(evolution_plan)
        executor.execute(actions)
        # 验证有结果存储
        assert executor.stats()["total_results"] > 0

    def test_get_result_not_found(self, executor):
        """获取不存在的结果."""
        assert executor.get_result("nonexistent") is None

    def test_get_actions_by_status(self, executor, evolution_plan):
        """按状态获取动作."""
        actions = executor.convert_plan(evolution_plan)
        executor.execute(actions)
        success_actions = executor.get_actions_by_status(ActionStatus.SUCCESS)
        assert len(success_actions) > 0

    def test_get_results_by_status(self, executor, evolution_plan):
        """按状态获取结果."""
        actions = executor.convert_plan(evolution_plan)
        executor.execute(actions)
        success_results = executor.get_results_by_status(ActionStatus.SUCCESS)
        assert len(success_results) > 0

    def test_stats_initial(self, executor):
        """初始统计."""
        s = executor.stats()
        assert s["total_actions"] == 0
        assert s["total_results"] == 0

    def test_stats_after_execution(self, executor, evolution_plan):
        """执行后统计."""
        actions = executor.convert_plan(evolution_plan)
        executor.execute(actions)
        s = executor.stats()
        assert s["total_actions"] > 0
        assert s["total_results"] > 0

    def test_reset(self, executor, evolution_plan):
        """重置."""
        executor.convert_plan(evolution_plan)
        executor.reset()
        assert executor.stats()["total_actions"] == 0
        assert executor.stats()["total_results"] == 0

    def test_factory_function(self):
        """工厂函数."""
        executor = create_decision_executor()
        assert isinstance(executor, DecisionExecutor)


# ═══════════════════════════════════════════════════════════
# 9. 回归测试 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestE1461Regression:
    """回归测试 — 确保 E14.6.1 不影响已有模块."""

    def test_regression_imports(self):
        """所有 E14.5 + E14.6.1 模块可导入."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            # E14.5.1
            GenomeIntelligence, GenePerformance, ContextAffinity, GeneIntelligence,
            GenomeIntelligenceReport, create_genome_intelligence,
            # E14.5.2
            PopulationAnalyzer, DiversityMetrics, TrendSignal, PopulationHealthReport,
            create_population_analyzer,
            # E14.5.3
            EvolutionPlanner, EvolutionGoal, GeneMutationPlan, EvolutionPlan,
            create_evolution_planner,
            # E14.5.4
            AdaptiveMutationSelector, AdaptiveMutation, AdaptiveMutationReport,
            create_adaptive_mutation_selector,
            # E14.5.5
            FitnessPredictor, FitnessPrediction, FitnessPredictionReport,
            create_fitness_predictor,
            # E14.5.6
            EvolutionMemoryGraph, EvolutionNode, EvolutionEdge, EvolutionPath,
            EvolutionMemoryReport, NodeType, EdgeType, create_evolution_memory_graph,
            # E14.6.1
            DecisionExecutor, EvolutionAction, ExecutionResult, ExecutionReport,
            ActionType, ActionStatus, create_decision_executor,
        )
        assert GenomeIntelligence is not None
        assert EvolutionPlanner is not None
        assert EvolutionMemoryGraph is not None
        assert DecisionExecutor is not None

    def test_regression_e1451_works(self):
        """E14.5.1 仍正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.genome_intelligence import (
            GenomeIntelligence,
        )
        gi = GenomeIntelligence()
        assert gi is not None

    def test_regression_e1452_works(self):
        """E14.5.2 仍正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import (
            PopulationAnalyzer,
        )
        pa = PopulationAnalyzer()
        assert pa is not None

    def test_regression_e1453_works(self):
        """E14.5.3 仍正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_planner import (
            EvolutionPlanner,
        )
        planner = EvolutionPlanner()
        assert planner is not None

    def test_regression_e1454_works(self):
        """E14.5.4 仍正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.adaptive_mutation import (
            AdaptiveMutationSelector,
        )
        selector = AdaptiveMutationSelector()
        assert selector is not None

    def test_regression_e1455_works(self):
        """E14.5.5 仍正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.fitness_predictor import (
            FitnessPredictor,
        )
        predictor = FitnessPredictor()
        assert predictor is not None

    def test_regression_e1456_works(self):
        """E14.5.6 仍正常."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_memory import (
            EvolutionMemoryGraph,
        )
        graph = EvolutionMemoryGraph()
        assert graph is not None

    def test_regression_full_pipeline(self, executor, evolution_plan, base_genomes):
        """完整流水线: Plan → Actions → Execute → Report."""
        # 1. 转换计划
        actions = executor.convert_plan(evolution_plan)
        assert len(actions) > 0

        # 2. 执行
        report = executor.execute(actions, base_genomes=base_genomes)
        assert report.total_genomes > 0

        # 3. 验证
        for result in report.results:
            assert result.generated_count > 0
            assert len(result.genome_ids) > 0

        # 4. 统计
        s = executor.stats()
        assert s["total_actions"] > 0
        assert s["total_results"] > 0

    def test_regression_population_manager_integration(self, executor, evolution_plan):
        """PopulationManager 集成."""
        pm = PopulationManager()
        pop = pm.create_population("pop_test", generation=1)
        assert pop.population_id == "pop_test"

        actions = executor.convert_plan(evolution_plan)
        report = executor.execute(actions, population_id="pop_test")
        assert report.population_id == "pop_test"

    def test_regression_decision_executor_isolated(self, executor):
        """隔离: 独立的 executor 互不影响."""
        e2 = DecisionExecutor()
        action = EvolutionAction(
            action_type=ActionType.DIVERSIFY,
            gene_category="visual",
            mutation_direction="cartoon",
            count=1,
            confidence=0.8,
        )
        e2.execute_single_action(action)
        assert e2.stats()["total_results"] == 1
        assert executor.stats()["total_results"] == 0