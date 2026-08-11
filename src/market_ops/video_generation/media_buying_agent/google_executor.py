from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class GoogleCampaignConfig:
    name: str
    campaign_type: str = "APP_CAMPAIGN"
    budget: float = 500.0
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS"
    status: str = "ENABLED"
    target_conversions: List[str] = field(default_factory=lambda: ["APP_INSTALL", "PURCHASE"])


class GoogleExecutor:
    def __init__(self):
        self.campaigns: Dict[str, GoogleCampaignConfig] = {}

    def create_campaign(self, config: GoogleCampaignConfig) -> Dict[str, Any]:
        campaign_id = f"google_campaign_{hash(config.name) % 10000:04d}"
        self.campaigns[campaign_id] = config
        return {
            "campaign_id": campaign_id,
            "name": config.name,
            "type": config.campaign_type,
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
        
        self.campaigns[campaign_id].status = "ENABLED"
        return {
            "campaign_id": campaign_id,
            "status": "resumed",
        }

    def get_campaign(self, campaign_id: str) -> Optional[GoogleCampaignConfig]:
        return self.campaigns.get(campaign_id)

    def execute_demo(self) -> Dict[str, Any]:
        config = GoogleCampaignConfig(
            name="Google_US_App_Install",
            campaign_type="APP_CAMPAIGN",
            budget=500.0,
        )
        campaign = self.create_campaign(config)
        budget_update = self.update_budget(campaign["campaign_id"], 600.0)
        
        return {
            "campaign": campaign,
            "budget_update": budget_update,
        }
