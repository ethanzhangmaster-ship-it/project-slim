"""E14.7.4 Growth Strategy Memory Optimizer — 增长策略记忆优化器.

E14.7「Autonomous Growth Execution Layer」第四层:
  从大量 GrowthExperience 中自动挖掘可复用 Growth Strategy，
  供 E14.8 Autonomous Growth Agent 调用。

与 E13.4.3 StrategyMemory 的关系:
  - E13.4.3: 从经验中提取多步动作链 (chain-based)
  - E14.7.4: 从经验中聚类提炼单步/多步策略 (cluster-based)
  - E14.7.4 输出 GrowthStrategyPattern 存入 E13.4.3 StrategyMemory

核心概念:
  - StrategyScore: 策略评分模型
  - StrategyExtractor: 聚类式策略提取器
  - StrategyEvaluator: 策略评估与排序
  - GrowthStrategyOptimizer: 策略优化器主入口

数据流:
  GrowthExperience[] (E14.7.3)
       ↓
  StrategyExtractor.cluster()
       ↓
  StrategyCluster[]
       ↓
  StrategyEvaluator.evaluate()
       ↓
  GrowthStrategyPattern[] (E13.4.3)
       ↓
  StrategyOptimizer.optimize()
       ↓
  StrategyMemory (E13.4.3)
       ↓
  E14.8 Autonomous Agent
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    GrowthExperience,
    ExperienceCategory,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
    GrowthStrategyPattern,
    StrategyCategory,
    StrategyPerformance,
    StrategyQuality,
    StrategyStep,
    StrategyTriggerCondition,
)


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class StrategyScore:
    """策略评分 — 用于评估和排序策略.

    评分公式 (与 E13.4.2 PatternMemory 一致):
      score = sample_factor × success_rate × avg_reward × confidence

    Attributes:
        sample_size: 样本数
        success_rate: 成功率 [0, 1]
        avg_reward: 平均奖励 [0, 1]
        confidence: 置信度 [0, 1]
        score: 综合评分 [0, 1]
    """
    sample_size: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0
    confidence: float = 0.0
    score: float = 0.0

    @classmethod
    def compute(
        cls,
        sample_size: int,
        success_rate: float,
        avg_reward: float,
        confidence: float = 0.0,
    ) -> "StrategyScore":
        """计算策略评分.

        score = sample_factor × success_rate × avg_reward × confidence_weight
        sample_factor = log(sample_size + 1) / log(100)
        """
        import math
        sample_factor = min(1.0, math.log(sample_size + 1) / math.log(100))
        conf_weight = confidence if confidence > 0 else (0.5 + 0.5 * success_rate)
        score = round(
            sample_factor * success_rate * max(avg_reward, 0.01) * conf_weight,
            4,
        )
        return cls(
            sample_size=sample_size,
            success_rate=round(success_rate, 4),
            avg_reward=round(avg_reward, 4),
            confidence=round(conf_weight, 4),
            score=score,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_size": self.sample_size,
            "success_rate": self.success_rate,
            "avg_reward": self.avg_reward,
            "confidence": self.confidence,
            "score": self.score,
        }


@dataclass
class StrategyCluster:
    """策略聚类 — 一组相似经验的聚合.

    Attributes:
        cluster_id: 聚类 ID
        action_type: 动作类型
        dimension: 聚类维度 (action_type, opportunity_type, context)
        experiences: 聚合的经验列表
        context_key: 上下文键 (opportunity_type|audience|product)
        sample_size: 样本数
        success_count: 成功数
        success_rate: 成功率
        avg_reward: 平均奖励
    """
    cluster_id: str = field(default_factory=lambda: f"sc_{uuid.uuid4().hex[:8]}")
    action_type: str = ""
    dimension: str = ""
    experiences: list[GrowthExperience] = field(default_factory=list)
    context_key: str = ""
    sample_size: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0

    def compute_stats(self) -> None:
        """计算聚类统计."""
        self.sample_size = len(self.experiences)
        if self.sample_size == 0:
            return
        self.success_count = sum(1 for e in self.experiences if e.is_successful())
        self.success_rate = round(self.success_count / self.sample_size, 4)
        self.avg_reward = round(
            sum(e.reward for e in self.experiences) / self.sample_size, 4
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "action_type": self.action_type,
            "dimension": self.dimension,
            "context_key": self.context_key,
            "sample_size": self.sample_size,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
            "avg_reward": self.avg_reward,
            "experience_ids": [e.experience_id for e in self.experiences],
        }


# ═══════════════════════════════════════════════════════════
# StrategyExtractor
# ═══════════════════════════════════════════════════════════

class StrategyExtractor:
    """策略提取器 — 从经验中聚类提取策略.

    核心职责:
      1. 按 (action_type, opportunity_type, dimension, context) 聚类
      2. 计算每个聚类的统计指标
      3. 过滤低质量聚类

    用法:
        extractor = StrategyExtractor()
        clusters = extractor.extract(experiences)
    """

    # 聚类维度定义
    DIMENSION_ACTION = "action_type"
    DIMENSION_OPPORTUNITY_ACTION = "opportunity_action"
    DIMENSION_ACTION_DIMENSION = "action_dimension"

    def __init__(
        self,
        min_samples: int = 3,
        min_success_rate: float = 0.3,
        dimension: str = "opportunity_action",
    ):
        """初始化提取器.

        Args:
            min_samples: 最小样本数 (低于此数的聚类被过滤)
            min_success_rate: 最低成功率
            dimension: 聚类维度
        """
        self._min_samples = min_samples
        self._min_success_rate = min_success_rate
        self._dimension = dimension
        self._extraction_count: int = 0

    # ── 核心: 提取 ────────────────────────────────────────

    def extract(
        self,
        experiences: list[GrowthExperience],
    ) -> list[StrategyCluster]:
        """从经验中提取策略聚类.

        Args:
            experiences: GrowthExperience 列表

        Returns:
            list[StrategyCluster]: 按 score 降序的聚类列表
        """
        self._extraction_count += 1

        if len(experiences) < self._min_samples:
            return []

        # 聚类
        clusters = self._cluster(experiences)

        # 计算统计
        for c in clusters:
            c.compute_stats()

        # 过滤
        clusters = self._filter(clusters)

        return clusters

    # ── 聚类逻辑 ──────────────────────────────────────────

    def _cluster(
        self,
        experiences: list[GrowthExperience],
    ) -> list[StrategyCluster]:
        """按聚类维度分组."""
        if self._dimension == self.DIMENSION_ACTION:
            return self._cluster_by_action(experiences)
        elif self._dimension == self.DIMENSION_OPPORTUNITY_ACTION:
            return self._cluster_by_opportunity_action(experiences)
        elif self._dimension == self.DIMENSION_ACTION_DIMENSION:
            return self._cluster_by_action_dimension(experiences)
        else:
            return self._cluster_by_opportunity_action(experiences)

    def _cluster_by_action(
        self,
        experiences: list[GrowthExperience],
    ) -> list[StrategyCluster]:
        """按 action_type 聚类."""
        groups: dict[str, list[GrowthExperience]] = defaultdict(list)
        for exp in experiences:
            groups[exp.action_type].append(exp)

        clusters: list[StrategyCluster] = []
        for action_type, exps in groups.items():
            cluster = StrategyCluster(
                action_type=action_type,
                dimension="action_type",
                experiences=exps,
                context_key=action_type,
            )
            clusters.append(cluster)
        return clusters

    def _cluster_by_opportunity_action(
        self,
        experiences: list[GrowthExperience],
    ) -> list[StrategyCluster]:
        """按 (opportunity_type, action_type, audience_segment) 聚类."""
        groups: dict[str, tuple[str, list[GrowthExperience]]] = {}
        for exp in experiences:
            opp = exp.context.opportunity_type or "unknown"
            audience = exp.context.audience_segment or "all"
            key = f"{opp}|{exp.action_type}|{audience}"
            if key not in groups:
                groups[key] = (exp.action_type, [])
            groups[key][1].append(exp)

        clusters: list[StrategyCluster] = []
        for key, (action_type, exps) in groups.items():
            cluster = StrategyCluster(
                action_type=action_type,
                dimension="opportunity_action",
                experiences=exps,
                context_key=key,
            )
            clusters.append(cluster)
        return clusters

    def _cluster_by_action_dimension(
        self,
        experiences: list[GrowthExperience],
    ) -> list[StrategyCluster]:
        """按 (action_type, category, dimension) 聚类."""
        groups: dict[str, tuple[str, list[GrowthExperience]]] = {}
        for exp in experiences:
            cat = exp.category.value
            key = f"{exp.action_type}|{cat}"
            if key not in groups:
                groups[key] = (exp.action_type, [])
            groups[key][1].append(exp)

        clusters: list[StrategyCluster] = []
        for key, (action_type, exps) in groups.items():
            cluster = StrategyCluster(
                action_type=action_type,
                dimension="action_dimension",
                experiences=exps,
                context_key=key,
            )
            clusters.append(cluster)
        return clusters

    # ── 过滤 ──────────────────────────────────────────────

    def _filter(self, clusters: list[StrategyCluster]) -> list[StrategyCluster]:
        """过滤低质量聚类."""
        return [
            c for c in clusters
            if c.sample_size >= self._min_samples
            and c.success_rate >= self._min_success_rate
        ]

    @property
    def min_samples(self) -> int:
        return self._min_samples

    @property
    def dimension(self) -> str:
        return self._dimension

    @property
    def extraction_count(self) -> int:
        return self._extraction_count


# ═══════════════════════════════════════════════════════════
# StrategyEvaluator
# ═══════════════════════════════════════════════════════════

class StrategyEvaluator:
    """策略评估器 — 评估聚类并转化为 GrowthStrategyPattern.

    核心职责:
      1. 为每个聚类计算 StrategyScore
      2. 将聚类转化为 E13.4.3 GrowthStrategyPattern
      3. 按评分排序

    用法:
        evaluator = StrategyEvaluator()
        patterns = evaluator.evaluate(clusters)
    """

    def __init__(self, min_score: float = 0.0):
        """初始化评估器.

        Args:
            min_score: 最低评分阈值
        """
        self._min_score = min_score
        self._evaluation_count: int = 0

    def evaluate(self, clusters: list[StrategyCluster]) -> list[GrowthStrategyPattern]:
        """评估聚类并生成策略.

        Args:
            clusters: StrategyCluster 列表

        Returns:
            list[GrowthStrategyPattern]: 按 score 降序的策略列表
        """
        self._evaluation_count += 1

        patterns: list[GrowthStrategyPattern] = []
        for cluster in clusters:
            pattern = self._cluster_to_pattern(cluster)
            if pattern is not None:
                pattern.compute_score()
                if pattern.score >= self._min_score:
                    patterns.append(pattern)

        # 排序
        patterns.sort(key=lambda p: -p.score)
        return patterns

    def _cluster_to_pattern(
        self,
        cluster: StrategyCluster,
    ) -> GrowthStrategyPattern | None:
        """将聚类转化为 GrowthStrategyPattern."""
        if cluster.sample_size == 0:
            return None

        # 构建触发条件
        trigger = self._build_trigger(cluster)

        # 构建步骤
        steps = self._build_steps(cluster)

        # 构建表现
        performance = self._build_performance(cluster)

        # 推断类别
        category = self._infer_category(cluster)

        # 策略名称
        name = self._generate_name(cluster)

        # 描述
        description = self._generate_description(cluster, performance)

        # 来源
        source_ids = [e.experience_id for e in cluster.experiences]

        # 标签
        tags = self._extract_tags(cluster)

        return GrowthStrategyPattern(
            name=name,
            category=category,
            trigger=trigger,
            steps=steps,
            performance=performance,
            source_experience_ids=source_ids,
            tags=tags,
            description=description,
        )

    def _build_trigger(self, cluster: StrategyCluster) -> StrategyTriggerCondition:
        """构建触发条件."""
        if not cluster.experiences:
            return StrategyTriggerCondition()

        first = cluster.experiences[0]
        opp = first.context.opportunity_type

        scenario_map = {
            "creative_scale": "Creative scaling opportunity detected",
            "creative_fatigue": "Creative fatigue detected",
            "creative_refresh": "Creative needs refresh",
            "roas_drop": "ROAS dropping below threshold",
            "roas_recovery": "ROAS recovery opportunity",
            "budget_waste": "Budget waste detected",
            "scale_opportunity": "Scaling opportunity identified",
            "audience_expansion": "Audience expansion opportunity",
        }

        return StrategyTriggerCondition(
            scenario=scenario_map.get(opp, f"Growth opportunity: {opp}"),
            opportunity_type=opp,
            signal_types=first.context.trigger_signals,
            audience_segment=first.context.audience_segment,
            product_category=first.context.product_id,
            min_confidence=0.3,
        )

    def _build_steps(self, cluster: StrategyCluster) -> list[StrategyStep]:
        """构建策略步骤."""
        return [
            StrategyStep(
                order=1,
                action_type=cluster.action_type,
                action_params={},
                expected_impact=(
                    f"Success rate: {cluster.success_rate:.0%}, "
                    f"Avg reward: {cluster.avg_reward:.2f}"
                ),
                approval_level="auto",
                timeout_hours=24.0,
            )
        ]

    def _build_performance(
        self,
        cluster: StrategyCluster,
    ) -> StrategyPerformance:
        """构建表现统计."""
        quality = self._assign_quality(cluster.sample_size, cluster.success_rate)

        timestamps = sorted([e.timestamp for e in cluster.experiences])
        first_seen = timestamps[0] if timestamps else ""
        last_seen = timestamps[-1] if timestamps else ""

        return StrategyPerformance(
            total_executions=cluster.sample_size,
            successful_executions=cluster.success_count,
            success_rate=cluster.success_rate,
            avg_reward=cluster.avg_reward,
            quality=quality,
            first_seen=first_seen,
            last_seen=last_seen,
        )

    def _assign_quality(
        self,
        samples: int,
        success_rate: float,
    ) -> StrategyQuality:
        """根据样本数和成功率分配质量等级."""
        if samples >= 100 and success_rate >= 0.7:
            return StrategyQuality.PROVEN
        elif samples >= 30 and success_rate >= 0.6:
            return StrategyQuality.RELIABLE
        elif samples >= 10 and success_rate >= 0.5:
            return StrategyQuality.EMERGING
        elif samples >= 3 and success_rate >= 0.4:
            return StrategyQuality.EXPERIMENTAL
        return StrategyQuality.UNTESTED

    def _infer_category(self, cluster: StrategyCluster) -> StrategyCategory:
        """推断策略类别."""
        if not cluster.experiences:
            return StrategyCategory.GENERAL

        opp = cluster.experiences[0].context.opportunity_type
        if "creative_scale" in opp or "scale_opportunity" in opp:
            return StrategyCategory.CREATIVE_SCALE
        if "creative_fatigue" in opp or "creative_refresh" in opp:
            return StrategyCategory.CREATIVE_REVIVAL
        if "roas" in opp:
            return StrategyCategory.ROAS_RECOVERY
        if "budget" in opp:
            return StrategyCategory.BUDGET_OPTIMIZATION
        if "audience" in opp:
            return StrategyCategory.AUDIENCE_EXPANSION
        if cluster.action_type in ("launch_campaign", "create_population"):
            return StrategyCategory.NEW_LAUNCH
        return StrategyCategory.GENERAL

    def _generate_name(self, cluster: StrategyCluster) -> str:
        """生成策略名称."""
        action_name = cluster.action_type.replace("_", " ").title()
        opp = ""
        if cluster.experiences:
            opp = cluster.experiences[0].context.opportunity_type
            opp = opp.replace("_", " ").title() if opp else ""
        if opp:
            return f"{opp} → {action_name}"
        return f"{action_name} Strategy"

    def _generate_description(
        self,
        cluster: StrategyCluster,
        performance: StrategyPerformance,
    ) -> str:
        """生成策略描述."""
        return (
            f"Strategy for {cluster.action_type}. "
            f"Based on {cluster.sample_size} experiences. "
            f"Success rate: {performance.success_rate:.0%}, "
            f"Avg reward: {performance.avg_reward:.2f}."
        )

    def _extract_tags(self, cluster: StrategyCluster) -> list[str]:
        """提取标签."""
        tags: set[str] = {cluster.action_type}
        for exp in cluster.experiences:
            for tag in exp.tags:
                tags.add(tag)
        return sorted(tags)

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count


# ═══════════════════════════════════════════════════════════
# GrowthStrategyOptimizer
# ═══════════════════════════════════════════════════════════

class GrowthStrategyOptimizer:
    """增长策略优化器 — E14.7.4 核心入口.

    将 E14.7.3 的 GrowthExperience 自动提炼为可复用 Growth Strategy，
    存入 E13.4.3 StrategyMemory，供 E14.8 Autonomous Growth Agent 调用。

    流程:
      Experience Memory
           ↓
      StrategyExtractor.cluster()
           ↓
      StrategyEvaluator.evaluate()
           ↓
      StrategyMemory.store_batch()
           ↓
      E14.8 Autonomous Agent

    用法:
        optimizer = GrowthStrategyOptimizer(strategy_memory)
        patterns = optimizer.optimize(experiences)
        optimizer.optimize_and_store(experiences)
    """

    def __init__(
        self,
        strategy_memory: Any,
        extractor: StrategyExtractor | None = None,
        evaluator: StrategyEvaluator | None = None,
    ):
        """初始化优化器.

        Args:
            strategy_memory: E13.4.3 StrategyMemory 实例
            extractor: 自定义 StrategyExtractor
            evaluator: 自定义 StrategyEvaluator
        """
        self._strategy_memory = strategy_memory
        self._extractor = extractor or StrategyExtractor()
        self._evaluator = evaluator or StrategyEvaluator()
        self._optimization_count: int = 0
        self._last_optimize_result: list[GrowthStrategyPattern] = []

    # ── 核心: 优化 ────────────────────────────────────────

    def optimize(
        self,
        experiences: list[GrowthExperience],
    ) -> list[GrowthStrategyPattern]:
        """从经验中优化提炼策略.

        Args:
            experiences: GrowthExperience 列表

        Returns:
            list[GrowthStrategyPattern]: 按 score 降序的策略列表
        """
        self._optimization_count += 1

        # 提取聚类
        clusters = self._extractor.extract(experiences)

        if not clusters:
            return []

        # 评估并生成策略
        patterns = self._evaluator.evaluate(clusters)

        self._last_optimize_result = patterns
        return patterns

    def optimize_and_store(
        self,
        experiences: list[GrowthExperience],
    ) -> list[str]:
        """优化并自动存储策略.

        Args:
            experiences: GrowthExperience 列表

        Returns:
            list[str]: 存储的策略 ID 列表
        """
        patterns = self.optimize(experiences)
        return self._strategy_memory.store_batch(patterns)

    # ── 便捷方法 ──────────────────────────────────────────

    def optimize_from_store(self) -> list[str]:
        """从 ExperienceStore 获取经验并优化存储."""
        exp_store = getattr(self._strategy_memory, "_exp_store", None)
        if exp_store is None:
            return []

        experiences = exp_store.get_all()
        return self.optimize_and_store(experiences)

    def optimize_from_store_successful(self) -> list[str]:
        """从 ExperienceStore 获取成功经验并优化存储."""
        exp_store = getattr(self._strategy_memory, "_exp_store", None)
        if exp_store is None:
            return []

        experiences = exp_store.get_successful()
        return self.optimize_and_store(experiences)

    # ── 查询 ──────────────────────────────────────────────

    def get_top_strategies(self, n: int = 10) -> list[GrowthStrategyPattern]:
        """获取最高评分策略."""
        return self._strategy_memory.get_top_strategies(n)

    def get_actionable_strategies(self, n: int = 20) -> list[GrowthStrategyPattern]:
        """获取可执行策略."""
        return self._strategy_memory.get_actionable_strategies(n)

    def recommend(
        self,
        opportunity_type: str = "",
        signal_types: list[str] | None = None,
        top_n: int = 5,
    ) -> list[GrowthStrategyPattern]:
        """为机会推荐策略."""
        return self._strategy_memory.recommend(
            opportunity_type=opportunity_type,
            signal_types=signal_types,
            top_n=top_n,
        )

    def stats(self) -> dict[str, Any]:
        """获取优化器统计."""
        memory_stats = self._strategy_memory.get_stats()
        return {
            "optimization_count": self._optimization_count,
            "total_strategies": memory_stats.total_strategies,
            "total_actionable": memory_stats.total_actionable,
            "total_proven": memory_stats.total_proven,
            "avg_score": memory_stats.avg_score,
            "avg_executions": memory_stats.avg_executions,
            "last_optimize_count": len(self._last_optimize_result),
            "extractor_dimension": self._extractor.dimension,
            "extractor_min_samples": self._extractor.min_samples,
            "extraction_count": self._extractor.extraction_count,
            "evaluation_count": self._evaluator.evaluation_count,
        }

    def reset(self) -> None:
        """重置优化器状态."""
        self._optimization_count = 0
        self._last_optimize_result = []

    @property
    def strategy_memory(self) -> Any:
        return self._strategy_memory

    @property
    def extractor(self) -> StrategyExtractor:
        return self._extractor

    @property
    def evaluator(self) -> StrategyEvaluator:
        return self._evaluator

    @property
    def optimization_count(self) -> int:
        return self._optimization_count


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_strategy_optimizer(
    strategy_memory: Any,
    min_samples: int = 3,
    dimension: str = "opportunity_action",
    min_score: float = 0.0,
) -> GrowthStrategyOptimizer:
    """创建默认 GrowthStrategyOptimizer.

    Args:
        strategy_memory: E13.4.3 StrategyMemory 实例
        min_samples: 最小样本数
        dimension: 聚类维度
        min_score: 最低评分阈值

    Returns:
        GrowthStrategyOptimizer: 配置好的优化器
    """
    extractor = StrategyExtractor(min_samples=min_samples, dimension=dimension)
    evaluator = StrategyEvaluator(min_score=min_score)
    return GrowthStrategyOptimizer(
        strategy_memory=strategy_memory,
        extractor=extractor,
        evaluator=evaluator,
    )