"""E13.5.1 Growth Intelligence Models — 决策智能层数据模型.

将 Reality Data + Memory Knowledge 融合为可执行的自主决策。

核心模型:
  - OpportunityType: 增长机会类型枚举
  - OpportunitySource: 机会来源枚举
  - DecisionStatus: 决策状态枚举
  - RiskLevel: 风险等级枚举
  - GrowthOpportunity: 增强型增长机会 (融合 Memory 上下文)
  - DecisionContext: 决策完整输入上下文
  - GrowthDecision: 最终决策对象
  - DecisionAction: 决策中的单个动作
  - DecisionResult: 决策执行结果
  - DecisionRecord: 决策历史记录

连接:
  E12 Reality → E13.4 Memory → E13.5 Intelligence → E13.6 Autonomous Runtime
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


class OpportunityType(str, Enum):
    """增长机会类型 — 系统可识别的增长机会分类."""
    CREATIVE_SCALE = "creative_scale"           # 素材放量
    CREATIVE_REFRESH = "creative_refresh"       # 素材刷新
    CREATIVE_MUTATE = "creative_mutate"         # 素材变异
    BUDGET_OPTIMIZATION = "budget_optimization"  # 预算优化
    BUDGET_REDISTRIBUTION = "budget_redistribution"  # 预算再分配
    AUDIENCE_EXPANSION = "audience_expansion"   # 受众扩展
    AUDIENCE_REFINE = "audience_refine"         # 受众精细化
    MONETIZATION_OPTIMIZATION = "monetization_optimization"  # 变现优化
    CAMPAIGN_RESTRUCTURE = "campaign_restructure"  # 广告系列重构
    BID_OPTIMIZATION = "bid_optimization"       # 出价优化
    EXPERIMENT_LAUNCH = "experiment_launch"     # 启动实验
    RISK_MITIGATION = "risk_mitigation"         # 风险缓解


class OpportunitySource(str, Enum):
    """机会来源 — 标记机会从哪个模块产生."""
    REALITY_INSIGHT = "reality_insight"     # 来自 E12 Reality 洞察
    PREDICTION = "prediction"               # 来自预测模型
    PATTERN_MEMORY = "pattern_memory"       # 来自已知模式匹配
    STRATEGY_MEMORY = "strategy_memory"     # 来自策略推荐
    SIGNAL_ENGINE = "signal_engine"         # 来自信号引擎
    MANUAL = "manual"                       # 人工创建


class DecisionStatus(str, Enum):
    """决策状态 — 决策生命周期."""
    DRAFT = "draft"               # 草稿
    PENDING_REVIEW = "pending_review"  # 待审核
    APPROVED = "approved"         # 已批准
    EXECUTING = "executing"       # 执行中
    EXECUTED = "executed"         # 已执行
    REJECTED = "rejected"         # 已拒绝
    BLOCKED = "blocked"           # 被风险控制拦截
    FAILED = "failed"             # 执行失败
    ROLLED_BACK = "rolled_back"   # 已回滚


class RiskLevel(str, Enum):
    """风险等级."""
    NONE = "none"           # 无风险
    LOW = "low"             # 低风险
    MEDIUM = "medium"       # 中风险
    HIGH = "high"           # 高风险
    CRITICAL = "critical"   # 致命风险


class DecisionPriority(str, Enum):
    """决策优先级."""
    CRITICAL = "critical"   # 紧急 (ROAS 骤降 / 预算浪费)
    HIGH = "high"           # 高 (素材疲劳 / 规模化机会)
    MEDIUM = "medium"       # 中 (优化机会)
    LOW = "low"             # 低 (实验性机会)


# ═══════════════════════════════════════════════════════════════
# Decision Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class CurrentMetrics:
    """当前指标快照 — 决策时的实时数据.

    Attributes:
        spend: 当前花费
        revenue: 当前收入
        roas: 当前 ROAS
        ctr: 当前点击率
        cpi: 当前单次安装成本
        ipm: 千次展示安装数
        frequency: 当前频次
        impressions: 展示量
        clicks: 点击量
        installs: 安装量
        payers: 付费用户数
        d7_ltv: D7 LTV
        d30_ltv: D30 LTV
        payer_rate: 付费率
        custom: 自定义指标
    """
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    ctr: float = 0.0
    cpi: float = 0.0
    ipm: float = 0.0
    frequency: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    payers: int = 0
    d7_ltv: float = 0.0
    d30_ltv: float = 0.0
    payer_rate: float = 0.0
    custom: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": round(self.roas, 4),
            "ctr": round(self.ctr, 4),
            "cpi": round(self.cpi, 4),
            "ipm": round(self.ipm, 4),
            "frequency": round(self.frequency, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "payers": self.payers,
            "d7_ltv": round(self.d7_ltv, 4),
            "d30_ltv": round(self.d30_ltv, 4),
            "payer_rate": round(self.payer_rate, 4),
            "custom": self.custom,
        }


@dataclass
class SignalSummary:
    """信号摘要 — 当前活跃信号的汇总.

    Attributes:
        active_signals: 活跃信号类型列表
        fatigue_detected: 是否检测到素材疲劳
        anomaly_detected: 是否检测到异常
        prediction: 预测结果 (如 fatigue_probability)
        trend: 趋势方向 (improving / stable / declining)
    """
    active_signals: list[str] = field(default_factory=list)
    fatigue_detected: bool = False
    anomaly_detected: bool = False
    prediction: dict[str, float] = field(default_factory=dict)
    trend: str = "stable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_signals": self.active_signals,
            "fatigue_detected": self.fatigue_detected,
            "anomaly_detected": self.anomaly_detected,
            "prediction": self.prediction,
            "trend": self.trend,
        }


@dataclass
class MemoryContext:
    """记忆上下文 — 决策时检索到的相关知识.

    Attributes:
        matched_patterns: 匹配到的 Pattern ID 列表
        recommended_strategies: 推荐的 Strategy ID 列表
        relevant_failures: 相关的 Failure Pattern ID 列表
        historical_success_rate: 类似场景历史成功率
        total_related_experiences: 相关经验总数
    """
    matched_patterns: list[str] = field(default_factory=list)
    recommended_strategies: list[str] = field(default_factory=list)
    relevant_failures: list[str] = field(default_factory=list)
    historical_success_rate: float = 0.0
    total_related_experiences: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched_patterns": self.matched_patterns,
            "recommended_strategies": self.recommended_strategies,
            "relevant_failures": self.relevant_failures,
            "historical_success_rate": self.historical_success_rate,
            "total_related_experiences": self.total_related_experiences,
        }


@dataclass
class DecisionContext:
    """决策上下文 — 完整决策输入.

    将 E12 Reality 数据、E13.3 信号、E13.4 Memory 知识汇总为决策输入。

    Attributes:
        context_id: 上下文唯一标识
        product_id: 产品 ID
        campaign_id: 广告系列 ID
        adset_id: 广告组 ID
        creative_id: 创意 ID
        date: 决策日期
        current_metrics: 实时指标
        signals: 信号摘要
        memory_context: 记忆检索结果
        creative_genome: 创意基因组信息 (如有)
        audience_segment: 受众分群
        platform: 投放平台
        metadata: 扩展元数据
    """
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    campaign_id: str = ""
    adset_id: str = ""
    creative_id: str = ""
    date: str = ""

    current_metrics: CurrentMetrics = field(default_factory=CurrentMetrics)
    signals: SignalSummary = field(default_factory=SignalSummary)
    memory_context: MemoryContext = field(default_factory=MemoryContext)

    creative_genome: dict[str, Any] = field(default_factory=dict)
    audience_segment: str = ""
    platform: str = "meta_ads"

    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "product_id": self.product_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "creative_id": self.creative_id,
            "date": self.date,
            "current_metrics": self.current_metrics.to_dict(),
            "signals": self.signals.to_dict(),
            "memory_context": self.memory_context.to_dict(),
            "creative_genome": self.creative_genome,
            "audience_segment": self.audience_segment,
            "platform": self.platform,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @property
    def has_metrics(self) -> bool:
        """是否有有效指标数据."""
        return self.current_metrics.impressions > 0

    @property
    def has_memory(self) -> bool:
        """是否有记忆上下文."""
        return self.memory_context.total_related_experiences > 0


# ═══════════════════════════════════════════════════════════════
# Growth Opportunity (E13.5 Enhanced)
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExpectedImpact:
    """预期影响 — 决策执行后的预期效果.

    Attributes:
        roas_change: ROAS 预期变化 (如 +0.15 表示 +15%)
        spend_change: 花费预期变化
        revenue_change: 收入预期变化
        ctr_change: CTR 预期变化
        cpi_change: CPI 预期变化
        confidence: 预期置信度
        timeframe_days: 预期生效时间 (天)
    """
    roas_change: float = 0.0
    spend_change: float = 0.0
    revenue_change: float = 0.0
    ctr_change: float = 0.0
    cpi_change: float = 0.0
    confidence: float = 0.0
    timeframe_days: int = 7

    def to_dict(self) -> dict[str, Any]:
        return {
            "roas_change": round(self.roas_change, 4),
            "spend_change": round(self.spend_change, 2),
            "revenue_change": round(self.revenue_change, 2),
            "ctr_change": round(self.ctr_change, 4),
            "cpi_change": round(self.cpi_change, 4),
            "confidence": round(self.confidence, 2),
            "timeframe_days": self.timeframe_days,
        }


@dataclass
class GrowthOpportunity:
    """增长机会 (E13.5 增强版) — 融合 Memory 上下文的可执行机会.

    比 E13.3 的 GrowthOpportunity 增加了:
      - 机会来源追踪 (OpportunitySource)
      - Memory 上下文 (关联 Pattern/Strategy/Failure)
      - 优先级 (DecisionPriority)
      - 紧急度 (urgency)
      - 多维度预期影响

    Attributes:
        opportunity_id: 机会唯一标识
        opportunity_type: 机会类型
        source: 机会来源
        product_id: 产品 ID
        campaign_id: 广告系列 ID
        creative_id: 创意 ID
        impact_score: 综合影响评分 [0, 1]
        confidence: 置信度 [0, 1]
        urgency: 紧急度 [0, 1]
        priority: 优先级
        reason: 机会描述
        recommended_action: 推荐动作类型
        expected_impact: 预期影响
        source_insight_id: 来源 Insight ID (如有)
        source_pattern_ids: 来源 Pattern ID 列表 (如有)
        source_strategy_id: 来源 Strategy ID (如有)
        related_failure_ids: 相关 Failure Pattern ID 列表
        detected_at: 发现时间
        metadata: 扩展元数据
    """
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_type: OpportunityType = OpportunityType.CREATIVE_SCALE
    source: OpportunitySource = OpportunitySource.REALITY_INSIGHT
    product_id: str = ""
    campaign_id: str = ""
    creative_id: str = ""

    impact_score: float = 0.0
    confidence: float = 0.0
    urgency: float = 0.0
    priority: DecisionPriority = DecisionPriority.MEDIUM

    reason: str = ""
    recommended_action: str = ""

    expected_impact: ExpectedImpact = field(default_factory=ExpectedImpact)

    source_insight_id: str = ""
    source_pattern_ids: list[str] = field(default_factory=list)
    source_strategy_id: str = ""
    related_failure_ids: list[str] = field(default_factory=list)

    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type.value,
            "source": self.source.value,
            "product_id": self.product_id,
            "campaign_id": self.campaign_id,
            "creative_id": self.creative_id,
            "impact_score": round(self.impact_score, 4),
            "confidence": round(self.confidence, 2),
            "urgency": round(self.urgency, 2),
            "priority": self.priority.value,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "expected_impact": self.expected_impact.to_dict(),
            "source_insight_id": self.source_insight_id,
            "source_pattern_ids": self.source_pattern_ids,
            "source_strategy_id": self.source_strategy_id,
            "related_failure_ids": self.related_failure_ids,
            "detected_at": self.detected_at,
            "metadata": self.metadata,
        }

    @property
    def is_high_priority(self) -> bool:
        """是否为高优先级机会."""
        return self.priority in {DecisionPriority.CRITICAL, DecisionPriority.HIGH}

    @property
    def is_actionable(self) -> bool:
        """是否可执行."""
        return self.confidence >= 0.6 and self.impact_score >= 0.3

    def compute_priority(self) -> None:
        """根据 impact_score 和 urgency 自动计算优先级."""
        score = self.impact_score * 0.6 + self.urgency * 0.4
        if score >= 0.8:
            self.priority = DecisionPriority.CRITICAL
        elif score >= 0.6:
            self.priority = DecisionPriority.HIGH
        elif score >= 0.4:
            self.priority = DecisionPriority.MEDIUM
        else:
            self.priority = DecisionPriority.LOW


# ═══════════════════════════════════════════════════════════════
# Decision Action
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionAction:
    """决策动作 — 决策中的单个执行动作.

    Attributes:
        action_id: 动作唯一标识
        action_type: 动作类型
        target_entity_id: 目标实体 ID
        target_entity_type: 目标实体类型 (creative / campaign / adset)
        params: 动作参数
        order: 执行顺序
        expected_impact: 该动作的预期影响
        approval_level: 审批级别 (auto / manual / blocked)
        timeout_seconds: 超时时间
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    target_entity_id: str = ""
    target_entity_type: str = "creative"
    params: dict[str, Any] = field(default_factory=dict)
    order: int = 1
    expected_impact: dict[str, float] = field(default_factory=dict)
    approval_level: str = "auto"
    timeout_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_entity_id": self.target_entity_id,
            "target_entity_type": self.target_entity_type,
            "params": self.params,
            "order": self.order,
            "expected_impact": self.expected_impact,
            "approval_level": self.approval_level,
            "timeout_seconds": self.timeout_seconds,
        }


# ═══════════════════════════════════════════════════════════════
# Growth Decision
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthDecision:
    """增长决策 — 最终决策对象.

    将 Opportunity → Strategy → Risk Check → Decision 的完整链路打包。

    Attributes:
        decision_id: 决策唯一标识
        context_id: 关联的决策上下文 ID
        opportunity_id: 关联的机会 ID
        objective: 决策目标 (如 increase_ROAS / scale_spend / recover_decay)
        status: 决策状态
        selected_strategy_id: 选中的策略 ID
        actions: 决策动作列表
        confidence: 决策置信度 [0, 1]
        risk_score: 风险评分 [0, 1] (越高越危险)
        risk_level: 风险等级
        expected_impact: 预期影响
        reasoning: 决策理由
        failure_warnings: 失败警告列表
        requires_approval: 是否需要人工审批
        created_at: 创建时间
        executed_at: 执行时间
        metadata: 扩展元数据
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = ""
    opportunity_id: str = ""
    objective: str = ""
    status: DecisionStatus = DecisionStatus.DRAFT

    selected_strategy_id: str = ""
    actions: list[DecisionAction] = field(default_factory=list)

    confidence: float = 0.0
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.NONE

    expected_impact: ExpectedImpact = field(default_factory=ExpectedImpact)

    reasoning: str = ""
    failure_warnings: list[str] = field(default_factory=list)
    requires_approval: bool = False

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "context_id": self.context_id,
            "opportunity_id": self.opportunity_id,
            "objective": self.objective,
            "status": self.status.value,
            "selected_strategy_id": self.selected_strategy_id,
            "actions": [a.to_dict() for a in self.actions],
            "confidence": round(self.confidence, 2),
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level.value,
            "expected_impact": self.expected_impact.to_dict(),
            "reasoning": self.reasoning,
            "failure_warnings": self.failure_warnings,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "metadata": self.metadata,
        }

    @property
    def is_approved(self) -> bool:
        return self.status == DecisionStatus.APPROVED

    @property
    def is_executable(self) -> bool:
        """是否可执行 — 已批准且未被风险拦截."""
        return self.status in {DecisionStatus.APPROVED, DecisionStatus.PENDING_REVIEW} and not self.is_blocked

    @property
    def is_blocked(self) -> bool:
        """是否被风险拦截."""
        return self.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH} and self.requires_approval

    @property
    def action_count(self) -> int:
        return len(self.actions)

    def approve(self) -> None:
        """批准决策."""
        if self.status == DecisionStatus.DRAFT:
            self.status = DecisionStatus.APPROVED

    def reject(self, reason: str = "") -> None:
        """拒绝决策."""
        self.status = DecisionStatus.REJECTED
        if reason:
            self.reasoning = reason

    def block(self, reason: str = "") -> None:
        """风险拦截."""
        self.status = DecisionStatus.BLOCKED
        self.risk_level = RiskLevel.CRITICAL
        if reason:
            self.failure_warnings.append(reason)

    def mark_executed(self) -> None:
        """标记已执行."""
        self.status = DecisionStatus.EXECUTED
        self.executed_at = datetime.now(timezone.utc).isoformat()

    def compute_risk_level(self) -> None:
        """根据 risk_score 自动计算风险等级."""
        if self.risk_score >= 0.8:
            self.risk_level = RiskLevel.CRITICAL
            self.requires_approval = True
        elif self.risk_score >= 0.6:
            self.risk_level = RiskLevel.HIGH
            self.requires_approval = True
        elif self.risk_score >= 0.4:
            self.risk_level = RiskLevel.MEDIUM
        elif self.risk_score >= 0.2:
            self.risk_level = RiskLevel.LOW
        else:
            self.risk_level = RiskLevel.NONE


# ═══════════════════════════════════════════════════════════════
# Decision Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionResult:
    """决策结果 — 决策执行后的反馈.

    Attributes:
        result_id: 结果唯一标识
        decision_id: 关联的决策 ID
        status: 执行状态
        success: 是否成功
        actual_metrics: 执行后实际指标
        metrics_delta: 指标变化 (vs 执行前)
        error_message: 错误信息
        rollback_performed: 是否已回滚
        executed_at: 执行时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    status: DecisionStatus = DecisionStatus.EXECUTED
    success: bool = False
    actual_metrics: CurrentMetrics = field(default_factory=CurrentMetrics)
    metrics_delta: dict[str, float] = field(default_factory=dict)
    error_message: str = ""
    rollback_performed: bool = False
    executed_at: str = ""
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "decision_id": self.decision_id,
            "status": self.status.value,
            "success": self.success,
            "actual_metrics": self.actual_metrics.to_dict(),
            "metrics_delta": self.metrics_delta,
            "error_message": self.error_message,
            "rollback_performed": self.rollback_performed,
            "executed_at": self.executed_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Decision Record
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionRecord:
    """决策记录 — 完整决策历史记录.

    Attributes:
        record_id: 记录唯一标识
        decision: 决策对象
        result: 执行结果
        context: 决策上下文
        opportunity: 触发机会
        created_at: 记录时间
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: GrowthDecision = field(default_factory=GrowthDecision)
    result: DecisionResult | None = None
    context: DecisionContext | None = None
    opportunity: GrowthOpportunity | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "decision": self.decision.to_dict(),
            "result": self.result.to_dict() if self.result else None,
            "context": self.context.to_dict() if self.context else None,
            "opportunity": self.opportunity.to_dict() if self.opportunity else None,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# E13.5.3 Strategy Selector Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class StrategyCandidate:
    """策略候选 — 一个候选策略及其评分.

    连接 Opportunity → StrategyMemory → 候选策略。

    Attributes:
        strategy_id: 策略唯一标识
        strategy_name: 策略名称
        strategy: GrowthStrategyPattern 实例 (序列化用 dict)
        match_score: 机会匹配度 [0, 1]
        historical_score: 历史成功率加权 [0, 1]
        confidence_score: 策略置信度 [0, 1]
        risk_score: 风险评分 [0, 1] (越高越危险)
        final_score: 最终综合评分 [0, 1]
        reason: 选择理由
        failure_warnings: 失败记忆警告
    """
    strategy_id: str = ""
    strategy_name: str = ""
    strategy: dict[str, Any] = field(default_factory=dict)
    match_score: float = 0.0
    historical_score: float = 0.0
    confidence_score: float = 0.0
    risk_score: float = 0.0
    final_score: float = 0.0
    reason: str = ""
    failure_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy": self.strategy,
            "match_score": round(self.match_score, 4),
            "historical_score": round(self.historical_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "risk_score": round(self.risk_score, 4),
            "final_score": round(self.final_score, 4),
            "reason": self.reason,
            "failure_warnings": self.failure_warnings,
        }

    @property
    def is_viable(self) -> bool:
        """是否可行 (final_score >= 0.5 且 risk_score < 0.8)."""
        return self.final_score >= 0.5 and self.risk_score < 0.8

    @property
    def is_blocked(self) -> bool:
        """是否被风险拦截."""
        return self.risk_score >= 0.8


@dataclass
class StrategySelection:
    """策略选择 — 最终策略选择结果.

    Attributes:
        selection_id: 选择唯一标识
        opportunity_id: 关联的机会 ID
        selected_strategy_id: 选中的策略 ID
        selected_strategy: 选中的策略详情 (序列化)
        alternatives: 备选策略列表
        decision_confidence: 决策置信度 [0, 1]
        selection_reason: 选择理由
        risk_warnings: 风险警告
        requires_approval: 是否需要人工审批
        created_at: 创建时间
    """
    selection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str = ""
    selected_strategy_id: str = ""
    selected_strategy: dict[str, Any] = field(default_factory=dict)
    alternatives: list[StrategyCandidate] = field(default_factory=list)
    decision_confidence: float = 0.0
    selection_reason: str = ""
    risk_warnings: list[str] = field(default_factory=list)
    requires_approval: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _best_candidate: StrategyCandidate | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "opportunity_id": self.opportunity_id,
            "selected_strategy_id": self.selected_strategy_id,
            "selected_strategy": self.selected_strategy,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "decision_confidence": round(self.decision_confidence, 4),
            "selection_reason": self.selection_reason,
            "risk_warnings": self.risk_warnings,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
        }

    @property
    def has_selection(self) -> bool:
        """是否有有效选择."""
        return bool(self.selected_strategy_id)

    @property
    def alternative_count(self) -> int:
        return len(self.alternatives)

    def get_top_alternative(self) -> StrategyCandidate | None:
        return self.alternatives[0] if self.alternatives else None