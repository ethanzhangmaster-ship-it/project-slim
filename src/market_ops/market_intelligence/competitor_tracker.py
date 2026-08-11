"""E5.1 Market Brain — Competitor Tracker.

Tracks competitor games across the hyper-casual to mid-core spectrum:
  - Game launches and updates
  - Download/revenue trajectory
  - Creative strategy shifts (UGC, gameplay, format changes)
  - Feature additions and gameplay innovations

Output: CompetitorProfile objects with genome-level analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CompetitorTier(Enum):
    TIER_1 = "tier_1"  # Dominant players (>10M installs/mo)
    TIER_2 = "tier_2"  # Rising players (1-10M)
    TIER_3 = "tier_3"  # Niche/new entries (<1M)


@dataclass
class CompetitorProfile:
    """A tracked competitor game."""
    game_id: str = ""
    name: str = ""
    category: str = ""                  # "merge", "sort", "puzzle", etc.
    tier: CompetitorTier = CompetitorTier.TIER_3
    downloads_30d: int = 0
    revenue_30d: int = 0
    growth_30d: float = 0.0             # percentage
    ad_volume: int = 0                  # active creatives
    ad_volume_change: float = 0.0        # percentage change
    key_genes: dict[str, str] = field(default_factory=dict)  # extracted DNA
    creative_strategy: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    threat_level: float = 0.0           # 0-100
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "name": self.name,
            "category": self.category,
            "tier": self.tier.value,
            "downloads_30d": self.downloads_30d,
            "revenue_30d": self.revenue_30d,
            "growth_30d": round(self.growth_30d, 1),
            "ad_volume": self.ad_volume,
            "ad_volume_change": round(self.ad_volume_change, 1),
            "key_genes": self.key_genes,
            "creative_strategy": self.creative_strategy,
            "weaknesses": self.weaknesses,
            "opportunities": self.opportunities,
            "threat_level": round(self.threat_level, 1),
        }


class CompetitorTracker:
    """Track and analyze competitor games.

    Mock data simulates SensorTower + AppMagic + Meta Ads Library.
    Production: integrate real APIs.
    """

    MOCK_COMPETITORS: list[dict[str, Any]] = [
        {
            "name": "Merge Mansion", "category": "merge", "tier": CompetitorTier.TIER_1,
            "downloads": 5000000, "revenue": 8000000, "growth": 15,
            "ad_volume": 1200, "ad_change": 10,
            "genes": {"core_loop": "merge", "hook": "mystery", "reward": "collection", "visual": "2d_bright"},
            "strategy": ["story_narrative", "ugc_emerging"],
            "weaknesses": ["high CPI on mature accounts", "limited character variety"],
            "opportunities": ["3D visual differentiator", "character companion system"],
            "threat": 75,
        },
        {
            "name": "Goods Sort", "category": "sort", "tier": CompetitorTier.TIER_1,
            "downloads": 8000000, "revenue": 12000000, "growth": 35,
            "ad_volume": 2500, "ad_change": 45,
            "genes": {"core_loop": "sort", "hook": "mess_to_clean", "reward": "satisfaction", "visual": "3d_physics"},
            "strategy": ["gameplay_capture", "facebook_dominant"],
            "weaknesses": ["no meta-layer", "low retention after D30"],
            "opportunities": ["add collection meta", "add merge crafting layer"],
            "threat": 90,
        },
        {
            "name": "Merge Dragons", "category": "merge", "tier": CompetitorTier.TIER_1,
            "downloads": 3000000, "revenue": 15000000, "growth": 5,
            "ad_volume": 800, "ad_change": -10,
            "genes": {"core_loop": "merge", "hook": "evolution", "reward": "collection", "visual": "bright_fantasy"},
            "strategy": ["gameplay_capture", "story_progression"],
            "weaknesses": ["aging creative strategy", "high production cost"],
            "opportunities": ["cost-reduced creative format", "tiktok short-form"],
            "threat": 60,
        },
        {
            "name": "Sort Puzzle", "category": "sort", "tier": CompetitorTier.TIER_2,
            "downloads": 2000000, "revenue": 3000000, "growth": 50,
            "ad_volume": 600, "ad_change": 80,
            "genes": {"core_loop": "sort", "hook": "color_match", "reward": "completion", "visual": "3d_cartoon"},
            "strategy": ["ugc_creator", "tiktok_viral"],
            "weaknesses": ["simple retention loop", "low depth"],
            "opportunities": ["add evolution reward", "add home decoration layer"],
            "threat": 70,
        },
        {
            "name": "Tasty Travels", "category": "merge", "tier": CompetitorTier.TIER_2,
            "downloads": 1500000, "revenue": 2500000, "growth": 40,
            "ad_volume": 450, "ad_change": 55,
            "genes": {"core_loop": "merge", "hook": "build_progress", "reward": "growth", "visual": "cozy_bright"},
            "strategy": ["cozy_lifestyle", "instagram_style"],
            "weaknesses": ["narrow audience", "slow early game"],
            "opportunities": ["add collection + competition", "add rescue event"],
            "threat": 55,
        },
        {
            "name": "Simulation Sort", "category": "sort", "tier": CompetitorTier.TIER_3,
            "downloads": 500000, "revenue": 800000, "growth": 180,
            "ad_volume": 200, "ad_change": 220,
            "genes": {"core_loop": "sort", "hook": "build_progress", "reward": "evolution", "visual": "3d_cartoon"},
            "strategy": ["gameplay_demo", "tiktok_growth"],
            "weaknesses": ["new game, unproven retention", "limited content"],
            "opportunities": ["category hybridization", "rescue hook ads"],
            "threat": 40,
        },
    ]

    def scan(self) -> list[CompetitorProfile]:
        """Scan all tracked competitors."""
        return [self._build_profile(c) for c in self.MOCK_COMPETITORS]

    def get_by_category(self, category: str) -> list[CompetitorProfile]:
        """Filter competitors by category."""
        return [c for c in self.scan() if c.category == category]

    def get_top_threats(self, n: int = 5) -> list[CompetitorProfile]:
        """Get top threats by threat level."""
        return sorted(self.scan(), key=lambda c: c.threat_level, reverse=True)[:n]

    def get_rising_competitors(self, min_growth: float = 30) -> list[CompetitorProfile]:
        """Get fast-growing competitors."""
        return [c for c in self.scan() if c.growth_30d >= min_growth]

    def extract_genome_patterns(self) -> dict[str, list[dict[str, Any]]]:
        """Extract common genome patterns across competitors.

        Returns: {gene_type: [{value, count, avg_growth}]}
        """
        patterns: dict[str, dict[str, list[float]]] = {}
        for c in self.scan():
            for key, value in c.key_genes.items():
                patterns.setdefault(key, {}).setdefault(value, []).append(c.growth_30d)

        result = {}
        for gene_type, values in patterns.items():
            result[gene_type] = []
            for value, growths in values.items():
                result[gene_type].append({
                    "value": value,
                    "count": len(growths),
                    "avg_growth": round(sum(growths) / len(growths), 1),
                })
        return result

    def _build_profile(self, data: dict[str, Any]) -> CompetitorProfile:
        return CompetitorProfile(
            game_id=f"comp_{data['name'].lower().replace(' ', '_')}",
            name=data["name"],
            category=data["category"],
            tier=data["tier"],
            downloads_30d=data["downloads"],
            revenue_30d=data["revenue"],
            growth_30d=data["growth"],
            ad_volume=data["ad_volume"],
            ad_volume_change=data["ad_change"],
            key_genes=data["genes"],
            creative_strategy=data["strategy"],
            weaknesses=data["weaknesses"],
            opportunities=data["opportunities"],
            threat_level=data["threat"],
        )
