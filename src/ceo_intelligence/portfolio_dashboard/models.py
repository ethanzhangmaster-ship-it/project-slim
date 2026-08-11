"""E17.10 Portfolio Dashboard — data models.

Pure dataclasses, deterministic, no LLM, no IO.
Aggregated top-down view over E17.1-E17.9 outputs for the one-person CEO:
fleet KPIs, per-game tiles, decision queue, risk flags, learned patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GameStatus(str, Enum):
    """Per-game health classification on the dashboard."""

    HEALTHY = "healthy"
    ATTENTION = "attention"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Severity of a portfolio risk flag."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def classify_game(
    *,
    confidence: float,
    daily_revenue: Optional[float],
    gate: str = "",
    at_risk: bool = False,
) -> GameStatus:
    """Deterministic per-game status.

    Rules (aligned with E17.9 ``classify_company`` / E17.1 at_risk semantics):
    - CRITICAL: at_risk from reality layer, or revenue known and <= 0,
      or the simulation gate blocked the game's top decision.
    - ATTENTION: low confidence (< 0.6) or gate == review.
    - HEALTHY: otherwise.
    """
    gate_norm = (gate or "").strip().lower()
    if at_risk or (daily_revenue is not None and daily_revenue <= 0.0) or gate_norm == "block":
        return GameStatus.CRITICAL
    if confidence < 0.6 or gate_norm == "review":
        return GameStatus.ATTENTION
    return GameStatus.HEALTHY


@dataclass
class PortfolioKPI:
    """Fleet-level aggregated KPIs."""

    total_games: int = 0
    total_daily_revenue: float = 0.0
    total_dau: int = 0
    total_spend: float = 0.0
    total_installs: int = 0
    avg_confidence: float = 0.0
    healthy_games: int = 0
    attention_games: int = 0
    critical_games: int = 0
    auto_actions: int = 0
    approval_actions: int = 0
    blocked_actions: int = 0
    expected_revenue_impact: float = 0.0
    portfolio_sim_p50: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_games": self.total_games,
            "total_daily_revenue": self.total_daily_revenue,
            "total_dau": self.total_dau,
            "total_spend": self.total_spend,
            "total_installs": self.total_installs,
            "avg_confidence": self.avg_confidence,
            "healthy_games": self.healthy_games,
            "attention_games": self.attention_games,
            "critical_games": self.critical_games,
            "auto_actions": self.auto_actions,
            "approval_actions": self.approval_actions,
            "blocked_actions": self.blocked_actions,
            "expected_revenue_impact": self.expected_revenue_impact,
            "portfolio_sim_p50": self.portfolio_sim_p50,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioKPI":
        return cls(
            total_games=int(data.get("total_games", 0)),
            total_daily_revenue=float(data.get("total_daily_revenue", 0.0)),
            total_dau=int(data.get("total_dau", 0)),
            total_spend=float(data.get("total_spend", 0.0)),
            total_installs=int(data.get("total_installs", 0)),
            avg_confidence=float(data.get("avg_confidence", 0.0)),
            healthy_games=int(data.get("healthy_games", 0)),
            attention_games=int(data.get("attention_games", 0)),
            critical_games=int(data.get("critical_games", 0)),
            auto_actions=int(data.get("auto_actions", 0)),
            approval_actions=int(data.get("approval_actions", 0)),
            blocked_actions=int(data.get("blocked_actions", 0)),
            expected_revenue_impact=float(data.get("expected_revenue_impact", 0.0)),
            portfolio_sim_p50=(
                float(data["portfolio_sim_p50"])
                if data.get("portfolio_sim_p50") is not None
                else None
            ),
        )


@dataclass
class GameTile:
    """Single-game overview tile on the dashboard."""

    game_id: str
    status: GameStatus = GameStatus.HEALTHY
    rank: int = 0
    priority_score: float = 0.0
    opportunity_type: str = ""
    top_action: str = ""
    decision_type: str = ""
    gate: str = ""
    daily_revenue: Optional[float] = None
    dau: Optional[int] = None
    roas: Optional[float] = None
    confidence: float = 0.0
    risk: float = 0.0
    expected_impact: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "status": self.status.value,
            "rank": self.rank,
            "priority_score": self.priority_score,
            "opportunity_type": self.opportunity_type,
            "top_action": self.top_action,
            "decision_type": self.decision_type,
            "gate": self.gate,
            "daily_revenue": self.daily_revenue,
            "dau": self.dau,
            "roas": self.roas,
            "confidence": self.confidence,
            "risk": self.risk,
            "expected_impact": self.expected_impact,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameTile":
        return cls(
            game_id=str(data.get("game_id", "")),
            status=GameStatus(data.get("status", GameStatus.HEALTHY.value)),
            rank=int(data.get("rank", 0)),
            priority_score=float(data.get("priority_score", 0.0)),
            opportunity_type=str(data.get("opportunity_type", "")),
            top_action=str(data.get("top_action", "")),
            decision_type=str(data.get("decision_type", "")),
            gate=str(data.get("gate", "")),
            daily_revenue=(
                float(data["daily_revenue"]) if data.get("daily_revenue") is not None else None
            ),
            dau=(int(data["dau"]) if data.get("dau") is not None else None),
            roas=(float(data["roas"]) if data.get("roas") is not None else None),
            confidence=float(data.get("confidence", 0.0)),
            risk=float(data.get("risk", 0.0)),
            expected_impact=float(data.get("expected_impact", 0.0)),
        )


@dataclass
class RiskFlag:
    """A single portfolio risk flag surfaced to the CEO."""

    level: RiskLevel
    game_id: str
    domain: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "game_id": self.game_id,
            "domain": self.domain,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskFlag":
        return cls(
            level=RiskLevel(data.get("level", RiskLevel.LOW.value)),
            game_id=str(data.get("game_id", "")),
            domain=str(data.get("domain", "")),
            reason=str(data.get("reason", "")),
        )


@dataclass
class QueueEntry:
    """One entry in the CEO decision queue (grouped by action kind)."""

    kind: str  # AUTO / APPROVAL / BLOCK (ActionKind.value from E17.9)
    game_id: str
    action: str
    detail: str = ""
    opportunity_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "game_id": self.game_id,
            "action": self.action,
            "detail": self.detail,
            "opportunity_type": self.opportunity_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueEntry":
        return cls(
            kind=str(data.get("kind", "")),
            game_id=str(data.get("game_id", "")),
            action=str(data.get("action", "")),
            detail=str(data.get("detail", "")),
            opportunity_type=str(data.get("opportunity_type", "")),
        )


@dataclass
class LearnedPattern:
    """Compact view of an E17.7 GraphPattern for dashboard display."""

    strategy_type: str
    domain: str
    action_type: str
    samples: int = 0
    success_rate: float = 0.0
    avg_revenue_delta: float = 0.0
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "domain": self.domain,
            "action_type": self.action_type,
            "samples": self.samples,
            "success_rate": self.success_rate,
            "avg_revenue_delta": self.avg_revenue_delta,
            "confidence_boost": self.confidence_boost,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedPattern":
        return cls(
            strategy_type=str(data.get("strategy_type", "")),
            domain=str(data.get("domain", "")),
            action_type=str(data.get("action_type", "")),
            samples=int(data.get("samples", 0)),
            success_rate=float(data.get("success_rate", 0.0)),
            avg_revenue_delta=float(data.get("avg_revenue_delta", 0.0)),
            confidence_boost=float(data.get("confidence_boost", 0.0)),
        )


@dataclass
class PortfolioDashboard:
    """The full portfolio dashboard document (serializable)."""

    date: str
    company_status: str = "healthy"
    kpi: PortfolioKPI = field(default_factory=PortfolioKPI)
    tiles: List[GameTile] = field(default_factory=list)
    decision_queue: List[QueueEntry] = field(default_factory=list)
    risk_flags: List[RiskFlag] = field(default_factory=list)
    learned_patterns: List[LearnedPattern] = field(default_factory=list)
    memory_summary: str = ""
    notes: List[str] = field(default_factory=list)

    def queue_by_kind(self, kind: str) -> List[QueueEntry]:
        return [entry for entry in self.decision_queue if entry.kind == kind]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "company_status": self.company_status,
            "kpi": self.kpi.to_dict(),
            "tiles": [tile.to_dict() for tile in self.tiles],
            "decision_queue": [entry.to_dict() for entry in self.decision_queue],
            "risk_flags": [flag.to_dict() for flag in self.risk_flags],
            "learned_patterns": [pattern.to_dict() for pattern in self.learned_patterns],
            "memory_summary": self.memory_summary,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioDashboard":
        return cls(
            date=str(data.get("date", "")),
            company_status=str(data.get("company_status", "healthy")),
            kpi=PortfolioKPI.from_dict(data.get("kpi", {}) or {}),
            tiles=[GameTile.from_dict(item) for item in data.get("tiles", [])],
            decision_queue=[QueueEntry.from_dict(item) for item in data.get("decision_queue", [])],
            risk_flags=[RiskFlag.from_dict(item) for item in data.get("risk_flags", [])],
            learned_patterns=[
                LearnedPattern.from_dict(item) for item in data.get("learned_patterns", [])
            ],
            memory_summary=str(data.get("memory_summary", "")),
            notes=[str(item) for item in data.get("notes", [])],
        )
