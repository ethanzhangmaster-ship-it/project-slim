"""E13.3 Decision Engine Models — 增长决策引擎数据模型.

模块:
  - SignalType: 信号类型枚举
  - SignalSeverity: 信号严重度
  - GrowthSignal: 增长信号（核心输出）
  - SignalContext: 信号上下文
  - SignalBatch: 批量信号结果
  - OpportunityType: 机会类型枚举
  - OpportunityPriority: 机会优先级
  - GrowthOpportunity: 增长机会
  - OpportunityBatch: 批量机会结果
  - ExecutionActionType: 执行动作类型枚举
  - ExecutionStatus: 执行状态枚举
  - ExecutionAction: 执行动作
  - ExecutionResult: 执行结果
  - ExecutionBatch: 批量执行结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class SignalType(str, Enum):
    """增长信号类型."""
    # Creative
    CREATIVE_WINNER = "creative_winner"
    CREATIVE_FATIGUE = "creative_fatigue"
    CREATIVE_UNDERPERFORM = "creative_underperform"

    # Revenue
    ROAS_DROP = "roas_drop"
    LTV_UPSIDE = "ltv_upside"

    # UA
    SCALE_OPPORTUNITY = "scale_opportunity"
    BUDGET_WASTE = "budget_waste"

    # Monetization
    MONETIZATION_ISSUE = "monetization_issue"


class SignalSeverity(str, Enum):
    """信号严重度."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalCategory(str, Enum):
    """信号分类（用于分组和路由）."""
    CREATIVE = "creative"
    REVENUE = "revenue"
    UA = "ua"
    MONETIZATION = "monetization"


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthSignal:
    """增长信号 — 从事实数据中提取的可决策信号.

    Attributes:
        signal_id: 信号唯一标识
        signal_type: 信号类型
        entity_id: 关联实体ID (creative_id / campaign_id / product_id)
        entity_type: 实体类型
        severity: 严重程度
        confidence: 置信度 [0, 1]
        metrics: 关键指标快照
        thresholds: 触发阈值
        explanation: 信号解释
        rule_name: 触发规则名称
        source_vector_id: 来源 CreativeFitnessVector 的 creative_id (如有)
        timestamp: 信号生成时间
        metadata: 扩展元数据
    """
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_type: SignalType = SignalType.CREATIVE_WINNER
    entity_id: str = ""
    entity_type: str = "creative"
    category: SignalCategory = SignalCategory.CREATIVE

    severity: SignalSeverity = SignalSeverity.MEDIUM
    confidence: float = 0.0

    metrics: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    explanation: str = ""

    rule_name: str = ""
    source_vector_id: str = ""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "category": self.category.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "explanation": self.explanation,
            "rule_name": self.rule_name,
            "source_vector_id": self.source_vector_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class SignalContext:
    """信号上下文 — 承载信号检测所需的完整输入.

    Attributes:
        product_id: 产品ID
        date: 分析日期
        vectors: CreativeFitnessVector 列表
        attribution_edges: AttributionEdge 列表
        knowledge_graph: KnowledgeGraph 实例
        category_benchmarks: 分类基准数据
    """
    product_id: str = ""
    date: str = ""

    vectors: list[Any] = field(default_factory=list)
    attribution_edges: list[Any] = field(default_factory=list)
    knowledge_graph: Any = None

    category_benchmarks: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class SignalBatch:
    """批量信号结果 — 承载一次分析产生的所有信号.

    Attributes:
        batch_id: 批次ID
        product_id: 产品ID
        date: 分析日期
        signals: 信号列表
        total_vectors: 输入的向量总数
        total_signals: 生成的信号总数
        summary: 分类统计
        elapsed_ms: 耗时(毫秒)
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    date: str = ""

    signals: list[GrowthSignal] = field(default_factory=list)

    total_vectors: int = 0
    total_signals: int = 0

    summary: dict[str, int] = field(default_factory=dict)

    elapsed_ms: float = 0.0

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "product_id": self.product_id,
            "date": self.date,
            "total_vectors": self.total_vectors,
            "total_signals": self.total_signals,
            "summary": self.summary,
            "signals": [s.to_dict() for s in self.signals],
            "elapsed_ms": self.elapsed_ms,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Signal Type → Category Mapping
# ═══════════════════════════════════════════════════════════════

SIGNAL_CATEGORY_MAP: dict[SignalType, SignalCategory] = {
    SignalType.CREATIVE_WINNER: SignalCategory.CREATIVE,
    SignalType.CREATIVE_FATIGUE: SignalCategory.CREATIVE,
    SignalType.CREATIVE_UNDERPERFORM: SignalCategory.CREATIVE,
    SignalType.ROAS_DROP: SignalCategory.REVENUE,
    SignalType.LTV_UPSIDE: SignalCategory.REVENUE,
    SignalType.SCALE_OPPORTUNITY: SignalCategory.UA,
    SignalType.BUDGET_WASTE: SignalCategory.UA,
    SignalType.MONETIZATION_ISSUE: SignalCategory.MONETIZATION,
}


# ═══════════════════════════════════════════════════════════════
# E13.3.2 Opportunity Enums
# ═══════════════════════════════════════════════════════════════


class OpportunityType(str, Enum):
    """增长机会类型."""
    # Creative
    CREATIVE_SCALE = "creative_scale"
    CREATIVE_REFRESH = "creative_refresh"
    CREATIVE_MUTATION = "creative_mutation"

    # UA
    UA_SCALE = "ua_scale"
    UA_REBALANCE = "ua_rebalance"
    BUDGET_REDUCTION = "budget_reduction"

    # Monetization
    MONETIZATION_OPTIMIZE = "monetization_optimize"
    MONETIZATION_SCALE = "monetization_scale"


class OpportunityPriority(str, Enum):
    """机会优先级."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OpportunityStatus(str, Enum):
    """机会状态."""
    NEW = "new"
    ACCEPTED = "accepted"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"


# ═══════════════════════════════════════════════════════════════
# E13.3.2 Opportunity Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthOpportunity:
    """增长机会 — 从 GrowthSignal 转换而来的可执行机会.

    Attributes:
        opportunity_id: 机会唯一标识
        opportunity_type: 机会类型
        source_signal: 来源 GrowthSignal
        source_signal_id: 来源信号ID
        entity_id: 关联实体ID
        entity_type: 实体类型
        priority: 优先级
        confidence: 置信度 [0, 1]
        expected_gain: 预期收益 (ROAS 提升百分比)
        expected_gain_pct: 预期收益百分比
        actions: 建议行动列表
        recommended_params: 推荐参数 (如预算、出价)
        evidence: 证据摘要
        risk: 风险等级
        business_value: 业务价值权重
        score: 综合评分
        status: 机会状态
        explanation: 自然语言解释
        timestamp: 生成时间
        metadata: 扩展元数据
    """
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_type: OpportunityType = OpportunityType.CREATIVE_SCALE
    source_signal: GrowthSignal | None = None
    source_signal_id: str = ""
    entity_id: str = ""
    entity_type: str = "creative"

    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    confidence: float = 0.0

    expected_gain: float = 0.0
    expected_gain_pct: float = 0.0

    actions: list[str] = field(default_factory=list)
    recommended_params: dict[str, Any] = field(default_factory=dict)

    evidence: dict[str, Any] = field(default_factory=dict)
    risk: str = "medium"

    business_value: float = 1.0
    score: float = 0.0

    status: str = "new"

    explanation: str = ""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type.value,
            "source_signal_id": self.source_signal_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "priority": self.priority.value,
            "confidence": self.confidence,
            "expected_gain": self.expected_gain,
            "expected_gain_pct": self.expected_gain_pct,
            "actions": self.actions,
            "recommended_params": self.recommended_params,
            "evidence": self.evidence,
            "risk": self.risk,
            "business_value": self.business_value,
            "score": self.score,
            "status": self.status,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class OpportunityBatch:
    """批量机会结果 — 承载一次分析产生的所有机会.

    Attributes:
        batch_id: 批次ID
        product_id: 产品ID
        date: 分析日期
        opportunities: 机会列表
        total_signals: 输入信号数
        total_opportunities: 生成的机会数
        summary: 分类统计
        elapsed_ms: 耗时(毫秒)
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    date: str = ""

    opportunities: list[GrowthOpportunity] = field(default_factory=list)

    total_signals: int = 0
    total_opportunities: int = 0

    summary: dict[str, int] = field(default_factory=dict)

    elapsed_ms: float = 0.0

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "product_id": self.product_id,
            "date": self.date,
            "total_signals": self.total_signals,
            "total_opportunities": self.total_opportunities,
            "summary": self.summary,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "elapsed_ms": self.elapsed_ms,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Signal Type → Opportunity Type Mapping
# ═══════════════════════════════════════════════════════════════

SIGNAL_TO_OPPORTUNITY_MAP: dict[SignalType, list[OpportunityType]] = {
    SignalType.CREATIVE_WINNER: [
        OpportunityType.CREATIVE_SCALE,
        OpportunityType.CREATIVE_MUTATION,
    ],
    SignalType.CREATIVE_FATIGUE: [
        OpportunityType.CREATIVE_REFRESH,
        OpportunityType.CREATIVE_MUTATION,
    ],
    SignalType.CREATIVE_UNDERPERFORM: [
        OpportunityType.CREATIVE_REFRESH,
    ],
    SignalType.ROAS_DROP: [
        OpportunityType.BUDGET_REDUCTION,
        OpportunityType.UA_REBALANCE,
    ],
    SignalType.LTV_UPSIDE: [
        OpportunityType.MONETIZATION_SCALE,
        OpportunityType.UA_SCALE,
    ],
    SignalType.SCALE_OPPORTUNITY: [
        OpportunityType.UA_SCALE,
    ],
    SignalType.BUDGET_WASTE: [
        OpportunityType.BUDGET_REDUCTION,
        OpportunityType.UA_REBALANCE,
    ],
    SignalType.MONETIZATION_ISSUE: [
        OpportunityType.MONETIZATION_OPTIMIZE,
    ],
}


# ═══════════════════════════════════════════════════════════════
# E13.3.3 Execution Enums
# ═══════════════════════════════════════════════════════════════


class ExecutionActionType(str, Enum):
    """执行动作类型 — 将 Opportunity 映射为具体可执行操作."""
    # Creative
    CLONE_DNA = "clone_dna"
    GENERATE_VARIANTS = "generate_variants"
    MUTATE_HOOK = "mutate_hook"
    MUTATE_VISUAL = "mutate_visual"
    CREATE_POPULATION = "create_population"
    LAUNCH_AB_TEST = "launch_ab_test"
    REPLACE_CREATIVE = "replace_creative"

    # UA
    INCREASE_BUDGET = "increase_budget"
    REDUCE_BUDGET = "reduce_budget"
    DUPLICATE_CAMPAIGN = "duplicate_campaign"
    PAUSE_CAMPAIGN = "pause_campaign"
    EXPAND_TARGETING = "expand_targeting"
    REALLOCATE_BUDGET = "reallocate_budget"
    ADJUST_BID = "adjust_bid"

    # Monetization
    OPTIMIZE_PRICING = "optimize_pricing"
    OPTIMIZE_AD_PLACEMENT = "optimize_ad_placement"
    INCREASE_RETENTION = "increase_retention"
    CREATE_HIGH_VALUE_AUDIENCE = "create_high_value_audience"


class ExecutionStatus(str, Enum):
    """执行状态."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ApprovalLevel(str, Enum):
    """审批级别."""
    AUTO = "auto"           # 自动执行，无需审批
    LOW = "low"             # 低风险，自动审批
    MEDIUM = "medium"       # 中风险，需人工确认
    HIGH = "high"           # 高风险，需多层审批
    CRITICAL = "critical"   # 关键操作，需总监审批


# ═══════════════════════════════════════════════════════════════
# E13.3.3 Execution Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionAction:
    """执行动作 — 从 GrowthOpportunity 转换而来的具体可执行操作.

    Attributes:
        action_id: 动作唯一标识
        action_type: 动作类型
        source_opportunity_id: 来源机会ID
        source_opportunity_type: 来源机会类型
        entity_id: 目标实体ID
        entity_type: 目标实体类型
        priority: 优先级
        confidence: 置信度
        params: 执行参数
        approval_level: 审批级别
        status: 执行状态
        expected_impact: 预期影响描述
        rollback_action: 回滚动作 (如有)
        explanation: 自然语言解释
        timestamp: 生成时间
        metadata: 扩展元数据
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ExecutionActionType = ExecutionActionType.CLONE_DNA
    source_opportunity_id: str = ""
    source_opportunity_type: OpportunityType = OpportunityType.CREATIVE_SCALE
    entity_id: str = ""
    entity_type: str = "creative"

    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    confidence: float = 0.0

    params: dict[str, Any] = field(default_factory=dict)
    approval_level: ApprovalLevel = ApprovalLevel.AUTO
    status: ExecutionStatus = ExecutionStatus.PENDING

    expected_impact: str = ""
    rollback_action: ExecutionActionType | None = None

    explanation: str = ""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "source_opportunity_id": self.source_opportunity_id,
            "source_opportunity_type": self.source_opportunity_type.value,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "priority": self.priority.value,
            "confidence": self.confidence,
            "params": self.params,
            "approval_level": self.approval_level.value,
            "status": self.status.value,
            "expected_impact": self.expected_impact,
            "rollback_action": self.rollback_action.value if self.rollback_action else None,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionResult:
    """执行结果 — 单个 ExecutionAction 的执行结果.

    Attributes:
        result_id: 结果唯一标识
        action_id: 对应的执行动作ID
        action_type: 动作类型
        status: 执行状态
        success: 是否成功
        output: 执行输出数据
        error: 错误信息
        elapsed_ms: 执行耗时
        rolled_back: 是否已回滚
        timestamp: 执行时间
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    action_type: ExecutionActionType = ExecutionActionType.CLONE_DNA
    status: ExecutionStatus = ExecutionStatus.PENDING
    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0
    rolled_back: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "status": self.status.value,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "rolled_back": self.rolled_back,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionBatch:
    """批量执行结果 — 承载一次执行产生的所有结果.

    Attributes:
        batch_id: 批次ID
        product_id: 产品ID
        date: 执行日期
        actions: 执行动作列表
        results: 执行结果列表
        total_opportunities: 输入机会数
        total_actions: 生成的执行动作数
        total_success: 成功数
        total_failed: 失败数
        total_rolled_back: 回滚数
        summary: 分类统计
        elapsed_ms: 总耗时
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    date: str = ""

    actions: list[ExecutionAction] = field(default_factory=list)
    results: list[ExecutionResult] = field(default_factory=list)

    total_opportunities: int = 0
    total_actions: int = 0
    total_success: int = 0
    total_failed: int = 0
    total_rolled_back: int = 0

    summary: dict[str, int] = field(default_factory=dict)

    elapsed_ms: float = 0.0

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "product_id": self.product_id,
            "date": self.date,
            "total_opportunities": self.total_opportunities,
            "total_actions": self.total_actions,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "total_rolled_back": self.total_rolled_back,
            "summary": self.summary,
            "actions": [a.to_dict() for a in self.actions],
            "results": [r.to_dict() for r in self.results],
            "elapsed_ms": self.elapsed_ms,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# Opportunity Type → Execution Action Type Mapping
# ═══════════════════════════════════════════════════════════════

OPPORTUNITY_TO_ACTION_MAP: dict[OpportunityType, list[ExecutionActionType]] = {
    OpportunityType.CREATIVE_SCALE: [
        ExecutionActionType.CLONE_DNA,
        ExecutionActionType.GENERATE_VARIANTS,
        ExecutionActionType.LAUNCH_AB_TEST,
    ],
    OpportunityType.CREATIVE_REFRESH: [
        ExecutionActionType.MUTATE_HOOK,
        ExecutionActionType.MUTATE_VISUAL,
        ExecutionActionType.CREATE_POPULATION,
        ExecutionActionType.REPLACE_CREATIVE,
    ],
    OpportunityType.CREATIVE_MUTATION: [
        ExecutionActionType.MUTATE_HOOK,
        ExecutionActionType.MUTATE_VISUAL,
        ExecutionActionType.CREATE_POPULATION,
    ],
    OpportunityType.UA_SCALE: [
        ExecutionActionType.INCREASE_BUDGET,
        ExecutionActionType.DUPLICATE_CAMPAIGN,
        ExecutionActionType.EXPAND_TARGETING,
    ],
    OpportunityType.UA_REBALANCE: [
        ExecutionActionType.REALLOCATE_BUDGET,
        ExecutionActionType.ADJUST_BID,
    ],
    OpportunityType.BUDGET_REDUCTION: [
        ExecutionActionType.REDUCE_BUDGET,
        ExecutionActionType.PAUSE_CAMPAIGN,
        ExecutionActionType.REALLOCATE_BUDGET,
    ],
    OpportunityType.MONETIZATION_OPTIMIZE: [
        ExecutionActionType.OPTIMIZE_PRICING,
        ExecutionActionType.OPTIMIZE_AD_PLACEMENT,
    ],
    OpportunityType.MONETIZATION_SCALE: [
        ExecutionActionType.INCREASE_BUDGET,
        ExecutionActionType.INCREASE_RETENTION,
        ExecutionActionType.CREATE_HIGH_VALUE_AUDIENCE,
    ],
}