"""
E16.6.7 — ASO Keyword Intelligence: data models.

Upgrades ASO keyword management from "find missing keywords" (E16.6.1) to
"keyword growth strategy system".

Key concepts:
  * ``KeywordReality`` — what we know about one keyword's performance
  * ``KeywordValueScore`` — commercial value (Demand × Conversion × Quality × Revenue / Competition)
  * ``KeywordPortfolioEntry`` — lifecycle stage (CORE / GROWTH / EXPERIMENTAL / DEAD)
  * ``KeywordOpportunity`` — actionable keyword target
  * ``KeywordPattern`` — learned keyword strategy (→ E16.6.4 Memory)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Portfolio lifecycle stages
# --------------------------------------------------------------------------- #
class KeywordPortfolioType(str, Enum):
    """Lifecycle stage for a keyword in the portfolio."""

    CORE = "CORE"
    GROWTH = "GROWTH"
    EXPERIMENTAL = "EXPERIMENTAL"
    DEAD = "DEAD"


OpportunityLevel = str  # "HIGH" | "MEDIUM" | "LOW"


# --------------------------------------------------------------------------- #
# 2. Keyword reality record
# --------------------------------------------------------------------------- #
@dataclass
class KeywordReality:
    """Observed reality for one keyword in one country."""

    keyword: str
    country: str
    category: str = ""
    search_volume: int = 0
    ranking_position: int = 0  # 1 = best, higher = worse; 0 = unknown
    installs: int = 0
    conversion_rate: float = 0.0
    payer_rate: float = 0.0
    ltv: float = 0.0
    revenue: float = 0.0
    competition: float = 0.5  # keyword difficulty (0–1)
    date: str = ""
    created_at: str = field(default_factory=_now_iso)

    @property
    def quality(self) -> float:
        """User quality signal = payer_rate × LTV."""
        return round(self.payer_rate * self.ltv, 6)

    @property
    def ranking_health(self) -> str:
        if self.ranking_position <= 0:
            return "unknown"
        if self.ranking_position <= 5:
            return "strong"
        if self.ranking_position <= 15:
            return "good"
        if self.ranking_position <= 30:
            return "moderate"
        return "weak"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "country": self.country,
            "category": self.category,
            "search_volume": self.search_volume,
            "ranking_position": self.ranking_position,
            "installs": self.installs,
            "conversion_rate": round(self.conversion_rate, 4),
            "payer_rate": round(self.payer_rate, 4),
            "ltv": round(self.ltv, 4),
            "revenue": round(self.revenue, 4),
            "competition": round(self.competition, 4),
            "date": self.date,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordReality":
        return cls(
            keyword=d.get("keyword", ""),
            country=d.get("country", ""),
            category=d.get("category", ""),
            search_volume=int(d.get("search_volume", 0)),
            ranking_position=int(d.get("ranking_position", 0)),
            installs=int(d.get("installs", 0)),
            conversion_rate=float(d.get("conversion_rate", 0.0)),
            payer_rate=float(d.get("payer_rate", 0.0)),
            ltv=float(d.get("ltv", 0.0)),
            revenue=float(d.get("revenue", 0.0)),
            competition=float(d.get("competition", 0.5)),
            date=d.get("date", ""),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 3. Keyword value score (commercial potential)
# --------------------------------------------------------------------------- #
@dataclass
class KeywordValueScore:
    """A keyword's commercial potential as an ASO target.

    ``score = demand × conversion × quality × revenue / competition``

    Where:
      * demand  = search_volume (raw)
      * conversion = store_cvr (0–1)
      * quality = payer_rate × LTV (user monetisation)
      * revenue = 1.0 (neutral default, can be adjusted)
      * competition = keyword difficulty (0–1, smaller = better)
    """

    keyword: str
    country: str
    demand: float = 0.0
    conversion: float = 0.0
    quality: float = 0.0  # payer_rate × ltv
    revenue_factor: float = 1.0  # additional revenue multiplier
    competition: float = 0.5
    score: float = 0.0
    estimated_revenue: float = 0.0
    estimated_installs: int = 0
    date: str = ""
    created_at: str = field(default_factory=_now_iso)

    def compute(self) -> float:
        """Score = demand × conversion × quality × revenue / competition."""
        s = (
            self.demand
            * self.conversion
            * self.quality
            * self.revenue_factor
            / max(self.competition, 0.01)
        )
        self.score = round(s, 6)
        return self.score

    def score_normalized(self, max_score: float = 100.0) -> float:
        """Normalise score to 0–100 scale (caller provides max)."""
        return round(self.score / max_score * 100.0, 1) if max_score > 0 else 0.0

    def is_high_value(self, threshold: float = 100.0) -> bool:
        return self.score >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "country": self.country,
            "demand": round(self.demand, 2),
            "conversion": round(self.conversion, 4),
            "quality": round(self.quality, 6),
            "revenue_factor": round(self.revenue_factor, 4),
            "competition": round(self.competition, 4),
            "score": round(self.score, 2),
            "estimated_revenue": round(self.estimated_revenue, 2),
            "estimated_installs": self.estimated_installs,
            "date": self.date,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordValueScore":
        kws = cls(
            keyword=d.get("keyword", ""),
            country=d.get("country", ""),
            demand=float(d.get("demand", 0.0)),
            conversion=float(d.get("conversion", 0.0)),
            quality=float(d.get("quality", 0.0)),
            revenue_factor=float(d.get("revenue_factor", 1.0)),
            competition=float(d.get("competition", 0.5)),
            date=d.get("date", ""),
            created_at=d.get("created_at", ""),
        )
        kws.score = float(d.get("score", 0.0))
        kws.estimated_revenue = float(d.get("estimated_revenue", 0.0))
        kws.estimated_installs = int(d.get("estimated_installs", 0))
        return kws


# --------------------------------------------------------------------------- #
# 4. Keyword portfolio entry
# --------------------------------------------------------------------------- #
@dataclass
class KeywordPortfolioEntry:
    """One keyword in the managed keyword portfolio."""

    keyword: str
    country: str
    portfolio_type: KeywordPortfolioType = KeywordPortfolioType.EXPERIMENTAL
    score: float = 0.0
    ranking_position: int = 0
    revenue: float = 0.0
    installs: int = 0
    ltv: float = 0.0
    reason: str = ""
    date: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "country": self.country,
            "portfolio_type": self.portfolio_type.value,
            "score": round(self.score, 2),
            "ranking_position": self.ranking_position,
            "revenue": round(self.revenue, 2),
            "installs": self.installs,
            "ltv": round(self.ltv, 4),
            "reason": self.reason,
            "date": self.date,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordPortfolioEntry":
        return cls(
            keyword=d.get("keyword", ""),
            country=d.get("country", ""),
            portfolio_type=KeywordPortfolioType(
                d.get("portfolio_type", "EXPERIMENTAL")
            ),
            score=float(d.get("score", 0.0)),
            ranking_position=int(d.get("ranking_position", 0)),
            revenue=float(d.get("revenue", 0.0)),
            installs=int(d.get("installs", 0)),
            ltv=float(d.get("ltv", 0.0)),
            reason=d.get("reason", ""),
            date=d.get("date", ""),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 5. Keyword opportunity
# --------------------------------------------------------------------------- #
@dataclass
class KeywordOpportunity:
    """An actionable keyword growth opportunity."""

    keyword: str
    country: str
    opportunity_type: str = "MEDIUM"  # HIGH / MEDIUM / LOW
    score: float = 0.0
    reason: str = ""
    action: str = "INVESTIGATE"  # ADD_KEYWORD / DEPRIORITIZE / INVESTIGATE
    expected_cvr_uplift: float = 0.0
    expected_revenue_uplift: float = 0.0
    source: str = ""  # "keyword_analysis" / "competitor_signal" / "portfolio_gap"
    date: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "country": self.country,
            "opportunity_type": self.opportunity_type,
            "score": round(self.score, 2),
            "reason": self.reason,
            "action": self.action,
            "expected_cvr_uplift": round(self.expected_cvr_uplift, 4),
            "expected_revenue_uplift": round(self.expected_revenue_uplift, 4),
            "source": self.source,
            "date": self.date,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordOpportunity":
        return cls(
            keyword=d.get("keyword", ""),
            country=d.get("country", ""),
            opportunity_type=d.get("opportunity_type", "MEDIUM"),
            score=float(d.get("score", 0.0)),
            reason=d.get("reason", ""),
            action=d.get("action", "INVESTIGATE"),
            expected_cvr_uplift=float(d.get("expected_cvr_uplift", 0.0)),
            expected_revenue_uplift=float(d.get("expected_revenue_uplift", 0.0)),
            source=d.get("source", ""),
            date=d.get("date", ""),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 6. Keyword pattern (→ E16.6.4 Memory)
# --------------------------------------------------------------------------- #
@dataclass
class KeywordPattern:
    """Learned keyword strategy pattern — what keyword traits predict success."""

    category: str
    keyword_tokens: List[str]  # e.g. ["magic", "merge"]
    avg_cvr_uplift: float = 0.0
    avg_ltv_uplift: float = 0.0
    sample_size: int = 0
    confidence: float = 0.0
    pattern_id: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "keyword_tokens": self.keyword_tokens,
            "avg_cvr_uplift": round(self.avg_cvr_uplift, 6),
            "avg_ltv_uplift": round(self.avg_ltv_uplift, 6),
            "sample_size": self.sample_size,
            "confidence": round(self.confidence, 4),
            "pattern_id": self.pattern_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordPattern":
        return cls(
            category=d.get("category", ""),
            keyword_tokens=list(d.get("keyword_tokens", [])),
            avg_cvr_uplift=float(d.get("avg_cvr_uplift", 0.0)),
            avg_ltv_uplift=float(d.get("avg_ltv_uplift", 0.0)),
            sample_size=int(d.get("sample_size", 0)),
            confidence=float(d.get("confidence", 0.0)),
            pattern_id=d.get("pattern_id", ""),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 7. Agent report
# --------------------------------------------------------------------------- #
@dataclass
class ASOKeywordReport:
    """Daily keyword intelligence report."""

    game_id: str
    date: str
    keyword_scores: List[KeywordValueScore] = field(default_factory=list)
    portfolio: List[KeywordPortfolioEntry] = field(default_factory=list)
    opportunities: List[KeywordOpportunity] = field(default_factory=list)
    patterns: List[KeywordPattern] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def top_opportunities(self, k: int = 5) -> List[KeywordOpportunity]:
        return sorted(
            self.opportunities,
            key=lambda o: o.score, reverse=True,
        )[:k]

    def portfolio_by_type(
        self, pt: KeywordPortfolioType
    ) -> List[KeywordPortfolioEntry]:
        return [e for e in self.portfolio if e.portfolio_type == pt]

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Keyword Intelligence Report")
        lines.append(f"")
        lines.append(f"**Game:** {self.game_id}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"")

        # Top opportunities
        lines.append(f"## Top Keyword Opportunities")
        top = self.top_opportunities(5)
        if not top:
            lines.append(f"\nNo keyword opportunities identified.\n")
        else:
            for i, opp in enumerate(top, 1):
                lines.append(f"")
                lines.append(f"### {i}. {opp.keyword} ({opp.country})")
                lines.append(f"")
                lines.append(f"- **Score:** {opp.score:.1f}/100")
                lines.append(f"- **Type:** {opp.opportunity_type}")
                lines.append(f"- **Reason:** {opp.reason}")
                lines.append(f"- **Action:** {opp.action}")
                if opp.expected_cvr_uplift > 0:
                    lines.append(
                        f"- **Expected:** CVR +{opp.expected_cvr_uplift:.0%}, "
                        f"Revenue +{opp.expected_revenue_uplift:.0%}"
                    )
                lines.append(f"")

        # Portfolio summary
        lines.append(f"## Keyword Portfolio")
        if self.portfolio:
            for pt in KeywordPortfolioType:
                entries = self.portfolio_by_type(pt)
                if entries:
                    lines.append(f"")
                    lines.append(f"### {pt.value} ({len(entries)})")
                    for e in entries:
                        lines.append(
                            f"- **{e.keyword}** — score {e.score:.1f}, "
                            f"rank #{e.ranking_position}, "
                            f"${e.revenue:.0f} revenue"
                        )
                    lines.append(f"")

        # Score rankings
        lines.append(f"## Keyword Score Rankings")
        for i, s in enumerate(
            sorted(self.keyword_scores, key=lambda x: x.score, reverse=True)[:10], 1
        ):
            lines.append(
                f"{i}. **{s.keyword}** — score {s.score:.1f}, "
                f"demand {s.demand:.0f}, quality {s.quality:.4f}"
            )

        # Patterns
        if self.patterns:
            lines.append(f"## Learned Keyword Patterns")
            for p in self.patterns:
                tokens = ", ".join(p.keyword_tokens)
                lines.append(
                    f"- **{p.pattern_id}**: tokens [{tokens}], "
                    f"CVR +{p.avg_cvr_uplift:.1%}, "
                    f"LTV +{p.avg_ltv_uplift:.1%}, "
                    f"n={p.sample_size}"
                )

        return "\n".join(lines)


__all__ = [
    "KeywordPortfolioType",
    "KeywordReality",
    "KeywordValueScore",
    "KeywordPortfolioEntry",
    "KeywordOpportunity",
    "KeywordPattern",
    "ASOKeywordReport",
]
