"""
E15.2.5 — Monetization Intelligence data models.

Input contract: raw MAX Report API rows (list[dict]) with columns
    day, application, ad_format, country, network,
    impressions, attempts, responses, ecpm, estimated_revenue

All detectors are deterministic rules (no LLM). Phase 1 output is
recommendation-only: every action carries requires_manual_apply=True.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def fnum(x: Any, d: float = 0.0) -> float:
    try:
        return float(x or d)
    except (TypeError, ValueError):
        return d


@dataclass
class SegmentStat:
    """Aggregated stats for one segment (network / app / country / format)."""
    key: str
    revenue: float = 0.0
    impressions: int = 0
    attempts: int = 0
    responses: int = 0
    days: int = 0

    @property
    def ecpm(self) -> float:
        return (self.revenue / self.impressions * 1000.0) if self.impressions else 0.0

    @property
    def show_rate(self) -> float:
        """impressions / attempts (win + display rate through the auction)."""
        return (self.impressions / self.attempts) if self.attempts else 0.0

    @property
    def fill_rate(self) -> float:
        """responses / attempts."""
        return (self.responses / self.attempts) if self.attempts else 0.0


@dataclass
class IntelSignal:
    """A detected issue/opportunity from one intelligence rule."""
    rule: str               # zombie_network | hidden_winner | waterfall_waste | bid_floor | revenue_concentration | geo_opportunity
    severity: str           # critical | warning | info
    action: str             # disable_network | quarantine_network | increase_bid_opportunity | adjust_bid_constraint | diversify | monitor | handoff_ua | reduce_waterfall_depth | review_segment
    target: str             # network name / app name / country / segment key
    confidence: float       # 0..1
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    requires_manual_apply: bool = True   # Phase 1: MAX API cannot write expanded-targeting waterfalls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule, "severity": self.severity, "action": self.action,
            "target": self.target, "confidence": self.confidence,
            "reason": self.reason, "metrics": self.metrics,
            "requires_manual_apply": self.requires_manual_apply,
        }


@dataclass
class ActionItem:
    """A prioritized, human-executable action for the daily report."""
    priority: str           # P0 | P1 | P2 | P3
    title: str
    action: str
    target: str
    expected_impact: str
    source_rule: str
    confidence: float
    requires_manual_apply: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority": self.priority, "title": self.title, "action": self.action,
            "target": self.target, "expected_impact": self.expected_impact,
            "source_rule": self.source_rule, "confidence": self.confidence,
            "requires_manual_apply": self.requires_manual_apply,
        }


@dataclass
class MonetizationDailyReport:
    """IAA Monetization Report — the E15.2.5 deliverable."""
    account: str
    date: str
    period_start: str
    period_end: str
    revenue: float
    impressions: int
    attempts: int
    blended_ecpm: float
    waterfall_depth: float          # attempts per impression
    health_score: int               # 0-100 — current monetization efficiency
    health_grade: str               # A/B/C/D
    # E15.2.5 calibration: Health alone is misleading. Split into three
    # orthogonal scores so a low-health account is not read as "hopeless".
    opportunity_score: int = 0      # 0-100 — recoverable in-app upside
    opportunity_grade: str = "LOW"  # HIGH/MEDIUM/LOW
    risk_score: int = 0             # 0-100 — revenue fragility (higher = riskier)
    risk_grade: str = "LOW"         # HIGH/MEDIUM/LOW
    scores: Dict[str, Any] = field(default_factory=dict)   # full breakdowns
    signals: List[IntelSignal] = field(default_factory=list)
    actions: List[ActionItem] = field(default_factory=list)
    # E15.2.5: actions sorted into Safe / Experiment / Observe execution
    # layers with an execution-value score (list of ValidatedAction dicts).
    validated_actions: List[Dict[str, Any]] = field(default_factory=list)
    # E15.2.5: user-side guardrail (ARPDAU / ads-per-user). May be a
    # PENDING record when no Adjust/Firebase key is configured.
    user_metrics: Dict[str, Any] = field(default_factory=dict)
    # E15.2.5+: Experiment & Verification Layer — tracked, manually-applied
    # changes and their verified outcomes (list of experiment dicts).
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    # E15.2.5+ Autonomous IAA: Target MAX Config recommendation (per
    # (app, geo, format) network ranking + floor ranges). Operator applies
    # manually; MAX Management API cannot write expanded-targeting waterfalls.
    config_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    # E15.2.5+ Autonomous IAA (increment 2): eCPM Prediction (module 6).
    # Next-period eCPM forecast per (app, geo, format, network) so the agent
    # is predictive, not just reactive. Pure forecast artifact (no writes).
    ecpm_forecasts: List[Dict[str, Any]] = field(default_factory=list)
    # E15.2.6+: IAA Growth Report — the result-driven daily view the operator
    # actually reads. Single KPI = IAA Revenue / DAU. Built by the agent's
    # run(); consumed by the Feishu card as the headline block.
    growth_report: Dict[str, Any] = field(default_factory=dict)
    # E15.2.6+: Auto-Executor decision layer — every proposed action is
    # tiered AUTO (AI auto-approves) / APPROVAL (needs human) / OBSERVE.
    # The human still applies in MAX; this only decides the risk tier.
    auto_executor: Dict[str, Any] = field(default_factory=dict)
    risks: List[str] = field(default_factory=list)
    sections: Dict[str, Any] = field(default_factory=dict)   # tables for md render

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account, "date": self.date,
            "period": {"start": self.period_start, "end": self.period_end},
            "totals": {
                "revenue": round(self.revenue, 2),
                "impressions": self.impressions,
                "attempts": self.attempts,
                "blended_ecpm": round(self.blended_ecpm, 2),
                "waterfall_depth": round(self.waterfall_depth, 1),
            },
            "health": {"score": self.health_score, "grade": self.health_grade},
            "opportunity": {"score": self.opportunity_score,
                            "grade": self.opportunity_grade},
            "risk": {"score": self.risk_score, "grade": self.risk_grade},
            "scores": self.scores,
            "signals": [s.to_dict() for s in self.signals],
            "actions": [a.to_dict() for a in self.actions],
            "validated_actions": self.validated_actions,
            "user_metrics": self.user_metrics,
            "experiments": self.experiments,
            "config_recommendations": self.config_recommendations,
            "ecpm_forecasts": self.ecpm_forecasts,
            "growth_report": self.growth_report,
            "auto_executor": self.auto_executor,
            "risks": self.risks,
        }
