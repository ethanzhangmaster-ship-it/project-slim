"""E15.3.1 Observation Collector — 观察收集器.

从 Reality Data 收集环境观察，输出统一 OperatorObservation。

数据来源:
  - Meta Ads (roas, ctr, cpm, frequency, spend, impressions)
  - Adjust (d1_roas, d7_roas, d30_roas, payer_rate, retention)
  - MAX (ecpm, fill_rate, revenue)
  - App Store / Google Play (downloads, ratings, revenue)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import OperatorObservation


# ═══════════════════════════════════════════════════════════════
# Observation Collector
# ═══════════════════════════════════════════════════════════════


class ObservationCollector:
    """E15.3.1 观察收集器.

    从多个数据源收集环境指标，输出统一 OperatorObservation。

    用法:
        collector = ObservationCollector()
        collector.register_source("meta_ads", meta_data)
        obs = collector.collect()
    """

    def __init__(self):
        self._sources: dict[str, dict[str, float]] = {}

    def register_source(self, name: str, metrics: dict[str, float]) -> None:
        """注册数据源.

        Args:
            name:    数据源名称
            metrics: 指标字典
        """
        self._sources[name] = dict(metrics)

    def update_source_metric(self, source: str, metric: str, value: float) -> None:
        """更新单个数据源指标.

        Args:
            source: 数据源名称
            metric: 指标名称
            value:  新值
        """
        if source not in self._sources:
            self._sources[source] = {}
        self._sources[source][metric] = value

    def collect(self) -> OperatorObservation:
        """收集所有数据源指标，合并为统一观察.

        Returns:
            OperatorObservation
        """
        merged: dict[str, float] = {}
        for source_name, metrics in self._sources.items():
            for metric_name, value in metrics.items():
                # 用 source_name 作为前缀避免冲突
                key = f"{source_name}.{metric_name}"
                merged[key] = value
                # 同时保留不带前缀的版本 (后者覆盖前者)
                merged[metric_name] = value

        return OperatorObservation(
            metrics=merged,
            source=",".join(self._sources.keys()),
        )

    def collect_from_raw(self, raw_data: dict[str, Any], source: str = "") -> OperatorObservation:
        """从原始数据收集观察.

        Args:
            raw_data: 原始数据
            source:   数据来源

        Returns:
            OperatorObservation
        """
        metrics: dict[str, float] = {}
        for key, value in raw_data.items():
            if isinstance(value, (int, float)):
                metrics[key] = float(value)

        return OperatorObservation(
            metrics=metrics,
            source=source,
        )

    def get_source_metrics(self, source: str) -> dict[str, float]:
        """获取特定数据源指标."""
        return self._sources.get(source, {})

    def get_all_sources(self) -> list[str]:
        """获取所有数据源名称."""
        return list(self._sources.keys())

    def clear_sources(self) -> None:
        """清空所有数据源."""
        self._sources.clear()

    def has_source(self, name: str) -> bool:
        """检查数据源是否存在."""
        return name in self._sources


__all__ = ["ObservationCollector"]