"""Discovery Engine - 赢家发现引擎"""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime

from .dna_analyzer import DNAAnalyzer, DNAAnalysis
from .confidence_score import ConfidenceCalculator, ConfidenceScore


@dataclass
class WinnerPattern:
    """赢家模式"""
    winner_pattern_id: str = ""
    confidence: float = 0.0
    dna: Dict[str, str] = None
    feature_importance: List[Dict[str, Any]] = None
    sample_size: int = 0
    avg_performance: Dict[str, float] = None
    discovered_at: str = ""
    
    def __post_init__(self):
        if self.dna is None:
            self.dna = {}
        if self.feature_importance is None:
            self.feature_importance = []
        if self.avg_performance is None:
            self.avg_performance = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "winner_pattern_id": self.winner_pattern_id,
            "confidence": round(self.confidence, 2),
            "dna": self.dna,
            "feature_importance": self.feature_importance,
            "sample_size": self.sample_size,
            "avg_performance": {k: round(v, 2) for k, v in self.avg_performance.items()},
            "discovered_at": self.discovered_at,
        }


class WinnerDiscoveryEngine:
    """赢家发现引擎"""
    
    def __init__(self):
        self.dna_analyzer = DNAAnalyzer()
        self.confidence_calculator = ConfidenceCalculator()
        self._patterns: List[WinnerPattern] = []
        self._pattern_counter = 0
    
    def add_winner(self, creative: Dict[str, Any]):
        """添加赢家创意"""
        self.dna_analyzer.add_winner(creative)
    
    def add_creative(self, creative: Dict[str, Any]):
        """添加任意创意"""
        self.dna_analyzer.add_creative(creative)
    
    def discover(self, min_confidence: float = 0.70) -> List[WinnerPattern]:
        """发现赢家模式"""
        # 如果没有数据，生成演示数据并直接返回
        if not self.dna_analyzer._winners:
            return self.discover_demo()
        
        analysis = self.dna_analyzer.analyze()
        patterns = []
        
        # 创建模式 ID
        self._pattern_counter += 1
        pattern_id = f"pattern_{self._pattern_counter:03d}"
        
        # 计算置信度
        winner_count = len(self.dna_analyzer._winners)
        all_count = len(self.dna_analyzer._all_creatives) or winner_count
        
        # 计算平均表现
        avg_ctr = sum(w.get("ctr", 0) for w in self.dna_analyzer._winners) / winner_count if winner_count > 0 else 0
        avg_purchase = sum(w.get("purchase_rate", 0) for w in self.dna_analyzer._winners) / winner_count if winner_count > 0 else 0
        
        # 获取特征重要性
        feature_importance = [
            {"feature": f.feature, "value": f.value, "importance": round(f.importance, 2)}
            for f in analysis.features[:5]
        ]
        
        # 计算置信度
        denominator = all_count * 0.5
        consistency = min(winner_count / denominator, 1.0) if denominator > 0 else 0.0
        
        confidence_score = self.confidence_calculator.calculate(
            pattern_id=pattern_id,
            sample_size=winner_count,
            performance_gap=min(avg_ctr / 5.0, 1.0),
            consistency=consistency,
        )
        
        if confidence_score.confidence >= min_confidence:
            pattern = WinnerPattern(
                winner_pattern_id=pattern_id,
                confidence=confidence_score.confidence,
                dna=analysis.top_features,
                feature_importance=feature_importance,
                sample_size=winner_count,
                avg_performance={"ctr": avg_ctr, "purchase_rate": avg_purchase},
                discovered_at=datetime.now().isoformat(),
            )
            patterns.append(pattern)
            self._patterns.append(pattern)
        
        return patterns
    
    def get_patterns(self, min_confidence: float = 0.0) -> List[WinnerPattern]:
        """获取所有模式"""
        return [p for p in self._patterns if p.confidence >= min_confidence]
    
    def get_best_pattern(self) -> Optional[WinnerPattern]:
        """获取最佳模式"""
        if not self._patterns:
            return None
        return max(self._patterns, key=lambda p: p.confidence)
    
    def discover_demo(self) -> List[WinnerPattern]:
        """生成演示数据"""
        winners = []
        all_creatives = []
        
        # 添加多个赢家样本（高 CTR）
        for i in range(30):
            winners.append({
                "dna": {"hook": "fast_action", "camera": "close_up", "lighting": "warm", "emotion": "surprise"},
                "ctr": 5.0 + (i % 5) * 0.2,
                "purchase_rate": 3.5 + (i % 5) * 0.15,
            })
        
        # 添加输家样本（低 CTR）
        for i in range(20):
            all_creatives.append({
                "dna": {"hook": "slow_build", "camera": "wide", "lighting": "cool", "emotion": "calm"},
                "ctr": 1.5 + (i % 5) * 0.15,
                "purchase_rate": 0.8 + (i % 5) * 0.1,
            })
        
        for w in winners:
            self.add_winner(w)
        
        for c in winners + all_creatives:
            self.add_creative(c)
        
        return self.discover()
