"""E11.5.1 Feedback Repository — 反馈存储。

保存和查询 PerformanceFeedback 历史记录。

接口：
  save()               — 保存反馈
  get_by_creative()    — 按创意 ID 查询
  get_by_campaign()    — 按广告系列查询
  get_by_source()      — 按数据源查询
  get_by_period()      — 按时间段查询
  history()            — 获取全部历史
  latest()             — 获取最新反馈

数据流：
  PerformanceFeedback → FeedbackRepository → E11.5.3 Fitness Engine
"""

from __future__ import annotations

from typing import Any

from .feedback_schema import PerformanceFeedback


class FeedbackRepository:
    """反馈存储。

    提供 PerformanceFeedback 的 CRUD 和查询功能。

    Usage:
        repo = FeedbackRepository()
        repo.save(feedback)
        results = repo.get_by_creative("creative_001")
        history = repo.history()
    """

    def __init__(self) -> None:
        self._feedbacks: dict[str, PerformanceFeedback] = {}

    # ── 写入 ──────────────────────────────────────────

    def save(self, feedback: PerformanceFeedback) -> None:
        """保存一条反馈。

        Args:
            feedback: PerformanceFeedback 实例
        """
        self._feedbacks[feedback.feedback_id] = feedback

    def save_batch(self, feedbacks: list[PerformanceFeedback]) -> None:
        """批量保存反馈。

        Args:
            feedbacks: PerformanceFeedback 列表
        """
        for fb in feedbacks:
            self._feedbacks[fb.feedback_id] = fb

    # ── 查询 ──────────────────────────────────────────

    def get(self, feedback_id: str) -> PerformanceFeedback | None:
        """按 ID 获取反馈。"""
        return self._feedbacks.get(feedback_id)

    def get_by_creative(self, creative_id: str) -> list[PerformanceFeedback]:
        """按创意 ID 查询所有反馈。

        Args:
            creative_id: 创意 ID

        Returns:
            匹配的反馈列表（按时间降序）
        """
        results = [
            fb for fb in self._feedbacks.values()
            if fb.creative_id == creative_id
        ]
        return sorted(results, key=lambda fb: fb.created_at, reverse=True)

    def get_by_campaign(self, campaign_id: str) -> list[PerformanceFeedback]:
        """按广告系列 ID 查询所有反馈。

        Args:
            campaign_id: 广告系列 ID

        Returns:
            匹配的反馈列表（按时间降序）
        """
        results = [
            fb for fb in self._feedbacks.values()
            if fb.campaign_id == campaign_id
        ]
        return sorted(results, key=lambda fb: fb.created_at, reverse=True)

    def get_by_source(self, source: str) -> list[PerformanceFeedback]:
        """按数据源查询所有反馈。

        Args:
            source: 数据源 ("facebook", "google", "asa", "tiktok")

        Returns:
            匹配的反馈列表
        """
        results = [
            fb for fb in self._feedbacks.values()
            if fb.source == source
        ]
        return sorted(results, key=lambda fb: fb.created_at, reverse=True)

    def get_by_period(self, period: str) -> list[PerformanceFeedback]:
        """按时间段查询所有反馈。

        Args:
            period: 时间段 ("2026-01-01_to_2026-01-07")

        Returns:
            匹配的反馈列表
        """
        results = [
            fb for fb in self._feedbacks.values()
            if fb.period == period
        ]
        return sorted(results, key=lambda fb: fb.created_at, reverse=True)

    def get_complete(self) -> list[PerformanceFeedback]:
        """获取所有完整反馈（包含 UA + Engagement + IAP 数据）。"""
        return [fb for fb in self._feedbacks.values() if fb.is_complete]

    def history(self) -> list[PerformanceFeedback]:
        """获取全部历史反馈（按时间降序）。"""
        return sorted(
            self._feedbacks.values(),
            key=lambda fb: fb.created_at,
            reverse=True,
        )

    def latest(self) -> PerformanceFeedback | None:
        """获取最新反馈。"""
        history = self.history()
        return history[0] if history else None

    # ── 管理 ──────────────────────────────────────────

    def delete(self, feedback_id: str) -> bool:
        """删除反馈。

        Returns:
            是否成功删除
        """
        if feedback_id in self._feedbacks:
            del self._feedbacks[feedback_id]
            return True
        return False

    def clear(self) -> None:
        """清空所有反馈。"""
        self._feedbacks.clear()

    @property
    def count(self) -> int:
        """反馈总数。"""
        return len(self._feedbacks)

    @property
    def creative_count(self) -> int:
        """涉及的不同创意数量。"""
        return len(set(fb.creative_id for fb in self._feedbacks.values()))

    @property
    def campaign_count(self) -> int:
        """涉及的不同广告系列数量。"""
        return len(set(fb.campaign_id for fb in self._feedbacks.values()))

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            fid: fb.to_dict()
            for fid, fb in self._feedbacks.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackRepository:
        repo = cls()
        for fid, fb_data in data.items():
            fb = PerformanceFeedback.from_dict(fb_data)
            repo._feedbacks[fid] = fb
        return repo

    def __repr__(self) -> str:
        return (
            f"FeedbackRepository(feedbacks={self.count}, "
            f"creatives={self.creative_count})"
        )