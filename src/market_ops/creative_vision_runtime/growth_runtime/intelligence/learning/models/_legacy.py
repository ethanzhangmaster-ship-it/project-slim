"""E15.3.5 Continuous Learning Models — 持续学习数据模型 (Legacy).

迁移说明:
  原 models.py 迁移至 models/_legacy.py，避免与 models/ 目录冲突。
  通过 models/__init__.py 统一导出，保持向后兼容。

定义:
  - ExperienceQuality:   经验质量评估
  - PatternStatus:       模式生命周期状态
  - LearningExperience:  学习经验 (E15.3.5 版本)
  - LearnedPattern:      学习到的模式
  - LearningInsight:     学习洞察
  - StrategyRecommendation: 策略推荐
  - LearningResult:      学习结果 (E15.3.5 版本)
  - PatternEvolution:    模式进化记录
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


class PatternStatus(str, Enum):
    """模式生命周期状态."""
    DISCOVERED = "discovered"   # 新发现
    VALIDATED = "validated"     # 已验证
    ACTIVE = "active"           # 活跃使用中
    DECAYING = "decaying"       # 效果衰减中
    RETIRED = "retired"         # 已退役


class InsightType(str, Enum):
    """洞察类型."""
    PATTERN = "pattern"             # 模式发现
    STRATEGY = "strategy"           # 策略更新
    RISK = "risk"                   # 风险发现
    OPPORTUNITY = "opportunity"     # 机会发现
    WARNING = "warning"             # 警告
    CORRELATION = "correlation"     # 相关性发现


class ExperienceQualityLevel(str, Enum):
    """经验质量等级."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOISE = "noise"


# ═══════════════════════════════════════════════════════════════
# ExperienceQuality
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExperienceQuality:
    """经验质量评估 — 判断经验的学习价值.

    Attributes:
        confidence:    置信度 (0-1)
        reliability:   可靠性 (0-1)
        impact:        影响力 (0-1)
        novelty:       新颖度 (0-1)
        learning_value: 综合学习价值 (0-1)
        level:         质量等级
        issues:        质量问题
    """
    confidence: float = 0.0
    reliability: float = 0.0
    impact: float = 0.0
    novelty: float = 0.0
    learning_value: float = 0.0
    level: ExperienceQualityLevel = ExperienceQualityLevel.MEDIUM
    issues: list[str] = field(default_factory=list)

    def is_valuable(self) -> bool:
        """是否值得学习."""
        return self.learning_value >= 0.3 and self.level != ExperienceQualityLevel.NOISE

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "reliability": self.reliability,
            "impact": self.impact,
            "novelty": self.novelty,
            "learning_value": self.learning_value,
            "level": self.level.value,
            "issues": self.issues,
        }


# ═══════════════════════════════════════════════════════════════
# LearningExperience (E15.3.5)
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningExperience:
    """学习经验 — 一次执行产生的完整经验记录 (E15.3.5 版本).

    Attributes:
        experience_id: 经验 ID
        action:        执行动作
        context:       执行上下文
        decision:      决策信息
        result:        执行结果
        reward:        收益值
        quality:       经验质量
        timestamp:     时间戳
        tags:          标签
        metadata:      扩展元数据
    """
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    quality: ExperienceQuality | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valuable(self) -> bool:
        if self.quality is None:
            return self.reward > 0
        return self.quality.is_valuable()

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "action": self.action,
            "context": self.context,
            "decision": self.decision,
            "result": self.result,
            "reward": self.reward,
            "quality": self.quality.to_dict() if self.quality else None,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


# ═══════════════════════════════════════════════════════════════
# LearnedPattern
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearnedPattern:
    """学习到的模式 — 从经验中提取的规律.

    Attributes:
        pattern_id:     模式 ID
        name:           模式名称
        conditions:     触发条件
        recommendation: 推荐动作
        confidence:     置信度
        success_rate:   成功率
        usage_count:    使用次数
        status:         生命周期状态
        evidence_count: 证据数量
        discovered_at:  发现时间
        last_validated: 最后验证时间
        decay_rate:     衰减率
        metadata:       扩展元数据
    """
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    confidence: float = 0.0
    success_rate: float = 0.0
    usage_count: int = 0
    status: PatternStatus = PatternStatus.DISCOVERED
    evidence_count: int = 0
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_validated: str | None = None
    decay_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == PatternStatus.ACTIVE

    def is_valid(self) -> bool:
        return self.status in (PatternStatus.VALIDATED, PatternStatus.ACTIVE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "conditions": self.conditions,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "status": self.status.value,
            "evidence_count": self.evidence_count,
            "discovered_at": self.discovered_at,
            "last_validated": self.last_validated,
            "decay_rate": self.decay_rate,
        }


# ═══════════════════════════════════════════════════════════════
# PatternEvolution
# ═══════════════════════════════════════════════════════════════


@dataclass
class PatternEvolution:
    """模式进化记录 — 追踪模式生命周期变化.

    Attributes:
        evolution_id:   进化 ID
        pattern_id:     模式 ID
        from_status:    之前状态
        to_status:      当前状态
        reason:         变化原因
        evidence:       证据
        timestamp:      时间戳
    """
    evolution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    from_status: PatternStatus = PatternStatus.DISCOVERED
    to_status: PatternStatus = PatternStatus.DISCOVERED
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "evolution_id": self.evolution_id,
            "pattern_id": self.pattern_id,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════
# LearningInsight
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningInsight:
    """学习洞察 — 从经验中提取的高级见解.

    Attributes:
        insight_id:         洞察 ID
        insight_type:       洞察类型
        description:        描述
        confidence:         置信度
        affected_components: 影响组件
        evidence:           证据
        source_patterns:    来源模式
        recommendations:    建议
        created_at:         创建时间
    """
    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    insight_type: InsightType = InsightType.PATTERN
    description: str = ""
    confidence: float = 0.0
    affected_components: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    source_patterns: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "description": self.description,
            "confidence": self.confidence,
            "affected_components": self.affected_components,
            "evidence": self.evidence,
            "source_patterns": self.source_patterns,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# StrategyRecommendation
# ═══════════════════════════════════════════════════════════════


@dataclass
class StrategyRecommendation:
    """策略推荐 — 从学习模式生成的策略建议.

    Attributes:
        recommendation_id: 推荐 ID
        strategy_name:     策略名称
        description:       描述
        confidence:        置信度
        expected_reward:   预期收益
        source_patterns:   来源模式
        conditions:        适用条件
        action:            推荐动作
        priority:          优先级
        created_at:        创建时间
    """
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = ""
    description: str = ""
    confidence: float = 0.0
    expected_reward: float = 0.0
    source_patterns: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    action: str = ""
    priority: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "strategy_name": self.strategy_name,
            "description": self.description,
            "confidence": self.confidence,
            "expected_reward": self.expected_reward,
            "source_patterns": self.source_patterns,
            "conditions": self.conditions,
            "action": self.action,
            "priority": self.priority,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# LearningResult (E15.3.5)
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningResult:
    """学习结果 — 一次学习周期的完整输出 (E15.3.5 版本).

    Attributes:
        result_id:        结果 ID
        cycle_number:     周期号
        experiences_collected: 收集经验数
        experiences_evaluated: 评估经验数
        valuable_experiences:  有价值经验数
        patterns_discovered:   发现模式数
        patterns_evolved:      进化模式数
        insights:          洞察列表
        strategy_recommendations: 策略推荐
        quality_distribution:  质量分布
        summary:            摘要
        timestamp:          时间戳
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    experiences_collected: int = 0
    experiences_evaluated: int = 0
    valuable_experiences: int = 0
    patterns_discovered: int = 0
    patterns_evolved: int = 0
    insights: list[LearningInsight] = field(default_factory=list)
    strategy_recommendations: list[StrategyRecommendation] = field(default_factory=list)
    quality_distribution: dict[str, int] = field(default_factory=dict)
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "cycle_number": self.cycle_number,
            "experiences_collected": self.experiences_collected,
            "experiences_evaluated": self.experiences_evaluated,
            "valuable_experiences": self.valuable_experiences,
            "patterns_discovered": self.patterns_discovered,
            "patterns_evolved": self.patterns_evolved,
            "insights": [i.to_dict() for i in self.insights],
            "strategy_recommendations": [s.to_dict() for s in self.strategy_recommendations],
            "quality_distribution": self.quality_distribution,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


__all__ = [
    # Enums
    "PatternStatus",
    "InsightType",
    "ExperienceQualityLevel",
    # Models
    "ExperienceQuality",
    "LearningExperience",
    "LearnedPattern",
    "PatternEvolution",
    "LearningInsight",
    "StrategyRecommendation",
    "LearningResult",
]