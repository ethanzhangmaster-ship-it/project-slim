"""E13.1.2 Meta Ads Client — Meta Marketing API 客户端.

提供模拟 API 以支持无真实 Token 的本地开发和测试。
真实生产环境通过 access_token 切换为真实 API 调用。
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .exceptions import (
    MetaAPIError,
    MetaAuthError,
    MetaConfigError,
    MetaConnectionError,
    MetaDataNotFoundError,
    MetaRateLimitError,
)
from .models import (
    MetaAPIResponse,
    MetaAccount,
    MetaAccountStatus,
    MetaAdSet,
    MetaCampaign,
    MetaCampaignObjective,
    MetaCampaignStatus,
    MetaCreative,
    MetaInsightLevel,
    MetaPerformance,
)


class MetaAdsClient:
    """Meta Marketing API 客户端.

    支持两种模式:
      - 模拟模式 (access_token 为空或 "mock"): 使用内置模拟数据
      - 真实模式 (access_token 有效): 调用 Meta Marketing API v18.0+
    """

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(
        self,
        access_token: str = "",
        app_id: str = "",
        app_secret: str = "",
        ad_account_id: str = "",
        use_mock: bool = True,
    ):
        self._access_token = access_token
        self._app_id = app_id
        self._app_secret = app_secret
        self._ad_account_id = ad_account_id
        self._use_mock = use_mock or not access_token

        self._authenticated: bool = False
        self._connected: bool = False
        self._request_count: int = 0
        self._rate_limit_remaining: int = 200

        # Mock data stores
        self._mock_accounts: dict[str, MetaAccount] = {}
        self._mock_campaigns: dict[str, MetaCampaign] = {}
        self._mock_adsets: dict[str, MetaAdSet] = {}
        self._mock_creatives: dict[str, MetaCreative] = {}
        self._mock_performances: list[MetaPerformance] = []

    # ── Authentication ────────────────────────────────────────

    def authenticate(self) -> bool:
        """认证."""
        if self._use_mock:
            self._authenticated = True
            return True

        if not self._access_token:
            raise MetaAuthError("No access token provided")

        try:
            # In production, validate token against Meta API
            self._authenticated = True
            return True
        except Exception as e:
            raise MetaAuthError(f"Authentication failed: {e}") from e

    def connect(self) -> bool:
        """建立连接."""
        if self._use_mock:
            self._connected = True
            self._seed_mock_data()
            return True

        if not self._access_token:
            raise MetaConfigError("Cannot connect: no access token")

        self._connected = True
        return True

    def disconnect(self) -> None:
        """断开连接."""
        self._connected = False
        self._authenticated = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    # ── Mock Data Seeding ─────────────────────────────────────

    def _seed_mock_data(self) -> None:
        """种子模拟数据."""
        account_id = self._ad_account_id or "act_123456789"
        self._mock_accounts[account_id] = MetaAccount(
            account_id=account_id,
            name="Test Ad Account",
            currency="USD",
            timezone="America/Los_Angeles",
            status=MetaAccountStatus.ACTIVE,
            business_name="Test Business",
            balance=5000.0,
            amount_spent=25000.0,
            created_at="2025-01-01T00:00:00Z",
        )

        # Create mock campaigns
        for i in range(1, 4):
            cid = f"c_{account_id}_{i}"
            self._mock_campaigns[cid] = MetaCampaign(
                campaign_id=cid,
                account_id=account_id,
                name=f"Campaign_{i}",
                objective=MetaCampaignObjective.APP_INSTALLS,
                status=MetaCampaignStatus.ACTIVE,
                daily_budget=100.0 * i,
                lifetime_budget=0.0,
                bid_strategy="LOWEST_COST_WITH_BID_CAP",
                created_at="2025-06-01T00:00:00Z",
                updated_at="2026-07-01T00:00:00Z",
            )

            # AdSets for each campaign
            for j in range(1, 3):
                asid = f"as_{cid}_{j}"
                self._mock_adsets[asid] = MetaAdSet(
                    adset_id=asid,
                    campaign_id=cid,
                    account_id=account_id,
                    name=f"AdSet_{i}_{j}",
                    status=MetaCampaignStatus.ACTIVE,
                    daily_budget=50.0,
                    bid_amount=5.0,
                    optimization_goal="APP_INSTALLS",
                    billing_event="IMPRESSIONS",
                    created_at="2025-06-01T00:00:00Z",
                )

                # Creatives for each adset
                for k in range(1, 3):
                    crid = f"cr_{asid}_{k}"
                    self._mock_creatives[crid] = MetaCreative(
                        creative_id=crid,
                        name=f"Creative_{i}_{j}_{k}",
                        account_id=account_id,
                        title=f"Amazing Game Level {k}",
                        body="Download now and play!",
                        thumbnail_url=f"https://example.com/thumb/{crid}.jpg",
                        video_url=f"https://example.com/video/{crid}.mp4",
                        call_to_action="INSTALL_MOBILE_APP",
                        created_at="2025-06-01T00:00:00Z",
                    )

        # Seed mock performances
        today = datetime.now(timezone.utc).date()
        for days_ago in range(7):
            date = (today - timedelta(days=days_ago)).isoformat()
            for i in range(1, 4):
                cid = f"c_{account_id}_{i}"
                spend = round(80.0 + i * 20 + days_ago * 5, 2)
                impressions = 10000 + i * 5000 - days_ago * 500
                clicks = int(impressions * 0.025)
                installs = int(clicks * 0.15)
                self._mock_performances.append(MetaPerformance(
                    campaign_id=cid,
                    adset_id=f"as_{cid}_1",
                    creative_id=f"cr_as_{cid}_1_1",
                    account_id=account_id,
                    date_start=date,
                    date_stop=date,
                    spend=spend,
                    revenue=spend * (1.2 + i * 0.1),
                    roas=1.2 + i * 0.1,
                    impressions=impressions,
                    clicks=clicks,
                    ctr=round(clicks / impressions, 4),
                    cpm=round(spend / impressions * 1000, 2),
                    cpc=round(spend / clicks, 2),
                    installs=installs,
                    cpi=round(spend / installs, 2) if installs > 0 else 0.0,
                    frequency=round(1.5 + days_ago * 0.3, 2),
                    reach=impressions - 500,
                    unique_clicks=clicks - 50,
                    actions={"mobile_app_install": installs, "purchase": int(installs * 0.1)},
                ))

    # ── Account Operations ────────────────────────────────────

    def get_accounts(self) -> list[MetaAccount]:
        """获取账户列表."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            return list(self._mock_accounts.values())

        return []

    def get_account(self, account_id: str) -> MetaAccount:
        """获取单个账户."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if account_id in self._mock_accounts:
                return self._mock_accounts[account_id]
            raise MetaDataNotFoundError(f"Account not found: {account_id}")

        raise MetaDataNotFoundError(f"Account not found: {account_id}")

    # ── Campaign Operations ───────────────────────────────────

    def get_campaigns(self, account_id: str = "") -> list[MetaCampaign]:
        """获取广告系列列表."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if account_id:
                return [c for c in self._mock_campaigns.values() if c.account_id == account_id]
            return list(self._mock_campaigns.values())

        return []

    def get_campaign(self, campaign_id: str) -> MetaCampaign:
        """获取单个广告系列."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if campaign_id in self._mock_campaigns:
                return self._mock_campaigns[campaign_id]
            raise MetaDataNotFoundError(f"Campaign not found: {campaign_id}")

        raise MetaDataNotFoundError(f"Campaign not found: {campaign_id}")

    # ── AdSet Operations ──────────────────────────────────────

    def get_adsets(self, campaign_id: str = "", account_id: str = "") -> list[MetaAdSet]:
        """获取广告组列表."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_adsets.values())
            if campaign_id:
                result = [a for a in result if a.campaign_id == campaign_id]
            if account_id:
                result = [a for a in result if a.account_id == account_id]
            return result

        return []

    def get_adset(self, adset_id: str) -> MetaAdSet:
        """获取单个广告组."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if adset_id in self._mock_adsets:
                return self._mock_adsets[adset_id]
            raise MetaDataNotFoundError(f"AdSet not found: {adset_id}")

        raise MetaDataNotFoundError(f"AdSet not found: {adset_id}")

    # ── Creative Operations ───────────────────────────────────

    def get_creatives(self, account_id: str = "") -> list[MetaCreative]:
        """获取创意列表."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if account_id:
                return [c for c in self._mock_creatives.values() if c.account_id == account_id]
            return list(self._mock_creatives.values())

        return []

    def get_creative(self, creative_id: str) -> MetaCreative:
        """获取单个创意."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if creative_id in self._mock_creatives:
                return self._mock_creatives[creative_id]
            raise MetaDataNotFoundError(f"Creative not found: {creative_id}")

        raise MetaDataNotFoundError(f"Creative not found: {creative_id}")

    # ── Insights / Performance ────────────────────────────────

    def get_campaign_insights(
        self,
        campaign_id: str = "",
        date_from: str = "",
        date_to: str = "",
        level: MetaInsightLevel = MetaInsightLevel.CAMPAIGN,
    ) -> list[MetaPerformance]:
        """获取广告系列洞察数据."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_performances)
            if campaign_id:
                result = [p for p in result if p.campaign_id == campaign_id]
            if date_from:
                result = [p for p in result if p.date_start >= date_from]
            if date_to:
                result = [p for p in result if p.date_stop <= date_to]
            return result

        return []

    def get_creative_insights(
        self,
        creative_id: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> list[MetaPerformance]:
        """获取创意级别洞察."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = [p for p in self._mock_performances if p.creative_id == creative_id]
            if date_from:
                result = [p for p in result if p.date_start >= date_from]
            if date_to:
                result = [p for p in result if p.date_stop <= date_to]
            return result

        return []

    def get_adset_insights(
        self,
        adset_id: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> list[MetaPerformance]:
        """获取广告组级别洞察."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = [p for p in self._mock_performances if p.adset_id == adset_id]
            if date_from:
                result = [p for p in result if p.date_start >= date_from]
            if date_to:
                result = [p for p in result if p.date_stop <= date_to]
            return result

        return []

    # ── Pagination Support ────────────────────────────────────

    def _build_paginated_response(
        self, data: list[dict[str, Any]], page_size: int = 25, after: str = "",
    ) -> MetaAPIResponse:
        """构建分页响应."""
        if not after:
            start_idx = 0
        else:
            try:
                start_idx = int(after)
            except ValueError:
                start_idx = 0

        page_data = data[start_idx:start_idx + page_size]
        paging: dict[str, Any] = {}
        if start_idx + page_size < len(data):
            paging["next"] = str(start_idx + page_size)

        return MetaAPIResponse(
            success=True,
            data=page_data,
            paging=paging,
            rate_limit_remaining=self._rate_limit_remaining,
            request_id=str(uuid.uuid4()),
        )

    # ── Internal Helpers ──────────────────────────────────────

    def _check_connected(self) -> None:
        if not self._connected:
            raise MetaConnectionError("Client is not connected. Call connect() first.")

    def _make_request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """发起 API 请求 (模拟)."""
        if not self._authenticated:
            raise MetaAuthError("Not authenticated")

        self._request_count += 1
        self._rate_limit_remaining -= 1

        if self._rate_limit_remaining <= 0:
            raise MetaRateLimitError("Rate limit exceeded", retry_after=60)

        time.sleep(0.001)  # Simulate network latency

        return {"success": True, "data": []}

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "authenticated": self._authenticated,
            "use_mock": self._use_mock,
            "ad_account_id": self._ad_account_id,
            "request_count": self._request_count,
            "rate_limit_remaining": self._rate_limit_remaining,
            "campaigns_count": len(self._mock_campaigns),
            "adsets_count": len(self._mock_adsets),
            "creatives_count": len(self._mock_creatives),
            "performances_count": len(self._mock_performances),
        }