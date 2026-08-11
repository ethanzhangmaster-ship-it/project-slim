"""E12.6.4 — Universal Pattern Library。

通用创意模式库。

保存和管理跨产品共享的创意规律。
支持:
  - 添加/查询通用模式
  - 按品类/市场/置信度筛选
  - 更新模式置信度
"""

from __future__ import annotations

from .models import (
    UniversalPattern,
)


class UniversalPatternLibrary:
    """通用创意模式库。

    存储跨产品验证过的创意模式。
    """

    def __init__(self, max_patterns: int = 1000) -> None:
        self.max_patterns = max_patterns
        self._patterns: dict[str, UniversalPattern] = {}
        self._by_type: dict[str, list[str]] = {}
        self._by_genre: dict[str, list[str]] = {}

    def add_pattern(self, pattern: UniversalPattern) -> None:
        """添加通用模式。

        Args:
            pattern: 通用模式
        """
        if len(self._patterns) >= self.max_patterns:
            # 移除最旧的模式
            oldest = min(self._patterns.values(), key=lambda p: p.created_at)
            self._remove_pattern(oldest.pattern_id)

        self._patterns[pattern.pattern_id] = pattern

        # 索引：按类型
        if pattern.pattern_type not in self._by_type:
            self._by_type[pattern.pattern_type] = []
        if pattern.pattern_id not in self._by_type[pattern.pattern_type]:
            self._by_type[pattern.pattern_type].append(pattern.pattern_id)

        # 索引：按品类
        for genre in pattern.applicable_genres:
            if genre not in self._by_genre:
                self._by_genre[genre] = []
            if pattern.pattern_id not in self._by_genre[genre]:
                self._by_genre[genre].append(pattern.pattern_id)

    def _remove_pattern(self, pattern_id: str) -> None:
        pattern = self._patterns.pop(pattern_id, None)
        if pattern is None:
            return
        if pattern.pattern_type in self._by_type:
            self._by_type[pattern.pattern_type] = [
                pid for pid in self._by_type[pattern.pattern_type] if pid != pattern_id
            ]
        for genre in pattern.applicable_genres:
            if genre in self._by_genre:
                self._by_genre[genre] = [
                    pid for pid in self._by_genre[genre] if pid != pattern_id
                ]

    def get_pattern(self, pattern_id: str) -> UniversalPattern | None:
        """获取指定模式。"""
        return self._patterns.get(pattern_id)

    def query(
        self,
        pattern_type: str | None = None,
        genre: str | None = None,
        min_confidence: float = 0.0,
        min_gain: float = 0.0,
        proven_only: bool = False,
        limit: int = 50,
    ) -> list[UniversalPattern]:
        """查询通用模式。

        Args:
            pattern_type:   按模式类型过滤
            genre:           按品类过滤
            min_confidence:  最低置信度
            min_gain:        最低性能提升
            proven_only:     仅返回已验证的模式
            limit:           最大返回数量

        Returns:
            UniversalPattern 列表
        """
        results: list[UniversalPattern] = []

        for pattern in self._patterns.values():
            if pattern_type and pattern.pattern_type != pattern_type:
                continue
            if genre and genre not in pattern.applicable_genres:
                continue
            if pattern.confidence < min_confidence:
                continue
            if pattern.performance_gain < min_gain:
                continue
            if proven_only and not pattern.is_proven:
                continue
            results.append(pattern)

        results.sort(key=lambda p: (p.confidence, p.performance_gain), reverse=True)
        return results[:limit]

    def get_by_type(self, pattern_type: str) -> list[UniversalPattern]:
        """按类型获取所有模式。"""
        pattern_ids = self._by_type.get(pattern_type, [])
        return [self._patterns[pid] for pid in pattern_ids if pid in self._patterns]

    def get_by_genre(self, genre: str) -> list[UniversalPattern]:
        """按品类获取所有模式。"""
        pattern_ids = self._by_genre.get(genre, [])
        return [self._patterns[pid] for pid in pattern_ids if pid in self._patterns]

    def update_confidence(
        self,
        pattern_id: str,
        new_confidence: float,
        new_gain: float | None = None,
    ) -> UniversalPattern | None:
        """更新模式置信度。

        Args:
            pattern_id:     模式 ID
            new_confidence: 新置信度
            new_gain:       新性能提升

        Returns:
            更新后的模式，或 None
        """
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None

        pattern.confidence = max(0.0, min(1.0, new_confidence))
        if new_gain is not None:
            pattern.performance_gain = new_gain

        return pattern

    def record_transfer(
        self,
        pattern_id: str,
        success: bool,
    ) -> None:
        """记录一次知识迁移。

        Args:
            pattern_id: 模式 ID
            success:    是否成功
        """
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return

        pattern.transfer_count += 1
        if success:
            pattern.success_count += 1

    def get_statistics(self) -> dict[str, int]:
        """获取模式库统计信息。"""
        return {
            "total_patterns": len(self._patterns),
            "by_type": {k: len(v) for k, v in self._by_type.items()},
            "proven_patterns": sum(1 for p in self._patterns.values() if p.is_proven),
            "total_transfers": sum(p.transfer_count for p in self._patterns.values()),
            "total_successes": sum(p.success_count for p in self._patterns.values()),
        }

    def get_all_patterns(self) -> list[UniversalPattern]:
        """获取所有模式。"""
        return list(self._patterns.values())

    def clear(self) -> None:
        """清空模式库。"""
        self._patterns.clear()
        self._by_type.clear()
        self._by_genre.clear()

    def __repr__(self) -> str:
        return (
            f"UniversalPatternLibrary(patterns={len(self._patterns)}, "
            f"max={self.max_patterns})"
        )