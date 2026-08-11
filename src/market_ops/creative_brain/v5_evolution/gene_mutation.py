"""V5.0 Mutation Engine — P2.1 Gene Mutation Operators.

Six gene-level mutation operators, all pure functions:
  - POINT_MUTATION: change one gene's value
  - RANDOM_RESET:   resample a gene from its mutation_pool
  - SWAP:           swap values of two genes
  - DUPLICATION:    copy a gene under a new key
  - DELETION:       remove a gene
  - INSERTION:      add a new gene from MutationRequest.new_genes

All operators are registered with mutation_registry for open-closed extension.
GeneMutationEngine is the unified entry point.
"""

from __future__ import annotations

from typing import Any

from .schemas import Gene, Genome, MutationRequest, MutationResult, MutationOperator
from .random_context import RandomContext
from .mutation_registry import register
from .constraint_validator import validate, filter_allowed_genes
from .mutation_utils import (
    clone_genome,
    build_mutation_result,
    track_gene_change,
    pick_random_gene,
    pick_random_value,
    should_mutate,
    calculate_mutation_cost,
)
from .mutation_exceptions import MutationConstraintError, MutationOperatorError


# ═══════════════════════════════════════════════════════════
# Operator: POINT_MUTATION
# ═══════════════════════════════════════════════════════════

@register("point_mutation", description="Change a single gene's value", category="gene")
def point_mutation(genome: Genome, request: MutationRequest, rng: RandomContext) -> tuple[Genome, list[dict[str, str]]]:
    """Point mutation: pick one gene and change its value."""
    cloned = clone_genome(genome, generation=genome.generation + 1)
    changes: list[dict[str, str]] = []

    # Determine candidate genes
    candidates = list(cloned.genes.keys())
    if request.target_genes:
        candidates = [k for k in candidates if k in request.target_genes]

    # Filter locked genes
    candidates = filter_allowed_genes(candidates, request.constraints)
    if not candidates:
        return cloned, changes

    gene_key = rng.choice(candidates)
    gene = cloned.genes[gene_key]
    old_value = gene.value

    # Pick new value from mutation_pool, avoiding old value if possible
    new_value = pick_random_value(gene, rng)
    if new_value == old_value and gene.mutation_pool and len(gene.mutation_pool) > 1:
        pool = [v for v in gene.mutation_pool if v != old_value]
        new_value = rng.choice(pool)

    gene.value = new_value
    track_gene_change(changes, gene_key, old_value, new_value)
    return cloned, changes


# ═══════════════════════════════════════════════════════════
# Operator: RANDOM_RESET
# ═══════════════════════════════════════════════════════════

@register("random_reset", description="Resample a gene from its mutation_pool", category="gene")
def random_reset(genome: Genome, request: MutationRequest, rng: RandomContext) -> tuple[Genome, list[dict[str, str]]]:
    """Random reset: pick a gene and replace its value with a random sample from mutation_pool."""
    cloned = clone_genome(genome, generation=genome.generation + 1)
    changes: list[dict[str, str]] = []

    candidates = list(cloned.genes.keys())
    if request.target_genes:
        candidates = [k for k in candidates if k in request.target_genes]
    candidates = filter_allowed_genes(candidates, request.constraints)
    if not candidates:
        return cloned, changes

    gene_key = rng.choice(candidates)
    gene = cloned.genes[gene_key]
    old_value = gene.value

    pool = gene.mutation_pool or []
    if not pool:
        return cloned, changes

    new_value = rng.choice(pool)
    gene.value = new_value
    track_gene_change(changes, gene_key, old_value, new_value)
    return cloned, changes


# ═══════════════════════════════════════════════════════════
# Operator: SWAP
# ═══════════════════════════════════════════════════════════

@register("swap", description="Swap values of two genes", category="gene")
def swap(genome: Genome, request: MutationRequest, rng: RandomContext) -> tuple[Genome, list[dict[str, str]]]:
    """Swap: exchange values between two distinct genes."""
    cloned = clone_genome(genome, generation=genome.generation + 1)
    changes: list[dict[str, str]] = []

    candidates = list(cloned.genes.keys())
    if request.target_genes:
        candidates = [k for k in candidates if k in request.target_genes]
    candidates = filter_allowed_genes(candidates, request.constraints)

    if len(candidates) < 2:
        return cloned, changes

    g1_key, g2_key = rng.sample(candidates, 2)
    gene1 = cloned.genes[g1_key]
    gene2 = cloned.genes[g2_key]

    old_v1, old_v2 = gene1.value, gene2.value
    gene1.value, gene2.value = old_v2, old_v1

    track_gene_change(changes, g1_key, old_v1, old_v2)
    track_gene_change(changes, g2_key, old_v2, old_v1)
    return cloned, changes


# ═══════════════════════════════════════════════════════════
# Operator: DUPLICATION
# ═══════════════════════════════════════════════════════════

@register("duplication", description="Duplicate a gene under a new key", category="gene")
def duplication(genome: Genome, request: MutationRequest, rng: RandomContext) -> tuple[Genome, list[dict[str, str]]]:
    """Duplication: copy an existing gene to a new key (e.g., hook → hook_copy)."""
    cloned = clone_genome(genome, generation=genome.generation + 1)
    changes: list[dict[str, str]] = []

    candidates = list(cloned.genes.keys())
    if request.target_genes:
        candidates = [k for k in candidates if k in request.target_genes]
    candidates = filter_allowed_genes(candidates, request.constraints)
    if not candidates:
        return cloned, changes

    source_key = rng.choice(candidates)
    source_gene = cloned.genes[source_key]

    # Generate new key
    new_key = f"{source_key}_copy"
    counter = 1
    while new_key in cloned.genes:
        new_key = f"{source_key}_copy_{counter}"
        counter += 1

    # Deep copy the gene
    import copy
    cloned.genes[new_key] = copy.deepcopy(source_gene)
    track_gene_change(changes, new_key, "", source_gene.value)
    return cloned, changes


# ═══════════════════════════════════════════════════════════
# Operator: DELETION
# ═══════════════════════════════════════════════════════════

@register("deletion", description="Remove a gene", category="gene")
def deletion(genome: Genome, request: MutationRequest, rng: RandomContext) -> tuple[Genome, list[dict[str, str]]]:
    """Deletion: remove one gene from the genome."""
    cloned = clone_genome(genome, generation=genome.generation + 1)
    changes: list[dict[str, str]] = []

    candidates = list(cloned.genes.keys())
    if request.target_genes:
        candidates = [k for k in candidates if k in request.target_genes]
    candidates = filter_allowed_genes(candidates, request.constraints)
    if not candidates:
        return cloned, changes

    gene_key = rng.choice(candidates)
    old_gene = cloned.genes.pop(gene_key)
    track_gene_change(changes, gene_key, old_gene.value, "")
    return cloned, changes


# ═══════════════════════════════════════════════════════════
# Operator: INSERTION
# ═══════════════════════════════════════════════════════════

@register("insertion", description="Insert a new gene from request.new_genes", category="gene")
def insertion(genome: Genome, request: MutationRequest, rng: RandomContext) -> tuple[Genome, list[dict[str, str]]]:
    """Insertion: add a new gene from MutationRequest.new_genes."""
    cloned = clone_genome(genome, generation=genome.generation + 1)
    changes: list[dict[str, str]] = []

    new_genes = request.new_genes or []
    if not new_genes:
        return cloned, changes

    # Pick one new gene spec
    spec = rng.choice(new_genes)
    gene_type_str = spec.get("gene_type", "custom")
    value = spec.get("value", "")
    mutation_pool = spec.get("mutation_pool", [value])

    # Check if gene_type already exists (skip if so, or create with suffix)
    gene_key = gene_type_str
    counter = 1
    while gene_key in cloned.genes:
        gene_key = f"{gene_type_str}_{counter}"
        counter += 1

    from .schemas import GeneType
    try:
        gt = GeneType(gene_type_str)
    except ValueError:
        gt = gene_type_str  # fallback to raw string for unknown gene types

    cloned.genes[gene_key] = Gene(gene_type=gt, value=value, mutation_pool=mutation_pool)
    track_gene_change(changes, gene_key, "", value)
    return cloned, changes


# ═══════════════════════════════════════════════════════════
# Gene Mutation Engine
# ═══════════════════════════════════════════════════════════

class GeneMutationEngine:
    """Unified entry point for gene-level mutations.

    Usage:
        engine = GeneMutationEngine()
        result = engine.mutate(genome, request, rng)
    """

    # Mapping from MutationOperator enum values to registry names
    _OPERATOR_MAP: dict[str, str] = {
        MutationOperator.POINT_MUTATION: "point_mutation",
        MutationOperator.RANDOM_RESET: "random_reset",
        MutationOperator.SWAP: "swap",
        MutationOperator.DUPLICATION: "duplication",
        MutationOperator.DELETION: "deletion",
        MutationOperator.INSERTION: "insertion",
    }

    def mutate(self, genome: Genome, request: MutationRequest, rng: RandomContext) -> MutationResult:
        """Execute a single gene mutation.

        Flow:
            validate request → select operator → apply → build MutationResult
        """
        # 1. Validate constraints
        errors = validate(request, genome)
        if errors:
            return build_mutation_result(
                request=request,
                original_genome=genome,
                mutated_genome=None,
                operators_used=[],
                is_valid=False,
                validation_errors=errors,
            )

        # 2. Select operator
        operator_name = self._select_operator(request, rng)
        if not operator_name:
            return build_mutation_result(
                request=request,
                original_genome=genome,
                mutated_genome=None,
                operators_used=[],
                is_valid=False,
                validation_errors=["No operator selected"],
            )

        # 3. Apply operator
        from .mutation_registry import get_operator
        try:
            op_fn = get_operator(operator_name)
        except Exception as e:
            return build_mutation_result(
                request=request,
                original_genome=genome,
                mutated_genome=None,
                operators_used=[operator_name],
                is_valid=False,
                validation_errors=[str(e)],
            )

        try:
            mutated_genome, gene_changes = op_fn(genome, request, rng)
        except Exception as e:
            return build_mutation_result(
                request=request,
                original_genome=genome,
                mutated_genome=None,
                operators_used=[operator_name],
                is_valid=False,
                validation_errors=[f"Operator '{operator_name}' failed: {e}"],
            )

        # 4. Post-mutation validation (forbidden values, required genes)
        post_errors = validate(request, mutated_genome)
        if post_errors:
            return build_mutation_result(
                request=request,
                original_genome=genome,
                mutated_genome=mutated_genome,
                operators_used=[operator_name],
                gene_changes=gene_changes,
                is_valid=False,
                validation_errors=post_errors,
            )

        # 5. Build result
        cost = calculate_mutation_cost(gene_changes)
        return build_mutation_result(
            request=request,
            original_genome=genome,
            mutated_genome=mutated_genome,
            operators_used=[operator_name],
            gene_changes=gene_changes,
            mutation_cost=cost,
            confidence=self._estimate_confidence(gene_changes, request),
        )

    def mutate_batch(self, genomes: list[Genome], request: MutationRequest, rng: RandomContext) -> list[MutationResult]:
        """Apply mutation to a batch of genomes."""
        return [self.mutate(g, request, rng) for g in genomes]

    def get_available_operators(self) -> list[str]:
        """List available gene-level operators."""
        from .mutation_registry import list_operators
        return list_operators(category="gene")

    def _select_operator(self, request: MutationRequest, rng: RandomContext) -> str | None:
        """Select an operator from request.operators, or default to point_mutation."""
        allowed = request.operators or []
        if not allowed:
            return "point_mutation"

        # Map MutationOperator enum values to registry names
        names = []
        for op in allowed:
            name = self._OPERATOR_MAP.get(op)
            if name:
                names.append(name)

        if not names:
            return None

        return rng.choice(names)

    def _estimate_confidence(self, gene_changes: list[dict[str, str]], request: MutationRequest) -> float:
        """Estimate confidence based on number of changes and temperature.

        More changes at lower temperature → lower confidence.
        """
        if not gene_changes:
            return 1.0

        # Base confidence inversely proportional to number of changes
        base = max(0.3, 1.0 - len(gene_changes) * 0.15)

        # Temperature factor: conservative (low temp) = higher confidence threshold
        temp = request.temperature
        if temp <= 0.3:
            factor = 0.9
        elif temp <= 0.7:
            factor = 1.0
        else:
            factor = 0.85  # Aggressive = slightly lower confidence

        return round(min(1.0, base * factor), 4)
