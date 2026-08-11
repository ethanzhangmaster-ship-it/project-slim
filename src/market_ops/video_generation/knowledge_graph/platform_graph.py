from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class PlatformRelation:
    relation_id: str
    platform_id: str
    attribute: str
    value: str
    confidence: float = 0.0


class PlatformGraph:
    def __init__(self):
        self.platforms: Dict[str, Dict[str, Any]] = {}
        self.relations: List[PlatformRelation] = []

    def add_platform(self, platform_id: str, properties: Dict[str, str], performance: Dict[str, float] = None) -> None:
        self.platforms[platform_id] = {
            "properties": properties,
            "performance": performance or {},
        }
        
        for key, value in properties.items():
            self.add_relation(platform_id, key, value, 0.9)

    def add_relation(self, platform_id: str, attribute: str, value: str, confidence: float) -> None:
        relation_id = f"prel_{hash(f'{platform_id}_{attribute}_{value}') % 10000:04d}"
        self.relations.append(PlatformRelation(
            relation_id=relation_id,
            platform_id=platform_id,
            attribute=attribute,
            value=value,
            confidence=confidence,
        ))

    def recommend_platform(self, audience_profile: Dict[str, str]) -> List[Dict[str, Any]]:
        results = []
        
        for platform_id, data in self.platforms.items():
            platform_props = data["properties"]
            score = 0.0

            country = audience_profile.get("country", "")
            if platform_props.get("region") == country or platform_props.get("region") == "global":
                score += 0.2

            os = audience_profile.get("os", "")
            if platform_props.get("os") == os or platform_props.get("os") == "all":
                score += 0.2

            age_range = audience_profile.get("age_range", "")
            platform_age = platform_props.get("target_age", "")
            if age_range and platform_age:
                score += 0.1

            score += data.get("performance", {}).get("efficiency", 0) * 0.3

            results.append({
                "platform_id": platform_id,
                "score": round(score, 2),
                "properties": platform_props,
                "performance": data.get("performance", {}),
            })

        return sorted(results, key=lambda x: x["score"], reverse=True)

    def find_best_performing(self, metric: str = "roas") -> Optional[Dict[str, Any]]:
        best = None
        best_value = 0
        
        for platform_id, data in self.platforms.items():
            value = data.get("performance", {}).get(metric, 0)
            if value > best_value:
                best_value = value
                best = {"platform_id": platform_id, metric: value, "properties": data["properties"]}
        
        return best

    def add_demo(self) -> None:
        self.add_platform(
            "meta_ios",
            {"platform": "meta", "os": "iOS", "region": "US", "target_age": "25-44"},
            {"roas": 2.8, "cpi": 2.2, "efficiency": 0.85},
        )
        self.add_platform(
            "google_android",
            {"platform": "google", "os": "Android", "region": "US", "target_age": "18-34"},
            {"roas": 2.2, "cpi": 1.8, "efficiency": 0.75},
        )
        self.add_platform(
            "tiktok_global",
            {"platform": "tiktok", "os": "all", "region": "global", "target_age": "18-24"},
            {"roas": 2.0, "cpi": 1.5, "efficiency": 0.8},
        )

    def recommend_demo(self) -> List[Dict[str, Any]]:
        self.add_demo()
        audience = {"country": "US", "os": "iOS", "age_range": "25-34"}
        return self.recommend_platform(audience)
