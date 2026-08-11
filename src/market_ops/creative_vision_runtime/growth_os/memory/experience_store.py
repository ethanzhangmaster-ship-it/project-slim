"""E12.7.5 Experience Store — 长期经验数据库抽象层."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import (
    GrowthExperience,
    GrowthPattern,
    MemoryType,
    Outcome,
)


class ExperienceStore:
    """经验存储 — 管理所有 GrowthExperience 和 GrowthPattern 的持久化.

    支持: 保存、查询、搜索、按产品/结果筛选。
    """

    def __init__(self):
        self._experiences: dict[str, GrowthExperience] = {}
        self._patterns: dict[str, GrowthPattern] = {}
        self._by_product: dict[str, list[str]] = defaultdict(list)
        self._by_type: dict[MemoryType, list[str]] = defaultdict(list)
        self._by_result: dict[Outcome, list[str]] = defaultdict(list)
        self._by_tag: dict[str, list[str]] = defaultdict(list)

    # ── Properties ────────────────────────────────────────────

    @property
    def experience_count(self) -> int:
        return len(self._experiences)

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    @property
    def total_count(self) -> int:
        return self.experience_count + self.pattern_count

    # ── Save ──────────────────────────────────────────────────

    def save(self, experience: GrowthExperience) -> GrowthExperience:
        """保存经验."""
        self._experiences[experience.experience_id] = experience
        self._by_product[experience.product_id].append(experience.experience_id)
        self._by_type[experience.memory_type].append(experience.experience_id)
        self._by_result[experience.result].append(experience.experience_id)
        for tag in experience.tags:
            self._by_tag[tag].append(experience.experience_id)
        return experience

    def save_batch(self, experiences: list[GrowthExperience]) -> list[GrowthExperience]:
        """批量保存经验."""
        return [self.save(e) for e in experiences]

    def save_pattern(self, pattern: GrowthPattern) -> GrowthPattern:
        """保存模式."""
        self._patterns[pattern.pattern_id] = pattern
        return pattern

    def save_patterns(self, patterns: list[GrowthPattern]) -> list[GrowthPattern]:
        """批量保存模式."""
        return [self.save_pattern(p) for p in patterns]

    # ── Query ─────────────────────────────────────────────────

    def get(self, experience_id: str) -> GrowthExperience | None:
        """按 ID 获取经验."""
        return self._experiences.get(experience_id)

    def get_pattern(self, pattern_id: str) -> GrowthPattern | None:
        """按 ID 获取模式."""
        return self._patterns.get(pattern_id)

    def get_all(self) -> list[GrowthExperience]:
        """获取所有经验."""
        return list(self._experiences.values())

    def get_all_patterns(self) -> list[GrowthPattern]:
        """获取所有模式."""
        return list(self._patterns.values())

    def get_by_product(self, product_id: str) -> list[GrowthExperience]:
        """按产品获取经验."""
        ids = self._by_product.get(product_id, [])
        return [self._experiences[eid] for eid in ids if eid in self._experiences]

    def get_by_type(self, memory_type: MemoryType) -> list[GrowthExperience]:
        """按类型获取经验."""
        ids = self._by_type.get(memory_type, [])
        return [self._experiences[eid] for eid in ids if eid in self._experiences]

    def get_by_result(self, outcome: Outcome) -> list[GrowthExperience]:
        """按结果获取经验."""
        ids = self._by_result.get(outcome, [])
        return [self._experiences[eid] for eid in ids if eid in self._experiences]

    def get_by_tag(self, tag: str) -> list[GrowthExperience]:
        """按标签获取经验."""
        ids = self._by_tag.get(tag, [])
        return [self._experiences[eid] for eid in ids if eid in self._experiences]

    def get_success_cases(self) -> list[GrowthExperience]:
        """获取所有成功案例."""
        return self.get_by_result(Outcome.SUCCESS)

    def get_failure_cases(self) -> list[GrowthExperience]:
        """获取所有失败案例."""
        return self.get_by_result(Outcome.FAILURE)

    def get_by_strategy(self, strategy_id: str) -> list[GrowthExperience]:
        """按策略 ID 获取经验."""
        return [e for e in self._experiences.values() if e.strategy_id == strategy_id]

    def get_by_execution(self, execution_id: str) -> list[GrowthExperience]:
        """按执行 ID 获取经验."""
        return [e for e in self._experiences.values() if e.execution_id == execution_id]

    # ── Search ────────────────────────────────────────────────

    def search(self, keywords: list[str], limit: int = 10) -> list[GrowthExperience]:
        """关键词搜索经验."""
        scored: list[tuple[float, GrowthExperience]] = []
        for exp in self._experiences.values():
            score = self._keyword_score(exp, keywords)
            if score > 0:
                scored.append((score, exp))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def search_patterns(self, keywords: list[str], limit: int = 10) -> list[GrowthPattern]:
        """关键词搜索模式."""
        scored: list[tuple[float, GrowthPattern]] = []
        for pat in self._patterns.values():
            score = self._pattern_keyword_score(pat, keywords)
            if score > 0:
                scored.append((score, pat))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:limit]]

    def _keyword_score(self, exp: GrowthExperience, keywords: list[str]) -> float:
        """计算经验与关键词的匹配分数."""
        score = 0.0
        text = (
            exp.summary.lower() + " "
            + " ".join(exp.tags).lower() + " "
            + " ".join(str(v) for v in exp.action.values()).lower() + " "
            + exp.context.market.lower() + " "
            + exp.context.channel.lower()
        )
        for kw in keywords:
            if kw.lower() in text:
                score += 1.0
        return score

    def _pattern_keyword_score(self, pat: GrowthPattern, keywords: list[str]) -> float:
        """计算模式与关键词的匹配分数."""
        score = 0.0
        text = (
            pat.description.lower() + " "
            + " ".join(str(v) for v in pat.conditions.values()).lower() + " "
            + pat.market.lower()
        )
        for kw in keywords:
            if kw.lower() in text:
                score += 1.0
        return score

    # ── Delete ────────────────────────────────────────────────

    def delete(self, experience_id: str) -> bool:
        """删除经验."""
        exp = self._experiences.pop(experience_id, None)
        if exp is None:
            return False
        self._by_product[exp.product_id].remove(experience_id)
        self._by_type[exp.memory_type].remove(experience_id)
        self._by_result[exp.result].remove(experience_id)
        for tag in exp.tags:
            if experience_id in self._by_tag[tag]:
                self._by_tag[tag].remove(experience_id)
        return True

    def delete_pattern(self, pattern_id: str) -> bool:
        """删除模式."""
        return self._patterns.pop(pattern_id, None) is not None

    def clear(self) -> None:
        """清空所有数据."""
        self._experiences.clear()
        self._patterns.clear()
        self._by_product.clear()
        self._by_type.clear()
        self._by_result.clear()
        self._by_tag.clear()

    # ── Statistics ────────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """获取存储统计."""
        return {
            "experience_count": self.experience_count,
            "pattern_count": self.pattern_count,
            "total_count": self.total_count,
            "by_type": {t.value: len(ids) for t, ids in self._by_type.items()},
            "by_result": {r.value: len(ids) for r, ids in self._by_result.items()},
            "by_product": dict(self._by_product),
            "success_rate": self._compute_success_rate(),
        }

    def _compute_success_rate(self) -> float:
        total = self.experience_count
        if total == 0:
            return 0.0
        return len(self._by_result.get(Outcome.SUCCESS, [])) / total