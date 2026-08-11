"""
E15.2.4 — Waterfall Optimizer

Reorders ad network waterfall based on eCPM performance.
Deterministic: rank by trailing-7-day eCPM, within guard rails.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WaterfallChange:
    """Proposed waterfall change."""
    game_id: str
    format: str
    country: str
    old_order: List[str]
    new_order: List[str]
    reason: str
    expected_impact: Dict[str, Any] = field(default_factory=dict)


class WaterfallOptimizer:
    """Optimizes ad network ordering based on performance data."""

    # Networks must have at least this many data points to be ranked
    MIN_IMPRESSIONS = 1000
    # Max position change for a network (prevent wild swings)
    MAX_POSITION_CHANGE = 3
    # Min eCPM difference to trigger reorder (avoid noise)
    MIN_ECPM_DIFF = 0.50

    def optimize(
        self,
        game_id: str,
        format: str,
        country: str,
        current_order: List[str],
        network_data: List[Dict[str, Any]],
    ) -> Optional[WaterfallChange]:
        """Analyze network data and propose reorder if warranted."""

        # Build performance map: network → avg eCPM
        perf: Dict[str, float] = {}
        for nd in network_data:
            network = nd.get("network", "")
            ecpm = nd.get("ecpm_7d_avg")
            imps = nd.get("impressions_7d", 0)
            if ecpm is not None and imps >= self.MIN_IMPRESSIONS:
                perf[network] = ecpm

        if len(perf) < 2:
            return None

        # Sort by eCPM descending
        new_order = sorted(perf.keys(), key=lambda n: perf[n], reverse=True)

        # Add any current networks not in data at the end
        for net in current_order:
            if net not in new_order:
                new_order.append(net)

        # Check if change is meaningful
        if new_order == current_order:
            return None

        # Check max position change constraint
        for net in current_order:
            if net not in new_order:
                continue
            old_pos = current_order.index(net)
            new_pos = new_order.index(net)
            if abs(new_pos - old_pos) > self.MAX_POSITION_CHANGE:
                # Clamp: keep within max position change
                clamped_pos = max(0, min(len(new_order) - 1,
                                         old_pos + self.MAX_POSITION_CHANGE
                                         if new_pos > old_pos
                                         else old_pos - self.MAX_POSITION_CHANGE))
                # Swap
                new_order.remove(net)
                new_order.insert(clamped_pos, net)

        # Check if eCPM difference justifies reorder
        old_top = current_order[0] if current_order else ""
        new_top = new_order[0] if new_order else ""
        if old_top != new_top and old_top in perf and new_top in perf:
            diff = perf[new_top] - perf[old_top]
            if diff < self.MIN_ECPM_DIFF:
                return None

        if new_order == current_order:
            return None

        old_ecpms = {n: perf.get(n, 0) for n in current_order}
        new_ecpms = {n: perf.get(n, 0) for n in new_order}

        return WaterfallChange(
            game_id=game_id,
            format=format,
            country=country,
            old_order=current_order,
            new_order=new_order,
            reason=f"Reordered by trailing-7d eCPM in {country}",
            expected_impact={
                "old_top_ecpm": old_ecpms.get(old_top, 0),
                "new_top_ecpm": new_ecpms.get(new_top, 0),
                "ecpm_improvement": round(new_ecpms.get(new_top, 0) - old_ecpms.get(old_top, 0), 2),
            },
        )

    def to_operations(self, change: WaterfallChange) -> List[Dict[str, Any]]:
        """Convert WaterfallChange to executable monetization operations."""
        ops = []
        for i, network in enumerate(change.new_order):
            ops.append({
                "operation": "configure_waterfall",
                "provider": "max",
                "game_id": change.game_id,
                "network": network,
                "position": i,
                "format": change.format,
                "country": change.country,
            })
        return ops


__all__ = ["WaterfallOptimizer", "WaterfallChange"]
