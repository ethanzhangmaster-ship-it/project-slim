"""
E16.6.6 — ASO Revenue Attribution: data models.

Connects ASO actions to real revenue outcomes. This is the layer that
upgrades ASO from "download optimization" to "revenue optimization".

Key concepts:
  * ``ASOAcquisitionEvent`` — one ASO source (keyword, country, listing version)
  * ``ASORevenueAttribution`` — revenue assigned to an ASO source
  * ``KeywordValueScore`` — "is this keyword worth pursuing?" → commercial intent
  * ``CountryRevenueAttribution`` — country-level revenue breakdown
  * ``ASOActionReward`` — revenue-adjusted experiment reward (feeds E16.6.4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Acquisition source types
# --------------------------------------------------------------------------- #
class ASOSourceType(str, Enum):
    """Where organic traffic came from."""

    ORGANIC_SEARCH = "ORGANIC_SEARCH"
    ORGANIC_BROWSE = "ORGANIC_BROWSE"
    FEATURED = "FEATURED"


# --------------------------------------------------------------------------- #
# 2. One acquisition event
# --------------------------------------------------------------------------- #
@dataclass
class ASOAcquisitionEvent:
    """A single ASO acquisition data point — keyword/country/listing."""

    game_id: str
    platform: str
    country: str
    source_type: ASOSourceType = ASOSourceType.ORGANIC_SEARCH
    keyword: Optional[str] = None
    listing_version: str = ""
    installs: int = 0
    impressions: int = 0
    date: str = ""  # ISO date
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "platform": self.platform,
            "country": self.country,
            "source_type": self.source_type.value,
            "keyword": self.keyword,
            "listing_version": self.listing_version,
            "installs": self.installs,
            "impressions": self.impressions,
            "date": self.date,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOAcquisitionEvent":
        try:
            st = ASOSourceType(d.get("source_type", "ORGANIC_SEARCH"))
        except ValueError:
            st = ASOSourceType.ORGANIC_SEARCH
        return cls(
            game_id=d.get("game_id", ""),
            platform=d.get("platform", ""),
            country=d.get("country", ""),
            source_type=st,
            keyword=d.get("keyword"),
            listing_version=d.get("listing_version", ""),
            installs=int(d.get("installs", 0)),
            impressions=int(d.get("impressions", 0)),
            date=d.get("date", ""),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 3. Revenue attribution (per source)
# --------------------------------------------------------------------------- #
@dataclass
class ASORevenueAttribution:
    """Revenue attributed to one ASO source (keyword, country, or listing)."""

    game_id: str
    source_key: str  # e.g. "keyword:merge_magic" or "country:US"
    installs: int = 0
    payer_count: int = 0
    revenue: float = 0.0  # total attributed revenue
    dau: int = 0
    created_at: str = field(default_factory=_now_iso)

    # --- derived ---
    @property
    def arpu(self) -> float:
        return round(self.revenue / self.installs, 4) if self.installs > 0 else 0.0

    @property
    def payer_rate(self) -> float:
        return round(self.payer_count / self.installs, 4) if self.installs > 0 else 0.0

    @property
    def ltv(self) -> float:
        """Revenue per install ≈ ARPU (simplified for organic)."""
        return self.arpu

    def is_high_quality(self, payer_rate_threshold: float = 0.02) -> bool:
        """True if payer_rate indicates valuable users."""
        return self.payer_rate >= payer_rate_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "source_key": self.source_key,
            "installs": self.installs,
            "payer_count": self.payer_count,
            "revenue": round(self.revenue, 4),
            "dau": self.dau,
            "arpu": self.arpu,
            "payer_rate": self.payer_rate,
            "ltv": self.ltv,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASORevenueAttribution":
        return cls(
            game_id=d.get("game_id", ""),
            source_key=d.get("source_key", ""),
            installs=int(d.get("installs", 0)),
            payer_count=int(d.get("payer_count", 0)),
            revenue=float(d.get("revenue", 0.0)),
            dau=int(d.get("dau", 0)),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 4. Keyword commercial value
# --------------------------------------------------------------------------- #
@dataclass
class KeywordValueScore:
    """A keyword's commercial potential as an ASO target.

    ``score = search_volume × install_rate × payer_rate × ltv / competition``

    ``search_volume`` — monthly searches (raw number)
    ``install_rate``  — fraction of searchers who install (0–1)
    ``payer_rate``    — fraction of installers who pay (0–1)
    ``ltv``           — average revenue per user from this keyword
    ``competition``   — keyword difficulty (1 = extremely hard, 0.1 = easy)
    """

    keyword: str
    game_id: str
    search_volume: int = 0
    install_rate: float = 0.0
    payer_rate: float = 0.0
    ltv: float = 0.0
    competition: float = 0.5  # default medium
    score: float = 0.0
    estimated_installs: int = 0
    estimated_revenue: float = 0.0
    created_at: str = field(default_factory=_now_iso)

    def compute(self) -> float:
        """Keyword Score = Search Volume × Install Rate × Payer Rate × LTV ÷ Competition."""
        s = self.search_volume * self.install_rate * self.payer_rate * self.ltv
        self.score = round(s / max(self.competition, 0.01), 6)
        self.estimated_installs = int(self.search_volume * self.install_rate)
        self.estimated_revenue = round(
            self.estimated_installs * self.payer_rate * self.ltv, 2
        )
        return self.score

    def is_high_value(self, threshold: float = 1000.0) -> bool:
        return self.score >= threshold

    def recommendation(self) -> str:
        """Human-readable ASO action for this keyword."""
        if self.score <= 0:
            return "Remove focus — no commercial value"
        if self.score < 500:
            return "Monitor — low commercial value"
        if self.score < 5000:
            return "Maintain — moderate commercial value"
        if self.score < 50000:
            return "Increase keyword priority — high commercial value"
        return "Top priority keyword — maximize investment"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "game_id": self.game_id,
            "search_volume": self.search_volume,
            "install_rate": round(self.install_rate, 4),
            "payer_rate": round(self.payer_rate, 4),
            "ltv": round(self.ltv, 4),
            "competition": round(self.competition, 4),
            "score": round(self.score, 2),
            "estimated_installs": self.estimated_installs,
            "estimated_revenue": round(self.estimated_revenue, 2),
            "recommendation": self.recommendation(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordValueScore":
        kws = cls(
            keyword=d.get("keyword", ""),
            game_id=d.get("game_id", ""),
            search_volume=int(d.get("search_volume", 0)),
            install_rate=float(d.get("install_rate", 0.0)),
            payer_rate=float(d.get("payer_rate", 0.0)),
            ltv=float(d.get("ltv", 0.0)),
            competition=float(d.get("competition", 0.5)),
            created_at=d.get("created_at", ""),
        )
        kws.score = float(d.get("score", 0.0))
        kws.estimated_installs = int(d.get("estimated_installs", 0))
        kws.estimated_revenue = float(d.get("estimated_revenue", 0.0))
        return kws


# --------------------------------------------------------------------------- #
# 5. Country-level attribution
# --------------------------------------------------------------------------- #
@dataclass
class CountryRevenueAttribution:
    """Country-level ASO revenue breakdown."""

    country: str
    game_id: str
    installs: int = 0
    revenue: float = 0.0
    payer_count: int = 0
    dau: int = 0
    created_at: str = field(default_factory=_now_iso)

    @property
    def arpu(self) -> float:
        return round(self.revenue / self.installs, 4) if self.installs > 0 else 0.0

    @property
    def payer_rate(self) -> float:
        return round(self.payer_count / self.installs, 4) if self.installs > 0 else 0.0

    @property
    def ltv(self) -> float:
        return self.arpu

    @property
    def revenue_share(self) -> float:
        """Fraction of game's total ASO revenue (computed externally)."""
        return 0.0  # set by analyser

    def is_priority_country(self, arpu_threshold: float = 1.0) -> bool:
        """True if this country's organic users have high LTV."""
        return self.arpu >= arpu_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "game_id": self.game_id,
            "installs": self.installs,
            "revenue": round(self.revenue, 4),
            "payer_count": self.payer_count,
            "dau": self.dau,
            "arpu": self.arpu,
            "payer_rate": self.payer_rate,
            "ltv": self.ltv,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CountryRevenueAttribution":
        return cls(
            country=d.get("country", ""),
            game_id=d.get("game_id", ""),
            installs=int(d.get("installs", 0)),
            revenue=float(d.get("revenue", 0.0)),
            payer_count=int(d.get("payer_count", 0)),
            dau=int(d.get("dau", 0)),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 6. Revenue-adjusted experiment reward (feeds E16.6.4)
# --------------------------------------------------------------------------- #
@dataclass
class ASOActionReward:
    """Revenue-adjusted reward for an ASO experiment.

    ``reward = cvr_uplift × revenue_quality × ltv_multiplier``

    ``cvr_uplift``    — relative CVR change (e.g. 0.20 = +20%)
    ``revenue_quality`` — how much the revenue quality improved
                          (e.g. payer_rate_after / payer_rate_before)
    ``ltv_multiplier`` — LTV change factor (e.g. 1.15 = +15%)
    ``final_reward``  — the combined revenue-adjusted reward
    ``is_fake_growth`` — True if CVR up but quality down
    """

    experiment_id: str
    game_id: str
    cvr_uplift: float = 0.0
    revenue_quality: float = 1.0
    ltv_multiplier: float = 1.0
    final_reward: float = 0.0
    payer_rate_before: float = 0.0
    payer_rate_after: float = 0.0
    ltv_before: float = 0.0
    ltv_after: float = 0.0
    is_fake_growth: bool = False
    verdict: str = ""

    def compute(self) -> float:
        """Reward = CVR uplift × Revenue quality × LTV multiplier."""
        self.revenue_quality = (
            self.payer_rate_after / max(self.payer_rate_before, 0.001)
            if self.payer_rate_before > 0
            else 1.0
        )
        self.ltv_multiplier = (
            self.ltv_after / max(self.ltv_before, 0.001)
            if self.ltv_before > 0
            else 1.0
        )
        self.final_reward = round(
            self.cvr_uplift * self.revenue_quality * self.ltv_multiplier, 6
        )
        self.is_fake_growth = (
            self.cvr_uplift > 0
            and self.revenue_quality < 0.9  # payer rate dropped >10%
        )
        if self.is_fake_growth:
            self.verdict = (
                f"CVR +{self.cvr_uplift:.1%} but payer rate dropped "
                f"({self.payer_rate_before:.2%} → {self.payer_rate_after:.2%}) — "
                f"FAKE GROWTH, reward penalised"
            )
        elif self.final_reward > self.cvr_uplift:
            self.verdict = (
                f"Genuine growth: CVR +{self.cvr_uplift:.1%}, "
                f"revenue quality ×{self.revenue_quality:.2f}, "
                f"LTV ×{self.ltv_multiplier:.2f}, "
                f"reward +{self.final_reward:.1%}"
            )
        else:
            self.verdict = (
                f"Mixed: CVR +{self.cvr_uplift:.1%}, "
                f"reward +{self.final_reward:.1%}"
            )
        return self.final_reward

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "game_id": self.game_id,
            "cvr_uplift": round(self.cvr_uplift, 6),
            "revenue_quality": round(self.revenue_quality, 6),
            "ltv_multiplier": round(self.ltv_multiplier, 6),
            "final_reward": round(self.final_reward, 6),
            "payer_rate_before": round(self.payer_rate_before, 6),
            "payer_rate_after": round(self.payer_rate_after, 6),
            "ltv_before": round(self.ltv_before, 6),
            "ltv_after": round(self.ltv_after, 6),
            "is_fake_growth": self.is_fake_growth,
            "verdict": self.verdict,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOActionReward":
        return cls(
            experiment_id=d.get("experiment_id", ""),
            game_id=d.get("game_id", ""),
            cvr_uplift=float(d.get("cvr_uplift", 0.0)),
            revenue_quality=float(d.get("revenue_quality", 1.0)),
            ltv_multiplier=float(d.get("ltv_multiplier", 1.0)),
            final_reward=float(d.get("final_reward", 0.0)),
            payer_rate_before=float(d.get("payer_rate_before", 0.0)),
            payer_rate_after=float(d.get("payer_rate_after", 0.0)),
            ltv_before=float(d.get("ltv_before", 0.0)),
            ltv_after=float(d.get("ltv_after", 0.0)),
            is_fake_growth=bool(d.get("is_fake_growth", False)),
            verdict=d.get("verdict", ""),
        )


# --------------------------------------------------------------------------- #
# 7. Revenue report
# --------------------------------------------------------------------------- #
@dataclass
class ASORevenueReport:
    """Daily ASO revenue attribution report."""

    game_id: str
    date: str
    keyword_scores: List[KeywordValueScore] = field(default_factory=list)
    country_attributions: List[CountryRevenueAttribution] = field(default_factory=list)
    action_rewards: List[ASOActionReward] = field(default_factory=list)
    total_aso_revenue: float = 0.0
    total_payers: int = 0
    total_installs: int = 0
    created_at: str = field(default_factory=_now_iso)

    def top_keywords(self, k: int = 5) -> List[KeywordValueScore]:
        return sorted(
            self.keyword_scores, key=lambda x: x.score, reverse=True
        )[:k]

    def top_countries(self, k: int = 5) -> List[CountryRevenueAttribution]:
        return sorted(
            self.country_attributions, key=lambda x: x.revenue, reverse=True
        )[:k]

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Revenue Report")
        lines.append(f"")
        lines.append(f"**Game:** {self.game_id}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"**Total ASO Revenue:** ${self.total_aso_revenue:,.2f}")
        lines.append(f"**Total Payers:** {self.total_payers}")
        lines.append(f"**Total Installs:** {self.total_installs}")
        lines.append(f"")

        # Top revenue keywords
        lines.append(f"## Top Revenue Keywords")
        for i, kw in enumerate(self.top_keywords(5), 1):
            lines.append(f"")
            lines.append(f"### {i}. {kw.keyword}")
            lines.append(f"")
            lines.append(f"- **Score:** {kw.score:,.2f}")
            lines.append(f"- **Search Volume:** {kw.search_volume:,}")
            lines.append(f"- **Install Rate:** {kw.install_rate:.1%}")
            lines.append(f"- **Payer Rate:** {kw.payer_rate:.1%}")
            lines.append(f"- **LTV:** ${kw.ltv:.2f}")
            lines.append(f"- **Revenue:** ${kw.estimated_revenue:,.2f}")
            lines.append(f"- **Action:** {kw.recommendation()}")
            lines.append(f"")

        # Country breakdown
        lines.append(f"## Country Revenue Breakdown")
        for i, c in enumerate(self.top_countries(5), 1):
            lines.append(f"")
            lines.append(f"### {i}. {c.country}")
            lines.append(f"- **Revenue:** ${c.revenue:,.2f}")
            lines.append(f"- **Installs:** {c.installs:,}")
            lines.append(f"- **ARPUs:** ${c.arpu:.2f}")
            lines.append(f"- **Payer Rate:** {c.payer_rate:.1%}")
            action = "Increase priority" if c.is_priority_country() else "Monitor"
            lines.append(f"- **Action:** {action}")
            lines.append(f"")

        # Recent experiment rewards
        if self.action_rewards:
            lines.append(f"## Experiment Revenue Rewards")
            for r in self.action_rewards:
                label = "⚠️ FAKE GROWTH" if r.is_fake_growth else "✅ GENUINE"
                lines.append(f"")
                lines.append(f"- **{r.experiment_id}**: {label}")
                lines.append(f"  {r.verdict}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "date": self.date,
            "keyword_scores": [k.to_dict() for k in self.keyword_scores],
            "country_attributions": [c.to_dict() for c in self.country_attributions],
            "action_rewards": [r.to_dict() for r in self.action_rewards],
            "total_aso_revenue": round(self.total_aso_revenue, 2),
            "total_payers": self.total_payers,
            "total_installs": self.total_installs,
            "created_at": self.created_at,
        }


__all__ = [
    "ASOSourceType",
    "ASOAcquisitionEvent",
    "ASORevenueAttribution",
    "KeywordValueScore",
    "CountryRevenueAttribution",
    "ASOActionReward",
    "ASORevenueReport",
]
