"""V4.2 Cross-Country Adapter — adapts creative DNA across countries.

Answers: "If this winner works in US, what should change for JP?"

Uses:
  - Country DNA profiles (what works in each market)
  - Dimension transferability scores
  - Historical cross-country performance data
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CountryDNAProfile:
    country: str = ""
    top_characters: list[str] = field(default_factory=list)
    top_rewards: list[str] = field(default_factory=list)
    top_hooks: list[str] = field(default_factory=list)
    top_gameplays: list[str] = field(default_factory=list)
    top_styles: list[str] = field(default_factory=list)
    preferred_cameras: list[str] = field(default_factory=list)
    preferred_palettes: list[str] = field(default_factory=list)
    avg_ctr: float = 0.0
    avg_roas: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "top_characters": self.top_characters[:5],
            "top_rewards": self.top_rewards[:5],
            "top_hooks": self.top_hooks[:5],
            "top_gameplays": self.top_gameplays[:5],
            "avg_ctr": self.avg_ctr,
            "avg_roas": self.avg_roas,
            "sample_count": self.sample_count,
        }


@dataclass
class AdaptationRecommendation:
    dimension: str = ""
    current_value: str = ""
    recommended_value: str = ""
    confidence: float = 0.0
    reason: str = ""
    estimated_impact: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "estimated_impact": self.estimated_impact,
        }


@dataclass
class CrossCountryAnalysis:
    source_country: str = ""
    target_country: str = ""
    creative_id: str = ""
    keep_dimensions: list[dict[str, Any]] = field(default_factory=list)
    adapt_dimensions: list[AdaptationRecommendation] = field(default_factory=list)
    transferability_score: float = 0.0
    risk_level: str = "medium"
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_country": self.source_country,
            "target_country": self.target_country,
            "creative_id": self.creative_id,
            "keep_dimensions": self.keep_dimensions,
            "adapt_dimensions": [a.to_dict() for a in self.adapt_dimensions],
            "transferability_score": round(self.transferability_score, 3),
            "risk_level": self.risk_level,
            "summary": self.summary,
        }


class CrossCountryAdapter:
    """Adapts creative DNA from one country to another.

    Not just "change everything". Intelligently determines:
      - Which DNA dimensions are universal (keep)
      - Which DNA dimensions are country-specific (adapt)
      - Confidence level for each adaptation
    """

    # Known country preferences (can be updated from data)
    COUNTRY_PROFILES: dict[str, dict[str, Any]] = {
        "US": {
            "top_characters": ["witch", "dragon", "warrior", "princess", "robot"],
            "top_rewards": ["dragon", "treasure", "evolution", "collection", "gold"],
            "top_hooks": ["collection", "transformation", "fail", "challenge", "surprise"],
            "top_gameplays": ["merge", "puzzle", "match", "idle", "fight"],
            "top_styles": ["cartoon", "3d", "anime", "realistic", "pixel"],
            "preferred_cameras": ["45_degree", "top_down", "close_up"],
            "preferred_palettes": ["bright", "colorful", "warm"],
        },
        "JP": {
            "top_characters": ["ninja", "samurai", "anime_girl", "monster", "cat"],
            "top_rewards": ["evolution", "collection", "gacha", "treasure", "dragon"],
            "top_hooks": ["collection", "gacha", "transformation", "satisfying", "asmr"],
            "top_gameplays": ["puzzle", "rpg", "gacha", "idle", "merge"],
            "top_styles": ["anime", "chibi", "pixel", "manga", "2d"],
            "preferred_cameras": ["close_up", "side_view", "isometric"],
            "preferred_palettes": ["pastel", "vibrant", "cool"],
        },
        "KR": {
            "top_characters": ["warrior", "mage", "anime_girl", "dragon", "knight"],
            "top_rewards": ["upgrade", "evolution", "collection", "treasure", "dragon"],
            "top_hooks": ["challenge", "transformation", "collection", "fail", "surprise"],
            "top_gameplays": ["rpg", "merge", "idle", "puzzle", "fight"],
            "top_styles": ["anime", "3d", "cartoon", "realistic", "chibi"],
            "preferred_cameras": ["45_degree", "close_up", "top_down"],
            "preferred_palettes": ["vibrant", "bright", "cool"],
        },
        "UK": {
            "top_characters": ["knight", "dragon", "witch", "warrior", "princess"],
            "top_rewards": ["treasure", "dragon", "gold", "evolution", "collection"],
            "top_hooks": ["challenge", "fail", "collection", "transformation", "surprise"],
            "top_gameplays": ["merge", "puzzle", "fight", "match", "idle"],
            "top_styles": ["cartoon", "3d", "realistic", "anime", "pixel"],
            "preferred_cameras": ["45_degree", "top_down", "isometric"],
            "preferred_palettes": ["bright", "warm", "colorful"],
        },
    }

    # Dimensions that are highly country-specific (should adapt)
    COUNTRY_SPECIFIC_DIMS = {"character", "style", "palette", "hook"}

    # Dimensions that are mostly universal (can keep)
    UNIVERSAL_DIMS = {"gameplay", "reward", "camera", "composition"}

    def __init__(self, retriever=None) -> None:
        self._retriever = retriever

    def adapt(self, creative_id: str, source_country: str,
              target_country: str, dna: dict[str, Any] | None = None,
              performance: dict[str, Any] | None = None) -> CrossCountryAnalysis:
        """Adapt a creative from source_country to target_country."""
        source_profile = self.COUNTRY_PROFILES.get(source_country, {})
        target_profile = self.COUNTRY_PROFILES.get(target_country, {})

        if not source_profile or not target_profile:
            return CrossCountryAnalysis(
                source_country=source_country,
                target_country=target_country,
                creative_id=creative_id,
                transferability_score=0.0,
                risk_level="high",
                summary=f"No profile data for {source_country} or {target_country}",
            )

        dna = dna or {}
        keep = []
        adapt = []

        for dim, value in dna.items():
            if not value:
                continue

            if dim in self.UNIVERSAL_DIMS:
                keep.append({"dimension": dim, "value": value, "reason": "universal dimension"})
                continue

            if dim in self.COUNTRY_SPECIFIC_DIMS:
                target_values = target_profile.get(f"top_{dim}s", [])
                if target_values and value not in target_values:
                    rec = target_values[0] if target_values else value
                    adapt.append(AdaptationRecommendation(
                        dimension=dim,
                        current_value=str(value),
                        recommended_value=rec,
                        confidence=self._compute_adaptation_confidence(dim, value, target_values),
                        reason=f"'{value}' not in {target_country} top {dim}s",
                        estimated_impact=self._estimate_impact(dim, value, rec, target_profile),
                    ))
                else:
                    keep.append({"dimension": dim, "value": value, "reason": f"already in {target_country} top {dim}s"})
            else:
                keep.append({"dimension": dim, "value": value, "reason": "neutral dimension"})

        # Compute transferability
        total_dims = len(keep) + len(adapt)
        transferability = len(keep) / max(total_dims, 1)

        # Risk level
        if transferability >= 0.7:
            risk = "low"
        elif transferability >= 0.4:
            risk = "medium"
        else:
            risk = "high"

        # Summary
        summary = (
            f"From {source_country} to {target_country}: "
            f"Keep {len(keep)} dimensions, adapt {len(adapt)} dimensions. "
            f"Transferability: {transferability:.0%}. Risk: {risk}."
        )

        return CrossCountryAnalysis(
            source_country=source_country,
            target_country=target_country,
            creative_id=creative_id,
            keep_dimensions=keep,
            adapt_dimensions=adapt,
            transferability_score=transferability,
            risk_level=risk,
            summary=summary,
        )

    def get_country_profile(self, country: str) -> CountryDNAProfile | None:
        """Get a country's DNA profile."""
        profile = self.COUNTRY_PROFILES.get(country)
        if not profile:
            return None
        return CountryDNAProfile(
            country=country,
            top_characters=profile.get("top_characters", []),
            top_rewards=profile.get("top_rewards", []),
            top_hooks=profile.get("top_hooks", []),
            top_gameplays=profile.get("top_gameplays", []),
            top_styles=profile.get("top_styles", []),
            preferred_cameras=profile.get("preferred_cameras", []),
            preferred_palettes=profile.get("preferred_palettes", []),
        )

    def update_profile(self, country: str, creatives: list[dict[str, Any]]) -> None:
        """Update a country's profile from real performance data."""
        # In production, this would analyze actual creatives
        pass

    def _compute_adaptation_confidence(self, dim: str, current_value: str,
                                        target_values: list[str]) -> float:
        """Compute confidence for an adaptation recommendation."""
        if not target_values:
            return 0.3
        # Higher confidence if the target has clear preference
        return 0.5 + min(len(target_values) / 10, 0.4)

    def _estimate_impact(self, dim: str, current: str, recommended: str,
                         target_profile: dict[str, Any]) -> str:
        """Estimate the impact of an adaptation."""
        if dim == "character":
            return "High — character is the most country-specific dimension"
        elif dim == "style":
            return "Medium — style significantly affects local appeal"
        elif dim == "hook":
            return "Medium — hook preferences vary by market"
        return "Low — minor adjustment"