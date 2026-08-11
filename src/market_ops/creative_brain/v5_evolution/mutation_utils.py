"""V5.0 Mutation Engine — Shared Utilities.

All mutation operators use these utilities so that:
  - mutation_hash is computed consistently
  - Genome cloning is pure (original never modified)
  - Gene change tracking is standardized
  - Result building is uniform across all operators
"""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any

from .schemas import Gene, Genome, MutationRequest, MutationResult, compute_mutation_hash
from .random_context import RandomContext


def clone_genome(genome: Genome, generation: int, parent_id: str = "") -> Genome:
    """Create a deep copy of a genome for mutation.

    The original genome is never modified. The clone gets:
      - new genome_id
      - incremented generation
      - parent_ids tracking
      - fresh creation timestamp
    """
    cloned = copy.deepcopy(genome)
    cloned.genome_id = f"gen_{str(uuid.uuid4())[:8]}"
    cloned.generation = generation
    if parent_id:
        cloned.parent_ids = [parent_id]
    else:
        cloned.parent_ids = [genome.genome_id] if genome.genome_id else []
    cloned.fitness = None
    cloned.fitness_history = []
    cloned.created_at = time.time()
    return cloned


def build_mutation_result(
    *,
    request: MutationRequest,
    original_genome: Genome,
    mutated_genome: Genome | None,
    operators_used: list[str],
    gene_changes: list[dict[str, str]] | None = None,
    mutation_cost: float = 0.0,
    risk_score: float = 0.0,
    confidence: float = 0.0,
    is_valid: bool = True,
    validation_errors: list[str] | None = None,
) -> MutationResult:
    """Build a MutationResult with consistent mutation_hash computation.

    All operators MUST use this function so mutation_hash is uniform.
    """
    # Build deterministic parameters for hash
    params: dict[str, Any] = {
        "operators": operators_used,
        "gene_changes": gene_changes or [],
        "mutation_cost": mutation_cost,
    }

    m_hash = compute_mutation_hash(
        parent_genome_id=original_genome.genome_id,
        operator="|".join(operators_used),
        parameters=params,
        schema_version=original_genome.schema_version,
    )

    return MutationResult(
        request_id=request.request_id,
        original_genome_id=original_genome.genome_id,
        mutated_genome=mutated_genome,
        mutated_genes=[c["gene"] for c in (gene_changes or [])],
        gene_changes=gene_changes or [],
        operators_used=operators_used,
        mutation_hash=m_hash,
        mutation_cost=mutation_cost,
        risk_score=risk_score,
        confidence=confidence,
        is_valid=is_valid,
        validation_errors=validation_errors or [],
    )


def track_gene_change(gene_changes: list[dict[str, str]], gene_key: str, old_value: str, new_value: str) -> None:
    """Append a standardized gene change record."""
    gene_changes.append({
        "gene": gene_key,
        "old": old_value,
        "new": new_value,
    })


def pick_random_gene(genome: Genome, rng: RandomContext, exclude: list[str] | None = None) -> str | None:
    """Pick a random gene key from a genome, optionally excluding some."""
    candidates = list(genome.genes.keys())
    if exclude:
        candidates = [k for k in candidates if k not in exclude]
    if not candidates:
        return None
    return rng.choice(candidates)


def pick_random_value(gene: Gene, rng: RandomContext) -> str:
    """Pick a random value from a gene's mutation_pool."""
    pool = gene.mutation_pool or []
    if not pool:
        return gene.value
    return rng.choice(pool)


def should_mutate(rate: float, rng: RandomContext) -> bool:
    """Probabilistic decision: mutate with given rate (0-1)."""
    return rng.random() < rate


def calculate_mutation_cost(gene_changes: list[dict[str, str]], base_cost: float = 0.05) -> float:
    """Calculate mutation cost based on number of gene changes.

    Cost model: base_cost per gene change.
    Structural mutations (insert/delete) cost more.
    """
    return round(len(gene_changes) * base_cost, 4)
