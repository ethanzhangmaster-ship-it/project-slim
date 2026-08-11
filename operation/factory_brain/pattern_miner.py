"""
E15.1.2 — Success Pattern Miner
================================

The Revenue OS -> Publishing Factory feedback line.

Mines "what combinations succeed" from:
  1. the fleet itself (GameProduct.metrics of published games), and
  2. PublishingMemory (screenshot styles / keyword sets that worked).

A game counts as a SUCCESS when revenue_per_dau >= threshold
(the single north-star KPI of the whole system).

Output: List[SuccessPattern] with a `weight` multiplier that the
SpecGenerator applies to next-generation spec confidence.

    success_rate 0.18 over >=5 games  ->  weight up to 1.5x
    success_rate 0.00                 ->  weight down to 0.5x
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.memory import PublishingMemory

from .models import SuccessPattern

# success definition (aligned with Revenue OS north star)
_SUCCESS_RPD = 0.03          # revenue_per_dau >= $0.03 == success
_MIN_SAMPLE = 2              # need >= 2 games to call it a pattern
_W_MIN, _W_MAX = 0.5, 1.5    # weight clamp


def _weight(success_rate: float, sample: int) -> float:
    """Deterministic weight: linear in success_rate, damped by sample.

    sample < _MIN_SAMPLE  -> neutral 1.0 (not enough evidence)
    rate 0.0  -> 0.5   |   rate 0.2 -> 1.5 (casual-portfolio ceiling)
    """
    if sample < _MIN_SAMPLE:
        return 1.0
    w = _W_MIN + (min(success_rate, 0.2) / 0.2) * (_W_MAX - _W_MIN)
    return round(max(_W_MIN, min(_W_MAX, w)), 4)


class PatternMiner:
    """Mines success patterns across the whole fleet."""

    def __init__(self, registry: GameRegistry,
                 memory: PublishingMemory = None):
        self.registry = registry
        self.memory = memory or PublishingMemory()

    # ------------------------------------------------------------------ #
    def mine(self) -> List[SuccessPattern]:
        """Group published games by (genre, monetization) and score."""
        groups: Dict[Tuple[str, str], List[float]] = {}
        for g in self.registry.list_all():
            if not g.is_published():
                continue
            rpd = float(g.metrics.get("revenue_per_dau", 0.0))
            groups.setdefault((g.genre, g.monetization), []).append(rpd)

        patterns: List[SuccessPattern] = []
        for (genre, monetization), rpds in sorted(groups.items()):
            sample = len(rpds)
            wins = sum(1 for r in rpds if r >= _SUCCESS_RPD)
            rate = round(wins / sample, 4) if sample else 0.0
            avg_rpd = round(sum(rpds) / sample, 4) if sample else 0.0
            rewarded = monetization in ("iaa", "hybrid")
            theme = self._dominant_theme(genre)
            patterns.append(SuccessPattern(
                pattern_id=f"pat_{genre}_{monetization}",
                genre=genre,
                theme=theme,
                monetization=monetization,
                rewarded_focus=rewarded,
                success_rate=rate,
                sample=sample,
                avg_revenue_per_dau=avg_rpd,
                weight=_weight(rate, sample),
            ))
        # strongest evidence first
        patterns.sort(key=lambda p: (-p.success_rate, -p.sample,
                                     p.pattern_id))
        return patterns

    # ------------------------------------------------------------------ #
    def _dominant_theme(self, genre: str) -> str:
        """Best screenshot style for this genre from PublishingMemory.

        Memory keys look like "<genre>_<style>" (E15.1.1 convention);
        strip the genre prefix to recover the style/theme token.
        """
        best = self.memory.best_style(genre)
        if not best:
            return ""
        prefix = f"{genre}_"
        return best[len(prefix):] if best.startswith(prefix) else best

    # ------------------------------------------------------------------ #
    def summarize(self) -> dict:
        pats = self.mine()
        return {
            "patterns": len(pats),
            "with_evidence": sum(1 for p in pats if p.sample >= _MIN_SAMPLE),
            "best": pats[0].to_dict() if pats else None,
        }


__all__ = ["PatternMiner"]
