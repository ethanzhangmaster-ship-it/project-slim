"""
E15.1.6 — Review Rule Engine

Deterministic rejection-code → fix-plan mapping. No LLM.

Covers:
  * Google Play: Policy violations, metadata issues, privacy, crashes
  * App Store: Guideline 2.1 (crash), 4.3 (spam/duplicate), 5.1 (privacy)
"""
from typing import Optional

from operation.publishing.review.models import ReviewFixPlan, ReviewRejectEvent

# --------------------------------------------------------------------------- #
# Rule tables
# --------------------------------------------------------------------------- #
_APPLE_RULES = {
    "Guideline 2.1": ReviewFixPlan(
        issue="App crashes or has critical bugs",
        cause="Build contains crashes or unhandled exceptions",
        fix_actions=[
            "Run crash diagnostics on the build",
            "Fix crash and rebuild",
            "Test on target devices before re-submission",
        ], priority="high",
    ),
    "Guideline 4.3": ReviewFixPlan(
        issue="App appears to be spam / duplicate of existing apps",
        cause="Similar metadata or assets to other apps; insufficient differentiation",
        fix_actions=[
            "Rewrite app title and description for better differentiation",
            "Replace duplicate screenshots and feature graphic",
            "Add unique game features to metadata",
        ], priority="high",
    ),
    "Guideline 5.1": ReviewFixPlan(
        issue="Privacy / legal compliance",
        cause="Missing or incomplete privacy policy, or data collection without consent",
        fix_actions=[
            "Add or update privacy_policy_url in metadata",
            "Ensure data collection disclosures are accurate",
            "Add App Tracking Transparency prompt if required",
        ], priority="high",
    ),
}

_GOOGLE_RULES = {
    "Policy:Privacy": ReviewFixPlan(
        issue="Privacy policy missing or insufficient",
        cause="No valid privacy policy URL in store listing",
        fix_actions=[
            "Add privacy_policy_url to store metadata",
            "Ensure data safety section is completed",
        ], priority="high",
    ),
    "Policy:Metadata": ReviewFixPlan(
        issue="Store listing metadata violates Google Play policy",
        cause="Title, description, or screenshots contain policy-violating content",
        fix_actions=[
            "Review and revise store listing text",
            "Replace screenshots that contain prohibited content",
            "Re-submit with corrected metadata",
        ], priority="high",
    ),
    "Crash:Stability": ReviewFixPlan(
        issue="Build rejected due to crashes or instability",
        cause="Application crashes during review testing",
        fix_actions=[
            "Reproduce crash on target device/emulator",
            "Fix crash and rebuild",
            "Increase test coverage before re-submission",
        ], priority="high",
    ),
    "Policy:Impersonation": ReviewFixPlan(
        issue="App impersonates another brand or app",
        cause="App name, icon, or description too similar to existing brand",
        fix_actions=[
            "Rename app and update icon if too similar to existing apps",
            "Ensure all branding is original",
        ], priority="high",
    ),
}

_FALLBACK = ReviewFixPlan(
    issue="Unknown rejection reason",
    cause="Rejection code not in known rule set; manual review required",
    fix_actions=[
        "Read the full rejection message from the store console",
        "Identify the specific policy/guideline violated",
        "Apply the recommended fix and re-submit",
    ], priority="medium",
)


# --------------------------------------------------------------------------- #
class ReviewRuleEngine:
    """Maps rejection codes to actionable fix plans."""

    def analyze(self, event: ReviewRejectEvent) -> ReviewFixPlan:
        key = event.rejection_code.strip()
        if event.store == "app_store":
            plan = _APPLE_RULES.get(key)
        elif event.store == "google_play":
            plan = _GOOGLE_RULES.get(key)
        else:
            plan = None
        if plan is None:
            plan = _FALLBACK
        return plan


__all__ = ["ReviewRuleEngine"]
