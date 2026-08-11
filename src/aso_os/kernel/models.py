"""
E16.6.14 — ASO Growth OS: core data models.

The system layer that wraps all 13 ASO modules into a unified
growth operating system. Manages state, events, workflows,
knowledge, and cross-module integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Events
# --------------------------------------------------------------------------- #
class ASOEventType(str, Enum):
    CVR_DROP = "CVR_DROP"
    RANKING_DROP = "RANKING_DROP"
    REVENUE_DROP = "REVENUE_DROP"
    COMPETITOR_CHANGE = "COMPETITOR_CHANGE"
    KEYWORD_OPPORTUNITY = "KEYWORD_OPPORTUNITY"
    SCREENSHOT_WEAK = "SCREENSHOT_WEAK"
    ICON_WEAK = "ICON_WEAK"
    LOCALIZATION_OPPORTUNITY = "LOCALIZATION_OPPORTUNITY"
    EXPERIMENT_WINNER = "EXPERIMENT_WINNER"
    EXPERIMENT_LOSER = "EXPERIMENT_LOSER"
    PATTERN_LEARNED = "PATTERN_LEARNED"
    PORTFOLIO_UPDATE = "PORTFOLIO_UPDATE"
    BUDGET_CHANGE = "BUDGET_CHANGE"


@dataclass
class ASOEvent:
    """Unified event bus message."""
    source: str  # module name
    event_type: ASOEventType
    game_id: str = ""
    market: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "event_type": self.event_type.value,
            "game_id": self.game_id,
            "market": self.market,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


# --------------------------------------------------------------------------- #
# 2. OS Kernel State
# --------------------------------------------------------------------------- #
@dataclass
class ASOOSState:
    """Current state of the ASO Growth OS."""
    game_count: int = 0
    market_count: int = 0
    active_experiments: int = 0
    pending_actions: int = 0
    knowledge_version: int = 0
    health: str = "healthy"  # healthy / degraded / error
    last_daily_run: str = ""
    updated_at: str = field(default_factory=_now_iso)


# --------------------------------------------------------------------------- #
# 3. Unified growth score
# --------------------------------------------------------------------------- #
@dataclass
class ASOGrowthScore:
    """Unified measurement for all ASO opportunities.

    ``score = revenue_impact × confidence × strategic_fit × execution_speed / risk``
    """
    opportunity_id: str
    revenue_impact: float = 0.0
    confidence: float = 0.0
    strategic_fit: float = 0.0
    execution_speed: float = 0.0
    risk: float = 1.0
    score: float = 0.0
    source: str = ""
    game_id: str = ""
    market: str = ""

    def compute(self) -> float:
        self.score = round(
            self.revenue_impact * self.confidence * self.strategic_fit
            * self.execution_speed / max(self.risk, 0.01),
            4,
        )
        return self.score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "revenue_impact": round(self.revenue_impact, 4),
            "confidence": round(self.confidence, 4),
            "strategic_fit": round(self.strategic_fit, 4),
            "execution_speed": round(self.execution_speed, 4),
            "risk": round(self.risk, 4),
            "score": self.score,
            "source": self.source,
            "game_id": self.game_id,
            "market": self.market,
        }


# --------------------------------------------------------------------------- #
# 4. Workflow stages
# --------------------------------------------------------------------------- #
class WorkflowStage(str, Enum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    PLANNED = "PLANNED"
    GENERATED = "GENERATED"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    MEASURED = "MEASURED"
    LEARNED = "LEARNED"


# --------------------------------------------------------------------------- #
# 5. Knowledge graph
# --------------------------------------------------------------------------- #
@dataclass
class KnowledgeNode:
    """A node in the ASO knowledge graph."""
    node_id: str
    node_type: str  # genre / creative_pattern / market / keyword / revenue_result
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "properties": self.properties,
            "created_at": self.created_at,
        }


@dataclass
class KnowledgeEdge:
    """A connection between two knowledge nodes."""
    edge_id: str
    source_id: str
    target_id: str
    relation: str  # "has_pattern" / "in_market" / "targets_keyword" / "yields_result"
    weight: float = 1.0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "weight": round(self.weight, 4),
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 6. Dashboard report
# --------------------------------------------------------------------------- #
@dataclass
class ASOOSDashboardReport:
    """Daily ASO Growth OS dashboard output."""

    date: str
    games_scanned: int = 0
    signals_detected: int = 0
    opportunities_created: int = 0
    actions_executed: int = 0
    experiments_running: int = 0
    patterns_learned: int = 0
    expected_revenue_impact: float = 0.0
    top_opportunities: List[ASOGrowthScore] = field(default_factory=list)
    state: Optional[ASOOSState] = None
    workflow_summary: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Growth OS Daily")
        lines.append(f"")
        lines.append(f"**Date:** {self.date}")
        if self.state:
            lines.append(f"**Portfolio:** {self.state.game_count} games")
            lines.append(f"**Active Experiments:** {self.state.active_experiments}")
        lines.append(f"")
        lines.append(f"## Summary")
        lines.append(f"- **Signals Detected:** {self.signals_detected}")
        lines.append(f"- **Opportunities Created:** {self.opportunities_created}")
        lines.append(f"- **Actions Executed:** {self.actions_executed}")
        lines.append(f"- **Patterns Learned:** {self.patterns_learned}")
        if self.expected_revenue_impact > 0:
            lines.append(f"- **Expected Revenue Impact:** +{self.expected_revenue_impact:.1%}")
        lines.append(f"")

        if self.top_opportunities:
            lines.append(f"## Top Priority")
            for i, opp in enumerate(self.top_opportunities[:3], 1):
                lines.append(f"")
                lines.append(f"### {i}. {opp.game_id} ({opp.market})")
                lines.append(f"- **Score:** {opp.score:.2f}")
                lines.append(f"- **Source:** {opp.source}")
                lines.append(f"- **Revenue Impact:** {opp.revenue_impact:.0%}")
                lines.append(f"- **Confidence:** {opp.confidence:.0%}")
                lines.append(f"")

        return "\n".join(lines)


__all__ = [
    "ASOEventType", "ASOEvent",
    "ASOOSState",
    "ASOGrowthScore",
    "WorkflowStage",
    "KnowledgeNode", "KnowledgeEdge",
    "ASOOSDashboardReport",
]
