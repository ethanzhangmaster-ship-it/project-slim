"""
E15.1.1 — Publishing Factory (per-game plan builder)
====================================================

Turns ONE GameProduct into a complete PublishingPlan:

    game assets -> prepare -> generate (aso/screenshots/icon/video)
               -> check (compliance + risk) -> recommend + require approval

Design rules (mirrors the rest of the system):
  * Pure-python, deterministic, NO LLM.
  * Three-tier sandbox gate: SIMULATION -> SHADOW -> PRODUCTION.
    Generators NEVER call a real store API, so real_api_called is
    always False here. Only the final "submit" step (delegated to the
    existing E15.1 PublishingAgent) may touch PRODUCTION, and only
    after human approval + unlock.
  * The plan is a RECOMMENDATION. It carries `requires_approval=True`
    and an `approval_status` that must become "approved" before any
    real submit.

Reuses (does NOT rewrite) E15.1's PublishingAgent for the actual
store call path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from monetization.providers.models import SandboxMode

from operation.publishing_factory.asset_pipeline.screenshot_generator import (
    ScreenshotGenerator, ScreenshotSet,
)
from operation.publishing_factory.asset_pipeline.icon_generator import (
    IconGenerator, IconSpec,
)
from operation.publishing_factory.asset_pipeline.video_generator import (
    VideoGenerator, VideoStoryboard,
)
from operation.publishing_factory.asset_pipeline.asset_validator import (
    AssetValidator, AssetValidationReport,
)
from operation.publishing_factory.metadata_engine.aso_generator import (
    AsoGenerator, AsoPack,
)
from operation.publishing_factory.metadata_engine.localization_engine import (
    LocalizationEngine,
)
from operation.publishing_factory.metadata_engine.keyword_optimizer import (
    KeywordOptimizer,
)
from operation.publishing_factory.compliance.policy_scanner import (
    PolicyScanner, PolicyReport,
)
from operation.publishing_factory.compliance.privacy_checker import (
    PrivacyChecker, PrivacyReport,
)
from operation.publishing_factory.compliance.store_risk_predictor import (
    StoreRiskPredictor, RiskPrediction,
)
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.memory import PublishingMemory
from operation.publishing_factory.auto_pilot import auto_pilot_enabled


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PublishingPlan:
    game_id: str
    sandbox: str
    # generated assets + metadata
    screenshots: ScreenshotSet = None
    icon: IconSpec = None
    video: VideoStoryboard = None
    aso: AsoPack = None
    localized: Dict[str, dict] = field(default_factory=dict)
    keywords_selected: List[str] = field(default_factory=list)
    # checks
    asset_validation: AssetValidationReport = None
    policy: PolicyReport = None
    privacy: PrivacyReport = None
    risk: RiskPrediction = None
    # decision
    requires_approval: bool = True
    approval_status: str = "pending"
    recommended: bool = False
    predicted_cvr_lift_pct: float = 0.0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "sandbox": self.sandbox,
            "screenshots": self.screenshots.to_dict() if self.screenshots else None,
            "icon": self.icon.to_dict() if self.icon else None,
            "video": self.video.to_dict() if self.video else None,
            "aso": self.aso.to_dict() if self.aso else None,
            "localized": self.localized,
            "keywords_selected": list(self.keywords_selected),
            "asset_validation": (self.asset_validation.to_dict()
                                 if self.asset_validation else None),
            "policy": self.policy.to_dict() if self.policy else None,
            "privacy": self.privacy.to_dict() if self.privacy else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "requires_approval": self.requires_approval,
            "approval_status": self.approval_status,
            "recommended": self.recommended,
            "predicted_cvr_lift_pct": self.predicted_cvr_lift_pct,
            "notes": list(self.notes),
        }


class PublishingFactory:
    """Builds a PublishingPlan for a single game."""

    def __init__(self, sandbox: SandboxMode = SandboxMode.SIMULATION,
                 memory: PublishingMemory = None,
                 competitor_hints: Dict[str, List[str]] = None,
                 privacy: Dict[str, object] = None):
        self.sandbox = sandbox
        self.memory = memory or PublishingMemory()
        self.competitor_hints = competitor_hints or {}
        self.privacy = privacy or {}
        # engines
        self.screenshot_gen = ScreenshotGenerator(count=5)
        self.icon_gen = IconGenerator()
        self.video_gen = VideoGenerator()
        self.asset_validator = AssetValidator()
        self.aso_gen = AsoGenerator()
        self.localizer = LocalizationEngine()
        self.kw_opt = KeywordOptimizer()
        self.policy_scan = PolicyScanner()
        self.privacy_check = PrivacyChecker()
        self.risk_pred = StoreRiskPredictor()

    # ------------------------------------------------------------------ #
    def build_plan(self, game: GameProduct,
                   fleet: List[GameProduct] = None) -> PublishingPlan:
        fleet = fleet or []
        plan = PublishingPlan(game_id=game.game_id,
                              sandbox=self.sandbox.value)

        # 1) assets
        plan.screenshots = self.screenshot_gen.generate(game)
        plan.icon = self.icon_gen.generate(game)
        plan.video = self.video_gen.generate(game)

        # 2) metadata / ASO
        plan.aso = self.aso_gen.generate(
            game, competitor_hints=self.competitor_hints.get(game.game_id))
        loc = self.localizer.localize(plan.aso)
        plan.localized = {k: v.to_dict() for k, v in loc.items()}
        genre_seeds = self._genre_seeds(game.genre)
        kw_plan = self.kw_opt.optimize(game.game_id, plan.aso.keywords,
                                       genre_seed=genre_seeds)
        plan.keywords_selected = kw_plan.selected
        game.keywords = kw_plan.selected  # refresh on product

        # 3) asset validation
        plan.asset_validation = self.asset_validator.validate(
            game.game_id, plan.screenshots, plan.icon, plan.video)

        # 4) compliance
        plan.policy = self.policy_scan.scan(game, fleet)
        plan.privacy = self.privacy_check.check(game, self.privacy)
        plan.risk = self.risk_pred.predict(game, plan.policy, plan.privacy)

        # 5) decision
        plan.recommended = (plan.asset_validation.valid
                            and plan.policy.clean
                            and plan.privacy.passed
                            and plan.risk.level != "high")
        # predicted CVR lift: memory-informed if available, else heuristic
        lift = self._predict_lift(game, plan)
        plan.predicted_cvr_lift_pct = lift

        # ---- auto-pilot: auto-approve passing plans ----
        if auto_pilot_enabled() and plan.recommended:
            plan.requires_approval = False
            plan.approval_status = "approved"
            plan.notes.append("auto-pilot: auto-approved (env)")

        if not plan.asset_validation.valid:
            plan.notes.append("asset validation failed — fix before submit")
        if plan.risk.level == "high":
            plan.notes.append("high rejection risk — human review required")
        if plan.recommended:
            plan.notes.append(f"recommended: est. store CVR +{lift:.0f}%")
        return plan

    # ------------------------------------------------------------------ #
    @staticmethod
    def _genre_seeds(genre: str) -> List[str]:
        from operation.publishing_factory.metadata_engine.aso_generator import (
            _SEED_KW,
        )
        return list(_SEED_KW.get(genre, _SEED_KW["casual"]))

    def _predict_lift(self, game: GameProduct, plan: PublishingPlan) -> float:
        # memory-informed: if prior good screenshot style exists for genre
        best = self.memory.best_style(game.genre)
        base = 8.0
        if best:
            base = 12.0
        # reduce lift if high risk
        if plan.risk.level == "high":
            base = 0.0
        elif plan.risk.level == "medium":
            base *= 0.5
        return round(base, 1)

    # ------------------------------------------------------------------ #
    # three-tier gate helpers (human approval simulation)
    def approve(self, plan: PublishingPlan, approve: bool = True) -> PublishingPlan:
        plan.approval_status = ("approved" if approve else "rejected")
        return plan

    @property
    def real_api_called(self) -> bool:
        # factory never calls a store; the E15.1 agent does, gated.
        return False


__all__ = ["PublishingFactory", "PublishingPlan", "ApprovalStatus"]
