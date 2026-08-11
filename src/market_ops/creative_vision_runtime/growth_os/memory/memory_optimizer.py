"""E12.7.5 Memory Optimizer — 记忆治理: 衰减、提升、合并."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .experience_store import ExperienceStore
from .models import (
    GrowthExperience,
    GrowthPattern,
    MemoryType,
    Outcome,
)


class MemoryOptimizer:
    """记忆优化器 — 负责记忆治理.

    功能:
      - Confidence Decay: 时间衰减
      - Memory Promotion: 低价值经验 → 高价值模式
      - Memory Merge: 相似经验合并
      - Memory Cleanup: 清除过期/低质量记忆
    """

    def __init__(
        self,
        decay_factor: float = 0.95,
        low_confidence_threshold: float = 0.2,
        max_age_days: float = 365.0,
    ):
        self._decay_factor = decay_factor
        self._low_confidence_threshold = low_confidence_threshold
        self._max_age_days = max_age_days
        self._optimize_count: int = 0

    @property
    def optimize_count(self) -> int:
        return self._optimize_count

    # ── Confidence Decay ──────────────────────────────────────

    def apply_decay(self, store: ExperienceStore) -> dict[str, int]:
        """对所有经验和模式应用时间衰减."""
        self._optimize_count += 1
        stats: dict[str, int] = {"experiences_decayed": 0, "patterns_decayed": 0}

        for exp_id, exp in store._experiences.items():
            days = exp.age_days
            if days > 30:  # Start decaying after 30 days
                decay = self._decay_factor ** (days / 30.0)
                exp.confidence *= decay
                stats["experiences_decayed"] += 1

        for pat_id, pat in store._patterns.items():
            days = pat.age_days
            if days > 30:
                decay = self._decay_factor ** (days / 30.0)
                pat.confidence = max(0.0, pat.confidence * decay)
                stats["patterns_decayed"] += 1

        return stats

    def decay_experience(self, experience: GrowthExperience) -> GrowthExperience:
        """对单个经验应用时间衰减."""
        days = experience.age_days
        if days > 30:
            decay = self._decay_factor ** (days / 30.0)
            experience.confidence *= decay
        return experience

    def decay_pattern(self, pattern: GrowthPattern) -> GrowthPattern:
        """对单个模式应用时间衰减."""
        days = pattern.age_days
        if days > 30:
            decay = self._decay_factor ** (days / 30.0)
            pattern.confidence = max(0.0, pattern.confidence * decay)
        return pattern

    # ── Memory Promotion ──────────────────────────────────────

    def promote_to_pattern(
        self, experiences: list[GrowthExperience], learner,
    ) -> list[GrowthPattern]:
        """将高价值经验提升为模式."""
        patterns = learner.learn(experiences)
        # Filter: only keep patterns with high enough confidence
        return [p for p in patterns if p.confidence >= 0.5]

    def should_promote(self, experience: GrowthExperience) -> bool:
        """判断经验是否应该被提升为模式."""
        return (
            experience.learning_value >= 0.7
            and experience.confidence >= 0.7
            and experience.is_success
        )

    # ── Memory Merge ──────────────────────────────────────────

    def merge_similar_experiences(
        self, experiences: list[GrowthExperience], learner,
    ) -> GrowthPattern | None:
        """合并相似经验为一个模式."""
        if len(experiences) < 2:
            return None

        # Check similarity
        similarity_threshold = 0.5
        groups = self._group_by_similarity(experiences, learner, similarity_threshold)

        if not groups:
            return None

        # Take the largest group
        largest_group = max(groups, key=len)
        if len(largest_group) < 2:
            return None

        patterns = learner.learn(largest_group)
        if patterns:
            return patterns[0]
        return None

    def _group_by_similarity(
        self,
        experiences: list[GrowthExperience],
        learner,
        threshold: float,
    ) -> list[list[GrowthExperience]]:
        """按相似度分组."""
        groups: list[list[GrowthExperience]] = []
        used: set[int] = set()

        for i, exp1 in enumerate(experiences):
            if i in used:
                continue
            group = [exp1]
            used.add(i)
            for j, exp2 in enumerate(experiences):
                if j in used:
                    continue
                if learner.compute_similarity(exp1, exp2) >= threshold:
                    group.append(exp2)
                    used.add(j)
            groups.append(group)

        return groups

    def merge_patterns(self, patterns: list[GrowthPattern]) -> GrowthPattern | None:
        """合并相似模式."""
        if len(patterns) < 2:
            return None

        # Average all metrics
        avg_success_rate = sum(p.success_rate for p in patterns) / len(patterns)
        avg_roas = sum(p.avg_roas for p in patterns) / len(patterns)
        avg_confidence = sum(p.confidence for p in patterns) / len(patterns)
        total_usage = sum(p.usage_count for p in patterns)

        all_sources: list[str] = []
        for p in patterns:
            all_sources.extend(p.source_experiences)

        merged_conditions: dict[str, Any] = {}
        for p in patterns:
            merged_conditions.update(p.conditions)

        merged_actions: list[dict[str, Any]] = []
        seen_actions: set[str] = set()
        for p in patterns:
            for action in p.actions:
                key = action.get("task_type", "")
                if key not in seen_actions:
                    merged_actions.append(action)
                    seen_actions.add(key)

        return GrowthPattern(
            pattern_type=patterns[0].pattern_type,
            conditions=merged_conditions,
            actions=merged_actions,
            success_rate=avg_success_rate,
            avg_roas=avg_roas,
            confidence=avg_confidence,
            usage_count=total_usage,
            source_experiences=list(set(all_sources)),
            market=patterns[0].market,
            product_id=patterns[0].product_id,
            description=f"Merged pattern from {len(patterns)} patterns",
        )

    # ── Memory Cleanup ────────────────────────────────────────

    def cleanup(self, store: ExperienceStore) -> dict[str, int]:
        """清除过期和低质量记忆."""
        self._optimize_count += 1
        stats: dict[str, int] = {
            "experiences_removed": 0,
            "patterns_removed": 0,
        }

        # Remove low confidence experiences
        to_remove: list[str] = []
        for exp_id, exp in store._experiences.items():
            if exp.confidence < self._low_confidence_threshold:
                to_remove.append(exp_id)
            elif exp.age_days > self._max_age_days:
                to_remove.append(exp_id)

        for exp_id in to_remove:
            store.delete(exp_id)
            stats["experiences_removed"] += 1

        # Remove low confidence patterns
        pat_to_remove: list[str] = []
        for pat_id, pat in store._patterns.items():
            if pat.confidence < self._low_confidence_threshold:
                pat_to_remove.append(pat_id)
            elif pat.age_days > self._max_age_days * 2:
                pat_to_remove.append(pat_id)

        for pat_id in pat_to_remove:
            store.delete_pattern(pat_id)
            stats["patterns_removed"] += 1

        return stats

    def get_high_value_experiences(
        self, store: ExperienceStore, threshold: float = 0.7,
    ) -> list[GrowthExperience]:
        """获取高价值经验."""
        return [
            e for e in store.get_all()
            if e.learning_value >= threshold and e.confidence >= threshold
        ]

    def get_low_value_experiences(
        self, store: ExperienceStore, threshold: float = 0.3,
    ) -> list[GrowthExperience]:
        """获取低价值经验."""
        return [
            e for e in store.get_all()
            if e.learning_value < threshold or e.confidence < self._low_confidence_threshold
        ]

    def get_summary(self) -> dict[str, Any]:
        return {
            "optimize_count": self.optimize_count,
            "decay_factor": self._decay_factor,
            "low_confidence_threshold": self._low_confidence_threshold,
            "max_age_days": self._max_age_days,
        }