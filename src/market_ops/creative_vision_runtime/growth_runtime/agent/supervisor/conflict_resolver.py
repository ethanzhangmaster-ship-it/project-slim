"""E14.2.4 Conflict Resolver — Agent 间冲突处理.

当多个 Agent 提出冲突建议时 (e.g. UA 建议增加预算, Monetization 建议减少),
Supervisor 需要仲裁:

冲突解决策略:
  1. 数据驱动: 基于历史数据选择最优方案
  2. 投票: 多 Agent 投票决定
  3. 仲裁: Supervisor 最终决策
  4. 妥协: 寻找中间方案

设计原则:
  - 冲突必须有明确的解决策略
  - 所有决策可追溯
  - 支持自动解决和人工升级
  - 解决结果记录到组织记忆
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import AgentRole
from ..communication.collaboration import (
    CollaborationEngine,
    VoteOption,
    ConsensusResult,
    Proposal,
)


# ═══════════════════════════════════════════════════════════════
# Conflict Models
# ═══════════════════════════════════════════════════════════════


class ConflictType(str, Enum):
    """冲突类型."""
    BUDGET_ALLOCATION = "budget_allocation"      # 预算分配冲突
    CAMPAIGN_ACTION = "campaign_action"          # 系列操作冲突
    CREATIVE_STRATEGY = "creative_strategy"      # 素材策略冲突
    PRICING = "pricing"                          # 定价冲突
    RISK_TOLERANCE = "risk_tolerance"            # 风险容忍度冲突
    RESOURCE = "resource"                        # 资源冲突
    GOAL = "goal"                                # 目标冲突
    STRATEGY = "strategy"                        # 策略冲突


class ResolutionStrategy(str, Enum):
    """解决策略."""
    VOTE = "vote"                   # 投票
    SUPERVISOR_DECISION = "supervisor_decision"  # 主管决策
    DATA_DRIVEN = "data_driven"    # 数据驱动
    COMPROMISE = "compromise"      # 妥协
    ESCALATE = "escalate"          # 升级
    DEFER = "defer"                # 推迟


@dataclass
class ConflictParty:
    """冲突方.

    Attributes:
        agent_role: Agent 角色
        position: 立场描述
        proposal: 具体提议
        expected_impact: 预期影响
        confidence: 置信度
        evidence: 支持证据
        metadata: 扩展元数据
    """
    agent_role: AgentRole
    position: str = ""
    proposal: dict[str, Any] = field(default_factory=dict)
    expected_impact: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.7
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_role": self.agent_role.value,
            "position": self.position,
            "proposal": self.proposal,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


@dataclass
class Conflict:
    """冲突 — 两个或多个 Agent 之间的分歧.

    Attributes:
        conflict_id: 冲突 ID
        conflict_type: 冲突类型
        description: 冲突描述
        parties: 冲突方列表
        context: 上下文 (预算、系列等)
        priority: 优先级 (0-1)
        created_at: 创建时间
        resolved_at: 解决时间
        resolution_strategy: 解决策略
        resolution_result: 解决结果
        resolution_rationale: 解决理由
        metadata: 扩展元数据
    """
    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conflict_type: ConflictType = ConflictType.STRATEGY
    description: str = ""
    parties: list[ConflictParty] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    resolution_strategy: ResolutionStrategy | None = None
    resolution_result: str = ""
    resolution_rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_resolved(self) -> bool:
        return self.resolution_strategy is not None

    @property
    def party_count(self) -> int:
        return len(self.parties)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "parties": [p.to_dict() for p in self.parties],
            "context": self.context,
            "priority": self.priority,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "is_resolved": self.is_resolved,
            "resolution_strategy": self.resolution_strategy.value if self.resolution_strategy else None,
            "resolution_result": self.resolution_result,
            "resolution_rationale": self.resolution_rationale,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Conflict Resolver
# ═══════════════════════════════════════════════════════════════


class ConflictResolver:
    """冲突解决器 — 处理 Agent 间分歧.

    职责:
      1. 检测并记录冲突
      2. 选择解决策略
      3. 执行解决 (投票/仲裁/数据驱动)
      4. 记录解决结果
    """

    def __init__(self, collab: CollaborationEngine | None = None):
        self._collab = collab or CollaborationEngine()
        self._conflicts: dict[str, Conflict] = {}
        self._resolved: list[Conflict] = []

    # ── 冲突创建 ──────────────────────────────────────────────

    def create_conflict(
        self,
        description: str,
        conflict_type: ConflictType,
        parties: list[ConflictParty],
        context: dict[str, Any] | None = None,
        priority: float = 0.5,
    ) -> Conflict:
        """创建冲突记录."""
        conflict = Conflict(
            conflict_type=conflict_type,
            description=description,
            parties=parties,
            context=context or {},
            priority=priority,
        )
        self._conflicts[conflict.conflict_id] = conflict
        return conflict

    def create_budget_conflict(
        self,
        description: str,
        ua_proposal: dict[str, Any],
        monetization_proposal: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Conflict:
        """创建预算冲突 (UA vs Monetization)."""
        return self.create_conflict(
            description=description,
            conflict_type=ConflictType.BUDGET_ALLOCATION,
            parties=[
                ConflictParty(
                    agent_role=AgentRole.UA,
                    position="增加预算",
                    proposal=ua_proposal,
                    expected_impact=ua_proposal.get("expected_impact", {}),
                    confidence=ua_proposal.get("confidence", 0.7),
                ),
                ConflictParty(
                    agent_role=AgentRole.MONETIZATION,
                    position="控制预算",
                    proposal=monetization_proposal,
                    expected_impact=monetization_proposal.get("expected_impact", {}),
                    confidence=monetization_proposal.get("confidence", 0.7),
                ),
            ],
            context=context or {},
            priority=0.8,
        )

    # ── 解决策略 ──────────────────────────────────────────────

    def resolve_by_vote(
        self,
        conflict: Conflict,
        voters: list[str],
        required_approval_ratio: float = 0.5,
    ) -> Conflict:
        """通过投票解决冲突.

        Args:
            conflict: 冲突
            voters: 投票者列表
            required_approval_ratio: 所需通过率

        Returns:
            更新后的 Conflict
        """
        # 构建提案
        options_desc = ""
        for i, party in enumerate(conflict.parties):
            options_desc += f"  {i + 1}. {party.agent_role.value}: {party.position}\n"

        proposal = self._collab.propose(
            title=f"Conflict: {conflict.description[:60]}",
            description=f"{conflict.description}\n\nOptions:\n{options_desc}",
            proposed_by="supervisor",
            required_voters=voters,
            required_approval_ratio=required_approval_ratio,
        )

        # 模拟投票: 各方按立场投票
        for party in conflict.parties:
            voter_id = f"{party.agent_role.value}_agent"
            if voter_id in voters:
                # 第一个 party 投 APPROVE
                if party == conflict.parties[0]:
                    self._collab.vote(proposal.proposal_id, voter_id, VoteOption.APPROVE, party.position)
                else:
                    self._collab.vote(proposal.proposal_id, voter_id, VoteOption.REJECT, party.position)

        result = self._collab.tally_proposal(proposal.proposal_id)

        conflict.resolution_strategy = ResolutionStrategy.VOTE
        conflict.resolved_at = datetime.now(timezone.utc).isoformat()

        if result == ConsensusResult.APPROVED:
            conflict.resolution_result = conflict.parties[0].position
            conflict.resolution_rationale = f"Vote approved ({proposal.approval_ratio:.0%})"
        elif result == ConsensusResult.REJECTED:
            # 回退到第二个方案
            if len(conflict.parties) > 1:
                conflict.resolution_result = conflict.parties[1].position
                conflict.resolution_rationale = f"Vote rejected, fallback to {conflict.parties[1].agent_role.value}"
            else:
                conflict.resolution_result = "rejected"
                conflict.resolution_rationale = "Vote rejected, no fallback"
        else:
            conflict.resolution_result = "deadlocked"
            conflict.resolution_rationale = f"Vote {result.value}"

        self._resolved.append(conflict)
        self._conflicts.pop(conflict.conflict_id, None)
        return conflict

    def resolve_by_supervisor(
        self,
        conflict: Conflict,
        decision: str,
        rationale: str,
    ) -> Conflict:
        """Supervisor 直接决策.

        Args:
            conflict: 冲突
            decision: Supervisor 决策
            rationale: 决策理由

        Returns:
            更新后的 Conflict
        """
        conflict.resolution_strategy = ResolutionStrategy.SUPERVISOR_DECISION
        conflict.resolution_result = decision
        conflict.resolution_rationale = rationale
        conflict.resolved_at = datetime.now(timezone.utc).isoformat()
        self._resolved.append(conflict)
        self._conflicts.pop(conflict.conflict_id, None)
        return conflict

    def resolve_by_data(
        self,
        conflict: Conflict,
        data: dict[str, Any],
    ) -> Conflict:
        """数据驱动解决 — 选择预期影响最大的方案.

        Args:
            conflict: 冲突
            data: 历史数据 (用于评估)

        Returns:
            更新后的 Conflict
        """
        best_party = None
        best_score = -1.0

        for party in conflict.parties:
            # 综合评分: 预期影响 × 置信度
            total_impact = sum(abs(v) for v in party.expected_impact.values())
            score = total_impact * party.confidence

            # 历史数据加权
            hist_key = f"{party.agent_role.value}_{conflict.conflict_type.value}"
            if hist_key in data:
                score *= data[hist_key].get("success_rate", 1.0)

            if score > best_score:
                best_score = score
                best_party = party

        if best_party:
            conflict.resolution_strategy = ResolutionStrategy.DATA_DRIVEN
            conflict.resolution_result = best_party.position
            conflict.resolution_rationale = (
                f"Data-driven: {best_party.agent_role.value} "
                f"score={best_score:.3f} (impact={best_party.expected_impact})"
            )
        else:
            conflict.resolution_strategy = ResolutionStrategy.DEFER
            conflict.resolution_result = "deferred"
            conflict.resolution_rationale = "No data-driven winner"

        conflict.resolved_at = datetime.now(timezone.utc).isoformat()
        self._resolved.append(conflict)
        self._conflicts.pop(conflict.conflict_id, None)
        return conflict

    def resolve_by_compromise(
        self,
        conflict: Conflict,
        compromise: dict[str, Any],
        rationale: str,
    ) -> Conflict:
        """妥协方案 — 取中间值.

        Example:
            UA 建议 +50% 预算, Monetization 建议 0%
            → 妥协: +25% 预算, 附带监控条件

        Args:
            conflict: 冲突
            compromise: 妥协方案
            rationale: 理由

        Returns:
            更新后的 Conflict
        """
        conflict.resolution_strategy = ResolutionStrategy.COMPROMISE
        conflict.resolution_result = str(compromise)
        conflict.resolution_rationale = rationale
        conflict.resolved_at = datetime.now(timezone.utc).isoformat()
        self._resolved.append(conflict)
        self._conflicts.pop(conflict.conflict_id, None)
        return conflict

    # ── 自动解决 ──────────────────────────────────────────────

    def auto_resolve(
        self,
        conflict: Conflict,
        voters: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Conflict:
        """自动选择最佳解决策略.

        优先级:
          1. 数据驱动 (有历史数据)
          2. 投票 (多方参与)
          3. 妥协 (Supervisor 决策)

        Args:
            conflict: 冲突
            voters: 投票者 (None = 从 parties 自动生成)
            data: 历史数据

        Returns:
            解决后的 Conflict
        """
        # 策略 1: 数据驱动
        if data and len(data) > 0:
            return self.resolve_by_data(conflict, data)

        # 策略 2: 投票
        if len(conflict.parties) >= 2:
            auto_voters = voters or [f"{p.agent_role.value}_agent" for p in conflict.parties]
            auto_voters.append("supervisor")
            return self.resolve_by_vote(conflict, auto_voters)

        # 策略 3: Supervisor 直接决策
        return self.resolve_by_supervisor(
            conflict,
            decision=conflict.parties[0].position if conflict.parties else "unknown",
            rationale="Auto-resolved by supervisor (single party)",
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_conflict(self, conflict_id: str) -> Conflict | None:
        return self._conflicts.get(conflict_id)

    def get_active_conflicts(self) -> list[Conflict]:
        return list(self._conflicts.values())

    def get_resolved_conflicts(self) -> list[Conflict]:
        return list(self._resolved)

    def get_conflicts_by_type(self, conflict_type: ConflictType) -> list[Conflict]:
        return [c for c in self._conflicts.values() if c.conflict_type == conflict_type]

    def get_by_role(self, role: AgentRole) -> list[Conflict]:
        """获取涉及特定角色的冲突."""
        result = []
        for c in self._conflicts.values():
            if any(p.agent_role == role for p in c.parties):
                result.append(c)
        for c in self._resolved:
            if any(p.agent_role == role for p in c.parties):
                result.append(c)
        return result

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        active = len(self._conflicts)
        resolved = len(self._resolved)
        total = active + resolved

        type_counts = {}
        for c in list(self._conflicts.values()) + self._resolved:
            type_counts[c.conflict_type.value] = type_counts.get(c.conflict_type.value, 0) + 1

        strategy_counts = {}
        for c in self._resolved:
            if c.resolution_strategy:
                strategy_counts[c.resolution_strategy.value] = (
                    strategy_counts.get(c.resolution_strategy.value, 0) + 1
                )

        return {
            "total_conflicts": total,
            "active_conflicts": active,
            "resolved_conflicts": resolved,
            "resolution_rate": resolved / max(total, 1),
            "type_counts": type_counts,
            "strategy_counts": strategy_counts,
        }

    def reset(self) -> None:
        self._conflicts.clear()
        self._resolved.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_conflict_resolver(collab: CollaborationEngine | None = None) -> ConflictResolver:
    return ConflictResolver(collab=collab)