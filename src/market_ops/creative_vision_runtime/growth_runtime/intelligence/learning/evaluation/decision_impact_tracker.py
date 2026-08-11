"""E13.7.6 Decision Impact Tracker — 决策质量追踪器.

Day 7.6.1:
  追踪每次决策的 before/after 质量，
  记录学习增强前后的评分、置信度变化，以及实际执行结果。

核心功能:
  - capture_baseline(): 捕获学习增强前的决策质量
  - capture_enhanced(): 捕获学习增强后的决策质量
  - record_outcome(): 记录实际执行结果
  - get_stats(): 获取基线 vs 增强的统计对比

设计原则:
  - 纯追踪器，不修改决策结果
  - 支持按维度分组统计 (action_type, strategy, opportunity_type)
  - 内存存储，可扩展到外部存储
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .models import DecisionQualitySnapshot


class DecisionImpactTracker:
    """决策质量追踪器 — 追踪学习对决策质量的影响.

    用法:
        tracker = DecisionImpactTracker(max_history=1000)

        # 决策前: 捕获基线
        snapshot = tracker.capture_baseline(
            decision_id="d_001",
            decision_type="EXECUTE",
            strategy_name="scale_winning",
            action_type="increase_budget",
            baseline_score=0.65,
            baseline_confidence=0.72,
        )

        # 学习增强后: 捕获增强结果
        tracker.capture_enhanced(
            snapshot=snapshot,
            enhanced_score=0.78,
            enhanced_confidence=0.85,
            enhancer_recommendation="approve",
            enhancer_confidence=0.79,
        )

        # 执行后: 记录结果
        tracker.record_outcome(
            snapshot_id=snapshot.snapshot_id,
            success=True,
            reward=0.72,
        )

        # 查看统计
        stats = tracker.get_stats()
    """

    def __init__(self, max_history: int = 1000) -> None:
        """初始化追踪器.

        Args:
            max_history: 最大历史记录数
        """
        self._max_history = max_history
        self._snapshots: dict[str, DecisionQualitySnapshot] = {}
        self._snapshot_order: list[str] = []

    @property
    def total_snapshots(self) -> int:
        """总快照数."""
        return len(self._snapshots)

    @property
    def completed_snapshots(self) -> int:
        """有实际结果的快照数."""
        return sum(1 for s in self._snapshots.values() if s.has_outcome)

    # ── Public API ───────────────────────────────────────────────

    def capture_baseline(
        self,
        decision_id: str = "",
        decision_type: str = "",
        strategy_name: str = "",
        action_type: str = "",
        opportunity_type: str = "",
        baseline_score: float = 0.0,
        baseline_confidence: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionQualitySnapshot:
        """捕获学习增强前的决策质量基线.

        Args:
            decision_id: 决策 ID
            decision_type: 决策类型
            strategy_name: 策略名称
            action_type: 动作类型
            opportunity_type: 机会类型
            baseline_score: 基线评分
            baseline_confidence: 基线置信度
            metadata: 扩展元数据

        Returns:
            DecisionQualitySnapshot: 决策质量快照
        """
        snapshot = DecisionQualitySnapshot(
            decision_id=decision_id,
            decision_type=decision_type,
            strategy_name=strategy_name,
            action_type=action_type,
            opportunity_type=opportunity_type,
            baseline_score=baseline_score,
            baseline_confidence=baseline_confidence,
            enhanced_score=baseline_score,  # 默认与基线相同
            enhanced_confidence=baseline_confidence,
            learning_enhanced=False,
            metadata=metadata or {},
        )
        self._store(snapshot)
        return snapshot

    def capture_enhanced(
        self,
        snapshot: DecisionQualitySnapshot,
        enhanced_score: float = 0.0,
        enhanced_confidence: float = 0.0,
        enhancer_recommendation: str = "",
        enhancer_confidence: float = 0.0,
    ) -> DecisionQualitySnapshot:
        """捕获学习增强后的决策质量.

        Args:
            snapshot: 已有的基线快照
            enhanced_score: 增强后评分
            enhanced_confidence: 增强后置信度
            enhancer_recommendation: 增强器推荐
            enhancer_confidence: 增强器置信度

        Returns:
            DecisionQualitySnapshot: 更新后的快照
        """
        snapshot.enhanced_score = enhanced_score
        snapshot.enhanced_confidence = enhanced_confidence
        snapshot.learning_enhanced = True
        snapshot.enhancer_recommendation = enhancer_recommendation
        snapshot.enhancer_confidence = enhancer_confidence
        snapshot.score_adjustment = enhanced_score - snapshot.baseline_score
        self._store(snapshot)
        return snapshot

    def record_outcome(
        self,
        snapshot_id: str,
        success: bool = False,
        reward: float = 0.0,
    ) -> DecisionQualitySnapshot | None:
        """记录实际执行结果.

        Args:
            snapshot_id: 快照 ID
            success: 是否成功
            reward: 实际奖励

        Returns:
            更新后的快照，不存在则返回 None
        """
        if snapshot_id not in self._snapshots:
            return None
        snapshot = self._snapshots[snapshot_id]
        snapshot.actual_outcome = "success" if success else "failure"
        snapshot.actual_reward = reward
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> DecisionQualitySnapshot | None:
        """获取单个快照."""
        return self._snapshots.get(snapshot_id)

    def get_history(self) -> list[DecisionQualitySnapshot]:
        """获取所有快照 (按时间顺序)."""
        return [self._snapshots[sid] for sid in self._snapshot_order if sid in self._snapshots]

    def get_enhanced_snapshots(self) -> list[DecisionQualitySnapshot]:
        """获取使用学习增强的快照."""
        return [s for s in self._snapshots.values() if s.learning_enhanced]

    def get_baseline_only_snapshots(self) -> list[DecisionQualitySnapshot]:
        """获取未使用学习增强的快照."""
        return [s for s in self._snapshots.values() if not s.learning_enhanced]

    def get_completed_snapshots(self) -> list[DecisionQualitySnapshot]:
        """获取有实际结果的快照."""
        return [s for s in self._snapshots.values() if s.has_outcome]

    def get_stats(self) -> dict[str, Any]:
        """获取统计对比.

        Returns:
            dict with baseline_stats and enhanced_stats
        """
        all_snapshots = list(self._snapshots.values())
        enhanced = self.get_enhanced_snapshots()
        baseline_only = self.get_baseline_only_snapshots()
        completed = self.get_completed_snapshots()

        # 基线统计 (所有快照)
        baseline_scores = [s.baseline_score for s in all_snapshots]
        baseline_confs = [s.baseline_confidence for s in all_snapshots]

        # 增强统计
        enhanced_scores = [s.enhanced_score for s in enhanced]
        enhanced_confs = [s.enhanced_confidence for s in enhanced]

        # 成功率统计 (有结果的快照)
        completed_enhanced = [s for s in completed if s.learning_enhanced]
        completed_baseline = [s for s in completed if not s.learning_enhanced]

        baseline_success_rate = (
            sum(1 for s in completed_baseline if s.is_success) / len(completed_baseline)
            if completed_baseline else 0.0
        )
        enhanced_success_rate = (
            sum(1 for s in completed_enhanced if s.is_success) / len(completed_enhanced)
            if completed_enhanced else 0.0
        )

        return {
            "total_snapshots": self.total_snapshots,
            "completed_snapshots": self.completed_snapshots,
            "learning_enhanced_count": len(enhanced),
            "baseline_only_count": len(baseline_only),
            "baseline_stats": {
                "avg_score": round(self._mean(baseline_scores), 4),
                "avg_confidence": round(self._mean(baseline_confs), 4),
                "success_rate": round(baseline_success_rate, 4),
                "sample_count": len(completed_baseline),
            },
            "enhanced_stats": {
                "avg_score": round(self._mean(enhanced_scores), 4),
                "avg_confidence": round(self._mean(enhanced_confs), 4),
                "success_rate": round(enhanced_success_rate, 4),
                "avg_score_adjustment": round(
                    self._mean([s.score_adjustment for s in enhanced]), 4
                ),
                "sample_count": len(completed_enhanced),
            },
            "learning_gain": round(enhanced_success_rate - baseline_success_rate, 4),
        }

    def get_stats_by_dimension(
        self, dimension: str = "action_type"
    ) -> dict[str, dict[str, Any]]:
        """按维度分组统计.

        Args:
            dimension: 分组维度 (action_type/strategy_name/opportunity_type)

        Returns:
            {dimension_value: stats_dict}
        """
        groups: dict[str, list[DecisionQualitySnapshot]] = defaultdict(list)
        for s in self._snapshots.values():
            key = getattr(s, dimension, "unknown")
            groups[key].append(s)

        result: dict[str, dict[str, Any]] = {}
        for key, snapshots in groups.items():
            enhanced = [s for s in snapshots if s.learning_enhanced]
            result[key] = {
                "total": len(snapshots),
                "enhanced_count": len(enhanced),
                "avg_baseline_score": round(
                    self._mean([s.baseline_score for s in snapshots]), 4
                ),
                "avg_enhanced_score": round(
                    self._mean([s.enhanced_score for s in enhanced]), 4
                ) if enhanced else 0.0,
                "avg_score_adjustment": round(
                    self._mean([s.score_adjustment for s in enhanced]), 4
                ) if enhanced else 0.0,
            }
        return result

    def clear(self) -> None:
        """清空所有追踪记录."""
        self._snapshots.clear()
        self._snapshot_order.clear()

    # ── Internal ─────────────────────────────────────────────────

    def _store(self, snapshot: DecisionQualitySnapshot) -> None:
        """存储快照并维护大小限制."""
        sid = snapshot.snapshot_id
        if sid not in self._snapshots:
            self._snapshot_order.append(sid)
        self._snapshots[sid] = snapshot
        self._trim()

    def _trim(self) -> None:
        """超出最大历史数时删除最旧记录."""
        while len(self._snapshot_order) > self._max_history:
            oldest = self._snapshot_order.pop(0)
            self._snapshots.pop(oldest, None)

    @staticmethod
    def _mean(values: list[float]) -> float:
        """计算平均值."""
        if not values:
            return 0.0
        return sum(values) / len(values)