"""E12.1 — Reality Data Hub。

E12 统一入口：合并 Meta Ads + Adjust 数据，生成 E11 Evolution
可消费的 RealitySnapshot。

数据流：
  MetaAdsReality.fetch_ad_performance()   → AdPerformanceRecord
  AdjustReality.fetch_revenue()           → RevenuePerformance
         │                                          │
         └──────────────┬───────────────────────────┘
                        ▼
                 RealityDataHub
                        │
                        ▼
                  CampaignReality (merged)
                  CreativeReality  (mapped)
                        │
                        ▼
                  RealitySnapshot
                        │
                        ▼
                  E11 Evolution Engine

Usage:
    hub = RealityDataHub(meta_ads=meta_reality, adjust=adjust_reality)
    snapshot = hub.poll(campaign_ids=["camp_001", "camp_002"])
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .models import (
    CampaignReality,
    CreativeReality,
    RealitySnapshot,
)

if TYPE_CHECKING:
    from .meta_ads_reality import MetaAdsReality
    from .adjust_reality import AdjustReality
    from .thinkingdata_reality import ThinkingDataReality

logger = logging.getLogger(__name__)


class RealityDataHub:
    """Reality 数据中枢 —— E12 统一入口。

    合并 Meta Ads 和 Adjust 数据，生成统一的 RealitySnapshot。

    Attributes:
        meta_ads:          Meta Ads 门面
        adjust:            Adjust 门面
        total_polls:       累计 poll 次数
        last_polled_at:    上次 poll 时间
        snapshots:         历史快照列表
    """

    def __init__(
        self,
        meta_ads: MetaAdsReality | None = None,
        adjust: AdjustReality | None = None,
        thinkingdata: ThinkingDataReality | None = None,
    ) -> None:
        self._meta_ads = meta_ads
        self._adjust = adjust
        self._thinkingdata = thinkingdata

        self.total_polls: int = 0
        self.last_polled_at: datetime | None = None
        self.snapshots: list[RealitySnapshot] = []

    # ── Public API ───────────────────────────────────────

    def poll(
        self,
        campaign_ids: list[str],
        lookback_days: int = 7,
        creative_dna_map: dict[str, dict] | None = None,
    ) -> RealitySnapshot:
        """拉取最新现实数据并生成快照。

        Args:
            campaign_ids:   Campaign ID 列表
            lookback_days:  回溯天数（默认 7）
            creative_dna_map: {
                creative_id: {
                    "dna_id": str,
                    "genome_name": str,
                    "hook_gene": str,
                    ...
                }
            }

        Returns:
            合并后的 RealitySnapshot
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()

        # 1. 拉取 Meta Ads 数据
        ad_records: dict[str, list] = {}
        if self._meta_ads:
            ad_records = self._meta_ads.fetch_recent_performance(
                campaign_ids, lookback_days,
            )

        # 2. 拉取 Adjust 数据
        revenue_records: dict[str, list] = {}
        if self._adjust:
            revenues = self._adjust.fetch_multi_revenue(
                campaign_ids, start, end,
            )
            for r in revenues:
                revenue_records.setdefault(r.campaign_id, []).append(r)

        # 3. 拉取 ThinkingData 产品行为数据
        behavior_records: dict[str, list] = {}
        if self._thinkingdata:
            behaviors = self._thinkingdata.fetch_campaign_users(
                0,  # project_id 由 thinkingdata_reality 内部管理
                campaign_ids,
                {"start": start, "end": end},
            )
            for r in behaviors:
                behavior_records.setdefault(r.campaign_id, []).append(r)

        # 4. 合并 → CampaignReality
        campaigns = self._merge_campaigns(
            campaign_ids, ad_records, revenue_records, behavior_records,
        )

        # 5. 生成 CreativeReality
        creatives = self._build_creatives(campaigns, creative_dna_map or {})

        # 6. 计算汇总指标
        total_spend = sum(c.spend for c in campaigns)
        total_revenue = sum(c.revenue_d30 for c in campaigns)
        total_roi = round(total_revenue / total_spend, 4) if total_spend > 0 else 0.0
        total_installs = sum(c.installs for c in campaigns)

        snapshot = RealitySnapshot(
            period_start=start,
            period_end=end,
            campaigns=campaigns,
            creatives=creatives,
            total_spend=total_spend,
            total_revenue=total_revenue,
            total_roi=total_roi,
            total_installs=total_installs,
            summary=self._build_summary(campaigns, creatives, total_roi),
        )

        self.snapshots.append(snapshot)
        self.total_polls += 1
        self.last_polled_at = datetime.now(timezone.utc)

        logger.info(
            f"RealityDataHub: poll #{self.total_polls} — "
            f"{len(campaigns)} campaigns, {len(creatives)} creatives, "
            f"ROI={total_roi:.4f}"
        )
        return snapshot

    def get_latest_snapshot(self) -> RealitySnapshot | None:
        """获取最近一次快照。"""
        return self.snapshots[-1] if self.snapshots else None

    def get_snapshot_history(self, n: int = 10) -> list[RealitySnapshot]:
        """获取最近 N 次快照。"""
        return self.snapshots[-n:] if self.snapshots else []

    def is_ready(self) -> bool:
        """检查是否所有数据源已连接。"""
        meta_ready = self._meta_ads.is_connected() if self._meta_ads else True
        adjust_ready = self._adjust.is_connected() if self._adjust else True
        td_ready = self._thinkingdata.is_connected() if self._thinkingdata else True
        return meta_ready and adjust_ready and td_ready

    # ── Internal ────────────────────────────────────────

    def _merge_campaigns(
        self,
        campaign_ids: list[str],
        ad_records: dict[str, list],
        revenue_records: dict[str, list],
        behavior_records: dict[str, list] | None = None,
    ) -> list[CampaignReality]:
        """合并 Meta Ads + Adjust + ThinkingData 数据为 CampaignReality。

        behavior_records 来自 ThinkingDataReality，包含产品行为真相数据，
        用于增强 CampaignReality 的留存/付费/进度维度。
        """
        behavior_records = behavior_records or {}
        campaigns: list[CampaignReality] = []

        for cid in campaign_ids:
            ads = ad_records.get(cid, [])
            revs = revenue_records.get(cid, [])

            if not ads and not revs:
                # 无数据 → 生成 mock
                campaigns.append(self._mock_campaign(cid))
                continue

            # Meta Ads 聚合
            total_spend = sum(a.spend for a in ads)
            total_impressions = sum(a.impressions for a in ads)
            total_clicks = sum(a.clicks for a in ads)
            total_installs_ads = sum(a.installs for a in ads)
            avg_ctr = (
                round(total_clicks / total_impressions, 4)
                if total_impressions > 0 else 0.0
            )
            avg_cpm = (
                round(total_spend / total_impressions * 1000, 2)
                if total_impressions > 0 else 0.0
            )
            avg_cpc = (
                round(total_spend / total_clicks, 2)
                if total_clicks > 0 else 0.0
            )

            # Adjust 聚合
            rev = revs[0] if revs else None
            revenue_d7 = rev.revenue_d7 if rev else 0.0
            revenue_d30 = rev.revenue_d30 if rev else 0.0
            ltv = rev.ltv if rev else 0.0
            roas_d7 = rev.roas_d7 if rev else 0.0
            roas_d30 = rev.roas_d30 if rev else 0.0
            retention_d7 = rev.retention_d7 if rev else 0.0
            payer_rate = rev.payer_rate if rev else 0.0
            total_installs = rev.installs if rev else total_installs_ads

            # ThinkingData 产品行为聚合（增强留存和付费维度）
            behaviors = behavior_records.get(cid, [])
            if behaviors:
                # 用数数真实留存数据覆盖 Adjust 的 mock 值
                retention_d7 = max(
                    retention_d7,
                    sum(b.d7_retention for b in behaviors) / len(behaviors),
                )
                # 用数数真实付费率覆盖
                payers = sum(1 for b in behaviors if b.is_payer)
                td_payer_rate = round(payers / len(behaviors), 4) if behaviors else 0.0
                payer_rate = td_payer_rate or payer_rate
                # 用数数真实收入补充
                td_revenue = sum(b.total_revenue for b in behaviors)
                revenue_d30 = max(revenue_d30, td_revenue)
                # 用数数安装用户数补充
                total_installs = max(total_installs, len(behaviors))

            campaigns.append(CampaignReality(
                campaign_id=cid,
                spend=round(total_spend, 2),
                impressions=total_impressions,
                clicks=total_clicks,
                installs=total_installs,
                ctr=avg_ctr,
                cpm=avg_cpm,
                cpc=avg_cpc,
                cpi=round(total_spend / total_installs, 2) if total_installs > 0 else 0.0,
                revenue_d7=round(revenue_d7, 2),
                revenue_d30=round(revenue_d30, 2),
                ltv=round(ltv, 2),
                roas_d7=roas_d7,
                roas_d30=roas_d30,
                retention_d7=retention_d7,
                payer_rate=payer_rate,
                period=f"{self.snapshots[-1].period_start if self.snapshots else 'N/A'} → "
                       f"{self.snapshots[-1].period_end if self.snapshots else 'N/A'}",
            ))

        return campaigns

    def _build_creatives(
        self,
        campaigns: list[CampaignReality],
        dna_map: dict[str, dict],
    ) -> list[CreativeReality]:
        """从 Campaign 生成 CreativeReality 列表。

        如果提供了 dna_map，将 Creative 与 DNA 关联。
        """
        creatives: list[CreativeReality] = []

        for campaign in campaigns:
            for creative_id in campaign.creatives or [f"{campaign.campaign_id}_creative"]:
                dna = dna_map.get(creative_id, {})
                performance_score = self._compute_performance_score(campaign)

                creatives.append(CreativeReality(
                    creative_id=creative_id,
                    dna_id=dna.get("dna_id", ""),
                    genome_name=dna.get("genome_name", ""),
                    hook_gene=dna.get("hook_gene", ""),
                    visual_gene=dna.get("visual_gene", ""),
                    gameplay_gene=dna.get("gameplay_gene", ""),
                    monetization_gene=dna.get("monetization_gene", ""),
                    audience_gene=dna.get("audience_gene", ""),
                    psychology_gene=dna.get("psychology_gene", ""),
                    context_gene=dna.get("context_gene", ""),
                    spend=campaign.spend,
                    revenue=campaign.revenue_d30,
                    roi=campaign.roi,
                    roas_d7=campaign.roas_d7,
                    roas_d30=campaign.roas_d30,
                    ctr=campaign.ctr,
                    cpi=campaign.cpi,
                    installs=campaign.installs,
                    payer_rate=campaign.payer_rate,
                    ltv=campaign.ltv,
                    performance_score=performance_score,
                ))

        return creatives

    def _compute_performance_score(self, campaign: CampaignReality) -> float:
        """计算创意综合表现评分。

        权重：ROI 40% + CTR 30% + Payer Rate 30%
        """
        roi_score = min(campaign.roi / 2.0, 1.0)  # ROI≥2.0 = 满分
        ctr_score = min(campaign.ctr / 0.05, 1.0)  # CTR≥5% = 满分
        payer_score = min(campaign.payer_rate / 0.10, 1.0)  # Payer Rate≥10% = 满分

        return round(roi_score * 0.4 + ctr_score * 0.3 + payer_score * 0.3, 4)

    def _build_summary(
        self,
        campaigns: list[CampaignReality],
        creatives: list[CreativeReality],
        total_roi: float,
    ) -> str:
        """生成快照摘要。"""
        profit_campaigns = sum(1 for c in campaigns if c.profit > 0)
        roi_status = "positive" if total_roi >= 1.0 else "negative"

        return (
            f"Reality Snapshot: {len(campaigns)} campaigns, "
            f"{len(creatives)} creatives. "
            f"Total ROI: {total_roi:.2%} ({roi_status}). "
            f"{profit_campaigns}/{len(campaigns)} campaigns profitable."
        )

    def _mock_campaign(self, campaign_id: str) -> CampaignReality:
        """生成 mock Campaign 数据。"""
        seed = sum(ord(c) for c in campaign_id) % 100 + 1
        spend = 500.0 + seed * 10.0
        revenue_d30 = spend * (0.8 + seed * 0.01)

        return CampaignReality(
            campaign_id=campaign_id,
            spend=round(spend, 2),
            impressions=50000 + seed * 1000,
            clicks=int((50000 + seed * 1000) * 0.03),
            installs=200 + seed * 5,
            ctr=0.03,
            cpm=round(spend / (50000 + seed * 1000) * 1000, 2),
            cpc=round(spend / int((50000 + seed * 1000) * 0.03), 2),
            cpi=round(spend / (200 + seed * 5), 2),
            revenue_d7=round(revenue_d30 * 0.6, 2),
            revenue_d30=round(revenue_d30, 2),
            ltv=round(revenue_d30 * 1.5, 2),
            roas_d7=round(revenue_d30 * 0.6 / spend, 4),
            roas_d30=round(revenue_d30 / spend, 4),
            retention_d7=0.3,
            payer_rate=0.05,
        )

    def __repr__(self) -> str:
        return f"RealityDataHub(polls={self.total_polls}, snapshots={len(self.snapshots)})"