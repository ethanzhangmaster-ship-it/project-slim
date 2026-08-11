"""
E15.2.4 — Revenue Analyzer

Detects monetization issues from raw metrics:
- eCPM decline per format/country
- Fill rate drops
- Revenue anomalies
- Opportunity detection

Deterministic rules, sample-driven, no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RevenueIssue:
    """A detected monetization issue or opportunity."""
    issue_type: str          # "ecpm_decline", "fill_drop", "revenue_anomaly"
    game_id: str
    severity: str            # "critical", "warning", "info"
    format: str              # "rewarded", "interstitial", "banner"
    country: str
    platform: str
    current_value: float
    baseline_value: float
    change_pct: float
    description: str
    suggested_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class RevenueAnalyzer:
    """Deterministic revenue issue detector."""

    # Thresholds
    ECPM_DECLINE_CRITICAL = -20.0   # critical if eCPM drops > 20%
    ECPM_DECLINE_WARNING = -10.0    # warning if > 10%
    FILL_DROP_CRITICAL = 15.0       # critical if fill drops > 15pp
    FILL_DROP_WARNING = 5.0         # warning if > 5pp
    REVENUE_DROP_CRITICAL = -15.0
    REVENUE_DROP_WARNING = -8.0

    def analyze(
        self,
        game_id: str,
        metrics: List[Dict[str, Any]],
        baselines: Optional[Dict[str, Any]] = None,
    ) -> List[RevenueIssue]:
        """Analyze metrics and return detected issues."""
        issues: List[RevenueIssue] = []
        bl = baselines or {}

        for m in metrics:
            fmt = m.get("format", "rewarded")
            country = m.get("country", "US")
            platform = m.get("platform", "android")

            # eCPM
            ecpm = m.get("ecpm")
            bl_ecpm = bl.get(f"{fmt}_{country}_ecpm")
            if ecpm and bl_ecpm and bl_ecpm > 0:
                change = (ecpm - bl_ecpm) / bl_ecpm * 100
                if change <= self.ECPM_DECLINE_CRITICAL:
                    issues.append(RevenueIssue(
                        issue_type="ecpm_decline",
                        game_id=game_id, severity="critical",
                        format=fmt, country=country, platform=platform,
                        current_value=ecpm, baseline_value=bl_ecpm,
                        change_pct=round(change, 1),
                        description=f"{fmt} eCPM dropped {abs(change):.0f}% in {country}",
                        suggested_action="raise_bid_floor",
                    ))
                elif change <= self.ECPM_DECLINE_WARNING:
                    issues.append(RevenueIssue(
                        issue_type="ecpm_decline",
                        game_id=game_id, severity="warning",
                        format=fmt, country=country, platform=platform,
                        current_value=ecpm, baseline_value=bl_ecpm,
                        change_pct=round(change, 1),
                        description=f"{fmt} eCPM declining {abs(change):.0f}% in {country}",
                        suggested_action="monitor_or_adjust_waterfall",
                    ))

            # Fill rate
            fill = m.get("fill_rate")
            bl_fill = bl.get(f"{fmt}_{country}_fill")
            if fill is not None and bl_fill is not None:
                drop = (bl_fill - fill) * 100  # in percentage points
                if drop >= self.FILL_DROP_CRITICAL:
                    issues.append(RevenueIssue(
                        issue_type="fill_drop",
                        game_id=game_id, severity="critical",
                        format=fmt, country=country, platform=platform,
                        current_value=fill, baseline_value=bl_fill,
                        change_pct=round(-drop, 1),
                        description=f"{fmt} fill rate dropped {drop:.0f}pp in {country}",
                        suggested_action="add_waterfall_networks",
                    ))
                elif drop >= self.FILL_DROP_WARNING:
                    issues.append(RevenueIssue(
                        issue_type="fill_drop",
                        game_id=game_id, severity="warning",
                        format=fmt, country=country, platform=platform,
                        current_value=fill, baseline_value=bl_fill,
                        change_pct=round(-drop, 1),
                        description=f"{fmt} fill rate declining {drop:.0f}pp in {country}",
                        suggested_action="adjust_floor_or_add_bidder",
                    ))

            # Revenue
            rev = m.get("revenue_daily")
            bl_rev = bl.get(f"{fmt}_{country}_revenue")
            if rev and bl_rev and bl_rev > 0:
                change = (rev - bl_rev) / bl_rev * 100
                if change <= self.REVENUE_DROP_CRITICAL:
                    issues.append(RevenueIssue(
                        issue_type="revenue_anomaly",
                        game_id=game_id, severity="critical",
                        format=fmt, country=country, platform=platform,
                        current_value=rev, baseline_value=bl_rev,
                        change_pct=round(change, 1),
                        description=f"{fmt} revenue dropped {abs(change):.0f}% in {country}",
                        suggested_action="investigate_and_optimize",
                    ))
                elif change <= self.REVENUE_DROP_WARNING:
                    issues.append(RevenueIssue(
                        issue_type="revenue_anomaly",
                        game_id=game_id, severity="warning",
                        format=fmt, country=country, platform=platform,
                        current_value=rev, baseline_value=bl_rev,
                        change_pct=round(change, 1),
                        description=f"{fmt} revenue declining {abs(change):.0f}%",
                        suggested_action="monitor",
                    ))

        # Sort: critical first, then by impact
        issues.sort(key=lambda i: (
            0 if i.severity == "critical" else 1 if i.severity == "warning" else 2,
            i.change_pct,
        ))
        return issues

    def detect_opportunities(
        self, game_id: str, metrics: List[Dict[str, Any]]
    ) -> List[RevenueIssue]:
        """Detect positive opportunities (eCPM trending up, room to raise floor)."""
        opportunities: List[RevenueIssue] = []
        for m in metrics:
            ecpm = m.get("ecpm")
            floor = m.get("bid_floor", 0)
            if ecpm and floor > 0 and ecpm > floor * 1.5:
                opportunities.append(RevenueIssue(
                    issue_type="floor_opportunity",
                    game_id=game_id, severity="info",
                    format=m.get("format", "rewarded"),
                    country=m.get("country", "US"),
                    platform=m.get("platform", "android"),
                    current_value=ecpm, baseline_value=floor,
                    change_pct=round((ecpm - floor) / floor * 100, 1),
                    description=f"eCPM {ecpm} significantly above floor {floor}",
                    suggested_action="raise_bid_floor",
                ))
        return opportunities


__all__ = ["RevenueAnalyzer", "RevenueIssue"]
