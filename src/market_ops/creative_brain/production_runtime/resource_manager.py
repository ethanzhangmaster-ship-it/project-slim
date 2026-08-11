"""V4.4 Resource Manager — unified CPU/GPU/Memory/Disk management.

GPU full → pause Creative Generation, continue Validation.
Manages resource allocation and limits across all workers.
"""

from __future__ import annotations

from typing import Any

from .schemas import ResourceState, ResourceType


class ResourceManager:
    """Unified resource manager for CPU, GPU, Memory, and Disk."""

    def __init__(self,
                 cpu_limit: float = 0.9,
                 gpu_limit: float = 0.95,
                 memory_limit: float = 0.85,
                 disk_limit: float = 0.90) -> None:
        self._limits = {
            ResourceType.CPU: cpu_limit,
            ResourceType.GPU: gpu_limit,
            ResourceType.MEMORY: memory_limit,
            ResourceType.DISK: disk_limit,
        }
        # Simulated resource usage (in production, read from system)
        self._usage = {
            ResourceType.CPU: 0.0,
            ResourceType.GPU: 0.0,
            ResourceType.MEMORY: 0.0,
            ResourceType.DISK: 0.0,
        }
        self._total = {
            ResourceType.CPU: 100.0,
            ResourceType.GPU: 100.0,
            ResourceType.MEMORY: 64.0,  # GB
            ResourceType.DISK: 500.0,   # GB
        }
        self._paused_workflows: set[str] = set()

    def can_allocate(self, resource_type: ResourceType,
                     amount: float) -> bool:
        """Check if more resources can be allocated.

        Args:
            resource_type: Type of resource.
            amount: Amount to allocate.

        Returns:
            True if allocation is within limits.
        """
        current = self._usage[resource_type]
        limit = self._limits[resource_type] * self._total[resource_type]
        return (current + amount) <= limit

    def allocate(self, resource_type: ResourceType,
                 amount: float) -> bool:
        """Allocate resources.

        Returns:
            True if allocation succeeded.
        """
        if not self.can_allocate(resource_type, amount):
            return False
        self._usage[resource_type] += amount
        return True

    def release(self, resource_type: ResourceType, amount: float) -> None:
        """Release allocated resources."""
        self._usage[resource_type] = max(0.0, self._usage[resource_type] - amount)

    def get_state(self, resource_type: ResourceType) -> ResourceState:
        """Get current state of a resource."""
        total = self._total[resource_type]
        used = self._usage[resource_type]
        return ResourceState(
            resource_type=resource_type,
            total=total,
            used=used,
            available=total - used,
            usage_pct=used / total if total > 0 else 0.0,
        )

    def get_all_states(self) -> list[ResourceState]:
        """Get states of all resources."""
        return [self.get_state(rt) for rt in ResourceType]

    def is_overloaded(self, resource_type: ResourceType) -> bool:
        """Check if a resource is over its limit."""
        state = self.get_state(resource_type)
        return state.usage_pct > self._limits[resource_type]

    def get_bottleneck(self) -> ResourceType | None:
        """Find the most constrained resource."""
        max_usage = 0.0
        bottleneck = None
        for rt in ResourceType:
            state = self.get_state(rt)
            if state.usage_pct > max_usage:
                max_usage = state.usage_pct
                bottleneck = rt
        return bottleneck

    def pause_workflow(self, workflow_id: str) -> None:
        """Pause a workflow due to resource constraints."""
        self._paused_workflows.add(workflow_id)

    def resume_workflow(self, workflow_id: str) -> None:
        """Resume a paused workflow."""
        self._paused_workflows.discard(workflow_id)

    def is_paused(self, workflow_id: str) -> bool:
        """Check if a workflow is paused."""
        return workflow_id in self._paused_workflows

    def set_usage(self, resource_type: ResourceType, value: float) -> None:
        """Set current resource usage (for testing/simulation)."""
        self._usage[resource_type] = max(0.0, value)

    def get_limits(self) -> dict[str, float]:
        """Get resource limits."""
        return {rt.value: limit for rt, limit in self._limits.items()}

    def get_usage_summary(self) -> dict[str, Any]:
        """Get usage summary."""
        return {
            rt.value: {
                "used": round(self._usage[rt], 2),
                "total": self._total[rt],
                "pct": round(self._usage[rt] / self._total[rt] * 100, 1),
                "limit": round(self._limits[rt] * 100, 1),
            }
            for rt in ResourceType
        }