"""E13.4.4 Failure Memory Models — 失败记忆数据模型.

Failure Memory 回答: "什么情况下不应该做什么？"

与 Pattern/Strategy Memory 的区别:
  - Pattern: 什么情况下什么动作有效？
  - Strategy: 面对问题应该执行什么完整流程？
  - Failure: 什么情况下什么动作绝对不能做？

核心模型:
  - FailureCondition: 失败触发条件
  - FailureSeverity: 失败严重程度枚举
  - FailurePattern: 失败模式 (Negative Knowledge)
  - FailureWarning: 失败警告 (面向决策)
  - FailureQuery: 失败模式查询条件
  - FailureStats: 失败模式统计聚合
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


class FailureSeverity(str, Enum):
    """失败严重程度."""
    CRITICAL = "critical"   # 致命: 历史失败率 > 90%, 大额损失
    HIGH = "high"           # 高危: 历史失败率 > 70%
    MEDIUM = "medium"       # 中危: 历史失败率 > 50%
    LOW = "low"             # 低危: 历史失败率 > 30%
    NEGLIGIBLE = "negligible"  # 可忽略: 失败率低或样本不足


class FailureCategory(str, Enum):
    """失败类别."""
    BUDGET_WASTE = "budget_waste"           # 预算浪费
    CREATIVE_BACKFIRE = "creative_backfire"  # 创意反效果
    ROAS_COLLAPSE = "roas_collapse"          # ROAS 崩溃
    AUDIENCE_MISMATCH = "audience_mismatch"  # 受众错配
    TIMING_ERROR = "timing_error"            # 时机错误
    SCALE_TOO_FAST = "scale_too_fast"        # 扩量过快
    GENERAL = "general"                      # 通用


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class FailureCondition:
    """失败触发条件 — 描述什么场景下该动作容易失败.

    Attributes:
        scenario: 场景描述
        opportunity_type: 关联机会类型
        signal_types: 触发信号类型
        metrics_conditions: 指标条件阈值 (如 {"roas": ("<", 0.2)})
        audience_segment: 目标受众
        product_category: 产品类别
        action_type: 应避免的动作类型
    """
    scenario: str = ""
    opportunity_type: str = ""
    signal_types: list[str] = field(default_factory=list)
    metrics_conditions: dict[str, tuple[str, float]] = field(default_factory=dict)
    audience_segment: str = ""
    product_category: str = ""
    action_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "opportunity_type": self.opportunity_type,
            "signal_types": self.signal_types,
            "metrics_conditions": {k: list(v) for k, v in self.metrics_conditions.items()},
            "audience_segment": self.audience_segment,
            "product_category": self.product_category,
            "action_type": self.action_type,
        }

    def matches(
        self,
        action_type: str = "",
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        audience_segment: str = "",
        product_category: str = "",
    ) -> bool:
        """检查是否匹配给定的动作和上下文."""
        if self.action_type and action_type and self.action_type != action_type:
            return False
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
class FailurePattern:
    """失败模式 — 记录"什么情况下什么动作不能做".

    这是 E13.4.4 Failure Memory 的核心存储单元。

    Attributes:
        failure_id: 失败模式唯一标识
        name: 失败模式名称
        category: 失败类别
        condition: 失败触发条件
        blocked_action: 应阻止的动作类型
        blocked_action_params: 应阻止的动作参数模式
        failure_rate: 历史失败率 [0, 1]
        total_attempts: 总尝试次数
        failed_attempts: 失败次数
        avg_loss: 平均损失 (金额)
        max_loss: 最大损失
        severity: 严重程度
        confidence: 置信度 [0, 1]
        suggestion: 替代建议
        source_experience_ids: 来源经验ID列表
        tags: 标签
        description: 详细描述
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    failure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: FailureCategory = FailureCategory.GENERAL
    condition: FailureCondition = field(default_factory=FailureCondition)
    blocked_action: str = ""
    blocked_action_params: dict[str, Any] = field(default_factory=dict)
    failure_rate: float = 0.0
    total_attempts: int = 0
    failed_attempts: int = 0
    avg_loss: float = 0.0
    max_loss: float = 0.0
    severity: FailureSeverity = FailureSeverity.NEGLIGIBLE
    confidence: float = 0.0
    suggestion: str = ""
    source_experience_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "name": self.name,
            "category": self.category.value,
            "condition": self.condition.to_dict(),
            "blocked_action": self.blocked_action,
            "blocked_action_params": self.blocked_action_params,
            "failure_rate": self.failure_rate,
            "total_attempts": self.total_attempts,
            "failed_attempts": self.failed_attempts,
            "avg_loss": self.avg_loss,
            "max_loss": self.max_loss,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "suggestion": self.suggestion,
            "source_experience_ids": self.source_experience_ids,
            "tags": self.tags,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def compute_confidence(self) -> float:
        """计算置信度: 样本因子 × 失败率."""
        import math
        if self.total_attempts == 0:
            return 0.0
        sample_factor = min(1.0, math.log(self.total_attempts + 1) / math.log(50))
        self.confidence = round(sample_factor * self.failure_rate, 4)
        return self.confidence

    def compute_severity(self) -> FailureSeverity:
        """根据失败率和样本量计算严重程度."""
        if self.total_attempts < 3:
            self.severity = FailureSeverity.NEGLIGIBLE
        elif self.failure_rate >= 0.9 and self.total_attempts >= 10:
            self.severity = FailureSeverity.CRITICAL
        elif self.failure_rate >= 0.7:
            self.severity = FailureSeverity.HIGH
        elif self.failure_rate >= 0.5:
            self.severity = FailureSeverity.MEDIUM
        elif self.failure_rate >= 0.3:
            self.severity = FailureSeverity.LOW
        else:
            self.severity = FailureSeverity.NEGLIGIBLE
        return self.severity

    def is_significant(self, min_attempts: int = 3, min_failure_rate: float = 0.5) -> bool:
        """是否构成有意义的失败模式."""
        return (
            self.total_attempts >= min_attempts
            and self.failure_rate >= min_failure_rate
        )

    def is_blocking(self) -> bool:
        """是否需要阻止执行 (CRITICAL 或 HIGH)."""
        return self.severity in (FailureSeverity.CRITICAL, FailureSeverity.HIGH)


@dataclass
class FailureWarning:
    """失败警告 — 对决策的实时风险提示.

    Attributes:
        warning_id: 警告唯一标识
        pattern_id: 关联失败模式ID
        pattern_name: 关联失败模式名称
        action_type: 被警告的动作类型
        risk_score: 综合风险评分 [0, 1]
        failure_rate: 历史失败率
        expected_loss: 预期损失
        severity: 严重程度
        suggestion: 建议 (替代方案)
        requires_approval: 是否需要人工审批
        context_summary: 匹配上下文摘要
    """
    warning_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    pattern_name: str = ""
    action_type: str = ""
    risk_score: float = 0.0
    failure_rate: float = 0.0
    expected_loss: float = 0.0
    severity: FailureSeverity = FailureSeverity.NEGLIGIBLE
    suggestion: str = ""
    requires_approval: bool = False
    context_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning_id": self.warning_id,
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "action_type": self.action_type,
            "risk_score": self.risk_score,
            "failure_rate": self.failure_rate,
            "expected_loss": self.expected_loss,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "requires_approval": self.requires_approval,
            "context_summary": self.context_summary,
        }


@dataclass
class FailureQuery:
    """失败模式查询条件.

    Attributes:
        action_types: 按动作类型过滤
        opportunity_types: 按机会类型过滤
        categories: 按失败类别过滤
        audience_segment: 按受众过滤
        product_category: 按产品类别过滤
        min_failure_rate: 最低失败率
        min_attempts: 最低尝试次数
        min_loss: 最低损失
        severity_levels: 按严重程度过滤
        blocking_only: 仅返回阻止级 (CRITICAL/HIGH)
        significant_only: 仅返回有意义模式
        tags: 按标签过滤
        limit: 返回数量上限
        sort_by: 排序字段 (failure_rate, attempts, avg_loss, severity)
        sort_desc: 是否降序
    """
    action_types: list[str] = field(default_factory=list)
    opportunity_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    audience_segment: str = ""
    product_category: str = ""
    min_failure_rate: float = 0.0
    min_attempts: int = 0
    min_loss: float = 0.0
    severity_levels: list[str] = field(default_factory=list)
    blocking_only: bool = False
    significant_only: bool = False
    tags: list[str] = field(default_factory=list)
    limit: int = 100
    sort_by: str = "failure_rate"
    sort_desc: bool = True


@dataclass
class FailureStats:
    """失败模式统计 — 对失败知识库的聚合统计.

    Attributes:
        total_patterns: 总失败模式数
        total_significant: 有意义模式数
        total_blocking: 阻止级模式数
        by_category: 按类别统计
        by_severity: 按严重程度统计
        by_action: 按被阻止动作统计
        top_dangerous: 最危险模式 (按损失排序)
        avg_failure_rate: 平均失败率
        avg_loss: 平均损失
        total_avoided_loss: 累计避免损失 (估算)
    """
    total_patterns: int = 0
    total_significant: int = 0
    total_blocking: int = 0
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    by_action: dict[str, int] = field(default_factory=dict)
    top_dangerous: list[dict[str, Any]] = field(default_factory=list)
    avg_failure_rate: float = 0.0
    avg_loss: float = 0.0
    total_avoided_loss: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_patterns": self.total_patterns,
            "total_significant": self.total_significant,
            "total_blocking": self.total_blocking,
            "by_category": self.by_category,
            "by_severity": self.by_severity,
            "by_action": self.by_action,
            "top_dangerous": self.top_dangerous,
            "avg_failure_rate": self.avg_failure_rate,
            "avg_loss": self.avg_loss,
            "total_avoided_loss": self.total_avoided_loss,
        }