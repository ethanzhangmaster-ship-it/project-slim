"""
E15.2.4 — Revenue Analyzer

Detects overall revenue anomalies across IAA + IAP.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from operation.optimizer.models import OptimizationSignal


class RevenueAnalyzer:
    REVENUE_DROP_CRITICAL = -15.0
    REVENUE_DROP_WARNING = -8.0
    REVENUE_SPIKE_OPPORTUNITY = 10.0

    def analyze(self, game_id: str, metrics: List[Dict[str, Any]],
                baselines: Optional[Dict[str, Any]] = None) -> List[OptimizationSignal]:
        signals: List[OptimizationSignal] = []
        bl = baselines or {}

        for m in metrics:
            fmt = m.get("format", "rewarded")
            country = m.get("country", "US")
            platform = m.get("platform", "android")
            rev = m.get("revenue_daily")
            bl_key = f"{fmt}_{country}_revenue"
            bl_rev = bl.get(bl_key)

            if rev and bl_rev and bl_rev > 0:
                change = (rev - bl_rev) / bl_rev * 100

                if change <= self.REVENUE_DROP_CRITICAL:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="revenue_anomaly",
                        country=country, platform=platform, ad_format=fmt,
                        metric="revenue_daily", current_value=rev,
                        expected_value=bl_rev, change_pct=round(change, 1),
                        severity="critical",
                        description=f"{fmt} revenue {abs(change):.0f}% in {country}",
                        suggested_action="investigate_and_optimize",
                    ))
                elif change <= self.REVENUE_DROP_WARNING:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="revenue_anomaly",
                        country=country, platform=platform, ad_format=fmt,
                        metric="revenue_daily", current_value=rev,
                        expected_value=bl_rev, change_pct=round(change, 1),
                        severity="warning",
                        description=f"{fmt} revenue {abs(change):.0f}% in {country}",
                        suggested_action="monitor",
                    ))
                elif change >= self.REVENUE_SPIKE_OPPORTUNITY:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="revenue_anomaly",
                        country=country, platform=platform, ad_format=fmt,
                        metric="revenue_daily", current_value=rev,
                        expected_value=bl_rev, change_pct=round(change, 1),
                        severity="info",
                        description=f"{fmt} revenue +{change:.0f}% — investigate cause",
                        suggested_action="analyze_and_replicate",
                    ))

        signals.sort(key=lambda s: (
            0 if s.severity == "critical" else 1 if s.severity == "warning" else 2,
            s.change_pct,
        ))
        return signals


__all__ = ["RevenueAnalyzer"]
