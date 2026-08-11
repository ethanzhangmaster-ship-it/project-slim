"""P2.3.2 Role Permission System.

Roles answer: "WHO is allowed to approve WHAT action?"

Hierarchy (ascending authority):
    SYSTEM < OPERATOR < MANAGER < ADMIN

- SYSTEM: policy auto-approval only (low-risk, high-confidence allowlist).
- OPERATOR: day-to-day safe ops (disable a bad ad network, open an
  investigation, pause a bleeding campaign). CANNOT approve money-scaling
  or store releases.
- MANAGER: budget scaling, waterfall changes — anything that moves money.
- ADMIN: releases and above-threshold budget moves.
"""

from __future__ import annotations

from typing import Dict, Tuple

from src.execution.models import ExecutionAction


class ApprovalRole:
    SYSTEM = "SYSTEM"
    OPERATOR = "OPERATOR"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


ROLE_ORDER: Tuple[str, ...] = (
    ApprovalRole.SYSTEM,
    ApprovalRole.OPERATOR,
    ApprovalRole.MANAGER,
    ApprovalRole.ADMIN,
)

# Explicit allowlists per role. A role also inherits everything allowed to
# LOWER roles (see role_can), so entries list the NEW capabilities only.
ROLE_ALLOWED: Dict[str, Tuple[str, ...]] = {
    ApprovalRole.SYSTEM: (
        # SYSTEM may only auto-approve what policy explicitly whitelists;
        # the policy layer further constrains by risk/confidence.
        ExecutionAction.DISABLE_NETWORK,
        ExecutionAction.CREATE_INVESTIGATION,
    ),
    ApprovalRole.OPERATOR: (
        ExecutionAction.DISABLE_NETWORK,
        ExecutionAction.CREATE_INVESTIGATION,
        ExecutionAction.PAUSE_CAMPAIGN,
    ),
    ApprovalRole.MANAGER: (
        ExecutionAction.DISABLE_NETWORK,
        ExecutionAction.CREATE_INVESTIGATION,
        ExecutionAction.PAUSE_CAMPAIGN,
        ExecutionAction.SCALE_BUDGET,
        ExecutionAction.UPDATE_WATERFALL,
        ExecutionAction.CREATE_ASO_UPDATE,
    ),
    ApprovalRole.ADMIN: (
        ExecutionAction.DISABLE_NETWORK,
        ExecutionAction.CREATE_INVESTIGATION,
        ExecutionAction.PAUSE_CAMPAIGN,
        ExecutionAction.SCALE_BUDGET,
        ExecutionAction.UPDATE_WATERFALL,
        ExecutionAction.CREATE_ASO_UPDATE,
        ExecutionAction.CREATE_RELEASE,
    ),
}


def role_level(role: str) -> int:
    """Numeric authority level; -1 for unknown roles."""
    try:
        return ROLE_ORDER.index(role)
    except ValueError:
        return -1


def role_can(role: str, action: str) -> bool:
    """True if `role` is allowed to approve `action`.

    Unknown roles can approve nothing. Unknown actions are denied.
    """
    allowed = ROLE_ALLOWED.get(role)
    if allowed is None:
        return False
    return action in allowed


def minimum_role_for(action: str) -> str:
    """Lowest role in the hierarchy that can approve `action` ('' if none)."""
    for role in ROLE_ORDER:
        if role_can(role, action):
            return role
    return ""
