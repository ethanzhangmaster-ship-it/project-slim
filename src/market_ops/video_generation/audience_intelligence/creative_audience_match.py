"""Creative Audience Match - 创意受众匹配"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MatchResult:
    """匹配结果"""
    creative_id: str = ""
    audience_id: str = ""
    match_score: float = 0.0
    recommended_platform: str = ""
    recommended_placement: str = ""
    recommended_audience: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "audience_id": self.audience_id,
            "match_score": round(self.match_score, 2),
            "recommended_platform": self.recommended_platform,
            "recommended_placement": self.recommended_placement,
            "recommended_audience": self.recommended_audience,
            "confidence": round(self.confidence, 2),
        }


class CreativeAudienceMatcher:
    """创意受众匹配器"""
    
    def match(
        self,
        creative_dna: Dict[str, str],
        audience_profile: Dict[str, Any],
        creative_id: str = "",
        audience_id: str = "",
    ) -> MatchResult:
        """匹配创意和受众"""
        # 计算匹配分数
        match_score = self._calculate_match_score(creative_dna, audience_profile)
        
        # 推荐平台和受众
        platform, placement, audience_segment = self._generate_recommendations(creative_dna, audience_profile)
        
        # 计算置信度
        confidence = min(match_score * 1.1, 1.0)
        
        return MatchResult(
            creative_id=creative_id,
            audience_id=audience_id,
            match_score=match_score,
            recommended_platform=platform,
            recommended_placement=placement,
            recommended_audience=audience_segment,
            confidence=confidence,
        )
    
    def _calculate_match_score(self, creative_dna: Dict[str, str], audience_profile: Dict[str, Any]) -> float:
        """计算匹配分数"""
        score = 0.0
        
        # 游戏类型匹配
        genre = creative_dna.get("genre", "")
        audience_genre = audience_profile.get("game_genre", "")
        if genre and audience_genre and genre.lower() in audience_genre.lower():
            score += 0.3
        
        # 受众特征匹配
        hook = creative_dna.get("hook", "")
        if "cute" in hook.lower() or "merge" in hook.lower():
            if audience_profile.get("gender") == "Female":
                score += 0.2
        
        if "action" in hook.lower() or "battle" in hook.lower():
            if audience_profile.get("gender") == "Male":
                score += 0.2
        
        # 年龄匹配
        age_range = audience_profile.get("age_range", "")
        if age_range in ["30-44", "35-44"]:
            if "relax" in hook.lower() or "brain" in hook.lower():
                score += 0.2
        
        if age_range in ["18-24", "25-34"]:
            if "action" in hook.lower() or "fast" in hook.lower():
                score += 0.2
        
        # OS 匹配
        os_type = audience_profile.get("os", "")
        score += 0.1  # 默认基础分
        
        return min(score, 1.0)
    
    def _generate_recommendations(self, creative_dna: Dict[str, str], audience_profile: Dict[str, Any]) -> tuple:
        """生成推荐"""
        platform = "Meta"
        placement = "Feed"
        audience_segment = ""
        
        country = audience_profile.get("country", "")
        gender = audience_profile.get("gender", "")
        age_range = audience_profile.get("age_range", "")
        
        # 平台推荐
        if audience_profile.get("os") == "iOS":
            platform = "Meta"
        else:
            platform = "Google"
        
        # 受众推荐
        if gender and age_range:
            audience_segment = f"{gender} {age_range}"
        
        if country:
            audience_segment = f"{country} {audience_segment}"
        
        return platform, placement, audience_segment.strip()
    
    def match_demo(self) -> MatchResult:
        """演示匹配"""
        creative_dna = {
            "hook": "cute creature merge surprise reward",
            "genre": "Puzzle",
            "camera": "close_up",
        }
        
        audience_profile = {
            "country": "US",
            "os": "iOS",
            "gender": "Female",
            "age_range": "30-44",
            "game_genre": "Puzzle",
        }
        
        return self.match(creative_dna, audience_profile, "creative_001", "audience_001")
