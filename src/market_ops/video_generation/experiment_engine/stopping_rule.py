"""Stopping Rule - 停止规则"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class StopDecision:
    """停止决策"""
    test_id: str = ""
    should_stop: bool = False
    winner: str = ""
    reason: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "should_stop": self.should_stop,
            "winner": self.winner,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
        }


class StoppingRuleEngine:
    """停止规则引擎"""
    
    def evaluate(self, test_id: str, variants: List[Dict[str, Any]]) -> StopDecision:
        """评估是否停止测试"""
        if not variants:
            return StopDecision(test_id=test_id)
        
        # 计算各变体分数
        scores = {}
        total_sample = 0
        
        for variant in variants:
            ctr = variant.get("ctr", 0.0)
            cvr = variant.get("cvr", 0.0)
            roas = variant.get("roas", 0.0)
            sample = variant.get("sample_size", 0)
            variant_id = variant.get("variant_id", "")
            
            # 综合分数
            score = ctr * 0.3 + cvr * 0.3 + roas * 0.4
            scores[variant_id] = score
            total_sample += sample
        
        # 找出赢家
        winner = max(scores, key=scores.get)
        winner_score = scores[winner]
        
        # 计算与第二名的差距
        sorted_scores = sorted(scores.values(), reverse=True)
        gap = 0.0
        if len(sorted_scores) >= 2:
            gap = (winner_score - sorted_scores[1]) / max(sorted_scores[1], 1)
        
        # 判断是否停止
        should_stop = False
        reason = ""
        confidence = 0.0
        
        # 规则 1: 高置信度赢家
        if gap >= 0.2 and total_sample >= 10000:
            should_stop = True
            reason = f"Clear winner ({winner}) with {gap:.0%} advantage"
            confidence = min(0.95, gap + 0.5)
        
        # 规则 2: 样本量足够大且胜率稳定
        elif total_sample >= 20000:
            should_stop = True
            reason = "Sample size threshold reached"
            confidence = 0.90
        
        # 规则 3: 预算耗尽
        elif total_sample >= 50000:
            should_stop = True
            reason = "Maximum sample size reached"
            confidence = 0.85
        
        return StopDecision(
            test_id=test_id,
            should_stop=should_stop,
            winner=winner,
            reason=reason,
            confidence=confidence,
        )
    
    def evaluate_demo(self) -> StopDecision:
        """演示停止规则评估"""
        variants = [
            {"variant_id": "A", "ctr": 5.8, "cvr": 4.2, "roas": 1.8, "sample_size": 5000},
            {"variant_id": "B", "ctr": 7.2, "cvr": 5.1, "roas": 2.3, "sample_size": 5000},
            {"variant_id": "C", "ctr": 3.1, "cvr": 2.5, "roas": 0.9, "sample_size": 5000},
        ]
        
        return self.evaluate("test_001", variants)
