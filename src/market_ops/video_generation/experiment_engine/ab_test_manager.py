"""A/B Test Manager - A/B 测试管理器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class TestVariant:
    """测试变体"""
    variant_id: str = ""
    creative_id: str = ""
    dna: Dict[str, str] = None
    metrics: Dict[str, Any] = None
    sample_size: int = 0
    
    def __post_init__(self):
        if self.dna is None:
            self.dna = {}
        if self.metrics is None:
            self.metrics = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "creative_id": self.creative_id,
            "dna": self.dna,
            "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in self.metrics.items()},
            "sample_size": self.sample_size,
        }


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    test_id: str = ""
    winner: str = ""
    variants: List[TestVariant] = None
    probabilities: Dict[str, float] = None
    should_stop: bool = False
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.variants is None:
            self.variants = []
        if self.probabilities is None:
            self.probabilities = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "winner": self.winner,
            "variants": [v.to_dict() for v in self.variants],
            "probabilities": {k: round(v, 2) for k, v in self.probabilities.items()},
            "should_stop": self.should_stop,
            "confidence": round(self.confidence, 2),
        }


class ABTestManager:
    """A/B 测试管理器"""
    
    def __init__(self):
        self._tests: Dict[str, List[TestVariant]] = {}
    
    def create_test(self, test_id: str, variants: List[TestVariant]):
        """创建测试"""
        self._tests[test_id] = variants
    
    def update_variant(self, test_id: str, variant_id: str, metrics: Dict[str, Any], sample_size: int = 0):
        """更新变体数据"""
        if test_id not in self._tests:
            return
        
        for variant in self._tests[test_id]:
            if variant.variant_id == variant_id:
                variant.metrics.update(metrics)
                variant.sample_size = sample_size
                break
    
    def evaluate(self, test_id: str) -> ABTestResult:
        """评估测试结果"""
        variants = self._tests.get(test_id, [])
        
        if not variants:
            return ABTestResult(test_id=test_id)
        
        # 计算胜率
        probabilities = self._calculate_probabilities(variants)
        
        # 找出赢家
        winner = max(probabilities, key=probabilities.get)
        
        # 判断是否应该停止测试
        should_stop = any(p >= 0.95 for p in probabilities.values())
        
        # 计算置信度
        confidence = max(probabilities.values())
        
        return ABTestResult(
            test_id=test_id,
            winner=winner,
            variants=variants,
            probabilities=probabilities,
            should_stop=should_stop,
            confidence=confidence,
        )
    
    def _calculate_probabilities(self, variants: List[TestVariant]) -> Dict[str, float]:
        """计算胜率"""
        # 使用简化的 Bayesian 方法
        scores = {}
        
        for variant in variants:
            ctr = variant.metrics.get("ctr", 0.0)
            cvr = variant.metrics.get("cvr", 0.0)
            sample = variant.sample_size
            
            # 综合分数
            score = (ctr * 0.4 + cvr * 0.4) * min(sample / 1000, 1) + 0.1
            
            scores[variant.variant_id] = score
        
        # 归一化为概率
        total = sum(scores.values()) or 1
        probabilities = {k: v / total for k, v in scores.items()}
        
        return probabilities
    
    def evaluate_demo(self) -> ABTestResult:
        """演示 A/B 测试评估"""
        variants = [
            TestVariant("A", "creative_A", {"hook": "fast_action"}, {"ctr": 5.8, "cvr": 4.2}, 5000),
            TestVariant("B", "creative_B", {"hook": "surprise_reveal"}, {"ctr": 7.2, "cvr": 5.1}, 5000),
            TestVariant("C", "creative_C", {"hook": "instant_reward"}, {"ctr": 3.1, "cvr": 2.5}, 5000),
        ]
        
        self.create_test("test_hook_compare", variants)
        return self.evaluate("test_hook_compare")
