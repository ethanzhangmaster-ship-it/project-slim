"""E13.1.2 Meta Ads Connector Adapter — 对接 E13.1.1 BaseConnector 框架."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..base import BaseConnector
from ..models import (
    CampaignMetrics,
    ConnectorConfig,
    ConnectorHealth,
    CreativeMetrics,
    DataSource,
    GrowthDataEvent,
    MetricType,
)
from .client import MetaAdsClient
from .exceptions import MetaAdsError, MetaDataNotFoundError
from .metrics_mapper import MetaMetricsMapper
from .models import (
    CreativeFatigueSignal,
    MetaAccount,
    MetaCampaign,
    MetaCreative,
    MetaPerformance,
    ScalingOpportunity,
)
from .validator import (
    CreativeFatigueValidator,
    MetaAccountValidator,
    MetaCampaignValidator,
    MetaCreativeValidator,
    MetaPerformanceValidator,
    ScalingOpportunityValidator,
)


class MetaAdsConnector(BaseConnector):
    """Meta Ads 连接器 — 对接 E13.1.1 BaseConnector.

    将所有 Meta API 数据通过 E13.1.1 框架标准化输出。
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._client = MetaAdsClient(
            access_token=config.access_token,
            app_id=config.app_id,
            app_secret=config.app_secret,
            ad_account_id=config.account_id,
        )
        self._accounts: dict[str, MetaAccount] = {}
        self._campaigns: dict[str, MetaCampaign] = {}
        self._creatives: dict[str, MetaCreative] = {}
        self._performances: list[MetaPerformance] = []
        self._fatigue_signals: list[CreativeFatigueSignal] = []
        self._scaling_opportunities: list[ScalingOpportunity] = []
        self._last_sync_at: str = ""

    # ── BaseConnector Abstract Methods ────────────────────────

    def _do_connect(self) -> None:
        self._client.connect()

    def _do_disconnect(self) -> None:
        self._client.disconnect()

    def _do_authenticate(self) -> None:
        self._client.authenticate()

    def _do_health_check(self) -> ConnectorHealth:
        if not self._client.is_connected:
            return ConnectorHealth.UNHEALTHY
        if not self._client.is_authenticated:
            return ConnectorHealth.DEGRADED
        return ConnectorHealth.HEALTHY

    # ── BaseConnector Data Fetching Overrides ─────────────────

    def fetch_campaigns(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[CampaignMetrics]:
        """拉取 Campaign 数据 — 转换为 E13.1.1 标准格式."""
        self._sync_campaigns()
        self._sync_performance(date_from, date_to)

        results: list[CampaignMetrics] = []
        for perf in self._performances:
            if date_from and perf.date_start < date_from:
                continue
            if date_to and perf.date_stop > date_to:
                continue

            cm = CampaignMetrics(
                campaign_id=perf.campaign_id,
                campaign_name=self._get_campaign_name(perf.campaign_id),
                platform=DataSource.META_ADS,
                product_id=product_id,
                spend=perf.spend,
                revenue=perf.revenue,
                roas=perf.roas,
                impressions=perf.impressions,
                clicks=perf.clicks,
                ctr=perf.ctr,
                cpm=perf.cpm,
                cpc=perf.cpc,
                installs=perf.installs,
                cpi=perf.cpi,
                date=perf.date_start,
            )
            results.append(cm)

        return results

    def fetch_creatives(
        self, adset_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[CreativeMetrics]:
        """拉取 Creative 数据."""
        self._sync_creatives()
        self._sync_performance(date_from, date_to)

        results: list[CreativeMetrics] = []
        for perf in self._performances:
            if not perf.creative_id:
                continue
            if date_from and perf.date_start < date_from:
                continue
            if date_to and perf.date_stop > date_to:
                continue

            cm = CreativeMetrics(
                creative_id=perf.creative_id,
                creative_name=self._get_creative_name(perf.creative_id),
                adset_id=perf.adset_id,
                campaign_id=perf.campaign_id,
                platform=DataSource.META_ADS,
                spend=perf.spend,
                impressions=perf.impressions,
                clicks=perf.clicks,
                ctr=perf.ctr,
                installs=perf.installs,
                revenue=perf.revenue,
                roas=perf.roas,
                frequency=perf.frequency,
                date=perf.date_start,
            )
            results.append(cm)

        return results

    # ── Sync Operations ───────────────────────────────────────

    def sync_all(self, account_id: str = "") -> dict[str, Any]:
        """全量同步: Accounts, Campaigns, Creatives, Performance."""
        self._sync_accounts()
        self._sync_campaigns()
        self._sync_creatives()
        self._sync_performance()
        self._last_sync_at = datetime.now(timezone.utc).isoformat()

        return {
            "accounts": len(self._accounts),
            "campaigns": len(self._campaigns),
            "creatives": len(self._creatives),
            "performances": len(self._performances),
            "last_sync_at": self._last_sync_at,
        }

    def sync_campaigns(self) -> list[MetaCampaign]:
        """同步广告系列."""
        return self._sync_campaigns()

    def sync_performance(
        self, date_from: str = "", date_to: str = "",
    ) -> list[MetaPerformance]:
        """同步表现数据."""
        return self._sync_performance(date_from, date_to)

    def sync_creatives(self) -> list[MetaCreative]:
        """同步创意."""
        return self._sync_creatives()

    def _sync_accounts(self) -> list[MetaAccount]:
        accounts = self._client.get_accounts()
        for acc in accounts:
            result = MetaAccountValidator.validate(acc)
            if result.is_valid:
                self._accounts[acc.account_id] = acc
        return list(self._accounts.values())

    def _sync_campaigns(self) -> list[MetaCampaign]:
        account_id = self._config.account_id
        campaigns = self._client.get_campaigns(account_id=account_id)
        for camp in campaigns:
            result = MetaCampaignValidator.validate(camp)
            if result.is_valid:
                self._campaigns[camp.campaign_id] = camp
        return list(self._campaigns.values())

    def _sync_creatives(self) -> list[MetaCreative]:
        account_id = self._config.account_id
        creatives = self._client.get_creatives(account_id=account_id)
        for cr in creatives:
            result = MetaCreativeValidator.validate(cr)
            if result.is_valid:
                self._creatives[cr.creative_id] = cr
        return list(self._creatives.values())

    def _sync_performance(
        self, date_from: str = "", date_to: str = "",
    ) -> list[MetaPerformance]:
        if not date_from:
            date_from = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        performances = self._client.get_campaign_insights(
            date_from=date_from,
            date_to=date_to,
        )

        validated: list[MetaPerformance] = []
        for perf in performances:
            result = MetaPerformanceValidator.validate(perf)
            if result.is_valid:
                validated.append(perf)

        self._performances = validated
        return validated

    # ── Growth Data Events ────────────────────────────────────

    def collect_events(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[GrowthDataEvent]:
        """收集所有 Growth Data Events."""
        events: list[GrowthDataEvent] = []

        # Ensure data is synced
        self._sync_campaigns()
        self._sync_performance(date_from, date_to)

        # Campaign metrics -> events
        for perf in self._performances:
            events.append(GrowthDataEvent(
                event_type=MetricType.SPEND,
                source=DataSource.META_ADS,
                product_id=product_id,
                date=perf.date_start,
                metrics={
                    "spend": perf.spend,
                    "revenue": perf.revenue,
                    "roas": perf.roas,
                    "impressions": perf.impressions,
                    "clicks": perf.clicks,
                    "installs": perf.installs,
                    "ctr": perf.ctr,
                    "cpm": perf.cpm,
                    "cpi": perf.cpi,
                    "frequency": perf.frequency,
                },
                campaign_id=perf.campaign_id,
                adset_id=perf.adset_id,
                creative_id=perf.creative_id,
            ))

        return events

    # ── Creative Fatigue Detection ────────────────────────────

    def detect_fatigue(
        self, date: str = "", period_days: int = 7,
    ) -> list[CreativeFatigueSignal]:
        """检测创意疲劳."""
        self._sync_creatives()
        self._sync_performance()

        signals: list[CreativeFatigueSignal] = []
        creative_perfs: dict[str, list[MetaPerformance]] = {}

        # Group by creative
        for perf in self._performances:
            if perf.creative_id:
                creative_perfs.setdefault(perf.creative_id, []).append(perf)

        for creative_id, perfs in creative_perfs.items():
            if len(perfs) < 2:
                continue

            sorted_perfs = sorted(perfs, key=lambda p: p.date_start)
            recent = sorted_perfs[-1]
            older = sorted_perfs[0]

            ctr_change = recent.ctr - older.ctr
            freq_change = recent.frequency - older.frequency
            cpm_change = recent.cpm - older.cpm if older.cpm > 0 else 0.0

            # Fatigue score (0-1)
            ctr_score = max(0.0, min(1.0, -ctr_change / 0.02))
            freq_score = max(0.0, min(1.0, freq_change / 3.0))
            cpm_score = max(0.0, min(1.0, cpm_change / 10.0))
            fatigue_score = (ctr_score * 0.4 + freq_score * 0.35 + cpm_score * 0.25)

            if fatigue_score < 0.3:
                level = "low"
            elif fatigue_score < 0.6:
                level = "medium"
            elif fatigue_score < 0.8:
                level = "high"
            else:
                level = "critical"

            if level == "low":
                recommendation = "Continue monitoring"
            elif level == "medium":
                recommendation = "Prepare creative variants"
            elif level == "high":
                recommendation = "Replace creative within 48 hours"
            else:
                recommendation = "Pause creative immediately and replace"

            signal = CreativeFatigueSignal(
                creative_id=creative_id,
                campaign_id=recent.campaign_id,
                adset_id=recent.adset_id,
                current_ctr=recent.ctr,
                current_frequency=recent.frequency,
                current_cpm=recent.cpm,
                current_spend=recent.spend,
                previous_ctr=older.ctr,
                previous_frequency=older.frequency,
                previous_cpm=older.cpm,
                ctr_change=ctr_change,
                frequency_change=freq_change,
                cpm_change=cpm_change,
                fatigue_score=fatigue_score,
                fatigue_level=level,
                recommendation=recommendation,
                date=date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                period_days=period_days,
            )

            result = CreativeFatigueValidator.validate(signal)
            if result.is_valid:
                signals.append(signal)

        self._fatigue_signals = signals
        return signals

    # ── Scaling Opportunity Detection ─────────────────────────

    def detect_scaling_opportunities(
        self, date: str = "", min_roas: float = 1.5, min_impressions: int = 1000,
    ) -> list[ScalingOpportunity]:
        """检测预算扩量机会."""
        self._sync_campaigns()
        self._sync_performance()

        opportunities: list[ScalingOpportunity] = []
        campaign_perfs: dict[str, list[MetaPerformance]] = {}

        for perf in self._performances:
            campaign_perfs.setdefault(perf.campaign_id, []).append(perf)

        for campaign_id, perfs in campaign_perfs.items():
            if not perfs:
                continue

            latest = perfs[-1]
            campaign = self._campaigns.get(campaign_id)

            if latest.roas < min_roas or latest.impressions < min_impressions:
                continue

            daily_budget = campaign.daily_budget if campaign else 0.0
            if daily_budget <= 0:
                daily_budget = latest.spend

            suggested_increase = min(0.5, max(0.1, (latest.roas - 1.0) * 0.3))
            suggested_budget = daily_budget * (1 + suggested_increase)
            confidence = min(0.9, max(0.3, (latest.roas - 1.0) * 0.5))

            opportunity = ScalingOpportunity(
                campaign_id=campaign_id,
                account_id=latest.account_id,
                current_daily_budget=daily_budget,
                current_spend=latest.spend,
                current_roas=latest.roas,
                current_installs=latest.installs,
                suggested_daily_budget=suggested_budget,
                suggested_budget_increase_pct=suggested_increase * 100,
                estimated_roas_at_scale=latest.roas * 0.9,
                estimated_installs_at_scale=int(latest.installs * (1 + suggested_increase)),
                confidence=confidence,
                reason=f"ROAS {latest.roas:.2f} > {min_roas} with {latest.impressions} impressions",
                date=date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )

            result = ScalingOpportunityValidator.validate(opportunity)
            if result.is_valid:
                opportunities.append(opportunity)

        self._scaling_opportunities = opportunities
        return opportunities

    # ── Helpers ───────────────────────────────────────────────

    def _get_campaign_name(self, campaign_id: str) -> str:
        camp = self._campaigns.get(campaign_id)
        return camp.name if camp else ""

    def _get_creative_name(self, creative_id: str) -> str:
        cr = self._creatives.get(creative_id)
        return cr.name if cr else ""

    # ── Properties ────────────────────────────────────────────

    @property
    def campaigns(self) -> list[MetaCampaign]:
        return list(self._campaigns.values())

    @property
    def performances(self) -> list[MetaPerformance]:
        return self._performances

    @property
    def fatigue_signals(self) -> list[CreativeFatigueSignal]:
        return self._fatigue_signals

    @property
    def scaling_opportunities(self) -> list[ScalingOpportunity]:
        return self._scaling_opportunities

    @property
    def last_sync_at(self) -> str:
        return self._last_sync_at

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            **super().get_summary(),
            "client_summary": self._client.get_summary(),
            "accounts_count": len(self._accounts),
            "campaigns_count": len(self._campaigns),
            "creatives_count": len(self._creatives),
            "performances_count": len(self._performances),
            "fatigue_signals_count": len(self._fatigue_signals),
            "scaling_opportunities_count": len(self._scaling_opportunities),
            "last_sync_at": self._last_sync_at,
        }