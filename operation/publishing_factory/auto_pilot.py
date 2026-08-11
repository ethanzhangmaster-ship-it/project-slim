"""
P3-auto — Auto-pilot mode for Google Play publishing
=====================================================

A single env-var toggle that turns the batch publishing pipeline from
"recommend → wait for human approval" into "recommend → auto-approve →
auto-execute" — a true closed loop.

    LAUNCHFORGE_AUTO_PUBLISH=1   →  auto-pilot ON
    LAUNCHFORGE_AUTO_PUBLISH=0   →  auto-pilot OFF (default, safe)

Auto-pilot ON changes:
  * BatchOrchestrator.run_daily() auto-approves plans that pass all
    compliance / risk checks (requires_approval=False, approval_status
    ="approved").
  * After plan generation, approved plans are auto-executed via the
    existing E15.1 PublishingAgent with a production-unlocked
    GooglePlayProductionProvider.
  * real_api_called becomes True ONLY when the provider has valid
    Google Play credentials AND the sandbox is PRODUCTION.

Auto-pilot OFF (default): identical to previous behavior — plans
remain recommendations requiring human approval.

Safety: the auto-pilot flag is OFF by default. The user must explicitly
set the env var to enable it. No code change bypasses the three-gate
policy by default.
"""
from __future__ import annotations

import os
from typing import Optional

ENV_VAR = "LAUNCHFORGE_AUTO_PUBLISH"


def auto_pilot_enabled() -> bool:
    """True when the operator explicitly opts in to autonomous publishing."""
    return os.environ.get(ENV_VAR) == "1"


def status() -> dict:
    return {"auto_pilot": auto_pilot_enabled(), "env_var": ENV_VAR,
            "note": "set LAUNCHFORGE_AUTO_PUBLISH=1 to enable autonomous "
                    "Google Play publishing (auto-approve + auto-execute)"}


__all__ = ["auto_pilot_enabled", "status", "ENV_VAR"]
