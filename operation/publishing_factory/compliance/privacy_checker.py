"""
E15.1.1 — Privacy Checker
==========================

Validates the privacy/age-gate posture of a game BEFORE submission.

Apple + Google both reject for missing privacy policy / improper
child-directed handling. Deterministic checklist over a product's
privacy metadata (carried on GameProduct.metrics or a privacy dict).

Checks:
  - privacy_policy_url present (non-empty)
  - data_collection_disclosed is True
  - if child_directed -> has age_gate AND coppa_compliant
  - if IAA/IAP -> has privacy choices / consent flag
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from operation.publishing_factory.catalog.product_profile import GameProduct


@dataclass
class PrivacyReport:
    game_id: str
    passed: bool
    issues: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "passed": self.passed,
                "issues": list(self.issues), "checks": dict(self.checks)}


class PrivacyChecker:
    """Deterministic privacy/age-gate compliance check."""

    def check(self, game: GameProduct,
              privacy: Dict[str, object] = None) -> PrivacyReport:
        privacy = privacy or {}
        issues: List[str] = []
        checks: Dict[str, bool] = {}

        url = privacy.get("privacy_policy_url") or game.metrics.get("privacy_policy_url", "")
        checks["privacy_policy_url"] = bool(url)
        if not url:
            issues.append("missing privacy_policy_url")

        disclosed = privacy.get("data_collection_disclosed",
                                game.metrics.get("data_collection_disclosed", False))
        checks["data_collection_disclosed"] = bool(disclosed)
        if not disclosed:
            issues.append("data collection not disclosed")

        child = privacy.get("child_directed",
                            game.metrics.get("child_directed", False))
        if child:
            age_gate = privacy.get("age_gate",
                                   game.metrics.get("age_gate", False))
            coppa = privacy.get("coppa_compliant",
                                game.metrics.get("coppa_compliant", False))
            checks["age_gate"] = bool(age_gate)
            checks["coppa_compliant"] = bool(coppa)
            if not age_gate:
                issues.append("child-directed but no age gate")
            if not coppa:
                issues.append("child-directed but not COPPA compliant")

        if game.monetization in ("iaa", "iap", "hybrid"):
            consent = privacy.get("has_consent",
                                  game.metrics.get("has_consent", False))
            checks["has_consent"] = bool(consent)
            if not consent:
                issues.append("monetized but no consent/choices flag")

        return PrivacyReport(game_id=game.game_id, passed=len(issues) == 0,
                             issues=issues, checks=checks)


__all__ = ["PrivacyChecker", "PrivacyReport"]
