"""E14.1.1 Agent Message — 多 Agent 通信消息协议.

定义 Agent 间通信的完整消息模型:
  - AgentIdentity: Agent 唯一标识
  - AgentRole: Agent 角色类型 (UA, Creative, Monetization, Product, Supervisor)
  - MessageType: 消息类型 (REQUEST, RESPONSE, BROADCAST, ALERT, TASK, ACK)
  - AgentMessage: 标准消息信封
  - MessagePriority: 优先级 (LOW, NORMAL, HIGH, CRITICAL)
  - MessageStatus: 消息状态 (SENT, DELIVERED, READ, PROCESSED, FAILED)

设计原则:
  - 所有消息必须包含 sender/receiver 标识
  - 消息体为结构化 dict，支持任意 payload
  - 优先级驱动消息路由
  - 消息不可变 (frozen dataclass 行为)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Agent Identity & Role
# ═══════════════════════════════════════════════════════════════


class AgentRole(str, Enum):
    """Agent 角色类型 — 定义 Agent 在组织中的职责."""
    SUPERVISOR = "supervisor"       # 主管 Agent: 分配任务、冲突解决
    UA = "ua"                       # UA Agent: 用户获取
    CREATIVE = "creative"           # Creative Agent: 创意素材
    MONETIZATION = "monetization"   # Monetization Agent: 变现
    PRODUCT = "product"             # Product Agent: 产品内增长
    OBSERVER = "observer"           # Observer Agent: 监控与告警
    EXECUTOR = "executor"           # Executor Agent: 执行引擎
    MEMORY = "memory"               # Memory Agent: 知识管理
    LIVEOPS = "liveops"             # LiveOps Agent: 生命周期运营、回流活动
    DESIGNER = "designer"           # Game Designer Agent: 关卡/数值/系统设计
    NUMERICAL = "numerical"         # Numerical Designer Agent: 数值建模/调优/A/B测试
    DATA_ANALYST = "data_analyst"   # Data Analyst Agent: 玩家行为分析/漏斗归因/BI 报表
    PLAYER_SUPPORT = "player_support"  # Player Support Agent: 工单/FAQ/舆情/VIP 服务


@dataclass(frozen=True)
class AgentIdentity:
    """Agent 唯一标识 — 不可变.

    Attributes:
        agent_id: Agent 唯一 ID
        role: Agent 角色
        name: Agent 名称
        capabilities: 能力列表
        metadata: 扩展元数据
    """
    agent_id: str
    role: AgentRole
    name: str = ""
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or f"{self.role.value}_{self.agent_id[:8]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentIdentity:
        return cls(
            agent_id=data["agent_id"],
            role=AgentRole(data["role"]),
            name=data.get("name", ""),
            capabilities=tuple(data.get("capabilities", [])),
            metadata=data.get("metadata", {}),
        )


# ═══════════════════════════════════════════════════════════════
# Message Types
# ═══════════════════════════════════════════════════════════════


class MessageType(str, Enum):
    """消息类型."""
    REQUEST = "request"              # 请求: 需要回复
    RESPONSE = "response"            # 响应: 回复请求
    BROADCAST = "broadcast"          # 广播: 发给所有 Agent
    TASK = "task"                    # 任务: 分配工作
    TASK_UPDATE = "task_update"      # 任务更新: 进度汇报
    TASK_RESULT = "task_result"      # 任务结果: 完成汇报
    ALERT = "alert"                  # 告警: 异常通知
    HEARTBEAT = "heartbeat"          # 心跳: 健康检查
    SYNC = "sync"                    # 同步: 状态同步
    QUERY = "query"                  # 查询: 信息请求
    ACK = "ack"                      # 确认

    # 是否为请求类消息 (需要响应)
    @property
    def is_request(self) -> bool:
        return self in (MessageType.REQUEST, MessageType.QUERY, MessageType.TASK)

    # 是否为响应类消息
    @property
    def is_response(self) -> bool:
        return self in (MessageType.RESPONSE, MessageType.TASK_RESULT, MessageType.ACK)


class MessagePriority(int, Enum):
    """消息优先级 — 数值越高优先级越高."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageStatus(str, Enum):
    """消息生命周期状态."""
    CREATED = "created"          # 已创建
    SENT = "sent"                # 已发送
    DELIVERED = "delivered"      # 已投递
    READ = "read"                # 已读取
    PROCESSING = "processing"    # 处理中
    PROCESSED = "processed"      # 已处理
    RESPONDED = "responded"      # 已响应
    FAILED = "failed"            # 失败
    EXPIRED = "expired"          # 已过期
    CANCELLED = "cancelled"      # 已取消


# ═══════════════════════════════════════════════════════════════
# Standard Message Types
# ═══════════════════════════════════════════════════════════════


class StandardMessageType(str, Enum):
    """标准消息类型 — 定义 Agent 间常见交互模式.

    每个 Agent 可根据 role 注册支持的 StandardMessageType.
    """
    # UA → Creative
    REQUEST_CREATIVE_ANALYSIS = "request_creative_analysis"
    REQUEST_CREATIVE_VARIANTS = "request_creative_variants"
    # Creative → UA
    CREATIVE_FATIGUE_ALERT = "creative_fatigue_alert"
    CREATIVE_VARIANTS_READY = "creative_variants_ready"
    # UA → Supervisor
    ROAS_ALERT = "roas_alert"
    BUDGET_SCALING_REQUEST = "budget_scaling_request"
    # Supervisor → UA
    BUDGET_ADJUSTMENT = "budget_adjustment"
    CAMPAIGN_ACTION = "campaign_action"
    # UA → Monetization
    REQUEST_LTV_ANALYSIS = "request_ltv_analysis"
    # Monetization → UA
    LTV_ESTIMATE = "ltv_estimate"
    PAYER_CONVERSION_REPORT = "payer_conversion_report"
    # Supervisor → All
    GOAL_ASSIGNMENT = "goal_assignment"
    STRATEGY_UPDATE = "strategy_update"
    # All → Supervisor
    PROGRESS_REPORT = "progress_report"
    ALERT_NOTIFICATION = "alert_notification"
    # 通用
    KNOWLEDGE_QUERY = "knowledge_query"
    MEMORY_SYNC = "memory_sync"
    HEALTH_CHECK = "health_check"


# ═══════════════════════════════════════════════════════════════
# Agent Message
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentMessage:
    """Agent 消息信封 — 所有 Agent 间通信的标准格式.

    消息生命周期:
      CREATED → SENT → DELIVERED → READ → PROCESSING → PROCESSED → RESPONDED
                                         ↓
                                      FAILED / EXPIRED / CANCELLED

    Attributes:
        message_id: 消息唯一 ID
        correlation_id: 关联 ID (回复时关联原消息)
        sender: 发送者身份
        receiver: 接收者身份 (BROADCAST 时可为空)
        message_type: 消息类型
        standard_type: 标准消息类型 (可选)
        subject: 消息主题
        body: 消息体 (结构化数据)
        priority: 优先级
        status: 当前状态
        created_at: 创建时间
        sent_at: 发送时间
        delivered_at: 投递时间
        processed_at: 处理时间
        expires_at: 过期时间
        ttl_seconds: 生存时间 (秒)
        metadata: 扩展元数据
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    sender: AgentIdentity | None = None
    receiver: AgentIdentity | None = None
    message_type: MessageType = MessageType.REQUEST
    standard_type: StandardMessageType | None = None
    subject: str = ""
    body: dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sent_at: str = ""
    delivered_at: str = ""
    processed_at: str = ""
    expires_at: str = ""
    ttl_seconds: float = 300.0  # 默认 5 分钟 TTL
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 工厂方法 ──────────────────────────────────────────────

    @classmethod
    def create_request(
        cls,
        sender: AgentIdentity,
        receiver: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        standard_type: StandardMessageType | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """创建请求消息."""
        return cls(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.REQUEST,
            standard_type=standard_type,
            subject=subject,
            body=body,
            priority=priority,
        )

    @classmethod
    def create_response(
        cls,
        original: AgentMessage,
        body: dict[str, Any],
        status: MessageStatus = MessageStatus.PROCESSED,
    ) -> AgentMessage:
        """创建响应消息 (关联原请求)."""
        return cls(
            correlation_id=original.message_id,
            sender=original.receiver,
            receiver=original.sender,
            message_type=MessageType.RESPONSE,
            standard_type=original.standard_type,
            subject=f"Re: {original.subject}",
            body=body,
            priority=original.priority,
            status=status,
        )

    @classmethod
    def create_broadcast(
        cls,
        sender: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        standard_type: StandardMessageType | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> AgentMessage:
        """创建广播消息."""
        return cls(
            sender=sender,
            message_type=MessageType.BROADCAST,
            standard_type=standard_type,
            subject=subject,
            body=body,
            priority=priority,
        )

    @classmethod
    def create_task(
        cls,
        sender: AgentIdentity,
        receiver: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        priority: MessagePriority = MessagePriority.HIGH,
    ) -> AgentMessage:
        """创建任务分配消息."""
        return cls(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.TASK,
            subject=subject,
            body=body,
            priority=priority,
        )

    @classmethod
    def create_alert(
        cls,
        sender: AgentIdentity,
        receiver: AgentIdentity,
        subject: str,
        body: dict[str, Any],
        priority: MessagePriority = MessagePriority.CRITICAL,
    ) -> AgentMessage:
        """创建告警消息."""
        return cls(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.ALERT,
            subject=subject,
            body=body,
            priority=priority,
        )

    @classmethod
    def create_heartbeat(
        cls,
        sender: AgentIdentity,
    ) -> AgentMessage:
        """创建心跳消息."""
        return cls(
            sender=sender,
            message_type=MessageType.HEARTBEAT,
            subject="heartbeat",
            priority=MessagePriority.LOW,
            ttl_seconds=30.0,
        )

    # ── 状态管理 ──────────────────────────────────────────────

    def mark_sent(self) -> None:
        self.status = MessageStatus.SENT
        self.sent_at = datetime.now(timezone.utc).isoformat()

    def mark_delivered(self) -> None:
        self.status = MessageStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc).isoformat()

    def mark_processed(self) -> None:
        self.status = MessageStatus.PROCESSED
        self.processed_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, error: str = "") -> None:
        self.status = MessageStatus.FAILED
        if error:
            self.metadata["error"] = error

    def mark_expired(self) -> None:
        self.status = MessageStatus.EXPIRED

    # ── 查询 ──────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        """检查消息是否过期."""
        if not self.expires_at:
            return False
        try:
            expire_time = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > expire_time
        except (ValueError, TypeError):
            return False

    @property
    def is_from(self) -> str:
        """发送者 ID."""
        return self.sender.agent_id if self.sender else ""

    @property
    def is_to(self) -> str:
        """接收者 ID."""
        return self.receiver.agent_id if self.receiver else ""

    @property
    def age_seconds(self) -> float:
        """消息存在时间 (秒)."""
        try:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.now(timezone.utc) - created).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    # ── 序列化 ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "sender": self.sender.to_dict() if self.sender else None,
            "receiver": self.receiver.to_dict() if self.receiver else None,
            "message_type": self.message_type.value,
            "standard_type": self.standard_type.value if self.standard_type else None,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "processed_at": self.processed_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "is_expired": self.is_expired,
            "age_seconds": round(self.age_seconds, 2),
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        sender_name = self.sender.display_name if self.sender else "?"
        receiver_name = self.receiver.display_name if self.receiver else "ALL"
        return (
            f"AgentMessage({self.message_type.value} [{self.priority.name}] "
            f"{sender_name} → {receiver_name}: {self.subject[:40]})"
        )


# ═══════════════════════════════════════════════════════════════
# Message Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class MessageContext:
    """消息上下文 — 携带消息处理时的额外运行时信息.

    Attributes:
        session_id: 会话 ID
        cycle_id: 循环 ID
        trigger: 触发来源
        metrics_snapshot: 当前指标快照
        priority_override: 优先级覆盖
        timeout_seconds: 处理超时
        metadata: 扩展元数据
    """
    session_id: str = ""
    cycle_id: str = ""
    trigger: str = ""
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    priority_override: MessagePriority | None = None
    timeout_seconds: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_agent_identity(
    role: AgentRole,
    name: str = "",
    capabilities: list[str] | None = None,
    agent_id: str | None = None,
) -> AgentIdentity:
    """创建 Agent 身份."""
    return AgentIdentity(
        agent_id=agent_id or str(uuid.uuid4()),
        role=role,
        name=name or f"{role.value}_agent",
        capabilities=tuple(capabilities or []),
    )


def create_ua_agent_identity(name: str = "UA Agent") -> AgentIdentity:
    """创建 UA Agent 身份."""
    return create_agent_identity(
        role=AgentRole.UA,
        name=name,
        capabilities=[
            "meta_ads_analysis",
            "google_ads_analysis",
            "campaign_management",
            "budget_allocation",
            "roas_monitoring",
            "audience_targeting",
        ],
    )


def create_creative_agent_identity(name: str = "Creative Agent") -> AgentIdentity:
    """创建 Creative Agent 身份."""
    return create_agent_identity(
        role=AgentRole.CREATIVE,
        name=name,
        capabilities=[
            "creative_dna_analysis",
            "fatigue_detection",
            "variant_generation",
            "winner_identification",
            "creative_evolution",
            "clip_analysis",
        ],
    )


def create_monetization_agent_identity(name: str = "Monetization Agent") -> AgentIdentity:
    """创建 Monetization Agent 身份."""
    return create_agent_identity(
        role=AgentRole.MONETIZATION,
        name=name,
        capabilities=[
            "ltv_analysis",
            "payer_conversion",
            "iap_optimization",
            "iaa_waterfall",
            "revenue_attribution",
            "price_optimization",
        ],
    )


def create_supervisor_agent_identity(name: str = "Growth Supervisor") -> AgentIdentity:
    """创建 Supervisor Agent 身份."""
    return create_agent_identity(
        role=AgentRole.SUPERVISOR,
        name=name,
        capabilities=[
            "goal_decomposition",
            "task_orchestration",
            "conflict_resolution",
            "priority_management",
            "strategy_optimization",
            "performance_review",
        ],
    )


def create_product_agent_identity(name: str = "Product Manager Agent") -> AgentIdentity:
    """创建 Product Agent 身份 — 产品经理，从市场机会到产品方案.

    覆盖两大职责:
      1. 产品立项: PRD/GDD/Feature 排序/Roadmap 规划/Go-No-Go 评估
      2. 产品内增长: 留存分析/关卡设计/经济系统/活动优化
    """
    return create_agent_identity(
        role=AgentRole.PRODUCT,
        name=name,
        capabilities=[
            "prd_generation",
            "gdd_generation",
            "feature_prioritization",
            "roadmap_planning",
            "go_no_go_assessment",
            "retention_analysis",
            "level_design",
            "economy_balance",
            "event_optimization",
            "live_ops",
        ],
    )


def create_liveops_agent_identity(name: str = "LiveOps Agent") -> AgentIdentity:
    """创建 LiveOps Agent 身份 — 生命周期运营、回流活动设计."""
    return create_agent_identity(
        role=AgentRole.LIVEOPS,
        name=name,
        capabilities=[
            "churn_analysis",
            "winback_campaign_design",
            "lifecycle_segmentation",
            "retention_uplift",
            "player_re_engagement",
        ],
    )


def create_game_designer_agent_identity(name: str = "Game Designer Agent") -> AgentIdentity:
    """创建 Game Designer Agent 身份 — 从 GDD 细化为可执行设计.

    职责:
      1. 关卡设计: 关卡列表、难度曲线、通关条件
      2. 数值平衡: 货币产出/消耗、道具定价、奖励配置
      3. 系统规格: 战斗/合成/社交等系统的详细设计
      4. 难度曲线: 分阶段难度配置
    """
    return create_agent_identity(
        role=AgentRole.DESIGNER,
        name=name,
        capabilities=[
            "level_design",
            "economy_balance",
            "system_specification",
            "difficulty_curve",
            "content_configuration",
            "mechanic_design",
            "progression_tuning",
        ],
    )


def create_numerical_designer_agent_identity(name: str = "Numerical Designer Agent") -> AgentIdentity:
    """创建 Numerical Designer Agent 身份 — 运营阶段数值建模与调优.

    职责:
      1. 数值建模: LTV/CAC/ROI/回本周期预测
      2. 留存曲线: D1/D7/D30 留存拟合与预测
      3. 付费分析: 付费转化漏斗、ARPPU/ARPU 分层
      4. 数值调优: 基于 KPI 偏差给出参数调整建议
      5. A/B 测试: 数值方案对照实验设计
      6. 通胀监控: 货币产出/消耗监控与调控
    """
    return create_agent_identity(
        role=AgentRole.NUMERICAL,
        name=name,
        capabilities=[
            "ltv_cac_modeling",
            "retention_curve_modeling",
            "pay_conversion_analysis",
            "numerical_tuning",
            "ab_test_design",
            "inflation_monitoring",
            "revenue_forecasting",
            "monetization_optimization",
        ],
    )


def create_data_analyst_agent_identity(name: str = "Data Analyst Agent") -> AgentIdentity:
    """创建 Data Analyst Agent 身份 — 玩家行为分析与 BI 洞察.

    职责:
      1. 行为分析: 玩家活跃/会话/路径分析
      2. 漏斗归因: 安装→激活→留存→付费归因
      3. 留存预测: 基于历史数据预测未来留存
      4. 分群洞察: RFM/行为聚类分群
      5. BI 报表: 自动生成运营数据报表
      6. 异常检测: 指标异常波动检测与告警

    与 Numerical Designer 的边界:
      - Numerical Designer: 偏数值建模 (LTV/CAC 公式)
      - Data Analyst: 偏行为洞察 (玩家在做什么、为什么流失)
    """
    return create_agent_identity(
        role=AgentRole.DATA_ANALYST,
        name=name,
        capabilities=[
            "player_behavior_analysis",
            "funnel_attribution",
            "retention_prediction",
            "player_segmentation",
            "bi_reporting",
            "anomaly_detection",
            "cohort_analysis",
            "engagement_scoring",
        ],
    )


def create_player_support_agent_identity(name: str = "Player Support Agent") -> AgentIdentity:
    """创建 Player Support Agent 身份 — 玩家服务与舆情管理.

    职责:
      1. 工单处理: 自动分类/路由/回复玩家工单
      2. FAQ 管理: 知识库维护与智能检索
      3. 舆情监控: 评分/评论/社媒负面情绪监控
      4. VIP 服务: 高价值玩家专属服务
      5. 问题升级: 复杂问题升级到人工/产品团队
      6. 满意度分析: CSAT/NPS 跟踪与改进建议

    与 LiveOps Agent 的边界:
      - LiveOps: 偏活动设计 (召回活动/礼包配置)
      - Player Support: 偏用户沟通 (工单/FAQ/客诉)
    """
    return create_agent_identity(
        role=AgentRole.PLAYER_SUPPORT,
        name=name,
        capabilities=[
            "ticket_management",
            "faq_knowledge_base",
            "sentiment_monitoring",
            "vip_service",
            "issue_escalation",
            "satisfaction_analysis",
            "auto_reply",
            "crisis_response",
        ],
    )