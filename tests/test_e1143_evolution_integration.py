"""E11.4.3 — Evolution Integration 测试。

测试范围：
  - GeneMutation: 数据模型 + delta 计算 + 序列化
  - GenomeMutationTask: 数据模型 + 状态管理 + 序列化
  - GenomeAdapter: VisionMutationPlan → GenomeMutationTask 转换
  - MutationExecutor: apply / validate / rollback / batch
  - EvolutionIntegrationEngine: evolve_from_vision / create_genome / rollback
  - Integration: 完整链路 VisionMutationPlan → GenomeMutationTask → Genome
  - Package exports
"""
from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.mutation.models import (
    MutationGeneChange,
    VisionMutationPlan,
)
from market_ops.creative_vision_runtime.mutation.constraint import ConstraintEngine
from market_ops.creative_vision_runtime.evolution_bridge.models import (
    GeneMutation,
    GenomeMutationTask,
)
from market_ops.creative_vision_runtime.evolution_bridge.genome_adapter import (
    GenomeAdapter,
)
from market_ops.creative_vision_runtime.evolution_bridge.mutation_executor import (
    MutationExecutor,
)
from market_ops.creative_vision_runtime.evolution_bridge.integration_engine import (
    EvolutionIntegrationEngine,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_plan(
    asset_id: str = "asset_001",
    changes: list[MutationGeneChange] | None = None,
    priority: str = "medium",
    confidence: float = 0.7,
    summary: str = "Test plan",
) -> VisionMutationPlan:
    if changes is None:
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5,
                new_value=0.65,
                operator="increase",
                confidence=0.8,
                reason="Improve opening hook",
                source_pattern="high_contrast_opening",
            ),
        ]
    return VisionMutationPlan(
        asset_id=asset_id,
        changes=changes,
        priority=priority,
        total_confidence=confidence,
        summary=summary,
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


# ═══════════════════════════════════════════════════════════
# GeneMutation
# ═══════════════════════════════════════════════════════════

class TestGeneMutationModel:
    """GeneMutation 数据模型测试。"""

    def test_create_default(self):
        gm = GeneMutation()
        assert gm.gene_name == ""
        assert gm.old_value == 0.0
        assert gm.new_value == 0.0
        assert gm.operator == "increase"
        assert gm.confidence == 0.0
        assert gm.delta == 0.0

    def test_create_with_values(self):
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5,
            new_value=0.75,
            operator="increase",
            confidence=0.8,
            reason="Improve contrast",
            source_pattern="high_contrast_opening",
        )
        assert gm.gene_name == "hook_contrast"
        assert gm.old_value == 0.5
        assert gm.new_value == 0.75
        assert gm.operator == "increase"
        assert gm.confidence == 0.8
        assert gm.delta == 0.25
        assert gm.reason == "Improve contrast"
        assert gm.source_pattern == "high_contrast_opening"

    def test_delta_positive(self):
        gm = GeneMutation(old_value=0.3, new_value=0.7)
        assert gm.delta == 0.4

    def test_delta_negative(self):
        gm = GeneMutation(old_value=0.7, new_value=0.3)
        assert gm.delta == -0.4

    def test_delta_zero(self):
        gm = GeneMutation(old_value=0.5, new_value=0.5)
        assert gm.delta == 0.0

    def test_delta_auto_computed(self):
        gm = GeneMutation(old_value=0.5, new_value=0.65)
        assert gm.delta == pytest.approx(0.15, abs=0.001)

    def test_to_dict(self):
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5,
            new_value=0.75,
            operator="increase",
            confidence=0.8,
            reason="test",
            source_pattern="high_contrast_opening",
        )
        d = gm.to_dict()
        assert d["gene_name"] == "hook_contrast"
        assert d["old_value"] == 0.5
        assert d["new_value"] == 0.75
        assert d["operator"] == "increase"
        assert d["confidence"] == 0.8
        assert d["delta"] == pytest.approx(0.25, abs=0.001)

    def test_from_dict(self):
        data = {
            "gene_name": "color_brightness",
            "old_value": 0.4,
            "new_value": 0.6,
            "operator": "increase",
            "confidence": 0.7,
            "reason": "brighter",
            "source_pattern": "bright_visual",
        }
        gm = GeneMutation.from_dict(data)
        assert gm.gene_name == "color_brightness"
        assert gm.old_value == 0.4
        assert gm.new_value == 0.6
        assert gm.confidence == 0.7

    def test_from_dict_defaults(self):
        gm = GeneMutation.from_dict({})
        assert gm.gene_name == ""
        assert gm.old_value == 0.0

    def test_repr(self):
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5,
            new_value=0.75,
        )
        r = repr(gm)
        assert "hook_contrast" in r
        assert "0.50" in r
        assert "0.75" in r


# ═══════════════════════════════════════════════════════════
# GenomeMutationTask
# ═══════════════════════════════════════════════════════════

class TestGenomeMutationTaskModel:
    """GenomeMutationTask 数据模型测试。"""

    def test_create_default(self):
        task = GenomeMutationTask()
        assert task.task_id.startswith("gmt_")
        assert task.genome_id == ""
        assert task.status == "pending"
        assert task.gene_mutations == []
        assert task.priority == "medium"

    def test_create_with_values(self):
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.75)
        task = GenomeMutationTask(
            genome_id="genome_001",
            asset_id="asset_001",
            source_plan_id="vmp_123",
            gene_mutations=[gm],
            priority="high",
            total_confidence=0.85,
            summary="Test mutation",
        )
        assert task.genome_id == "genome_001"
        assert task.asset_id == "asset_001"
        assert task.source_plan_id == "vmp_123"
        assert task.priority == "high"
        assert task.total_confidence == 0.85
        assert task.status == "pending"

    def test_mutation_count(self):
        mutations = [
            GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.6),
            GeneMutation(gene_name="color_brightness", old_value=0.5, new_value=0.7),
        ]
        task = GenomeMutationTask(gene_mutations=mutations)
        assert task.mutation_count == 2

    def test_mutation_count_empty(self):
        task = GenomeMutationTask()
        assert task.mutation_count == 0

    def test_genes_touched(self):
        mutations = [
            GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.6),
            GeneMutation(gene_name="color_brightness", old_value=0.5, new_value=0.7),
        ]
        task = GenomeMutationTask(gene_mutations=mutations)
        assert task.genes_touched == ["hook_contrast", "color_brightness"]

    def test_max_delta(self):
        mutations = [
            GeneMutation(old_value=0.5, new_value=0.55),  # delta=0.05
            GeneMutation(old_value=0.5, new_value=0.75),  # delta=0.25
            GeneMutation(old_value=0.5, new_value=0.45),  # delta=-0.05
        ]
        task = GenomeMutationTask(gene_mutations=mutations)
        assert task.max_delta == pytest.approx(0.25, abs=0.01)

    def test_max_delta_empty(self):
        task = GenomeMutationTask()
        assert task.max_delta == 0.0

    def test_is_pending(self):
        task = GenomeMutationTask()
        assert task.is_pending is True
        assert task.is_applied is False
        assert task.is_failed is False

    def test_mark_applied(self):
        task = GenomeMutationTask()
        task.mark_applied()
        assert task.is_applied is True
        assert task.is_pending is False
        assert task.applied_at != ""

    def test_mark_failed(self):
        task = GenomeMutationTask()
        task.mark_failed("test error")
        assert task.is_failed is True
        assert task.error_message == "test error"
        assert task.applied_at != ""

    def test_to_dict(self):
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.75)
        task = GenomeMutationTask(
            genome_id="genome_001",
            gene_mutations=[gm],
            priority="high",
            summary="Test",
        )
        d = task.to_dict()
        assert d["genome_id"] == "genome_001"
        assert d["status"] == "pending"
        assert d["priority"] == "high"
        assert len(d["gene_mutations"]) == 1

    def test_task_id_unique(self):
        t1 = GenomeMutationTask()
        t2 = GenomeMutationTask()
        assert t1.task_id != t2.task_id

    def test_repr(self):
        task = GenomeMutationTask(genome_id="genome_001", priority="high")
        r = repr(task)
        assert "genome_001" in r
        assert "pending" in r


# ═══════════════════════════════════════════════════════════
# GenomeAdapter
# ═══════════════════════════════════════════════════════════

class TestGenomeAdapter:
    """GenomeAdapter 测试。"""

    def test_to_mutation_task_single_change(self):
        plan = _make_plan()
        adapter = GenomeAdapter()
        task = adapter.to_mutation_task(plan)

        assert isinstance(task, GenomeMutationTask)
        assert task.genome_id == plan.asset_id
        assert task.asset_id == plan.asset_id
        assert task.source_plan_id == plan.plan_id
        assert task.priority == plan.priority
        assert task.total_confidence == plan.total_confidence
        assert task.summary == plan.summary
        assert task.mutation_count == 1

    def test_to_mutation_task_multiple_changes(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.65,
                operator="increase", confidence=0.8,
                reason="r1", source_pattern="p1",
            ),
            MutationGeneChange(
                gene_name="color_brightness",
                old_value=0.5, new_value=0.7,
                operator="increase", confidence=0.7,
                reason="r2", source_pattern="p2",
            ),
        ]
        plan = _make_plan(changes=changes)
        adapter = GenomeAdapter()
        task = adapter.to_mutation_task(plan)

        assert task.mutation_count == 2
        assert task.genes_touched == ["hook_contrast", "color_brightness"]

    def test_to_mutation_task_with_genome_context(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.65,
                operator="increase", confidence=0.8,
                reason="r1", source_pattern="p1",
            ),
        ]
        plan = _make_plan(changes=changes)
        adapter = GenomeAdapter()

        context = {"hook_contrast": 0.6}
        task = adapter.to_mutation_task(plan, genome_id="genome_001", genome_context=context)

        # old_value should come from context, not from change
        assert task.gene_mutations[0].old_value == 0.6

    def test_to_mutation_task_custom_genome_id(self):
        plan = _make_plan()
        adapter = GenomeAdapter()
        task = adapter.to_mutation_task(plan, genome_id="genome_002")

        assert task.genome_id == "genome_002"

    def test_to_mutation_tasks_batch(self):
        plans = [
            _make_plan(asset_id="asset_001"),
            _make_plan(asset_id="asset_002"),
            _make_plan(asset_id="asset_003"),
        ]
        adapter = GenomeAdapter()
        tasks = adapter.to_mutation_tasks(plans)

        assert len(tasks) == 3
        assert tasks[0].asset_id == "asset_001"
        assert tasks[1].asset_id == "asset_002"
        assert tasks[2].asset_id == "asset_003"

    def test_to_mutation_tasks_with_genome_map(self):
        plans = [
            _make_plan(asset_id="asset_001"),
            _make_plan(asset_id="asset_002"),
        ]
        genome_map = {"asset_001": "genome_A", "asset_002": "genome_B"}
        adapter = GenomeAdapter()
        tasks = adapter.to_mutation_tasks(plans, genome_map=genome_map)

        assert tasks[0].genome_id == "genome_A"
        assert tasks[1].genome_id == "genome_B"

    def test_to_mutation_tasks_with_genome_contexts(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.65,
                operator="increase", confidence=0.8,
                reason="r1", source_pattern="p1",
            ),
        ]
        plan = _make_plan(asset_id="asset_001", changes=changes)
        adapter = GenomeAdapter()

        # genome_contexts is keyed by genome_id (after genome_map lookup)
        contexts = {"genome_A": {"hook_contrast": 0.7}}
        tasks = adapter.to_mutation_tasks(
            [plan],
            genome_map={"asset_001": "genome_A"},
            genome_contexts=contexts,
        )

        assert tasks[0].gene_mutations[0].old_value == 0.7

    def test_task_count(self):
        adapter = GenomeAdapter()
        assert adapter.task_count == 0

        adapter.to_mutation_task(_make_plan())
        assert adapter.task_count == 1

        adapter.to_mutation_task(_make_plan(asset_id="asset_002"))
        assert adapter.task_count == 2

    def test_repr(self):
        adapter = GenomeAdapter()
        adapter.to_mutation_task(_make_plan())
        r = repr(adapter)
        assert "tasks=1" in r

    def test_gene_mutation_confidence_preserved(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.65,
                operator="increase", confidence=0.85,
                reason="r1", source_pattern="p1",
            ),
        ]
        plan = _make_plan(changes=changes)
        adapter = GenomeAdapter()
        task = adapter.to_mutation_task(plan)

        assert task.gene_mutations[0].confidence == 0.85

    def test_gene_mutation_reason_and_source_preserved(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.65,
                operator="increase", confidence=0.8,
                reason="Improve opening hook",
                source_pattern="high_contrast_opening",
            ),
        ]
        plan = _make_plan(changes=changes)
        adapter = GenomeAdapter()
        task = adapter.to_mutation_task(plan)

        gm = task.gene_mutations[0]
        assert gm.reason == "Improve opening hook"
        assert gm.source_pattern == "high_contrast_opening"


# ═══════════════════════════════════════════════════════════
# MutationExecutor
# ═══════════════════════════════════════════════════════════

class TestMutationExecutor:
    """MutationExecutor 测试。"""

    def test_apply_single_mutation(self):
        genome = _make_genome()
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5, new_value=0.65,
            operator="increase", confidence=0.8,
        )
        task = GenomeMutationTask(
            genome_id="genome_001",
            gene_mutations=[gm],
        )

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert task.is_applied is True

    def test_apply_multiple_mutations(self):
        genome = _make_genome()
        mutations = [
            GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65, operator="increase"),
            GeneMutation(gene_name="color_brightness", old_value=0.5, new_value=0.7, operator="increase"),
        ]
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=mutations)

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert result["genes"]["color_brightness"] == pytest.approx(0.7, abs=0.01)
        assert task.is_applied is True

    def test_apply_decrease_mutation(self):
        genome = _make_genome(genes={"color_saturation": 0.8})
        gm = GeneMutation(
            gene_name="color_saturation",
            old_value=0.8, new_value=0.65,
            operator="decrease",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["color_saturation"] < 0.8

    def test_apply_constrained_by_engine(self):
        """ConstraintEngine should prevent delta > 0.25."""
        genome = _make_genome()
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5, new_value=0.9,  # delta=0.4, but max is 0.25
            operator="increase",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] <= 0.75  # 0.5 + 0.25

    def test_apply_constrained_min_value(self):
        genome = _make_genome(genes={"hook_contrast": 0.2})
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.2, new_value=0.0,
            operator="decrease",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] >= 0.0

    def test_apply_constrained_max_value(self):
        genome = _make_genome(genes={"hook_contrast": 0.9})
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.9, new_value=1.0,
            operator="increase",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] <= 1.0

    def test_apply_preserves_parent_ids(self):
        genome = _make_genome()
        original_id = genome["genome_id"]
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert original_id in result["parent_ids"]

    def test_apply_increments_mutation_count(self):
        genome = _make_genome()
        mutations = [
            GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65),
            GeneMutation(gene_name="color_brightness", old_value=0.5, new_value=0.7),
        ]
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=mutations)

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["mutation_count"] == 2

    def test_apply_stores_rollback_snapshot(self):
        genome = _make_genome()
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert "_rollback_snapshot" in result["metadata"]
        assert result["metadata"]["_last_mutation_task_id"] == task.task_id

    def test_validate_valid(self):
        genome = _make_genome()
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5, new_value=0.65,
            operator="increase",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        assert executor.validate(task, genome) is True

    def test_validate_invalid_delta_too_large(self):
        genome = _make_genome()
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5, new_value=0.9,  # delta=0.4 > 0.25
            operator="increase",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        assert executor.validate(task, genome) is False

    def test_validate_invalid_direction(self):
        # transition_speed only allows increase
        genome = _make_genome()
        gm = GeneMutation(
            gene_name="transition_speed",
            old_value=0.5, new_value=0.35,
            operator="decrease",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        assert executor.validate(task, genome) is False

    def test_validate_no_genes_dict(self):
        genome = {"genome_id": "genome_001", "genes": "not_a_dict"}
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        assert executor.validate(task, genome) is False

    def test_apply_batch(self):
        genomes = {
            "genome_A": _make_genome(gid="genome_A"),
            "genome_B": _make_genome(gid="genome_B"),
        }
        tasks = [
            GenomeMutationTask(
                genome_id="genome_A",
                gene_mutations=[
                    GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65),
                ],
            ),
            GenomeMutationTask(
                genome_id="genome_B",
                gene_mutations=[
                    GeneMutation(gene_name="color_brightness", old_value=0.5, new_value=0.7),
                ],
            ),
        ]

        executor = MutationExecutor()
        result = executor.apply_batch(tasks, genomes)

        assert result["genome_A"]["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert result["genome_B"]["genes"]["color_brightness"] == pytest.approx(0.7, abs=0.01)
        assert tasks[0].is_applied is True
        assert tasks[1].is_applied is True

    def test_apply_batch_missing_genome(self):
        genomes = {"genome_A": _make_genome(gid="genome_A")}
        tasks = [
            GenomeMutationTask(
                genome_id="genome_B",  # not in genomes
                gene_mutations=[
                    GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65),
                ],
            ),
        ]

        executor = MutationExecutor()
        result = executor.apply_batch(tasks, genomes)

        assert tasks[0].is_failed is True
        assert "genome_A" in result

    def test_rollback(self):
        genome = _make_genome()
        original_genes = dict(genome["genes"])
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        mutated = executor.apply(task, genome)
        assert mutated["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)

        rolled_back = executor.rollback(task, mutated)
        assert rolled_back["genes"]["hook_contrast"] == original_genes["hook_contrast"]

    def test_rollback_not_applied(self):
        genome = _make_genome()
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor()
        result = executor.rollback(task, genome)

        # Should return unchanged
        assert result == genome

    def test_rollback_no_snapshot(self):
        genome = _make_genome()
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])
        task.mark_applied()  # Mark as applied but no snapshot

        executor = MutationExecutor()
        result = executor.rollback(task, genome)

        # Should return unchanged (no snapshot)
        assert result == genome

    def test_get_stats(self):
        executor = MutationExecutor()
        genome = _make_genome()
        gm = GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65)
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor.apply(task, genome)

        stats = executor.get_stats()
        assert stats["applied"] == 1
        assert stats["failed"] == 0
        assert stats["rolled_back"] == 0

    def test_get_stats_after_failure(self):
        executor = MutationExecutor()
        task = GenomeMutationTask(
            genome_id="genome_missing",
            gene_mutations=[
                GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65),
            ],
        )
        executor.apply_batch([task], {})

        stats = executor.get_stats()
        assert stats["failed"] == 1

    def test_repr(self):
        executor = MutationExecutor()
        r = repr(executor)
        assert "applied=0" in r

    def test_custom_constraints(self):
        """Custom constraint engine should be used."""
        from market_ops.creative_vision_runtime.mutation.models import MutationConstraint

        custom_constraints = ConstraintEngine()
        custom_constraints.add_constraint(MutationConstraint(
            gene_name="hook_contrast",
            min_value=0.0, max_value=1.0,
            max_delta=0.1,  # Stricter than default 0.25
            min_delta=0.01,
            direction="both",
        ))

        genome = _make_genome()
        gm = GeneMutation(
            gene_name="hook_contrast",
            old_value=0.5, new_value=0.8,  # delta=0.3, but custom max is 0.1
            operator="increase",
        )
        task = GenomeMutationTask(genome_id="genome_001", gene_mutations=[gm])

        executor = MutationExecutor(constraints=custom_constraints)
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] <= 0.6  # 0.5 + 0.1


# ═══════════════════════════════════════════════════════════
# EvolutionIntegrationEngine
# ═══════════════════════════════════════════════════════════

class TestEvolutionIntegrationEngine:
    """EvolutionIntegrationEngine 测试。"""

    def test_evolve_from_vision(self):
        plan = _make_plan()
        genome = _make_genome()

        engine = EvolutionIntegrationEngine()
        result = engine.evolve_from_vision(plan, genome)

        assert result["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert result["mutation_count"] == 1
        assert engine.evolve_count == 1

    def test_evolve_from_vision_with_high_confidence_plan(self):
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.7,
                operator="increase", confidence=0.9,
                reason="Strong signal", source_pattern="high_contrast_opening",
            ),
            MutationGeneChange(
                gene_name="color_saturation",
                old_value=0.5, new_value=0.7,
                operator="increase", confidence=0.85,
                reason="High saturation works", source_pattern="high_saturation",
            ),
        ]
        plan = _make_plan(changes=changes, confidence=0.9, priority="high")
        genome = _make_genome()

        engine = EvolutionIntegrationEngine()
        result = engine.evolve_from_vision(plan, genome)

        assert result["genes"]["hook_contrast"] > 0.5
        assert result["genes"]["color_saturation"] > 0.5
        assert result["mutation_count"] == 2

    def test_evolve_from_vision_constrained(self):
        """Extreme mutation should be constrained."""
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=1.0,  # delta=0.5, constrained to 0.25
                operator="increase", confidence=0.9,
                reason="Extreme", source_pattern="p1",
            ),
        ]
        plan = _make_plan(changes=changes)
        genome = _make_genome()

        engine = EvolutionIntegrationEngine()
        result = engine.evolve_from_vision(plan, genome)

        assert result["genes"]["hook_contrast"] <= 0.75

    def test_evolve_from_vision_preserves_unrelated_genes(self):
        plan = _make_plan()
        genome = _make_genome(genes={"color_brightness": 0.8})

        engine = EvolutionIntegrationEngine()
        result = engine.evolve_from_vision(plan, genome)

        # hook_contrast changes, but color_brightness preserves
        assert result["genes"]["color_brightness"] == 0.8
        assert result["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)

    def test_evolve_from_vision_batch(self):
        plans = [
            _make_plan(asset_id="genome_A", changes=[
                MutationGeneChange(
                    gene_name="hook_contrast", old_value=0.5, new_value=0.65,
                    operator="increase", confidence=0.8,
                    reason="r1", source_pattern="p1",
                ),
            ]),
            _make_plan(asset_id="genome_B", changes=[
                MutationGeneChange(
                    gene_name="color_brightness", old_value=0.5, new_value=0.7,
                    operator="increase", confidence=0.8,
                    reason="r2", source_pattern="p2",
                ),
            ]),
        ]
        genomes = {
            "genome_A": _make_genome(gid="genome_A"),
            "genome_B": _make_genome(gid="genome_B"),
        }

        engine = EvolutionIntegrationEngine()
        result = engine.evolve_from_vision_batch(plans, genomes)

        assert result["genome_A"]["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert result["genome_B"]["genes"]["color_brightness"] == pytest.approx(0.7, abs=0.01)
        assert engine.evolve_count == 2

    def test_create_genome_from_plan(self):
        plan = _make_plan()
        engine = EvolutionIntegrationEngine()

        genome = engine.create_genome_from_plan(
            plan,
            name="New Genome",
            generation=0,
        )

        assert "genome_id" in genome
        assert genome["name"] == "New Genome"
        assert genome["generation"] == 0
        assert "genes" in genome
        assert genome["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert "source_plan_id" in genome["metadata"]
        assert genome["metadata"]["source_plan_id"] == plan.plan_id

    def test_create_genome_from_plan_with_base(self):
        plan = _make_plan()
        base = _make_genome(genes={"hook_contrast": 0.4, "color_brightness": 0.9})

        engine = EvolutionIntegrationEngine()
        genome = engine.create_genome_from_plan(
            plan,
            name="Derived",
            generation=1,
            base_genome=base,
        )

        assert genome["generation"] == 1
        assert genome["genes"]["color_brightness"] == 0.9  # preserved from base
        assert genome["genes"]["hook_contrast"] > 0.4  # mutated by plan (0.4→0.65 delta=0.25)

    def test_create_genome_from_plan_all_genes_present(self):
        """All 6 genome genes should be present in created genome."""
        plan = _make_plan()
        engine = EvolutionIntegrationEngine()

        genome = engine.create_genome_from_plan(plan, name="Test")
        expected_genes = {
            "hook_contrast", "color_brightness", "color_saturation",
            "object_density", "transition_speed", "reward_reveal_curve",
        }
        assert set(genome["genes"].keys()) == expected_genes

    def test_rollback(self):
        plan = _make_plan()
        genome = _make_genome()
        original_hook = genome["genes"]["hook_contrast"]

        engine = EvolutionIntegrationEngine()
        mutated = engine.evolve_from_vision(plan, genome)

        assert mutated["genes"]["hook_contrast"] != original_hook

        rolled_back = engine.rollback(mutated)
        assert rolled_back["genes"]["hook_contrast"] == original_hook

    def test_rollback_no_task(self):
        genome = _make_genome()
        engine = EvolutionIntegrationEngine()

        result = engine.rollback(genome)
        assert result == genome

    def test_evolve_count(self):
        engine = EvolutionIntegrationEngine()
        assert engine.evolve_count == 0

        engine.evolve_from_vision(_make_plan(), _make_genome())
        assert engine.evolve_count == 1

        engine.evolve_from_vision(_make_plan(asset_id="asset_002"), _make_genome(gid="genome_002"))
        assert engine.evolve_count == 2

    def test_get_stats(self):
        engine = EvolutionIntegrationEngine()
        engine.evolve_from_vision(_make_plan(), _make_genome())

        stats = engine.get_stats()
        assert stats["evolve_count"] == 1
        assert "adapter" in stats
        assert "executor" in stats

    def test_repr(self):
        engine = EvolutionIntegrationEngine()
        engine.evolve_from_vision(_make_plan(), _make_genome())
        r = repr(engine)
        assert "evolve_count=1" in r

    def test_connect_to_v5(self):
        """connect_to_v5 should not raise."""
        engine = EvolutionIntegrationEngine()
        # Use a mock object with on_event method
        class MockGenomeManager:
            def on_event(self, handler):
                pass

        engine.connect_to_v5(MockGenomeManager())
        # Should not raise

    def test_connect_to_v5_no_on_event(self):
        """connect_to_v5 should handle missing on_event gracefully."""
        engine = EvolutionIntegrationEngine()
        engine.connect_to_v5(object())
        # Should not raise


# ═══════════════════════════════════════════════════════════
# Integration: Full Pipeline
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路集成测试。"""

    def test_vision_plan_to_mutated_genome(self):
        """VisionMutationPlan → GenomeMutationTask → mutated genome."""
        # 1. 创建 VisionMutationPlan
        changes = [
            MutationGeneChange(
                gene_name="hook_contrast",
                old_value=0.5, new_value=0.65,
                operator="increase", confidence=0.8,
                reason="Improve opening hook",
                source_pattern="high_contrast_opening",
            ),
            MutationGeneChange(
                gene_name="color_brightness",
                old_value=0.5, new_value=0.7,
                operator="increase", confidence=0.7,
                reason="Brighter visuals",
                source_pattern="bright_visual",
            ),
        ]
        plan = VisionMutationPlan(
            asset_id="asset_001",
            changes=changes,
            priority="high",
            total_confidence=0.75,
            summary="Improve visual impact",
        )

        # 2. 转换 Plan → Task
        adapter = GenomeAdapter()
        task = adapter.to_mutation_task(plan, genome_id="genome_001")

        assert task.mutation_count == 2
        assert task.priority == "high"
        assert task.total_confidence == 0.75

        # 3. 应用突变
        genome = _make_genome()
        executor = MutationExecutor()
        result = executor.apply(task, genome)

        assert result["genes"]["hook_contrast"] == pytest.approx(0.65, abs=0.01)
        assert result["genes"]["color_brightness"] == pytest.approx(0.7, abs=0.01)
        assert task.is_applied is True
        assert result["mutation_count"] == 2

    def test_vision_plan_to_genome_with_rollback(self):
        """Full pipeline with rollback."""
        changes = [
            MutationGeneChange(
                gene_name="color_saturation",
                old_value=0.5, new_value=0.6,
                operator="increase", confidence=0.7,
                reason="Saturation up", source_pattern="high_saturation",
            ),
        ]
        plan = VisionMutationPlan(
            asset_id="asset_001",
            changes=changes,
            priority="medium",
            total_confidence=0.7,
            summary="Saturation adjustment",
        )

        genome = _make_genome()
        original_saturation = genome["genes"]["color_saturation"]

        engine = EvolutionIntegrationEngine()
        mutated = engine.evolve_from_vision(plan, genome)

        assert mutated["genes"]["color_saturation"] > original_saturation

        rolled_back = engine.rollback(mutated)
        assert rolled_back["genes"]["color_saturation"] == original_saturation

    def test_multiple_plans_sequential_evolution(self):
        """Sequential mutation of the same genome with multiple plans."""
        genome = _make_genome()
        engine = EvolutionIntegrationEngine()

        # Plan 1: increase hook_contrast
        plan1 = VisionMutationPlan(
            asset_id="genome_001",
            changes=[
                MutationGeneChange(
                    gene_name="hook_contrast",
                    old_value=0.5, new_value=0.6,
                    operator="increase", confidence=0.8,
                    reason="r1", source_pattern="p1",
                ),
            ],
        )
        genome = engine.evolve_from_vision(plan1, genome)
        assert genome["genes"]["hook_contrast"] == pytest.approx(0.6, abs=0.01)

        # Plan 2: increase color_brightness
        plan2 = VisionMutationPlan(
            asset_id="genome_001",
            changes=[
                MutationGeneChange(
                    gene_name="color_brightness",
                    old_value=0.5, new_value=0.65,
                    operator="increase", confidence=0.8,
                    reason="r2", source_pattern="p2",
                ),
            ],
        )
        genome = engine.evolve_from_vision(plan2, genome)

        assert genome["genes"]["hook_contrast"] == pytest.approx(0.6, abs=0.01)
        assert genome["genes"]["color_brightness"] == pytest.approx(0.65, abs=0.01)
        assert genome["mutation_count"] == 2

    def test_all_six_genes_mutated(self):
        """All 6 genes can be mutated through the pipeline."""
        changes = [
            MutationGeneChange(gene_name="hook_contrast", old_value=0.5, new_value=0.55, operator="increase", confidence=0.7, reason="r", source_pattern="p"),
            MutationGeneChange(gene_name="color_brightness", old_value=0.5, new_value=0.55, operator="increase", confidence=0.7, reason="r", source_pattern="p"),
            MutationGeneChange(gene_name="color_saturation", old_value=0.5, new_value=0.55, operator="increase", confidence=0.7, reason="r", source_pattern="p"),
            MutationGeneChange(gene_name="object_density", old_value=0.5, new_value=0.4, operator="decrease", confidence=0.7, reason="r", source_pattern="p"),
            MutationGeneChange(gene_name="transition_speed", old_value=0.5, new_value=0.6, operator="increase", confidence=0.7, reason="r", source_pattern="p"),
            MutationGeneChange(gene_name="reward_reveal_curve", old_value=0.5, new_value=0.6, operator="increase", confidence=0.7, reason="r", source_pattern="p"),
        ]
        plan = VisionMutationPlan(
            asset_id="asset_001",
            changes=changes,
            total_confidence=0.7,
            summary="All genes",
        )

        genome = _make_genome()
        engine = EvolutionIntegrationEngine()
        result = engine.evolve_from_vision(plan, genome)

        # All 6 genes should have changed
        assert result["genes"]["hook_contrast"] > 0.5
        assert result["genes"]["color_brightness"] > 0.5
        assert result["genes"]["color_saturation"] > 0.5
        assert result["genes"]["object_density"] < 0.5
        assert result["genes"]["transition_speed"] > 0.5
        assert result["genes"]["reward_reveal_curve"] > 0.5
        assert result["mutation_count"] == 6

    def test_serialization_roundtrip(self):
        """GenomeMutationTask serialization roundtrip."""
        mutations = [
            GeneMutation(gene_name="hook_contrast", old_value=0.5, new_value=0.65, confidence=0.8),
            GeneMutation(gene_name="color_brightness", old_value=0.5, new_value=0.7, confidence=0.7),
        ]
        task = GenomeMutationTask(
            genome_id="genome_001",
            asset_id="asset_001",
            source_plan_id="vmp_123",
            gene_mutations=mutations,
            priority="high",
            total_confidence=0.75,
            summary="Test",
        )

        d = task.to_dict()
        assert d["task_id"] == task.task_id
        assert d["genome_id"] == "genome_001"
        assert d["status"] == "pending"
        assert len(d["gene_mutations"]) == 2


# ═══════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════

class TestPackageExports:
    """包导出测试。"""

    def test_all_exports(self):
        from market_ops.creative_vision_runtime.evolution_bridge import (
            GeneMutation,
            GenomeMutationTask,
            GenomeAdapter,
            MutationExecutor,
            EvolutionIntegrationEngine,
        )
        assert GeneMutation is not None
        assert GenomeMutationTask is not None
        assert GenomeAdapter is not None
        assert MutationExecutor is not None
        assert EvolutionIntegrationEngine is not None

    def test_all_list(self):
        import market_ops.creative_vision_runtime.evolution_bridge as eb
        expected = [
            "GeneMutation",
            "GenomeMutationTask",
            "GenomeAdapter",
            "MutationExecutor",
            "EvolutionIntegrationEngine",
        ]
        for name in expected:
            assert name in eb.__all__, f"{name} missing from __all__"