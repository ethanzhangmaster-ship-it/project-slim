"""E15.2.4 — Fill Rate Analyzer + Waterfall Analyzer + Retention Impact"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from operation.optimizer.models import OptimizationSignal


class FillAnalyzer:
    FILL_DROP_CRITICAL = 15.0    # percentage points
    FILL_DROP_WARNING = 5.0

    def analyze(self, game_id: str, metrics: List[Dict[str, Any]],
                baselines: Optional[Dict[str, Any]] = None) -> List[OptimizationSignal]:
        signals: List[OptimizationSignal] = []
        bl = baselines or {}

        for m in metrics:
            fmt = m.get("format", "rewarded")
            country = m.get("country", "US")
            platform = m.get("platform", "android")
            fill = m.get("fill_rate")
            bl_key = f"{fmt}_{country}_fill"
            bl_fill = bl.get(bl_key)

            if fill is not None and bl_fill is not None:
                drop = (bl_fill - fill) * 100
                if drop >= self.FILL_DROP_CRITICAL:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="fill_drop",
                        country=country, platform=platform, ad_format=fmt,
                        metric="fill_rate", current_value=fill,
                        expected_value=bl_fill, change_pct=round(-drop, 1),
                        severity="critical",
                        description=f"{fmt} fill {drop:.0f}pp in {country}",
                        suggested_action="add_waterfall_networks",
                    ))
                elif drop >= self.FILL_DROP_WARNING:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="fill_drop",
                        country=country, platform=platform, ad_format=fmt,
                        metric="fill_rate", current_value=fill,
                        expected_value=bl_fill, change_pct=round(-drop, 1),
                        severity="warning",
                        description=f"{fmt} fill {drop:.0f}pp in {country}",
                        suggested_action="adjust_floor_or_add_bidder",
                    ))

        return signals


class WaterfallAnalyzer:
    """Analyzes network performance within a waterfall."""

    MIN_ECPM_DIFF_FOR_REORDER = 0.50
    MIN_IMPRESSIONS = 1000

    def analyze(self, game_id: str, format: str, country: str,
                network_data: List[Dict[str, Any]],
                current_order: List[str]) -> List[OptimizationSignal]:
        signals: List[OptimizationSignal] = []

        perf: Dict[str, float] = {}
        for nd in network_data:
            network = nd.get("network", "")
            ecpm = nd.get("ecpm_7d_avg")
            imps = nd.get("impressions_7d", 0)
            if ecpm and imps >= self.MIN_IMPRESSIONS:
                perf[network] = ecpm

        if len(perf) < 2:
            return signals

        optimal = sorted(perf.keys(), key=lambda n: perf[n], reverse=True)
        if optimal != current_order:
            old_top = current_order[0] if current_order else ""
            new_top = optimal[0] if optimal else ""
            if old_top in perf and new_top in perf:
                diff = perf[new_top] - perf[old_top]
                if diff >= self.MIN_ECPM_DIFF_FOR_REORDER:
                    signals.append(OptimizationSignal(
                        game_id=game_id, signal_type="network_underperform",
                        country=country, platform="", ad_format=format,
                        metric="ecpm", current_value=perf[new_top],
                        expected_value=perf[old_top], change_pct=round(diff, 2),
                        severity="warning",
                        description=f"Waterfall reorder: {new_top} > {old_top} by ${diff:.2f}",
                        suggested_action="reorder_waterfall",
                        metadata={"old_order": current_order, "new_order": optimal},
                    ))

        # Detect underperforming networks
        avg_ecpm = sum(perf.values()) / len(perf) if perf else 0
        for network, ecpm in perf.items():
            if ecpm < avg_ecpm * 0.7:
                signals.append(OptimizationSignal(
                    game_id=game_id, signal_type="network_underperform",
                    country=country, platform="", ad_format=format,
                    metric="ecpm", current_value=ecpm, expected_value=avg_ecpm,
                    change_pct=round((ecpm - avg_ecpm) / avg_ecpm * 100, 1),
                    severity="info",
                    description=f"{network} eCPM ${ecpm} below avg ${avg_ecpm:.1f}",
                    suggested_action="lower_network_priority",
                    metadata={"network": network},
                ))

        return signals


class RetentionImpactAnalyzer:
    """Evaluates ad changes against retention impact."""

    RETENTION_D1_BLOCK = -8.0
    RETENTION_D1_WARN = -3.0

    def analyze(self, game_id: str, retention_data: Dict[str, Any],
                proposed_changes: List[Dict[str, Any]]) -> List[OptimizationSignal]:
        signals: List[OptimizationSignal] = []

        current_d1 = retention_data.get("d1", 0.35)
        current_d7 = retention_data.get("d7", 0.15)

        for change in proposed_changes:
            est_retention_impact = change.get("retention_impact_pct", 0)
            if est_retention_impact <= self.RETENTION_D1_BLOCK:
                signals.append(OptimizationSignal(
                    game_id=game_id, signal_type="retention_risk",
                    country=change.get("country", ""),
                    platform=change.get("platform", ""),
                    ad_format=change.get("ad_format", ""),
                    metric="retention_d1", current_value=current_d1,
                    expected_value=current_d1 * (1 + est_retention_impact / 100),
                    change_pct=est_retention_impact, severity="critical",
                    description=f"D1 retention risk {abs(est_retention_impact):.0f}% — BLOCK",
                    suggested_action="reject_change",
                ))
            elif est_retention_impact <= self.RETENTION_D1_WARN:
                signals.append(OptimizationSignal(
                    game_id=game_id, signal_type="retention_risk",
                    country=change.get("country", ""),
                    platform=change.get("platform", ""),
                    ad_format=change.get("ad_format", ""),
                    metric="retention_d1", current_value=current_d1,
                    expected_value=current_d1 * (1 + est_retention_impact / 100),
                    change_pct=est_retention_impact, severity="warning",
                    description=f"D1 retention risk {abs(est_retention_impact):.0f}%",
                    suggested_action="review",
                ))

        return signals


__all__ = ["FillAnalyzer", "WaterfallAnalyzer", "RetentionImpactAnalyzer"]
