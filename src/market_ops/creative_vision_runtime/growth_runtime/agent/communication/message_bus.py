"""E14.1.2 Message Bus — 多 Agent 消息总线.

消息总线是 Agent 通信层的核心路由基础设施:
  - 点对点路由: sender → receiver
  - 广播: sender → all registered agents
  - 角色路由: sender → all agents with specific role
  - 发布/订阅: 按 topic 订阅消息
  - 优先级队列: 按 MessagePriority 排序投递
  - 消息持久化: 消息历史记录 (用于审计和重放)

设计原则:
  - 消息总线是无状态的 — 状态由 Agent 自身管理
  - 支持同步和异步投递
  - 消息不丢失 (内存队列, 非持久化)
  - 优先级保证高优先级消息先投递
"""

from __future__ import annotations

import heapq
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


# ═══════════════════════════════════════════════════════════════
# Message Handler
# ═══════════════════════════════════════════════════════════════


@dataclass
class MessageHandler:
    """消息处理器 — 注册到 MessageBus 的回调.

    Attributes:
        handler_id: 处理器 ID
        agent_id: 关联的 Agent ID
        handler: 回调函数 (AgentMessage → AgentMessage | None)
        message_types: 感兴趣的消息类型 (空 = 所有)
        standard_types: 感兴趣的标准消息类型 (空 = 所有)
        priority: 最低处理优先级
        timeout: 处理超时 (秒)
        is_active: 是否激活
    """
    handler_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    handler: Callable[[AgentMessage], AgentMessage | None] | None = None
    message_types: list[MessageType] = field(default_factory=list)
    standard_types: list[StandardMessageType] = field(default_factory=list)
    priority: MessagePriority = MessagePriority.LOW
    timeout: float = 60.0
    is_active: bool = True

    def can_handle(self, msg: AgentMessage) -> bool:
        """检查是否可以处理该消息."""
        if not self.is_active:
            return False
        if self.message_types and msg.message_type not in self.message_types:
            return False
        if self.standard_types and msg.standard_type not in self.standard_types:
            return False
        if msg.priority < self.priority:
            return False
        return True

    def handle(self, msg: AgentMessage) -> AgentMessage | None:
        """处理消息."""
        if not self.handler:
            return None
        try:
            return self.handler(msg)
        except Exception as e:
            msg.mark_failed(str(e))
            return None


# ═══════════════════════════════════════════════════════════════
# Subscription
# ═══════════════════════════════════════════════════════════════


@dataclass
class Subscription:
    """订阅 — Agent 对特定 topic 的订阅.

    Attributes:
        subscription_id: 订阅 ID
        agent_id: 订阅者 Agent ID
        topic: 订阅主题
        filter_func: 过滤函数 (AgentMessage → bool)
        priority: 最低优先级
        is_active: 是否激活
    """
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    topic: str = ""
    filter_func: Callable[[AgentMessage], bool] | None = None
    priority: MessagePriority = MessagePriority.LOW
    is_active: bool = True

    def matches(self, msg: AgentMessage) -> bool:
        """检查消息是否匹配此订阅."""
        if not self.is_active:
            return False
        if msg.priority < self.priority:
            return False
        if self.filter_func and not self.filter_func(msg):
            return False
        return True


# ═══════════════════════════════════════════════════════════════
# Message Queue
# ═══════════════════════════════════════════════════════════════


@dataclass(order=True)
class _QueuedMessage:
    """优先级队列中的消息包装."""
    priority: int  # 负值用于 heapq (最小堆) 实现最大优先级
    message: AgentMessage = field(compare=False)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), compare=False)


class MessageQueue:
    """优先级消息队列 — 按优先级排序的消息缓冲区.

    用于 Agent 的 inbox 和 Bus 的待投递队列.
    """

    def __init__(self, max_size: int = 1000):
        self._heap: list[_QueuedMessage] = []
        self._max_size = max_size
        self._delivered_count: int = 0
        self._dropped_count: int = 0

    @property
    def size(self) -> int:
        return len(self._heap)

    def push(self, msg: AgentMessage) -> bool:
        """入队消息 (优先级排序)."""
        if self.size >= self._max_size:
            # 丢弃最低优先级
            if self._heap:
                heapq.heappop(self._heap)
                self._dropped_count += 1
            else:
                return False

        heapq.heappush(self._heap, _QueuedMessage(
            priority=-msg.priority.value,
            message=msg,
        ))
        return True

    def pop(self) -> AgentMessage | None:
        """出队最高优先级消息."""
        if not self._heap:
            return None
        item = heapq.heappop(self._heap)
        self._delivered_count += 1
        return item.message

    def peek(self) -> AgentMessage | None:
        """查看最高优先级消息 (不移除)."""
        if not self._heap:
            return None
        return self._heap[0].message

    def drain(self) -> list[AgentMessage]:
        """清空队列."""
        messages = []
        while self._heap:
            item = heapq.heappop(self._heap)
            messages.append(item.message)
        self._delivered_count += len(messages)
        return messages

    def stats(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "delivered_count": self._delivered_count,
            "dropped_count": self._dropped_count,
        }


# ═══════════════════════════════════════════════════════════════
# Message Bus
# ═══════════════════════════════════════════════════════════════


class MessageBus:
    """消息总线 — Agent 通信层的核心路由基础设施.

    职责:
      1. 路由: 根据 sender/receiver 投递消息
      2. 广播: 向所有注册 Agent 发送消息
      3. 角色路由: 向特定 role 的所有 Agent 发送
      4. 发布/订阅: 按 topic 投递
      5. 历史记录: 消息审计追踪

    用法:
        bus = MessageBus()
        bus.register_handler("agent_1", handler_fn)
        bus.send(msg)
        results = bus.deliver("agent_1")
    """

    def __init__(self, bus_id: str = "", max_history: int = 10000):
        self._bus_id = bus_id or str(uuid.uuid4())
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._inboxes: dict[str, MessageQueue] = defaultdict(MessageQueue)
        self._history: list[AgentMessage] = []
        self._max_history = max_history
        self._sent_count: int = 0
        self._delivered_count: int = 0
        self._error_count: int = 0

    # ── 注册 ──────────────────────────────────────────────────

    def register_handler(self, handler: MessageHandler) -> None:
        """注册消息处理器."""
        self._handlers[handler.agent_id].append(handler)

    def register_handler_fn(
        self,
        agent_id: str,
        handler_fn: Callable[[AgentMessage], AgentMessage | None],
        message_types: list[MessageType] | None = None,
        standard_types: list[StandardMessageType] | None = None,
    ) -> MessageHandler:
        """注册回调函数作为处理器."""
        handler = MessageHandler(
            agent_id=agent_id,
            handler=handler_fn,
            message_types=message_types or [],
            standard_types=standard_types or [],
        )
        self.register_handler(handler)
        return handler

    def register_subscription(self, sub: Subscription) -> None:
        """注册订阅."""
        self._subscriptions[sub.topic].append(sub)

    def subscribe(
        self,
        agent_id: str,
        topic: str,
        filter_func: Callable[[AgentMessage], bool] | None = None,
        priority: MessagePriority = MessagePriority.LOW,
    ) -> Subscription:
        """订阅主题."""
        sub = Subscription(
            agent_id=agent_id,
            topic=topic,
            filter_func=filter_func,
            priority=priority,
        )
        self.register_subscription(sub)
        return sub

    def unregister_handler(self, agent_id: str) -> None:
        """注销 Agent 的所有处理器."""
        self._handlers.pop(agent_id, None)

    def unregister_subscription(self, subscription_id: str) -> None:
        """注销订阅."""
        for topic, subs in self._subscriptions.items():
            self._subscriptions[topic] = [
                s for s in subs if s.subscription_id != subscription_id
            ]

    # ── 发送 ──────────────────────────────────────────────────

    def send(self, msg: AgentMessage) -> None:
        """发送消息 — 路由到目标 Agent 的 inbox.

        路由规则:
          1. 点对点: 有 receiver → 投递到 receiver inbox
          2. 广播: BROADCAST → 投递到所有注册 Agent inbox
          3. 订阅: 匹配 topic → 投递到订阅者 inbox
        """
        msg.mark_sent()
        self._sent_count += 1
        self._add_to_history(msg)

        if msg.message_type == MessageType.BROADCAST:
            # 广播: 投递到所有注册 Agent
            for agent_id in self._handlers:
                self._inboxes[agent_id].push(msg)
        elif msg.receiver:
            # 点对点
            self._inboxes[msg.is_to].push(msg)
        else:
            # 无 receiver 且非广播: 按 topic 投递
            topic = msg.standard_type.value if msg.standard_type else msg.subject
            for sub in self._subscriptions.get(topic, []):
                if sub.matches(msg):
                    self._inboxes[sub.agent_id].push(msg)

    def send_to_role(
        self,
        msg: AgentMessage,
        role: AgentRole,
        known_agents: dict[str, AgentIdentity] | None = None,
    ) -> None:
        """向特定角色的所有 Agent 发送消息."""
        msg.mark_sent()
        self._sent_count += 1
        self._add_to_history(msg)

        if known_agents:
            for agent_id, identity in known_agents.items():
                if identity.role == role:
                    self._inboxes[agent_id].push(msg)
        else:
            # 遍历所有注册的 handler
            for agent_id in self._handlers:
                self._inboxes[agent_id].push(msg)

    def send_response(
        self,
        original: AgentMessage,
        body: dict[str, Any],
    ) -> AgentMessage:
        """发送响应消息."""
        response = AgentMessage.create_response(original, body)
        self.send(response)
        return response

    # ── 投递 ──────────────────────────────────────────────────

    def deliver(self, agent_id: str, max_count: int = 10) -> list[AgentMessage]:
        """投递消息给指定 Agent — 从 inbox 取出并处理.

        Args:
            agent_id: Agent ID
            max_count: 最多投递数量

        Returns:
            处理后的消息列表
        """
        inbox = self._inboxes[agent_id]
        results = []

        for _ in range(min(max_count, inbox.size)):
            msg = inbox.pop()
            if msg is None:
                break

            if msg.is_expired:
                msg.mark_expired()
                results.append(msg)
                continue

            msg.mark_delivered()

            # 查找匹配的 handler
            handlers = self._handlers.get(agent_id, [])
            handled = False
            for handler in handlers:
                if handler.can_handle(msg):
                    try:
                        response = handler.handle(msg)
                        if response:
                            self.send(response)
                        msg.mark_processed()
                        handled = True
                        self._delivered_count += 1
                    except Exception as e:
                        msg.mark_failed(str(e))
                        self._error_count += 1
                    break

            if not handled:
                # 没有 handler 处理, 标记为已处理
                msg.mark_processed()
                self._delivered_count += 1

            results.append(msg)

        return results

    def deliver_all(self, agent_id: str) -> list[AgentMessage]:
        """投递所有待处理消息."""
        inbox = self._inboxes[agent_id]
        return self.deliver(agent_id, max_count=inbox.size)

    def deliver_to_all(self, max_per_agent: int = 10) -> dict[str, list[AgentMessage]]:
        """向所有 Agent 投递消息."""
        results = {}
        for agent_id in list(self._inboxes.keys()):
            delivered = self.deliver(agent_id, max_per_agent)
            if delivered:
                results[agent_id] = delivered
        return results

    # ── 查询 ──────────────────────────────────────────────────

    def get_inbox_size(self, agent_id: str) -> int:
        """获取 Agent inbox 大小."""
        return self._inboxes[agent_id].size

    def get_inbox_stats(self, agent_id: str) -> dict[str, Any]:
        """获取 Agent inbox 统计."""
        return self._inboxes[agent_id].stats()

    def get_history(self, n: int = 100) -> list[AgentMessage]:
        """获取最近消息历史."""
        return self._history[-n:]

    def get_history_by_type(self, msg_type: MessageType, n: int = 100) -> list[AgentMessage]:
        """按类型获取历史."""
        return [m for m in self._history if m.message_type == msg_type][-n:]

    def get_history_between(self, sender_id: str, receiver_id: str, n: int = 100) -> list[AgentMessage]:
        """获取两个 Agent 间的消息历史."""
        return [
            m for m in self._history
            if m.is_from == sender_id and m.is_to == receiver_id
        ][-n:]

    def stats(self) -> dict[str, Any]:
        """获取总线统计."""
        return {
            "bus_id": self._bus_id,
            "sent_count": self._sent_count,
            "delivered_count": self._delivered_count,
            "error_count": self._error_count,
            "history_size": len(self._history),
            "registered_agents": len(self._handlers),
            "active_subscriptions": sum(len(subs) for subs in self._subscriptions.values()),
            "pending_inboxes": sum(inbox.size for inbox in self._inboxes.values()),
        }

    def reset(self) -> None:
        """重置总线."""
        self._handlers.clear()
        self._subscriptions.clear()
        self._inboxes.clear()
        self._history.clear()
        self._sent_count = 0
        self._delivered_count = 0
        self._error_count = 0

    # ── 内部 ──────────────────────────────────────────────────

    def _add_to_history(self, msg: AgentMessage) -> None:
        """添加到历史记录."""
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_message_bus(max_history: int = 10000) -> MessageBus:
    """创建默认消息总线."""
    return MessageBus(max_history=max_history)