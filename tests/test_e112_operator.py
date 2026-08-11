"""E11.2 Step 2 — Mutation Operator Test.

7 AC covering:
  1. REPLACE — 替换基因值
  2. ENHANCE — 增强数值型基因
  3. COMBINE — 合并两个 Genome
  4. REMOVE  — 删除基因槽位
  5. Lineage — 谱系追踪
  6. MutationResult — 变更记录
  7. Deterministic — 确定性验证
"""

from __future__ import annotations

import copy

from market_ops.e11 import (
    CreativeGenome,
    GenomeLineage,
    GenomeManager,
)
from market_ops.e11.mutation import (
    MutationType,
    MutationTarget,
    MutationRule,
    MutationResult,
    MutationOperator,
    UnsupportedMutationType,
    GeneNotFoundError,
    GeneSlotEmptyError,
    CombineSourceError,
    EnhanceNotNumericError,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_genome(genome_id: str, **overrides: dict) -> CreativeGenome:
    """创建标准测试 Genome。"""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }
    genes.update(overrides)
    return CreativeGenome(
        genome_id=genome_id,
        parent_id=None,
        generation=0,
        genes=genes,
        fitness={"ctr": 0.12, "roas_d7": 0.32},
        lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
    )


def _make_rule(
    target_gene: str,
    mutation_type: MutationType,
    strategy: str = "winner_pattern",
    priority: float = 0.8,
) -> MutationRule:
    return MutationRule(
        target_gene=target_gene,
        mutation_type=mutation_type,
        strategy=strategy,
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# AC1 — REPLACE 替换基因值
# ═══════════════════════════════════════════════════════════

def test_ac1_replace_hook():
    """AC1a: Replace hook type rescue → discovery."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, target = operator.replace(
        genome,
        gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
        confidence=0.85,
    )

    assert child.genome_id == "genome_001_v1"
    assert child.genes["hook"]["type"] == "discovery"
    assert child.genes["hook"]["strength"] == 0.90
    assert target.gene_name == "hook"
    assert target.old_value["type"] == "rescue"
    assert target.new_value["type"] == "discovery"
    assert target.confidence == 0.85


def test_ac1b_replace_preserves_other_genes():
    """AC1b: Replace only modifies target gene, others unchanged."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, _ = operator.replace(
        genome,
        gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )

    assert child.genes["visual"]["style"] == "fantasy"
    assert child.genes["reward"]["type"] == "unlock"
    assert child.genes["emotion"]["primary"] == "curiosity"
    assert child.genes["gameplay"]["mechanic"] == "merge"


def test_ac1c_replace_parent_unchanged():
    """AC1c: Parent genome is not mutated (immutable)."""
    genome = _make_genome("genome_001")
    original_hook = copy.deepcopy(genome.genes["hook"])
    operator = MutationOperator()

    child, _ = operator.replace(
        genome,
        gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )

    # 父代不变
    assert genome.genes["hook"]["type"] == original_hook["type"]
    assert genome.genes["hook"]["strength"] == original_hook["strength"]
    # 子代已变
    assert child.genes["hook"]["type"] == "discovery"


def test_ac1d_replace_via_mutate():
    """AC1d: Replace via mutate() dispatch with rule."""
    genome = _make_genome("genome_001")
    rule = _make_rule("hook", MutationType.REPLACE)
    operator = MutationOperator()

    child, result = operator.mutate(genome, rule)

    assert child.genome_id == "genome_001_v1"
    assert result.success is True
    assert result.parent_genome_id == "genome_001"
    assert result.child_genome_id == "genome_001_v1"
    assert len(result.changes) == 1


# ═══════════════════════════════════════════════════════════
# AC2 — ENHANCE 增强数值型基因
# ═══════════════════════════════════════════════════════════

def test_ac2_enhance_strength():
    """AC2a: Enhance hook.strength by 20%."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, target = operator.enhance(
        genome,
        gene_name="hook",
        boost=0.2,
        sub_field="strength",
    )

    assert child.genes["hook"]["strength"] == round(0.82 * 1.2, 4)
    assert child.genes["hook"]["type"] == "rescue"  # 非数值字段不变
    assert target.gene_name == "hook"
    assert target.old_value["strength"] == 0.82
    assert target.new_value["strength"] == round(0.82 * 1.2, 4)


def test_ac2b_enhance_all_numeric():
    """AC2b: Enhance all numeric sub-fields in a gene."""
    genome = _make_genome("genome_001")
    # hook has "strength" (numeric), "type" (str)
    operator = MutationOperator()

    child, target = operator.enhance(
        genome,
        gene_name="hook",
        boost=0.5,
    )

    # strength 增强 50%
    assert child.genes["hook"]["strength"] == round(0.82 * 1.5, 4)
    # type 是字符串，不变
    assert child.genes["hook"]["type"] == "rescue"


def test_ac2c_enhance_intensity():
    """AC2c: Enhance reward.intensity."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, target = operator.enhance(
        genome,
        gene_name="reward",
        boost=0.3,
        sub_field="intensity",
    )

    assert child.genes["reward"]["intensity"] == round(0.75 * 1.3, 4)
    assert child.genes["reward"]["type"] == "unlock"


def test_ac2d_enhance_non_numeric_raises():
    """AC2d: Enhance on non-numeric field raises error."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    try:
        operator.enhance(genome, gene_name="emotion", boost=0.2)
        assert False, "Expected EnhanceNotNumericError"
    except EnhanceNotNumericError:
        pass


def test_ac2e_enhance_empty_gene_raises():
    """AC2e: Enhance on empty gene slot raises GeneSlotEmptyError."""
    genome = _make_genome("genome_001")
    genome.genes["hook"] = {}
    operator = MutationOperator()

    try:
        operator.enhance(genome, gene_name="hook", boost=0.2)
        assert False, "Expected GeneSlotEmptyError"
    except GeneSlotEmptyError:
        pass


# ═══════════════════════════════════════════════════════════
# AC3 — COMBINE 合并两个 Genome
# ═══════════════════════════════════════════════════════════

def test_ac3_combine_two_genomes():
    """AC3a: Combine genes from source into parent."""
    genome_a = _make_genome("genome_A")
    genome_b = _make_genome("genome_B", **{
        "hook": {"type": "challenge", "strength": 0.91},
        "reward": {"type": "treasure", "intensity": 0.88},
    })

    operator = MutationOperator()

    child, targets = operator.combine(genome_a, genome_b, target_genes=["hook", "reward"])

    # 合并后基因来自 B
    assert child.genes["hook"]["type"] == "challenge"
    assert child.genes["reward"]["type"] == "treasure"
    # 未合并的基因保留 A
    assert child.genes["visual"]["style"] == "fantasy"
    assert child.genes["emotion"]["primary"] == "curiosity"
    assert len(targets) == 2


def test_ac3b_combine_all_genes():
    """AC3b: Combine all non-empty genes from source."""
    genome_a = _make_genome("genome_A")
    genome_b = _make_genome("genome_B", **{
        "hook": {"type": "challenge", "strength": 0.91},
        "visual": {"style": "realistic", "composition": "full_body"},
        "reward": {"type": "treasure", "intensity": 0.88},
        "emotion": {"primary": "excitement"},
        "gameplay": {"mechanic": "puzzle"},
    })

    operator = MutationOperator()

    child, targets = operator.combine(genome_a, genome_b)

    # 所有基因来自 B
    assert child.genes["hook"]["type"] == "challenge"
    assert child.genes["visual"]["style"] == "realistic"
    assert child.genes["reward"]["type"] == "treasure"
    assert child.genes["emotion"]["primary"] == "excitement"
    assert child.genes["gameplay"]["mechanic"] == "puzzle"
    assert len(targets) == 5


def test_ac3c_combine_no_source_raises():
    """AC3c: COMBINE via mutate() without source raises CombineSourceError."""
    genome = _make_genome("genome_001")
    rule = _make_rule("hook", MutationType.COMBINE)
    operator = MutationOperator()

    try:
        operator.mutate(genome, rule)
        assert False, "Expected CombineSourceError"
    except CombineSourceError:
        pass


def test_ac3d_combine_single_gene():
    """AC3d: Combine single gene as string."""
    genome_a = _make_genome("genome_A")
    genome_b = _make_genome("genome_B", **{
        "emotion": {"primary": "excitement"},
    })

    operator = MutationOperator()

    child, targets = operator.combine(genome_a, genome_b, target_genes="emotion")

    assert child.genes["emotion"]["primary"] == "excitement"
    assert len(targets) == 1
    assert targets[0].gene_name == "emotion"


def test_ac3e_combine_parent_unchanged():
    """AC3e: Combine does not mutate parent or source."""
    genome_a = _make_genome("genome_A")
    genome_b = _make_genome("genome_B", **{
        "hook": {"type": "challenge", "strength": 0.91},
    })

    original_a_hook = copy.deepcopy(genome_a.genes["hook"])
    original_b_hook = copy.deepcopy(genome_b.genes["hook"])

    operator = MutationOperator()
    child, _ = operator.combine(genome_a, genome_b, target_genes="hook")

    # 父代不变
    assert genome_a.genes["hook"] == original_a_hook
    assert genome_b.genes["hook"] == original_b_hook
    # 子代已变
    assert child.genes["hook"]["type"] == "challenge"


# ═══════════════════════════════════════════════════════════
# AC4 — REMOVE 删除基因槽位
# ═══════════════════════════════════════════════════════════

def test_ac4_remove_gene():
    """AC4a: Remove visual gene slot."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, targets = operator.remove(genome, gene_name="visual")

    assert child.genes["visual"] == {}
    assert len(targets) == 1
    assert targets[0].gene_name == "visual"
    assert targets[0].old_value["style"] == "fantasy"
    assert targets[0].new_value == {}


def test_ac4b_remove_preserves_other_genes():
    """AC4b: Remove only affects target gene."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, _ = operator.remove(genome, gene_name="reward")

    assert child.genes["reward"] == {}
    # 其他基因不变
    assert child.genes["hook"]["type"] == "rescue"
    assert child.genes["visual"]["style"] == "fantasy"
    assert child.genes["emotion"]["primary"] == "curiosity"
    assert child.genes["gameplay"]["mechanic"] == "merge"


def test_ac4c_remove_parent_unchanged():
    """AC4c: Remove does not mutate parent."""
    genome = _make_genome("genome_001")
    original_visual = copy.deepcopy(genome.genes["visual"])
    operator = MutationOperator()

    child, _ = operator.remove(genome, gene_name="visual")

    assert genome.genes["visual"] == original_visual
    assert child.genes["visual"] == {}


def test_ac4d_remove_via_mutate():
    """AC4d: Remove via mutate() dispatch."""
    genome = _make_genome("genome_001")
    rule = _make_rule("visual", MutationType.REMOVE)
    operator = MutationOperator()

    child, result = operator.mutate(genome, rule)

    assert child.genes["visual"] == {}
    assert result.success is True


# ═══════════════════════════════════════════════════════════
# AC5 — Lineage 谱系追踪
# ═══════════════════════════════════════════════════════════

def test_ac5_lineage_parent_id():
    """AC5a: Child has correct parent_id."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, _ = operator.replace(
        genome,
        gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )

    assert child.parent_id == "genome_001"
    assert child.generation == 1


def test_ac5b_lineage_generation_chain():
    """AC5b: Multiple mutations build correct generation chain."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    # gen1
    child1, _ = operator.replace(
        genome, gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )
    assert child1.generation == 1
    assert child1.parent_id == "genome_001"

    # gen2
    child2, _ = operator.enhance(
        child1, gene_name="reward",
        boost=0.3, sub_field="intensity",
    )
    assert child2.generation == 2
    assert child2.parent_id == "genome_001_v1"

    # gen3
    child3, _ = operator.remove(child2, gene_name="visual")
    assert child3.generation == 3
    assert child3.parent_id == "genome_001_v1_v2"


def test_ac5c_lineage_source_preserved():
    """AC5c: All descendants preserve original source."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child1, _ = operator.replace(
        genome, gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )
    child2, _ = operator.enhance(
        child1, gene_name="reward",
        boost=0.3, sub_field="intensity",
    )

    assert child1.lineage.source == "winner_001"
    assert child2.lineage.source == "winner_001"


def test_ac5d_lineage_created_by():
    """AC5d: Descendants have created_by='mutation_engine'."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child, _ = operator.replace(
        genome, gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )

    assert child.lineage.created_by == "mutation_engine"


# ═══════════════════════════════════════════════════════════
# AC6 — MutationResult 变更记录
# ═══════════════════════════════════════════════════════════

def test_ac6_result_replace():
    """AC6a: MutationResult records replace changes."""
    genome = _make_genome("genome_001")
    rule = _make_rule("hook", MutationType.REPLACE)
    operator = MutationOperator()

    child, result = operator.mutate(genome, rule)

    assert result.parent_genome_id == "genome_001"
    assert result.child_genome_id == "genome_001_v1"
    assert result.success is True
    assert len(result.changes) == 1
    assert result.changes[0].gene_name == "hook"
    assert result.mutation_id.startswith("mutation_")


def test_ac6b_result_combine():
    """AC6b: MutationResult records combine changes."""
    genome_a = _make_genome("genome_A")
    genome_b = _make_genome("genome_B", **{
        "hook": {"type": "challenge", "strength": 0.91},
        "reward": {"type": "treasure", "intensity": 0.88},
    })
    rule = _make_rule("hook", MutationType.COMBINE)
    operator = MutationOperator()

    child, result = operator.mutate(genome_a, rule, source_genome=genome_b)

    assert result.parent_genome_id == "genome_A"
    assert result.child_genome_id == "genome_A_v1"
    assert result.success is True
    assert len(result.changes) == 1
    assert result.changes[0].gene_name == "hook"


def test_ac6c_result_remove():
    """AC6c: MutationResult records remove changes."""
    genome = _make_genome("genome_001")
    rule = _make_rule("visual", MutationType.REMOVE)
    operator = MutationOperator()

    child, result = operator.mutate(genome, rule)

    assert result.changes[0].gene_name == "visual"
    assert result.changes[0].old_value["style"] == "fantasy"
    assert result.changes[0].new_value == {}


def test_ac6d_mutation_count():
    """AC6d: Mutation count increments correctly."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    assert operator.mutation_count == 0

    operator.replace(genome, gene_name="hook",
                     new_value={"type": "discovery", "strength": 0.90})
    assert operator.mutation_count == 1

    operator.enhance(genome, gene_name="reward", boost=0.3, sub_field="intensity")
    assert operator.mutation_count == 2

    other = _make_genome("genome_other")
    operator.combine(genome, other, target_genes="hook")
    assert operator.mutation_count == 3

    operator.remove(genome, gene_name="visual")
    assert operator.mutation_count == 4


# ═══════════════════════════════════════════════════════════
# AC7 — Deterministic 确定性验证
# ═══════════════════════════════════════════════════════════

def test_ac7_deterministic_replace():
    """AC7a: Same replace twice produces identical results."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child1, _ = operator.replace(
        genome, gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )
    child2, _ = operator.replace(
        genome, gene_name="hook",
        new_value={"type": "discovery", "strength": 0.90},
    )

    assert child1.genes == child2.genes
    assert child1.generation == child2.generation


def test_ac7b_deterministic_enhance():
    """AC7b: Same enhance twice produces identical results."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child1, _ = operator.enhance(genome, gene_name="hook", boost=0.3, sub_field="strength")
    child2, _ = operator.enhance(genome, gene_name="hook", boost=0.3, sub_field="strength")

    assert child1.genes == child2.genes


def test_ac7c_deterministic_combine():
    """AC7c: Same combine twice produces identical results."""
    genome_a = _make_genome("genome_A")
    genome_b = _make_genome("genome_B", **{
        "hook": {"type": "challenge", "strength": 0.91},
    })
    operator = MutationOperator()

    child1, _ = operator.combine(genome_a, genome_b, target_genes="hook")
    child2, _ = operator.combine(genome_a, genome_b, target_genes="hook")

    assert child1.genes == child2.genes


def test_ac7d_deterministic_remove():
    """AC7d: Same remove twice produces identical results."""
    genome = _make_genome("genome_001")
    operator = MutationOperator()

    child1, _ = operator.remove(genome, gene_name="visual")
    child2, _ = operator.remove(genome, gene_name="visual")

    assert child1.genes == child2.genes


def test_ac7e_deterministic_mutate():
    """AC7e: Same mutate() call twice produces identical results."""
    genome = _make_genome("genome_001")
    rule = _make_rule("hook", MutationType.REPLACE)
    operator = MutationOperator()

    child1, result1 = operator.mutate(genome, rule)
    child2, result2 = operator.mutate(genome, rule)

    assert child1.genes == child2.genes
    assert result1.success == result2.success
    # mutation_id 不同（UUID），但其他字段相同
    assert result1.parent_genome_id == result2.parent_genome_id
    assert result1.child_genome_id == result2.child_genome_id