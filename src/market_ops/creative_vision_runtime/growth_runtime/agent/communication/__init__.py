"""E14.1 Agent Communication Layer — 多 Agent 通信基础设施.

提供多 Agent 系统所需的核心通信组件:

  1. agent_message: Agent 消息协议 (身份、消息类型、优先级)
  2. message_bus: 消息总线 (路由、发布/订阅、优先级队列)
  3. task_protocol: 任务协议 (分配、追踪、分解)
  4. agent_registry: Agent 注册中心 (发现、健康检查)
  5. collaboration: 协作原语 (请求/响应、投票、协商)

典型用法:
    from communication import (
        MessageBus, AgentRegistry, CollaborationEngine,
        create_agent_identity, AgentRole, create_default_organization,
    )

    bus = MessageBus()
    registry = create_default_organization()
    collab = CollaborationEngine(bus=bus, registry=registry)

    ua = registry.find_by_role(AgentRole.UA)[0].identity
    creative = registry.find_by_role(AgentRole.CREATIVE)[0].identity

    collab.request(ua, creative, "分析素材疲劳", {"campaign": "P04"})
"""

from .agent_message import (
    AgentIdentity,
    AgentRole,
    AgentMessage,
    MessageType,
    MessagePriority,
    MessageStatus,
    StandardMessageType,
    MessageContext,
    create_agent_identity,
    create_ua_agent_identity,
    create_creative_agent_identity,
    create_monetization_agent_identity,
    create_supervisor_agent_identity,
    create_product_agent_identity,
    create_liveops_agent_identity,
    create_game_designer_agent_identity,
    create_numerical_designer_agent_identity,
    create_data_analyst_agent_identity,
    create_player_support_agent_identity,
)

from .message_bus import (
    MessageBus,
    MessageHandler,
    MessageQueue,
    Subscription,
    create_message_bus,
)

from .task_protocol import (
    GrowthTask,
    TaskAssignment,
    TaskResult,
    TaskStatus,
    TaskPriority,
    TaskTracker,
    TaskDecomposer,
    create_task_tracker,
    create_task_decomposer,
)

from .agent_registry import (
    AgentRegistry,
    AgentRecord,
    AgentStatus,
    create_agent_registry,
    create_default_organization,
)

from .collaboration import (
    CollaborationEngine,
    Proposal,
    Vote,
    VoteOption,
    ConsensusResult,
    create_collaboration_engine,
)

__all__ = [
    # agent_message
    "AgentIdentity",
    "AgentRole",
    "AgentMessage",
    "MessageType",
    "MessagePriority",
    "MessageStatus",
    "StandardMessageType",
    "MessageContext",
    "create_agent_identity",
    "create_ua_agent_identity",
    "create_creative_agent_identity",
    "create_monetization_agent_identity",
    "create_supervisor_agent_identity",
    "create_product_agent_identity",
    "create_liveops_agent_identity",
    "create_game_designer_agent_identity",
    "create_numerical_designer_agent_identity",
    "create_data_analyst_agent_identity",
    "create_player_support_agent_identity",
    # message_bus
    "MessageBus",
    "MessageHandler",
    "MessageQueue",
    "Subscription",
    "create_message_bus",
    # task_protocol
    "GrowthTask",
    "TaskAssignment",
    "TaskResult",
    "TaskStatus",
    "TaskPriority",
    "TaskTracker",
    "TaskDecomposer",
    "create_task_tracker",
    "create_task_decomposer",
    # agent_registry
    "AgentRegistry",
    "AgentRecord",
    "AgentStatus",
    "create_agent_registry",
    "create_default_organization",
    # collaboration
    "CollaborationEngine",
    "Proposal",
    "Vote",
    "VoteOption",
    "ConsensusResult",
    "create_collaboration_engine",
]