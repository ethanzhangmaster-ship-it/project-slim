"""E13.4 Growth Memory Models — 增长记忆数据模型.

模块:
  E13.4.1 Experience Store:
    - ExperienceContext: 决策上下文
    - ExperienceOutcome: 执行结果
    - GrowthExperience: 完整经验记录
    - ExperienceQuery: 经验查询条件
    - ExperienceStats: 经验统计聚合

  E13.4.2 Pattern Memory:
    - PatternCondition: 模式触发条件
    - PatternAction: 模式推荐动作
    - PatternPerformance: 模式表现统计
    - PatternMemory: 完整增长模式
    - PatternQuery: 模式查询条件
    - PatternStats: 模式统计聚合
    - PatternMiningDimension: 挖掘维度枚举
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


class ExperienceCategory(str, Enum):
    """经验类别."""
    CREATIVE = "creative"
    UA = "ua"
    REVENUE = "revenue"
    MONETIZATION = "monetization"


class ExperienceOutcomeLevel(str, Enum):
    """经验结果等级."""
    STRONG_SUCCESS = "strong_success"     # 超出预期
    SUCCESS = "success"                   # 达成预期
    NEUTRAL = "neutral"                   # 无明显影响
    FAILURE = "failure"                   # 未达预期
    STRONG_FAILURE = "strong_failure"     # 严重失败


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExperienceContext:
    """决策上下文 — 记录决策发生时的情况.

    Attributes:
        product_id: 产品ID
        date: 决策日期
        opportunity_type: 触发机会类型
        opportunity_id: 来源机会ID
        action_type: 执行动作类型
        entity_id: 目标实体ID
        entity_type: 目标实体类型
        market_conditions: 市场条件 (ROAS、CPI、CTR 等)
        trigger_signals: 触发信号列表
        dna_genes: 涉及的DNA基因 (如 hook, visual, gameplay)
        audience_segment: 受众分群
    """
    product_id: str = ""
    date: str = ""

    opportunity_type: str = ""
    opportunity_id: str = ""
    action_type: str = ""

    entity_id: str = ""
    entity_type: str = "creative"

    # 市场条件快照
    market_conditions: dict[str, float] = field(default_factory=dict)

    # 触发信号
    trigger_signals: list[str] = field(default_factory=list)

    # 创意基因 (如有)
    dna_genes: dict[str, Any] = field(default_factory=dict)

    # 受众信息
    audience_segment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "date": self.date,
            "opportunity_type": self.opportunity_type,
            "opportunity_id": self.opportunity_id,
            "action_type": self.action_type,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "market_conditions": self.market_conditions,
            "trigger_signals": self.trigger_signals,
            "dna_genes": self.dna_genes,
            "audience_segment": self.audience_segment,
        }


@dataclass
class ExperienceOutcome:
    """执行结果 — 记录决策执行后的实际效果.

    Attributes:
        success: 是否成功
        outcome_level: 结果等级
        metrics_before: 执行前指标
        metrics_after: 执行后指标
        metrics_delta: 指标变化 (after - before)
        actual_impact: 实际影响描述
        actual_reward: 实际奖励分数 [0, 1]
        error: 错误信息 (如有)
        rolled_back: 是否已回滚
        time_to_outcome_hours: 结果显现时间 (小时)
    """
    success: bool = False
    outcome_level: ExperienceOutcomeLevel = ExperienceOutcomeLevel.NEUTRAL

    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    metrics_delta: dict[str, float] = field(default_factory=dict)

    actual_impact: str = ""
    actual_reward: float = 0.0

    error: str = ""
    rolled_back: bool = False

    time_to_outcome_hours: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "outcome_level": self.outcome_level.value,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "metrics_delta": self.metrics_delta,
            "actual_impact": self.actual_impact,
            "actual_reward": self.actual_reward,
            "error": self.error,
            "rolled_back": self.rolled_back,
            "time_to_outcome_hours": self.time_to_outcome_hours,
        }


@dataclass
class GrowthExperience:
    """增长经验 — 完整记录一次决策→执行→结果的经验.

    这是 E13.4.1 Experience Store 的核心存储单元。

    Attributes:
        experience_id: 经验唯一标识
        context: 决策上下文
        action_id: 执行动作ID
        action_type: 执行动作类型
        action_params: 执行参数
        outcome: 执行结果
        reward: 综合奖励分数 [0, 1]
        confidence: 决策时的置信度
        category: 经验类别
        tags: 标签 (用于检索)
        timestamp: 记录时间
        metadata: 扩展元数据
    """
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: ExperienceContext = field(default_factory=ExperienceContext)
    action_id: str = ""
    action_type: str = ""
    action_params: dict[str, Any] = field(default_factory=dict)
    outcome: ExperienceOutcome = field(default_factory=ExperienceOutcome)
    reward: float = 0.0
    confidence: float = 0.0
    category: ExperienceCategory = ExperienceCategory.CREATIVE
    tags: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """自动计算 reward 和 category."""
        if self.reward == 0.0 and self.outcome.actual_reward > 0:
            self.reward = self.outcome.actual_reward
        if self.category == ExperienceCategory.CREATIVE:
            cat = self._infer_category()
            if cat is not None:
                self.category = cat

    def _infer_category(self) -> ExperienceCategory | None:
        """从 action_type 推断类别."""
        creative_actions = {
            "clone_dna", "generate_variants", "mutate_hook", "mutate_visual",
            "create_population", "launch_ab_test", "replace_creative",
        }
        ua_actions = {
            "increase_budget", "reduce_budget", "duplicate_campaign",
            "pause_campaign", "expand_targeting", "reallocate_budget", "adjust_bid",
        }
        revenue_actions = {
            "optimize_pricing", "optimize_ad_placement", "increase_retention",
            "create_high_value_audience",
        }
        if self.action_type in creative_actions:
            return ExperienceCategory.CREATIVE
        elif self.action_type in ua_actions:
            return ExperienceCategory.UA
        elif self.action_type in revenue_actions:
            return ExperienceCategory.REVENUE
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "context": self.context.to_dict(),
            "action_id": self.action_id,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "outcome": self.outcome.to_dict(),
            "reward": self.reward,
            "confidence": self.confidence,
            "category": self.category.value,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def is_successful(self) -> bool:
        """是否成功经验."""
        return self.outcome.success and self.outcome.outcome_level in (
            ExperienceOutcomeLevel.STRONG_SUCCESS,
            ExperienceOutcomeLevel.SUCCESS,
        )

    def is_failure(self) -> bool:
        """是否失败经验."""
        return self.outcome.outcome_level in (
            ExperienceOutcomeLevel.FAILURE,
            ExperienceOutcomeLevel.STRONG_FAILURE,
        )


@dataclass
class ExperienceQuery:
    """经验查询条件 — 用于从 ExperienceStore 中检索经验.

    Attributes:
        action_types: 按动作类型过滤
        opportunity_types: 按机会类型过滤
        categories: 按类别过滤
        entity_id: 按实体ID过滤
        product_id: 按产品ID过滤
        date_from: 起始日期
        date_to: 截止日期
        min_reward: 最低奖励分数
        min_confidence: 最低置信度
        success_only: 仅成功经验
        failure_only: 仅失败经验
        tags: 按标签过滤
        limit: 返回数量上限
        sort_by: 排序字段 (reward, timestamp, confidence)
        sort_desc: 是否降序
    """
    action_types: list[str] = field(default_factory=list)
    opportunity_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    entity_id: str = ""
    product_id: str = ""
    date_from: str = ""
    date_to: str = ""
    min_reward: float = 0.0
    min_confidence: float = 0.0
    success_only: bool = False
    failure_only: bool = False
    tags: list[str] = field(default_factory=list)
    limit: int = 100
    sort_by: str = "reward"
    sort_desc: bool = True


@dataclass
class ExperienceStats:
    """经验统计 — 对经验库的聚合统计.

    Attributes:
        total_experiences: 总经验数
        total_success: 成功数
        total_failure: 失败数
        success_rate: 成功率
        avg_reward: 平均奖励
        avg_confidence: 平均置信度
        by_action_type: 按动作类型统计
        by_category: 按类别统计
        by_opportunity_type: 按机会类型统计
        top_actions: 成功率最高的动作
        worst_actions: 成功率最低的动作
        recent_trend: 最近趋势 (最近N次成功率)
    """
    total_experiences: int = 0
    total_success: int = 0
    total_failure: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_confidence: float = 0.0

    by_action_type: dict[str, dict[str, float]] = field(default_factory=dict)
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    by_opportunity_type: dict[str, dict[str, float]] = field(default_factory=dict)

    top_actions: list[dict[str, Any]] = field(default_factory=list)
    worst_actions: list[dict[str, Any]] = field(default_factory=list)

    recent_trend: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_experiences": self.total_experiences,
            "total_success": self.total_success,
            "total_failure": self.total_failure,
            "success_rate": self.success_rate,
            "avg_reward": self.avg_reward,
            "avg_confidence": self.avg_confidence,
            "by_action_type": self.by_action_type,
            "by_category": self.by_category,
            "by_opportunity_type": self.by_opportunity_type,
            "top_actions": self.top_actions,
            "worst_actions": self.worst_actions,
            "recent_trend": self.recent_trend,
        }


# ═══════════════════════════════════════════════════════════════
# E13.4.2 Pattern Memory Enums
# ═══════════════════════════════════════════════════════════════


class PatternMiningDimension(str, Enum):
    """模式挖掘维度 — 决定从哪些维度聚合经验."""
    OPPORTUNITY_ACTION = "opportunity_action"       # 机会类型 × 动作类型
    OPPORTUNITY_CATEGORY = "opportunity_category"   # 机会类型 × 类别
    ACTION_AUDIENCE = "action_audience"             # 动作类型 × 受众
    ACTION_DNA = "action_dna"                       # 动作类型 × DNA基因
    SIGNAL_ACTION = "signal_action"                 # 信号类型 × 动作类型
    FULL_CONTEXT = "full_context"                   # 全上下文组合


class PatternQuality(str, Enum):
    """模式质量等级."""
    STRONG = "strong"           # 大样本 + 高成功率
    RELIABLE = "reliable"       # 中等样本 + 高成功率
    EMERGING = "emerging"       # 小样本 + 高成功率
    WEAK = "weak"               # 低成功率
    AVOID = "avoid"             # 高失败率 (failure pattern)


# ═══════════════════════════════════════════════════════════════
# E13.4.2 Pattern Memory Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class PatternCondition:
    """模式触发条件 — 描述什么情况下该模式有效.

    Attributes:
        opportunity_type: 机会类型
        action_type: 动作类型
        category: 经验类别
        audience_segment: 受众分群
        dna_genes: DNA基因条件 (如 {"hook": "rescue"})
        signal_types: 触发信号类型
        market_conditions: 市场条件阈值 (如 {"roas": (0.5, 2.0)})
        product_category: 产品类别 (如 "merge")
        entity_type: 实体类型
    """
    opportunity_type: str = ""
    action_type: str = ""
    category: str = ""
    audience_segment: str = ""
    dna_genes: dict[str, Any] = field(default_factory=dict)
    signal_types: list[str] = field(default_factory=list)
    market_conditions: dict[str, tuple[float, float]] = field(default_factory=dict)
    product_category: str = ""
    entity_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "category": self.category,
            "audience_segment": self.audience_segment,
            "dna_genes": self.dna_genes,
            "signal_types": self.signal_types,
            "market_conditions": {k: list(v) for k, v in self.market_conditions.items()},
            "product_category": self.product_category,
            "entity_type": self.entity_type,
        }

    def dimension_key(self, dimension: PatternMiningDimension) -> str:
        """根据挖掘维度生成聚合键."""
        if dimension == PatternMiningDimension.OPPORTUNITY_ACTION:
            return f"{self.opportunity_type}|{self.action_type}"
        elif dimension == PatternMiningDimension.OPPORTUNITY_CATEGORY:
            return f"{self.opportunity_type}|{self.category}"
        elif dimension == PatternMiningDimension.ACTION_AUDIENCE:
            return f"{self.action_type}|{self.audience_segment}"
        elif dimension == PatternMiningDimension.ACTION_DNA:
            dna_key = "|".join(f"{k}={v}" for k, v in sorted(self.dna_genes.items()))
            return f"{self.action_type}|{dna_key}" if dna_key else self.action_type
        elif dimension == PatternMiningDimension.SIGNAL_ACTION:
            sig_key = "|".join(sorted(self.signal_types))
            return f"{sig_key}|{self.action_type}" if sig_key else self.action_type
        elif dimension == PatternMiningDimension.FULL_CONTEXT:
            parts = [
                self.opportunity_type,
                self.action_type,
                self.category,
                self.audience_segment,
            ]
            parts += [f"{k}={v}" for k, v in sorted(self.dna_genes.items())]
            parts += sorted(self.signal_types)
            return "|".join(p for p in parts if p)
        return ""


@dataclass
class PatternAction:
    """模式推荐动作 — 该模式建议执行什么.

    Attributes:
        action_type: 推荐动作类型
        params_template: 参数模板 (如 {"clone_hook": True})
        expected_impact: 预期影响描述
        approval_level: 建议审批级别
    """
    action_type: str = ""
    params_template: dict[str, Any] = field(default_factory=dict)
    expected_impact: str = ""
    approval_level: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "params_template": self.params_template,
            "expected_impact": self.expected_impact,
            "approval_level": self.approval_level,
        }


@dataclass
class PatternPerformance:
    """模式表现统计 — 该模式的历史表现.

    Attributes:
        samples: 样本数
        success_count: 成功数
        success_rate: 成功率 [0, 1]
        avg_reward: 平均奖励
        avg_confidence: 平均置信度
        avg_metrics_delta: 平均指标变化
        std_reward: 奖励标准差
        quality: 模式质量等级
        first_seen: 首次出现时间
        last_seen: 最近出现时间
        trend: 趋势 (最近N次成功率)
    """
    samples: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_confidence: float = 0.0
    avg_metrics_delta: dict[str, float] = field(default_factory=dict)
    std_reward: float = 0.0
    quality: PatternQuality = PatternQuality.WEAK
    first_seen: str = ""
    last_seen: str = ""
    trend: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
            "avg_reward": self.avg_reward,
            "avg_confidence": self.avg_confidence,
            "avg_metrics_delta": self.avg_metrics_delta,
            "std_reward": self.std_reward,
            "quality": self.quality.value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "trend": self.trend,
        }


@dataclass
class PatternMemory:
    """增长模式 — 从经验中挖掘的可复用增长规律.

    这是 E13.4.2 Pattern Memory 的核心存储单元。

    Attributes:
        pattern_id: 模式唯一标识
        dimension: 挖掘维度
        condition: 触发条件
        action: 推荐动作
        performance: 历史表现
        score: 综合评分 (sample_size × success_rate × reward × confidence)
        confidence: 模式置信度 [0, 1]
        tags: 标签
        source_experience_ids: 来源经验ID列表
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dimension: PatternMiningDimension = PatternMiningDimension.OPPORTUNITY_ACTION
    condition: PatternCondition = field(default_factory=PatternCondition)
    action: PatternAction = field(default_factory=PatternAction)
    performance: PatternPerformance = field(default_factory=PatternPerformance)
    score: float = 0.0
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    source_experience_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_score(self) -> float:
        """计算综合评分.

        Pattern Score = sample_factor × success_rate × avg_reward × confidence_weight

        样本因子: 使用对数平滑，避免大样本过度主导
        """
        perf = self.performance
        if perf.samples == 0:
            return 0.0

        import math
        # 样本因子: 对数平滑，10 样本 ~0.5, 100 样本 ~0.7, 1000 样本 ~0.85
        sample_factor = min(1.0, math.log(perf.samples + 1) / math.log(100))
        # 置信度权重: 成功率越高越可信
        confidence_weight = 0.5 + 0.5 * perf.success_rate
        # 综合评分
        self.score = round(
            sample_factor * perf.success_rate * max(perf.avg_reward, 0.01) * confidence_weight,
            4,
        )
        self.confidence = round(
            sample_factor * perf.success_rate,
            4,
        )
        return self.score

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "dimension": self.dimension.value,
            "condition": self.condition.to_dict(),
            "action": self.action.to_dict(),
            "performance": self.performance.to_dict(),
            "score": self.score,
            "confidence": self.confidence,
            "tags": self.tags,
            "source_experience_ids": self.source_experience_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def is_actionable(self, min_samples: int = 5, min_success_rate: float = 0.5) -> bool:
        """是否可执行."""
        return (
            self.performance.samples >= min_samples
            and self.performance.success_rate >= min_success_rate
        )

    def is_avoid_pattern(self, failure_threshold: float = 0.7) -> bool:
        """是否应避免的模式 (高失败率)."""
        return (
            self.performance.samples >= 3
            and (1.0 - self.performance.success_rate) >= failure_threshold
        )


@dataclass
class PatternQuery:
    """模式查询条件 — 用于从 PatternStore 中检索模式.

    Attributes:
        opportunity_types: 按机会类型过滤
        action_types: 按动作类型过滤
        categories: 按类别过滤
        dimensions: 按挖掘维度过滤
        audience_segment: 按受众过滤
        dna_genes: 按DNA基因过滤
        signal_types: 按信号类型过滤
        min_samples: 最低样本数
        min_success_rate: 最低成功率
        min_score: 最低评分
        actionable_only: 仅可执行模式
        avoid_only: 仅应避免模式
        quality_levels: 按质量等级过滤
        tags: 按标签过滤
        limit: 返回数量上限
        sort_by: 排序字段 (score, samples, success_rate, avg_reward)
        sort_desc: 是否降序
    """
    opportunity_types: list[str] = field(default_factory=list)
    action_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    audience_segment: str = ""
    dna_genes: dict[str, Any] = field(default_factory=dict)
    signal_types: list[str] = field(default_factory=list)
    min_samples: int = 0
    min_success_rate: float = 0.0
    min_score: float = 0.0
    actionable_only: bool = False
    avoid_only: bool = False
    quality_levels: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    limit: int = 100
    sort_by: str = "score"
    sort_desc: bool = True


@dataclass
class PatternStats:
    """模式统计 — 对模式库的聚合统计.

    Attributes:
        total_patterns: 总模式数
        total_actionable: 可执行模式数
        total_avoid: 应避免模式数
        by_dimension: 按维度统计
        by_quality: 按质量等级统计
        by_category: 按类别统计
        top_patterns: 最高评分模式
        avoid_patterns: 应避免模式
        avg_score: 平均评分
        avg_samples: 平均样本数
    """
    total_patterns: int = 0
    total_actionable: int = 0
    total_avoid: int = 0
    by_dimension: dict[str, dict[str, float]] = field(default_factory=dict)
    by_quality: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    top_patterns: list[dict[str, Any]] = field(default_factory=list)
    avoid_patterns: list[dict[str, Any]] = field(default_factory=list)
    avg_score: float = 0.0
    avg_samples: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_patterns": self.total_patterns,
            "total_actionable": self.total_actionable,
            "total_avoid": self.total_avoid,
            "by_dimension": self.by_dimension,
            "by_quality": self.by_quality,
            "by_category": self.by_category,
            "top_patterns": self.top_patterns,
            "avoid_patterns": self.avoid_patterns,
            "avg_score": self.avg_score,
            "avg_samples": self.avg_samples,
        }