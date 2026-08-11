"""E13.4.5 Memory Evolution Models — 记忆进化数据模型.

Memory Evolution 让记忆不再只是存储，而是自动进化：
  Experience → Pattern → Strategy → Failure → Evolution → Consolidation → Upgrade

核心能力:
  1. Knowledge Consolidation: 合并相似模式/策略，升级置信度
  2. Pattern Evolution: 新经验确认/否定已有模式，动态调整
  3. Strategy Evolution: 新模式出现时自动更新策略步骤
  4. Cross-Referencing: 建立 Pattern ↔ Strategy ↔ Failure 知识图谱
  5. Decay Management: 过期知识自动衰减
  6. Evolution Tracking: 完整进化历史记录

核心模型:
  - EvolutionEventType: 进化事件类型枚举
  - EvolutionEvent: 单个进化事件记录
  - ConsolidationResult: 知识合并结果
  - KnowledgeGraph: 跨层知识图谱
  - EvolutionMetrics: 进化质量指标
  - EvolutionConfig: 进化参数配置
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


class EvolutionEventType(str, Enum):
    """进化事件类型."""
    CONSOLIDATE = "consolidate"           # 知识合并 (多个相似模式合并为一个)
    UPGRADE = "upgrade"                   # 置信度升级 (新证据验证/强化已有知识)
    DOWNGRADE = "downgrade"               # 置信度降级 (新证据削弱已有知识)
    DECAY = "decay"                       # 知识衰减 (长期未使用的知识降低置信度)
    CONFLICT_RESOLVE = "conflict_resolve"  # 冲突解决 (矛盾知识选择更可靠的一方)
    CROSS_REFERENCE = "cross_reference"   # 跨层引用 (建立 Pattern↔Strategy↔Failure 连接)
    NEW_KNOWLEDGE = "new_knowledge"       # 新知识发现 (从经验中提取全新模式)
    DEPRECATE = "deprecate"               # 知识废弃 (标记为过时/无效)
    MERGE = "merge"                       # 策略合并 (相似策略合并升级)


class EvolutionTarget(str, Enum):
    """进化目标类型."""
    PATTERN = "pattern"
    STRATEGY = "strategy"
    FAILURE = "failure"
    CROSS_LAYER = "cross_layer"


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class EvolutionEvent:
    """进化事件 — 记录一次记忆进化操作.

    Attributes:
        event_id: 事件唯一标识
        event_type: 事件类型
        target_type: 影响的知识类型
        source_ids: 来源知识ID列表 (被合并/升级的源)
        target_id: 目标知识ID (合并后的结果)
        before_state: 进化前状态摘要
        after_state: 进化后状态摘要
        delta: 变化量 (如 confidence 变化)
        reason: 进化原因
        timestamp: 发生时间
        metadata: 扩展元数据
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EvolutionEventType = EvolutionEventType.UPGRADE
    target_type: EvolutionTarget = EvolutionTarget.PATTERN
    source_ids: list[str] = field(default_factory=list)
    target_id: str = ""
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    delta: dict[str, float] = field(default_factory=dict)
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "target_type": self.target_type.value,
            "source_ids": self.source_ids,
            "target_id": self.target_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "delta": self.delta,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ConsolidationResult:
    """知识合并结果 — 多个相似知识合并为一个.

    Attributes:
        consolidated_id: 合并后的新ID
        source_ids: 被合并的源ID列表
        target_type: 合并的知识类型
        name: 合并后的名称
        confidence_before: 合并前平均置信度
        confidence_after: 合并后置信度
        total_evidence: 合并后总证据量 (样本数)
        improvement: 置信度提升幅度
        merged_fields: 被合并的字段列表
        events: 产生的进化事件列表
    """
    consolidated_id: str = ""
    source_ids: list[str] = field(default_factory=list)
    target_type: EvolutionTarget = EvolutionTarget.PATTERN
    name: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    total_evidence: int = 0
    improvement: float = 0.0
    merged_fields: list[str] = field(default_factory=list)
    events: list[EvolutionEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "consolidated_id": self.consolidated_id,
            "source_ids": self.source_ids,
            "target_type": self.target_type.value,
            "name": self.name,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "total_evidence": self.total_evidence,
            "improvement": self.improvement,
            "merged_fields": self.merged_fields,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class KnowledgeGraph:
    """跨层知识图谱 — 连接 Pattern ↔ Strategy ↔ Failure.

    建立三层记忆之间的引用关系，形成可追溯的知识网络。

    Attributes:
        pattern_to_strategies: Pattern ID → [StrategyStep 引用列表]
        strategy_to_patterns: Strategy ID → [引用的 Pattern ID 列表]
        failure_to_patterns: Failure Pattern ID → [关联的 Pattern ID 列表]
        failure_to_strategies: Failure Pattern ID → [受影响的 Strategy ID 列表]
        isolated_patterns: 未被任何策略引用的孤立模式
        isolated_strategies: 未被任何模式支持的策略步骤
        cross_references: 跨层引用总数
        graph_density: 图谱密度 (实际引用 / 最大可能引用)
        last_updated: 最后更新时间
    """
    pattern_to_strategies: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    strategy_to_patterns: dict[str, list[str]] = field(default_factory=dict)
    failure_to_patterns: dict[str, list[str]] = field(default_factory=dict)
    failure_to_strategies: dict[str, list[str]] = field(default_factory=dict)
    isolated_patterns: list[str] = field(default_factory=list)
    isolated_strategies: list[str] = field(default_factory=list)
    cross_references: int = 0
    graph_density: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_to_strategies": self.pattern_to_strategies,
            "strategy_to_patterns": self.strategy_to_patterns,
            "failure_to_patterns": self.failure_to_patterns,
            "failure_to_strategies": self.failure_to_strategies,
            "isolated_patterns": self.isolated_patterns,
            "isolated_strategies": self.isolated_strategies,
            "cross_references": self.cross_references,
            "graph_density": self.graph_density,
            "last_updated": self.last_updated,
        }


@dataclass
class EvolutionMetrics:
    """进化质量指标 — 衡量记忆进化效果.

    Attributes:
        total_events: 总进化事件数
        consolidations: 合并次数
        upgrades: 升级次数
        downgrades: 降级次数
        decays: 衰减次数
        conflict_resolutions: 冲突解决次数
        cross_references: 跨层引用建立次数
        new_knowledge: 新知识发现次数
        deprecations: 知识废弃次数
        avg_confidence_before: 进化前平均置信度
        avg_confidence_after: 进化后平均置信度
        confidence_improvement: 置信度提升幅度
        knowledge_graph_size: 知识图谱规模 (节点数)
        knowledge_graph_density: 知识图谱密度
        evolution_score: 综合进化评分 [0, 1]
        evolution_velocity: 进化速度 (最近N天事件数)
        last_evolution: 最后进化时间
    """
    total_events: int = 0
    consolidations: int = 0
    upgrades: int = 0
    downgrades: int = 0
    decays: int = 0
    conflict_resolutions: int = 0
    cross_references: int = 0
    new_knowledge: int = 0
    deprecations: int = 0
    avg_confidence_before: float = 0.0
    avg_confidence_after: float = 0.0
    confidence_improvement: float = 0.0
    knowledge_graph_size: int = 0
    knowledge_graph_density: float = 0.0
    evolution_score: float = 0.0
    evolution_velocity: float = 0.0
    last_evolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "consolidations": self.consolidations,
            "upgrades": self.upgrades,
            "downgrades": self.downgrades,
            "decays": self.decays,
            "conflict_resolutions": self.conflict_resolutions,
            "cross_references": self.cross_references,
            "new_knowledge": self.new_knowledge,
            "deprecations": self.deprecations,
            "avg_confidence_before": self.avg_confidence_before,
            "avg_confidence_after": self.avg_confidence_after,
            "confidence_improvement": self.confidence_improvement,
            "knowledge_graph_size": self.knowledge_graph_size,
            "knowledge_graph_density": self.knowledge_graph_density,
            "evolution_score": self.evolution_score,
            "evolution_velocity": self.evolution_velocity,
            "last_evolution": self.last_evolution,
        }


@dataclass
class EvolutionConfig:
    """进化参数配置.

    Attributes:
        consolidation_threshold: 模式相似度阈值 (超过此值触发合并)
        min_confidence_improvement: 最小置信度提升 (低于此值不触发升级)
        decay_days: 衰减天数 (超过此天数未使用的知识开始衰减)
        decay_rate: 衰减率 (每天衰减比例)
        max_evolution_history: 最大进化历史记录数
        auto_consolidate: 是否自动合并
        auto_upgrade: 是否自动升级
        auto_decay: 是否自动衰减
        auto_cross_reference: 是否自动建立跨层引用
    """
    consolidation_threshold: float = 0.7
    min_confidence_improvement: float = 0.05
    decay_days: int = 30
    decay_rate: float = 0.01
    max_evolution_history: int = 1000
    auto_consolidate: bool = True
    auto_upgrade: bool = True
    auto_decay: bool = True
    auto_cross_reference: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "consolidation_threshold": self.consolidation_threshold,
            "min_confidence_improvement": self.min_confidence_improvement,
            "decay_days": self.decay_days,
            "decay_rate": self.decay_rate,
            "max_evolution_history": self.max_evolution_history,
            "auto_consolidate": self.auto_consolidate,
            "auto_upgrade": self.auto_upgrade,
            "auto_decay": self.auto_decay,
            "auto_cross_reference": self.auto_cross_reference,
        }