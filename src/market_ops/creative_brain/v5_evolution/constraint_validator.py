"""V5.0 Mutation Engine — Constraint Validator.

Centralized validation for all mutation constraints. No operator should
manually check constraints — call validate() before or after mutation.

Supported constraints (from MutationRequest.constraints):
  locked_genes:     list[str]            — genes that cannot be mutated
  forbidden_values: dict[str, list[str]] — {gene_type: [forbidden_values]}
  required_values:  dict[str, Any]       — {gene_type: required_exists}
  max_cost:         float                — maximum mutation cost
  max_risk:         float                — maximum risk score
  preserve_lineage: bool                 — require parent_ids to be preserved
"""

from __future__ import annotations

from typing import Any

from .schemas import Genome, MutationRequest
from .mutation_exceptions import MutationConstraintError


def validate(request: MutationRequest, genome: Genome | None = None, result: dict[str, Any] | None = None) -> list[str]:
    """Validate a mutation request (and optionally its result) against constraints.

    Returns a list of validation error messages. Empty list means all constraints pass.
    Raises MutationConstraintError if strict=True is preferred by caller.

    Args:
        request: The mutation request with constraints.
        genome:  The genome being mutated (for locked_gene / required_value checks).
        result:  The mutation result dict (for max_cost / max_risk checks).
    """
    errors: list[str] = []
    constraints = request.constraints or {}

    if not constraints:
        return errors

    # 1. locked_genes — check target_genes do not overlap
    locked_genes = constraints.get("locked_genes", [])
    target_genes = request.target_genes or []
    if locked_genes and target_genes:
        conflicts = set(locked_genes) & set(target_genes)
        if conflicts:
            errors.append(f"Locked genes cannot be mutated: {sorted(conflicts)}")

    # If genome is provided, also check that no locked gene is in genome
    if genome and locked_genes:
        for gene_key in locked_genes:
            if gene_key in genome.genes:
                # Only error if the operator would modify it
                if not target_genes or gene_key in target_genes:
                    errors.append(f"Gene '{gene_key}' is locked and cannot be mutated")

    # 2. forbidden_values — check proposed values
    forbidden = constraints.get("forbidden_values", {})
    if forbidden and genome:
        for gene_key, bad_values in forbidden.items():
            gene = genome.genes.get(gene_key)
            if gene and gene.value in bad_values:
                errors.append(f"Gene '{gene_key}' has forbidden value '{gene.value}'")

    # 3. required_values — check required genes exist
    required = constraints.get("required_values", {})
    if required and genome:
        for gene_key, _ in required.items():
            if gene_key not in genome.genes:
                errors.append(f"Required gene '{gene_key}' missing from genome")

    # 4. max_cost — check mutation cost
    max_cost = constraints.get("max_cost")
    if max_cost is not None and result is not None:
        cost = result.get("mutation_cost", 0.0)
        if cost > max_cost:
            errors.append(f"Mutation cost {cost:.4f} exceeds max_cost {max_cost}")

    # 5. max_risk — check risk score
    max_risk = constraints.get("max_risk")
    if max_risk is not None and result is not None:
        risk = result.get("risk_score", 0.0)
        if risk > max_risk:
            errors.append(f"Risk score {risk:.4f} exceeds max_risk {max_risk}")

    # 6. preserve_lineage — check parent_ids are preserved
    preserve = constraints.get("preserve_lineage", False)
    if preserve and genome and result is not None:
        mutated = result.get("mutated_genome")
        if mutated and hasattr(mutated, "parent_ids"):
            if genome.genome_id not in mutated.parent_ids:
                errors.append("Lineage preservation failed: original genome_id not in parent_ids")

    return errors


def validate_strict(request: MutationRequest, genome: Genome | None = None, result: dict[str, Any] | None = None) -> None:
    """Validate strictly: raise MutationConstraintError on any violation."""
    errors = validate(request, genome, result)
    if errors:
        raise MutationConstraintError(
            f"Constraint validation failed: {'; '.join(errors)}",
            genome_id=genome.genome_id if genome else "",
            details={"errors": errors, "constraints": request.constraints},
        )


def check_locked_gene(gene_key: str, constraints: dict[str, Any]) -> bool:
    """Quick check if a gene is locked. Returns True if locked (cannot mutate)."""
    locked = constraints.get("locked_genes", [])
    return gene_key in locked


def check_forbidden_value(gene_key: str, value: str, constraints: dict[str, Any]) -> bool:
    """Quick check if a value is forbidden for a gene. Returns True if forbidden."""
    forbidden = constraints.get("forbidden_values", {})
    return value in forbidden.get(gene_key, [])


def filter_allowed_genes(gene_keys: list[str], constraints: dict[str, Any]) -> list[str]:
    """Filter out locked genes from a list of candidate gene keys."""
    locked = set(constraints.get("locked_genes", []))
    return [k for k in gene_keys if k not in locked]
