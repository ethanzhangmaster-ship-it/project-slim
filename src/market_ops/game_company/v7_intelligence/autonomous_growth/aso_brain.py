from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class ASORecommendation:
    recommendation_id: str
    category: str
    priority: str
    action: str
    expected_impact: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KeywordOptimization:
    keyword: str
    current_rank: int
    target_rank: int
    search_volume: int
    difficulty: float
    opportunity_score: float
    suggestions: List[str] = field(default_factory=list)


class ASOBrain:
    """ASO 大脑，负责应用商店优化。"""

    def __init__(self):
        self.keywords: List[Dict[str, Any]] = []
        self.rankings: Dict[str, int] = {}

    def optimize_keywords(self, current_keywords: List[str], competitor_keywords: List[str]) -> List[KeywordOptimization]:
        """优化关键词策略。"""
        results = []
        all_keywords = list(set(current_keywords + competitor_keywords))
        for i, kw in enumerate(all_keywords):
            volume = 10000 - i * 500
            difficulty = round(0.3 + (i % 5) * 0.1, 2)
            current_rank = self.rankings.get(kw, 50 + i * 3)
            opportunity = round((volume / 10000) * (1 - difficulty) * 100, 2)

            opt = KeywordOptimization(
                keyword=kw,
                current_rank=current_rank,
                target_rank=max(1, current_rank - 10),
                search_volume=max(volume, 1000),
                difficulty=difficulty,
                opportunity_score=opportunity,
                suggestions=[f"增加 {kw} 在标题中的密度", "优化副标题"] if opportunity > 50 else ["保持监控"],
            )
            results.append(opt)
        return sorted(results, key=lambda x: x.opportunity_score, reverse=True)

    def optimize_metadata(self, metadata: Dict[str, Any]) -> List[ASORecommendation]:
        """优化应用商店元数据。"""
        recommendations = []
        title = metadata.get("title", "")
        subtitle = metadata.get("subtitle", "")
        description = metadata.get("description", "")

        if len(title) < 20:
            recommendations.append(
                ASORecommendation(
                    recommendation_id="aso_title_001",
                    category="title",
                    priority="high",
                    action="extend_title",
                    expected_impact="+5% 曝光",
                    details={"current_length": len(title), "suggested_length": 25},
                )
            )
        if len(subtitle) < 20:
            recommendations.append(
                ASORecommendation(
                    recommendation_id="aso_sub_001",
                    category="subtitle",
                    priority="medium",
                    action="enhance_subtitle",
                    expected_impact="+3% 转化",
                    details={"current_length": len(subtitle)},
                )
            )
        if len(description) < 100:
            recommendations.append(
                ASORecommendation(
                    recommendation_id="aso_desc_001",
                    category="description",
                    priority="medium",
                    action="expand_description",
                    expected_impact="+2% 搜索权重",
                    details={"current_length": len(description)},
                )
            )
        return recommendations

    def analyze_ranking(self, keyword: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析特定关键词的排名趋势。"""
        ranks = [h.get("rank", 100) for h in history if h.get("keyword") == keyword]
        if not ranks:
            return {"keyword": keyword, "trend": "unknown", "avg_rank": None}

        avg_rank = sum(ranks) / len(ranks)
        trend = "improving" if ranks[-1] < ranks[0] else "declining" if ranks[-1] > ranks[0] else "stable"
        return {
            "keyword": keyword,
            "trend": trend,
            "avg_rank": round(avg_rank, 1),
            "current_rank": ranks[-1],
            "change": ranks[0] - ranks[-1],
            "analyzed_at": datetime.now().isoformat(),
        }

    def suggest_changes(self, app_metadata: Dict[str, Any]) -> List[ASORecommendation]:
        """基于整体 ASO 状况给出改进建议。"""
        recommendations = []
        screenshots = app_metadata.get("screenshots", [])
        if len(screenshots) < 5:
            recommendations.append(
                ASORecommendation(
                    recommendation_id="aso_ss_001",
                    category="screenshots",
                    priority="high",
                    action="add_more_screenshots",
                    expected_impact="+8% 转化",
                    details={"current_count": len(screenshots), "recommended": 8},
                )
            )
        if not app_metadata.get("video_preview"):
            recommendations.append(
                ASORecommendation(
                    recommendation_id="aso_vid_001",
                    category="video",
                    priority="medium",
                    action="add_preview_video",
                    expected_impact="+10% 转化",
                    details={},
                )
            )
        return recommendations
