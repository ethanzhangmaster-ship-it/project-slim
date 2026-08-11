"""E14.1.5 Collaboration — 多 Agent 协作原语.

协作原语定义了 Agent 间的交互模式:
  - Request/Response: 同步请求-响应
  - Broadcast: 一对多通知
  - Task Dispatch: 任务分配
  - Negotiation: 冲突协商
  - Voting: 投票决策
  - Consensus: 共识达成

设计原则:
  - 基于 MessageBus 实现
  - 每种协作模式有明确的语义
  - 支持超时和重试
  - 保留协作历史用于审计
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from .agent_message import (
    AgentIdentity,
    AgentMessage,
    AgentRole,
    MessagePriority,
    MessageStatus,
    MessageType,
    StandardMessageType,
)
from .agent_registry import AgentRegistry, AgentStatus
from .message_bus import MessageBus


# ═══════════════════════════════════════════════════════════════
# Collaboration Models
# ═══════════════════════════════════════════════════════════════


class VoteOption(str, Enum):
    """投票选项."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class ConsensusResult(str, Enum):
    """共识结果."""
    APPROVED = "approved"
    REJECTED = "rejected"
    DEADLOCKED = "deadlocked"
    TIMED_OUT = "timed_out"


@dataclass
class Vote:
    """投票记录."""
    vote_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str = ""
    voter_id: str = ""
    option: VoteOption = VoteOption.ABSTAIN
    reason: str = ""
    voted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote_id": self.vote_id,
            "proposal_id": self.proposal_id,
            "voter_id": self.voter_id,
            "option": self.option.value,
            "reason": self.reason,
            "voted_at": self.voted_at,
        }


@dataclass
class Proposal:
    """提案 — 需要多 Agent 投票决策的事项."""
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    proposed_by: str = ""
    required_voters: list[str] = field(default_factory=list)
    required_approval_ratio: float = 0.5
    deadline_seconds: float = 300.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    votes: list[Vote] = field(default_factory=list)
    result: ConsensusResult | None = None

    @property
    def is_expired(self) -> bool:
        try:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.now(timezone.utc) - created).total_seconds() > self.deadline_seconds
        except (ValueError, TypeError):
            return False

    @property
    def approval_ratio(self) -> float:
        total = len(self.votes)
        if total == 0:
            return 0.0
        approves = sum(1 for v in self.votes if v.option == VoteOption.APPROVE)
        return approves / total

    def tally(self) -> ConsensusResult:
        """计票."""
        if self.is_expired:
            return ConsensusResult.TIMED_OUT

        required = len(self.required_voters)
        if required == 0:
            return ConsensusResult.APPROVED

        if len(self.votes) < required:
            return ConsensusResult.TIMED_OUT  # 投票不足

        if self.approval_ratio >= self.required_approval_ratio:
            return ConsensusResult.APPROVED
        else:
            return ConsensusResult.REJECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "proposed_by": self.proposed_by,
            "required_voters": self.required_voters,
            "required_approval_ratio": self.required_approval_ratio,
            "deadline_seconds": self.deadline_seconds,
            "votes": [v.to_dict() for v in self.votes],
            "approval_ratio": self.approval_ratio,
            "result": self.result.value if self.result else None,
            "is_expired": self.is_expired,
        }


# ═══════════════════════════════════════════════════════════════
# Collaboration Engine
# ═══════════════════════════════════════════════════════════════


class CollaborationEngine:
    """协作引擎 — 提供多 Agent 协作原语.

    支持:
      - Request/Response: 同步请求-响应
      - Broadcast: 一对多通知
      - Task Dispatch: 任务分配
      - Voting: 投票决策
      - Consensus: 共识达成
      - Negotiation: 冲突协商
    """

    def __init__(
        self,
        bus: MessageBus | None = None,
        registry: AgentRegistry | None = None,
    ):
        self._bus = bus or MessageBus()
        self._registry = registry or AgentRegistry()
        self._proposals: dict[str, Proposal] = {}
        self._pending_requests: dict[str, AgentMessage] = {}
        self._responses: dict[str, list[AgentMessage]] = defaultdict(list)
        self._collaboration_log: list[dict[str, Any]] = []

    # ── Request/Response ──────────────────────────────────────

    def request(
        self,
        sender: AgentIdentity,
        receiver: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        standard_type: StandardMessageType | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """发起请求 — 等待对方响应."""
        msg = AgentMessage.create_request(
            sender=sender,
            receiver=receiver,
            subject=subject,
            body=body,
            standard_type=standard_type,
            priority=priority,
        )
        self._bus.send(msg)
        self._pending_requests[msg.message_id] = msg
        self._log_collaboration("request", msg)
        return msg

    def respond(
        self,
        original: AgentMessage,
        body: dict[str, Any],
    ) -> AgentMessage:
        """响应请求."""
        response = self._bus.send_response(original, body)
        self._responses[original.message_id].append(response)
        self._log_collaboration("response", response)
        return response

    def get_response(self, request_id: str) -> list[AgentMessage]:
        """获取请求的响应."""
        return self._responses.get(request_id, [])

    # ── Broadcast ─────────────────────────────────────────────

    def broadcast(
        self,
        sender: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        standard_type: StandardMessageType | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """广播消息 — 发给所有已注册 Agent."""
        msg = AgentMessage.create_broadcast(
            sender=sender,
            subject=subject,
            body=body,
            standard_type=standard_type,
            priority=priority,
        )
        self._bus.send(msg)
        self._log_collaboration("broadcast", msg)
        return msg

    def broadcast_to_role(
        self,
        sender: AgentIdentity,
        role: AgentRole,
        subject: str,
        body: dict[str, Any],
        standard_type: StandardMessageType | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """向特定角色广播."""
        msg = AgentMessage.create_broadcast(
            sender=sender,
            subject=subject,
            body=body,
            standard_type=standard_type,
            priority=priority,
        )
        known = {r.identity.agent_id: r.identity for r in self._registry.get_all()}
        self._bus.send_to_role(msg, role, known)
        self._log_collaboration("broadcast_to_role", msg)
        return msg

    # ── Task Dispatch ─────────────────────────────────────────

    def dispatch_task(
        self,
        sender: AgentIdentity,
        receiver: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        priority: MessagePriority = MessagePriority.HIGH,
    ) -> AgentMessage:
        """分配任务."""
        msg = AgentMessage.create_task(
            sender=sender,
            receiver=receiver,
            subject=subject,
            body=body,
            priority=priority,
        )
        self._bus.send(msg)
        self._log_collaboration("task_dispatch", msg)
        return msg

    def dispatch_to_role(
        self,
        sender: AgentIdentity,
        role: AgentRole,
        subject: str,
        body: dict[str, Any],
        registry: AgentRegistry | None = None,
    ) -> list[AgentMessage]:
        """向特定角色的所有 Agent 分配任务.

        Returns:
            发送的任务消息列表
        """
        reg = registry or self._registry
        agents = reg.find_by_role(role)
        messages = []
        for record in agents:
            if record.is_alive():
                msg = self.dispatch_task(
                    sender=sender,
                    receiver=record.identity,
                    subject=subject,
                    body=body,
                )
                messages.append(msg)
        return messages

    # ── Voting ────────────────────────────────────────────────

    def propose(
        self,
        title: str,
        description: str,
        proposed_by: str,
        required_voters: list[str],
        required_approval_ratio: float = 0.5,
        deadline_seconds: float = 300.0,
    ) -> Proposal:
        """创建提案."""
        proposal = Proposal(
            title=title,
            description=description,
            proposed_by=proposed_by,
            required_voters=required_voters,
            required_approval_ratio=required_approval_ratio,
            deadline_seconds=deadline_seconds,
        )
        self._proposals[proposal.proposal_id] = proposal
        self._log_collaboration("proposal", proposal)
        return proposal

    def vote(
        self,
        proposal_id: str,
        voter_id: str,
        option: VoteOption,
        reason: str = "",
    ) -> Vote | None:
        """投票."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None

        # 检查是否已投票
        for v in proposal.votes:
            if v.voter_id == voter_id:
                return v  # 已投过

        vote = Vote(
            proposal_id=proposal_id,
            voter_id=voter_id,
            option=option,
            reason=reason,
        )
        proposal.votes.append(vote)

        # 检查是否达成共识
        if len(proposal.votes) >= len(proposal.required_voters):
            proposal.result = proposal.tally()

        self._log_collaboration("vote", vote)
        return vote

    def tally_proposal(self, proposal_id: str) -> ConsensusResult | None:
        """计票."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        proposal.result = proposal.tally()
        return proposal.result

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        """获取提案."""
        return self._proposals.get(proposal_id)

    # ── Negotiation ───────────────────────────────────────────

    def negotiate(
        self,
        sender: AgentIdentity,
        receiver: AgentIdentity,
        subject: str,
        initial_offer: dict[str, Any],
        max_rounds: int = 3,
        deadline_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """协商 — 多轮 offer/counter-offer.

        Args:
            sender: 发起方
            receiver: 接收方
            subject: 协商主题
            initial_offer: 初始提议
            max_rounds: 最大回合数
            deadline_seconds: 截止时间

        Returns:
            negotiation_result: 协商结果
        """
        negotiation_id = str(uuid.uuid4())
        rounds = [{
            "round": 0,
            "from": sender.agent_id,
            "to": receiver.agent_id,
            "offer": initial_offer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

        # 发送初始提议
        self.request(
            sender=sender,
            receiver=receiver,
            subject=f"Negotiation: {subject}",
            body={
                "negotiation_id": negotiation_id,
                "round": 0,
                "max_rounds": max_rounds,
                "offer": initial_offer,
                "deadline_seconds": deadline_seconds,
            },
            priority=MessagePriority.HIGH,
        )

        self._log_collaboration("negotiation_start", {
            "negotiation_id": negotiation_id,
            "subject": subject,
            "parties": [sender.agent_id, receiver.agent_id],
            "max_rounds": max_rounds,
        })

        return {
            "negotiation_id": negotiation_id,
            "status": "initiated",
            "rounds": rounds,
            "current_round": 0,
        }

    # ── 冲突解决 ──────────────────────────────────────────────

    def resolve_conflict(
        self,
        conflict_description: str,
        models: list[dict[str, Any]],
        required_voters: list[str],
    ) -> Proposal:
        """冲突解决 — 通过投票解决 Agent 间冲突.

        Example:
            UA 建议增加预算 50%
            Monetization 拒绝 (LTV 下降)
            → 投票解决

        Args:
            conflict_description: 冲突描述
            models: 各 Agent 的提议
            required_voters: 需要投票的 Agent

        Returns:
            Proposal: 投票提案
        """
        description = f"{conflict_description}\n\nOptions:\n"
        for i, model in enumerate(models):
            description += f"  {i + 1}. {model.get('agent', '?')}: {model.get('proposal', '?')}\n"

        return self.propose(
            title=f"Conflict: {conflict_description[:60]}",
            description=description,
            proposed_by="supervisor",
            required_voters=required_voters,
            required_approval_ratio=0.5,
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_pending_requests(self) -> list[AgentMessage]:
        """获取未响应的请求."""
        return [
            msg for msg in self._pending_requests.values()
            if msg.status == MessageStatus.SENT
        ]

    def get_collaboration_log(self, n: int = 100) -> list[dict[str, Any]]:
        """获取协作日志."""
        return self._collaboration_log[-n:]

    def stats(self) -> dict[str, Any]:
        """获取协作统计."""
        return {
            "pending_requests": len(self.get_pending_requests()),
            "total_responses": sum(len(r) for r in self._responses.values()),
            "active_proposals": len([p for p in self._proposals.values() if p.result is None]),
            "resolved_proposals": len([p for p in self._proposals.values() if p.result is not None]),
            "log_entries": len(self._collaboration_log),
        }

    def reset(self) -> None:
        """重置协作引擎."""
        self._proposals.clear()
        self._pending_requests.clear()
        self._responses.clear()
        self._collaboration_log.clear()
        self._bus.reset()

    # ── 内部 ──────────────────────────────────────────────────

    def _log_collaboration(self, event_type: str, data: Any) -> None:
        """记录协作事件."""
        entry = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(data, "to_dict"):
            entry["data"] = data.to_dict()
        elif isinstance(data, dict):
            entry["data"] = data
        else:
            entry["data"] = str(data)
        self._collaboration_log.append(entry)


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_collaboration_engine(
    bus: MessageBus | None = None,
    registry: AgentRegistry | None = None,
) -> CollaborationEngine:
    """创建默认协作引擎."""
    return CollaborationEngine(bus=bus, registry=registry)