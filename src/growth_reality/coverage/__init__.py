"""P1.6 — 真实数据覆盖层（Reality Coverage）。

汇聚 E17.1 公司快照 + GameRegistry，提供三块能力：
- gaps.MissingDataDetector    : 缺口检测，自动标记 DATA_GAP（防 CEO 被骗）
- health.RealityHealthMonitor  : 逐游戏真实源健康 + 每日覆盖日报
- snapshot_store.DailyRealityStore : 按游戏/日期落盘的真实经营数据库
"""
from __future__ import annotations

from .gaps import DataGap, MissingDataDetector
from .health import (
    GameRealityHealth,
    RealityCoverageReport,
    RealityHealthMonitor,
    SourceHealth,
)
from .snapshot_store import DailyRealityStore, build_store_from_company

__all__ = [
    "DataGap",
    "MissingDataDetector",
    "GameRealityHealth",
    "RealityCoverageReport",
    "RealityHealthMonitor",
    "SourceHealth",
    "DailyRealityStore",
    "build_store_from_company",
]
