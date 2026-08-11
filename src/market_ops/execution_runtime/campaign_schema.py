"""E10.2 Phase 3 — Campaign Lifecycle Schema.

Defines the core campaign domain objects that bridge ExecutionTask
with real platform campaign identities. Enables the Decision →
Execute → Measure → Learn closed loop.

Core entities:
  - CampaignIdentity: maps task_id → real campaign_id
  - CampaignState: ACTIVE / PAUSED / DELETED lifecycle
  - CampaignMutation: records budget/status changes
  - CampaignSnapshot: post-mutation campaign state
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CampaignStatus(str, Enum):
    """Campaign lifecycle state machine.

    UNKNOWN → ACTIVE → PAUSED → DELETED
    """
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"


# ═══════════════════════════════════════════════════════════
# CampaignIdentity
# ═══════════════════════════════════════════════════════════

@dataclass
class CampaignIdentity:
    """Maps an ExecutionTask to a real platform campaign.

    Links task_id to the external platform campaign ID so
    lifecycle tracking can be correlated across the system.
    """
    identity_id: str = ""
    task_id: str = ""
    campaign_id: str = ""
    ad_account_id: str = ""
    platform: str = "mock"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.identity_id:
            self.identity_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "task_id": self.task_id,
            "campaign_id": self.campaign_id,
            "ad_account_id": self.ad_account_id,
            "platform": self.platform,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# CampaignMutation
# ═══════════════════════════════════════════════════════════

@dataclass
class CampaignMutation:
    """Records a single campaign change (budget or status).

    Captures the delta between before/after state for audit
    trail and rollback capability.
    """
    mutation_id: str = ""
    campaign_id: str = ""
    task_id: str = ""
    action: str = ""                    # SCALE / KILL / WATCH / RETEST
    platform: str = "mock"

    # Budget change
    budget_before: float = 0.0
    budget_after: float = 0.0
    budget_delta: float = 0.0

    # Status change
    status_before: str = CampaignStatus.UNKNOWN.value
    status_after: str = CampaignStatus.UNKNOWN.value

    # Metadata
    success: bool = True
    error_message: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.mutation_id:
            self.mutation_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.budget_delta == 0.0:
            self.budget_delta = round(self.budget_after - self.budget_before, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "campaign_id": self.campaign_id,
            "task_id": self.task_id,
            "action": self.action,
            "platform": self.platform,
            "budget_before": round(self.budget_before, 2),
            "budget_after": round(self.budget_after, 2),
            "budget_delta": round(self.budget_delta, 2),
            "status_before": self.status_before,
            "status_after": self.status_after,
            "success": self.success,
            "error_message": self.error_message,
            "raw_response": self.raw_response,
            "created_at": self.created_at,
        }

    @property
    def is_scale(self) -> bool:
        return self.action == "SCALE"

    @property
    def is_kill(self) -> bool:
        return self.action == "KILL"

    @property
    def is_retest(self) -> bool:
        return self.action == "RETEST"


# ═══════════════════════════════════════════════════════════
# CampaignSnapshot
# ═══════════════════════════════════════════════════════════

@dataclass
class CampaignSnapshot:
    """Post-mutation snapshot of a campaign's state.

    Captured after a mutation is applied, used by ResultCollector
    and FeedbackLoop for performance tracking.
    """
    snapshot_id: str = ""
    campaign_id: str = ""
    task_id: str = ""
    platform: str = "mock"

    status: str = CampaignStatus.UNKNOWN.value
    daily_budget: float = 0.0
    lifetime_budget: float = 0.0

    # Metrics (from platform)
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    ctr: float = 0.0

    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            self.snapshot_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "campaign_id": self.campaign_id,
            "task_id": self.task_id,
            "platform": self.platform,
            "status": self.status,
            "daily_budget": round(self.daily_budget, 2),
            "lifetime_budget": round(self.lifetime_budget, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "spend": round(self.spend, 2),
            "cpm": round(self.cpm, 2),
            "cpc": round(self.cpc, 2),
            "ctr": round(self.ctr, 4),
            "created_at": self.created_at,
        }