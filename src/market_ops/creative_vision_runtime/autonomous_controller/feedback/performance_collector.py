"""E11.5.3 — Performance Collector。

将原始实验数据转换为 PerformanceSignal。

核心职责：
  1. 解析原始实验数据（dict）
  2. 自动计算 CTR、CVR、ROI
  3. 处理缺失数据（补 0）
  4. 数据验证
"""

from __future__ import annotations

import logging
from typing import Any

from .models import PerformanceSignal

logger = logging.getLogger(__name__)


class PerformanceCollector:
    """性能数据收集器。

    将原始实验数据（来自 Facebook Ads、Adjust 等）转换为 PerformanceSignal。

    Attributes:
        collected_count: 已收集数
    """

    def __init__(self) -> None:
        self._collected_count: int = 0

    # ── 核心接口 ──────────────────────────────────────

    def collect(
        self,
        experiment_result: dict[str, Any],
    ) -> PerformanceSignal:
        """从原始实验数据中收集性能信号。

        Args:
            experiment_result: 原始实验数据

        Returns:
            PerformanceSignal（含自动计算的 CTR/CVR/ROI）
        """
        signal = PerformanceSignal.from_dict(experiment_result)

        # 自动计算派生指标
        signal = self._compute_derived_metrics(signal)

        self._collected_count += 1
        return signal

    def collect_batch(
        self,
        experiment_results: list[dict[str, Any]],
    ) -> list[PerformanceSignal]:
        """批量收集性能信号。"""
        return [self.collect(r) for r in experiment_results]

    # ── 内部 ──────────────────────────────────────────

    @staticmethod
    def _compute_derived_metrics(signal: PerformanceSignal) -> PerformanceSignal:
        """自动计算 CTR、CVR、ROI。"""
        # CTR = clicks / impressions
        if signal.ctr == 0.0 and signal.impressions > 0:
            signal.ctr = round(signal.clicks / signal.impressions, 6)

        # CVR = installs / clicks
        if signal.cvr == 0.0 and signal.clicks > 0:
            signal.cvr = round(signal.installs / signal.clicks, 6)

        # ROI = revenue / spend
        if signal.roi == 0.0 and signal.spend > 0:
            signal.roi = round(signal.revenue / signal.spend, 4)

        return signal

    # ── Stats ──────────────────────────────────────────

    @property
    def collected_count(self) -> int:
        return self._collected_count

    def reset(self) -> None:
        self._collected_count = 0

    def __repr__(self) -> str:
        return f"PerformanceCollector(collected={self._collected_count})"