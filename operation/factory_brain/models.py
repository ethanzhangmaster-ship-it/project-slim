"""
E15.1.2 — Game Factory Brain: Core Models
==========================================

The brain closes the loop:

    Growth OS (opportunity)  ->  Publishing Factory (production)
        ^                                |
        |                                v
    Product Memory  <-  Revenue OS (monetization outcomes)

Everything here is a deterministic, JSON-serializable dataclass.
No LLM, no real API. The brain PROPOSES; humans execute.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


# --------------------------------------------------------------------- #
# 1. Market opportunity (input contract from Growth OS — drop-in JSON)
# --------------------------------------------------------------------- #
@dataclass
class MarketOpportunity:
    """A structured opportunity signal.

    Sources:
      - "growth_os"  : dropped into data/market_opportunities.json by the
                       external Growth OS (same drop-in pattern as DAU).
      - "fleet"      : derived internally from the fleet's own metrics
                       (a genre that monetizes well = internal signal).
    """
    opportunity_id: str
    genre: str                       # merge / puzzle / idle / word / ...
    theme: str = ""                  # witch / castle / hospital / ...
    source: str = "growth_os"        # growth_os | fleet
    target_geos: List[str] = field(default_factory=lambda: ["US"])
    # deterministic sub-scores, each 0..1
    keyword_trend: float = 0.0       # search volume rising
    competition: float = 0.5         # 0 = empty market, 1 = saturated
    ecpm_signal: float = 0.0         # observed/known eCPM strength
    ltv_forecast: float = 0.0        # predicted LTV strength
    notes: str = ""

    def score(self) -> float:
        """Composite opportunity score, 0..1 (higher = better).

        competition is inverted: less competition = more attractive.
        Weights are fixed and documented — deterministic by design.
        """
        s = (0.30 * _clamp(self.keyword_trend)
             + 0.25 * (1.0 - _clamp(self.competition))
             + 0.25 * _clamp(self.ecpm_signal)
             + 0.20 * _clamp(self.ltv_forecast))
        return round(s, 4)

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "genre": self.genre, "theme": self.theme,
            "source": self.source, "target_geos": list(self.target_geos),
            "keyword_trend": self.keyword_trend,
            "competition": self.competition,
            "ecpm_signal": self.ecpm_signal,
            "ltv_forecast": self.ltv_forecast,
            "score": self.score(), "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MarketOpportunity":
        return cls(
            opportunity_id=d["opportunity_id"],
            genre=d.get("genre", "casual"),
            theme=d.get("theme", ""),
            source=d.get("source", "growth_os"),
            target_geos=list(d.get("target_geos", ["US"])),
            keyword_trend=float(d.get("keyword_trend", 0.0)),
            competition=float(d.get("competition", 0.5)),
            ecpm_signal=float(d.get("ecpm_signal", 0.0)),
            ltv_forecast=float(d.get("ltv_forecast", 0.0)),
            notes=d.get("notes", ""),
        )


# --------------------------------------------------------------------- #
# 1b. ROAS prediction (Product Opportunity Engine output)
# --------------------------------------------------------------------- #
@dataclass
class RoasPrediction:
    """Deterministic economics forecast for an opportunity.

    Mirrors the operator's mental model:

        prediction:
          CPI:       1.2      (install cost, USD)
          D30_ROAS:  0.65     (65% of spend recouped by day 30)
          D90_ROAS:  1.10     (110% -> profitable by day 90)
        confidence:  0.82

    No LLM: every number is a fixed function of the opportunity's
    sub-scores. Same inputs -> same forecast, always.
    """
    opportunity_id: str
    cpi: float = 0.0             # predicted install cost, USD
    d30_roas: float = 0.0        # fraction (0.65 == 65%)
    d90_roas: float = 0.0        # fraction (1.10 == 110%)
    confidence: float = 0.0      # 0..1
    payback_ok: bool = False     # d90_roas >= 1.0 (recoups within 90d)
    notes: str = ""

    def to_dict(self) -> dict:
        return {"opportunity_id": self.opportunity_id, "cpi": self.cpi,
                "d30_roas": self.d30_roas, "d90_roas": self.d90_roas,
                "confidence": self.confidence, "payback_ok": self.payback_ok,
                "notes": self.notes}


# --------------------------------------------------------------------- #
# 2. Product spec (opportunity -> concrete production order)
# --------------------------------------------------------------------- #
@dataclass
class ProductSpec:
    """The production order handed to the Publishing Factory.

    Mirrors the operator's product.yaml shape:

        product:      genre / theme / target_geo
        monetization: type (+ rewarded_focus / starter_pack)
        aso:          seed keywords
    """
    spec_id: str
    opportunity_id: str
    genre: str
    theme: str
    target_geos: List[str] = field(default_factory=lambda: ["US"])
    monetization: str = "hybrid"          # iaa | iap | hybrid
    rewarded_focus: bool = True
    starter_pack: bool = False
    aso_keywords: List[str] = field(default_factory=list)
    working_title: str = ""
    confidence: float = 0.0               # from opportunity score + priors
    pattern_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "spec_id": self.spec_id,
            "opportunity_id": self.opportunity_id,
            "product": {
                "genre": self.genre, "theme": self.theme,
                "target_geo": list(self.target_geos),
            },
            "monetization": {
                "type": self.monetization,
                "rewarded_focus": self.rewarded_focus,
                "starter_pack": self.starter_pack,
            },
            "aso": {"keywords": list(self.aso_keywords)},
            "working_title": self.working_title,
            "confidence": self.confidence,
            "pattern_notes": list(self.pattern_notes),
        }


# --------------------------------------------------------------------- #
# 2b. Game blueprint (spec -> full product design, handed to Unity agent)
# --------------------------------------------------------------------- #
@dataclass
class GameBlueprint:
    """A concrete product design derived from a ProductSpec.

    This is what the operator's example calls a "Game Blueprint":

        core_loop:  merge -> reward -> unlock
        iaa:        rewarded_video, interstitial
        iap:        starter_pack, remove_ads
        meta:       fantasy collection
        aso:        vampire merge, magic merge

    Deterministic: every field comes from fixed per-genre tables +
    the spec's monetization choice. Ready to hand to the Unity
    Operation Agent (E15.4) — no LLM.
    """
    blueprint_id: str
    spec_id: str
    genre: str
    theme: str
    core_loop: List[str] = field(default_factory=list)
    iaa: List[str] = field(default_factory=list)
    iap: List[str] = field(default_factory=list)
    meta: str = ""
    aso_keywords: List[str] = field(default_factory=list)
    target_geos: List[str] = field(default_factory=lambda: ["US"])

    def to_dict(self) -> dict:
        return {"blueprint_id": self.blueprint_id, "spec_id": self.spec_id,
                "genre": self.genre, "theme": self.theme,
                "core_loop": list(self.core_loop),
                "iaa": list(self.iaa), "iap": list(self.iap),
                "meta": self.meta,
                "aso_keywords": list(self.aso_keywords),
                "target_geos": list(self.target_geos)}


# --------------------------------------------------------------------- #
# 3. Portfolio lifecycle
# --------------------------------------------------------------------- #
class LifecycleStage(str, Enum):
    IDEA = "idea"
    PROTOTYPE = "prototype"
    SOFT_LAUNCH = "soft_launch"
    UA_TEST = "ua_test"
    SCALE = "scale"
    KILL = "kill"


# ordered progression (KILL reachable from anywhere)
STAGE_ORDER: List[str] = [
    LifecycleStage.IDEA.value,
    LifecycleStage.PROTOTYPE.value,
    LifecycleStage.SOFT_LAUNCH.value,
    LifecycleStage.UA_TEST.value,
    LifecycleStage.SCALE.value,
]


class PortfolioAction(str, Enum):
    ADVANCE = "advance"            # move to next stage
    INCREASE_BUDGET = "increase_budget"
    KEEP_OPTIMIZING = "keep_optimizing"
    STOP_UA = "stop_ua"
    BOOST_IAA = "boost_iaa"
    BOOST_IAP = "boost_iap"
    KILL = "kill"
    HOLD = "hold"


@dataclass
class PortfolioDecision:
    """One daily judgement for one game. requires_manual_apply is ALWAYS
    True — the brain never spends money or kills a game by itself."""
    game_id: str
    stage: str
    action: str
    reason: str
    metric_snapshot: Dict[str, float] = field(default_factory=dict)
    requires_manual_apply: bool = True

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "stage": self.stage,
                "action": self.action, "reason": self.reason,
                "metric_snapshot": dict(self.metric_snapshot),
                "requires_manual_apply": self.requires_manual_apply}


# --------------------------------------------------------------------- #
# 3b. Game decision engine verdict (KEEP / SCALE / KILL)
# --------------------------------------------------------------------- #
class Verdict(str, Enum):
    """The fund-manager verdict for one live game.

    FIX is IAA-specific: the game has live traffic and ads FILL but are
    never SHOWN (impressions == 0 while responses > 0) — a broken show
    path is an engineering ticket, not a portfolio kill.
    """
    KEEP = "keep"
    SCALE = "scale"
    KILL = "kill"
    FIX = "fix"


@dataclass
class GameDecision:
    """One retention/economics-aware verdict for a live game.

    Inputs (from GameProduct.metrics): d1_retention, d7_retention,
    cpi, roas, arpdau. Output: KEEP / SCALE / KILL with a human
    reason, a suggested budget delta, and a projected payback horizon.

    requires_manual_apply is ALWAYS True — the brain never spends
    money or archives a game on its own.
    """
    game_id: str
    verdict: str
    reason: str
    budget_delta_pct: float = 0.0        # +30 == raise UA budget 30%
    payback_days: float = 0.0            # projected days to recoup CPI
    metric_snapshot: Dict[str, float] = field(default_factory=dict)
    requires_manual_apply: bool = True
    mode: str = "ua"                     # "ua" (CPI/ROAS) | "iaa" (rev/DAU)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "verdict": self.verdict,
                "reason": self.reason,
                "budget_delta_pct": self.budget_delta_pct,
                "payback_days": self.payback_days,
                "metric_snapshot": dict(self.metric_snapshot),
                "requires_manual_apply": self.requires_manual_apply,
                "mode": self.mode}


# --------------------------------------------------------------------- #
# 4. Success pattern (Revenue OS -> next-generation weights)
# --------------------------------------------------------------------- #
@dataclass
class SuccessPattern:
    """A mined "what works" combination.

    Example: genre=merge + theme=fantasy + rewarded_focus
             success_rate=0.18 over sample=11 games.
    """
    pattern_id: str
    genre: str
    theme: str = ""
    monetization: str = ""
    rewarded_focus: bool = False
    success_rate: float = 0.0
    sample: int = 0
    avg_revenue_per_dau: float = 0.0
    weight: float = 1.0            # multiplier applied to spec confidence

    def to_dict(self) -> dict:
        return {"pattern_id": self.pattern_id, "genre": self.genre,
                "theme": self.theme, "monetization": self.monetization,
                "rewarded_focus": self.rewarded_focus,
                "success_rate": self.success_rate, "sample": self.sample,
                "avg_revenue_per_dau": self.avg_revenue_per_dau,
                "weight": self.weight}


# --------------------------------------------------------------------- #
# 5. ASO bandit
# --------------------------------------------------------------------- #
@dataclass
class AsoVariant:
    """One store-listing variant being trialled (title/icon/screenshot)."""
    variant_id: str
    game_id: str
    kind: str                       # "title" | "icon" | "screenshot_set"
    payload: str                    # e.g. "Merge Magic Castle"
    impressions: int = 0
    installs: int = 0

    def cvr(self) -> float:
        if self.impressions <= 0:
            return 0.0
        return round(self.installs / self.impressions, 4)

    def to_dict(self) -> dict:
        return {"variant_id": self.variant_id, "game_id": self.game_id,
                "kind": self.kind, "payload": self.payload,
                "impressions": self.impressions, "installs": self.installs,
                "cvr": self.cvr()}


@dataclass
class StoreExperimentPlan:
    """A ready-to-run store experiment (PPO / Play listing experiment).

    The brain generates the variant assets/copy; the operator creates the
    experiment in App Store Connect / Play Console by hand (no real API).
    """
    experiment_id: str
    game_id: str
    store: str                      # "app_store" | "google_play"
    trigger: str                    # e.g. "install_rate_drop"
    icon_variants: List[str] = field(default_factory=list)
    screenshot_variants: List[str] = field(default_factory=list)
    copy_variants: List[str] = field(default_factory=list)
    requires_manual_apply: bool = True

    def to_dict(self) -> dict:
        return {"experiment_id": self.experiment_id, "game_id": self.game_id,
                "store": self.store, "trigger": self.trigger,
                "icon_variants": list(self.icon_variants),
                "screenshot_variants": list(self.screenshot_variants),
                "copy_variants": list(self.copy_variants),
                "requires_manual_apply": self.requires_manual_apply}


# --------------------------------------------------------------------- #
# 6. Brain daily report
# --------------------------------------------------------------------- #
@dataclass
class BrainReport:
    """Output of one FactoryBrain.run_daily() cycle."""
    date: str = ""
    opportunities: List[MarketOpportunity] = field(default_factory=list)
    predictions: List[RoasPrediction] = field(default_factory=list)
    specs: List[ProductSpec] = field(default_factory=list)
    blueprints: List[GameBlueprint] = field(default_factory=list)
    decisions: List[PortfolioDecision] = field(default_factory=list)
    verdicts: List[GameDecision] = field(default_factory=list)
    patterns: List[SuccessPattern] = field(default_factory=list)
    aso_winners: List[dict] = field(default_factory=list)
    store_experiments: List[StoreExperimentPlan] = field(default_factory=list)
    real_api_called: bool = False   # locked False, forever

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "predictions": [p.to_dict() for p in self.predictions],
            "specs": [s.to_dict() for s in self.specs],
            "blueprints": [b.to_dict() for b in self.blueprints],
            "decisions": [d.to_dict() for d in self.decisions],
            "verdicts": [v.to_dict() for v in self.verdicts],
            "patterns": [p.to_dict() for p in self.patterns],
            "aso_winners": list(self.aso_winners),
            "store_experiments": [e.to_dict() for e in self.store_experiments],
            "real_api_called": self.real_api_called,
        }


__all__ = [
    "MarketOpportunity", "RoasPrediction", "ProductSpec", "GameBlueprint",
    "LifecycleStage", "STAGE_ORDER", "PortfolioAction", "PortfolioDecision",
    "Verdict", "GameDecision",
    "SuccessPattern", "AsoVariant", "StoreExperimentPlan", "BrainReport",
]
