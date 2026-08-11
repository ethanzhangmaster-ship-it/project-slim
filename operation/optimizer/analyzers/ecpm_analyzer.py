"""E15.2.4 — eCPM Analyzer"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from operation.optimizer.models import OptimizationSignal


class EcpmAnalyzer:
    ECPM_DECLINE_CRITICAL = -20.0
    ECPM_DECLINE_WARNING = -10.0
    FLOOR_OPPORTUNITY_RATIO = 1.5
    FLOOR_OPPORTUNITY_DAYS = 7

    def analyze(self, game_id: str, metrics: List[Dict[str, Any]],
                baselines: Optional[Dict[str, Any]] = None) -> List[OptimizationSignal]:
        signals: List[OptimizationSignal] = []
        bl = baselines or {}

        for m in metrics:
            fmt = m.get("format", "rewarded")
            country = m.get("country", "US")
            platform = m.get("platform", "android")
            ecpm = m.get("ecpm")
            floor = m.get("bid_floor")

            # eCPM decline vs baseline
            bl_key = f"{fmt}_{country}_ecpm"
            bl_ecpm = bl.get(bl_key)
            if ecpm and bl_ecpm and bl_ecpm > 0:
                change = (ecpm - bl_ecpm) / bl_ecpm * 100
                if change <= self.ECPM_DECLINE_CRITICAL:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="ecpm_decline",
                        country=country, platform=platform, ad_format=fmt,
                        metric="ecpm", current_value=ecpm, expected_value=bl_ecpm,
                        change_pct=round(change, 1), severity="critical",
                        description=f"{fmt} eCPM {abs(change):.0f}% in {country}",
                        suggested_action="raise_bid_floor",
                    ))
                elif change <= self.ECPM_DECLINE_WARNING:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="ecpm_decline",
                        country=country, platform=platform, ad_format=fmt,
                        metric="ecpm", current_value=ecpm, expected_value=bl_ecpm,
                        change_pct=round(change, 1), severity="warning",
                        description=f"{fmt} eCPM {abs(change):.0f}% in {country}",
                        suggested_action="monitor_or_adjust_waterfall",
                    ))

            # Floor opportunity: eCPM significantly above current floor
            if ecpm and floor and floor > 0 and ecpm > floor * self.FLOOR_OPPORTUNITY_RATIO:
                change = (ecpm - floor) / floor * 100
                signals.append(OptimizationSignal(
                    game_id=game_id, signal_type="floor_opportunity",
                    country=country, platform=platform, ad_format=fmt,
                    metric="ecpm", current_value=ecpm, expected_value=floor,
                    change_pct=round(change, 1), severity="info",
                    description=f"eCPM {ecpm} >> floor {floor} — room to raise",
                    suggested_action="raise_bid_floor",
                    metadata={"ecpm": ecpm, "bid_floor": floor,
                              "suggested_new_floor": round(floor * 1.10, 2)},
                ))

        signals.sort(key=lambda s: (
            0 if s.severity == "critical" else 1 if s.severity == "warning" else 2,
            s.change_pct,
        ))
        return signals


__all__ = ["EcpmAnalyzer"]
