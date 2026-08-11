"""E5.1 Market Brain — Creative Signal Miner.

Mines creative advertising data for signals:
  - Which hooks are trending in competitor ads
  - Which visual styles dominate
  - Which reward mechanics appear most
  - Creative format shifts (UGC, gameplay, story)

Mock data simulates Meta Ads Library + TikTok Creative Center.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CreativeSignal:
    """A signal mined from creative advertising data."""
    signal_id: str = ""
    dimension: str = ""       # "hook", "visual", "reward", "format", "character"
    value: str = ""           # e.g. "rescue", "3d_cartoon"
    prevalence: float = 0.0    # 0-100, how common in top ads
    growth_30d: float = 0.0    # change in prevalence
    ctr_prediction: str = ""   # "high", "medium", "low"
    cpi_prediction: float = 0.0
    sample_size: int = 0
    source: str = ""          # "meta_ads", "tiktok", "youtube"
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "dimension": self.dimension,
            "value": self.value,
            "prevalence": round(self.prevalence, 1),
            "growth_30d": round(self.growth_30d, 1),
            "ctr_prediction": self.ctr_prediction,
            "cpi_prediction": round(self.cpi_prediction, 2),
            "sample_size": self.sample_size,
            "source": self.source,
        }


class CreativeSignalMiner:
    """Mines creative signals from advertising data.

    Scans competitor ad libraries to identify:
      - Trending hooks (rescue, reward, mess-to-clean)
      - Dominant visual styles (3D, bright, dark)
      - Winning reward mechanics (evolution, collection)
      - Creative format shifts (UGC, gameplay capture)
    """

    # Pre-loaded signal database simulating Meta Ads Library + TikTok
    MOCK_SIGNALS: list[dict[str, Any]] = [
        # Hook signals
        {"dimension": "hook", "value": "rescue", "prevalence": 35, "growth": 45, "ctr": "high", "cpi": 2.8, "n": 1200, "src": "meta_ads"},
        {"dimension": "hook", "value": "mess_to_clean", "prevalence": 28, "growth": 15, "ctr": "high", "cpi": 3.2, "n": 950, "src": "meta_ads"},
        {"dimension": "hook", "value": "before_after", "prevalence": 22, "growth": 8, "ctr": "medium", "cpi": 3.8, "n": 780, "src": "tiktok"},
        {"dimension": "hook", "value": "fail_recovery", "prevalence": 18, "growth": 25, "ctr": "high", "cpi": 3.0, "n": 650, "src": "tiktok"},
        {"dimension": "hook", "value": "evolution_reveal", "prevalence": 15, "growth": 55, "ctr": "medium", "cpi": 4.5, "n": 520, "src": "meta_ads"},
        {"dimension": "hook", "value": "collection_progress", "prevalence": 12, "growth": 40, "ctr": "medium", "cpi": 4.0, "n": 400, "src": "youtube"},
        # Visual signals
        {"dimension": "visual", "value": "3d_cartoon", "prevalence": 42, "growth": 35, "ctr": "high", "cpi": 3.0, "n": 1500, "src": "all"},
        {"dimension": "visual", "value": "2d_bright", "prevalence": 30, "growth": -5, "ctr": "medium", "cpi": 3.5, "n": 1100, "src": "all"},
        {"dimension": "visual", "value": "realistic_3d", "prevalence": 18, "growth": 20, "ctr": "medium", "cpi": 4.2, "n": 600, "src": "meta_ads"},
        {"dimension": "visual", "value": "minimal_flat", "prevalence": 10, "growth": -15, "ctr": "low", "cpi": 5.0, "n": 350, "src": "all"},
        # Reward signals
        {"dimension": "reward", "value": "evolution", "prevalence": 38, "growth": 30, "ctr": "high", "cpi": 3.2, "n": 1300, "src": "all"},
        {"dimension": "reward", "value": "collection", "prevalence": 32, "growth": 20, "ctr": "medium", "cpi": 3.5, "n": 1100, "src": "all"},
        {"dimension": "reward", "value": "growth_upgrade", "prevalence": 20, "growth": 10, "ctr": "medium", "cpi": 3.8, "n": 700, "src": "meta_ads"},
        # Format signals
        {"dimension": "format", "value": "ugc_creator", "prevalence": 45, "growth": 60, "ctr": "high", "cpi": 2.5, "n": 1600, "src": "tiktok"},
        {"dimension": "format", "value": "gameplay_capture", "prevalence": 35, "growth": 5, "ctr": "medium", "cpi": 4.0, "n": 1200, "src": "all"},
        {"dimension": "format", "value": "story_narrative", "prevalence": 15, "growth": 25, "ctr": "medium", "cpi": 4.5, "n": 500, "src": "youtube"},
        {"dimension": "format", "value": "comparison_split", "prevalence": 5, "growth": 80, "ctr": "high", "cpi": 3.0, "n": 200, "src": "tiktok"},
        # Character signals
        {"dimension": "character", "value": "baby_animal", "prevalence": 30, "growth": 20, "ctr": "high", "cpi": 3.0, "n": 1000, "src": "meta_ads"},
        {"dimension": "character", "value": "dragon", "prevalence": 25, "growth": 10, "ctr": "high", "cpi": 3.2, "n": 850, "src": "all"},
        {"dimension": "character", "value": "mermaid", "prevalence": 15, "growth": 15, "ctr": "medium", "cpi": 3.8, "n": 500, "src": "tiktok"},
    ]

    def mine(self) -> list[CreativeSignal]:
        """Mine all creative signals."""
        return [
            CreativeSignal(
                signal_id=f"cs_{s['dimension']}_{s['value']}",
                dimension=s["dimension"], value=s["value"],
                prevalence=s["prevalence"], growth_30d=s["growth"],
                ctr_prediction=s["ctr"], cpi_prediction=s["cpi"],
                sample_size=s["n"], source=s["src"],
            )
            for s in self.MOCK_SIGNALS
        ]

    def get_top_signals(self, dimension: str, n: int = 5) -> list[CreativeSignal]:
        """Get top N signals for a specific dimension."""
        signals = [s for s in self.mine() if s.dimension == dimension]
        return sorted(signals, key=lambda s: s.prevalence + s.growth_30d * 0.5, reverse=True)[:n]

    def get_trending_signals(self, min_growth: float = 30) -> list[CreativeSignal]:
        """Get signals growing faster than threshold."""
        return [s for s in self.mine() if s.growth_30d >= min_growth]

    def get_hot_hooks(self, n: int = 5) -> list[CreativeSignal]:
        """Get hottest hook signals."""
        return self.get_top_signals("hook", n)

    def get_hot_visuals(self, n: int = 5) -> list[CreativeSignal]:
        """Get hottest visual signals."""
        return self.get_top_signals("visual", n)

    def get_low_cpi_channels(self, max_cpi: float = 3.5) -> list[CreativeSignal]:
        """Get signals with low predicted CPI."""
        return sorted(
            [s for s in self.mine() if s.cpi_prediction <= max_cpi],
            key=lambda s: s.cpi_prediction,
        )
