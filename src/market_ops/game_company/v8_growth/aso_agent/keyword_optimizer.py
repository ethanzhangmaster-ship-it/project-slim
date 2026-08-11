from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class KeywordStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    TESTING = "testing"
    ARCHIVED = "archived"


class KeywordDifficulty(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class KeywordData:
    keyword_id: str
    keyword: str
    position: int = 0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    ctr: float = 0.0
    conversion_rate: float = 0.0
    difficulty: KeywordDifficulty = KeywordDifficulty.MEDIUM
    status: KeywordStatus = KeywordStatus.ACTIVE
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword_id": self.keyword_id,
            "keyword": self.keyword,
            "position": self.position,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "ctr": self.ctr,
            "conversion_rate": self.conversion_rate,
            "difficulty": self.difficulty.value,
            "status": self.status.value,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class KeywordRecommendation:
    keyword: str
    action: str
    reason: str = ""
    expected_position_change: int = 0
    priority: int = 5
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "action": self.action,
            "reason": self.reason,
            "expected_position_change": self.expected_position_change,
            "priority": self.priority,
            "confidence": self.confidence,
        }


@dataclass
class KeywordCluster:
    cluster_id: str
    name: str
    keywords: List[str] = field(default_factory=list)
    avg_position: float = 0.0
    total_impressions: int = 0
    total_installs: int = 0
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "keywords": self.keywords,
            "avg_position": self.avg_position,
            "total_impressions": self.total_impressions,
            "total_installs": self.total_installs,
            "relevance_score": self.relevance_score,
        }


class KeywordOptimizer:
    def __init__(self):
        self._keywords: Dict[str, KeywordData] = {}
        self._clusters: Dict[str, KeywordCluster] = {}
        self._recommendations: List[KeywordRecommendation] = []
        self._position_history: Dict[str, List[int]] = {}
        self._target_positions: Dict[str, int] = {}

    def register_keyword(self, keyword: str, position: int = 0, **kwargs) -> KeywordData:
        keyword_id = f"kw_{keyword.replace(' ', '_').lower()}"
        kw_data = KeywordData(
            keyword_id=keyword_id,
            keyword=keyword,
            position=position,
            **{k: v for k, v in kwargs.items() if hasattr(KeywordData, k)}
        )
        self._keywords[keyword_id] = kw_data
        return kw_data

    def analyze_keywords(self) -> Dict[str, Any]:
        analysis = {
            "total_keywords": len(self._keywords),
            "active_keywords": sum(1 for k in self._keywords.values() if k.status == KeywordStatus.ACTIVE),
            "average_position": sum(k.position for k in self._keywords.values()) / len(self._keywords) if self._keywords else 0,
            "top_positions": [k.keyword for k in self._keywords.values() if k.position <= 10],
            "improvement_candidates": [],
            "high_difficulty_keywords": [],
        }

        for kw in self._keywords.values():
            if kw.position > 20 and kw.position < 50 and kw.difficulty != KeywordDifficulty.VERY_HIGH:
                analysis["improvement_candidates"].append(kw.keyword)
            if kw.difficulty in [KeywordDifficulty.HIGH, KeywordDifficulty.VERY_HIGH]:
                analysis["high_difficulty_keywords"].append(kw.keyword)

        return analysis

    def optimize_keywords(self) -> List[KeywordRecommendation]:
        recommendations = []
        for kw_id, kw_data in self._keywords.items():
            if kw_data.status != KeywordStatus.ACTIVE:
                continue

            if kw_data.position > 20:
                rec = KeywordRecommendation(
                    keyword=kw_data.keyword,
                    action="optimize",
                    reason=f"Position {kw_data.position} is below optimal threshold",
                    expected_position_change=-5,
                    priority=1 if kw_data.difficulty == KeywordDifficulty.LOW else 3,
                    confidence=random.uniform(0.7, 0.9),
                )
                recommendations.append(rec)

            if kw_data.ctr < 0.05 and kw_data.position <= 10:
                rec = KeywordRecommendation(
                    keyword=kw_data.keyword,
                    action="improve_metadata",
                    reason=f"CTR {kw_data.ctr:.2%} is low despite good position",
                    expected_position_change=0,
                    priority=2,
                    confidence=0.8,
                )
                recommendations.append(rec)

            if kw_data.position <= 5 and kw_data.difficulty == KeywordDifficulty.LOW:
                rec = KeywordRecommendation(
                    keyword=kw_data.keyword,
                    action="maintain",
                    reason="Strong position on low difficulty keyword - maintain current strategy",
                    expected_position_change=0,
                    priority=5,
                    confidence=0.95,
                )
                recommendations.append(rec)

        self._recommendations.extend(recommendations)
        return recommendations

    def get_keyword_suggestions(self, existing_keywords: List[str] = None) -> List[str]:
        base_keywords = ["game", "play", "free", "download", "mobile", "online", "adventure", "puzzle", "strategy", "action"]
        existing = existing_keywords or [k.keyword for k in self._keywords.values()]

        suggestions = []
        for base in base_keywords:
            variations = [
                f"best {base}",
                f"{base} game",
                f"free {base}",
                f"new {base}",
                f"{base} app",
            ]
            suggestions.extend(variations)

        suggestions = [s for s in suggestions if s not in existing]
        return suggestions[:20]

    def create_cluster(self, name: str, keywords: List[str]) -> KeywordCluster:
        cluster_id = f"cluster_{name.replace(' ', '_').lower()}"
        cluster = KeywordCluster(
            cluster_id=cluster_id,
            name=name,
            keywords=keywords,
        )
        self._clusters[cluster_id] = cluster
        return cluster

    def get_keyword(self, keyword_id: str) -> Optional[KeywordData]:
        return self._keywords.get(keyword_id)

    def get_keyword_by_name(self, keyword: str) -> Optional[KeywordData]:
        for kw in self._keywords.values():
            if kw.keyword == keyword:
                return kw
        return None

    def update_position(self, keyword_id: str, new_position: int) -> Optional[KeywordData]:
        kw = self._keywords.get(keyword_id)
        if kw:
            kw.position = new_position
            kw.last_updated = datetime.now()
            if keyword_id not in self._position_history:
                self._position_history[keyword_id] = []
            self._position_history[keyword_id].append(new_position)
        return kw

    def get_position_history(self, keyword_id: str) -> List[int]:
        return self._position_history.get(keyword_id, [])

    def get_all_keywords(self) -> List[KeywordData]:
        return list(self._keywords.values())

    def get_recommendations(self) -> List[KeywordRecommendation]:
        return list(self._recommendations)

    def get_clusters(self) -> List[KeywordCluster]:
        return list(self._clusters.values())

    def get_stats(self) -> Dict[str, Any]:
        keywords = list(self._keywords.values())
        return {
            "total_keywords": len(keywords),
            "keywords_by_status": {
                status.value: sum(1 for k in keywords if k.status == status)
                for status in KeywordStatus
            },
            "keywords_by_difficulty": {
                diff.value: sum(1 for k in keywords if k.difficulty == diff)
                for diff in KeywordDifficulty
            },
            "average_position": sum(k.position for k in keywords) / len(keywords) if keywords else 0,
            "keywords_in_top_10": sum(1 for k in keywords if k.position <= 10),
            "total_recommendations": len(self._recommendations),
            "total_clusters": len(self._clusters),
        }