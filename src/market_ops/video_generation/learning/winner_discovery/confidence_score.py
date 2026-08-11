"""Confidence Score - 置信度评分"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ConfidenceScore:
    """置信度评分"""
    pattern_id: str = ""
    confidence: float = 0.0
    sample_size: int = 0
    performance_gap: float = 0.0
    consistency: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "confidence": round(self.confidence, 2),
            "sample_size": self.sample_size,
            "performance_gap": round(self.performance_gap, 2),
            "consistency": round(self.consistency, 2),
        }


class ConfidenceCalculator:
    """置信度计算器"""
    
    def calculate(
        self,
        pattern_id: str,
        sample_size: int,
        performance_gap: float,
        consistency: float,
    ) -> ConfidenceScore:
        """计算置信度
        
        Confidence = Sample Size × Performance Gap × Consistency
        
        Args:
            pattern_id: 模式ID
            sample_size: 样本数量
            performance_gap: 表现差距 (0-1)
            consistency: 一致性 (0-1)
        
        Returns:
            ConfidenceScore
        """
        # 标准化样本大小 (0-1)
        normalized_sample = min(sample_size / 50.0, 1.0)
        
        # 置信度公式: Confidence = Sample Size × Performance Gap × Consistency
        confidence = normalized_sample * performance_gap * consistency * 2
        
        return ConfidenceScore(
            pattern_id=pattern_id,
            confidence=min(confidence, 1.0),
            sample_size=sample_size,
            performance_gap=performance_gap,
            consistency=consistency,
        )
    
    def calculate_from_winners(
        self,
        pattern_id: str,
        winner_count: int,
        total_count: int,
        avg_winner_ctr: float,
        avg_loser_ctr: float,
    ) -> ConfidenceScore:
        """从赢家数据计算置信度"""
        sample_size = winner_count
        performance_gap = self._calculate_performance_gap(avg_winner_ctr, avg_loser_ctr)
        consistency = self._calculate_consistency(winner_count, total_count)
        
        return self.calculate(pattern_id, sample_size, performance_gap, consistency)
    
    def _calculate_performance_gap(self, winner_ctr: float, loser_ctr: float) -> float:
        """计算表现差距"""
        if loser_ctr <= 0:
            return min(winner_ctr / 5.0, 1.0)
        ratio = winner_ctr / loser_ctr
        return min((ratio - 1) / 2, 1.0)
    
    def _calculate_consistency(self, winner_count: int, total_count: int) -> float:
        """计算一致性"""
        if total_count == 0:
            return 0.0
        return min(winner_count / (total_count * 0.5), 1.0)
