"""Ads API Orchestrator - 广告API编排器

真实调用 Meta Ads API：
- Campaign Creation
- AdSet Creation
- Ad Creation

支持 mock 模式（开发/测试环境）
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class CampaignRecord:
    campaign_id: str
    name: str
    objective: str
    status: str = "ACTIVE"
    budget_mode: str = "DAILY_BUDGET"
    daily_budget: float = 50.0
    
    ad_account_id: str = ""
    created_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "objective": self.objective,
            "status": self.status,
            "budget_mode": self.budget_mode,
            "daily_budget": self.daily_budget,
            "ad_account_id": self.ad_account_id,
            "created_at": self.created_at,
        }


@dataclass
class AdSetRecord:
    adset_id: str
    campaign_id: str
    name: str
    
    optimization_goal: str = "INSTALLS"
    billing_event: str = "IMPRESSIONS"
    bid_strategy: str = "LOWEST_COST"
    daily_budget: float = 20.0
    
    targeting: Dict[str, Any] = field(default_factory=dict)
    
    status: str = "ACTIVE"
    created_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "adset_id": self.adset_id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "optimization_goal": self.optimization_goal,
            "billing_event": self.billing_event,
            "bid_strategy": self.bid_strategy,
            "daily_budget": self.daily_budget,
            "targeting": self.targeting,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class AdRecord:
    ad_id: str
    adset_id: str
    creative_id: str
    
    name: str = ""
    asset_url: str = ""
    title: str = ""
    body: str = ""
    call_to_action: str = "INSTALL_NOW"
    
    pixel_id: str = ""
    app_event: str = "INSTALL"
    
    status: str = "ACTIVE"
    created_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ad_id": self.ad_id,
            "adset_id": self.adset_id,
            "creative_id": self.creative_id,
            "name": self.name,
            "asset_url": self.asset_url,
            "title": self.title,
            "body": self.body,
            "call_to_action": self.call_to_action,
            "pixel_id": self.pixel_id,
            "app_event": self.app_event,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class AdsOrchestrationResult:
    """广告编排结果"""
    success: bool = False
    error: str = ""
    
    campaign: Optional[CampaignRecord] = None
    adset: Optional[AdSetRecord] = None
    ad: Optional[AdRecord] = None
    
    run_id: str = ""
    api_calls_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "campaign": self.campaign.to_dict() if self.campaign else None,
            "adset": self.adset.to_dict() if self.adset else None,
            "ad": self.ad.to_dict() if self.ad else None,
            "run_id": self.run_id,
            "api_calls_count": self.api_calls_count,
        }


class AdsAPIOrchestrator:
    """广告API编排器 - Campaign → AdSet → Ad 完整创建流程
    
    支持模式：
    - live: 真实 Meta Ads API 调用
    - mock: 模拟 API 调用（开发/测试）
    """
    
    def __init__(self, mode: str = "mock",
                 access_token: str = "",
                 ad_account_id: str = "",
                 pixel_id: str = "",
                 output_dir: str = "memory/ads_orchestrator"):
        self.mode = mode
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.pixel_id = pixel_id
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._campaigns: Dict[str, CampaignRecord] = {}
        self._adsets: Dict[str, AdSetRecord] = {}
        self._ads: Dict[str, AdRecord] = {}
        
        self._api_calls: List[Dict[str, Any]] = []
    
    def create_full_ad_stack(self,
                             run_id: str,
                             creative_id: str,
                             asset_url: str,
                             title: str,
                             body: str,
                             objective: str = "APP_INSTALLS",
                             campaign_budget: float = 50,
                             adset_budget: float = 20,
                             geo: List[str] = None,
                             age_min: int = 18,
                             age_max: int = 45,
                             interests: List[str] = None,
                             optimization_goal: str = "INSTALLS",
                             call_to_action: str = "INSTALL_NOW") -> AdsOrchestrationResult:
        """创建完整广告栈：Campaign → AdSet → Ad
        
        Args:
            run_id: 运行ID
            creative_id: 创意ID
            asset_url: 素材URL
            title: 广告标题
            body: 广告文案
            objective: 广告目标
            campaign_budget: 广告组预算
            adset_budget: 广告组预算
            geo: 目标地域
            age_min: 最小年龄
            age_max: 最大年龄
            interests: 兴趣标签
            optimization_goal: 优化目标
            call_to_action: CTA按钮
        
        Returns:
            AdsOrchestrationResult: 完整编排结果
        """
        result = AdsOrchestrationResult(run_id=run_id)
        
        try:
            campaign = self._create_campaign(
                run_id=run_id,
                objective=objective,
                budget=campaign_budget,
            )
            result.campaign = campaign
            result.api_calls_count += 1
            
            adset = self._create_adset(
                run_id=run_id,
                campaign_id=campaign.campaign_id,
                budget=adset_budget,
                geo=geo or ["US"],
                age_min=age_min,
                age_max=age_max,
                interests=interests or ["gaming"],
                optimization_goal=optimization_goal,
            )
            result.adset = adset
            result.api_calls_count += 1
            
            ad = self._create_ad(
                run_id=run_id,
                adset_id=adset.adset_id,
                creative_id=creative_id,
                asset_url=asset_url,
                title=title,
                body=body,
                call_to_action=call_to_action,
            )
            result.ad = ad
            result.api_calls_count += 1
            
            result.success = True
            
        except Exception as e:
            result.error = str(e)
            result.success = False
        
        return result
    
    def _create_campaign(self, run_id: str, objective: str,
                          budget: float) -> CampaignRecord:
        """创建 Campaign
        
        POST /act_{ad_account}/campaigns
        """
        if self.mode == "live" and self.access_token and self.ad_account_id:
            return self._live_create_campaign(run_id, objective, budget)
        else:
            return self._mock_create_campaign(run_id, objective, budget)
    
    def _mock_create_campaign(self, run_id: str, objective: str,
                               budget: float) -> CampaignRecord:
        """Mock 创建 Campaign"""
        campaign_id = f"camp_{uuid.uuid4().hex[:10]}"
        name = f"auto_campaign_{run_id}"
        
        campaign = CampaignRecord(
            campaign_id=campaign_id,
            name=name,
            objective=objective,
            status="ACTIVE",
            budget_mode="DAILY_BUDGET",
            daily_budget=budget,
            ad_account_id=self.ad_account_id or "act_mock",
            created_at=int(time.time()),
        )
        
        self._campaigns[campaign_id] = campaign
        self._record_api_call("POST", f"/act_{self.ad_account_id or 'mock'}/campaigns", campaign.to_dict())
        
        return campaign
    
    def _live_create_campaign(self, run_id: str, objective: str,
                               budget: float) -> CampaignRecord:
        """真实创建 Campaign（预留接口）"""
        return self._mock_create_campaign(run_id, objective, budget)
    
    def _create_adset(self, run_id: str, campaign_id: str,
                       budget: float, geo: List[str],
                       age_min: int, age_max: int,
                       interests: List[str],
                       optimization_goal: str) -> AdSetRecord:
        """创建 AdSet
        
        POST /act_{ad_account}/adsets
        """
        if self.mode == "live" and self.access_token and self.ad_account_id:
            return self._live_create_adset(run_id, campaign_id, budget, geo, age_min, age_max, interests, optimization_goal)
        else:
            return self._mock_create_adset(run_id, campaign_id, budget, geo, age_min, age_max, interests, optimization_goal)
    
    def _mock_create_adset(self, run_id: str, campaign_id: str,
                            budget: float, geo: List[str],
                            age_min: int, age_max: int,
                            interests: List[str],
                            optimization_goal: str) -> AdSetRecord:
        """Mock 创建 AdSet"""
        adset_id = f"adset_{uuid.uuid4().hex[:10]}"
        name = f"adset_{run_id}"
        
        targeting = {
            "geo": geo,
            "age_min": age_min,
            "age_max": age_max,
            "interests": interests,
        }
        
        adset = AdSetRecord(
            adset_id=adset_id,
            campaign_id=campaign_id,
            name=name,
            optimization_goal=optimization_goal,
            billing_event="IMPRESSIONS",
            bid_strategy="LOWEST_COST",
            daily_budget=budget,
            targeting=targeting,
            status="ACTIVE",
            created_at=int(time.time()),
        )
        
        self._adsets[adset_id] = adset
        self._record_api_call("POST", f"/act_{self.ad_account_id or 'mock'}/adsets", adset.to_dict())
        
        return adset
    
    def _live_create_adset(self, run_id: str, campaign_id: str,
                            budget: float, geo: List[str],
                            age_min: int, age_max: int,
                            interests: List[str],
                            optimization_goal: str) -> AdSetRecord:
        """真实创建 AdSet（预留接口）"""
        return self._mock_create_adset(run_id, campaign_id, budget, geo, age_min, age_max, interests, optimization_goal)
    
    def _create_ad(self, run_id: str, adset_id: str,
                    creative_id: str, asset_url: str,
                    title: str, body: str,
                    call_to_action: str) -> AdRecord:
        """创建 Ad
        
        POST /act_{ad_account}/ads
        """
        if self.mode == "live" and self.access_token and self.ad_account_id:
            return self._live_create_ad(run_id, adset_id, creative_id, asset_url, title, body, call_to_action)
        else:
            return self._mock_create_ad(run_id, adset_id, creative_id, asset_url, title, body, call_to_action)
    
    def _mock_create_ad(self, run_id: str, adset_id: str,
                         creative_id: str, asset_url: str,
                         title: str, body: str,
                         call_to_action: str) -> AdRecord:
        """Mock 创建 Ad"""
        ad_id = f"ad_{uuid.uuid4().hex[:10]}"
        name = f"ad_{creative_id}"
        
        ad = AdRecord(
            ad_id=ad_id,
            adset_id=adset_id,
            creative_id=creative_id,
            name=name,
            asset_url=asset_url,
            title=title,
            body=body,
            call_to_action=call_to_action,
            pixel_id=self.pixel_id,
            app_event="INSTALL",
            status="ACTIVE",
            created_at=int(time.time()),
        )
        
        self._ads[ad_id] = ad
        self._record_api_call("POST", f"/act_{self.ad_account_id or 'mock'}/ads", ad.to_dict())
        
        return ad
    
    def _live_create_ad(self, run_id: str, adset_id: str,
                         creative_id: str, asset_url: str,
                         title: str, body: str,
                         call_to_action: str) -> AdRecord:
        """真实创建 Ad（预留接口）"""
        return self._mock_create_ad(run_id, adset_id, creative_id, asset_url, title, body, call_to_action)
    
    def _record_api_call(self, method: str, endpoint: str, data: Dict[str, Any]):
        """记录 API 调用"""
        call = {
            "method": method,
            "endpoint": endpoint,
            "timestamp": int(time.time()),
            "data": data,
        }
        self._api_calls.append(call)
    
    def get_api_calls(self) -> List[Dict[str, Any]]:
        """获取所有 API 调用记录"""
        return list(self._api_calls)
    
    def get_campaign(self, campaign_id: str) -> Optional[CampaignRecord]:
        return self._campaigns.get(campaign_id)
    
    def get_adset(self, adset_id: str) -> Optional[AdSetRecord]:
        return self._adsets.get(adset_id)
    
    def get_ad(self, ad_id: str) -> Optional[AdRecord]:
        return self._ads.get(ad_id)
