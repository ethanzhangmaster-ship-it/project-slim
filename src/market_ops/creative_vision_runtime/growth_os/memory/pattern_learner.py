"""E12.7.5 Pattern Learner — 从大量经验中发现增长规律."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import (
    GrowthExperience,
    GrowthPattern,
    MemoryType,
    Outcome,
)


class PatternLearner:
    """模式学习器 — 从经验中抽象出 GrowthPattern.

    算法: 聚类 + 相似度匹配 + 成功率统计 + 时间衰减.
    """

    def __init__(self, min_experiences: int = 3, min_success_rate: float = 0.5):
        self._min_experiences = min_experiences
        self._min_success_rate = min_success_rate
        self._learn_count: int = 0

    @property
    def learn_count(self) -> int:
        return self._learn_count

    # ── Learn Patterns ────────────────────────────────────────

    def learn(self, experiences: list[GrowthExperience]) -> list[GrowthPattern]:
        """从经验列表中学习模式."""
        self._learn_count += 1
        patterns: list[GrowthPattern] = []

        # Cluster by product_id
        by_product = self._cluster_by_product(experiences)
        for product_id, product_exps in by_product.items():
            patterns.extend(self._learn_product_patterns(product_id, product_exps))

        # Cluster by market
        by_market = self._cluster_by_market(experiences)
        for market, market_exps in by_market.items():
            patterns.extend(self._learn_market_patterns(market, market_exps))

        # Cluster by memory type
        by_type = self._cluster_by_type(experiences)
        for mtype, type_exps in by_type.items():
            patterns.extend(self._learn_type_patterns(mtype, type_exps))

        return patterns

    def _cluster_by_product(
        self, experiences: list[GrowthExperience],
    ) -> dict[str, list[GrowthExperience]]:
        clusters: dict[str, list[GrowthExperience]] = defaultdict(list)
        for exp in experiences:
            clusters[exp.product_id].append(exp)
        return dict(clusters)

    def _cluster_by_market(
        self, experiences: list[GrowthExperience],
    ) -> dict[str, list[GrowthExperience]]:
        clusters: dict[str, list[GrowthExperience]] = defaultdict(list)
        for exp in experiences:
            market = exp.context.market or "unknown"
            clusters[market].append(exp)
        return dict(clusters)

    def _cluster_by_type(
        self, experiences: list[GrowthExperience],
    ) -> dict[MemoryType, list[GrowthExperience]]:
        clusters: dict[MemoryType, list[GrowthExperience]] = defaultdict(list)
        for exp in experiences:
            clusters[exp.memory_type].append(exp)
        return dict(clusters)

    def _learn_product_patterns(
        self, product_id: str, experiences: list[GrowthExperience],
    ) -> list[GrowthPattern]:
        """学习产品级别的模式."""
        patterns: list[GrowthPattern] = []

        if len(experiences) < self._min_experiences:
            return patterns

        # Group by action similarity
        action_groups = self._cluster_by_action_similarity(experiences)
        for action_key, exps in action_groups.items():
            if len(exps) < self._min_experiences:
                continue
            pattern = self._build_pattern_from_group(
                exps, product_id=product_id, pattern_type=MemoryType.STRATEGY_MEMORY,
            )
            if pattern is not None:
                patterns.append(pattern)

        return patterns

    def _learn_market_patterns(
        self, market: str, experiences: list[GrowthExperience],
    ) -> list[GrowthPattern]:
        """学习市场级别的模式."""
        patterns: list[GrowthPattern] = []

        if len(experiences) < self._min_experiences:
            return patterns

        # Group by outcome
        success_exps = [e for e in experiences if e.is_success]
        if len(success_exps) >= self._min_experiences:
            pattern = self._build_pattern_from_group(
                success_exps, market=market, pattern_type=MemoryType.SUCCESS_PATTERN,
            )
            if pattern is not None:
                patterns.append(pattern)

        failure_exps = [e for e in experiences if e.is_failure]
        if len(failure_exps) >= self._min_experiences:
            pattern = self._build_pattern_from_group(
                failure_exps, market=market, pattern_type=MemoryType.FAILURE_MEMORY,
            )
            if pattern is not None:
                patterns.append(pattern)

        return patterns

    def _learn_type_patterns(
        self, memory_type: MemoryType, experiences: list[GrowthExperience],
    ) -> list[GrowthPattern]:
        """学习类型级别的模式."""
        patterns: list[GrowthPattern] = []

        if len(experiences) < self._min_experiences:
            return patterns

        action_groups = self._cluster_by_action_similarity(experiences)
        for action_key, exps in action_groups.items():
            if len(exps) < self._min_experiences:
                continue
            pattern = self._build_pattern_from_group(
                exps, pattern_type=memory_type,
            )
            if pattern is not None:
                patterns.append(pattern)

        return patterns

    # ── Clustering ────────────────────────────────────────────

    def _cluster_by_action_similarity(
        self, experiences: list[GrowthExperience],
    ) -> dict[str, list[GrowthExperience]]:
        """按动作相似度聚类."""
        groups: dict[str, list[GrowthExperience]] = defaultdict(list)
        for exp in experiences:
            key = self._action_key(exp)
            groups[key].append(exp)
        return dict(groups)

    def _action_key(self, exp: GrowthExperience) -> str:
        """生成动作聚类键."""
        task_type = exp.action.get("task_type", "unknown")
        return f"{task_type}"

    # ── Pattern Building ──────────────────────────────────────

    def _build_pattern_from_group(
        self,
        experiences: list[GrowthExperience],
        product_id: str = "",
        market: str = "",
        pattern_type: MemoryType = MemoryType.SUCCESS_PATTERN,
    ) -> GrowthPattern | None:
        """从一组经验构建模式."""
        if len(experiences) < self._min_experiences:
            return None

        success_count = sum(1 for e in experiences if e.is_success)
        success_rate = success_count / len(experiences)

        if success_rate < self._min_success_rate and pattern_type == MemoryType.SUCCESS_PATTERN:
            return None

        avg_roas = self._compute_avg_roas(experiences)
        avg_confidence = sum(e.confidence for e in experiences) / len(experiences)

        # Time-decay weighted confidence
        time_weight = self._time_decay_weight(experiences)
        confidence = avg_confidence * time_weight

        conditions = self._extract_common_conditions(experiences)
        actions = self._extract_common_actions(experiences)
        description = self._build_description(experiences, success_rate, avg_roas)

        source_ids = [e.experience_id for e in experiences]

        return GrowthPattern(
            pattern_type=pattern_type,
            conditions=conditions,
            actions=actions,
            success_rate=success_rate,
            avg_roas=avg_roas,
            confidence=confidence,
            usage_count=len(experiences),
            source_experiences=source_ids,
            market=market or experiences[0].context.market,
            product_id=product_id or experiences[0].product_id,
            description=description,
        )

    def _compute_avg_roas(self, experiences: list[GrowthExperience]) -> float:
        values = [e.metrics.roas for e in experiences if e.metrics.roas > 0]
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _time_decay_weight(self, experiences: list[GrowthExperience]) -> float:
        """时间衰减权重 — 越新的经验权重越高."""
        now = datetime.now(timezone.utc)
        weights: list[float] = []
        for exp in experiences:
            age_days = (now - exp.created_at).total_seconds() / 86400.0
            decay = max(0.3, 1.0 - age_days / 365.0)  # Linear decay over 1 year
            weights.append(decay)
        if not weights:
            return 1.0
        return sum(weights) / len(weights)

    def _extract_common_conditions(self, experiences: list[GrowthExperience]) -> dict[str, Any]:
        """提取共同条件."""
        markets = list({e.context.market for e in experiences if e.context.market})
        channels = list({e.context.channel for e in experiences if e.context.channel})
        lifecycles = list({e.context.lifecycle for e in experiences if e.context.lifecycle})

        return {
            "markets": markets,
            "channels": channels,
            "lifecycles": lifecycles,
            "product_id": experiences[0].product_id,
            "experience_count": len(experiences),
        }

    def _extract_common_actions(self, experiences: list[GrowthExperience]) -> list[dict[str, Any]]:
        """提取共同动作."""
        # Count action frequency
        action_counts: dict[str, int] = defaultdict(int)
        action_examples: dict[str, dict[str, Any]] = {}
        for exp in experiences:
            task_type = exp.action.get("task_type", "unknown")
            action_counts[task_type] += 1
            if task_type not in action_examples:
                action_examples[task_type] = exp.action

        # Sort by frequency
        sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        return [action_examples[at] for at, _ in sorted_actions[:5]]

    def _build_description(
        self,
        experiences: list[GrowthExperience],
        success_rate: float,
        avg_roas: float,
    ) -> str:
        """构建模式描述."""
        product = experiences[0].product_id
        market = experiences[0].context.market or "unknown"
        task_types = list({e.action.get("task_type", "") for e in experiences})
        action_desc = "+".join(task_types[:3])

        return (
            f"Pattern: {product} in {market} — {action_desc} "
            f"→ Success Rate: {success_rate:.0%}, Avg ROAS: {avg_roas:.2f} "
            f"(n={len(experiences)})"
        )

    # ── Similarity ────────────────────────────────────────────

    def compute_similarity(
        self, exp1: GrowthExperience, exp2: GrowthExperience,
    ) -> float:
        """计算两个经验之间的相似度."""
        score = 0.0
        if exp1.product_id == exp2.product_id:
            score += 0.3
        if exp1.context.market == exp2.context.market:
            score += 0.2
        if exp1.context.channel == exp2.context.channel:
            score += 0.15
        if exp1.memory_type == exp2.memory_type:
            score += 0.15
        if self._action_key(exp1) == self._action_key(exp2):
            score += 0.2
        return min(1.0, score)

    def find_similar(
        self, target: GrowthExperience, candidates: list[GrowthExperience], limit: int = 5,
    ) -> list[GrowthExperience]:
        """找到与目标最相似的经验."""
        scored = [(self.compute_similarity(target, c), c) for c in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]