"""E9.8: Opportunity Detector — Finds market gaps for new creative exploration.

Discovers unexplored DNA combinations that could yield high-value creatives.
Analyzes existing creative space to identify:
  - Under-explored DNA dimensions
  - Missing combinations (e.g., no "challenge + horror" creatives)
  - High-potential archetype gaps
"""

from __future__ import annotations

from collections import defaultdict
from itertools import product
from typing import Any

from market_ops.creative_evolution.schemas import MarketOpportunity
from market_ops.creative_evolution.schemas import WinnerPattern


class OpportunityDetector:
    """Detects market gaps and creative opportunities.

    Usage:
        detector = OpportunityDetector()
        opportunities = detector.detect(dna_list, winner_pattern)
    """

    def detect(
        self,
        dna_list: list[dict[str, Any]],
        winner_pattern: WinnerPattern,
    ) -> list[MarketOpportunity]:
        """Detect creative opportunities in the market.

        Args:
            dna_list: All creative DNA entries
            winner_pattern: Aggregated winner patterns

        Returns:
            List of MarketOpportunity objects
        """
        opportunities: list[MarketOpportunity] = []

        # 1. Find under-explored dimensions
        opportunities.extend(self._detect_under_explored(dna_list))

        # 2. Find missing combinations
        opportunities.extend(self._detect_missing_combinations(dna_list))

        # 3. Find archetype gaps
        opportunities.extend(self._detect_archetype_gaps(winner_pattern))

        # 4. Sort by confidence
        opportunities.sort(key=lambda o: o.confidence, reverse=True)

        return opportunities[:20]

    # ── Under-Explored Dimensions ──────────────────────────

    def _detect_under_explored(
        self,
        dna_list: list[dict[str, Any]],
    ) -> list[MarketOpportunity]:
        """Find DNA values that are rarely used."""
        opportunities = []

        # Available value spaces
        spaces = {
            "hook": ["emotional", "challenge", "secret", "curiosity", "collection", "progression", "competition"],
            "reward": ["discovery", "unlock", "collection", "upgrade", "rare", "power_up", "progression"],
            "visual": ["2d_flat", "3d_cartoon", "3d_realistic", "pixel_art", "minimalist"],
            "fantasy": ["become_powerful", "discovery_world", "collect_dragons", "build_kingdom", "rescue_princess", "solve_mystery"],
        }

        for dim, all_values in spaces.items():
            # Count existing values
            counter: dict[str, int] = defaultdict(int)
            for d in dna_list:
                dim_data = d.get(dim, {}) or {}
                if dim == "fantasy":
                    for v in dim_data.get("drives", []) or []:
                        counter[v] += 1
                else:
                    val = dim_data.get("type" if dim != "visual" else "style", "") or ""
                    if val and val != "unknown":
                        counter[val] += 1

            total = len(dna_list)
            for val in all_values:
                count = counter.get(val, 0)
                pct = count / total if total > 0 else 0

                # Under-explored: < 5% of creatives
                if pct < 0.05:
                    opportunities.append(MarketOpportunity(
                        opportunity_id=f"underexplored_{dim}_{val}",
                        description=f"Under-explored {dim}: '{val}' (only {pct:.1%})",
                        dimension=dim,
                        target_value=val,
                        target_archetype="",
                        confidence=round(1.0 - pct, 2),
                        reason=f"Only {count}/{total} creatives use {dim}={val}",
                    ))

        return opportunities

    # ── Missing Combinations ───────────────────────────────

    def _detect_missing_combinations(
        self,
        dna_list: list[dict[str, Any]],
    ) -> list[MarketOpportunity]:
        """Find promising DNA combinations that don't exist yet."""
        opportunities = []

        # Extract existing combinations
        existing_combos: set[tuple[str, str]] = set()
        for d in dna_list:
            hook = (d.get("hook", {}) or {}).get("type", "")
            reward = (d.get("reward", {}) or {}).get("type", "")
            if hook and reward and hook != "unknown" and reward != "unknown":
                existing_combos.add((hook, reward))

        # Check for missing combinations among top values
        top_hooks = ["emotional", "challenge", "secret", "curiosity"]
        top_rewards = ["discovery", "unlock", "collection", "upgrade", "rare"]

        for hook, reward in product(top_hooks, top_rewards):
            if (hook, reward) not in existing_combos:
                opportunities.append(MarketOpportunity(
                    opportunity_id=f"combo_{hook}_{reward}",
                    description=f"Missing combination: hook='{hook}' + reward='{reward}'",
                    dimension="hook+reward",
                    target_value=f"{hook}+{reward}",
                    target_archetype="",
                    confidence=0.65,
                    reason=f"No existing creative combines hook={hook} with reward={reward}",
                ))

        return opportunities

    # ── Archetype Gaps ─────────────────────────────────────

    def _detect_archetype_gaps(
        self,
        winner_pattern: WinnerPattern,
    ) -> list[MarketOpportunity]:
        """Find archetypes with low winner affinity."""
        opportunities = []

        arch_affinity = winner_pattern.archetype_affinity
        if not arch_affinity:
            return opportunities

        for arch, affinity in arch_affinity.items():
            if affinity < 0.15:
                opportunities.append(MarketOpportunity(
                    opportunity_id=f"arch_gap_{arch}",
                    description=f"Under-represented archetype '{arch}' in winners ({affinity:.1%})",
                    dimension="archetype",
                    target_value=arch,
                    target_archetype=arch,
                    confidence=round(1.0 - affinity, 2),
                    reason=f"Only {affinity:.1%} of winners attract {arch} players",
                ))

        return opportunities