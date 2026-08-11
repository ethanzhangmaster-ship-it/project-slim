from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class CampaignBlueprint:
    creative_dna: Dict[str, str] = field(default_factory=dict)
    audience_segment: Dict[str, str] = field(default_factory=dict)
    budget_recommendation: float = 0.0
    platform_rules: Dict[str, Any] = field(default_factory=dict)
    objective: str = "purchase"


@dataclass
class CampaignStructure:
    campaign_id: str
    name: str
    objective: str
    budget: float
    ad_sets: List[Dict[str, Any]] = field(default_factory=list)
    ads: List[Dict[str, Any]] = field(default_factory=list)
    platform: str = ""
    status: str = "created"


class CampaignBuilder:
    def __init__(self):
        self.platform_templates = {
            "meta": self._build_meta_structure,
            "google": self._build_google_structure,
            "asa": self._build_asa_structure,
            "tiktok": self._build_tiktok_structure,
        }

    def build(self, blueprint: CampaignBlueprint) -> CampaignStructure:
        platform = blueprint.platform_rules.get("platform", "meta")
        builder = self.platform_templates.get(platform, self._build_meta_structure)
        
        creative_name = "_".join(blueprint.creative_dna.values())[:30]
        audience_name = "_".join(blueprint.audience_segment.values())[:30]
        campaign_name = f"{platform.upper()}_{creative_name}_{audience_name}"
        
        return builder(campaign_name, blueprint)

    def _build_meta_structure(self, name: str, blueprint: CampaignBlueprint) -> CampaignStructure:
        ad_set_name = f"{name}_AdSet"
        country = blueprint.audience_segment.get("country", "US")
        gender = blueprint.audience_segment.get("gender", "female")
        age_range = blueprint.audience_segment.get("age_range", "25-34")
        
        return CampaignStructure(
            campaign_id=f"campaign_{hash(name) % 10000:04d}",
            name=name,
            objective=blueprint.objective.upper(),
            budget=blueprint.budget_recommendation,
            platform="meta",
            ad_sets=[{
                "name": ad_set_name,
                "audience": {"country": country, "gender": gender, "age_range": age_range},
                "optimization_goal": blueprint.objective.upper(),
            }],
            ads=[{
                "name": f"{name}_Ad",
                "creative_dna": blueprint.creative_dna,
            }],
        )

    def _build_google_structure(self, name: str, blueprint: CampaignBlueprint) -> CampaignStructure:
        return CampaignStructure(
            campaign_id=f"campaign_{hash(name) % 10000:04d}",
            name=name,
            objective=blueprint.objective.upper(),
            budget=blueprint.budget_recommendation,
            platform="google",
            ad_sets=[{
                "name": f"{name}_AdSet",
                "targeting": blueprint.audience_segment,
            }],
            ads=[{
                "name": f"{name}_Ad",
                "creative_dna": blueprint.creative_dna,
            }],
        )

    def _build_asa_structure(self, name: str, blueprint: CampaignBlueprint) -> CampaignStructure:
        return CampaignStructure(
            campaign_id=f"campaign_{hash(name) % 10000:04d}",
            name=name,
            objective=blueprint.objective.upper(),
            budget=blueprint.budget_recommendation,
            platform="asa",
            ad_sets=[{
                "name": f"{name}_AdSet",
                "match_type": "EXACT",
            }],
            ads=[{
                "name": f"{name}_Ad",
                "keywords": blueprint.platform_rules.get("keywords", []),
            }],
        )

    def _build_tiktok_structure(self, name: str, blueprint: CampaignBlueprint) -> CampaignStructure:
        return CampaignStructure(
            campaign_id=f"campaign_{hash(name) % 10000:04d}",
            name=name,
            objective="APP_INSTALL",
            budget=blueprint.budget_recommendation,
            platform="tiktok",
            ad_sets=[{
                "name": f"{name}_AdSet",
                "audience": blueprint.audience_segment,
            }],
            ads=[{
                "name": f"{name}_Ad",
                "creative_dna": blueprint.creative_dna,
            }],
        )

    def build_demo(self) -> CampaignStructure:
        blueprint = CampaignBlueprint(
            creative_dna={"hook": "fast_action", "camera": "close_up", "emotion": "surprise"},
            audience_segment={"country": "US", "gender": "female", "age_range": "25-34"},
            budget_recommendation=500.0,
            platform_rules={"platform": "meta"},
            objective="purchase",
        )
        return self.build(blueprint)
