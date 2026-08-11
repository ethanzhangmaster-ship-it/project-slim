"""
E16.6.10 — ASO Competitor War Room: data models.

Competitive intelligence layer for the ASO Agent. Tracks competitors,
detects changes, diagnoses strategy shifts, and generates counter-strategies.

Key concepts:
  * ``CompetitorSnapshot`` — state of one competitor at one point in time
  * ``CompetitorChange`` — detected change (icon / screenshot / keyword / title / ranking)
  * ``ThreatScore`` — how threatening a competitor is
  * ``CompetitorDiagnosis`` — possible explanation for competitor growth
  * ``WarRoomReport`` — daily competitive intelligence output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Change types
# --------------------------------------------------------------------------- #
class CompetitorChangeType(str, Enum):
    """Type of change detected in a competitor's store listing."""
    ICON_CHANGE = "ICON_CHANGE"
    SCREENSHOT_CHANGE = "SCREENSHOT_CHANGE"
    KEYWORD_CHANGE = "KEYWORD_CHANGE"
    TITLE_CHANGE = "TITLE_CHANGE"
    RANKING_SURGE = "RANKING_SURGE"


# --------------------------------------------------------------------------- #
# 2. Competitor snapshot — one point in time
# --------------------------------------------------------------------------- #
@dataclass
class CompetitorSnapshot:
    """State of one competitor at one collection time."""

    app_id: str
    game_category: str
    country: str
    ranking_position: int = 0
    previous_ranking: int = 0
    rating: float = 0.0
    review_count: int = 0
    title: str = ""
    description_hash: str = ""
    icon_hash: str = ""
    screenshot_hashes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    collected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "game_category": self.game_category,
            "country": self.country,
            "ranking_position": self.ranking_position,
            "previous_ranking": self.previous_ranking,
            "rating": round(self.rating, 2),
            "review_count": self.review_count,
            "title": self.title,
            "description_hash": self.description_hash,
            "icon_hash": self.icon_hash,
            "screenshot_hashes": self.screenshot_hashes,
            "keywords": self.keywords,
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompetitorSnapshot":
        return cls(
            app_id=d.get("app_id", ""),
            game_category=d.get("game_category", ""),
            country=d.get("country", ""),
            ranking_position=int(d.get("ranking_position", 0)),
            previous_ranking=int(d.get("previous_ranking", 0)),
            rating=float(d.get("rating", 0.0)),
            review_count=int(d.get("review_count", 0)),
            title=d.get("title", ""),
            description_hash=d.get("description_hash", ""),
            icon_hash=d.get("icon_hash", ""),
            screenshot_hashes=list(d.get("screenshot_hashes", [])),
            keywords=list(d.get("keywords", [])),
            collected_at=d.get("collected_at", ""),
        )


# --------------------------------------------------------------------------- #
# 3. A detected change event
# --------------------------------------------------------------------------- #
@dataclass
class CompetitorChange:
    """One detected change in a competitor's listing."""

    app_id: str
    change_type: CompetitorChangeType
    description: str = ""
    impact: str = "medium"  # high / medium / low
    confidence: float = 0.7
    old_value: str = ""
    new_value: str = ""
    detected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "change_type": self.change_type.value,
            "description": self.description,
            "impact": self.impact,
            "confidence": round(self.confidence, 4),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompetitorChange":
        return cls(
            app_id=d.get("app_id", ""),
            change_type=CompetitorChangeType(
                d.get("change_type", "ICON_CHANGE")
            ),
            description=d.get("description", ""),
            impact=d.get("impact", "medium"),
            confidence=float(d.get("confidence", 0.7)),
            old_value=d.get("old_value", ""),
            new_value=d.get("new_value", ""),
            detected_at=d.get("detected_at", ""),
        )


# --------------------------------------------------------------------------- #
# 4. Ranking velocity and threat score
# --------------------------------------------------------------------------- #
@dataclass
class RankingVelocity:
    """Speed and direction of ranking change."""

    app_id: str
    previous_rank: int
    current_rank: int
    days: int = 7
    velocity: float = 0.0  # positive = rising

    def compute(self) -> float:
        self.velocity = round(
            (self.previous_rank - self.current_rank) / max(self.days, 1), 2
        )
        return self.velocity

    def is_surge(self, threshold: float = 3.0) -> bool:
        """True if velocity exceeds threshold (ranks/day)."""
        return self.velocity >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "previous_rank": self.previous_rank,
            "current_rank": self.current_rank,
            "days": self.days,
            "velocity": self.velocity,
            "is_surge": self.is_surge(),
        }


@dataclass
class ThreatScore:
    """Overall threat level of a competitor.

    ``score = ranking_growth × revenue_potential × similarity × momentum``
    """

    app_id: str
    ranking_growth: float = 0.5  # 0–1: how much they're rising
    revenue_potential: float = 0.5  # 0–1: how much revenue they could take
    similarity: float = 0.5  # 0–1: how similar the game is to yours
    momentum: float = 0.5  # 0–1: recent momentum
    score: float = 0.0
    level: str = "medium"  # high / medium / low

    def compute(self) -> float:
        self.score = round(
            self.ranking_growth * self.revenue_potential
            * self.similarity * self.momentum,
            4,
        )
        if self.score >= 0.5:
            self.level = "high"
        elif self.score >= 0.2:
            self.level = "medium"
        else:
            self.level = "low"
        return self.score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "ranking_growth": round(self.ranking_growth, 4),
            "revenue_potential": round(self.revenue_potential, 4),
            "similarity": round(self.similarity, 4),
            "momentum": round(self.momentum, 4),
            "score": round(self.score, 4),
            "level": self.level,
        }


# --------------------------------------------------------------------------- #
# 5. Competitor diagnosis — why did they grow?
# --------------------------------------------------------------------------- #
@dataclass
class CompetitorDiagnosis:
    """Diagnosis of why a competitor is growing."""

    app_id: str
    possible_reasons: List[str] = field(default_factory=list)
    detected_changes: List[CompetitorChange] = field(default_factory=list)
    confidence: float = 0.0
    recommended_action: str = ""
    recommended_priority: str = "medium"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "possible_reasons": self.possible_reasons,
            "detected_changes": [c.to_dict() for c in self.detected_changes],
            "confidence": round(self.confidence, 4),
            "recommended_action": self.recommended_action,
            "recommended_priority": self.recommended_priority,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 6. War Room report
# --------------------------------------------------------------------------- #
@dataclass
class WarRoomReport:
    """Daily competitive intelligence report."""

    game_category: str
    date: str
    high_threat: List[Dict[str, Any]] = field(default_factory=list)
    medium_threat: List[Dict[str, Any]] = field(default_factory=list)
    low_threat: List[Dict[str, Any]] = field(default_factory=list)
    changes_detected: List[CompetitorChange] = field(default_factory=list)
    diagnoses: List[CompetitorDiagnosis] = field(default_factory=list)
    keyword_movements: List[Dict[str, Any]] = field(default_factory=list)
    patterns_learned: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Competitor War Room")
        lines.append(f"")
        lines.append(f"**Category:** {self.game_category}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"")

        # High threat
        lines.append(f"## 🔴 High Threat")
        if self.high_threat:
            for comp in self.high_threat:
                lines.append(f"")
                lines.append(f"### {comp.get('app_id', 'Unknown')}")
                lines.append(f"- **Threat Score:** {comp.get('score', 0):.2f}")
                lines.append(f"- **Ranking:** "
                             f"{comp.get('prev_rank', '?')} → {comp.get('curr_rank', '?')}")
                if comp.get('changes'):
                    lines.append(f"- **Detected Changes:**")
                    for ch in comp['changes']:
                        lines.append(f"  ✓ {ch.get('description', '')}")
                if comp.get('recommended_action'):
                    lines.append(f"- **Recommended:** {comp['recommended_action']}")
                lines.append(f"")
        else:
            lines.append(f"\nNo high-threat competitors.\n")

        # Medium threat
        lines.append(f"## 🟡 Medium Threat ({len(self.medium_threat)})")
        if self.medium_threat:
            for comp in self.medium_threat[:5]:
                lines.append(
                    f"- **{comp.get('app_id', 'Unknown')}** — "
                    f"score {comp.get('score', 0):.2f}, "
                    f"rank {comp.get('prev_rank', '?')} → {comp.get('curr_rank', '?')}"
                )
        lines.append(f"")

        # All changes
        lines.append(f"## Detected Changes ({len(self.changes_detected)})")
        for ch in self.changes_detected[:10]:
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            e = emoji.get(ch.impact, "⚪")
            lines.append(
                f"- {e} **{ch.app_id}**: {ch.description} "
                f"(conf: {ch.confidence:.0%})"
            )
        lines.append(f"")

        # Keyword movements
        if self.keyword_movements:
            lines.append(f"## Keyword Opportunities from Competitors")
            for kw in self.keyword_movements[:5]:
                lines.append(
                    f"- **{kw.get('keyword', '')}** — "
                    f"opportunity: {kw.get('opportunity', 'MEDIUM')}, "
                    f"source: {kw.get('source', '')}"
                )

        if self.patterns_learned:
            lines.append(f"\n**Patterns learned from competitors:** {self.patterns_learned}")

        return "\n".join(lines)


__all__ = [
    "CompetitorChangeType",
    "CompetitorSnapshot",
    "CompetitorChange",
    "RankingVelocity",
    "ThreatScore",
    "CompetitorDiagnosis",
    "WarRoomReport",
]
