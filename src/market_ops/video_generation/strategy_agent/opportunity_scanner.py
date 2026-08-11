from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GrowthOpportunity:
    opportunity_id: str
    type: str
    target: str
    country: str = ""
    audience: Dict[str, str] = field(default_factory=dict)
    platform: str = ""
    potential_roas: float = 0.0
    confidence: float = 0.0
    budget_needed: float = 0.0
    priority: str = "medium"
    timestamp: datetime = field(default_factory=datetime.now)


class OpportunityScanner:
    def __init__(self):
        self.scanners = {
            "platform": self._scan_platforms,
            "country": self._scan_countries,
            "audience": self._scan_audiences,
            "creative": self._scan_creatives,
            "keyword": self._scan_keywords,
        }

    def scan(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        
        for scanner_type, scanner in self.scanners.items():
            results = scanner(data)
            opportunities.extend(results)
        
        opportunities.sort(key=lambda x: x.confidence * x.potential_roas, reverse=True)
        return opportunities[:10]

    def _scan_platforms(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        active_platforms = data.get("active_platforms", ["meta"])
        all_platforms = ["meta", "google", "asa", "tiktok"]
        
        platform_opportunities = {
            "tiktok": {"roas": 2.5, "confidence": 0.75},
            "google": {"roas": 2.0, "confidence": 0.7},
            "asa": {"roas": 2.2, "confidence": 0.65},
        }
        
        for platform, metrics in platform_opportunities.items():
            if platform not in active_platforms:
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_platform_{hash(platform)}",
                    type="platform",
                    target=platform,
                    potential_roas=metrics["roas"],
                    confidence=metrics["confidence"],
                    budget_needed=500,
                    priority="high" if metrics["confidence"] > 0.7 else "medium",
                ))
        
        return opportunities

    def _scan_countries(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        active_countries = data.get("active_countries", ["US"])
        
        country_opportunities = {
            "DE": {"roas": 2.8, "confidence": 0.8},
            "JP": {"roas": 3.0, "confidence": 0.75},
            "AU": {"roas": 2.4, "confidence": 0.65},
        }
        
        for country, metrics in country_opportunities.items():
            if country not in active_countries:
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_country_{hash(country)}",
                    type="country",
                    target=country,
                    country=country,
                    potential_roas=metrics["roas"],
                    confidence=metrics["confidence"],
                    budget_needed=400,
                    priority="high",
                ))
        
        return opportunities

    def _scan_audiences(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        audience_data = data.get("audience_data", {})
        
        for segment, metrics in audience_data.items():
            if metrics.get("match_score", 0) > 0.85 and metrics.get("historical_success", 0) < 0.3:
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_audience_{hash(segment)}",
                    type="audience",
                    target=segment,
                    audience={"segment": segment},
                    potential_roas=metrics.get("expected_roas", 2.5),
                    confidence=metrics.get("match_score", 0.85),
                    budget_needed=300,
                    priority="high",
                ))
        
        return opportunities

    def _scan_creatives(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        creative_data = data.get("creative_data", {})
        
        for creative_id, metrics in creative_data.items():
            if metrics.get("dna_score", 0) > 0.9 and not metrics.get("tested", False):
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_creative_{hash(creative_id)}",
                    type="creative",
                    target=creative_id,
                    potential_roas=metrics.get("expected_roas", 2.8),
                    confidence=metrics.get("dna_score", 0.9),
                    budget_needed=200,
                    priority="medium",
                ))
        
        return opportunities

    def _scan_keywords(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        keyword_data = data.get("keyword_data", {})
        
        for keyword, metrics in keyword_data.items():
            if metrics.get("volume", 0) > 1000 and metrics.get("competition", 0) < 0.5:
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_keyword_{hash(keyword)}",
                    type="keyword",
                    target=keyword,
                    potential_roas=metrics.get("expected_roas", 2.0),
                    confidence=0.7,
                    budget_needed=150,
                    priority="low",
                ))
        
        return opportunities

    def scan_demo(self) -> List[GrowthOpportunity]:
        data = {
            "active_platforms": ["meta"],
            "active_countries": ["US"],
            "audience_data": {
                "US_Female_35-44": {"match_score": 0.91, "historical_success": 0.15, "expected_roas": 3.0},
            },
            "creative_data": {
                "creative_new_001": {"dna_score": 0.92, "tested": False, "expected_roas": 2.8},
            },
            "keyword_data": {
                "merge games": {"volume": 5000, "competition": 0.3},
            },
        }
        return self.scan(data)
