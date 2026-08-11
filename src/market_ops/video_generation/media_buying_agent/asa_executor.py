from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class ASACampaignConfig:
    name: str
    budget: float = 500.0
    match_type: str = "EXACT"
    status: str = "ACTIVE"
    keywords: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=lambda: ["US"])


class ASAExecutor:
    def __init__(self):
        self.campaigns: Dict[str, ASACampaignConfig] = {}

    def create_campaign(self, config: ASACampaignConfig) -> Dict[str, Any]:
        campaign_id = f"asa_campaign_{hash(config.name) % 10000:04d}"
        self.campaigns[campaign_id] = config
        return {
            "campaign_id": campaign_id,
            "name": config.name,
            "budget": config.budget,
            "keywords": len(config.keywords),
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

    def add_keywords(self, campaign_id: str, keywords: List[str]) -> Dict[str, Any]:
        if campaign_id not in self.campaigns:
            return {"status": "failed", "error": "Campaign not found"}
        
        self.campaigns[campaign_id].keywords.extend(keywords)
        return {
            "campaign_id": campaign_id,
            "added_keywords": len(keywords),
            "total_keywords": len(self.campaigns[campaign_id].keywords),
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

    def get_campaign(self, campaign_id: str) -> Optional[ASACampaignConfig]:
        return self.campaigns.get(campaign_id)

    def execute_demo(self) -> Dict[str, Any]:
        config = ASACampaignConfig(
            name="ASA_US_Game_Keywords",
            budget=300.0,
            keywords=["merge games", "cute creatures", "magic merge"],
        )
        campaign = self.create_campaign(config)
        budget_update = self.update_budget(campaign["campaign_id"], 400.0)
        keyword_update = self.add_keywords(campaign["campaign_id"], ["puzzle game", "merge magic"])
        
        return {
            "campaign": campaign,
            "budget_update": budget_update,
            "keyword_update": keyword_update,
        }
