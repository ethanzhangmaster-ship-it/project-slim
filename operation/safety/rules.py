"""
E15.2.2 — Action Safety Rules Engine

Deterministic safety rules for monetization operations:
- Revenue protection (expected loss > 10% → blocked)
- Retention protection (retention risk → require_confirmation)
- Frequency caps (hard limits on ad frequency)
- Rollback requirement (major changes need rollback snapshot)
- Past evidence check (similar operations with negative outcomes → warning)

All rules are deterministic — no LLM, no ML.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import SafetyCheck, SafetyResult

# --------------------------------------------------------------------------- #
# Safety thresholds (tunable per game)
# --------------------------------------------------------------------------- #
MAX_REVENUE_LOSS_PCT = 10.0          # block if expected loss > 10%
REVENUE_WARNING_THRESHOLD = 3.0      # warn if expected loss > 3%
RETENTION_DROP_WARNING = 3.0         # warn if retention drop > 3%
RETENTION_DROP_BLOCK = 8.0           # block if retention drop > 8%

# Ad frequency hard caps (seconds between ads)
FREQUENCY_CAPS = {
    "interstitial": 90,
    "rewarded": 30,
    "banner": 1,
    "app_open": 120,
}

# Operations that always require rollback snapshot
ROLLBACK_REQUIRED_OPS = {
    "raise_bid_floor", "lower_bid_floor", "add_waterfall_network",
    "remove_waterfall_network", "update_price", "delete_product",
    "change_frequency_cap", "disable_ad_format",
}


# --------------------------------------------------------------------------- #
# Rule Base
# --------------------------------------------------------------------------- #
class SafetyRule(ABC):
    """One safety check rule."""

    name: str = "base"

    @abstractmethod
    def check(self, sc: SafetyCheck) -> List[str]:
        """Return list of violation descriptions, empty if safe."""
        ...


class RevenueProtectionRule(SafetyRule):
    """Block operations expected to lose too much revenue."""

    name = "revenue_protection"

    def check(self, sc: SafetyCheck) -> List[str]:
        violations = []
        impact = sc.expected_impact.get("revenue_change_pct", 0)
        if impact is not None and impact < -MAX_REVENUE_LOSS_PCT:
            violations.append(
                f"Expected revenue loss {abs(impact):.1f}% exceeds max {MAX_REVENUE_LOSS_PCT}%"
            )
        return violations


class RevenueWarningRule(SafetyRule):
    """Warn about significant revenue impact (but not block-level)."""

    name = "revenue_warning"

    def check(self, sc: SafetyCheck) -> List[str]:
        impact = sc.expected_impact.get("revenue_change_pct", 0)
        if impact is not None and impact < -REVENUE_WARNING_THRESHOLD:
            return [f"Expected revenue impact: {impact:+.1f}%"]
        return []


class RetentionProtectionRule(SafetyRule):
    """Block operations with unacceptable retention risk."""

    name = "retention_protection"

    def check(self, sc: SafetyCheck) -> List[str]:
        violations = []
        drop = sc.expected_impact.get("retention_change_pct", 0)
        if drop is not None and drop < -RETENTION_DROP_BLOCK:
            violations.append(
                f"Expected retention drop {abs(drop):.1f}% exceeds max {RETENTION_DROP_BLOCK}%"
            )
        return violations


class RetentionWarningRule(SafetyRule):
    """Warn about noticeable retention impact."""

    name = "retention_warning"

    def check(self, sc: SafetyCheck) -> List[str]:
        drop = sc.expected_impact.get("retention_change_pct", 0)
        if drop is not None and drop < -RETENTION_DROP_WARNING:
            ret = sc.current_metrics.get("retention_d1", "?")
            return [f"Retention risk: D1 may drop from {ret} by {abs(drop):.1f}%"]
        return []


class FrequencyCapRule(SafetyRule):
    """Enforce hard limits on ad frequency."""

    name = "frequency_cap"

    def check(self, sc: SafetyCheck) -> List[str]:
        ad_format = sc.changes.get("ad_format", "")
        if ad_format not in FREQUENCY_CAPS:
            return []

        new_interval = sc.changes.get("interval_seconds", sc.changes.get("frequency", 0))
        cap = FREQUENCY_CAPS[ad_format]

        if isinstance(new_interval, (int, float)) and new_interval < cap:
            return [f"{ad_format} interval {new_interval}s below minimum {cap}s"]
        return []


class RollbackRule(SafetyRule):
    """Require rollback snapshot for major changes."""

    name = "rollback_check"

    def check(self, sc: SafetyCheck) -> List[str]:
        if sc.operation in ROLLBACK_REQUIRED_OPS and not sc.has_rollback:
            return [f"Operation '{sc.operation}' requires rollback snapshot"]
        return []


class PastEvidenceRule(SafetyRule):
    """Check past similar operations for negative outcomes."""

    name = "past_evidence"

    def check(self, sc: SafetyCheck) -> List[str]:
        if not sc.past_evidence:
            return []

        failures = [e for e in sc.past_evidence if not e.get("success", True)]
        if failures:
            return [f"{len(failures)} similar past operation(s) failed; review before proceeding"]
        return []


# --------------------------------------------------------------------------- #
# Rule Engine
# --------------------------------------------------------------------------- #
class SafetyRuleEngine:
    """Evaluates all safety rules and produces a SafetyResult."""

    def __init__(self, rules: List[SafetyRule] = None):
        self._rules = rules or self._default_rules()
        self._block_rules = {
            RevenueProtectionRule.name,
            RetentionProtectionRule.name,
            FrequencyCapRule.name,
            RollbackRule.name,
        }
        self._warn_rules = {
            RevenueWarningRule.name,
            RetentionWarningRule.name,
            PastEvidenceRule.name,
        }

    @staticmethod
    def _default_rules() -> List[SafetyRule]:
        return [
            RevenueProtectionRule(),
            RevenueWarningRule(),
            RetentionProtectionRule(),
            RetentionWarningRule(),
            FrequencyCapRule(),
            RollbackRule(),
            PastEvidenceRule(),
        ]

    def evaluate(self, sc: SafetyCheck) -> SafetyResult:
        """Run all rules and produce a consolidated result."""
        all_violations: List[str] = []
        all_warnings: List[str] = []
        blocked: List[str] = []
        required_confirmations: List[str] = []

        for rule in self._rules:
            issues = rule.check(sc)
            if not issues:
                continue

            if rule.name in self._block_rules:
                blocked.extend(issues)
                all_violations.extend(issues)
            elif rule.name in self._warn_rules:
                all_warnings.extend(issues)
            else:
                all_warnings.extend(issues)

        # Determine status
        if blocked:
            status = "blocked"
            reason = "; ".join(blocked)
            required_confirmations = blocked
        elif all_warnings:
            status = "require_confirmation"
            reason = "; ".join(all_warnings)
            required_confirmations = all_warnings
        else:
            status = "allowed"
            reason = "All safety checks passed"

        return SafetyResult(
            status=status,
            reason=reason,
            violated_rules=[r for r in self._block_rules if any(r in v for v in blocked)],
            warnings=all_warnings,
            required_confirmations=required_confirmations if status != "allowed" else [],
            rollback_required=sc.operation in ROLLBACK_REQUIRED_OPS and not sc.has_rollback,
            metadata={
                "rules_checked": len(self._rules),
                "rules_blocked": len(blocked),
                "rules_warned": len(all_warnings),
            },
        )
