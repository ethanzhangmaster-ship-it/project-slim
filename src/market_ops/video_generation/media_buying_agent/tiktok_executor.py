from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class TikTokCampaignConfig:
    name: str
    budget: float = 500.0
    objective: str = "APP_INSTALL"
    status: str = "ACTIVE"
    audience: Dict[str, Any] = field(default_factory=dict)


class TikTokExecutor:
    def __init__(self):
        self.campaigns: Dict[str, TikTokCampaignConfig] = {}

    def create_campaign(self, config: TikTokCampaignConfig) -> Dict[str, Any]:
        campaign_id = f"tiktok_campaign_{hash(config.name) % 10000:04d}"
        self.campaigns[campaign_id] = config
        return {
            "campaign_id": campaign_id,
            "name": config.name,
            "objective": config.objective,
            "budget": config.budget,
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

    def get_campaign(self, campaign_id: str) -> Optional[TikTokCampaignConfig]:
        return self.campaigns.get(campaign_id)

    def execute_demo(self) -> Dict[str, Any]:
        config = TikTokCampaignConfig(
            name="TikTok_US_GenZ",
            objective="APP_INSTALL",
            budget=400.0,
            audience={"country": "US", "age_range": "18-24"},
        )
        campaign = self.create_campaign(config)
        budget_update = self.update_budget(campaign["campaign_id"], 550.0)
        
        return {
            "campaign": campaign,
            "budget_update": budget_update,
        }
