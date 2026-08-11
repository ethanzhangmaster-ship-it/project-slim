"""
E16.6.3 — Competitor Visual Intelligence.

The ASO → E16.6.2 Competitor Provider chain, extended into the *visual* domain:

    Competitor Provider (E16.6.2)
        → Top Games
        → Visual Feature Database  (list of ``CompetitorCreative``)
        → Cluster                 (group by visual DNA)
        → ASO Pattern             (``ASOCreativePattern`` with mean fitness)

This module is deterministic: it consumes already-built ``CompetitorCreative``
records (each carrying a vision ``feature`` + ``dna``) and mines cross-game
visual patterns. The production bridge that turns raw competitor store pages
into ``CompetitorCreative`` (via the vision analyzer) is intentionally left as
a thin adapter — the competitor provider in E16.6.2 is still a seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.aso_intelligence.creative.models import (
    ASOCreativePattern,
    CompetitorCreative,
)

# DNA dimensions we cluster competitors on.
_PATTERN_DIMENSIONS = [
    "composition",
    "character_style",
    "message_type",
    "emotional_trigger",
]


@dataclass
class CompetitorCluster:
    """One visual cluster of competitor creatives."""

    key: str  # e.g. "screenshot:composition:centered_focal"
    asset: str
    dimension: str
    value: str
    members: List[CompetitorCreative] = field(default_factory=list)
    mean_fitness: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "asset": self.asset,
            "dimension": self.dimension,
            "value": self.value,
            "member_count": len(self.members),
            "mean_fitness": round(self.mean_fitness, 4),
            "competitors": [m.competitor_id for m in self.members],
        }


class CompetitorVisualAnalyzer:
    """Mines visual patterns from a pool of competitor creatives."""

    def __init__(self, pattern_dimensions: Optional[List[str]] = None):
        self._dims = pattern_dimensions or list(_PATTERN_DIMENSIONS)

    # ------------------------------------------------------------------ #
    def cluster(
        self, creatives: List[CompetitorCreative]
    ) -> List[CompetitorCluster]:
        """Group competitor creatives into visual clusters (one per asset +
        DNA dimension + value). Only creatives with a ``dna`` participate."""
        buckets: Dict[str, CompetitorCluster] = {}
        for c in creatives:
            if c.dna is None or c.feature is None:
                continue
            for dim in self._dims:
                val = getattr(c.dna, dim, "unknown")
                if not val or val == "unknown":
                    continue
                key = f"{c.asset_type.value}:{dim}:{val}"
                if key not in buckets:
                    buckets[key] = CompetitorCluster(
                        key=key,
                        asset=c.asset_type.value,
                        dimension=dim,
                        value=val,
                    )
                buckets[key].members.append(c)

        clusters = list(buckets.values())
        for cl in clusters:
            feats = [m.feature.fitness() for m in cl.members if m.feature]
            cl.mean_fitness = round(sum(feats) / len(feats), 4) if feats else 0.0
        return clusters

    # ------------------------------------------------------------------ #
    def mine_patterns(
        self,
        category: str,
        creatives: List[CompetitorCreative],
        *,
        min_sample: int = 3,
    ) -> List[ASOCreativePattern]:
        """Cluster competitors and emit one ``ASOCreativePattern`` per cluster
        whose sample size meets ``min_sample``.

        ``success`` = mean creative fitness of the cluster (0.0–1.0).
        """
        patterns: List[ASOCreativePattern] = []
        for cl in self.cluster(creatives):
            if len(cl.members) < min_sample:
                continue
            patterns.append(
                ASOCreativePattern(
                    category=category,
                    asset=cl.asset,
                    pattern=f"{cl.dimension}:{cl.value}",
                    success=cl.mean_fitness,
                    sample_size=len(cl.members),
                    note=f"mean fitness {cl.mean_fitness:.2f} over "
                    f"{len(cl.members)} competitors",
                )
            )
        # highest-success patterns first
        patterns.sort(key=lambda p: p.success, reverse=True)
        return patterns

    # ------------------------------------------------------------------ #
    def top_pattern(
        self,
        category: str,
        creatives: List[CompetitorCreative],
        *,
        min_sample: int = 3,
    ) -> Optional[ASOCreativePattern]:
        """The single best (highest-success) mined pattern, if any."""
        patterns = self.mine_patterns(
            category, creatives, min_sample=min_sample
        )
        return patterns[0] if patterns else None


__all__ = [
    "CompetitorVisualAnalyzer",
    "CompetitorCluster",
    "_PATTERN_DIMENSIONS",
]
