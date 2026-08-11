"""E9.9.5 → E10 API Contract — Request/Response Schemas.

Frozen API boundary types. E10 Autonomous Growth Layer
MUST use these schemas and ONLY these schemas to interact
with E9.9.5 Growth Control Plane.

All schemas are dataclass-based for type safety and JSON
serialization compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════
# API 1: get_growth_actions()
# ═══════════════════════════════════════════════════════════

@dataclass
class GrowthActionRequest:
    """Request to fetch growth actions for the current cycle.

    E10 calls this every scheduling cycle to get the list
    of actions that need execution.
    """
    request_id: str = ""
    timestamp: str = ""


@dataclass
class GrowthActionItem:
    """Single growth action for E10 execution.

    Contains all information E10 needs to execute the action:
    creative_id, action type, budget change, confidence, and reason.
    """
    creative_id: str = ""
    action: str = ""            # SCALE / KILL / WATCH / RETEST
    budget_current: float = 0.0
    budget_target: float = 0.0
    confidence: float = 0.0
    reason: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "action": self.action,
            "budget_change": {
                "current": round(self.budget_current, 2),
                "target": round(self.budget_target, 2),
            },
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
        }


@dataclass
class GrowthActionResponse:
    """Response containing all growth actions for the current cycle."""
    timestamp: str = ""
    actions: list[GrowthActionItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "actions": [a.to_dict() for a in self.actions],
        }


# ═══════════════════════════════════════════════════════════
# API 2: get_portfolio_state()
# ═══════════════════════════════════════════════════════════

@dataclass
class PortfolioPoolState:
    """State of a single portfolio pool."""
    count: int = 0
    budget: float = 0.0
    ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "budget": round(self.budget, 2),
            "ratio": round(self.ratio, 3),
        }


@dataclass
class PortfolioStateResponse:
    """Full portfolio state for E10 budget allocation."""
    exploration: PortfolioPoolState = field(default_factory=PortfolioPoolState)
    growth: PortfolioPoolState = field(default_factory=PortfolioPoolState)
    harvest: PortfolioPoolState = field(default_factory=PortfolioPoolState)
    total_budget: float = 0.0
    total_assets: int = 0
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio": {
                "exploration": self.exploration.to_dict(),
                "growth": self.growth.to_dict(),
                "harvest": self.harvest.to_dict(),
            },
            "total_budget": round(self.total_budget, 2),
            "total_assets": self.total_assets,
            "generated_at": self.generated_at,
        }


# ═══════════════════════════════════════════════════════════
# API 3: get_risk_status()
# ═══════════════════════════════════════════════════════════

@dataclass
class RiskItem:
    """Single risk dimension status."""
    type: str = ""              # BUDGET / SCALE / DIVERSITY
    level: str = ""             # SAFE / WARNING / CRITICAL
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "level": self.level,
            "detail": self.detail,
        }


@dataclass
class RiskStatusResponse:
    """E10 safety gate — if blocking=True, STOP ALL AUTOMATION."""
    blocking: bool = False
    risk_level: str = "SAFE"    # SAFE / WARNING / CRITICAL
    risks: list[RiskItem] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocking": self.blocking,
            "risk_level": self.risk_level,
            "risks": [r.to_dict() for r in self.risks],
            "generated_at": self.generated_at,
        }