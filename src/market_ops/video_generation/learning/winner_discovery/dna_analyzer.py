"""DNA Analyzer - DNA 分析器"""
from dataclasses import dataclass
from typing import Dict, List, Any
from collections import Counter


@dataclass
class DNAFeature:
    """DNA 特征"""
    feature: str = ""
    value: str = ""
    importance: float = 0.0
    winner_count: int = 0
    total_count: int = 0
    winner_probability: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "value": self.value,
            "importance": round(self.importance, 2),
            "winner_count": self.winner_count,
            "total_count": self.total_count,
            "winner_probability": round(self.winner_probability, 2),
        }


@dataclass
class DNAAnalysis:
    """DNA 分析结果"""
    features: List[DNAFeature] = None
    top_features: Dict[str, str] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.top_features is None:
            self.top_features = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "features": [f.to_dict() for f in self.features],
            "top_features": self.top_features,
        }


class DNAAnalyzer:
    """DNA 分析器"""
    
    DNA_ELEMENTS = ["hook", "camera", "lighting", "scene", "character", "emotion", "cta", "style"]
    
    def __init__(self):
        self._winners: List[Dict[str, Any]] = []
        self._all_creatives: List[Dict[str, Any]] = []
    
    def add_winner(self, creative: Dict[str, Any]):
        """添加赢家创意"""
        self._winners.append(creative)
    
    def add_creative(self, creative: Dict[str, Any]):
        """添加任意创意"""
        self._all_creatives.append(creative)
    
    def analyze(self) -> DNAAnalysis:
        """分析 DNA 特征"""
        features = []
        top_features = {}
        
        for element in self.DNA_ELEMENTS:
            element_features = self._analyze_element(element)
            features.extend(element_features)
            
            if element_features:
                top_feature = max(element_features, key=lambda f: f.importance)
                top_features[element] = top_feature.value
        
        return DNAAnalysis(
            features=sorted(features, key=lambda f: f.importance, reverse=True),
            top_features=top_features,
        )
    
    def _analyze_element(self, element: str) -> List[DNAFeature]:
        """分析单个 DNA 元素"""
        features = []
        
        # 统计赢家和整体中的值分布
        winner_values = []
        all_values = []
        
        for winner in self._winners:
            dna = winner.get("dna", {})
            if element in dna:
                winner_values.append(dna[element])
        
        for creative in self._all_creatives:
            dna = creative.get("dna", {})
            if element in dna:
                all_values.append(dna[element])
        
        if not winner_values:
            return features
        
        # 统计每个值的重要性
        value_counter = Counter(winner_values)
        all_counter = Counter(all_values)
        
        total_winners = len(winner_values)
        total_all = len(all_values) if all_values else total_winners
        
        for value, winner_count in value_counter.items():
            total_count = all_counter.get(value, 0)
            
            # 重要性 = (赢家出现次数/总赢家) / (整体出现次数/总创意)
            if total_count == 0:
                importance = 0.0
            else:
                winner_ratio = winner_count / total_winners
                all_ratio = total_count / total_all
                importance = winner_ratio / all_ratio if all_ratio > 0 else 1.0
            
            importance = min(importance, 10.0) / 10.0  # 标准化到 0-1
            
            features.append(DNAFeature(
                feature=element,
                value=value,
                importance=importance,
                winner_count=winner_count,
                total_count=total_count,
                winner_probability=winner_count / total_winners,
            ))
        
        return features
    
    def get_feature_importance(self, element: str, value: str) -> float:
        """获取特定特征的重要性"""
        analysis = self.analyze()
        for feature in analysis.features:
            if feature.feature == element and feature.value == value:
                return feature.importance
        return 0.0
    
    def get_top_n_features(self, n: int = 5) -> List[DNAFeature]:
        """获取 Top N 特征"""
        analysis = self.analyze()
        return analysis.features[:n]
    
    def analyze_feature(self, element: str, value: str, winner_count: int = 0) -> DNAFeature:
        """分析单个特征"""
        importance = self.get_feature_importance(element, value)
        if importance == 0 and winner_count > 0:
            importance = min(winner_count / 50.0, 0.85)
        
        return DNAFeature(
            feature=element,
            value=value,
            importance=importance,
            winner_count=winner_count,
        )
    
    def analyze_all_features(self, dna: Dict[str, str]) -> List[DNAFeature]:
        """分析所有特征"""
        features = []
        for element, value in dna.items():
            importance = self.get_feature_importance(element, value)
            features.append(DNAFeature(
                feature=element,
                value=value,
                importance=importance,
            ))
        return features
    
    def get_top_features(self, n: int = 5) -> List[DNAFeature]:
        """获取 Top N 特征"""
        return self.get_top_n_features(n)
    
    def calculate_winner_probability(self, dna: Dict[str, str]) -> float:
        """计算赢家概率"""
        total_importance = 0.0
        count = 0
        
        for element, value in dna.items():
            importance = self.get_feature_importance(element, value)
            total_importance += importance
            count += 1
        
        if count == 0:
            return 0.0
        
        return min(total_importance / count, 1.0)
