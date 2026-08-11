"""Shared fixtures for revenue_optimizer tests (no live data)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.optimizer.intel_models import IntelSignal, MonetizationDailyReport


def sig(rule: str, target: str, action: str, confidence: float = 0.9,
        metrics: Optional[Dict[str, Any]] = None,
        severity: str = "warning", reason: str = "r") -> IntelSignal:
    return IntelSignal(rule=rule, severity=severity, action=action,
                        target=target, confidence=confidence, reason=reason,
                        metrics=metrics or {})


def zombie_sig(target: str = "CHARTBOOST", attempts: int = 100_000,
               rev: float = 1.0, confidence: float = 0.95) -> IntelSignal:
    return sig("zombie_network", target, "disable_network", confidence,
               {"attempts": attempts, "revenue": rev})


def winner_sig(target: str = "MINT_BIDDING", capture: float = 0.3,
               share: float = 0.03, ecpm: float = 80.0, imps: int = 5_000,
               confidence: float = 0.85) -> IntelSignal:
    return sig("hidden_winner", target, "increase_bid_opportunity", confidence,
               {"revenue_capture_rate": capture, "revenue_share": share,
                "ecpm": ecpm, "impressions": imps})


def floor_sig(target: str = "APPLOVIN_EXCHANGE", ecpm: float = 1.4,
              share: float = 0.10, rng: tuple = (1.0, 2.0),
              confidence: float = 0.85) -> IntelSignal:
    return sig("bid_floor", target, "adjust_bid_constraint", confidence,
               {"ecpm": ecpm, "impression_share": share,
                "recommended_floor_range": list(rng)})


def diversify_sig(target: str = "US", confidence: float = 0.6) -> IntelSignal:
    return sig("revenue_concentration", target, "diversify", confidence,
               {"concentration": 0.9})


def report(account: str = "ACCT_2", signals: Optional[List[IntelSignal]] = None,
           revenue: float = 10_000.0, blended: float = 57.0,
           impressions: int = 200_000, dau: float = 100_000.0,
           growth: Optional[Dict[str, Any]] = None) -> MonetizationDailyReport:
    return MonetizationDailyReport(
        account=account, date="2026-07-23",
        period_start="2026-07-14", period_end="2026-07-23",
        revenue=revenue, impressions=impressions, attempts=impressions,
        blended_ecpm=blended, waterfall_depth=1.0,
        health_score=60, health_grade="C",
        signals=signals or [], validated_actions=[],
        growth_report=growth or {"arpdau": 0.1, "revenue_per_dau": 0.1,
                                 "dau": dau})


def ctx(total_revenue: float = 10_000.0, blended: float = 57.0,
        impressions: int = 200_000, dau: float = 100_000.0) -> Dict[str, Any]:
    return {"total_revenue": total_revenue, "blended_ecpm": blended,
            "total_impressions": impressions, "dau": dau}


def max_rows(target: str = "MINT_BIDDING", applied: str = "2026-07-18"
             ) -> List[Dict[str, Any]]:
    """Build before/after MAX rows around an applied_at date for evaluation
    tests. Others stay flat at 100/day; target varies by scenario via kwargs
    is overkill — callers mutate the returned list."""
    rows: List[Dict[str, Any]] = []
    others = [("OTHER_A", 100.0), ("OTHER_B", 100.0)]
    for d in range(14, 18):           # before
        rows.append({"day": f"2026-07-{d:02d}", "application": "app",
                     "ad_format": "REWARD", "country": "US",
                     "network": target, "impressions": 1000,
                     "attempts": 1000, "responses": 1000,
                     "ecpm": 50.0, "estimated_revenue": 10.0})
        for n, r in others:
            rows.append({"day": f"2026-07-{d:02d}", "application": "app",
                         "ad_format": "REWARD", "country": "US", "network": n,
                         "impressions": 1000, "attempts": 1000,
                         "responses": 1000, "ecpm": 50.0,
                         "estimated_revenue": r})
    for d in range(19, 24):           # after
        rows.append({"day": f"2026-07-{d:02d}", "application": "app",
                     "ad_format": "REWARD", "country": "US",
                     "network": target, "impressions": 1000,
                     "attempts": 1000, "responses": 1000,
                     "ecpm": 50.0, "estimated_revenue": 20.0})
        for n, r in others:
            rows.append({"day": f"2026-07-{d:02d}", "application": "app",
                         "ad_format": "REWARD", "country": "US", "network": n,
                         "impressions": 1000, "attempts": 1000,
                         "responses": 1000, "ecpm": 50.0,
                         "estimated_revenue": r})
    return rows
