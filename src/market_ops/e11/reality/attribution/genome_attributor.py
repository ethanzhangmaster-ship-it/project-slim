"""E11.6.3 GenomeAttributor — RevenueEvent → GenomeAttributionResult 核心服务。

将 Adjust 已归因的 RevenueEvent 反推到 Creative DNA / Genome 层。

流程：
  RevenueEvent → creative_id → CreativeDNAMapper → genome_id → Revenue Aggregate → GenomeAttributionResult
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..revenue_schema import RevenueEvent
from ..adjust.adjust_mapper import AdjustCreativeMapper
from .attribution_schema import (
    CreativeRevenueAttribution,
    GenomeAttributionResult,
)


# ═══════════════════════════════════════════════════════════
# GenomeAttributor
# ═══════════════════════════════════════════════════════════

class GenomeAttributor:
    """RevenueEvent → Genome 归因核心服务。

    将 RevenueEvent 列表归因到 Genome 级别，
    计算每个 Genome 的商业表现。

    Usage:
        attributor = GenomeAttributor(creative_mapper=mapper)
        results = attributor.attribute(revenue_events)
        for r in results:
            print(f"{r.genome_id}: attr_score={r.attribution_score}, top_genes={r.top_genes}")
    """

    def __init__(
        self,
        creative_mapper: AdjustCreativeMapper | None = None,
    ) -> None:
        self._creative_mapper = creative_mapper or AdjustCreativeMapper()

    # ── 主入口 ────────────────────────────────────────

    def attribute(
        self,
        events: list[RevenueEvent],
    ) -> list[GenomeAttributionResult]:
        """将 RevenueEvent 列表归因到 Genome 级别。

        Args:
            events: RevenueEvent 列表

        Returns:
            GenomeAttributionResult 列表（按 total_revenue 降序）
        """
        if not events:
            return []

        # 1. 聚合 Creative 级别数据
        creative_attrs = self._aggregate_creative(events)

        # 2. 聚合 Genome 级别数据
        genome_attrs = self._aggregate_genome(creative_attrs)

        # 3. 计算 Fitness 和 Top Genes
        results = [
            self._build_result(genome_id, data)
            for genome_id, data in genome_attrs.items()
        ]

        # 4. 按 total_revenue 降序
        results.sort(key=lambda r: r.total_revenue, reverse=True)
        return results

    def attribute_creative(
        self,
        events: list[RevenueEvent],
    ) -> list[CreativeRevenueAttribution]:
        """将 RevenueEvent 归因到 Creative 级别。

        Args:
            events: RevenueEvent 列表

        Returns:
            CreativeRevenueAttribution 列表
        """
        return list(self._aggregate_creative(events).values())

    # ── 内部聚合 ──────────────────────────────────────

    def _aggregate_creative(
        self,
        events: list[RevenueEvent],
    ) -> dict[str, CreativeRevenueAttribution]:
        """按 creative_id 聚合 RevenueEvent。"""
        creative_data: dict[str, dict[str, Any]] = {}

        for event in events:
            if not event.is_valid:
                continue

            cid = event.creative_id
            if not cid:
                continue

            if cid not in creative_data:
                creative_data[cid] = {
                    "creative_id": cid,
                    "genome_id": event.genome_id or self._creative_mapper.map_creative(cid),
                    "total_users": 0,
                    "total_revenue": 0.0,
                    "iap_revenue": 0.0,
                    "ad_revenue": 0.0,
                    "payer_count": 0,
                    "user_ids": set(),
                }

            cd = creative_data[cid]
            cd["total_revenue"] += event.revenue
            cd["user_ids"].add(event.user_id)

            if event.product_id.startswith("iap_"):
                cd["iap_revenue"] += event.revenue
            elif event.product_id.startswith("ad_"):
                cd["ad_revenue"] += event.revenue

            if event.revenue > 0:
                cd["payer_count"] = len(cd["user_ids"])

        # 构建 CreativeRevenueAttribution
        result: dict[str, CreativeRevenueAttribution] = {}
        for cid, cd in creative_data.items():
            users = cd["total_users"] or len(cd["user_ids"])
            total_rev = cd["total_revenue"]
            payer_count = cd["payer_count"]

            result[cid] = CreativeRevenueAttribution(
                creative_id=cd["creative_id"],
                genome_id=cd["genome_id"],
                total_users=users,
                total_revenue=round(total_rev, 2),
                iap_revenue=round(cd["iap_revenue"], 2),
                ad_revenue=round(cd["ad_revenue"], 2),
                payer_count=payer_count,
                payer_rate=round(payer_count / users, 4) if users > 0 else 0.0,
                arpu=round(total_rev / users, 2) if users > 0 else 0.0,
            )

        return result

    def _aggregate_genome(
        self,
        creative_attrs: dict[str, CreativeRevenueAttribution],
    ) -> dict[str, dict[str, Any]]:
        """按 genome_id 聚合 CreativeRevenueAttribution。"""
        genome_data: dict[str, dict[str, Any]] = {}

        for attr in creative_attrs.values():
            gid = attr.genome_id
            if not gid:
                continue

            if gid not in genome_data:
                genome_data[gid] = {
                    "genome_id": gid,
                    "creatives": [],
                    "total_users": 0,
                    "total_revenue": 0.0,
                    "iap_revenue": 0.0,
                    "ad_revenue": 0.0,
                    "payer_count": 0,
                }

            gd = genome_data[gid]
            gd["creatives"].append(attr.creative_id)
            gd["total_users"] += attr.total_users
            gd["total_revenue"] += attr.total_revenue
            gd["iap_revenue"] += attr.iap_revenue
            gd["ad_revenue"] += attr.ad_revenue
            gd["payer_count"] += attr.payer_count

        return genome_data

    def _build_result(
        self,
        genome_id: str,
        data: dict[str, Any],
    ) -> GenomeAttributionResult:
        """构建 GenomeAttributionResult（含 fitness 和 top_genes）。"""
        users = data["total_users"]
        total_rev = data["total_revenue"]
        payer_count = data["payer_count"]

        payer_rate = round(payer_count / users, 4) if users > 0 else 0.0
        arpu = round(total_rev / users, 2) if users > 0 else 0.0
        d30_ltv = round(total_rev / users, 2) if users > 0 else 0.0

        # 计算 fitness = 收入规模 × 效率 × 付费率
        revenue_score = min(total_rev / 100000.0, 1.0)
        efficiency_score = min(arpu / 5.0, 1.0)
        payer_score = min(payer_rate / 0.15, 1.0)
        fitness = round(
            revenue_score * 0.4 + efficiency_score * 0.3 + payer_score * 0.3,
            4,
        )

        # top_genes 由 DNARevenueAnalyzer 填入
        return GenomeAttributionResult(
            genome_id=genome_id,
            creatives=sorted(data["creatives"]),
            total_users=users,
            total_revenue=round(total_rev, 2),
            iap_revenue=round(data["iap_revenue"], 2),
            ad_revenue=round(data["ad_revenue"], 2),
            payer_count=payer_count,
            payer_rate=payer_rate,
            arpu=arpu,
            d30_ltv=d30_ltv,
            attribution_score=fitness,
        )

    def __repr__(self) -> str:
        return (
            f"GenomeAttributor(creatives={self._creative_mapper.mapped_count})"
        )