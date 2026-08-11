"""Phase 4.1 — Creative Performance Analyzer (广告层).

读取 sync_pipeline 输出的 merged CSV，输出 PerformanceMetrics 列表。
提供按平台/ROAS/CPI/Spend 的排序和过滤能力。

注意：这层只是广告表现分析，不包含 IAP 价值判断。
      IAP 价值判断由 iap_fitness_engine.py 负责。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .models import PerformanceMetrics


class CreativePerformanceAnalyzer:
    """广告层表现分析器。

    从 sync_pipeline 输出的 CSV 加载数据，
    提供排序、过滤和统计能力。
    """

    def __init__(self, csv_path: Path | None = None) -> None:
        from pathlib import Path as _Path
        root = _Path(__file__).parent.parent.parent.parent
        self._csv_path = csv_path or (
            root / "output" / "p04_platform_analysis" / "p04_merged_fb_adjust.csv"
        )
        self._metrics: list[PerformanceMetrics] = []

    # ── Loading ────────────────────────────────────────────

    def load(self) -> list[PerformanceMetrics]:
        """加载并解析 CSV 数据."""
        if not self._csv_path.exists():
            return []

        with open(self._csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        self._metrics = [
            PerformanceMetrics.from_csv_row(row)
            for row in rows
            if self._has_data(row)
        ]
        return self._metrics

    @staticmethod
    def _has_data(row: dict[str, str]) -> bool:
        spend = float(row.get("fb_spend") or 0)
        adj_rev = float(row.get("adj_revenue") or 0)
        adj_inst = int(float(row.get("adj_installs") or 0))
        return spend > 0 or adj_rev > 0 or adj_inst > 0

    # ── Filtering ──────────────────────────────────────────

    def by_platform(self, platform: str) -> list[PerformanceMetrics]:
        return [m for m in self._metrics if m.platform.lower() == platform.lower()]

    def by_status(self, status: str) -> list[PerformanceMetrics]:
        return [m for m in self._metrics if m.status.upper() == status.upper()]

    def by_media_type(self, is_video: bool) -> list[PerformanceMetrics]:
        return [m for m in self._metrics if m.is_video == is_video]

    def with_min_spend(self, min_spend: float) -> list[PerformanceMetrics]:
        return [m for m in self._metrics if m.spend >= min_spend]

    def with_valid_roas(self) -> list[PerformanceMetrics]:
        """有足够样本量的 ROAS 数据（spend > $100）."""
        return [m for m in self._metrics if m.spend >= 100 and m.roas > 0]

    # ── Ranking ────────────────────────────────────────────

    def top_by_roas(self, n: int = 10) -> list[PerformanceMetrics]:
        valid = self.with_valid_roas()
        return sorted(valid, key=lambda m: m.roas, reverse=True)[:n]

    def top_by_spend(self, n: int = 10) -> list[PerformanceMetrics]:
        return sorted(self._metrics, key=lambda m: m.spend, reverse=True)[:n]

    def top_by_cpi(self, n: int = 10, lowest: bool = True) -> list[PerformanceMetrics]:
        """Top by CPI (lowest CPI = best)."""
        valid = [m for m in self._metrics if m.cpi > 0]
        return sorted(valid, key=lambda m: m.cpi, reverse=not lowest)[:n]

    def top_by_ctr(self, n: int = 10) -> list[PerformanceMetrics]:
        valid = [m for m in self._metrics if m.ctr > 0 and m.fb_impressions > 1000]
        return sorted(valid, key=lambda m: m.ctr, reverse=True)[:n]

    # ── Statistics ─────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """全局统计摘要."""
        if not self._metrics:
            return {"total": 0}

        ios = self.by_platform("ios")
        android = self.by_platform("android")
        active = self.by_status("ACTIVE")
        videos = self.by_media_type(True)
        images = self.by_media_type(False)
        valid_roas = self.with_valid_roas()

        return {
            "total": len(self._metrics),
            "by_platform": {
                "ios": len(ios),
                "android": len(android),
            },
            "by_status": {
                "active": len(active),
                "paused": len(self.by_status("PAUSED")),
                "deleted": len(self.by_status("DELETED")),
                "archived": len(self.by_status("ARCHIVED")),
            },
            "by_media": {
                "video": len(videos),
                "image": len(images),
            },
            "total_spend": round(sum(m.spend for m in self._metrics), 2),
            "total_revenue": round(sum(m.adjust_revenue for m in self._metrics), 2),
            "total_installs": sum(m.adjust_installs for m in self._metrics),
            "avg_roas": round(
                sum(m.roas for m in valid_roas) / len(valid_roas), 3
            ) if valid_roas else 0,
            "avg_cpi": round(
                sum(m.cpi for m in valid_roas if m.cpi > 0) / max(1, len([m for m in valid_roas if m.cpi > 0])), 2
            ),
            "avg_ctr": round(
                sum(m.ctr for m in self._metrics if m.ctr > 0) / max(1, len([m for m in self._metrics if m.ctr > 0])), 4
            ),
        }

    def ios_android_comparison(self) -> dict[str, Any]:
        """iOS vs Android 对比."""
        ios = self.by_platform("ios")
        android = self.by_platform("android")

        def _avg_roas(metrics: list[PerformanceMetrics]) -> float:
            valid = [m.roas for m in metrics if m.spend >= 100 and m.roas > 0]
            return round(sum(valid) / len(valid), 3) if valid else 0

        def _avg_cpi(metrics: list[PerformanceMetrics]) -> float:
            valid = [m.cpi for m in metrics if m.cpi > 0]
            return round(sum(valid) / len(valid), 2) if valid else 0

        return {
            "ios": {
                "count": len(ios),
                "total_spend": round(sum(m.spend for m in ios), 2),
                "total_revenue": round(sum(m.adjust_revenue for m in ios), 2),
                "avg_roas": _avg_roas(ios),
                "avg_cpi": _avg_cpi(ios),
            },
            "android": {
                "count": len(android),
                "total_spend": round(sum(m.spend for m in android), 2),
                "total_revenue": round(sum(m.adjust_revenue for m in android), 2),
                "avg_roas": _avg_roas(android),
                "avg_cpi": _avg_cpi(android),
            },
        }