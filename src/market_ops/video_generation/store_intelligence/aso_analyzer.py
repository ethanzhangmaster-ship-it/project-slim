"""ASO Analyzer - ASO 分析器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class ASOData:
    """ASO 数据"""
    app_id: str = ""
    title: str = ""
    subtitle: str = ""
    description: str = ""
    keywords: List[str] = None
    category: str = ""
    rating: float = 0.0
    reviews: int = 0
    downloads: int = 0
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "keywords": self.keywords,
            "category": self.category,
            "rating": round(self.rating, 2),
            "reviews": self.reviews,
            "downloads": self.downloads,
        }


@dataclass
class ASOAnalysis:
    """ASO 分析结果"""
    app_id: str = ""
    title_score: float = 0.0
    keyword_score: float = 0.0
    description_score: float = 0.0
    overall_score: float = 0.0
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "title_score": round(self.title_score, 2),
            "keyword_score": round(self.keyword_score, 2),
            "description_score": round(self.description_score, 2),
            "overall_score": round(self.overall_score, 2),
            "suggestions": self.suggestions,
        }


class ASOAnalyzer:
    """ASO 分析器"""
    
    def analyze(self, aso_data: ASOData) -> ASOAnalysis:
        """分析 ASO"""
        title_score = self._score_title(aso_data)
        keyword_score = self._score_keywords(aso_data)
        description_score = self._score_description(aso_data)
        
        overall_score = (title_score * 0.4 + keyword_score * 0.3 + description_score * 0.3)
        
        suggestions = self._generate_suggestions(aso_data, title_score, keyword_score, description_score)
        
        return ASOAnalysis(
            app_id=aso_data.app_id,
            title_score=title_score,
            keyword_score=keyword_score,
            description_score=description_score,
            overall_score=overall_score,
            suggestions=suggestions,
        )
    
    def _score_title(self, data: ASOData) -> float:
        """评分标题"""
        score = 0.0
        
        if len(data.title) >= 10:
            score += 0.3
        
        if any(k.lower() in data.title.lower() for k in data.keywords[:3]):
            score += 0.4
        
        if len(data.title) <= 50:
            score += 0.3
        
        return min(score, 1.0)
    
    def _score_keywords(self, data: ASOData) -> float:
        """评分关键词"""
        score = 0.0
        
        if len(data.keywords) >= 5:
            score += 0.3
        
        if len(data.keywords) <= 10:
            score += 0.2
        
        # 关键词多样性
        unique_keywords = set(k.lower() for k in data.keywords)
        if len(unique_keywords) >= len(data.keywords) * 0.8:
            score += 0.5
        
        return min(score, 1.0)
    
    def _score_description(self, data: ASOData) -> float:
        """评分描述"""
        score = 0.0
        
        if len(data.description) >= 100:
            score += 0.3
        
        if any(k.lower() in data.description.lower() for k in data.keywords[:5]):
            score += 0.4
        
        if len(data.description) <= 500:
            score += 0.3
        
        return min(score, 1.0)
    
    def _generate_suggestions(self, data: ASOData, title_score: float, keyword_score: float, description_score: float) -> List[str]:
        """生成建议"""
        suggestions = []
        
        if title_score < 0.7:
            suggestions.append("Include main keywords in title")
        
        if keyword_score < 0.7:
            suggestions.append("Add more relevant keywords")
        
        if description_score < 0.7:
            suggestions.append("Expand description and include keywords")
        
        return suggestions
    
    def analyze_demo(self) -> ASOAnalysis:
        """演示 ASO 分析"""
        aso_data = ASOData(
            app_id="com.example.game",
            title="Merge Dragon Magic Adventure",
            subtitle="Puzzle Game",
            description="Play the best merge puzzle game! Merge dragons and discover magic adventures.",
            keywords=["merge", "dragon", "magic", "puzzle", "adventure"],
            category="Games",
            rating=4.5,
            reviews=10000,
            downloads=500000,
        )
        
        return self.analyze(aso_data)
