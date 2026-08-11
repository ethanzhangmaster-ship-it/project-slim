"""
E15.2.4 — BidFloorStrategy, WaterfallStrategy, FrequencyStrategy, NetworkStrategy

Each strategy converts OptimizationSignals into OptimizationActions.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from operation.optimizer.models import OptimizationAction, OptimizationSignal


def _uid(p: str = "act") -> str:
    return f"{p}_{uuid.uuid4().hex[:8]}"


class BidFloorStrategy:
    """Adjusts bid floors with safety guard rails."""

    MAX_INCREASE_PCT = 20.0
    MAX_DECREASE_PCT = 15.0
    MIN_FLOOR = 0.50
    MAX_FLOOR = 50.0

    def generate(self, signals: List[OptimizationSignal],
                 current_floors: Optional[Dict[str, float]] = None) -> List[OptimizationAction]:
        actions: List[OptimizationAction] = []
        floors = current_floors or {}

        for sig in signals:
            if sig.suggested_action not in ("raise_bid_floor", "lower_bid_floor"):
                continue

            key = f"{sig.ad_format}_{sig.country}"
            current = floors.get(key, sig.expected_value)
            new = sig.metadata.get("suggested_new_floor")

            if sig.suggested_action == "raise_bid_floor":
                if new is None:
                    new = min(current * 1.10, current + current * self.MAX_INCREASE_PCT / 100)
                new = min(round(new, 2), self.MAX_FLOOR)
                if new <= current:
                    continue
            else:
                decrease = min(current * self.MAX_DECREASE_PCT / 100,
                              current - self.MIN_FLOOR)
                new = max(current - decrease, self.MIN_FLOOR)
                new = round(new, 2)
                if new >= current:
                    continue

            actions.append(OptimizationAction(
                action_id=_uid("bf"),
                action_type=sig.suggested_action,
                game_id=sig.game_id, provider="max",
                country=sig.country, ad_format=sig.ad_format,
                changes={"old_floor": current, "new_floor": new,
                         "change_pct": round((new - current) / current * 100, 1)},
                expected_impact={"revenue_change_pct": 5.0 if new > current else -3.0,
                                 "ecpm_change_pct": 3.0 if new > current else -5.0},
                priority=0 if sig.is_critical else 1 if sig.severity == "warning" else 2,
                source_signal=sig,
            ))

        return actions


class WaterfallStrategy:
    """Reorders waterfall networks based on performance."""

    MAX_POSITION_CHANGE = 3
    MIN_ECPM_DIFF = 0.50

    def generate(self, signals: List[OptimizationSignal],
                 current_order: Optional[Dict[str, List[str]]] = None) -> List[OptimizationAction]:
        actions: List[OptimizationAction] = []
        orders = current_order or {}

        for sig in signals:
            if sig.suggested_action not in ("reorder_waterfall", "lower_network_priority"):
                continue

            meta = sig.metadata
            new_order = meta.get("new_order")
            old_order = meta.get("old_order")
            if not new_order or not old_order:
                continue

            # Clamp position changes
            clamped = list(new_order)
            for net in old_order:
                if net not in clamped:
                    continue
                old_pos = old_order.index(net)
                new_pos = clamped.index(net)
                if abs(new_pos - old_pos) > self.MAX_POSITION_CHANGE:
                    target = old_pos + self.MAX_POSITION_CHANGE if new_pos > old_pos else old_pos - self.MAX_POSITION_CHANGE
                    target = max(0, min(len(clamped) - 1, target))
                    clamped.remove(net)
                    clamped.insert(target, net)

            actions.append(OptimizationAction(
                action_id=_uid("wf"),
                action_type="reorder_waterfall",
                game_id=sig.game_id, provider="max",
                country=sig.country, ad_format=sig.ad_format,
                changes={"old_order": old_order, "new_order": clamped},
                expected_impact={"ecpm_improvement": round(abs(sig.change_pct), 2)},
                priority=1 if sig.is_critical else 2,
                source_signal=sig,
            ))

        return actions


class FrequencyStrategy:
    """Adjusts ad frequency balancing revenue and retention."""

    def generate(self, signals: List[OptimizationSignal],
                 current_frequencies: Optional[Dict[str, float]] = None) -> List[OptimizationAction]:
        actions: List[OptimizationAction] = []
        freqs = current_frequencies or {}

        for sig in signals:
            if sig.suggested_action != "adjust_frequency":
                continue

            current = freqs.get(sig.ad_format, 60)
            new = sig.metadata.get("suggested_interval", current * 0.9)
            change_pct = (new - current) / current * 100

            actions.append(OptimizationAction(
                action_id=_uid("fq"),
                action_type="adjust_frequency",
                game_id=sig.game_id, provider="max",
                country=sig.country, ad_format=sig.ad_format,
                changes={"old_interval_s": current, "new_interval_s": new,
                         "change_pct": round(change_pct, 1)},
                expected_impact={"revenue_change_pct": round(-change_pct * 0.4, 1),
                                 "retention_change_pct": round(change_pct * 0.6, 1)},
                priority=2,
                source_signal=sig,
            ))

        return actions


class NetworkStrategy:
    """Adds or removes waterfall networks."""

    def generate(self, signals: List[OptimizationSignal]) -> List[OptimizationAction]:
        actions: List[OptimizationAction] = []

        for sig in signals:
            if sig.suggested_action == "add_waterfall_networks":
                actions.append(OptimizationAction(
                    action_id=_uid("nw"),
                    action_type="add_network",
                    game_id=sig.game_id, provider="max",
                    country=sig.country, ad_format=sig.ad_format,
                    changes={"action": "add_network", "reason": sig.description},
                    expected_impact={"fill_change_pct": 10.0},
                    priority=1,
                    source_signal=sig,
                ))
            elif sig.suggested_action == "remove_network":
                network = sig.metadata.get("network", "")
                actions.append(OptimizationAction(
                    action_id=_uid("nw"),
                    action_type="remove_network",
                    game_id=sig.game_id, provider="max",
                    country=sig.country, ad_format=sig.ad_format,
                    changes={"network": network, "reason": sig.description},
                    expected_impact={"fill_change_pct": -3.0},
                    priority=2,
                    source_signal=sig,
                ))

        return actions


__all__ = ["BidFloorStrategy", "WaterfallStrategy", "FrequencyStrategy", "NetworkStrategy"]
