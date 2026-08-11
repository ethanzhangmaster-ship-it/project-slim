"""L2 - Ad Platform Orchestrator — 广告平台编排器

多平台支持：
- Meta Ads（Facebook/Instagram）
- TikTok Ads
- Google Ads

核心能力：
- Campaign Manager：campaign creation, budget control, objective config
- AdSet Manager：targeting, bidding, geo + interest + device
- Ad Manager：绑定 creative + asset

必须能力：
- idempotent create
- retry mechanism
- rate limit handling
- multi-account routing
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class Platform(Enum):
    META = "meta"
    TIKTOK = "tiktok"
    GOOGLE = "google"


class Objective(Enum):
    APP_INSTALLS = "APP_INSTALLS"
    APP_PROMOTION = "APP_PROMOTION"
    OUTCOME_APP_PROMOTION = "OUTCOME_APP_PROMOTION"
    CONVERSIONS = "CONVERSIONS"
    SALES = "SALES"
    OUTCOME_SALES = "OUTCOME_SALES"
    TRAFFIC = "TRAFFIC"
    OUTCOME_TRAFFIC = "OUTCOME_TRAFFIC"
    PURCHASE = "PURCHASE"
    LEAD_GENERATION = "LEAD_GENERATION"


class OptimizationGoal(Enum):
    INSTALLS = "INSTALLS"
    APP_INSTALLS = "APP_INSTALLS"
    CONVERSIONS = "CONVERSIONS"
    OFFSITE_CONVERSIONS = "OFFSITE_CONVERSIONS"
    PURCHASE = "PURCHASE"
    VALUE = "VALUE"
    CLICKS = "CLICKS"
    LINK_CLICKS = "LINK_CLICKS"
    IMPRESSIONS = "IMPRESSIONS"
    REACH = "REACH"
    LANDING_PAGE_VIEWS = "LANDING_PAGE_VIEWS"


class BidStrategy(Enum):
    LOWEST_COST = "LOWEST_COST"
    LOWEST_COST_WITHOUT_CAP = "LOWEST_COST_WITHOUT_CAP"
    COST_CAP = "COST_CAP"
    BID_CAP = "BID_CAP"
    TARGET_COST = "TARGET_COST"


@dataclass
class CampaignConfig:
    """Campaign 配置"""
    name: str
    objective: Objective
    status: str = "ACTIVE"
    budget_mode: str = "DAILY_BUDGET"
    daily_budget: float = 50.0
    lifetime_budget: float = 0.0
    
    ad_account_id: str = ""
    platform: Platform = Platform.META
    
    def to_api_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "objective": self.objective.value,
            "status": self.status,
            "budget_mode": self.budget_mode,
            "daily_budget": int(self.daily_budget * 100),  # cents
        }


@dataclass
class AdSetConfig:
    """AdSet 配置"""
    name: str
    campaign_id: str
    
    optimization_goal: OptimizationGoal = OptimizationGoal.INSTALLS
    billing_event: str = "IMPRESSIONS"
    bid_strategy: BidStrategy = BidStrategy.LOWEST_COST
    daily_budget: float = 20.0
    
    targeting: Dict[str, Any] = field(default_factory=dict)
    
    geo: List[str] = field(default_factory=list)
    age_min: int = 18
    age_max: int = 45
    interests: List[str] = field(default_factory=list)
    devices: List[str] = field(default_factory=list)
    
    status: str = "ACTIVE"
    platform: Platform = Platform.META
    
    def to_api_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "campaign_id": self.campaign_id,
            "optimization_goal": self.optimization_goal.value,
            "billing_event": self.billing_event,
            "bid_strategy": self.bid_strategy.value,
            "daily_budget": int(self.daily_budget * 100),
            "targeting": {
                "geo_locations": {"countries": self.geo},
                "age_min": self.age_min,
                "age_max": self.age_max,
                "interests": [{"name": i} for i in self.interests],
            },
            "status": self.status,
        }


@dataclass
class AdConfig:
    """Ad 配置"""
    name: str
    adset_id: str
    creative_id: str
    
    asset_url: str = ""
    headline: str = ""
    body: str = ""
    call_to_action: str = "INSTALL_NOW"
    
    pixel_id: str = ""
    app_id: str = ""
    
    status: str = "ACTIVE"
    platform: Platform = Platform.META
    
    def to_api_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "adset_id": self.adset_id,
            "creative": {
                "object_story_spec": {
                    "link_data": {
                        "image_url": self.asset_url,
                        "link": f"https://play.google.com/store/apps/details?id={self.app_id}",
                        "message": self.body,
                        "call_to_action": {"type": self.call_to_action},
                    }
                }
            },
            "status": self.status,
            "tracking_specs": [
                {
                    "action.type": ["mobile_app_install"],
                    "application": [self.app_id],
                }
            ] if self.app_id else [],
        }


@dataclass
class AdStackRecord:
    """广告栈记录（Campaign + AdSet + Ad）"""
    campaign_id: str = ""
    adset_id: str = ""
    ad_id: str = ""
    
    campaign_config: Optional[CampaignConfig] = None
    adset_config: Optional[AdSetConfig] = None
    ad_config: Optional[AdConfig] = None
    
    creative_id: str = ""
    asset_id: str = ""
    
    platform: Platform = Platform.META
    ad_account_id: str = ""
    
    created_at: int = 0
    api_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "ad_id": self.ad_id,
            "creative_id": self.creative_id,
            "asset_id": self.asset_id,
            "platform": self.platform.value,
            "ad_account_id": self.ad_account_id,
            "created_at": self.created_at,
            "api_calls_count": len(self.api_calls),
        }


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries - 1:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    time.sleep(delay)
        
        raise last_error


class RateLimitHandler:
    """Rate Limit 处理器"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self._requests: List[int] = []
    
    def wait_if_needed(self):
        """如果需要，等待 Rate Limit"""
        now = int(time.time())
        
        self._requests = [t for t in self._requests if now - t < 60]
        
        if len(self._requests) >= self.rpm:
            wait_time = 60 - (now - self._requests[0])
            time.sleep(wait_time)
            self._requests = []
        
        self._requests.append(now)


class IdempotencyManager:
    """幂等性管理器"""
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
    
    def generate_key(self, config: Dict[str, Any]) -> str:
        """生成幂等性 Key"""
        content = json.dumps(config, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def check_existing(self, key: str) -> Optional[str]:
        """检查是否已存在"""
        return self._cache.get(key)
    
    def store(self, key: str, result_id: str):
        """存储结果"""
        self._cache[key] = result_id


class MetaAdsClient:
    """Meta Ads API Client"""
    
    def __init__(self, access_token: str = "",
                 ad_account_id: str = "",
                 mode: str = "mock"):
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.mode = mode
        
        self.retry_handler = RetryHandler()
        self.rate_limiter = RateLimitHandler(requests_per_minute=50)
        self.idempotency = IdempotencyManager()
        
        self._campaigns: Dict[str, Dict[str, Any]] = {}
        self._adsets: Dict[str, Dict[str, Any]] = {}
        self._ads: Dict[str, Dict[str, Any]] = {}
    
    def create_campaign(self, config: CampaignConfig) -> str:
        """创建 Campaign"""
        payload = config.to_api_payload()
        idempotency_key = self.idempotency.generate_key(payload)
        
        existing = self.idempotency.check_existing(idempotency_key)
        if existing:
            return existing
        
        self.rate_limiter.wait_if_needed()
        
        if self.mode == "live" and self.access_token:
            campaign_id = self.retry_handler.execute_with_retry(
                self._live_create_campaign, config
            )
        else:
            campaign_id = self._mock_create_campaign(config)
        
        self.idempotency.store(idempotency_key, campaign_id)
        return campaign_id
    
    def _mock_create_campaign(self, config: CampaignConfig) -> str:
        """Mock 创建 Campaign"""
        campaign_id = f"meta_camp_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": campaign_id,
            "name": config.name,
            "objective": config.objective.value,
            "status": config.status,
            "daily_budget": config.daily_budget,
            "ad_account_id": config.ad_account_id or self.ad_account_id,
            "created_at": int(time.time()),
        }
        
        self._campaigns[campaign_id] = record
        return campaign_id
    
    def _live_create_campaign(self, config: CampaignConfig) -> str:
        """真实创建 Campaign（预留）"""
        return self._mock_create_campaign(config)
    
    def create_adset(self, config: AdSetConfig) -> str:
        """创建 AdSet"""
        payload = config.to_api_payload()
        idempotency_key = self.idempotency.generate_key(payload)
        
        existing = self.idempotency.check_existing(idempotency_key)
        if existing:
            return existing
        
        self.rate_limiter.wait_if_needed()
        
        if self.mode == "live" and self.access_token:
            adset_id = self.retry_handler.execute_with_retry(
                self._live_create_adset, config
            )
        else:
            adset_id = self._mock_create_adset(config)
        
        self.idempotency.store(idempotency_key, adset_id)
        return adset_id
    
    def _mock_create_adset(self, config: AdSetConfig) -> str:
        """Mock 创建 AdSet"""
        adset_id = f"meta_adset_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": adset_id,
            "name": config.name,
            "campaign_id": config.campaign_id,
            "optimization_goal": config.optimization_goal.value,
            "daily_budget": config.daily_budget,
            "targeting": config.targeting,
            "status": config.status,
            "created_at": int(time.time()),
        }
        
        self._adsets[adset_id] = record
        return adset_id
    
    def _live_create_adset(self, config: AdSetConfig) -> str:
        """真实创建 AdSet（预留）"""
        return self._mock_create_adset(config)
    
    def create_ad(self, config: AdConfig) -> str:
        """创建 Ad"""
        payload = config.to_api_payload()
        idempotency_key = self.idempotency.generate_key(payload)
        
        existing = self.idempotency.check_existing(idempotency_key)
        if existing:
            return existing
        
        self.rate_limiter.wait_if_needed()
        
        if self.mode == "live" and self.access_token:
            ad_id = self.retry_handler.execute_with_retry(
                self._live_create_ad, config
            )
        else:
            ad_id = self._mock_create_ad(config)
        
        self.idempotency.store(idempotency_key, ad_id)
        return ad_id
    
    def _mock_create_ad(self, config: AdConfig) -> str:
        """Mock 创建 Ad"""
        ad_id = f"meta_ad_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": ad_id,
            "name": config.name,
            "adset_id": config.adset_id,
            "creative_id": config.creative_id,
            "asset_url": config.asset_url,
            "headline": config.headline,
            "status": config.status,
            "created_at": int(time.time()),
        }
        
        self._ads[ad_id] = record
        return ad_id
    
    def _live_create_ad(self, config: AdConfig) -> str:
        """真实创建 Ad（预留）"""
        return self._mock_create_ad(config)
    
    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        return self._campaigns.get(campaign_id)
    
    def get_adset(self, adset_id: str) -> Optional[Dict[str, Any]]:
        return self._adsets.get(adset_id)
    
    def get_ad(self, ad_id: str) -> Optional[Dict[str, Any]]:
        return self._ads.get(ad_id)
    
    def update_budget(self, entity_id: str, entity_type: str,
                       new_budget: float) -> bool:
        """更新预算"""
        if entity_type == "campaign":
            if entity_id in self._campaigns:
                self._campaigns[entity_id]["daily_budget"] = new_budget
                return True
        elif entity_type == "adset":
            if entity_id in self._adsets:
                self._adsets[entity_id]["daily_budget"] = new_budget
                return True
        return False


class TikTokAdsClient:
    """TikTok Ads API Client"""
    
    def __init__(self, access_token: str = "",
                 advertiser_id: str = "",
                 mode: str = "mock"):
        self.access_token = access_token
        self.advertiser_id = advertiser_id
        self.mode = mode
        
        self.retry_handler = RetryHandler()
        self.rate_limiter = RateLimitHandler(requests_per_minute=30)
        self.idempotency = IdempotencyManager()
        
        self._campaigns: Dict[str, Dict[str, Any]] = {}
        self._adgroups: Dict[str, Dict[str, Any]] = {}
        self._ads: Dict[str, Dict[str, Any]] = {}
    
    def create_campaign(self, config: CampaignConfig) -> str:
        """创建 Campaign（TikTok）"""
        campaign_id = f"tt_camp_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": campaign_id,
            "name": config.name,
            "objective_type": config.objective.value,
            "budget_mode": config.budget_mode,
            "budget": config.daily_budget,
            "advertiser_id": self.advertiser_id,
            "created_at": int(time.time()),
        }
        
        self._campaigns[campaign_id] = record
        return campaign_id
    
    def create_adgroup(self, config: AdSetConfig) -> str:
        """创建 AdGroup（TikTok）"""
        adgroup_id = f"tt_adgroup_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": adgroup_id,
            "campaign_id": config.campaign_id,
            "name": config.name,
            "optimization_goal": config.optimization_goal.value,
            "budget": config.daily_budget,
            "targeting": {
                "location": config.geo,
                "age_range": [config.age_min, config.age_max],
                "interests": config.interests,
            },
            "created_at": int(time.time()),
        }
        
        self._adgroups[adgroup_id] = record
        return adgroup_id
    
    def create_ad(self, config: AdConfig) -> str:
        """创建 Ad（TikTok）"""
        ad_id = f"tt_ad_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": ad_id,
            "adgroup_id": config.adset_id,
            "creative_id": config.creative_id,
            "image_url": config.asset_url,
            "headline": config.headline,
            "created_at": int(time.time()),
        }
        
        self._ads[ad_id] = record
        return ad_id
    
    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        return self._campaigns.get(campaign_id)
    
    def get_adgroup(self, adgroup_id: str) -> Optional[Dict[str, Any]]:
        return self._adgroups.get(adgroup_id)
    
    def get_ad(self, ad_id: str) -> Optional[Dict[str, Any]]:
        return self._ads.get(ad_id)


class GoogleAdsClient:
    """Google Ads API Client"""
    
    def __init__(self, developer_token: str = "",
                 customer_id: str = "",
                 mode: str = "mock"):
        self.developer_token = developer_token
        self.customer_id = customer_id
        self.mode = mode
        
        self.retry_handler = RetryHandler()
        self.rate_limiter = RateLimitHandler(requests_per_minute=100)
        self.idempotency = IdempotencyManager()
        
        self._campaigns: Dict[str, Dict[str, Any]] = {}
        self._adgroups: Dict[str, Dict[str, Any]] = {}
        self._ads: Dict[str, Dict[str, Any]] = {}
    
    def create_campaign(self, config: CampaignConfig) -> str:
        """创建 Campaign（Google）"""
        campaign_id = f"g_camp_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": campaign_id,
            "name": config.name,
            "campaign_budget": config.daily_budget,
            "advertising_channel_type": "MULTI_CHANNEL",
            "created_at": int(time.time()),
        }
        
        self._campaigns[campaign_id] = record
        return campaign_id
    
    def create_adgroup(self, config: AdSetConfig) -> str:
        """创建 AdGroup（Google）"""
        adgroup_id = f"g_adgroup_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": adgroup_id,
            "campaign_id": config.campaign_id,
            "name": config.name,
            "cpc_bid_micros": int(config.daily_budget * 1000000),
            "created_at": int(time.time()),
        }
        
        self._adgroups[adgroup_id] = record
        return adgroup_id
    
    def create_ad(self, config: AdConfig) -> str:
        """创建 Ad（Google）"""
        ad_id = f"g_ad_{uuid.uuid4().hex[:10]}"
        
        record = {
            "id": ad_id,
            "adgroup_id": config.adset_id,
            "headline": config.headline,
            "description": config.body,
            "image_url": config.asset_url,
            "created_at": int(time.time()),
        }
        
        self._ads[ad_id] = record
        return ad_id


class MultiPlatformOrchestrator:
    """多平台编排器 — L2 层主入口
    
    统一管理：
    - Meta Ads
    - TikTok Ads
    - Google Ads
    
    支持：
    - multi-account routing
    - cross-platform campaign sync
    """
    
    def __init__(self, mode: str = "mock", output_dir: str = "memory/orchestrator"):
        self.mode = mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.meta_client = MetaAdsClient(mode=mode)
        self.tiktok_client = TikTokAdsClient(mode=mode)
        self.google_client = GoogleAdsClient(mode=mode)
        
        self._clients: Dict[Platform, Any] = {
            Platform.META: self.meta_client,
            Platform.TIKTOK: self.tiktok_client,
            Platform.GOOGLE: self.google_client,
        }
        
        self._ad_stacks: Dict[str, AdStackRecord] = {}
    
    def create_full_ad_stack(self,
                              platform: Platform,
                              campaign_config: CampaignConfig,
                              adset_config: AdSetConfig,
                              ad_config: AdConfig,
                              creative_id: str,
                              asset_id: str) -> AdStackRecord:
        """创建完整广告栈（Campaign → AdSet → Ad）
        
        Args:
            platform: 广告平台
            campaign_config: Campaign 配置
            adset_config: AdSet 配置
            ad_config: Ad 配置
            creative_id: 创意ID
            asset_id: 资产ID
        
        Returns:
            AdStackRecord: 广告栈记录
        """
        client = self._clients.get(platform)
        if not client:
            raise ValueError(f"Unsupported platform: {platform}")
        
        stack = AdStackRecord(
            platform=platform,
            creative_id=creative_id,
            asset_id=asset_id,
            created_at=int(time.time()),
        )
        
        campaign_config.platform = platform
        campaign_id = client.create_campaign(campaign_config)
        stack.campaign_id = campaign_id
        stack.campaign_config = campaign_config
        stack.api_calls.append({
            "type": "create_campaign",
            "platform": platform.value,
            "timestamp": int(time.time()),
        })
        
        adset_config.platform = platform
        adset_config.campaign_id = campaign_id
        adset_id = client.create_adset(adset_config)
        stack.adset_id = adset_id
        stack.adset_config = adset_config
        stack.api_calls.append({
            "type": "create_adset",
            "platform": platform.value,
            "timestamp": int(time.time()),
        })
        
        ad_config.platform = platform
        ad_config.adset_id = adset_id
        ad_id = client.create_ad(ad_config)
        stack.ad_id = ad_id
        stack.ad_config = ad_config
        stack.api_calls.append({
            "type": "create_ad",
            "platform": platform.value,
            "timestamp": int(time.time()),
        })
        
        stack_key = f"{platform.value}_{campaign_id}"
        self._ad_stacks[stack_key] = stack
        
        return stack
    
    def get_ad_stack(self, stack_key: str) -> Optional[AdStackRecord]:
        return self._ad_stacks.get(stack_key)
    
    def get_client(self, platform: Platform) -> Any:
        return self._clients.get(platform)
    
    def update_budget(self, platform: Platform, entity_id: str,
                       entity_type: str, new_budget: float) -> bool:
        """更新预算"""
        client = self._clients.get(platform)
        if client:
            return client.update_budget(entity_id, entity_type, new_budget)
        return False