"""E10.2 Phase 3 — Campaign Registry.

Maintains the mapping between ExecutionTask (task_id) and real
platform campaign identities. This is the bridge that solves the
E10.1 limitation of having no real ad object association.

Usage:
    registry = CampaignRegistry()
    registry.register(task_id, campaign_identity)
    identity = registry.get_campaign(task_id)
"""

from __future__ import annotations

from market_ops.execution_runtime.campaign_schema import CampaignIdentity, CampaignMutation, CampaignSnapshot


class CampaignRegistry:
    """Registry for task_id → campaign_id mapping.

    Tracks all campaign identities and mutations throughout
    the execution lifecycle. Thread-safe for single-threaded use.
    """

    def __init__(self) -> None:
        self._identities: dict[str, CampaignIdentity] = {}       # task_id → identity
        self._campaigns: dict[str, CampaignIdentity] = {}        # campaign_id → identity
        self._mutations: list[CampaignMutation] = []
        self._snapshots: list[CampaignSnapshot] = []

    # ── Registration ───────────────────────────────────────

    def register(self, task_id: str, identity: CampaignIdentity) -> None:
        """Register a campaign identity for a task.

        Args:
            task_id: The ExecutionTask.task_id.
            identity: CampaignIdentity with platform campaign ID.
        """
        self._identities[task_id] = identity
        self._campaigns[identity.campaign_id] = identity

    def get_campaign(self, task_id: str) -> CampaignIdentity | None:
        """Get campaign identity by task_id.

        Args:
            task_id: The ExecutionTask.task_id.

        Returns:
            CampaignIdentity or None if not found.
        """
        return self._identities.get(task_id)

    def get_by_campaign_id(self, campaign_id: str) -> CampaignIdentity | None:
        """Get campaign identity by platform campaign_id.

        Args:
            campaign_id: Platform-specific campaign ID.

        Returns:
            CampaignIdentity or None if not found.
        """
        return self._campaigns.get(campaign_id)

    # ── Mutations ──────────────────────────────────────────

    def record_mutation(self, mutation: CampaignMutation) -> None:
        """Record a campaign mutation for audit trail.

        Args:
            mutation: The CampaignMutation to record.
        """
        self._mutations.append(mutation)

    def record_snapshot(self, snapshot: CampaignSnapshot) -> None:
        """Record a campaign snapshot after mutation.

        Args:
            snapshot: The CampaignSnapshot to record.
        """
        self._snapshots.append(snapshot)

    def get_mutations(self, task_id: str) -> list[CampaignMutation]:
        """Get all mutations for a task."""
        return [m for m in self._mutations if m.task_id == task_id]

    def get_snapshots(self, task_id: str) -> list[CampaignSnapshot]:
        """Get all snapshots for a task."""
        return [s for s in self._snapshots if s.task_id == task_id]

    # ── State management ───────────────────────────────────

    def update_state(self, campaign_id: str, status: str) -> None:
        """Update the active state of a tracked campaign.

        Args:
            campaign_id: Platform-specific campaign ID.
            status: New campaign status (ACTIVE/PAUSED/DELETED).
        """
        identity = self._campaigns.get(campaign_id)
        if identity:
            # Create a mutation reflecting the state change
            mutation = CampaignMutation(
                campaign_id=campaign_id,
                task_id=identity.task_id,
                action="STATE_CHANGE",
                platform=identity.platform,
                status_before=CampaignSnapshot.__new__(CampaignSnapshot).status if False else "",
                status_after=status,
            )
            self._mutations.append(mutation)

    def has_task(self, task_id: str) -> bool:
        """Check if a task has a registered campaign."""
        return task_id in self._identities

    def has_campaign(self, campaign_id: str) -> bool:
        """Check if a campaign ID is tracked."""
        return campaign_id in self._campaigns

    # ── Properties ─────────────────────────────────────────

    @property
    def identity_count(self) -> int:
        return len(self._identities)

    @property
    def mutation_count(self) -> int:
        return len(self._mutations)

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def list_campaign_ids(self) -> list[str]:
        """Return all tracked campaign IDs."""
        return list(self._campaigns.keys())

    def list_task_ids(self) -> list[str]:
        """Return all tracked task IDs."""
        return list(self._identities.keys())