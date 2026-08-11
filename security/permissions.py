"""
EP0.1.4 — Permission Audit: Agent-level resource access control.

Model: each Agent declares which resources it reads / writes.
Before execution, permissions are checked against a policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Resource(str, Enum):
    ADJUST = "adjust"
    META_ADS = "meta_ads"
    GOOGLE_PLAY = "google_play"
    APP_STORE = "app_store"
    MAX = "max"
    ADMOB = "admob"
    LEVEL_PLAY = "level_play"
    FIREBASE = "firebase"
    REVENUE_DATA = "revenue_data"
    ASO_STORE = "aso_store"
    CREDENTIALS = "credentials"
    MEMORY = "memory"
    DECISION_LOG = "decision_log"
    EXPERIMENT = "experiment"


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"


@dataclass
class AgentPermission:
    agent: str
    resource: Resource
    actions: List[Action]
    reason: str = ""


@dataclass
class AgentPermissionSet:
    agent: str
    permissions: List[AgentPermission] = field(default_factory=list)

    def allows(self, resource: Resource, action: Action) -> bool:
        for perm in self.permissions:
            if perm.resource == resource and action in perm.actions:
                return True
        return False


class PermissionAudit:
    """Audit trail for agent permission checks."""

    def __init__(self):
        self._records: List[Dict] = []

    def check(
        self,
        agent: str,
        resource: Resource,
        action: Action,
        allowed: bool,
    ) -> None:
        self._records.append({
            "agent": agent,
            "resource": resource.value,
            "action": action.value,
            "allowed": allowed,
        })

    def violations(self) -> List[Dict]:
        return [r for r in self._records if not r["allowed"]]

    def report(self) -> str:
        lines = ["# Permission Audit", ""]
        violations = self.violations()
        if violations:
            lines.append(f"❌ {len(violations)} violation(s):\n")
            for v in violations:
                lines.append(
                    f"  - `{v['agent']}` tried `{v['action']}` on `{v['resource']}`"
                )
        else:
            lines.append("✅ All permission checks passed.\n")
        lines.append(f"  Total checks: {len(self._records)}")
        return "\n".join(lines)


# -- Predefined Agent Permission Sets --

ASO_AGENT_PERMISSIONS = AgentPermissionSet(
    agent="aso_agent",
    permissions=[
        AgentPermission("aso_agent", Resource.ASO_STORE, [Action.READ], "read store listings"),
        AgentPermission("aso_agent", Resource.REVENUE_DATA, [Action.READ], "read organic revenue"),
        AgentPermission("aso_agent", Resource.MEMORY, [Action.READ, Action.WRITE], "learn patterns"),
        AgentPermission("aso_agent", Resource.EXPERIMENT, [Action.WRITE], "create experiments"),
    ],
)

REVENUE_AGENT_PERMISSIONS = AgentPermissionSet(
    agent="revenue_agent",
    permissions=[
        AgentPermission("revenue_agent", Resource.ADJUST, [Action.READ], "read attribution"),
        AgentPermission("revenue_agent", Resource.REVENUE_DATA, [Action.READ], "analyze revenue"),
        AgentPermission("revenue_agent", Resource.MEMORY, [Action.READ, Action.WRITE], "store insights"),
        AgentPermission("revenue_agent", Resource.REVENUE_DATA, [Action.WRITE], "publish reports"),
    ],
)

RELEASE_AGENT_PERMISSIONS = AgentPermissionSet(
    agent="release_agent",
    permissions=[
        AgentPermission("release_agent", Resource.GOOGLE_PLAY, [Action.READ, Action.WRITE], "manage releases"),
        AgentPermission("release_agent", Resource.APP_STORE, [Action.READ, Action.WRITE], "manage releases"),
        AgentPermission("release_agent", Resource.DECISION_LOG, [Action.WRITE], "log decisions"),
    ],
)

MAX_AGENT_PERMISSIONS = AgentPermissionSet(
    agent="max_agent",
    permissions=[
        AgentPermission("max_agent", Resource.MAX, [Action.READ], "read reports"),
        AgentPermission("max_agent", Resource.MAX, [Action.WRITE], "update waterfalls (dry-run only)"),
        AgentPermission("max_agent", Resource.MEMORY, [Action.READ, Action.WRITE], "learn patterns"),
    ],
)

ALL_PERMISSION_SETS: Dict[str, AgentPermissionSet] = {
    "aso_agent": ASO_AGENT_PERMISSIONS,
    "revenue_agent": REVENUE_AGENT_PERMISSIONS,
    "release_agent": RELEASE_AGENT_PERMISSIONS,
    "max_agent": MAX_AGENT_PERMISSIONS,
}
