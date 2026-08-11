"""V5.0 Phase 2.1 — Gene Mutation Release Gate (22 tests).

Validates 6 gene-level operators + GeneMutationEngine:
  - POINT_MUTATION, RANDOM_RESET, SWAP
  - DUPLICATION, DELETION, INSERTION
  - Constraint blocking, random seed replay
  - mutation_hash consistency, result tracing

All tests must PASS before P2.2 structural_mutation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.v5_evolution.schemas import (
    Gene, GeneType, Genome, MutationRequest, MutationOperator,
)
from market_ops.creative_brain.v5_evolution.random_context import RandomContext
from market_ops.creative_brain.v5_evolution.gene_mutation import (
    point_mutation, random_reset, swap, duplication, deletion, insertion,
    GeneMutationEngine,
)
from market_ops.creative_brain.v5_evolution.mutation_registry import clear_registry, is_registered
from market_ops.creative_brain.v5_evolution.mutation_exceptions import MutationConstraintError
from market_ops.creative_brain.v5_evolution.constraint_validator import validate


# Helper to build a test genome
def make_genome(**gene_kwargs) -> Genome:
    genes = {}
    for key, (gene_type, value, pool) in gene_kwargs.items():
        genes[key] = Gene(gene_type=gene_type, value=value, mutation_pool=pool)
    return Genome(genome_id="g_test", genes=genes, generation=0)


# ═══════════════════════════════════════════════════════════
# 1. Point Mutation (3 tests)
# ═══════════════════════════════════════════════════════════

def test_point_mutation_changes_value():
    """Point Mutation: gene value changes"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape", "protect"]),
    )
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.POINT_MUTATION])
    rng = RandomContext(seed=42)

    mutated, changes = point_mutation(genome, req, rng)
    assert mutated.genome_id != genome.genome_id  # cloned
    assert len(changes) == 1
    assert changes[0]["gene"] == "hook"
    assert changes[0]["old"] == "rescue"
    assert changes[0]["new"] != "rescue"
    assert mutated.genes["hook"].value == changes[0]["new"]
    # Original unchanged
    assert genome.genes["hook"].value == "rescue"
    return True


def test_point_mutation_target_genes():
    """Point Mutation: only mutates target_genes if specified"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat"]),
    )
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.POINT_MUTATION],
        target_genes=["character"],
    )
    rng = RandomContext(seed=1)

    mutated, changes = point_mutation(genome, req, rng)
    assert len(changes) == 1
    assert changes[0]["gene"] == "character"
    assert genome.genes["hook"].value == "rescue"  # unchanged
    return True


def test_point_mutation_avoids_same_value():
    """Point Mutation: avoids picking same value when pool > 1"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.POINT_MUTATION])
    # Run many times; with pool size 2, should sometimes change
    changed_count = 0
    for seed in range(100):
        rng = RandomContext(seed=seed)
        mutated, changes = point_mutation(genome, req, rng)
        if changes and changes[0]["new"] != "rescue":
            changed_count += 1
    # With 2 options and avoidance logic, almost all should change
    assert changed_count >= 80, f"Only {changed_count}/100 changed"
    return True


# ═══════════════════════════════════════════════════════════
# 2. Random Reset (2 tests)
# ═══════════════════════════════════════════════════════════

def test_random_reset_from_pool():
    """Random Reset: value comes from mutation_pool"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape", "protect"]),
    )
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.RANDOM_RESET])
    rng = RandomContext(seed=7)

    mutated, changes = random_reset(genome, req, rng)
    assert len(changes) == 1
    assert changes[0]["new"] in genome.genes["hook"].mutation_pool
    return True


def test_random_reset_respects_target():
    """Random Reset: respects target_genes"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
        emotion=(GeneType.EMOTION, "cute", ["cute", "fear"]),
    )
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.RANDOM_RESET],
        target_genes=["emotion"],
    )
    rng = RandomContext(seed=3)

    mutated, changes = random_reset(genome, req, rng)
    assert len(changes) == 1
    assert changes[0]["gene"] == "emotion"
    return True


# ═══════════════════════════════════════════════════════════
# 3. Swap (2 tests)
# ═══════════════════════════════════════════════════════════

def test_swap_two_genes():
    """Swap: exchanges values between two genes"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat"]),
    )
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.SWAP])
    rng = RandomContext(seed=5)

    mutated, changes = swap(genome, req, rng)
    assert len(changes) == 2
    assert mutated.genes["hook"].value == "dragon"
    assert mutated.genes["character"].value == "rescue"
    return True


def test_swap_noop_single_gene():
    """Swap: no-op if genome has < 2 genes"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.SWAP])
    rng = RandomContext(seed=1)

    mutated, changes = swap(genome, req, rng)
    assert len(changes) == 0
    assert mutated.genes["hook"].value == "rescue"
    return True


# ═══════════════════════════════════════════════════════════
# 4. Insertion / Deletion / Duplication (4 tests)
# ═══════════════════════════════════════════════════════════

def test_insertion_adds_gene():
    """Insertion: adds a new gene from request.new_genes"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.INSERTION],
        new_genes=[{"gene_type": "reward", "value": "coin", "mutation_pool": ["coin", "gem"]}],
    )
    rng = RandomContext(seed=1)

    mutated, changes = insertion(genome, req, rng)
    assert len(changes) == 1
    assert "reward" in mutated.genes
    assert mutated.genes["reward"].value == "coin"
    return True


def test_deletion_removes_gene():
    """Deletion: removes a gene"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat"]),
    )
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.DELETION],
        target_genes=["character"],
    )
    rng = RandomContext(seed=1)

    mutated, changes = deletion(genome, req, rng)
    assert len(changes) == 1
    assert "character" not in mutated.genes
    assert "hook" in mutated.genes
    return True


def test_duplication_copies_gene():
    """Duplication: creates a copy of a gene"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.DUPLICATION])
    rng = RandomContext(seed=1)

    mutated, changes = duplication(genome, req, rng)
    assert len(changes) == 1
    assert "hook_copy" in mutated.genes
    assert mutated.genes["hook_copy"].value == "rescue"
    # Original still there
    assert "hook" in mutated.genes
    return True


def test_insertion_suffix_when_exists():
    """Insertion: adds suffix when gene_type already exists"""
    genome = make_genome(
        reward=(GeneType.REWARD, "coin", ["coin", "gem"]),
    )
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.INSERTION],
        new_genes=[{"gene_type": "reward", "value": "star", "mutation_pool": ["star"]}],
    )
    rng = RandomContext(seed=1)

    mutated, changes = insertion(genome, req, rng)
    assert "reward_1" in mutated.genes
    assert mutated.genes["reward_1"].value == "star"
    return True


# ═══════════════════════════════════════════════════════════
# 5. Constraint Blocking (4 tests)
# ═══════════════════════════════════════════════════════════

def test_locked_gene_blocked():
    """Constraints: locked gene is not mutated"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.POINT_MUTATION],
        constraints={"locked_genes": ["hook"]},
    )
    rng = RandomContext(seed=1)

    result = engine.mutate(genome, req, rng)
    # Should still mutate (character is not locked), but never hook
    if result.is_valid and result.mutated_genome:
        for change in result.gene_changes:
            assert change["gene"] != "hook", "Locked gene was mutated"
    return True


def test_forbidden_value_post_check():
    """Constraints: mutation result with forbidden value is invalid"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape", "angry"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.POINT_MUTATION],
        constraints={"forbidden_values": {"hook": ["angry"]}},
    )

    # Try many seeds until we get "angry" or confirm it's caught
    for seed in range(200):
        rng = RandomContext(seed=seed)
        result = engine.mutate(genome, req, rng)
        if result.is_valid and result.mutated_genome:
            assert result.mutated_genome.genes["hook"].value != "angry"
        # If invalid, check it's because of forbidden value
        if not result.is_valid:
            errors_str = " ".join(result.validation_errors)
            if "forbidden" in errors_str.lower():
                break  # Found the constraint working
    else:
        # If we never hit an invalid result, that's also fine (mutation might avoid angry)
        pass
    return True


def test_required_gene_preserved():
    """Constraints: required gene prevents deletion"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.DELETION],
        constraints={"required_values": {"hook": True}},
    )
    rng = RandomContext(seed=1)

    errors = validate(req, genome)
    assert len(errors) == 0  # hook exists, so pre-check passes
    # But deletion would remove it; post-check should catch this
    mutated, changes = deletion(genome, req, rng)
    post_errors = validate(req, mutated)
    assert len(post_errors) > 0
    return True


def test_engine_returns_invalid_on_constraint_violation():
    """Engine: returns invalid MutationResult when constraints violated"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.POINT_MUTATION],
        target_genes=["hook"],
        constraints={"locked_genes": ["hook"]},
    )
    rng = RandomContext(seed=1)

    result = engine.mutate(genome, req, rng)
    assert not result.is_valid
    assert len(result.validation_errors) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 6. Random Seed Replay (3 tests)
# ═══════════════════════════════════════════════════════════

def test_same_seed_same_result():
    """Replay: same seed produces identical mutation"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape", "protect"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat", "monster"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.POINT_MUTATION],
    )

    rng1 = RandomContext(seed=12345)
    result1 = engine.mutate(genome, req, rng1)

    rng2 = RandomContext(seed=12345)
    result2 = engine.mutate(genome, req, rng2)

    assert result1.is_valid == result2.is_valid
    if result1.is_valid and result2.is_valid:
        assert result1.gene_changes == result2.gene_changes
        assert result1.mutation_hash == result2.mutation_hash
    return True


def test_different_seed_different_result():
    """Replay: different seeds produce different mutations (with high probability)"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape", "protect"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat", "monster"]),
        emotion=(GeneType.EMOTION, "cute", ["cute", "fear", "curiosity"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(
        genome_id="g_test",
        operators=[MutationOperator.POINT_MUTATION],
    )

    changes_set = set()
    for seed in range(20):
        rng = RandomContext(seed=seed)
        result = engine.mutate(genome, req, rng)
        if result.is_valid:
            changes_set.add(result.gene_changes[0]["new"] if result.gene_changes else "none")

    # With 3 genes each having 3 options, should see variety
    assert len(changes_set) >= 2, f"Only saw changes: {changes_set}"
    return True


def test_seed_determinism_across_operators():
    """Replay: same seed is deterministic for all operators"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat"]),
    )
    operators = [
        MutationOperator.POINT_MUTATION,
        MutationOperator.SWAP,
        MutationOperator.RANDOM_RESET,
    ]

    op_map = {
        MutationOperator.POINT_MUTATION: point_mutation,
        MutationOperator.SWAP: swap,
        MutationOperator.RANDOM_RESET: random_reset,
    }

    for op in operators:
        req = MutationRequest(genome_id="g_test", operators=[op])
        op_fn = op_map[op]

        rng1 = RandomContext(seed=999)
        mutated1, changes1 = op_fn(genome, req, rng1)

        rng2 = RandomContext(seed=999)
        mutated2, changes2 = op_fn(genome, req, rng2)

        assert changes1 == changes2, f"Operator {op} not deterministic"

    return True


# ═══════════════════════════════════════════════════════════
# 7. mutation_hash Consistency (2 tests)
# ═══════════════════════════════════════════════════════════

def test_hash_deterministic():
    """Hash: same input → same mutation_hash"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.POINT_MUTATION])

    rng = RandomContext(seed=42)
    result1 = engine.mutate(genome, req, rng)

    rng = RandomContext(seed=42)
    result2 = engine.mutate(genome, req, rng)

    if result1.is_valid and result2.is_valid:
        assert result1.mutation_hash == result2.mutation_hash
    return True


def test_hash_different_for_different_changes():
    """Hash: different gene changes → different mutation_hash"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape", "protect"]),
        character=(GeneType.CHARACTER, "dragon", ["dragon", "cat", "monster"]),
    )
    engine = GeneMutationEngine()

    hashes = set()
    for seed in range(10):
        req = MutationRequest(genome_id="g_test", operators=[MutationOperator.POINT_MUTATION])
        rng = RandomContext(seed=seed)
        result = engine.mutate(genome, req, rng)
        if result.is_valid:
            hashes.add(result.mutation_hash)

    # With 2 genes × 3 values, should see different hashes
    assert len(hashes) >= 2, f"Only {len(hashes)} unique hashes"
    return True


# ═══════════════════════════════════════════════════════════
# 8. MutationResult Tracing (2 tests)
# ═══════════════════════════════════════════════════════════

def test_result_has_gene_changes():
    """Result: gene_changes accurately records what changed"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.POINT_MUTATION])
    rng = RandomContext(seed=42)

    result = engine.mutate(genome, req, rng)
    assert result.is_valid
    assert len(result.gene_changes) > 0
    assert result.gene_changes[0]["old"] == "rescue"
    assert result.gene_changes[0]["new"] != "rescue"
    assert result.mutated_genome is not None
    return True


def test_result_parent_ids_preserved():
    """Result: mutated genome has original genome in parent_ids"""
    genome = make_genome(
        hook=(GeneType.HOOK, "rescue", ["rescue", "escape"]),
    )
    engine = GeneMutationEngine()
    req = MutationRequest(genome_id="g_test", operators=[MutationOperator.POINT_MUTATION])
    rng = RandomContext(seed=42)

    result = engine.mutate(genome, req, rng)
    assert result.is_valid
    assert result.mutated_genome is not None
    assert genome.genome_id in result.mutated_genome.parent_ids
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Point Mutation (3)
        ("GM: Point Mutation changes value", test_point_mutation_changes_value),
        ("GM: Point Mutation target genes", test_point_mutation_target_genes),
        ("GM: Point Mutation avoids same", test_point_mutation_avoids_same_value),
        # 2. Random Reset (2)
        ("GM: Random Reset from pool", test_random_reset_from_pool),
        ("GM: Random Reset respects target", test_random_reset_respects_target),
        # 3. Swap (2)
        ("GM: Swap two genes", test_swap_two_genes),
        ("GM: Swap no-op single gene", test_swap_noop_single_gene),
        # 4. Insert/Delete/Dup (4)
        ("GM: Insertion adds gene", test_insertion_adds_gene),
        ("GM: Deletion removes gene", test_deletion_removes_gene),
        ("GM: Duplication copies gene", test_duplication_copies_gene),
        ("GM: Insertion suffix when exists", test_insertion_suffix_when_exists),
        # 5. Constraints (4)
        ("GM: Locked gene blocked", test_locked_gene_blocked),
        ("GM: Forbidden value post check", test_forbidden_value_post_check),
        ("GM: Required gene preserved", test_required_gene_preserved),
        ("GM: Engine invalid on constraint", test_engine_returns_invalid_on_constraint_violation),
        # 6. Random Seed (3)
        ("GM: Same seed same result", test_same_seed_same_result),
        ("GM: Different seed different", test_different_seed_different_result),
        ("GM: Seed determinism all ops", test_seed_determinism_across_operators),
        # 7. Hash (2)
        ("GM: Hash deterministic", test_hash_deterministic),
        ("GM: Hash different changes", test_hash_different_for_different_changes),
        # 8. Tracing (2)
        ("GM: Result has gene changes", test_result_has_gene_changes),
        ("GM: Result parent IDs", test_result_parent_ids_preserved),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Phase 2.1 — Gene Mutation Release Gate")
    print("  22 tests")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            result = fn()
            if result:
                passed += 1
                print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    print(f"  Results: {passed}/{passed + failed} PASS")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
