from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class BusinessGoal:
    goal_id: str
    name: str
    target: Dict[str, Any] = field(default_factory=dict)
    current_value: Dict[str, Any] = field(default_factory=dict)
    deadline: Optional[datetime] = None
    progress: float = 0.0


@dataclass
class GrowthGoal:
    goal_id: str
    business_goal_id: str
    name: str
    target_roas: float = 0.0
    current_roas: float = 0.0
    required_improvement: float = 0.0


@dataclass
class CampaignGoal:
    goal_id: str
    growth_goal_id: str
    name: str
    target_cpi: float = 0.0
    target_cvr: float = 0.0
    budget: float = 0.0


@dataclass
class CreativeGoal:
    goal_id: str
    campaign_goal_id: str
    name: str
    winner_target: int = 0
    current_winners: int = 0
    mutation_count: int = 0


class GoalManager:
    def __init__(self):
        self.business_goals: Dict[str, BusinessGoal] = {}
        self.growth_goals: Dict[str, GrowthGoal] = {}
        self.campaign_goals: Dict[str, CampaignGoal] = {}
        self.creative_goals: Dict[str, CreativeGoal] = {}

    def create_business_goal(self, name: str, target: Dict[str, Any], deadline: Optional[datetime] = None) -> BusinessGoal:
        goal = BusinessGoal(
            goal_id=f"bg_{hash(name) % 10000:04d}",
            name=name,
            target=target,
            deadline=deadline,
        )
        self.business_goals[goal.goal_id] = goal
        return goal

    def decompose_to_growth(self, business_goal: BusinessGoal) -> GrowthGoal:
        profit_target = business_goal.target.get("monthly_profit_growth", 0.3)
        
        growth_goal = GrowthGoal(
            goal_id=f"gg_{business_goal.goal_id[-4:]}",
            business_goal_id=business_goal.goal_id,
            name=f"Support: {business_goal.name}",
            target_roas=1.2,
            required_improvement=profit_target * 0.8,
        )
        self.growth_goals[growth_goal.goal_id] = growth_goal
        return growth_goal

    def decompose_to_campaign(self, growth_goal: GrowthGoal) -> CampaignGoal:
        campaign_goal = CampaignGoal(
            goal_id=f"cg_{growth_goal.goal_id[-4:]}",
            growth_goal_id=growth_goal.goal_id,
            name=f"Campaign: {growth_goal.name}",
            target_cpi=2.5,
            target_cvr=0.08,
            budget=50000,
        )
        self.campaign_goals[campaign_goal.goal_id] = campaign_goal
        return campaign_goal

    def decompose_to_creative(self, campaign_goal: CampaignGoal) -> CreativeGoal:
        creative_goal = CreativeGoal(
            goal_id=f"crg_{campaign_goal.goal_id[-4:]}",
            campaign_goal_id=campaign_goal.goal_id,
            name=f"Creative: {campaign_goal.name}",
            winner_target=10,
            mutation_count=100,
        )
        self.creative_goals[creative_goal.goal_id] = creative_goal
        return creative_goal

    def get_full_goal_tree(self, business_goal_id: str) -> Dict[str, Any]:
        business = self.business_goals.get(business_goal_id)
        if not business:
            return {}

        growth = next((g for g in self.growth_goals.values() if g.business_goal_id == business_goal_id), None)
        campaign = next((c for c in self.campaign_goals.values() if growth and c.growth_goal_id == growth.goal_id), None)
        creative = next((cr for cr in self.creative_goals.values() if campaign and cr.campaign_goal_id == campaign.goal_id), None)

        return {
            "business": business,
            "growth": growth,
            "campaign": campaign,
            "creative": creative,
        }

    def update_progress(self, business_goal_id: str, metrics: Dict[str, Any]) -> float:
        goal = self.business_goals.get(business_goal_id)
        if not goal:
            return 0.0

        profit_target = goal.target.get("monthly_profit_growth", 0.3)
        current_profit = metrics.get("current_profit_growth", 0.0)
        
        goal.progress = min(current_profit / profit_target, 1.0)
        goal.current_value = metrics
        
        if goal.growth_goals:
            growth = next((g for g in self.growth_goals.values() if g.business_goal_id == business_goal_id), None)
            if growth:
                growth.current_roas = metrics.get("current_roas", 0.0)
        
        return goal.progress

    def decompose(self, business_target: Dict[str, Any]) -> List[Any]:
        name = f"Business Goal"
        if "monthly_profit" in business_target:
            name = f"Monthly Profit +{business_target['monthly_profit'] * 100}%"
        
        business = self.create_business_goal(
            name=name,
            target=business_target,
        )
        growth = self.decompose_to_growth(business)
        campaign = self.decompose_to_campaign(growth)
        creative = self.decompose_to_creative(campaign)
        
        return [business, growth, campaign, creative]

    def create_goal_tree_demo(self) -> Dict[str, Any]:
        business = self.create_business_goal(
            name="Monthly Profit +30%",
            target={"monthly_profit_growth": 0.3},
        )
        growth = self.decompose_to_growth(business)
        campaign = self.decompose_to_campaign(growth)
        creative = self.decompose_to_creative(campaign)
        
        return {
            "business": business,
            "growth": growth,
            "campaign": campaign,
            "creative": creative,
        }
