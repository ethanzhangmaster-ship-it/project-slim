"""Keyword Match - 关键词匹配"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class KeywordMatchResult:
    """关键词匹配结果"""
    app_id: str = ""
    creative_keywords: List[str] = None
    store_keywords: List[str] = None
    match_score: float = 0.0
    matched_keywords: List[str] = None
    missing_keywords: List[str] = None
    
    def __post_init__(self):
        if self.creative_keywords is None:
            self.creative_keywords = []
        if self.store_keywords is None:
            self.store_keywords = []
        if self.matched_keywords is None:
            self.matched_keywords = []
        if self.missing_keywords is None:
            self.missing_keywords = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "creative_keywords": self.creative_keywords,
            "store_keywords": self.store_keywords,
            "match_score": round(self.match_score, 2),
            "matched_keywords": self.matched_keywords,
            "missing_keywords": self.missing_keywords,
        }


class KeywordMatcher:
    """关键词匹配器"""
    
    def match(self, creative_keywords: List[str], store_keywords: List[str], app_id: str = "") -> KeywordMatchResult:
        """匹配关键词"""
        creative_set = set(k.lower() for k in creative_keywords)
        store_set = set(k.lower() for k in store_keywords)
        
        # 匹配的关键词
        matched = list(creative_set & store_set)
        
        # 缺失的关键词
        missing = list(creative_set - store_set)
        
        # 匹配分数
        match_score = len(matched) / max(len(creative_set), 1)
        
        return KeywordMatchResult(
            app_id=app_id,
            creative_keywords=creative_keywords,
            store_keywords=store_keywords,
            match_score=match_score,
            matched_keywords=matched,
            missing_keywords=missing,
        )
    
    def suggest_keywords(self, creative_keywords: List[str], store_keywords: List[str]) -> List[str]:
        """建议添加的关键词"""
        creative_set = set(k.lower() for k in creative_keywords)
        store_set = set(k.lower() for k in store_keywords)
        
        return list(creative_set - store_set)
    
    def match_demo(self) -> KeywordMatchResult:
        """演示关键词匹配"""
        creative_keywords = ["merge", "dragon", "magic", "adventure"]
        store_keywords = ["puzzle", "brain", "relax", "game"]
        
        return self.match(creative_keywords, store_keywords, "com.example.game")
