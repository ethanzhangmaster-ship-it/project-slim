"""V5.0 Mutation Engine — Operator Registry.

Implements open-closed principle: new operators are registered without
modifying the engine. All mutation operators self-register on import.

Usage:
    @register("point_mutation")
    def point_mutate(genome, request, rng):
        ...

    op = get_operator("point_mutation")
    result = op(genome, request, rng)
"""

from __future__ import annotations

from typing import Any, Callable

from .mutation_exceptions import MutationRegistryError

# Registry: operator_name → callable
_REGISTRY: dict[str, Callable[..., Any]] = {}

# Metadata: operator_name → {description, category, ...}
_METADATA: dict[str, dict[str, Any]] = {}


def register(name: str, *, description: str = "", category: str = "gene", supports_batch: bool = False) -> Callable:
    """Decorator to register a mutation operator.

    Args:
        name: Unique operator name (e.g., "point_mutation").
        description: Human-readable description.
        category: "gene" | "structural" | "crossover".
        supports_batch: Whether the operator can process a list of genomes.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in _REGISTRY:
            raise MutationRegistryError(
                f"Operator '{name}' already registered by {_REGISTRY[name].__module__}",
                operator=name,
            )
        _REGISTRY[name] = func
        _METADATA[name] = {
            "description": description,
            "category": category,
            "supports_batch": supports_batch,
            "function": f"{func.__module__}.{func.__qualname__}",
        }
        return func

    return decorator


def get_operator(name: str) -> Callable[..., Any]:
    """Get a registered operator by name."""
    if name not in _REGISTRY:
        raise MutationRegistryError(
            f"Operator '{name}' not found. Available: {list_operators()}",
            operator=name,
        )
    return _REGISTRY[name]


def list_operators(category: str | None = None) -> list[str]:
    """List all registered operator names, optionally filtered by category."""
    if category is None:
        return list(_REGISTRY.keys())
    return [name for name, meta in _METADATA.items() if meta.get("category") == category]


def get_operator_meta(name: str) -> dict[str, Any]:
    """Get metadata for a registered operator."""
    if name not in _METADATA:
        raise MutationRegistryError(f"No metadata for operator '{name}'", operator=name)
    return dict(_METADATA[name])


def get_all_metadata() -> dict[str, dict[str, Any]]:
    """Get metadata for all registered operators."""
    return {k: dict(v) for k, v in _METADATA.items()}


def unregister(name: str) -> None:
    """Remove an operator from the registry (mainly for testing)."""
    _REGISTRY.pop(name, None)
    _METADATA.pop(name, None)


def clear_registry() -> None:
    """Clear all registrations (for testing only)."""
    _REGISTRY.clear()
    _METADATA.clear()


def is_registered(name: str) -> bool:
    """Check if an operator is registered."""
    return name in _REGISTRY
