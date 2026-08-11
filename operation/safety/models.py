"""
E15.2.2 — Action Safety Models

SafetyCheck evaluates a proposed monetization operation against safety rules.
SafetyResult: allowed | blocked | require_confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SafetyCheck:
    """Input to the safety layer: a proposed operation with context."""

    game_id: str
    operation: str           # e.g. "raise_bid_floor", "increase_frequency"
    provider: str            # e.g. "max", "iap"
    changes: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"floor": 35, "old_floor": 30, "ad_format": "reward"}

    # Current metrics for context
    current_metrics: Dict[str, Any] = field(default_factory=dict)
    # {"retention_d1": 0.38, "ecpm": 12.5, "revenue_daily": 340, "fill_rate": 0.92}

    # Expected impact if executed
    expected_impact: Dict[str, Any] = field(default_factory=dict)
    # {"revenue_change_pct": 10, "retention_change_pct": -2}

    # What we know from past similar operations
    past_evidence: List[Dict[str, Any]] = field(default_factory=list)

    # Rollback capability
    has_rollback: bool = False
    rollback_snapshot_id: Optional[str] = None


@dataclass
class SafetyResult:
    """Output: whether the operation is safe to execute."""

    status: str  # allowed | blocked | require_confirmation
    reason: str
    violated_rules: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    required_confirmations: List[str] = field(default_factory=list)
    rollback_required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.status == "allowed"

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def needs_confirmation(self) -> bool:
        return self.status == "require_confirmation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "violated_rules": self.violated_rules,
            "warnings": self.warnings,
            "required_confirmations": self.required_confirmations,
            "rollback_required": self.rollback_required,
            "metadata": self.metadata,
        }
