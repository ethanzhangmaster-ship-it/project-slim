"""V5.0 Mutation Engine — Unified Exception Hierarchy.

All mutation-related errors use this hierarchy so callers can handle
them precisely without catching generic ValueError/RuntimeError.

Hierarchy:
  MutationError (base)
    ├── MutationValidationError     — constraint violation, invalid input
    ├── MutationOperatorError       — operator execution failed
    ├── MutationRegistryError       — operator not found, duplicate key
    ├── MutationReplayError         — deterministic replay mismatch
    └── MutationConstraintError     — locked gene, forbidden value, etc.
"""

from __future__ import annotations


class MutationError(Exception):
    """Base exception for all mutation engine errors."""

    def __init__(self, message: str, *, genome_id: str = "", operator: str = "", details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.genome_id = genome_id
        self.operator = operator
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "genome_id": self.genome_id,
            "operator": self.operator,
            "details": self.details,
        }


class MutationValidationError(MutationError):
    """Input validation failed (e.g., bad request, missing required fields)."""


class MutationOperatorError(MutationError):
    """A mutation operator failed during execution."""


class MutationRegistryError(MutationError):
    """Registry operation failed (operator not found, duplicate registration)."""


class MutationReplayError(MutationError):
    """Replay verification failed (deterministic mismatch)."""


class MutationConstraintError(MutationError):
    """Constraint violation (locked gene, forbidden value, missing required gene)."""
