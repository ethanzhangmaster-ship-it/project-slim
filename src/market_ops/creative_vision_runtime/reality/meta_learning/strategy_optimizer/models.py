"""E12.5.4 — Meta Strategy Optimizer Models。

将历史经验转换为可执行的进化战略。

核心模型:
  OptimizationGoal:     优化目标（CTR, ROAS, CVR, CPI, BALANCED）
  MetaStrategy:         元策略（核心输出）
  StrategyRanking:      策略排序结果
  ExplorationPolicy:    探索策略
  OptimizationResult:   优化结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──────────────────────────────────────────────────


class OptimizationGoal(str, Enum):
    """优化目标。"""

    CTR = "ctr"
    ROAS = "roas"
    CVR = "cvr"
    CPI = "cpi"
    BALANCED = "balanced"


class StrategyStatus(str, Enum):
    """策略状态。"""

    DRAFT = "draft"
    RANKED = "ranked"
    SELECTED = "selected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class StrategySource(str, Enum):
    """策略来源。"""

    PATTERN = "pattern"          # 来自 E12.5.2 Pattern
    KNOWLEDGE = "knowledge"      # 来自 E12.5.3 Knowledge Graph
    EXPLORATION = "exploration"  # 探索生成
    TRANSFER = "transfer"        # 跨产品迁移
    MANUAL = "manual"            # 手动输入


# ── MetaStrategy ───────────────────────────────────────────


@dataclass
class MetaStrategy:
    """元策略 —— E12.5.4 核心输出。

    将 Pattern / Knowledge Graph 的经验转化为
    E11 Evolution Orchestrator 可执行的进化战略。

    Attributes:
        strategy_id:         策略 ID
        name:                策略名称
        target_product:      目标产品
        optimization_goal:   优化目标
        dna_mutations:       DNA 修改建议 {gene: value}
        dna_amplify:         需要放大权重的基因
        dna_suppress:        需要抑制权重的基因
        dna_explore:         需要探索的基因
        source_patterns:     来源 Pattern ID 列表
        source_knowledge:    来源 Knowledge 节点 ID 列表
        expected_ctr_delta:  预期 CTR 变化
        expected_roas_delta: 预期 ROAS 变化
        expected_cvr_delta:  预期 CVR 变化
        expected_cpi_delta:  预期 CPI 变化
        confidence:          置信度 [0, 1]
        risk_score:          风险评分 [0, 1]
        exploration:         是否为探索策略
        strategy_source:     策略来源
        status:              策略状态
        evidence_count:      证据数量
        markets:             适用市场
        platforms:           适用平台
        audiences:           适用受众
        insight:             策略洞察
        recommendation:      执行建议
        created_at:          创建时间
        score:               综合评分
    """

    strategy_id: str = ""
    name: str = ""
    target_product: str = ""

    optimization_goal: OptimizationGoal = OptimizationGoal.BALANCED

    dna_mutations: dict[str, str] = field(default_factory=dict)
    dna_amplify: list[str] = field(default_factory=list)
    dna_suppress: list[str] = field(default_factory=list)
    dna_explore: list[str] = field(default_factory=list)

    source_patterns: list[str] = field(default_factory=list)
    source_knowledge: list[str] = field(default_factory=list)

    expected_ctr_delta: float = 0.0
    expected_roas_delta: float = 0.0
    expected_cvr_delta: float = 0.0
    expected_cpi_delta: float = 0.0

    confidence: float = 0.0
    risk_score: float = 0.0
    exploration: bool = False

    strategy_source: StrategySource = StrategySource.PATTERN
    status: StrategyStatus = StrategyStatus.DRAFT

    evidence_count: int = 0
    markets: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    audiences: list[str] = field(default_factory=list)

    insight: str = ""
    recommendation: str = ""

    created_at: datetime = field(default_factory=_now)
    score: float = 0.0

    def __post_init__(self) -> None:
        if not self.strategy_id:
            self.strategy_id = _gen_id("MS")

    @property
    def is_reliable(self) -> bool:
        """策略是否可靠。"""
        return self.confidence >= 0.60 and self.evidence_count >= 5

    @property
    def is_strong(self) -> bool:
        """策略是否强信号。"""
        return self.confidence >= 0.80 and self.evidence_count >= 20

    @property
    def performance_impact(self) -> float:
        """综合性能影响。"""
        return (
            self.expected_ctr_delta
            + self.expected_roas_delta
            + self.expected_cvr_delta
            - self.expected_cpi_delta
        ) / 4.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "target_product": self.target_product,
            "optimization_goal": self.optimization_goal.value,
            "dna_mutations": self.dna_mutations,
            "dna_amplify": self.dna_amplify,
            "dna_suppress": self.dna_suppress,
            "dna_explore": self.dna_explore,
            "source_patterns": self.source_patterns,
            "source_knowledge": self.source_knowledge,
            "expected_ctr_delta": round(self.expected_ctr_delta, 4),
            "expected_roas_delta": round(self.expected_roas_delta, 4),
            "expected_cvr_delta": round(self.expected_cvr_delta, 4),
            "expected_cpi_delta": round(self.expected_cpi_delta, 4),
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "exploration": self.exploration,
            "strategy_source": self.strategy_source.value,
            "status": self.status.value,
            "evidence_count": self.evidence_count,
            "markets": self.markets,
            "platforms": self.platforms,
            "audiences": self.audiences,
            "insight": self.insight,
            "recommendation": self.recommendation,
            "score": round(self.score, 4),
            "is_reliable": self.is_reliable,
            "is_strong": self.is_strong,
            "performance_impact": round(self.performance_impact, 4),
        }

    def to_evolution_strategy(self) -> dict[str, Any]:
        """转换为 E11 Evolution Orchestrator 可用的进化策略。

        输出格式与 E11.9 EvolutionStrategy 兼容。
        """
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "optimization_goal": self.optimization_goal.value,
            "dna_mutations": self.dna_mutations,
            "amplify": self.dna_amplify,
            "suppress": self.dna_suppress,
            "explore": self.dna_explore,
            "priority": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "expected_impact": {
                "ctr_delta": round(self.expected_ctr_delta, 4),
                "roas_delta": round(self.expected_roas_delta, 4),
                "cvr_delta": round(self.expected_cvr_delta, 4),
                "cpi_delta": round(self.expected_cpi_delta, 4),
            },
            "evidence_count": self.evidence_count,
            "markets": self.markets,
            "platforms": self.platforms,
            "audiences": self.audiences,
            "insight": self.insight,
            "recommendation": self.recommendation,
        }

    def __repr__(self) -> str:
        return (
            f"MetaStrategy({self.name[:20]}, "
            f"goal={self.optimization_goal.value}, "
            f"score={self.score:.2f}, "
            f"conf={self.confidence:.2f})"
        )


# ── ExplorationPolicy ──────────────────────────────────────


@dataclass
class ExplorationPolicy:
    """探索策略 —— 控制 Exploitation vs Exploration 比例。

    Attributes:
        exploit_ratio:      利用已验证策略的比例 (default 0.7)
        explore_ratio:      探索新组合的比例 (default 0.3)
        mutation_strength:  探索时的突变强度 [0, 1]
        min_exploit_ratio:  最低利用比例
        max_explore_ratio:  最高探索比例
        fatigue_threshold:  疲劳阈值（触发更多探索）
        decay_enabled:      是否启用探索衰减
    """

    exploit_ratio: float = 0.7
    explore_ratio: float = 0.3
    mutation_strength: float = 0.5
    min_exploit_ratio: float = 0.5
    max_explore_ratio: float = 0.5
    fatigue_threshold: float = 0.75
    decay_enabled: bool = True

    def __post_init__(self) -> None:
        self._validate_ratios()

    def _validate_ratios(self) -> None:
        """确保比例和为 1。"""
        total = self.exploit_ratio + self.explore_ratio
        if abs(total - 1.0) > 0.001:
            self.exploit_ratio /= total
            self.explore_ratio /= total

    def adjust_for_fatigue(self, fatigue_level: float) -> None:
        """根据疲劳度调整探索比例。"""
        if fatigue_level > self.fatigue_threshold:
            extra_explore = min(
                (fatigue_level - self.fatigue_threshold) * 0.5,
                self.max_explore_ratio - self.explore_ratio,
            )
            self.explore_ratio += extra_explore
            self.exploit_ratio -= extra_explore
            self._validate_ratios()

    def to_dict(self) -> dict[str, Any]:
        return {
            "exploit_ratio": round(self.exploit_ratio, 4),
            "explore_ratio": round(self.explore_ratio, 4),
            "mutation_strength": round(self.mutation_strength, 4),
            "min_exploit_ratio": round(self.min_exploit_ratio, 4),
            "max_explore_ratio": round(self.max_explore_ratio, 4),
            "fatigue_threshold": round(self.fatigue_threshold, 4),
            "decay_enabled": self.decay_enabled,
        }

    def __repr__(self) -> str:
        return (
            f"ExplorationPolicy(exploit={self.exploit_ratio:.0%}, "
            f"explore={self.explore_ratio:.0%}, "
            f"strength={self.mutation_strength:.2f})"
        )


# ── StrategyRanking ────────────────────────────────────────


@dataclass
class StrategyRanking:
    """策略排序结果。

    Attributes:
        strategies:    已排序的策略列表
        total_count:   总数
        top_exploit:   顶部利用策略
        top_explore:   顶部探索策略
        ranking_summary: 排序摘要
    """

    strategies: list[MetaStrategy] = field(default_factory=list)
    total_count: int = 0
    top_exploit: list[MetaStrategy] = field(default_factory=list)
    top_explore: list[MetaStrategy] = field(default_factory=list)
    ranking_summary: str = ""

    def __post_init__(self) -> None:
        self.total_count = len(self.strategies)
        if not self.top_exploit:
            self.top_exploit = [s for s in self.strategies if not s.exploration][:5]
        if not self.top_explore:
            self.top_explore = [s for s in self.strategies if s.exploration][:5]

    def get_top(self, n: int = 5) -> list[MetaStrategy]:
        """获取 Top N 策略。"""
        return self.strategies[:n]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "top_exploit": [s.to_dict() for s in self.top_exploit],
            "top_explore": [s.to_dict() for s in self.top_explore],
            "ranking_summary": self.ranking_summary,
            "strategies": [s.to_dict() for s in self.strategies],
        }

    def __repr__(self) -> str:
        return (
            f"StrategyRanking(total={self.total_count}, "
            f"exploit={len(self.top_exploit)}, "
            f"explore={len(self.top_explore)})"
        )


# ── OptimizationResult ─────────────────────────────────────


@dataclass
class OptimizationResult:
    """优化结果 —— Pipeline 完整输出。

    Attributes:
        strategies:       最终策略列表
        ranking:          排序结果
        exploration_policy: 探索策略
        total_patterns:   输入 Pattern 数
        total_knowledge:  输入 Knowledge 节点数
        strategies_generated: 生成策略数
        strategies_selected:  选中策略数
        summary:          优化摘要
    """

    strategies: list[MetaStrategy] = field(default_factory=list)
    ranking: StrategyRanking | None = None
    exploration_policy: ExplorationPolicy = field(default_factory=ExplorationPolicy)

    total_patterns: int = 0
    total_knowledge: int = 0
    strategies_generated: int = 0
    strategies_selected: int = 0
    summary: str = ""

    def __post_init__(self) -> None:
        self.strategies_generated = len(self.strategies)
        if self.ranking is None and self.strategies:
            self.ranking = StrategyRanking(strategies=self.strategies)
        self.strategies_selected = len(self.ranking.strategies) if self.ranking else 0
        if not self.summary:
            self.summary = (
                f"Generated {self.strategies_generated} strategies "
                f"from {self.total_patterns} patterns, "
                f"selected {self.strategies_selected}"
            )

    def get_exploit_strategies(self) -> list[MetaStrategy]:
        """获取利用策略（已验证）。"""
        return [s for s in self.strategies if not s.exploration]

    def get_explore_strategies(self) -> list[MetaStrategy]:
        """获取探索策略（新组合）。"""
        return [s for s in self.strategies if s.exploration]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_patterns": self.total_patterns,
            "total_knowledge": self.total_knowledge,
            "strategies_generated": self.strategies_generated,
            "strategies_selected": self.strategies_selected,
            "summary": self.summary,
            "strategies": [s.to_dict() for s in self.strategies],
            "ranking": self.ranking.to_dict() if self.ranking else None,
            "exploration_policy": self.exploration_policy.to_dict(),
            "exploit_strategies": [s.to_dict() for s in self.get_exploit_strategies()],
            "explore_strategies": [s.to_dict() for s in self.get_explore_strategies()],
        }

    def __repr__(self) -> str:
        return (
            f"OptimizationResult(strategies={self.strategies_generated}, "
            f"selected={self.strategies_selected})"
        )