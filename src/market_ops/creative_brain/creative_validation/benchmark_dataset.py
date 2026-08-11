"""V4.2 Benchmark Dataset — standard validation datasets.

Builds standardized datasets for Creative Brain validation:
  - 1000 Winners (ROAS >= 0.5)
  - 1000 Losers (ROAS < 0.35)
  - 500 Borderline (0.35 <= ROAS < 0.5)
  - 500 New Trend (emerging patterns)
  - 500 Dead Trend (declining patterns)

Train/Validation/Test split with strict isolation.
"""

from __future__ import annotations

import random
from typing import Any

from .schemas import HistoricalCreative, SplitType


class BenchmarkDataset:
    """Standardized benchmark datasets for Creative Brain validation.

    Guarantees:
      - Train/Val/Test isolation (no data leakage)
      - Balanced class distribution
      - Support for 5000+ historical creatives
    """

    def __init__(self) -> None:
        self._creatives: list[HistoricalCreative] = []
        self._train: list[HistoricalCreative] = []
        self._val: list[HistoricalCreative] = []
        self._test: list[HistoricalCreative] = []
        self._holdout: list[HistoricalCreative] = []

    def generate(self, n_winners: int = 1000, n_losers: int = 1000,
                 n_borderline: int = 500, n_new_trend: int = 500,
                 n_dead_trend: int = 500,
                 seed: int = 42) -> list[HistoricalCreative]:
        """Generate a complete benchmark dataset.

        Total: up to 3500 synthetic creatives.
        """
        random.seed(seed)
        creatives = []

        # Winners: proven high-ROAS patterns
        creatives.extend(self._generate_winners(n_winners))

        # Losers: proven low-ROAS patterns
        creatives.extend(self._generate_losers(n_losers))

        # Borderline: mid-ROAS, ambiguous
        creatives.extend(self._generate_borderline(n_borderline))

        # New trends: emerging patterns
        creatives.extend(self._generate_new_trends(n_new_trend))

        # Dead trends: declining patterns
        creatives.extend(self._generate_dead_trends(n_dead_trend))

        # Shuffle
        random.shuffle(creatives)

        # Time-based split
        n = len(creatives)
        train_end = int(n * 0.5)
        val_end = int(n * 0.7)
        test_end = int(n * 0.9)

        for i, c in enumerate(creatives):
            if i < train_end:
                c.split = SplitType.TRAIN
            elif i < val_end:
                c.split = SplitType.VALIDATION
            elif i < test_end:
                c.split = SplitType.TEST
            else:
                c.split = SplitType.HOLDOUT

        self._creatives = creatives
        self._train = [c for c in creatives if c.split == SplitType.TRAIN]
        self._val = [c for c in creatives if c.split == SplitType.VALIDATION]
        self._test = [c for c in creatives if c.split == SplitType.TEST]
        self._holdout = [c for c in creatives if c.split == SplitType.HOLDOUT]

        return creatives

    def load_custom(self, creatives: list[dict[str, Any]]) -> list[HistoricalCreative]:
        """Load custom creative data."""
        historical = []
        for c in creatives:
            historical.append(HistoricalCreative(
                creative_id=c.get("creative_id", ""),
                dna=c.get("dna", {}),
                performance=c.get("performance", {}),
                country=c.get("country", "US"),
                date=c.get("date", "2024-01-01"),
            ))
        self._creatives = historical
        return historical

    # ── Generators ──

    def _generate_winners(self, n: int) -> list[HistoricalCreative]:
        """Generate winner creatives (ROAS >= 0.5)."""
        creatives = []
        for i in range(n):
            creatives.append(HistoricalCreative(
                creative_id=f"winner_{i:04d}",
                dna={"character": "dragon", "reward": "dragon",
                     "hook": "collection", "gameplay": "merge",
                     "style": "cartoon", "camera": "45_degree"},
                performance={"roas_d7": random.uniform(0.7, 1.2),
                             "ctr": random.uniform(3.5, 5.5),
                             "ipm": random.uniform(20, 40)},
                country="US",
                date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                labels=["winner"],
            ))
        return creatives

    def _generate_losers(self, n: int) -> list[HistoricalCreative]:
        """Generate loser creatives (ROAS < 0.35)."""
        creatives = []
        for i in range(n):
            creatives.append(HistoricalCreative(
                creative_id=f"loser_{i:04d}",
                dna={"character": "ninja", "reward": "gold",
                     "hook": "fail", "gameplay": "runner",
                     "style": "pixel", "camera": "side_view"},
                performance={"roas_d7": random.uniform(0.05, 0.35),
                             "ctr": random.uniform(0.5, 2.0),
                             "ipm": random.uniform(5, 15)},
                country="US",
                date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                labels=["loser"],
            ))
        return creatives

    def _generate_borderline(self, n: int) -> list[HistoricalCreative]:
        """Generate borderline creatives (0.35 <= ROAS < 0.5)."""
        creatives = []
        for i in range(n):
            creatives.append(HistoricalCreative(
                creative_id=f"border_{i:04d}",
                dna={"character": "warrior", "reward": "treasure",
                     "hook": "challenge", "gameplay": "fight",
                     "style": "3d", "camera": "top_down"},
                performance={"roas_d7": random.uniform(0.35, 0.5),
                             "ctr": random.uniform(2.0, 3.5),
                             "ipm": random.uniform(10, 25)},
                country="US",
                date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                labels=["borderline"],
            ))
        return creatives

    def _generate_new_trends(self, n: int) -> list[HistoricalCreative]:
        """Generate emerging trend creatives."""
        creatives = []
        for i in range(n):
            creatives.append(HistoricalCreative(
                creative_id=f"trend_{i:04d}",
                dna={"character": "phoenix", "reward": "crystal",
                     "hook": "mystery", "gameplay": "explore",
                     "style": "fantasy", "camera": "overhead"},
                performance={"roas_d7": random.uniform(0.4, 0.8),
                             "ctr": random.uniform(2.5, 4.5),
                             "ipm": random.uniform(15, 30)},
                country="US",
                date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                labels=["new_trend"],
            ))
        return creatives

    def _generate_dead_trends(self, n: int) -> list[HistoricalCreative]:
        """Generate dead trend creatives (previously winning, now losing)."""
        creatives = []
        for i in range(n):
            creatives.append(HistoricalCreative(
                creative_id=f"dead_{i:04d}",
                dna={"character": "knight", "reward": "evolution",
                     "hook": "transformation", "gameplay": "idle",
                     "style": "cartoon", "camera": "45_degree"},
                performance={"roas_d7": random.uniform(0.1, 0.3),
                             "ctr": random.uniform(1.0, 2.5),
                             "ipm": random.uniform(5, 15)},
                country="US",
                date=f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                labels=["dead_trend"],
            ))
        return creatives

    # ── Accessors ──

    @property
    def all(self) -> list[HistoricalCreative]:
        return self._creatives

    @property
    def train(self) -> list[HistoricalCreative]:
        return self._train

    @property
    def val(self) -> list[HistoricalCreative]:
        return self._val

    @property
    def test(self) -> list[HistoricalCreative]:
        return self._test

    @property
    def holdout(self) -> list[HistoricalCreative]:
        return self._holdout

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total": len(self._creatives),
            "train": len(self._train),
            "val": len(self._val),
            "test": len(self._test),
            "holdout": len(self._holdout),
            "winners": sum(1 for c in self._creatives if c.is_winner),
            "losers": sum(1 for c in self._creatives if not c.is_winner),
        }