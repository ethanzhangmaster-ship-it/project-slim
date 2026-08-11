"""E11.4.2 — Mutation Mapping Layer 测试。

测试范围：
  - MutationGeneChange: 数据模型 + delta 计算
  - MutationConstraint: 约束 + clamp + validate
  - VisionMutationPlan: 数据模型 + genes_touched
  - GeneMapper: Pattern→Genome Gene 映射 + intermediate→genome
  - ConstraintEngine: 约束应用 + 全局默认
  - MutationPlanner: VisionDecision → VisionMutationPlan
  - Integration: Decision → MutationPlan → Genome Change
"""
from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.decision.models import (
    VisionDecision,
    MutationInstruction,
)
from market_ops.creative_vision_runtime.mutation.models import (
    MutationGeneChange,
    MutationConstraint,
    VisionMutationPlan,
)
from market_ops.creative_vision_runtime.mutation.gene_mapper import (
    GeneMapper,
    GeneMapping,
    PATTERN_TO_GENOME,
)
from market_ops.creative_vision_runtime.mutation.constraint import (
    ConstraintEngine,
    DEFAULT_CONSTRAINTS,
)
from market_ops.creative_vision_runtime.mutation.mutation_planner import (
    MutationPlanner,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _make_decision(
    asset_id: str = "MW_VID_001",
    instructions: list[MutationInstruction] | None = None,
    confidence: float = 0.75,
) -> VisionDecision:
    if instructions is None:
        instructions = [
            MutationInstruction(
                target_gene="hook_contrast",
                operator="increase",
                magnitude=0.2,
                source_pattern="high_contrast_opening",
                description="Visual contrast in opening scene",
            ),
            MutationInstruction(
                target_gene="color_palette",
                operator="increase",
                magnitude=0.15,
                source_pattern="high_saturation",
                description="Color saturation level",
            ),
        ]
    return VisionDecision(
        creative_asset_id=asset_id,
        confidence=confidence,
        mutation_instructions=instructions,
        keep_patterns=["high_contrast_opening"],
        mutate_patterns=["high_saturation"],
        remove_patterns=["dark_visual"],
    )


def _make_genome(**kwargs) -> dict[str, float]:
    defaults = {
        "hook_contrast": 0.5,
        "color_brightness": 0.55,
        "color_saturation": 0.6,
        "object_density": 0.4,
        "transition_speed": 0.45,
        "reward_reveal_curve": 0.5,
    }
    defaults.update(kwargs)
    return defaults


# ════════════════════════════════════════════════════════════════════
# MutationGeneChange
# ════════════════════════════════════════════════════════════════════

class TestMutationGeneChange:
    """MutationGeneChange 数据模型测试。"""

    def test_create(self):
        mgc = MutationGeneChange(
            gene_name="hook_contrast",
            old_value=0.5,
            new_value=0.7,
            operator="increase",
            confidence=0.8,
            reason="Winner pattern",
            source_pattern="high_contrast_opening",
        )
        assert mgc.gene_name == "hook_contrast"
        assert mgc.delta == 0.2

    def test_delta_negative(self):
        mgc = MutationGeneChange(
            gene_name="object_density",
            old_value=0.6,
            new_value=0.4,
            operator="decrease",
        )
        assert mgc.delta == -0.2

    def test_to_dict(self):
        mgc = MutationGeneChange(
            gene_name="color_saturation",
            old_value=0.5,
            new_value=0.65,
            operator="increase",
            confidence=0.7,
            reason="test",
            source_pattern="high_saturation",
        )
        d = mgc.to_dict()
        assert d["gene_name"] == "color_saturation"
        assert d["delta"] == 0.15

    def test_repr(self):
        mgc = MutationGeneChange(
            gene_name="hook_contrast",
            old_value=0.5,
            new_value=0.7,
        )
        r = repr(mgc)
        assert "hook_contrast" in r
        assert "+0.20" in r


# ════════════════════════════════════════════════════════════════════
# MutationConstraint
# ════════════════════════════════════════════════════════════════════

class TestMutationConstraint:
    """MutationConstraint 约束测试。"""

    def test_create(self):
        c = MutationConstraint(
            gene_name="hook_contrast",
            min_value=0.0,
            max_value=1.0,
            max_delta=0.25,
            direction="both",
        )
        assert c.gene_name == "hook_contrast"
        assert c.max_delta == 0.25

    def test_clamp_within_range(self):
        c = MutationConstraint(gene_name="test", min_value=0.0, max_value=1.0)
        assert c.clamp(0.5) == 0.5
        assert c.clamp(1.5) == 1.0
        assert c.clamp(-0.5) == 0.0

    def test_clamp_delta_increase(self):
        c = MutationConstraint(gene_name="test", max_delta=0.25)
        assert c.clamp_delta(0.3, "increase") == 0.25
        assert c.clamp_delta(0.1, "increase") == 0.1

    def test_clamp_delta_decrease(self):
        c = MutationConstraint(gene_name="test", max_delta=0.25)
        assert c.clamp_delta(-0.3, "decrease") == -0.25
        assert c.clamp_delta(-0.1, "decrease") == -0.1

    def test_clamp_delta_below_min(self):
        c = MutationConstraint(gene_name="test", min_delta=0.05)
        assert c.clamp_delta(0.02, "increase") == 0.0

    def test_is_valid(self):
        c = MutationConstraint(gene_name="test", max_delta=0.25)
        assert c.is_valid(0.5, 0.7) is True
        assert c.is_valid(0.5, 0.8) is False  # delta > 0.25
        assert c.is_valid(0.5, 1.5) is False  # out of range

    def test_is_valid_direction_constraint(self):
        c = MutationConstraint(gene_name="test", direction="increase")
        assert c.is_valid(0.5, 0.7) is True
        assert c.is_valid(0.7, 0.5) is False  # decrease not allowed

    def test_to_dict(self):
        c = MutationConstraint(gene_name="test", max_delta=0.2)
        d = c.to_dict()
        assert d["gene_name"] == "test"
        assert d["max_delta"] == 0.2

    def test_repr(self):
        c = MutationConstraint(gene_name="test", max_delta=0.2)
        assert "test" in repr(c)


# ════════════════════════════════════════════════════════════════════
# VisionMutationPlan
# ════════════════════════════════════════════════════════════════════

class TestVisionMutationPlan:
    """VisionMutationPlan 数据模型测试。"""

    def test_create_empty(self):
        plan = VisionMutationPlan(asset_id="MW_VID_001")
        assert plan.plan_id.startswith("vmp_")
        assert plan.change_count == 0
        assert plan.max_delta == 0.0

    def test_create_with_changes(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast", old_value=0.5, new_value=0.7,
                confidence=0.8,
            ),
            MutationGeneChange(
                gene_name="color_saturation", old_value=0.6, new_value=0.45,
                operator="decrease", confidence=0.6,
            ),
        ]
        plan = VisionMutationPlan(
            asset_id="MW_VID_001",
            source_decision_id="vd_001",
            changes=changes,
            priority="high",
            expected_impact="Improve visual performance",
            total_confidence=0.7,
        )
        assert plan.change_count == 2
        assert plan.genes_touched == ["hook_contrast", "color_saturation"]
        assert plan.max_delta == 0.2

    def test_to_dict(self):
        plan = VisionMutationPlan(
            asset_id="MW_VID_001",
            changes=[
                MutationGeneChange(
                    gene_name="hook_contrast", old_value=0.5, new_value=0.7,
                ),
            ],
            priority="high",
        )
        d = plan.to_dict()
        assert d["asset_id"] == "MW_VID_001"
        assert len(d["changes"]) == 1
        assert d["priority"] == "high"

    def test_repr(self):
        plan = VisionMutationPlan(
            asset_id="MW_VID_001",
            changes=[
                MutationGeneChange(
                    gene_name="hook_contrast", old_value=0.5, new_value=0.7,
                ),
            ],
            priority="high",
        )
        r = repr(plan)
        assert "MW_VID_001" in r
        assert "high" in r


# ════════════════════════════════════════════════════════════════════
# GeneMapper
# ════════════════════════════════════════════════════════════════════

class TestGeneMapper:
    """GeneMapper 映射测试。"""

    @pytest.fixture
    def mapper(self):
        return GeneMapper()

    def test_pattern_to_genome_high_contrast(self, mapper):
        gene = mapper.pattern_to_genome_gene("high_contrast_opening")
        assert gene == "hook_contrast"

    def test_pattern_to_genome_bright(self, mapper):
        assert mapper.pattern_to_genome_gene("bright_visual") == "color_brightness"

    def test_pattern_to_genome_dark(self, mapper):
        assert mapper.pattern_to_genome_gene("dark_visual") == "color_brightness"

    def test_pattern_to_genome_saturation(self, mapper):
        assert mapper.pattern_to_genome_gene("high_saturation") == "color_saturation"

    def test_pattern_to_genome_clean(self, mapper):
        assert mapper.pattern_to_genome_gene("clean_composition") == "object_density"

    def test_pattern_to_genome_complex(self, mapper):
        assert mapper.pattern_to_genome_gene("complex_scene") == "object_density"

    def test_pattern_to_genome_fast_change(self, mapper):
        assert mapper.pattern_to_genome_gene("fast_visual_change") == "transition_speed"

    def test_pattern_to_genome_rising(self, mapper):
        assert mapper.pattern_to_genome_gene("rising_brightness") == "reward_reveal_curve"

    def test_pattern_to_genome_unknown(self, mapper):
        assert mapper.pattern_to_genome_gene("unknown") is None

    def test_intermediate_to_genome(self, mapper):
        assert mapper.intermediate_to_genome_gene("hook_contrast") == "hook_contrast"
        assert mapper.intermediate_to_genome_gene("brightness") == "color_brightness"
        assert mapper.intermediate_to_genome_gene("color_palette") == "color_saturation"
        assert mapper.intermediate_to_genome_gene("object_count") == "object_density"
        assert mapper.intermediate_to_genome_gene("scene_transition") == "transition_speed"

    def test_get_operator_for_pattern(self, mapper):
        assert mapper.get_operator_for_pattern("high_contrast_opening") == "increase"
        assert mapper.get_operator_for_pattern("complex_scene") == "decrease"
        assert mapper.get_operator_for_pattern("clean_composition") == "set"

    def test_get_range(self, mapper):
        assert mapper.get_range_for_pattern("high_contrast_opening") == (0.0, 1.0)
        assert mapper.get_range_for_gene("hook_contrast") == (0.0, 1.0)

    def test_get_description(self, mapper):
        desc = mapper.get_description("high_contrast_opening")
        assert "contrast" in desc.lower()

    def test_list_patterns(self, mapper):
        patterns = mapper.list_patterns()
        assert len(patterns) == len(PATTERN_TO_GENOME)
        assert "high_contrast_opening" in patterns

    def test_list_genome_genes(self, mapper):
        genes = mapper.list_genome_genes()
        assert "hook_contrast" in genes
        assert "color_brightness" in genes
        assert "object_density" in genes
        # 6 unique genes
        assert len(genes) == 6

    def test_repr(self, mapper):
        assert "GeneMapper" in repr(mapper)


# ════════════════════════════════════════════════════════════════════
# ConstraintEngine
# ════════════════════════════════════════════════════════════════════

class TestConstraintEngine:
    """ConstraintEngine 约束引擎测试。"""

    @pytest.fixture
    def engine(self):
        return ConstraintEngine()

    def test_default_genes(self, engine):
        genes = engine.list_genes()
        assert "hook_contrast" in genes
        assert "color_brightness" in genes
        assert "color_saturation" in genes
        assert "object_density" in genes
        assert "transition_speed" in genes
        assert "reward_reveal_curve" in genes

    def test_apply_increase(self, engine):
        new_value = engine.apply("hook_contrast", old_value=0.5, target_value=0.7, operator="increase")
        assert new_value == 0.7

    def test_apply_clamped_delta(self, engine):
        # delta 0.4 > max_delta 0.25
        new_value = engine.apply("hook_contrast", old_value=0.5, target_value=0.9, operator="increase")
        assert new_value == 0.75

    def test_apply_clamped_boundary(self, engine):
        new_value = engine.apply("hook_contrast", old_value=0.9, target_value=1.3, operator="increase")
        assert new_value <= 1.0

    def test_apply_decrease(self, engine):
        new_value = engine.apply("object_density", old_value=0.6, target_value=0.4, operator="decrease")
        assert new_value == 0.4

    def test_apply_small_delta(self, engine):
        # delta 0.02 < min_delta 0.05 → 0
        new_value = engine.apply("hook_contrast", old_value=0.5, target_value=0.52, operator="increase")
        assert new_value == 0.5

    def test_validate(self, engine):
        assert engine.validate("hook_contrast", 0.5, 0.7) is True
        assert engine.validate("hook_contrast", 0.5, 0.8) is False  # delta > 0.25

    def test_unknown_gene_default(self, engine):
        new_value = engine.apply("unknown_gene", old_value=0.5, target_value=0.7, operator="increase")
        assert new_value == 0.7

    def test_add_custom_constraint(self, engine):
        c = MutationConstraint(gene_name="custom_gene", max_delta=0.1)
        engine.add_constraint(c)
        new_value = engine.apply("custom_gene", old_value=0.5, target_value=0.7, operator="increase")
        assert new_value == 0.6

    def test_remove_constraint(self, engine):
        assert engine.remove_constraint("hook_contrast") is True
        assert "hook_contrast" not in engine.list_genes()

    def test_remove_nonexistent(self, engine):
        assert engine.remove_constraint("nonexistent") is False

    def test_to_dict(self, engine):
        d = engine.to_dict()
        assert "hook_contrast" in d
        assert d["hook_contrast"]["max_delta"] == 0.25

    def test_repr(self, engine):
        assert "ConstraintEngine" in repr(engine)


# ════════════════════════════════════════════════════════════════════
# MutationPlanner
# ════════════════════════════════════════════════════════════════════

class TestMutationPlanner:
    """MutationPlanner 计划生成测试。"""

    @pytest.fixture
    def planner(self):
        return MutationPlanner()

    def test_create_plan(self, planner):
        decision = _make_decision("MW_VID_001")
        genome = _make_genome()
        plan = planner.create_plan(decision, genome)

        assert plan.asset_id == "MW_VID_001"
        assert plan.source_decision_id == decision.decision_id
        assert plan.change_count >= 2
        assert plan.total_confidence > 0

    def test_create_plan_genes_mapped(self, planner):
        decision = _make_decision("MW_VID_001")
        genome = _make_genome()
        plan = planner.create_plan(decision, genome)

        genes = set(plan.genes_touched)
        assert "hook_contrast" in genes
        assert "color_saturation" in genes

    def test_create_plan_values_changed(self, planner):
        decision = _make_decision("MW_VID_001")
        genome = _make_genome(hook_contrast=0.5, color_saturation=0.6)
        plan = planner.create_plan(decision, genome)

        for change in plan.changes:
            if change.gene_name == "hook_contrast":
                assert change.old_value == 0.5
                assert change.new_value > 0.5
            if change.gene_name == "color_saturation":
                assert change.old_value == 0.6
                assert change.new_value > 0.6

    def test_create_plan_constrained(self, planner):
        # 大 magnitude 应被约束
        decision = _make_decision("MW_VID_001", instructions=[
            MutationInstruction(
                target_gene="hook_contrast",
                operator="increase",
                magnitude=0.5,  # exceeding max_delta
                source_pattern="high_contrast_opening",
                description="test",
            ),
        ])
        genome = _make_genome(hook_contrast=0.5)
        plan = planner.create_plan(decision, genome)

        for change in plan.changes:
            assert change.new_value - change.old_value <= 0.25

    def test_create_plan_empty_instructions(self, planner):
        decision = _make_decision("MW_VID_001", instructions=[])
        plan = planner.create_plan(decision, _make_genome())
        assert plan.change_count == 0

    def test_create_plan_priority_high(self, planner):
        decision = _make_decision("MW_VID_001", confidence=0.8)
        plan = planner.create_plan(decision, _make_genome())
        assert plan.priority == "high"

    def test_create_plan_priority_low(self, planner):
        decision = _make_decision("MW_VID_001", confidence=0.3, instructions=[])
        plan = planner.create_plan(decision, _make_genome())
        assert plan.priority == "low"

    def test_create_plan_summary(self, planner):
        decision = _make_decision("MW_VID_001")
        plan = planner.create_plan(decision, _make_genome())
        assert "MW_VID_001" in plan.summary
        assert "→" in plan.summary

    def test_create_plan_expected_impact(self, planner):
        decision = _make_decision("MW_VID_001")
        plan = planner.create_plan(decision, _make_genome())
        assert len(plan.expected_impact) > 0

    def test_create_plan_batch(self, planner):
        decisions = [
            _make_decision("MW_VID_001"),
            _make_decision("MW_VID_002"),
        ]
        genomes = {
            "MW_VID_001": _make_genome(),
            "MW_VID_002": _make_genome(hook_contrast=0.6),
        }
        plans = planner.create_plan_batch(decisions, genomes)
        assert len(plans) == 2
        assert plans[0].asset_id == "MW_VID_001"

    def test_plan_count(self, planner):
        assert planner.plan_count == 0
        planner.create_plan(_make_decision("MW_VID_001"), _make_genome())
        assert planner.plan_count == 1

    def test_repr(self, planner):
        assert "MutationPlanner" in repr(planner)


# ════════════════════════════════════════════════════════════════════
# Integration: Decision → MutationPlan → Genome Change
# ════════════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试：完整突变映射流程。"""

    def test_full_pipeline(self):
        planner = MutationPlanner()

        # 1. 创建 VisionDecision（模拟 E11.4.1 输出）
        decision = _make_decision("MW_MUTANT_001", instructions=[
            MutationInstruction(
                target_gene="hook_contrast",
                operator="increase",
                magnitude=0.2,
                source_pattern="high_contrast_opening",
                description="Visual contrast in opening",
            ),
            MutationInstruction(
                target_gene="color_palette",
                operator="increase",
                magnitude=0.15,
                source_pattern="high_saturation",
                description="Color saturation",
            ),
            MutationInstruction(
                target_gene="object_count",
                operator="set",
                magnitude=0.4,
                source_pattern="clean_composition",
                description="Subject density",
            ),
        ])

        # 2. 当前 Genome
        genome = _make_genome(
            hook_contrast=0.5,
            color_saturation=0.6,
            object_density=0.35,
        )

        # 3. 生成 MutationPlan
        plan = planner.create_plan(decision, genome)

        # 4. 验证映射
        genes = set(plan.genes_touched)
        assert "hook_contrast" in genes
        assert "color_saturation" in genes
        assert "object_density" in genes

        # 5. 验证每个 change
        for change in plan.changes:
            assert change.old_value > 0
            assert change.new_value > 0
            assert abs(change.delta) <= 0.25  # 约束
            assert 0 <= change.new_value <= 1  # 边界

        # 6. 验证计划元数据
        assert plan.asset_id == "MW_MUTANT_001"
        assert plan.priority in ("high", "medium", "low")
        assert plan.total_confidence > 0
        assert len(plan.summary) > 0

    def test_constraint_prevents_runaway(self):
        planner = MutationPlanner()

        # 极端情况：大 magnitude
        decision = _make_decision("MW_EXTREME", instructions=[
            MutationInstruction(
                target_gene="hook_contrast",
                operator="increase",
                magnitude=0.8,  # 非常大
                source_pattern="high_contrast_opening",
                description="test",
            ),
        ])
        genome = _make_genome(hook_contrast=0.9)

        plan = planner.create_plan(decision, genome)

        for change in plan.changes:
            # delta 不应超过 0.25
            assert abs(change.delta) <= 0.25
            # new_value 不应超过 1.0
            assert change.new_value <= 1.0
            # 边界保护
            if change.old_value >= 0.9:
                assert change.new_value <= 1.0

    def test_serialization_roundtrip(self):
        planner = MutationPlanner()
        decision = _make_decision("MW_VID_001")
        plan = planner.create_plan(decision, _make_genome())

        # VisionMutationPlan → dict
        d = plan.to_dict()
        assert d["asset_id"] == "MW_VID_001"
        assert len(d["changes"]) > 0

        # 每个 change → dict
        for change_dict in d["changes"]:
            assert "gene_name" in change_dict
            assert "old_value" in change_dict
            assert "new_value" in change_dict
            assert "delta" in change_dict

    def test_package_exports(self):
        from market_ops.creative_vision_runtime.mutation import (
            MutationPlanner as ExportedPlanner,
            GeneMapper as ExportedMapper,
            ConstraintEngine as ExportedCE,
            VisionMutationPlan as ExportedPlan,
            MutationGeneChange as ExportedChange,
            MutationConstraint as ExportedConstraint,
        )
        assert ExportedPlanner is MutationPlanner
        assert ExportedMapper is GeneMapper
        assert ExportedCE is ConstraintEngine
        assert ExportedPlan is VisionMutationPlan
        assert ExportedChange is MutationGeneChange
        assert ExportedConstraint is MutationConstraint