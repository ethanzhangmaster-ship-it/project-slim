"""Bayesian Optimizer - 贝叶斯优化器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class BayesianResult:
    """贝叶斯优化结果"""
    test_id: str = ""
    variant_id: str = ""
    probability: float = 0.0
    expected_improvement: float = 0.0
    exploitation_value: float = 0.0
    exploration_value: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "variant_id": self.variant_id,
            "probability": round(self.probability, 2),
            "expected_improvement": round(self.expected_improvement, 2),
            "exploitation_value": round(self.exploitation_value, 2),
            "exploration_value": round(self.exploration_value, 2),
        }


class BayesianOptimizer:
    """贝叶斯优化器"""
    
    def update(self, test_id: str, variant_id: str, reward: float, sample_size: int = 1000):
        """更新贝叶斯模型"""
        pass
    
    def predict(self, test_id: str) -> List[BayesianResult]:
        """预测各变体的胜率"""
        return []
    
    def recommend(self, test_id: str, variants: List[Dict[str, Any]]) -> str:
        """推荐下一个要测试的变体"""
        if not variants:
            return ""
        
        scores = {}
        
        for variant in variants:
            ctr = variant.get("ctr", 0.0)
            cvr = variant.get("cvr", 0.0)
            sample = variant.get("sample_size", 0)
            variant_id = variant.get("variant_id", "")
            
            # Upper Confidence Bound
            # UCB = exploitation + exploration
            exploitation = (ctr * 0.5 + cvr * 0.5) * min(sample / 5000, 1)
            exploration = (5000 / max(sample, 1)) ** 0.5 * 0.1
            
            scores[variant_id] = exploitation + exploration
        
        return max(scores, key=scores.get) if scores else ""
    
    def calculate_winner_probabilities(self, variants: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算各变体的胜率"""
        scores = {}
        
        for variant in variants:
            ctr = variant.get("ctr", 0.0)
            cvr = variant.get("cvr", 0.0)
            roas = variant.get("roas", 0.0)
            sample = variant.get("sample_size", 0)
            
            # 综合评分
            base_score = ctr * 0.3 + cvr * 0.3 + roas * 0.4
            sample_factor = min(sample / 1000, 1)
            
            scores[variant.get("variant_id", "")] = base_score * sample_factor
        
        # 归一化
        total = sum(scores.values()) or 1
        probabilities = {k: v / total for k, v in scores.items()}
        
        return probabilities
    
    def recommend_demo(self) -> str:
        """演示推荐"""
        variants = [
            {"variant_id": "A", "ctr": 5.8, "cvr": 4.2, "roas": 1.8, "sample_size": 5000},
            {"variant_id": "B", "ctr": 7.2, "cvr": 5.1, "roas": 2.3, "sample_size": 5000},
            {"variant_id": "C", "ctr": 3.1, "cvr": 2.5, "roas": 0.9, "sample_size": 5000},
        ]
        
        return self.recommend("test_001", variants)
