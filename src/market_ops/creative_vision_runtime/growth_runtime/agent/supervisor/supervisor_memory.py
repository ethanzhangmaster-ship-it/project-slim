"""E14.2.5 Supervisor Memory — 组织级记忆系统.

从 E13 单 Agent Memory 升级到 E14 组织级记忆:

  E13: Experience Memory + Pattern Memory + Knowledge Graph
  E14: Organization Brain (跨 Agent 记忆)

记录:
  - 各 Agent 的决策历史
  - 哪些策略长期有效
  - 过去冲突的解决结果
  - 组织级经验教训

设计原则:
  - 按 Agent 角色组织
  - 支持跨 Agent 查询
  - 记录决策到结果的完整链路
  - 支持经验回放 (供 Supervisor 决策参考)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import AgentRole


# ═══════════════════════════════════════════════════════════════
# Memory Models
# ═══════════════════════════════════════════════════════════════


class MemoryType(str, Enum):
    """记忆类型."""
    DECISION = "decision"            # 决策记录
    STRATEGY = "strategy"            # 策略记录
    CONFLICT = "conflict"            # 冲突记录
    SUCCESS = "success"              # 成功案例
    FAILURE = "failure"              # 失败案例
    INSIGHT = "insight"              # 洞察
    PATTERN = "pattern"              # 模式
    MILESTONE = "milestone"          # 里程碑


@dataclass
class OrganizationMemory:
    """组织记忆条目 — 跨 Agent 共享的知识.

    Attributes:
        memory_id: 记忆 ID
        memory_type: 记忆类型
        agent_role: 相关 Agent 角色
        description: 描述
        context: 上下文 (当时的状态)
        action: 采取的行动
        outcome: 结果
        success_rating: 成功率 (0-1)
        tags: 标签
        created_at: 创建时间
        referenced_by: 被哪些决策引用过
        metadata: 扩展元数据
    """
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType = MemoryType.DECISION
    agent_role: AgentRole | None = None
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    action: str = ""
    outcome: str = ""
    success_rating: float = 0.5
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    referenced_by: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type.value,
            "agent_role": self.agent_role.value if self.agent_role else None,
            "description": self.description,
            "context": self.context,
            "action": self.action,
            "outcome": self.outcome,
            "success_rating": self.success_rating,
            "tags": self.tags,
            "created_at": self.created_at,
            "referenced_by": self.referenced_by,
            "metadata": self.metadata,
        }


@dataclass
class AgentPerformance:
    """Agent 绩效记录 — 追踪各 Agent 的表现.

    Attributes:
        agent_role: Agent 角色
        total_tasks: 总任务数
        successful_tasks: 成功任务数
        failed_tasks: 失败任务数
        avg_impact: 平均影响
        best_strategy: 最佳策略
        last_updated: 最后更新时间
        metrics: 关键指标
        metadata: 扩展元数据
    """
    agent_role: AgentRole
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    avg_impact: float = 0.0
    best_strategy: str = ""
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_role": self.agent_role.value,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.success_rate,
            "avg_impact": self.avg_impact,
            "best_strategy": self.best_strategy,
            "last_updated": self.last_updated,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Supervisor Memory
# ═══════════════════════════════════════════════════════════════


class SupervisorMemory:
    """组织级记忆 — 跨 Agent 的知识库.

    职责:
      1. 记录各 Agent 的决策和结果
      2. 追踪 Agent 绩效
      3. 发现长期有效的策略
      4. 为 Supervisor 决策提供历史参考
    """

    def __init__(self, max_memories: int = 10000):
        self._memories: list[OrganizationMemory] = []
        self._performance: dict[AgentRole, AgentPerformance] = {}
        self._max_memories = max_memories

    # ── 记忆写入 ──────────────────────────────────────────────

    def record(
        self,
        memory_type: MemoryType,
        description: str,
        agent_role: AgentRole,
        action: str = "",
        outcome: str = "",
        success_rating: float = 0.5,
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> OrganizationMemory:
        """记录组织记忆."""
        mem = OrganizationMemory(
            memory_type=memory_type,
            agent_role=agent_role,
            description=description,
            context=context or {},
            action=action,
            outcome=outcome,
            success_rating=success_rating,
            tags=tags or [],
        )
        self._memories.append(mem)
        self._trim()
        self._update_performance(agent_role, success_rating)
        return mem

    def record_decision(
        self,
        description: str,
        agent_role: AgentRole,
        action: str,
        outcome: str = "",
        success_rating: float = 0.5,
        tags: list[str] | None = None,
    ) -> OrganizationMemory:
        """记录决策."""
        return self.record(
            MemoryType.DECISION, description, agent_role,
            action=action, outcome=outcome, success_rating=success_rating,
            tags=tags,
        )

    def record_success(
        self,
        description: str,
        agent_role: AgentRole,
        action: str,
        outcome: str = "",
        tags: list[str] | None = None,
    ) -> OrganizationMemory:
        """记录成功案例."""
        return self.record(
            MemoryType.SUCCESS, description, agent_role,
            action=action, outcome=outcome, success_rating=0.9,
            tags=tags,
        )

    def record_failure(
        self,
        description: str,
        agent_role: AgentRole,
        action: str,
        outcome: str = "",
        tags: list[str] | None = None,
    ) -> OrganizationMemory:
        """记录失败案例."""
        return self.record(
            MemoryType.FAILURE, description, agent_role,
            action=action, outcome=outcome, success_rating=0.1,
            tags=tags,
        )

    def record_conflict(
        self,
        description: str,
        agent_role: AgentRole,
        outcome: str = "",
        tags: list[str] | None = None,
    ) -> OrganizationMemory:
        """记录冲突解决."""
        return self.record(
            MemoryType.CONFLICT, description, agent_role,
            outcome=outcome, tags=tags,
        )

    def record_strategy(
        self,
        description: str,
        agent_role: AgentRole,
        action: str,
        success_rating: float = 0.5,
        tags: list[str] | None = None,
    ) -> OrganizationMemory:
        """记录策略."""
        return self.record(
            MemoryType.STRATEGY, description, agent_role,
            action=action, success_rating=success_rating,
            tags=tags,
        )

    # ── 绩效追踪 ──────────────────────────────────────────────

    def _update_performance(self, role: AgentRole, success_rating: float) -> None:
        """更新 Agent 绩效."""
        if role not in self._performance:
            self._performance[role] = AgentPerformance(agent_role=role)

        perf = self._performance[role]
        perf.total_tasks += 1
        if success_rating >= 0.5:
            perf.successful_tasks += 1
        else:
            perf.failed_tasks += 1

        # 更新平均影响
        perf.avg_impact = (
            (perf.avg_impact * (perf.total_tasks - 1) + success_rating)
            / perf.total_tasks
        )
        perf.last_updated = datetime.now(timezone.utc).isoformat()

    def get_performance(self, role: AgentRole) -> AgentPerformance:
        """获取 Agent 绩效."""
        if role not in self._performance:
            self._performance[role] = AgentPerformance(agent_role=role)
        return self._performance[role]

    def get_all_performances(self) -> dict[AgentRole, AgentPerformance]:
        return dict(self._performance)

    # ── 记忆检索 ──────────────────────────────────────────────

    def get_recent(self, n: int = 100) -> list[OrganizationMemory]:
        """获取最近记忆."""
        return self._memories[-n:]

    def get_by_role(self, role: AgentRole) -> list[OrganizationMemory]:
        """按角色检索."""
        return [m for m in self._memories if m.agent_role == role]

    def get_by_type(self, memory_type: MemoryType) -> list[OrganizationMemory]:
        """按类型检索."""
        return [m for m in self._memories if m.memory_type == memory_type]

    def get_successful(self, min_rating: float = 0.7) -> list[OrganizationMemory]:
        """获取成功记忆."""
        return [m for m in self._memories if m.success_rating >= min_rating]

    def get_failures(self) -> list[OrganizationMemory]:
        """获取失败记忆."""
        return self.get_by_type(MemoryType.FAILURE)

    def get_by_tag(self, tag: str) -> list[OrganizationMemory]:
        """按标签检索."""
        return [m for m in self._memories if tag in m.tags]

    def get_strategies(self, role: AgentRole | None = None) -> list[OrganizationMemory]:
        """获取策略记录."""
        strategies = self.get_by_type(MemoryType.STRATEGY)
        if role:
            strategies = [s for s in strategies if s.agent_role == role]
        return strategies

    def get_best_strategies(self, role: AgentRole | None = None, top_n: int = 5) -> list[OrganizationMemory]:
        """获取最佳策略 (按成功率排序)."""
        strategies = self.get_strategies(role)
        return sorted(strategies, key=lambda s: s.success_rating, reverse=True)[:top_n]

    # ── 决策支持 ──────────────────────────────────────────────

    def get_decision_context(
        self,
        role: AgentRole,
        context_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """为 Supervisor 决策提供历史上下文.

        Returns:
            {
                "performance": AgentPerformance,
                "recent_decisions": [...],
                "best_strategies": [...],
                "recent_failures": [...],
                "similar_cases": [...],
            }
        """
        perf = self.get_performance(role)
        recent = self.get_by_role(role)[-10:]
        best = self.get_best_strategies(role, top_n=3)
        failures = [m for m in self.get_by_role(role) if m.memory_type == MemoryType.FAILURE][-5:]

        similar = []
        if context_tags:
            for tag in context_tags:
                similar.extend(self.get_by_tag(tag))

        return {
            "role": role.value,
            "performance": perf.to_dict(),
            "recent_decisions": [m.to_dict() for m in recent],
            "best_strategies": [m.to_dict() for m in best],
            "recent_failures": [m.to_dict() for m in failures],
            "similar_cases": [m.to_dict() for m in similar[-5:]],
        }

    def get_organization_health(self) -> dict[str, Any]:
        """获取组织健康度."""
        performances = {
            role.value: perf.to_dict()
            for role, perf in self._performance.items()
        }

        avg_success_rate = (
            sum(p.success_rate for p in self._performance.values())
            / max(len(self._performance), 1)
        )

        return {
            "total_memories": len(self._memories),
            "agent_count": len(self._performance),
            "avg_success_rate": round(avg_success_rate, 3),
            "performances": performances,
            "best_performer": (
                max(self._performance.values(), key=lambda p: p.success_rate).agent_role.value
                if self._performance else None
            ),
        }

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total = len(self._memories)
        type_counts = {}
        role_counts = {}
        for m in self._memories:
            type_counts[m.memory_type.value] = type_counts.get(m.memory_type.value, 0) + 1
            if m.agent_role:
                role_counts[m.agent_role.value] = role_counts.get(m.agent_role.value, 0) + 1

        return {
            "total_memories": total,
            "type_counts": type_counts,
            "role_counts": role_counts,
            "avg_success_rating": (
                sum(m.success_rating for m in self._memories) / total
                if total > 0 else 0
            ),
            "performance": {
                role.value: perf.to_dict()
                for role, perf in self._performance.items()
            },
        }

    def reset(self) -> None:
        self._memories.clear()
        self._performance.clear()

    def _trim(self) -> None:
        """裁剪超出上限的记忆."""
        if len(self._memories) > self._max_memories:
            self._memories = self._memories[-self._max_memories:]


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_supervisor_memory(max_memories: int = 10000) -> SupervisorMemory:
    return SupervisorMemory(max_memories=max_memories)