from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class MetaCampaignConfig:
    name: str
    objective: str = "PURCHASE"
    budget: float = 500.0
    budget_type: str = "DAILY"
    status: str = "ACTIVE"


@dataclass
class MetaAdSetConfig:
    name: str
    campaign_id: str
    audience: Dict[str, Any] = field(default_factory=dict)
    placements: List[str] = field(default_factory=lambda: ["FEED", "STORIES", "REELS"])
    optimization_goal: str = "PURCHASE"
    bid_strategy: str = "LOWEST_COST_WITH_BID_CAP"
    bid_cap: float = 10.0


@dataclass
class MetaAdConfig:
    name: str
    ad_set_id: str
    creative_id: str
    copy: str = ""
    headline: str = ""
    primary_text: str = ""


class MetaExecutor:
    def __init__(self):
        self.campaigns: Dict[str, MetaCampaignConfig] = {}
        self.ad_sets: Dict[str, MetaAdSetConfig] = {}
        self.ads: Dict[str, MetaAdConfig] = {}

    def create_campaign(self, config: MetaCampaignConfig) -> Dict[str, Any]:
        campaign_id = f"meta_campaign_{hash(config.name) % 10000:04d}"
        self.campaigns[campaign_id] = config
        return {
            "campaign_id": campaign_id,
            "name": config.name,
            "objective": config.objective,
            "budget": config.budget,
            "status": "created",
        }

    def create_ad_set(self, config: MetaAdSetConfig) -> Dict[str, Any]:
        ad_set_id = f"meta_adset_{hash(config.name) % 10000:04d}"
        self.ad_sets[ad_set_id] = config
        return {
            "ad_set_id": ad_set_id,
            "name": config.name,
            "campaign_id": config.campaign_id,
            "status": "created",
        }

    def create_ad(self, config: MetaAdConfig) -> Dict[str, Any]:
        ad_id = f"meta_ad_{hash(config.name) % 10000:04d}"
        self.ads[ad_id] = config
        return {
            "ad_id": ad_id,
            "name": config.name,
            "ad_set_id": config.ad_set_id,
            "status": "created",
        }

    def update_budget(self, campaign_id: str, new_budget: float) -> Dict[str, Any]:
        if campaign_id not in self.campaigns:
            return {"status": "failed", "error": "Campaign not found"}
        
        old_budget = self.campaigns[campaign_id].budget
        self.campaigns[campaign_id].budget = new_budget
        return {
            "campaign_id": campaign_id,
            "old_budget": old_budget,
            "new_budget": new_budget,
            "status": "updated",
        }

    def pause_campaign(self, campaign_id: str) -> Dict[str, Any]:
        if campaign_id not in self.campaigns:
            return {"status": "failed", "error": "Campaign not found"}
        
        self.campaigns[campaign_id].status = "PAUSED"
        return {
            "campaign_id": campaign_id,
            "status": "paused",
        }

    def resume_campaign(self, campaign_id: str) -> Dict[str, Any]:
        if campaign_id not in self.campaigns:
            return {"status": "failed", "error": "Campaign not found"}
        
        self.campaigns[campaign_id].status = "ACTIVE"
        return {
            "campaign_id": campaign_id,
            "status": "resumed",
        }

    def get_campaign(self, campaign_id: str) -> Optional[MetaCampaignConfig]:
        return self.campaigns.get(campaign_id)

    def execute_demo(self) -> Dict[str, Any]:
        campaign_config = MetaCampaignConfig(
            name="US_WITCH_WINNER_001",
            objective="PURCHASE",
            budget=500.0,
        )
        campaign = self.create_campaign(campaign_config)
        
        ad_set_config = MetaAdSetConfig(
            name="US_Female_25-34",
            campaign_id=campaign["campaign_id"],
            audience={"country": "US", "gender": "female", "age_range": "25-34"},
        )
        ad_set = self.create_ad_set(ad_set_config)
        
        ad_config = MetaAdConfig(
            name="Creative_A_Witch",
            ad_set_id=ad_set["ad_set_id"],
            creative_id="creative_001",
            copy="Merge cute creatures!",
            headline="Magic Merge",
        )
        ad = self.create_ad(ad_config)
        
        budget_update = self.update_budget(campaign["campaign_id"], 700.0)
        
        return {
            "campaign": campaign,
            "ad_set": ad_set,
            "ad": ad,
            "budget_update": budget_update,
        }
