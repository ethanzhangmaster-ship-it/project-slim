"""
E15.2.5 Rule 1 — ZombieNetworkDetector (with kill-switch protection).

A zombie network eats waterfall slots (attempts/latency/SDK cost) while
producing near-zero revenue. Grounded in real ACCT_2 findings:
CHARTBOOST 17,261 att / 14 imp / $0.11 ; INMOBI 1,608 att / 0 imp / $0.

CALIBRATION (user): "disable_network" is destructive. Before recommending
a hard disable, guard against killing a network that *has historical
value* or is the *unique filler in a geo*. When a candidate zombie trips
a protection, downgrade the recommendation from disable_network (P0) to
quarantine_network (monitor-first, P2) instead of silently killing it.

    history_revenue:      {network -> revenue over a longer lookback (e.g. 30d)}
    network_unique_geos:  {network -> [countries where it is the primary filler]}

Both inputs are optional; without them the detector behaves exactly as
before (safe default for offline replay).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from operation.optimizer.intel_models import IntelSignal, SegmentStat


class ZombieNetworkDetector:
    MIN_ATTEMPTS = 10_000       # enough traffic to judge
    MAX_IMPRESSIONS = 100       # essentially never wins
    MAX_REVENUE = 1.0           # near-zero contribution (USD, over window)
    # secondary rule: zero impressions with meaningful attempts is zombie too
    ZERO_IMP_MIN_ATTEMPTS = 1_000
    # kill-switch protection thresholds
    HISTORICAL_VALUE_USD = 5.0  # earned >= this over the lookback -> protect

    def analyze(self, by_network: Dict[str, SegmentStat],
                history_revenue: Optional[Dict[str, float]] = None,
                network_unique_geos: Optional[Dict[str, List[str]]] = None,
                ) -> List[IntelSignal]:
        history_revenue = history_revenue or {}
        network_unique_geos = network_unique_geos or {}
        signals: List[IntelSignal] = []
        for net, s in by_network.items():
            primary = (s.attempts > self.MIN_ATTEMPTS
                       and s.impressions < self.MAX_IMPRESSIONS
                       and s.revenue < self.MAX_REVENUE)
            zero_imp = (s.impressions == 0
                        and s.attempts >= self.ZERO_IMP_MIN_ATTEMPTS)
            if not (primary or zero_imp):
                continue

            # --- kill-switch protection ---------------------------------
            hist_rev = float(history_revenue.get(net, 0.0))
            unique_geos = list(network_unique_geos.get(net, []))
            protected_by_history = hist_rev >= self.HISTORICAL_VALUE_USD
            protected_by_geo = bool(unique_geos)
            protected = protected_by_history or protected_by_geo

            base_conf = 0.98 if primary else 0.90
            metrics = {
                "attempts": s.attempts,
                "impressions": s.impressions,
                "revenue": round(s.revenue, 2),
                "show_rate": round(s.show_rate, 4),
                "history_revenue": round(hist_rev, 2),
                "unique_geos": unique_geos,
            }

            if protected:
                why = []
                if protected_by_history:
                    why.append(f"earned ${hist_rev:.2f} in the lookback window")
                if protected_by_geo:
                    why.append(f"sole filler in {', '.join(unique_geos)}")
                signals.append(IntelSignal(
                    rule="zombie_network",
                    severity="warning",
                    action="quarantine_network",
                    target=net,
                    confidence=round(min(base_conf, 0.7), 2),
                    reason=(f"{s.attempts:,} requests / ${s.revenue:.2f} this window "
                            f"looks like a zombie, BUT protected ({'; '.join(why)}). "
                            f"Monitor 7 days before disabling."),
                    metrics={**metrics, "protection": "; ".join(why)},
                ))
            else:
                signals.append(IntelSignal(
                    rule="zombie_network",
                    severity="critical",
                    action="disable_network",
                    target=net,
                    confidence=base_conf,
                    reason=(f"{s.attempts:,} requests generated "
                            f"${s.revenue:.2f} revenue "
                            f"({s.impressions} impressions, show-rate {s.show_rate:.2%})"),
                    metrics=metrics,
                ))
        signals.sort(key=lambda x: -x.metrics["attempts"])
        return signals
