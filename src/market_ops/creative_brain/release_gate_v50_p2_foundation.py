"""V5.0 Phase 2.0 — Mutation Engine Foundation Release Gate (20 tests).

Validates the 5 Foundation modules before any operator implementation:
  1. mutation_exceptions — unified error hierarchy
  2. random_context — deterministic random number generation
  3. mutation_registry — operator registration (open-closed)
  4. constraint_validator — centralized constraint checking
  5. mutation_utils — pure functions for clone/hash/result/build

All tests must PASS before P2.1 gene_mutation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.v5_evolution.schemas import (
    Gene, GeneType, Genome, MutationRequest, MutationResult, MutationOperator,
)
from market_ops.creative_brain.v5_evolution.mutation_exceptions import (
    MutationError,
    MutationValidationError,
    MutationOperatorError,
    MutationRegistryError,
    MutationReplayError,
    MutationConstraintError,
)
from market_ops.creative_brain.v5_evolution.random_context import RandomContext, with_seed
from market_ops.creative_brain.v5_evolution import mutation_registry as registry
from market_ops.creative_brain.v5_evolution.constraint_validator import (
    validate, validate_strict, check_locked_gene, check_forbidden_value, filter_allowed_genes,
)
from market_ops.creative_brain.v5_evolution.mutation_utils import (
    clone_genome, build_mutation_result, track_gene_change,
    pick_random_gene, pick_random_value, should_mutate, calculate_mutation_cost,
)


# ═══════════════════════════════════════════════════════════
# 1. mutation_exceptions (4 tests)
# ═══════════════════════════════════════════════════════════

def test_exc_base_to_dict():
    """Exceptions: base class serializes to dict"""
    e = MutationError("test", genome_id="g1", operator="op", details={"k": 1})
    d = e.to_dict()
    assert d["error_type"] == "MutationError"
    assert d["message"] == "test"
    assert d["genome_id"] == "g1"
    assert d["operator"] == "op"
    assert d["details"]["k"] == 1
    return True


def test_exc_hierarchy_isinstance():
    """Exceptions: all subclasses are MutationError instances"""
    assert isinstance(MutationValidationError("v"), MutationError)
    assert isinstance(MutationOperatorError("o"), MutationError)
    assert isinstance(MutationRegistryError("r"), MutationError)
    assert isinstance(MutationReplayError("rp"), MutationError)
    assert isinstance(MutationConstraintError("c"), MutationError)
    return True


def test_exc_constraint_details():
    """Exceptions: constraint error carries details"""
    e = MutationConstraintError("locked", genome_id="g1", details={"errors": ["e1"]})
    assert e.genome_id == "g1"
    assert e.details["errors"] == ["e1"]
    return True


def test_exc_str_message():
    """Exceptions: str() returns message"""
    e = MutationValidationError("bad input")
    assert str(e) == "bad input"
    return True


# ═══════════════════════════════════════════════════════════
# 2. random_context (4 tests)
# ═══════════════════════════════════════════════════════════

def test_rng_seed_determinism():
    """RandomContext: same seed → same sequence"""
    rng1 = RandomContext(seed=42)
    rng2 = RandomContext(seed=42)
    seq1 = [rng1.randint(0, 100) for _ in range(10)]
    seq2 = [rng2.randint(0, 100) for _ in range(10)]
    assert seq1 == seq2
    return True


def test_rng_different_seeds():
    """RandomContext: different seeds → different sequences (with high probability)"""
    rng1 = RandomContext(seed=1)
    rng2 = RandomContext(seed=2)
    seq1 = [rng1.random() for _ in range(5)]
    seq2 = [rng2.random() for _ in range(5)]
    assert seq1 != seq2
    return True


def test_rng_choice_empty_raises():
    """RandomContext: choice on empty sequence raises IndexError"""
    rng = RandomContext(seed=1)
    try:
        rng.choice([])
        assert False, "Should have raised"
    except IndexError:
        pass
    return True


def test_rng_with_seed_context_manager():
    """RandomContext: context manager yields usable rng"""
    with with_seed(seed=99) as rng:
        v = rng.randint(0, 10)
        assert 0 <= v <= 10
    return True


# ═══════════════════════════════════════════════════════════
# 3. mutation_registry (4 tests)
# ═══════════════════════════════════════════════════════════

def test_registry_register_and_get():
    """Registry: register and retrieve operator"""
    registry.clear_registry()

    @registry.register("test_op", description="test", category="gene")
    def test_op_fn(*args, **kwargs):
        return "ok"

    op = registry.get_operator("test_op")
    assert op() == "ok"

    registry.unregister("test_op")
    return True


def test_registry_duplicate_raises():
    """Registry: duplicate registration raises MutationRegistryError"""
    registry.clear_registry()

    @registry.register("dup_op")
    def dup_op_fn():
        pass

    try:
        @registry.register("dup_op")
        def dup_op_fn2():
            pass
        assert False, "Should have raised"
    except MutationRegistryError:
        pass

    registry.clear_registry()
    return True


def test_registry_list_and_meta():
    """Registry: list operators and get metadata"""
    registry.clear_registry()

    @registry.register("op_a", description="A", category="gene")
    def op_a():
        pass

    @registry.register("op_b", description="B", category="structural")
    def op_b():
        pass

    all_ops = registry.list_operators()
    assert "op_a" in all_ops
    assert "op_b" in all_ops

    gene_ops = registry.list_operators(category="gene")
    assert "op_a" in gene_ops
    assert "op_b" not in gene_ops

    meta = registry.get_operator_meta("op_a")
    assert meta["description"] == "A"
    assert meta["category"] == "gene"

    registry.clear_registry()
    return True


def test_registry_not_found():
    """Registry: getting unregistered operator raises"""
    registry.clear_registry()
    try:
        registry.get_operator("nonexistent")
        assert False, "Should have raised"
    except MutationRegistryError:
        pass
    return True


# ═══════════════════════════════════════════════════════════
# 4. constraint_validator (4 tests)
# ═══════════════════════════════════════════════════════════

def test_validator_locked_gene():
    """Validator: locked gene conflict detected"""
    genome = Genome(genome_id="g1", genes={"hook": Gene(gene_type=GeneType.HOOK, value="rescue")})
    req = MutationRequest(
        genome_id="g1",
        target_genes=["hook"],
        constraints={"locked_genes": ["hook"]},
    )
    errors = validate(req, genome)
    assert len(errors) > 0
    assert "locked" in errors[0].lower()
    return True


def test_validator_forbidden_value():
    """Validator: forbidden value detected"""
    genome = Genome(genome_id="g1", genes={"hook": Gene(gene_type=GeneType.HOOK, value="angry")})
    req = MutationRequest(
        genome_id="g1",
        constraints={"forbidden_values": {"hook": ["angry", "violent"]}},
    )
    errors = validate(req, genome)
    assert len(errors) > 0
    assert "forbidden" in errors[0].lower()
    return True


def test_validator_required_gene_missing():
    """Validator: required gene missing detected"""
    genome = Genome(genome_id="g1", genes={"hook": Gene(gene_type=GeneType.HOOK, value="rescue")})
    req = MutationRequest(
        genome_id="g1",
        constraints={"required_values": {"reward": True}},
    )
    errors = validate(req, genome)
    assert len(errors) > 0
    assert "required" in errors[0].lower()
    return True


def test_validator_strict_raises():
    """Validator: validate_strict raises MutationConstraintError"""
    genome = Genome(genome_id="g1", genes={"hook": Gene(gene_type=GeneType.HOOK, value="rescue")})
    req = MutationRequest(
        genome_id="g1",
        target_genes=["hook"],
        constraints={"locked_genes": ["hook"]},
    )
    try:
        validate_strict(req, genome)
        assert False, "Should have raised"
    except MutationConstraintError:
        pass
    return True


# ═══════════════════════════════════════════════════════════
# 5. mutation_utils (4 tests)
# ═══════════════════════════════════════════════════════════

def test_utils_clone_genome_pure():
    """Utils: clone_genome does not modify original"""
    g1 = Genome(genome_id="orig", genes={"hook": Gene(gene_type=GeneType.HOOK, value="rescue")})
    g2 = clone_genome(g1, generation=1)

    assert g1.genome_id == "orig"
    assert g2.genome_id != "orig"
    assert g2.generation == 1
    assert g1.genome_id in g2.parent_ids or "orig" in g2.parent_ids
    assert g2.fitness is None
    return True


def test_utils_build_mutation_result_hash():
    """Utils: build_mutation_result computes deterministic mutation_hash"""
    genome = Genome(genome_id="g1", genes={"hook": Gene(gene_type=GeneType.HOOK, value="rescue")})
    req = MutationRequest(genome_id="g1")

    result1 = build_mutation_result(
        request=req, original_genome=genome, mutated_genome=None,
        operators_used=["point_mutation"], gene_changes=[{"gene": "hook", "old": "rescue", "new": "escape"}],
    )
    result2 = build_mutation_result(
        request=req, original_genome=genome, mutated_genome=None,
        operators_used=["point_mutation"], gene_changes=[{"gene": "hook", "old": "rescue", "new": "escape"}],
    )

    assert result1.mutation_hash == result2.mutation_hash
    assert result1.mutation_hash != ""
    assert len(result1.mutation_hash) == 16
    return True


def test_utils_track_gene_change():
    """Utils: track_gene_change appends standardized record"""
    changes = []
    track_gene_change(changes, "hook", "rescue", "escape")
    assert len(changes) == 1
    assert changes[0] == {"gene": "hook", "old": "rescue", "new": "escape"}
    return True


def test_utils_should_mutate_deterministic():
    """Utils: should_mutate is deterministic with fixed seed"""
    rng1 = RandomContext(seed=123)
    rng2 = RandomContext(seed=123)

    results1 = [should_mutate(0.5, rng1) for _ in range(20)]
    results2 = [should_mutate(0.5, rng2) for _ in range(20)]
    assert results1 == results2
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. mutation_exceptions (4)
        ("Exc: Base to_dict", test_exc_base_to_dict),
        ("Exc: Hierarchy isinstance", test_exc_hierarchy_isinstance),
        ("Exc: Constraint details", test_exc_constraint_details),
        ("Exc: str message", test_exc_str_message),
        # 2. random_context (4)
        ("RNG: Seed determinism", test_rng_seed_determinism),
        ("RNG: Different seeds", test_rng_different_seeds),
        ("RNG: Choice empty raises", test_rng_choice_empty_raises),
        ("RNG: with_seed context", test_rng_with_seed_context_manager),
        # 3. mutation_registry (4)
        ("Reg: Register and get", test_registry_register_and_get),
        ("Reg: Duplicate raises", test_registry_duplicate_raises),
        ("Reg: List and meta", test_registry_list_and_meta),
        ("Reg: Not found", test_registry_not_found),
        # 4. constraint_validator (4)
        ("Val: Locked gene", test_validator_locked_gene),
        ("Val: Forbidden value", test_validator_forbidden_value),
        ("Val: Required gene missing", test_validator_required_gene_missing),
        ("Val: Strict raises", test_validator_strict_raises),
        # 5. mutation_utils (4)
        ("Util: Clone pure", test_utils_clone_genome_pure),
        ("Util: Build result hash", test_utils_build_mutation_result_hash),
        ("Util: Track change", test_utils_track_gene_change),
        ("Util: Should mutate deterministic", test_utils_should_mutate_deterministic),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Phase 2.0 — Foundation Release Gate")
    print("  20 tests")
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
