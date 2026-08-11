"""Audience Cluster - 受众聚类"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class AudienceProfile:
    """受众画像"""
    audience_id: str = ""
    country: str = ""
    os: str = ""
    gender: str = ""
    age_range: str = ""
    interests: List[str] = None
    device: str = ""
    game_genre: str = ""
    
    def __post_init__(self):
        if self.interests is None:
            self.interests = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "audience_id": self.audience_id,
            "country": self.country,
            "os": self.os,
            "gender": self.gender,
            "age_range": self.age_range,
            "interests": self.interests,
            "device": self.device,
            "game_genre": self.game_genre,
        }


@dataclass
class ClusterResult:
    """聚类结果"""
    cluster_id: str = ""
    audiences: List[AudienceProfile] = None
    size: int = 0
    characteristics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.audiences is None:
            self.audiences = []
        if self.characteristics is None:
            self.characteristics = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "characteristics": self.characteristics,
            "audience_count": len(self.audiences),
        }


class AudienceClusterEngine:
    """受众聚类引擎"""
    
    def __init__(self):
        self._audiences: Dict[str, AudienceProfile] = {}
        self._clusters: Dict[str, ClusterResult] = {}
    
    def add_audience(self, profile: AudienceProfile):
        """添加受众"""
        self._audiences[profile.audience_id] = profile
    
    def cluster(self, n_clusters: int = 5) -> List[ClusterResult]:
        """聚类受众"""
        audiences = list(self._audiences.values())
        
        if not audiences:
            return []
        
        clusters = []
        for i in range(min(n_clusters, len(audiences))):
            cluster_audiences = audiences[i::n_clusters]
            
            # 计算聚类特征
            characteristics = self._calculate_characteristics(cluster_audiences)
            
            cluster = ClusterResult(
                cluster_id=f"cluster_{i+1:03d}",
                audiences=cluster_audiences,
                size=len(cluster_audiences),
                characteristics=characteristics,
            )
            clusters.append(cluster)
            self._clusters[cluster.cluster_id] = cluster
        
        return clusters
    
    def _calculate_characteristics(self, audiences: List[AudienceProfile]) -> Dict[str, Any]:
        """计算聚类特征"""
        if not audiences:
            return {}
        
        # 统计各维度
        countries = {}
        os_types = {}
        genders = {}
        age_ranges = {}
        interests = {}
        
        for a in audiences:
            countries[a.country] = countries.get(a.country, 0) + 1
            os_types[a.os] = os_types.get(a.os, 0) + 1
            genders[a.gender] = genders.get(a.gender, 0) + 1
            age_ranges[a.age_range] = age_ranges.get(a.age_range, 0) + 1
            for interest in a.interests:
                interests[interest] = interests.get(interest, 0) + 1
        
        return {
            "top_country": max(countries, key=countries.get),
            "top_os": max(os_types, key=os_types.get),
            "top_gender": max(genders, key=genders.get),
            "top_age": max(age_ranges, key=age_ranges.get),
            "top_interests": sorted(interests, key=interests.get, reverse=True)[:3],
        }
    
    def get_cluster(self, cluster_id: str) -> ClusterResult:
        """获取聚类"""
        return self._clusters.get(cluster_id, ClusterResult(cluster_id=cluster_id))
    
    def cluster_demo(self) -> List[ClusterResult]:
        """演示聚类"""
        profiles = [
            AudienceProfile("a001", "US", "iOS", "Female", "30-44", ["casual games", "puzzle"], "iPhone", "Puzzle"),
            AudienceProfile("a002", "US", "iOS", "Female", "35-44", ["match-3", "relax"], "iPhone", "Puzzle"),
            AudienceProfile("a003", "US", "Android", "Male", "25-34", ["action", "RPG"], "Samsung", "Action"),
            AudienceProfile("a004", "UK", "iOS", "Female", "30-44", ["casual", "simulation"], "iPhone", "Simulation"),
            AudienceProfile("a005", "CA", "iOS", "Female", "25-34", ["puzzle", "brain"], "iPhone", "Puzzle"),
            AudienceProfile("a006", "US", "Android", "Male", "18-24", ["strategy", "war"], "Pixel", "Strategy"),
            AudienceProfile("a007", "AU", "iOS", "Female", "35-44", ["relax", "match-3"], "iPhone", "Puzzle"),
            AudienceProfile("a008", "US", "iOS", "Male", "30-44", ["RPG", "adventure"], "iPhone", "RPG"),
        ]
        
        for p in profiles:
            self.add_audience(p)
        
        return self.cluster(3)
