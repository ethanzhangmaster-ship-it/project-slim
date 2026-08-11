"""
E15.1.1 — Store Risk Predictor
==============================

Combines PolicyReport + PrivacyReport + metadata-quality signals into a
per-store rejection probability and the top reasons.

Deterministic weighted model (no LLM). Each fired risk adds weight;
probabilities are clamped to [0,1].

  Apple (4.3 spam sensitive):
      policy flags heavy  + privacy gaps  + metadata thin
  Google (policy/privacy sensitive, less 4.3 strict):
      privacy gaps  + metadata thin  (policy flags lighter)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from operation.publishing_factory.compliance.policy_scanner import PolicyReport
from operation.publishing_factory.compliance.privacy_checker import PrivacyReport
from operation.publishing_factory.catalog.product_profile import GameProduct


@dataclass
class RiskPrediction:
    game_id: str
    apple_prob: float
    google_prob: float
    level: str                  # "low" | "medium" | "high"
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id,
                "apple_prob": round(self.apple_prob, 3),
                "google_prob": round(self.google_prob, 3),
                "level": self.level, "reasons": list(self.reasons)}


class StoreRiskPredictor:
    """Fused rejection-probability estimator per store."""

    def predict(self, game: GameProduct, policy: PolicyReport,
                privacy: PrivacyReport) -> RiskPrediction:
        reasons: List[str] = []

        # --- shared signals ---
        privacy_gap = 0.0 if privacy.passed else min(0.4, 0.12 * len(privacy.issues))
        if not privacy.passed:
            reasons.append(f"privacy gaps ({len(privacy.issues)})")

        meta_thin = 0.0
        if not game.keywords or len(game.keywords) < 3:
            meta_thin += 0.1
            reasons.append("thin keyword set")
        if not game.display_name:
            meta_thin += 0.05

        # --- policy / 4.3 signal ---
        policy_w = 0.0
        if not policy.clean:
            # strongest single flag drives it
            policy_w = min(0.5, 0.15 * len(policy.flags)
                           + 0.2 * policy.max_similarity)
            reasons.append(f"similarity to {len(policy.flags)} fleet game(s)")

        apple = min(1.0, policy_w * 1.0 + privacy_gap * 0.9 + meta_thin * 0.8)
        google = min(1.0, policy_w * 0.6 + privacy_gap * 1.0 + meta_thin * 0.7)

        level = "low"
        if max(apple, google) >= 0.5:
            level = "high"
        elif max(apple, google) >= 0.25:
            level = "medium"
        if level != "high" and not reasons:
            reasons.append("clean — low rejection risk")

        return RiskPrediction(
            game_id=game.game_id, apple_prob=round(apple, 3),
            google_prob=round(google, 3), level=level, reasons=reasons)


__all__ = ["StoreRiskPredictor", "RiskPrediction"]
