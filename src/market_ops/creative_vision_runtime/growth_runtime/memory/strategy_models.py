"""E13.4.3 Strategy Memory Models — 增长策略记忆数据模型.

Strategy Memory 回答: "面对一个增长问题，应该采用什么完整方案？"

与 Pattern Memory 的区别:
  - Pattern: 单步动作的规律 (什么情况下什么动作有效？)
  - Strategy: 多步方案 (面对问题应该执行什么完整流程？)

核心模型:
  - StrategyTriggerCondition: 策略触发条件
  - StrategyStep: 策略步骤 (可引用 PatternMemory)
  - StrategyPerformance: 策略历史表现
  - GrowthStrategyPattern: 完整增长策略 (Playbook)
  - StrategyQuery: 策略查询条件
  - StrategyStats: 策略统计聚合
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


class StrategyCategory(str, Enum):
    """策略类别."""
    CREATIVE_REVIVAL = "creative_revival"       # 创意复活
    CREATIVE_SCALE = "creative_scale"           # 创意放大
    ROAS_RECOVERY = "roas_recovery"             # ROAS 恢复
    BUDGET_OPTIMIZATION = "budget_optimization" # 预算优化
    AUDIENCE_EXPANSION = "audience_expansion"   # 受众扩展
    NEW_LAUNCH = "new_launch"                   # 新品发布
    GENERAL = "general"                         # 通用


class StrategyQuality(str, Enum):
    """策略质量等级."""
    PROVEN = "proven"           # 大规模验证 (100+ samples)
    RELIABLE = "reliable"       # 中等验证 (30+ samples)
    EMERGING = "emerging"       # 初步验证 (10+ samples)
    EXPERIMENTAL = "experimental"  # 少量验证 (3+ samples)
    UNTESTED = "untested"       # 未验证


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class StrategyTriggerCondition:
    """策略触发条件 — 描述什么场景下应该使用该策略.

    Attributes:
        scenario: 场景描述 (如 "ROAS dropping", "Creative fatigue")
        opportunity_type: 关联机会类型
        signal_types: 触发信号类型
        metrics_conditions: 指标条件阈值 (如 {"roas": ("<", 0.8)})
        audience_segment: 目标受众
        product_category: 产品类别
        min_confidence: 触发所需最低置信度
    """
    scenario: str = ""
    opportunity_type: str = ""
    signal_types: list[str] = field(default_factory=list)
    metrics_conditions: dict[str, tuple[str, float]] = field(default_factory=dict)
    audience_segment: str = ""
    product_category: str = ""
    min_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "opportunity_type": self.opportunity_type,
            "signal_types": self.signal_types,
            "metrics_conditions": {k: list(v) for k, v in self.metrics_conditions.items()},
            "audience_segment": self.audience_segment,
            "product_category": self.product_category,
            "min_confidence": self.min_confidence,
        }

    def matches_opportunity(
        self,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> bool:
        """检查是否匹配给定机会."""
        if self.opportunity_type and opportunity_type and self.opportunity_type != opportunity_type:
            return False
        if signal_types and self.signal_types:
            if not any(s in self.signal_types for s in signal_types):
                return False
        if self.audience_segment and audience_segment and self.audience_segment != audience_segment:
            return False
        if self.product_category and product_category and self.product_category != product_category:
            return False
        return True


@dataclass
class StrategyStep:
    """策略步骤 — 策略中的一个执行步骤.

    Attributes:
        order: 执行顺序 (1-based)
        action_type: 动作类型
        action_params: 动作参数模板
        pattern_id: 关联的 PatternMemory ID (可选，用于引用已验证模式)
        expected_impact: 预期影响描述
        approval_level: 建议审批级别 (auto / manual / review)
        rollback_action: 回滚动作 (如有)
        timeout_hours: 步骤超时时间 (小时)
    """
    order: int = 1
    action_type: str = ""
    action_params: dict[str, Any] = field(default_factory=dict)
    pattern_id: str = ""
    expected_impact: str = ""
    approval_level: str = "auto"
    rollback_action: str = ""
    timeout_hours: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "pattern_id": self.pattern_id,
            "expected_impact": self.expected_impact,
            "approval_level": self.approval_level,
            "rollback_action": self.rollback_action,
            "timeout_hours": self.timeout_hours,
        }


@dataclass
class StrategyPerformance:
    """策略表现统计 — 该策略的历史执行效果.

    Attributes:
        total_executions: 总执行次数
        successful_executions: 成功执行次数
        success_rate: 成功率 [0, 1]
        avg_reward: 平均奖励
        avg_roas_change: 平均 ROAS 变化
        avg_duration_hours: 平均执行耗时
        quality: 策略质量等级
        first_seen: 首次出现时间
        last_seen: 最近出现时间
        trend: 趋势 (最近N次成功率)
    """
    total_executions: int = 0
    successful_executions: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    avg_roas_change: float = 0.0
    avg_duration_hours: float = 0.0
    quality: StrategyQuality = StrategyQuality.UNTESTED
    first_seen: str = ""
    last_seen: str = ""
    trend: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "success_rate": self.success_rate,
            "avg_reward": self.avg_reward,
            "avg_roas_change": self.avg_roas_change,
            "avg_duration_hours": self.avg_duration_hours,
            "quality": self.quality.value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "trend": self.trend,
        }


@dataclass
class GrowthStrategyPattern:
    """增长策略模式 — 完整的增长打法 (Playbook).

    这是 E13.4.3 Strategy Memory 的核心存储单元。

    Attributes:
        strategy_id: 策略唯一标识
        name: 策略名称 (如 "Creative Revival Pipeline")
        category: 策略类别
        trigger: 触发条件
        steps: 执行步骤列表 (按 order 排序)
        performance: 历史表现
        score: 综合评分
        confidence: 策略置信度 [0, 1]
        source_experience_ids: 来源经验ID列表
        source_pattern_ids: 来源模式ID列表
        tags: 标签
        description: 策略描述
        prerequisites: 前置条件描述
        risks: 风险描述
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: StrategyCategory = StrategyCategory.GENERAL
    trigger: StrategyTriggerCondition = field(default_factory=StrategyTriggerCondition)
    steps: list[StrategyStep] = field(default_factory=list)
    performance: StrategyPerformance = field(default_factory=StrategyPerformance)
    score: float = 0.0
    confidence: float = 0.0
    source_experience_ids: list[str] = field(default_factory=list)
    source_pattern_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    prerequisites: str = ""
    risks: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """确保 steps 按 order 排序."""
        if self.steps:
            self.steps = sorted(self.steps, key=lambda s: s.order)

    def compute_score(self) -> float:
        """计算策略综合评分.

        Strategy Score = sample_factor × success_rate × avg_reward × step_bonus × confidence_weight

        step_bonus: 步骤越多越完整的策略有额外加分 (但单步策略不扣分)
        """
        perf = self.performance
        if perf.total_executions == 0:
            return 0.0

        import math
        # 样本因子: 对数平滑
        sample_factor = min(1.0, math.log(perf.total_executions + 1) / math.log(100))
        # 置信度权重
        confidence_weight = 0.5 + 0.5 * perf.success_rate
        # 步骤加分: 3+ 步策略 +10%
        step_bonus = 1.1 if len(self.steps) >= 3 else 1.0
        # 综合评分
        self.score = round(
            sample_factor * perf.success_rate * max(perf.avg_reward, 0.01)
            * confidence_weight * step_bonus,
            4,
        )
        self.confidence = round(sample_factor * perf.success_rate, 4)
        return self.score

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "category": self.category.value,
            "trigger": self.trigger.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "performance": self.performance.to_dict(),
            "score": self.score,
            "confidence": self.confidence,
            "source_experience_ids": self.source_experience_ids,
            "source_pattern_ids": self.source_pattern_ids,
            "tags": self.tags,
            "description": self.description,
            "prerequisites": self.prerequisites,
            "risks": self.risks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def is_actionable(self, min_executions: int = 3, min_success_rate: float = 0.5) -> bool:
        """是否可执行."""
        return (
            self.performance.total_executions >= min_executions
            and self.performance.success_rate >= min_success_rate
        )

    def is_proven(self) -> bool:
        """是否已被大规模验证."""
        return (
            self.performance.total_executions >= 100
            and self.performance.success_rate >= 0.7
        )

    def get_step_count(self) -> int:
        """获取步骤数."""
        return len(self.steps)

    def get_first_step(self) -> StrategyStep | None:
        """获取第一步."""
        return self.steps[0] if self.steps else None

    def get_approval_summary(self) -> dict[str, int]:
        """获取审批级别汇总."""
        summary: dict[str, int] = {}
        for step in self.steps:
            summary[step.approval_level] = summary.get(step.approval_level, 0) + 1
        return summary


@dataclass
class StrategyQuery:
    """策略查询条件 — 用于从 StrategyMemory 中检索策略.

    Attributes:
        scenario: 按场景过滤
        opportunity_types: 按机会类型过滤
        categories: 按策略类别过滤
        audience_segment: 按受众过滤
        product_category: 按产品类别过滤
        min_executions: 最低执行次数
        min_success_rate: 最低成功率
        min_score: 最低评分
        actionable_only: 仅可执行策略
        proven_only: 仅已验证策略
        quality_levels: 按质量等级过滤
        tags: 按标签过滤
        limit: 返回数量上限
        sort_by: 排序字段 (score, executions, success_rate, avg_reward)
        sort_desc: 是否降序
    """
    scenario: str = ""
    opportunity_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    audience_segment: str = ""
    product_category: str = ""
    min_executions: int = 0
    min_success_rate: float = 0.0
    min_score: float = 0.0
    actionable_only: bool = False
    proven_only: bool = False
    quality_levels: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    limit: int = 100
    sort_by: str = "score"
    sort_desc: bool = True


@dataclass
class StrategyStats:
    """策略统计 — 对策略库的聚合统计.

    Attributes:
        total_strategies: 总策略数
        total_actionable: 可执行策略数
        total_proven: 已验证策略数
        by_category: 按类别统计
        by_quality: 按质量等级统计
        top_strategies: 最高评分策略
        avg_score: 平均评分
        avg_executions: 平均执行次数
        avg_steps: 平均步骤数
    """
    total_strategies: int = 0
    total_actionable: int = 0
    total_proven: int = 0
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    by_quality: dict[str, int] = field(default_factory=dict)
    top_strategies: list[dict[str, Any]] = field(default_factory=list)
    avg_score: float = 0.0
    avg_executions: float = 0.0
    avg_steps: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_strategies": self.total_strategies,
            "total_actionable": self.total_actionable,
            "total_proven": self.total_proven,
            "by_category": self.by_category,
            "by_quality": self.by_quality,
            "top_strategies": self.top_strategies,
            "avg_score": self.avg_score,
            "avg_executions": self.avg_executions,
            "avg_steps": self.avg_steps,
        }