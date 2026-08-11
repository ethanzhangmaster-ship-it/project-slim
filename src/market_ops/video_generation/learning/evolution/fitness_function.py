"""Fitness Function - 适应度函数"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class FitnessScore:
    """适应度评分"""
    creative_id: str = ""
    fitness: float = 0.0
    ctr_component: float = 0.0
    ipm_component: float = 0.0
    purchase_component: float = 0.0
    roas_component: float = 0.0
    rank: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "fitness": round(self.fitness, 2),
            "ctr_component": round(self.ctr_component, 2),
            "ipm_component": round(self.ipm_component, 2),
            "purchase_component": round(self.purchase_component, 2),
            "roas_component": round(self.roas_component, 2),
            "rank": self.rank,
        }


class FitnessFunction:
    """适应度函数"""
    
    # 权重配置
    WEIGHTS = {
        "ctr": 0.25,
        "ipm": 0.25,
        "purchase_rate": 0.30,
        "roas": 0.20,
    }
    
    def calculate(
        self,
        creative_id: str,
        ctr: float = 0.0,
        ipm: float = 0.0,
        purchase_rate: float = 0.0,
        roas: float = 0.0,
    ) -> FitnessScore:
        """计算适应度
        
        Fitness Score = CTR × 0.25 + IPM × 0.25 + Purchase Rate × 0.30 + ROAS × 0.20
        
        Args:
            creative_id: 创意 ID
            ctr: Click Through Rate (%)
            ipm: Installs Per Mille
            purchase_rate: Purchase Rate (%)
            roas: Return On Ad Spend
        
        Returns:
            FitnessScore
        """
        # 标准化各指标 (0-100)
        ctr_norm = min(ctr * 10, 100)  # CTR 5% → 50
        ipm_norm = min(ipm / 10, 100)  # IPM 100 → 100
        purchase_norm = min(purchase_rate * 10, 100)  # Purchase 10% → 100
        roas_norm = min(roas * 50, 100)  # ROAS 2 → 100
        
        # 计算各分量
        ctr_component = ctr_norm * self.WEIGHTS["ctr"]
        ipm_component = ipm_norm * self.WEIGHTS["ipm"]
        purchase_component = purchase_norm * self.WEIGHTS["purchase_rate"]
        roas_component = roas_norm * self.WEIGHTS["roas"]
        
        # 总适应度
        fitness = ctr_component + ipm_component + purchase_component + roas_component
        
        return FitnessScore(
            creative_id=creative_id,
            fitness=fitness,
            ctr_component=ctr_component,
            ipm_component=ipm_component,
            purchase_component=purchase_component,
            roas_component=roas_component,
        )
    
    def rank_creatives(self, scores: Dict[str, FitnessScore]) -> List[FitnessScore]:
        """对创意排名"""
        sorted_scores = sorted(scores.values(), key=lambda s: s.fitness, reverse=True)
        
        for i, score in enumerate(sorted_scores):
            score.rank = i + 1
        
        return sorted_scores
    
    def select_survivors(
        self,
        scores: Dict[str, FitnessScore],
        survival_rate: float = 0.20,
    ) -> List[FitnessScore]:
        """选择幸存者（Top N%）"""
        ranked = self.rank_creatives(scores)
        survivor_count = max(1, int(len(ranked) * survival_rate))
        return ranked[:survivor_count]
    
    def is_eligible(self, score: FitnessScore, min_fitness: float = 50.0) -> bool:
        """判断是否合格"""
        return score.fitness >= min_fitness
