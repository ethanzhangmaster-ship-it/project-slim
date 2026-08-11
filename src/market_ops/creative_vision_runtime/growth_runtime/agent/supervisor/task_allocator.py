"""E14.2.3 Task Allocator — 基于能力的 Agent 任务分配.

根据 Agent 能力、当前负载和任务需求，将任务分配到最合适的 Agent:

  1. 查询 Agent Registry 获取可用 Agent
  2. 根据任务需求匹配 Agent 能力
  3. 考虑 Agent 当前负载
  4. 分配任务并通过 MessageBus 发送

设计原则:
  - 能力匹配优先 (capability-based routing)
  - 负载均衡 (避免单 Agent 过载)
  - 支持亲和性 (affinity: 优先分配给处理过类似任务的 Agent)
  - 可回退 (fallback to other agents)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import AgentIdentity, AgentRole, AgentMessage, MessagePriority, StandardMessageType
from ..communication.agent_registry import AgentRegistry, AgentStatus
from ..communication.message_bus import MessageBus
from .goal_manager import SubGoal
from .priority_engine import PrioritySignal


# ═══════════════════════════════════════════════════════════════
# Allocation Models
# ═══════════════════════════════════════════════════════════════


class AllocationStatus(str, Enum):
    """分配状态."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentLoad:
    """Agent 负载信息.

    Attributes:
        agent_id: Agent ID
        role: Agent 角色
        active_tasks: 当前活跃任务数
        max_tasks: 最大任务数
        last_assigned_at: 最后分配时间
        load_ratio: 负载率 (0-1)
    """
    agent_id: str = ""
    role: AgentRole | None = None
    active_tasks: int = 0
    max_tasks: int = 10
    last_assigned_at: str = ""
    load_ratio: float = 0.0

    def __post_init__(self):
        if self.max_tasks > 0:
            self.load_ratio = self.active_tasks / self.max_tasks

    @property
    def is_overloaded(self) -> bool:
        return self.active_tasks >= self.max_tasks

    @property
    def available_slots(self) -> int:
        return max(self.max_tasks - self.active_tasks, 0)


@dataclass
class AllocationRecord:
    """任务分配记录.

    Attributes:
        allocation_id: 分配 ID
        task_id: 任务 ID (关联 GrowthTask 或 SubGoal)
        assigned_to: 分配的 Agent ID
        assigned_role: 分配的 Agent 角色
        capability_match: 能力匹配度 (0-1)
        assigned_by: 分配者 (Supervisor)
        assigned_at: 分配时间
        status: 分配状态
        reason: 分配理由
        metadata: 扩展元数据
    """
    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    assigned_to: str = ""
    assigned_role: AgentRole | None = None
    capability_match: float = 0.0
    assigned_by: str = ""
    assigned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: AllocationStatus = AllocationStatus.PENDING
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "task_id": self.task_id,
            "assigned_to": self.assigned_to,
            "assigned_role": self.assigned_role.value if self.assigned_role else None,
            "capability_match": self.capability_match,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at,
            "status": self.status.value,
            "reason": self.reason,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Capability Mapping
# ═══════════════════════════════════════════════════════════════


# 子目标类型 → 所需能力
GOAL_CAPABILITY_MAP: dict[str, list[str]] = {
    "roas": ["meta_ads_analysis", "campaign_management", "roas_monitoring"],
    "cpi": ["meta_ads_analysis", "budget_allocation", "audience_targeting"],
    "creative_revenue": ["creative_dna_analysis", "fatigue_detection", "variant_generation"],
    "ctr": ["creative_dna_analysis", "creative_evolution", "clip_analysis"],
    "payer_rate": ["payer_conversion", "iap_optimization", "price_optimization"],
    "arpu": ["ltv_analysis", "revenue_attribution", "price_optimization"],
    "ltv": ["ltv_analysis", "revenue_attribution"],
    "d7_retention": ["retention_analysis", "level_design", "event_optimization"],
    "installs": ["meta_ads_analysis", "campaign_management", "budget_allocation"],
    "creative_volume": ["creative_dna_analysis", "variant_generation", "winner_identification"],
}

# 信号类别 → 目标 Agent 角色
SIGNAL_TARGET_ROLE_MAP: dict[str, AgentRole] = {
    "roas": AgentRole.UA,
    "cpi": AgentRole.UA,
    "creative": AgentRole.CREATIVE,
    "revenue": AgentRole.MONETIZATION,
    "payer": AgentRole.MONETIZATION,
    "retention": AgentRole.PRODUCT,
    "budget": AgentRole.UA,
    "risk": AgentRole.SUPERVISOR,
    "opportunity": AgentRole.SUPERVISOR,
    "system": AgentRole.SUPERVISOR,
}


# ═══════════════════════════════════════════════════════════════
# Task Allocator
# ═══════════════════════════════════════════════════════════════


class TaskAllocator:
    """任务分配器 — 根据能力将任务分配给最合适的 Agent.

    职责:
      1. 查询 Agent Registry 获取候选人
      2. 计算能力匹配度
      3. 考虑负载均衡
      4. 通过 MessageBus 发送任务
    """

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        bus: MessageBus | None = None,
    ):
        self._registry = registry or AgentRegistry()
        self._bus = bus or MessageBus()
        self._allocations: dict[str, AllocationRecord] = {}
        self._loads: dict[str, AgentLoad] = {}
        self._affinity: dict[str, list[str]] = {}  # task_type → agent_ids

    # ── 能力匹配 ──────────────────────────────────────────────

    def compute_capability_match(
        self,
        required_capabilities: list[str],
        agent_capabilities: tuple[str, ...],
    ) -> float:
        """计算能力匹配度.

        Returns:
            match_score: 0-1, 越高越匹配
        """
        if not required_capabilities:
            return 1.0
        if not agent_capabilities:
            return 0.0

        cap_set = set(agent_capabilities)
        matches = sum(1 for c in required_capabilities if c in cap_set)
        return matches / len(required_capabilities)

    def find_candidates(
        self,
        required_capabilities: list[str],
        target_role: AgentRole | None = None,
    ) -> list[tuple[AgentIdentity, float]]:
        """查找候选 Agent (能力匹配 + 在线 + 未过载).

        Returns:
            [(identity, match_score), ...] 按匹配度降序
        """
        candidates = []

        if target_role:
            records = self._registry.find_by_role(target_role)
        else:
            records = self._registry.find_online()

        for record in records:
            if not record.is_alive():
                continue
            if record.status == AgentStatus.OFFLINE:
                continue

            match = self.compute_capability_match(
                required_capabilities, record.identity.capabilities
            )
            if match > 0:
                candidates.append((record.identity, match))

        # 按匹配度降序
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    # ── 任务分配 ──────────────────────────────────────────────

    def allocate_sub_goal(
        self,
        sub_goal: SubGoal,
        assigned_by: str = "supervisor",
    ) -> AllocationRecord | None:
        """为子目标分配 Agent.

        Args:
            sub_goal: 子目标
            assigned_by: 分配者 ID

        Returns:
            AllocationRecord or None (无可分配 Agent)
        """
        if not sub_goal.agent_role:
            return None

        required_caps = GOAL_CAPABILITY_MAP.get(sub_goal.metric, [])
        candidates = self.find_candidates(required_caps, sub_goal.agent_role)

        if not candidates:
            return None

        # 选择最佳候选 (能力匹配 + 负载均衡)
        best_identity, best_match = self._select_best_candidate(candidates)
        if not best_identity:
            return None

        record = AllocationRecord(
            task_id=sub_goal.sub_goal_id,
            assigned_to=best_identity.agent_id,
            assigned_role=best_identity.role,
            capability_match=best_match,
            assigned_by=assigned_by,
            status=AllocationStatus.ASSIGNED,
            reason=f"capability_match={best_match:.2f}",
        )
        self._allocations[record.allocation_id] = record

        # 更新负载
        self._increment_load(best_identity.agent_id, best_identity.role)

        # 发送任务消息
        self._send_task_message(best_identity, sub_goal)

        return record

    def allocate_signal(
        self,
        signal: PrioritySignal,
        assigned_by: str = "supervisor",
    ) -> AllocationRecord | None:
        """为优先级信号分配 Agent.

        Args:
            signal: 优先级信号
            assigned_by: 分配者

        Returns:
            AllocationRecord or None
        """
        target_role = signal.target_agent or SIGNAL_TARGET_ROLE_MAP.get(
            signal.category.value
        )
        if not target_role:
            return None

        required_caps = GOAL_CAPABILITY_MAP.get(signal.category.value, [])
        candidates = self.find_candidates(required_caps, target_role)

        if not candidates:
            return None

        best_identity, best_match = self._select_best_candidate(candidates)
        if not best_identity:
            return None

        record = AllocationRecord(
            task_id=signal.signal_id,
            assigned_to=best_identity.agent_id,
            assigned_role=best_identity.role,
            capability_match=best_match,
            assigned_by=assigned_by,
            status=AllocationStatus.ASSIGNED,
            reason=f"signal_{signal.category.value}_match={best_match:.2f}",
        )
        self._allocations[record.allocation_id] = record

        self._increment_load(best_identity.agent_id, best_identity.role)
        self._send_signal_message(best_identity, signal)

        return record

    def allocate_batch(
        self,
        sub_goals: list[SubGoal],
        assigned_by: str = "supervisor",
    ) -> list[AllocationRecord]:
        """批量分配子目标."""
        results = []
        for sg in sub_goals:
            record = self.allocate_sub_goal(sg, assigned_by)
            if record:
                results.append(record)
        return results

    # ── 内部选择逻辑 ──────────────────────────────────────────

    def _select_best_candidate(
        self,
        candidates: list[tuple[AgentIdentity, float]],
    ) -> tuple[AgentIdentity | None, float]:
        """选择最佳候选 (匹配度 + 负载 + 亲和性)."""
        best = None
        best_score = -1.0

        for identity, match in candidates:
            load = self._loads.get(identity.agent_id)
            if load and load.is_overloaded:
                continue

            # 综合评分: 70% 匹配度 + 30% 可用槽位
            load_factor = (
                load.available_slots / load.max_tasks if load else 1.0
            )
            composite = match * 0.7 + load_factor * 0.3

            if composite > best_score:
                best_score = composite
                best = identity

        return best, best_score if best else 0.0

    def _increment_load(self, agent_id: str, role: AgentRole | None) -> None:
        """增加 Agent 负载."""
        if agent_id not in self._loads:
            self._loads[agent_id] = AgentLoad(
                agent_id=agent_id,
                role=role,
                max_tasks=10,
            )
        load = self._loads[agent_id]
        load.active_tasks += 1
        load.load_ratio = load.active_tasks / load.max_tasks
        load.last_assigned_at = datetime.now(timezone.utc).isoformat()

    def _decrement_load(self, agent_id: str) -> None:
        """减少 Agent 负载."""
        if agent_id in self._loads:
            load = self._loads[agent_id]
            load.active_tasks = max(load.active_tasks - 1, 0)
            load.load_ratio = load.active_tasks / load.max_tasks

    def _send_task_message(self, identity: AgentIdentity, sub_goal: SubGoal) -> None:
        """发送任务消息."""
        msg = AgentMessage(
            sender=None,  # Supervisor 填充
            receiver=identity,
            message_type=AgentMessage.create_task.__name__,  # placeholder
            priority=MessagePriority.HIGH,
            subject=f"Task: {sub_goal.metric}",
            body={
                "sub_goal_id": sub_goal.sub_goal_id,
                "goal_type": sub_goal.goal_type.value,
                "target_value": sub_goal.target_value,
                "metric": sub_goal.metric,
                "hypothesis": sub_goal.hypothesis,
                "action_plan": sub_goal.action_plan,
            },
        )
        # 使用 TASK 类型
        from ..communication.agent_message import MessageType
        msg.message_type = MessageType.TASK
        self._bus.send(msg)

    def _send_signal_message(self, identity: AgentIdentity, signal: PrioritySignal) -> None:
        """发送信号消息."""
        from ..communication.agent_message import MessageType
        msg = AgentMessage(
            receiver=identity,
            message_type=MessageType.ALERT,
            priority=MessagePriority.HIGH,
            subject=f"Alert: {signal.category.value}",
            body={
                "signal_id": signal.signal_id,
                "category": signal.category.value,
                "severity": signal.severity.value,
                "description": signal.description,
                "metrics": signal.metrics,
            },
        )
        self._bus.send(msg)

    # ── 负载管理 ──────────────────────────────────────────────

    def get_load(self, agent_id: str) -> AgentLoad | None:
        return self._loads.get(agent_id)

    def get_all_loads(self) -> dict[str, AgentLoad]:
        return dict(self._loads)

    def get_least_loaded(self, role: AgentRole | None = None) -> AgentLoad | None:
        """获取负载最低的 Agent."""
        candidates = [
            load for load in self._loads.values()
            if (role is None or load.role == role) and not load.is_overloaded
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda l: l.load_ratio)

    def complete_task(self, allocation_id: str) -> bool:
        """标记任务完成."""
        record = self._allocations.get(allocation_id)
        if not record:
            return False
        record.status = AllocationStatus.COMPLETED
        self._decrement_load(record.assigned_to)
        return True

    def fail_task(self, allocation_id: str, reason: str = "") -> bool:
        """标记任务失败."""
        record = self._allocations.get(allocation_id)
        if not record:
            return False
        record.status = AllocationStatus.FAILED
        if reason:
            record.metadata["failure_reason"] = reason
        self._decrement_load(record.assigned_to)
        return True

    # ── 查询 ──────────────────────────────────────────────────

    def get_allocation(self, allocation_id: str) -> AllocationRecord | None:
        return self._allocations.get(allocation_id)

    def get_allocations_by_agent(self, agent_id: str) -> list[AllocationRecord]:
        return [a for a in self._allocations.values() if a.assigned_to == agent_id]

    def get_pending_allocations(self) -> list[AllocationRecord]:
        return [a for a in self._allocations.values() if a.status == AllocationStatus.PENDING]

    def get_active_allocations(self) -> list[AllocationRecord]:
        return [a for a in self._allocations.values() if a.status == AllocationStatus.ASSIGNED]

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total = len(self._allocations)
        status_counts = {}
        for a in self._allocations.values():
            status_counts[a.status.value] = status_counts.get(a.status.value, 0) + 1

        return {
            "total_allocations": total,
            "active_allocations": status_counts.get("assigned", 0),
            "completed_allocations": status_counts.get("completed", 0),
            "failed_allocations": status_counts.get("failed", 0),
            "status_counts": status_counts,
            "agent_loads": {
                agent_id: {
                    "active_tasks": load.active_tasks,
                    "load_ratio": load.load_ratio,
                    "is_overloaded": load.is_overloaded,
                }
                for agent_id, load in self._loads.items()
            },
        }

    def reset(self) -> None:
        self._allocations.clear()
        self._loads.clear()
        self._affinity.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_task_allocator(
    registry: AgentRegistry | None = None,
    bus: MessageBus | None = None,
) -> TaskAllocator:
    return TaskAllocator(registry=registry, bus=bus)