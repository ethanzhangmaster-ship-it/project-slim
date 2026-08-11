"""E5.1 Market Brain — Category Heatmap.

Visualizes market heat across game categories:
  - Which categories are hot/cold
  - Competition density per category
  - Opportunity gap scoring
  - Cross-category hybridization potential
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CategoryCell:
    """A single cell in the heatmap — one game category."""
    category: str = ""
    market_heat: float = 0.0         # 0-100, how hot is the market
    competition_density: float = 0.0  # 0-100, how crowded
    opportunity_gap: float = 0.0      # 0-100, how much untapped space
    growth_trajectory: str = ""       # "accelerating", "stable", "declining"
    dominant_genes: list[str] = field(default_factory=list)
    recommended_hybrids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "market_heat": round(self.market_heat, 1),
            "competition_density": round(self.competition_density, 1),
            "opportunity_gap": round(self.opportunity_gap, 1),
            "growth_trajectory": self.growth_trajectory,
            "dominant_genes": self.dominant_genes,
            "recommended_hybrids": self.recommended_hybrids,
        }


@dataclass
class CategoryHeatmap:
    """Full market category heatmap."""
    cells: list[CategoryCell] = field(default_factory=list)
    hot_categories: list[str] = field(default_factory=list)
    cold_categories: list[str] = field(default_factory=list)
    top_opportunities: list[CategoryCell] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": [c.to_dict() for c in self.cells],
            "hot_categories": self.hot_categories,
            "cold_categories": self.cold_categories,
            "top_opportunities": [c.to_dict() for c in self.top_opportunities],
        }


class CategoryHeatmapEngine:
    """Generates market category heatmaps from trend + competitor data.

    Uses TrendDetector + CompetitorTracker signals.
    """

    def generate(self) -> CategoryHeatmap:
        """Generate current category heatmap from mock data.

        In production: combines real SensorTower, AppMagic, Meta Ads data.
        """
        cells = [
            CategoryCell(
                category="sort",
                market_heat=92,
                competition_density=75,
                opportunity_gap=82,
                growth_trajectory="accelerating",
                dominant_genes=["sort", "3d_physics", "mess_to_clean"],
                recommended_hybrids=["sort_merge", "sort_simulation", "sort_collection"],
            ),
            CategoryCell(
                category="merge",
                market_heat=78,
                competition_density=85,
                opportunity_gap=60,
                growth_trajectory="stable",
                dominant_genes=["merge", "collection", "evolution"],
                recommended_hybrids=["merge_simulation", "merge_decorate", "merge_rescue"],
            ),
            CategoryCell(
                category="puzzle",
                market_heat=65,
                competition_density=60,
                opportunity_gap=72,
                growth_trajectory="accelerating",
                dominant_genes=["puzzle", "satisfaction", "color_match"],
                recommended_hybrids=["puzzle_simulation", "puzzle_collection"],
            ),
            CategoryCell(
                category="simulation",
                market_heat=85,
                competition_density=55,
                opportunity_gap=90,
                growth_trajectory="accelerating",
                dominant_genes=["simulation", "build_progress", "cozy"],
                recommended_hybrids=["sim_merge", "sim_sort", "sim_factory"],
            ),
            CategoryCell(
                category="decorate",
                market_heat=70,
                competition_density=40,
                opportunity_gap=85,
                growth_trajectory="accelerating",
                dominant_genes=["decorate", "collection", "home"],
                recommended_hybrids=["decorate_merge", "decorate_sort"],
            ),
            CategoryCell(
                category="battle",
                market_heat=45,
                competition_density=90,
                opportunity_gap=25,
                growth_trajectory="declining",
                dominant_genes=["battle", "rpg", "arena"],
                recommended_hybrids=["battle_simulation"],
            ),
            CategoryCell(
                category="hyper_casual",
                market_heat=55,
                competition_density=95,
                opportunity_gap=15,
                growth_trajectory="stable",
                dominant_genes=["simple_tap", "satisfaction", "fast"],
                recommended_hybrids=[],
            ),
        ]

        cells.sort(key=lambda c: c.opportunity_gap, reverse=True)
        hot = [c.category for c in cells if c.market_heat >= 75]
        cold = [c.category for c in cells if c.market_heat < 50]
        top_opps = sorted(cells, key=lambda c: c.opportunity_gap, reverse=True)[:5]

        return CategoryHeatmap(
            cells=cells, hot_categories=hot, cold_categories=cold, top_opportunities=top_opps,
        )

    def get_hybridization_suggestions(self) -> list[dict[str, Any]]:
        """Suggest cross-category hybrids with highest opportunity."""
        heatmap = self.generate()
        suggestions = []
        for cell in heatmap.top_opportunities:
            for hybrid in cell.recommended_hybrids:
                suggestions.append({
                    "primary_category": cell.category,
                    "hybrid_name": hybrid,
                    "opportunity_gap": cell.opportunity_gap,
                    "market_heat": cell.market_heat,
                })
        return sorted(suggestions, key=lambda s: s["opportunity_gap"], reverse=True)
