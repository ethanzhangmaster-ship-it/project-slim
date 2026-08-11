"""E10.2 Phase 5 — Optimization Exceptions."""

from __future__ import annotations


class OptimizationError(Exception):
    """Base exception for optimization engine errors."""

    def __init__(self, message: str, campaign_id: str = "") -> None:
        super().__init__(message)
        self.campaign_id = campaign_id


class PolicyViolationError(OptimizationError):
    """Budget or safety policy violation."""

    def __init__(self, message: str, campaign_id: str = "") -> None:
        super().__init__(message, campaign_id=campaign_id)


class ScaleLimitError(PolicyViolationError):
    """Scale operation exceeds safe limits."""

    def __init__(self, current: float, requested: float, limit: float, campaign_id: str = "") -> None:
        super().__init__(
            f"Cannot scale ${current:.2f} → ${requested:.2f} (limit: ${limit:.2f})",
            campaign_id=campaign_id,
        )
        self.current = current
        self.requested = requested
        self.limit = limit


class NoScorableCampaignsError(OptimizationError):
    """No campaigns available for scoring."""

    def __init__(self) -> None:
        super().__init__("No campaigns available for scoring")