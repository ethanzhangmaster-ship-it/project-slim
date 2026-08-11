"""E13.1.4 MAX Revenue Mapper — MAX 原始数据 → Growth OS 标准指标."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import (
    MAXAdFormat,
    MAXNetwork,
    MAXPerformance,
    MAXRevenueEvent,
    MAXRevenueSnapshot,
    MAXWaterfallEntry,
)


class MAXRevenueMapper:
    """MAX 收入数据映射器.

    核心职责: 将 MAX 原始收入事件和聚合数据转换为 MAXRevenueSnapshot，
    作为 Growth OS Reality Layer 的广告收入输入。
    """

    @classmethod
    def build_snapshot(
        cls,
        performances: list[MAXPerformance],
        revenue_events: list[MAXRevenueEvent] | None = None,
        waterfall: list[MAXWaterfallEntry] | None = None,
        product_id: str = "",
        date: str = "",
    ) -> MAXRevenueSnapshot:
        """从聚合数据构建 MAXRevenueSnapshot.

        Args:
            performances: MAX 聚合表现数据
            revenue_events: 收入事件 (可选，用于更细粒度分析)
            waterfall: Waterfall 数据 (可选)
            product_id: 产品 ID
            date: 快照日期

        Returns:
            MAXRevenueSnapshot 聚合结果
        """
        snapshot_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pid = product_id or cls._extract_product_id(performances)

        total_revenue = round(sum(p.revenue for p in performances), 6)
        total_impressions = sum(p.impressions for p in performances)
        total_requests = sum(p.requests for p in performances)
        total_fills = sum(p.fills for p in performances)

        # Unit economics
        ecpm = round(total_revenue / total_impressions * 1000, 4) if total_impressions > 0 else 0.0
        fill_rate = round(total_fills / total_requests, 4) if total_requests > 0 else 0.0
        show_rate = round(total_impressions / total_fills, 4) if total_fills > 0 else 0.0

        # DAU & ARPDAU
        dau = max(p.dau for p in performances) if performances else 0
        arpdau = round(total_revenue / dau, 6) if dau > 0 else 0.0

        # Breakdowns
        by_format = cls._build_format_breakdown(performances)
        by_network = cls._build_network_breakdown(performances)
        by_country = cls._build_country_breakdown(performances)
        by_ad_unit = cls._build_ad_unit_breakdown(performances)

        return MAXRevenueSnapshot(
            product_id=pid,
            date=snapshot_date,
            total_revenue=total_revenue,
            total_impressions=total_impressions,
            total_requests=total_requests,
            total_fills=total_fills,
            ecpm=ecpm,
            fill_rate=fill_rate,
            show_rate=show_rate,
            dau=dau,
            arpdau=arpdau,
            by_format=by_format,
            by_network=by_network,
            by_country=by_country,
            by_ad_unit=by_ad_unit,
        )

    @classmethod
    def build_snapshots_by_date(
        cls,
        performances: list[MAXPerformance],
        product_id: str = "",
    ) -> list[MAXRevenueSnapshot]:
        """按日期拆分构建多个快照."""
        by_date: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_date[p.date].append(p)

        snapshots: list[MAXRevenueSnapshot] = []
        for date_key in sorted(by_date.keys()):
            snapshot = cls.build_snapshot(
                performances=by_date[date_key],
                product_id=product_id,
                date=date_key,
            )
            snapshots.append(snapshot)

        return snapshots

    @classmethod
    def build_snapshot_by_network(
        cls,
        performances: list[MAXPerformance],
        product_id: str = "",
        date: str = "",
    ) -> dict[str, MAXRevenueSnapshot]:
        """按网络分别构建快照."""
        by_network: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_network[p.network.value].append(p)

        result: dict[str, MAXRevenueSnapshot] = {}
        for network, perfs in by_network.items():
            result[network] = cls.build_snapshot(
                performances=perfs,
                product_id=product_id,
                date=date,
            )

        return result

    @classmethod
    def aggregate_events_to_performance(
        cls,
        events: list[MAXRevenueEvent],
        product_id: str = "",
        date: str = "",
    ) -> list[MAXPerformance]:
        """从 Impression-level 事件聚合为 MAXPerformance."""
        # Group by (ad_unit_id, network, country, date, ad_format)
        key_groups: dict[tuple[str, str, str, str, MAXAdFormat], list[MAXRevenueEvent]] = defaultdict(list)

        for event in events:
            key = (
                event.ad_unit_id,
                event.network.value,
                event.country_code,
                event.date,
                event.ad_format,
            )
            key_groups[key].append(event)

        performances: list[MAXPerformance] = []
        for (ad_unit_id, network_str, country, evt_date, ad_format), evts in key_groups.items():
            network = MAXNetwork(network_str) if network_str else MAXNetwork.UNKNOWN
            total_revenue = sum(e.revenue for e in evts)
            total_impressions = len(evts)

            perf = MAXPerformance(
                ad_unit_id=ad_unit_id,
                ad_unit_name=evts[0].ad_unit_name,
                product_id=product_id,
                date=evt_date or date,
                network=network,
                country=country,
                ad_format=ad_format,
                impressions=total_impressions,
                revenue=round(total_revenue, 6),
                ecpm=round(total_revenue / total_impressions * 1000, 4) if total_impressions > 0 else 0.0,
                fill_rate=1.0,
                show_rate=1.0,
            )
            performances.append(perf)

        return performances

    @classmethod
    def compute_waterfall_stats(
        cls,
        waterfall: list[MAXWaterfallEntry],
    ) -> dict[str, Any]:
        """计算 Waterfall 统计."""
        bidding = [w for w in waterfall if w.is_bidding]
        mediated = [w for w in waterfall if not w.is_bidding]

        return {
            "total_networks": len(waterfall),
            "bidding_networks": len(bidding),
            "mediated_networks": len(mediated),
            "bidding_revenue": round(sum(w.revenue for w in bidding), 6),
            "mediated_revenue": round(sum(w.revenue for w in mediated), 6),
            "bidding_revenue_ratio": round(
                sum(w.revenue for w in bidding) / sum(w.revenue for w in waterfall)
                if sum(w.revenue for w in waterfall) > 0 else 0.0, 4,
            ),
            "top_network": cls._get_top_network(waterfall),
            "avg_ecpm": round(
                sum(w.ecpm for w in waterfall) / len(waterfall) if waterfall else 0.0, 4,
            ),
        }

    @classmethod
    def compute_network_stats(
        cls, performances: list[MAXPerformance],
    ) -> dict[str, dict[str, Any]]:
        """计算各网络收入统计."""
        by_network: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_network[p.network.value].append(p)

        stats: dict[str, dict[str, Any]] = {}
        for network, perfs in by_network.items():
            total_revenue = sum(p.revenue for p in perfs)
            total_impressions = sum(p.impressions for p in perfs)
            stats[network] = {
                "revenue": round(total_revenue, 6),
                "impressions": total_impressions,
                "ecpm": round(total_revenue / total_impressions * 1000, 4) if total_impressions > 0 else 0.0,
                "revenue_share": 0.0,  # computed below
            }

        total_revenue_all = sum(s["revenue"] for s in stats.values())
        for network in stats:
            stats[network]["revenue_share"] = round(
                stats[network]["revenue"] / total_revenue_all, 4,
            ) if total_revenue_all > 0 else 0.0

        return stats

    # ── Internal Helpers ──────────────────────────────────────

    @classmethod
    def _extract_product_id(cls, performances: list[MAXPerformance]) -> str:
        for p in performances:
            if p.product_id:
                return p.product_id
        return ""

    @classmethod
    def _build_format_breakdown(
        cls, performances: list[MAXPerformance],
    ) -> dict[str, dict[str, Any]]:
        by_format: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_format[p.ad_format.value].append(p)

        result: dict[str, dict[str, Any]] = {}
        for fmt, perfs in by_format.items():
            rev = sum(p.revenue for p in perfs)
            imp = sum(p.impressions for p in perfs)
            result[fmt] = {
                "revenue": round(rev, 6),
                "impressions": imp,
                "ecpm": round(rev / imp * 1000, 4) if imp > 0 else 0.0,
            }
        return result

    @classmethod
    def _build_network_breakdown(
        cls, performances: list[MAXPerformance],
    ) -> dict[str, dict[str, Any]]:
        by_network: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_network[p.network.value].append(p)

        result: dict[str, dict[str, Any]] = {}
        for network, perfs in by_network.items():
            rev = sum(p.revenue for p in perfs)
            imp = sum(p.impressions for p in perfs)
            result[network] = {
                "revenue": round(rev, 6),
                "impressions": imp,
                "ecpm": round(rev / imp * 1000, 4) if imp > 0 else 0.0,
            }
        return result

    @classmethod
    def _build_country_breakdown(
        cls, performances: list[MAXPerformance],
    ) -> dict[str, dict[str, Any]]:
        by_country: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_country[p.country].append(p)

        result: dict[str, dict[str, Any]] = {}
        for country, perfs in by_country.items():
            rev = sum(p.revenue for p in perfs)
            imp = sum(p.impressions for p in perfs)
            result[country] = {
                "revenue": round(rev, 6),
                "impressions": imp,
                "ecpm": round(rev / imp * 1000, 4) if imp > 0 else 0.0,
            }
        return result

    @classmethod
    def _build_ad_unit_breakdown(
        cls, performances: list[MAXPerformance],
    ) -> dict[str, dict[str, Any]]:
        by_ad_unit: dict[str, list[MAXPerformance]] = defaultdict(list)
        for p in performances:
            by_ad_unit[p.ad_unit_id].append(p)

        result: dict[str, dict[str, Any]] = {}
        for ad_unit, perfs in by_ad_unit.items():
            rev = sum(p.revenue for p in perfs)
            imp = sum(p.impressions for p in perfs)
            result[ad_unit] = {
                "revenue": round(rev, 6),
                "impressions": imp,
                "ecpm": round(rev / imp * 1000, 4) if imp > 0 else 0.0,
            }
        return result

    @classmethod
    def _get_top_network(
        cls, waterfall: list[MAXWaterfallEntry],
    ) -> dict[str, Any]:
        if not waterfall:
            return {}
        top = max(waterfall, key=lambda w: w.revenue)
        return {
            "network": top.network.value,
            "revenue": round(top.revenue, 6),
            "ecpm": round(top.ecpm, 4),
        }